"""
Arsenal Fan 360 :: Lakeflow Spark Declarative Pipeline (SDP)
============================================================
The canonical medallion implementation for Arsenal Fan 360, expressed as a
Databricks Lakeflow Spark Declarative Pipeline using `from pyspark import pipelines as dp`.

    RAW CSV (UC Volume landing)
        -> Bronze  STREAMING tables      (Auto Loader / cloudFiles, append-only + lineage)
        -> Silver  materialized views    (cleaned, typed, de-duped) with native EXPECTATIONS
                   + *_quarantine views   (rows rejected by expectations, preserved not lost)
        -> Gold    materialized views     (gold_supporter_360, gold_supporter_activity)

Schemas (preserved from the original design):
    af360_bronze.bronze_*
    af360_silver.silver_*  (+ *_quarantine)
    af360_gold.gold_supporter_360, gold_supporter_activity

Expectation behaviour is chosen deliberately:
    * expect_all_or_drop -> malformed rows that must NOT reach Silver (dropped + quarantined)
    * expect_all         -> suspicious-but-usable rows (WARN only, kept)

Pipeline default target: catalog=serverless_stable_1acr1x_catalog, schema=af360_gold.
Cross-schema tables are written with fully-qualified `schema.table` names.

The ML/GenAI step (../ml/train_intent_model.py) writes model scores to
af360_gold.gold_supporter_scores; the operational layer (Lakebase sync + app
snapshot) joins gold_supporter_360 + gold_supporter_scores so the pipeline's
Gold stays cleanly declarative while ML remains a separate, MLflow-tracked step.
"""
from pyspark import pipelines as dp
from pyspark.sql.functions import col, current_timestamp

CATALOG = "serverless_stable_1acr1x_catalog"
LANDING = f"/Volumes/{CATALOG}/af360_bronze/landing"
# Auto Loader schema/checkpoint metadata (never the source volume)
SCHEMA_BASE = f"/Volumes/{CATALOG}/af360_bronze/pipeline_state/schemas"

KNOWN_EVENT_TYPES = (
    "viewed_match_ticket', 'viewed_home_shirt', 'viewed_away_shirt', 'added_to_cart', "
    "'abandoned_cart', 'viewed_membership', 'viewed_hospitality', 'viewed_stadium_tour', "
    "'viewed_fixtures', 'viewed_news"
)


# =============================================================================
# BRONZE  ::  streaming ingestion via Auto Loader (cloudFiles)
# =============================================================================
def _bronze(name: str, source: str):
    """Register a Bronze streaming table that Auto Loads a CSV source folder."""
    @dp.table(
        name=f"af360_bronze.{name}",
        comment=f"BRONZE: raw {source} extract, Auto Loaded from the landing volume (synthetic).",
    )
    def _ingest():
        return (
            spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "csv")
            .option("header", "true")
            .option("cloudFiles.inferColumnTypes", "true")
            .option("cloudFiles.schemaLocation", f"{SCHEMA_BASE}/{name}")
            .option("cloudFiles.schemaEvolutionMode", "rescue")
            .load(f"{LANDING}/{source}/")
            .withColumn("_source_file", col("_metadata.file_path"))
            .withColumn("_ingested_at", current_timestamp())
        )
    return _ingest


bronze_supporters       = _bronze("bronze_supporters", "supporters")
bronze_web_events       = _bronze("bronze_web_events", "web_events")
bronze_ecommerce_orders = _bronze("bronze_ecommerce_orders", "ecommerce_orders")
bronze_ticket_orders    = _bronze("bronze_ticket_orders", "ticket_orders")
bronze_marketing_events = _bronze("bronze_marketing_events", "marketing_events")


# =============================================================================
# SILVER  ::  cleaned / typed / de-duped, with EXPECTATIONS + quarantine
# =============================================================================

# ---- Supporters -------------------------------------------------------------
@dp.materialized_view(
    name="af360_silver.silver_supporters",
    comment="SILVER: conformed supporter dimension. Standardised casing, missing age_band -> Unknown, de-duplicated on supporter_id.",
)
@dp.expect_all_or_drop({"valid_supporter_id": "supporter_id IS NOT NULL"})
@dp.expect_all({
    "valid_membership_tier": "membership_tier IN ('None','Free','Silver','Gold','Red Member')",
    "sensible_registration_date": "registration_date IS NULL OR registration_date <= current_date()",
})
def silver_supporters():
    return spark.sql(f"""
        WITH cleaned AS (
          SELECT
            NULLIF(TRIM(CAST(supporter_id AS STRING)), '')                        AS supporter_id,
            INITCAP(TRIM(first_name))                                             AS first_name,
            NULLIF(TRIM(age_band), '')                                            AS age_band_raw,
            INITCAP(TRIM(country))                                                AS country,
            INITCAP(TRIM(city))                                                   AS city,
            NULLIF(TRIM(membership_tier), '')                                     AS membership_tier_raw,
            TRIM(favourite_player)                                                AS favourite_player,
            TRIM(favourite_product_category)                                      AS favourite_product_category,
            CAST(registration_date AS DATE)                                       AS registration_date,
            CAST(LOWER(CAST(email_opt_in AS STRING)) = 'true' AS BOOLEAN)         AS email_opt_in,
            CAST(LOWER(CAST(season_ticket_holder AS STRING)) = 'true' AS BOOLEAN) AS season_ticket_holder,
            ROW_NUMBER() OVER (PARTITION BY NULLIF(TRIM(CAST(supporter_id AS STRING)),'')
                               ORDER BY CAST(registration_date AS DATE)) AS rn
          FROM af360_bronze.bronze_supporters
        )
        SELECT supporter_id, first_name,
               COALESCE(age_band_raw, 'Unknown')     AS age_band,
               country, city,
               COALESCE(membership_tier_raw, 'None') AS membership_tier,
               favourite_player, favourite_product_category,
               registration_date, email_opt_in, season_ticket_holder
        FROM cleaned WHERE rn = 1
    """)


@dp.materialized_view(name="af360_silver.silver_supporters_quarantine",
                      comment="QUARANTINE: supporter rows rejected by expectations (missing supporter_id).")
def silver_supporters_quarantine():
    return spark.sql("""
        SELECT *, 'missing_supporter_id' AS _reject_reason
        FROM af360_bronze.bronze_supporters
        WHERE NULLIF(TRIM(CAST(supporter_id AS STRING)), '') IS NULL
    """)


# ---- Web events -------------------------------------------------------------
@dp.materialized_view(
    name="af360_silver.silver_web_events",
    comment="SILVER: conformed clickstream. Casted timestamps, lower-cased event_type, de-duplicated.",
)
@dp.expect_all_or_drop({
    "valid_supporter_id": "supporter_id IS NOT NULL",
    "valid_event_timestamp": "event_timestamp IS NOT NULL",
})
@dp.expect_all({"known_event_type": f"event_type IN ('{KNOWN_EVENT_TYPES}')"})
def silver_web_events():
    return spark.sql("""
        SELECT DISTINCT
          NULLIF(TRIM(CAST(supporter_id AS STRING)), '') AS supporter_id,
          CAST(event_timestamp AS TIMESTAMP)             AS event_timestamp,
          TRIM(page_type)                                AS page_type,
          TRIM(page_name)                                AS page_name,
          NULLIF(TRIM(product_id), '')                   AS product_id,
          NULLIF(TRIM(match_id), '')                     AS match_id,
          TRIM(session_id)                               AS session_id,
          LOWER(TRIM(event_type))                        AS event_type
        FROM af360_bronze.bronze_web_events
    """)


@dp.materialized_view(name="af360_silver.silver_web_events_quarantine",
                      comment="QUARANTINE: web events rejected by expectations (missing supporter_id or timestamp).")
def silver_web_events_quarantine():
    return spark.sql("""
        SELECT *, CASE
                    WHEN NULLIF(TRIM(CAST(supporter_id AS STRING)),'') IS NULL THEN 'missing_supporter_id'
                    WHEN CAST(event_timestamp AS TIMESTAMP) IS NULL THEN 'invalid_event_timestamp'
                    ELSE 'other' END AS _reject_reason
        FROM af360_bronze.bronze_web_events
        WHERE NULLIF(TRIM(CAST(supporter_id AS STRING)),'') IS NULL
           OR CAST(event_timestamp AS TIMESTAMP) IS NULL
    """)


# ---- Ecommerce orders (de-duplicated on order_id) ---------------------------
@dp.materialized_view(
    name="af360_silver.silver_ecommerce_orders",
    comment="SILVER: conformed merchandise orders. De-duplicated on order_id (removes replayed transactions).",
)
@dp.expect_all_or_drop({
    "valid_order_id": "order_id IS NOT NULL",
    "valid_supporter_id": "supporter_id IS NOT NULL",
    "non_negative_revenue": "revenue >= 0",
})
def silver_ecommerce_orders():
    return spark.sql("""
        WITH ranked AS (
          SELECT
            NULLIF(TRIM(CAST(supporter_id AS STRING)), '') AS supporter_id,
            NULLIF(TRIM(CAST(order_id AS STRING)), '')     AS order_id,
            TRIM(product)                                  AS product,
            TRIM(category)                                 AS category,
            CAST(quantity AS INT)                          AS quantity,
            CAST(revenue AS DOUBLE)                        AS revenue,
            CAST(purchase_timestamp AS TIMESTAMP)          AS purchase_timestamp,
            ROW_NUMBER() OVER (PARTITION BY NULLIF(TRIM(CAST(order_id AS STRING)),'')
                               ORDER BY CAST(purchase_timestamp AS TIMESTAMP)) AS rn
          FROM af360_bronze.bronze_ecommerce_orders
        )
        SELECT supporter_id, order_id, product, category, quantity, revenue, purchase_timestamp
        FROM ranked WHERE rn = 1
    """)


@dp.materialized_view(name="af360_silver.silver_ecommerce_orders_quarantine",
                      comment="QUARANTINE: ecommerce orders rejected by expectations (missing ids or negative revenue).")
def silver_ecommerce_orders_quarantine():
    return spark.sql("""
        SELECT *, CASE
                    WHEN NULLIF(TRIM(CAST(order_id AS STRING)),'') IS NULL THEN 'missing_order_id'
                    WHEN NULLIF(TRIM(CAST(supporter_id AS STRING)),'') IS NULL THEN 'missing_supporter_id'
                    WHEN CAST(revenue AS DOUBLE) < 0 THEN 'negative_revenue'
                    ELSE 'other' END AS _reject_reason
        FROM af360_bronze.bronze_ecommerce_orders
        WHERE NULLIF(TRIM(CAST(order_id AS STRING)),'') IS NULL
           OR NULLIF(TRIM(CAST(supporter_id AS STRING)),'') IS NULL
           OR CAST(revenue AS DOUBLE) < 0
    """)


# ---- Ticket orders ----------------------------------------------------------
@dp.materialized_view(
    name="af360_silver.silver_ticket_orders",
    comment="SILVER: conformed matchday tickets. Casted price/attended, de-duplicated.",
)
@dp.expect_all_or_drop({
    "valid_supporter_id": "supporter_id IS NOT NULL",
    "non_negative_price": "ticket_price >= 0",
})
@dp.expect_all({"match_populated": "match IS NOT NULL AND match <> ''"})
def silver_ticket_orders():
    return spark.sql("""
        SELECT DISTINCT
          NULLIF(TRIM(CAST(supporter_id AS STRING)), '') AS supporter_id,
          TRIM(match)                                    AS match,
          TRIM(competition)                              AS competition,
          TRIM(ticket_type)                              AS ticket_type,
          CAST(ticket_price AS DOUBLE)                   AS ticket_price,
          CAST(purchase_timestamp AS TIMESTAMP)          AS purchase_timestamp,
          CAST(LOWER(CAST(attended AS STRING)) = 'true' AS BOOLEAN) AS attended
        FROM af360_bronze.bronze_ticket_orders
    """)


@dp.materialized_view(name="af360_silver.silver_ticket_orders_quarantine",
                      comment="QUARANTINE: ticket orders rejected by expectations (missing supporter_id or negative price).")
def silver_ticket_orders_quarantine():
    return spark.sql("""
        SELECT *, CASE
                    WHEN NULLIF(TRIM(CAST(supporter_id AS STRING)),'') IS NULL THEN 'missing_supporter_id'
                    WHEN CAST(ticket_price AS DOUBLE) < 0 THEN 'negative_price'
                    ELSE 'other' END AS _reject_reason
        FROM af360_bronze.bronze_ticket_orders
        WHERE NULLIF(TRIM(CAST(supporter_id AS STRING)),'') IS NULL
           OR CAST(ticket_price AS DOUBLE) < 0
    """)


# ---- Marketing events -------------------------------------------------------
@dp.materialized_view(
    name="af360_silver.silver_marketing_events",
    comment="SILVER: conformed marketing interactions. Casted booleans/timestamps, de-duplicated.",
)
@dp.expect_all_or_drop({
    "valid_supporter_id": "supporter_id IS NOT NULL",
    "valid_event_timestamp": "event_timestamp IS NOT NULL",
})
def silver_marketing_events():
    return spark.sql("""
        SELECT DISTINCT
          NULLIF(TRIM(CAST(supporter_id AS STRING)), '') AS supporter_id,
          TRIM(campaign)                                 AS campaign,
          CAST(LOWER(CAST(sent AS STRING)) = 'true' AS BOOLEAN)      AS sent,
          CAST(LOWER(CAST(opened AS STRING)) = 'true' AS BOOLEAN)    AS opened,
          CAST(LOWER(CAST(clicked AS STRING)) = 'true' AS BOOLEAN)   AS clicked,
          CAST(LOWER(CAST(converted AS STRING)) = 'true' AS BOOLEAN) AS converted,
          CAST(timestamp AS TIMESTAMP)                   AS event_timestamp
        FROM af360_bronze.bronze_marketing_events
    """)


@dp.materialized_view(name="af360_silver.silver_marketing_events_quarantine",
                      comment="QUARANTINE: marketing events rejected by expectations (missing supporter_id or timestamp).")
def silver_marketing_events_quarantine():
    return spark.sql("""
        SELECT *, CASE
                    WHEN NULLIF(TRIM(CAST(supporter_id AS STRING)),'') IS NULL THEN 'missing_supporter_id'
                    WHEN CAST(timestamp AS TIMESTAMP) IS NULL THEN 'invalid_timestamp'
                    ELSE 'other' END AS _reject_reason
        FROM af360_bronze.bronze_marketing_events
        WHERE NULLIF(TRIM(CAST(supporter_id AS STRING)),'') IS NULL
           OR CAST(timestamp AS TIMESTAMP) IS NULL
    """)


# =============================================================================
# GOLD  ::  Customer 360 + activity feed (materialized views)
# =============================================================================
@dp.materialized_view(
    name="gold_supporter_360",   # default schema = af360_gold
    comment="GOLD: Customer 360 - one row per supporter with engagement features. Intent score, Next Best Action and reason prefer the ML overlay (af360_gold.gold_supporter_scores) and fall back to a rule-based baseline when a supporter has no ML score.",
)
@dp.expect_all({"one_row_per_supporter": "supporter_id IS NOT NULL"})
def gold_supporter_360():
    return spark.sql("""
        WITH params AS (SELECT TIMESTAMP '2025-09-20 12:00:00' AS ref_ts),
        web AS (
          SELECT supporter_id,
            COUNT(DISTINCT CASE WHEN event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN session_id END) AS website_sessions_30d,
            COUNT(CASE WHEN page_type='Store' AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS product_views_30d,
            COUNT(CASE WHEN event_type='viewed_match_ticket' AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS ticket_views_30d,
            COUNT(CASE WHEN event_type='abandoned_cart' AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS cart_abandons_30d,
            COUNT(CASE WHEN event_type='viewed_membership' AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS membership_views_30d,
            COUNT(CASE WHEN event_type='viewed_hospitality' AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS hospitality_views_30d,
            MAX(event_timestamp) AS last_web_event
          FROM af360_silver.silver_web_events GROUP BY supporter_id
        ),
        ecom AS (
          SELECT supporter_id, ROUND(SUM(revenue),2) AS total_merchandise_spend,
                 COUNT(*) AS merchandise_orders, MAX(purchase_timestamp) AS last_merch_purchase
          FROM af360_silver.silver_ecommerce_orders GROUP BY supporter_id
        ),
        tix AS (
          SELECT supporter_id, ROUND(SUM(ticket_price),2) AS total_ticket_spend,
                 COUNT(*) AS ticket_purchases,
                 SUM(CASE WHEN attended THEN 1 ELSE 0 END) AS matches_attended,
                 MAX(CASE WHEN attended THEN purchase_timestamp END) AS last_match_attended,
                 MAX(purchase_timestamp) AS last_ticket_purchase
          FROM af360_silver.silver_ticket_orders GROUP BY supporter_id
        ),
        mkt AS (
          SELECT supporter_id,
            COUNT(CASE WHEN opened  AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS marketing_opens_30d,
            COUNT(CASE WHEN clicked AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS marketing_clicks_30d,
            MAX(event_timestamp) AS last_marketing_event
          FROM af360_silver.silver_marketing_events GROUP BY supporter_id
        ),
        base AS (
          SELECT s.supporter_id, s.first_name, s.age_band, s.country, s.city,
            s.membership_tier, s.favourite_player, s.favourite_product_category,
            s.registration_date, s.email_opt_in, s.season_ticket_holder,
            COALESCE(t.total_ticket_spend,0) AS total_ticket_spend,
            COALESCE(e.total_merchandise_spend,0) AS total_merchandise_spend,
            COALESCE(t.matches_attended,0) AS matches_attended, t.last_match_attended,
            COALESCE(t.ticket_purchases,0) AS ticket_purchases,
            COALESCE(e.merchandise_orders,0) AS merchandise_orders,
            COALESCE(w.website_sessions_30d,0) AS website_sessions_30d,
            COALESCE(w.product_views_30d,0) AS product_views_30d,
            COALESCE(w.ticket_views_30d,0) AS ticket_views_30d,
            COALESCE(w.cart_abandons_30d,0) AS cart_abandons_30d,
            COALESCE(w.membership_views_30d,0) AS membership_views_30d,
            COALESCE(w.hospitality_views_30d,0) AS hospitality_views_30d,
            COALESCE(m.marketing_opens_30d,0) AS marketing_opens_30d,
            COALESCE(m.marketing_clicks_30d,0) AS marketing_clicks_30d,
            (SELECT ref_ts FROM params) AS ref_ts,
            GREATEST(COALESCE(e.last_merch_purchase, TIMESTAMP '2000-01-01'),
                     COALESCE(t.last_ticket_purchase, TIMESTAMP '2000-01-01')) AS last_purchase_ts,
            GREATEST(COALESCE(w.last_web_event, TIMESTAMP '2000-01-01'),
                     COALESCE(e.last_merch_purchase, TIMESTAMP '2000-01-01'),
                     COALESCE(t.last_ticket_purchase, TIMESTAMP '2000-01-01'),
                     COALESCE(m.last_marketing_event, TIMESTAMP '2000-01-01')) AS last_activity_ts
          FROM af360_silver.silver_supporters s
          LEFT JOIN web w ON s.supporter_id=w.supporter_id
          LEFT JOIN ecom e ON s.supporter_id=e.supporter_id
          LEFT JOIN tix t ON s.supporter_id=t.supporter_id
          LEFT JOIN mkt m ON s.supporter_id=m.supporter_id
        ),
        scored AS (
          SELECT *,
            ROUND(total_ticket_spend + total_merchandise_spend,2) AS total_customer_value,
            CASE WHEN last_purchase_ts=TIMESTAMP '2000-01-01' THEN 999 ELSE DATEDIFF(ref_ts,last_purchase_ts) END AS days_since_last_purchase,
            CASE WHEN last_activity_ts=TIMESTAMP '2000-01-01' THEN 999 ELSE DATEDIFF(ref_ts,last_activity_ts) END AS days_since_last_activity,
            LEAST(100, GREATEST(0, ROUND(
                website_sessions_30d*3.0 + product_views_30d*1.2 + ticket_views_30d*2.0
              + marketing_opens_30d*2.0 + matches_attended*5.0
              - GREATEST(0,(CASE WHEN last_activity_ts=TIMESTAMP '2000-01-01' THEN 999 ELSE DATEDIFF(ref_ts,last_activity_ts) END)-30)*0.3))) AS engagement_score,
            LEAST(100, GREATEST(0, ROUND(
                ticket_views_30d*6.0 + product_views_30d*2.0 + cart_abandons_30d*8.0
              + membership_views_30d*5.0 + hospitality_views_30d*6.0 + marketing_clicks_30d*4.0
              + matches_attended*2.0
              - (CASE WHEN last_purchase_ts=TIMESTAMP '2000-01-01' THEN 60 ELSE DATEDIFF(ref_ts,last_purchase_ts) END)*0.3))) AS purchase_intent_score
          FROM base
        ),
        baseline AS (
          SELECT scored.*,
            CASE
              WHEN ticket_views_30d >= 3 AND ticket_purchases = 0 THEN 'Match Ticket'
              WHEN matches_attended >= 4 AND total_customer_value >= 400 THEN 'Hospitality'
              WHEN matches_attended >= 3 AND membership_tier IN ('None','Free') THEN 'Membership Upgrade'
              WHEN (product_views_30d >= 4 OR cart_abandons_30d >= 1) THEN 'Arsenal Shirt / Merchandise'
              WHEN membership_views_30d >= 1 AND membership_tier IN ('None','Free') THEN 'Membership Upgrade'
              WHEN days_since_last_activity >= 60 THEN 'Re-engagement Campaign'
              WHEN hospitality_views_30d >= 1 THEN 'Hospitality'
              ELSE 'Stadium Tour'
            END AS baseline_nba,
            CASE
              WHEN ticket_views_30d >= 3 AND ticket_purchases = 0
                THEN CONCAT(first_name,' viewed match tickets ',ticket_views_30d,' times in the last 30 days but has not purchased.')
              WHEN matches_attended >= 4 AND total_customer_value >= 400
                THEN CONCAT(first_name,' attended ',matches_attended,' matches and has spent £',CAST(ROUND(total_customer_value) AS INT),' - a strong hospitality candidate.')
              WHEN matches_attended >= 3 AND membership_tier IN ('None','Free')
                THEN CONCAT(first_name,' attended ',matches_attended,' matches this season but is not a paying member.')
              WHEN (product_views_30d >= 4 OR cart_abandons_30d >= 1)
                THEN CONCAT(first_name,' browsed merchandise ',product_views_30d,' times with ',cart_abandons_30d,' abandoned baskets recently.')
              WHEN membership_views_30d >= 1 AND membership_tier IN ('None','Free')
                THEN CONCAT(first_name,' visited membership pages ',membership_views_30d,' times in the last 30 days.')
              WHEN days_since_last_activity >= 60
                THEN CONCAT(first_name,' has had no meaningful interaction for ',days_since_last_activity,' days.')
              WHEN hospitality_views_30d >= 1
                THEN CONCAT(first_name,' has shown interest in hospitality experiences recently.')
              ELSE CONCAT(first_name,' is an engaged supporter - nurture with an experience offer.')
            END AS baseline_reason
          FROM scored
        )
        -- Prefer the ML overlay (af360_gold.gold_supporter_scores) when present, so
        -- the served intent/NBA/reason are ML-driven and identical everywhere
        -- (app, Genie, evidence). ML scores feed back on each pipeline refresh.
        SELECT
          b.supporter_id, b.first_name, b.age_band, b.country, b.city, b.membership_tier,
          b.favourite_player, b.favourite_product_category, b.registration_date,
          b.email_opt_in, b.season_ticket_holder,
          b.total_ticket_spend, b.total_merchandise_spend, b.total_customer_value,
          b.matches_attended, b.last_match_attended, b.ticket_purchases, b.merchandise_orders,
          b.website_sessions_30d, b.product_views_30d, b.ticket_views_30d, b.cart_abandons_30d,
          b.membership_views_30d, b.hospitality_views_30d, b.marketing_opens_30d, b.marketing_clicks_30d,
          b.days_since_last_purchase, b.days_since_last_activity, b.engagement_score,
          CAST(COALESCE(ml.purchase_intent_score, b.purchase_intent_score) AS INT) AS purchase_intent_score,
          COALESCE(ml.recommended_next_action, b.baseline_nba)  AS recommended_next_action,
          COALESCE(ml.genai_reason, b.baseline_reason)          AS recommendation_reason,
          CAST('2025-09-20 12:00:00' AS TIMESTAMP) AS scored_at
        FROM baseline b
        LEFT JOIN af360_gold.gold_supporter_scores ml ON b.supporter_id = ml.supporter_id
    """)


@dp.materialized_view(
    name="gold_supporter_activity",
    comment="GOLD: normalised cross-channel supporter activity feed powering the Supporter 360 timeline.",
)
def gold_supporter_activity():
    return spark.sql("""
        SELECT supporter_id, 'web' AS channel, event_type AS activity_type, page_name AS activity_detail, event_timestamp AS activity_timestamp
        FROM af360_silver.silver_web_events
        UNION ALL
        SELECT supporter_id, 'merch', 'purchase', product, purchase_timestamp
        FROM af360_silver.silver_ecommerce_orders
        UNION ALL
        SELECT supporter_id, 'ticketing', CASE WHEN attended THEN 'attended' ELSE 'ticket_purchase' END, match, purchase_timestamp
        FROM af360_silver.silver_ticket_orders
        UNION ALL
        SELECT supporter_id, 'marketing', CASE WHEN converted THEN 'converted' WHEN clicked THEN 'clicked' WHEN opened THEN 'opened' ELSE 'sent' END, campaign, event_timestamp
        FROM af360_silver.silver_marketing_events
    """)
