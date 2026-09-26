-- =============================================================================
-- Arsenal Fan 360 :: LAKEFLOW  ::  GOLD  (Customer 360)
-- -----------------------------------------------------------------------------
-- Build the one-row-per-supporter Customer 360 feature table plus a recent
-- activity feed for the application. Scores here are transparent, rule-based
-- baselines; the ML + GenAI step (see /ml) overwrites purchase_intent_score
-- and recommendation_reason with the model probability and LLM explanation.
--
-- Reference "now" for the synthetic dataset: 2025-09-20 12:00:00
-- Target: <cat>.af360_gold.gold_supporter_360, gold_supporter_activity
-- =============================================================================

CREATE OR REPLACE TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360 AS
WITH params AS (
  SELECT TIMESTAMP '2025-09-20 12:00:00' AS ref_ts
),
web AS (
  SELECT
    supporter_id,
    COUNT(DISTINCT CASE WHEN event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN session_id END) AS website_sessions_30d,
    COUNT(CASE WHEN page_type = 'Store' AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS product_views_30d,
    COUNT(CASE WHEN event_type = 'viewed_match_ticket' AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS ticket_views_30d,
    COUNT(CASE WHEN event_type = 'abandoned_cart' AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS cart_abandons_30d,
    COUNT(CASE WHEN event_type = 'viewed_membership' AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS membership_views_30d,
    COUNT(CASE WHEN event_type = 'viewed_hospitality' AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS hospitality_views_30d,
    MAX(event_timestamp) AS last_web_event
  FROM serverless_stable_1acr1x_catalog.af360_silver.silver_web_events
  GROUP BY supporter_id
),
ecom AS (
  SELECT
    supporter_id,
    ROUND(SUM(revenue), 2) AS total_merchandise_spend,
    COUNT(*) AS merchandise_orders,
    MAX(purchase_timestamp) AS last_merch_purchase
  FROM serverless_stable_1acr1x_catalog.af360_silver.silver_ecommerce_orders
  GROUP BY supporter_id
),
tix AS (
  SELECT
    supporter_id,
    ROUND(SUM(ticket_price), 2) AS total_ticket_spend,
    COUNT(*) AS ticket_purchases,
    SUM(CASE WHEN attended THEN 1 ELSE 0 END) AS matches_attended,
    MAX(CASE WHEN attended THEN purchase_timestamp END) AS last_match_attended,
    MAX(purchase_timestamp) AS last_ticket_purchase
  FROM serverless_stable_1acr1x_catalog.af360_silver.silver_ticket_orders
  GROUP BY supporter_id
),
mkt AS (
  SELECT
    supporter_id,
    COUNT(CASE WHEN opened  AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS marketing_opens_30d,
    COUNT(CASE WHEN clicked AND event_timestamp >= (SELECT ref_ts FROM params) - INTERVAL 30 DAYS THEN 1 END) AS marketing_clicks_30d,
    MAX(event_timestamp) AS last_marketing_event
  FROM serverless_stable_1acr1x_catalog.af360_silver.silver_marketing_events
  GROUP BY supporter_id
),
base AS (
  SELECT
    s.supporter_id, s.first_name, s.age_band, s.country, s.city,
    s.membership_tier, s.favourite_player, s.favourite_product_category,
    s.registration_date, s.email_opt_in, s.season_ticket_holder,
    COALESCE(t.total_ticket_spend, 0)        AS total_ticket_spend,
    COALESCE(e.total_merchandise_spend, 0)   AS total_merchandise_spend,
    COALESCE(t.matches_attended, 0)          AS matches_attended,
    t.last_match_attended,
    COALESCE(t.ticket_purchases, 0)          AS ticket_purchases,
    COALESCE(e.merchandise_orders, 0)        AS merchandise_orders,
    COALESCE(w.website_sessions_30d, 0)      AS website_sessions_30d,
    COALESCE(w.product_views_30d, 0)         AS product_views_30d,
    COALESCE(w.ticket_views_30d, 0)          AS ticket_views_30d,
    COALESCE(w.cart_abandons_30d, 0)         AS cart_abandons_30d,
    COALESCE(w.membership_views_30d, 0)      AS membership_views_30d,
    COALESCE(w.hospitality_views_30d, 0)     AS hospitality_views_30d,
    COALESCE(m.marketing_opens_30d, 0)       AS marketing_opens_30d,
    COALESCE(m.marketing_clicks_30d, 0)      AS marketing_clicks_30d,
    (SELECT ref_ts FROM params) AS ref_ts,
    GREATEST(
      COALESCE(e.last_merch_purchase, TIMESTAMP '2000-01-01'),
      COALESCE(t.last_ticket_purchase, TIMESTAMP '2000-01-01')
    ) AS last_purchase_ts,
    GREATEST(
      COALESCE(w.last_web_event, TIMESTAMP '2000-01-01'),
      COALESCE(e.last_merch_purchase, TIMESTAMP '2000-01-01'),
      COALESCE(t.last_ticket_purchase, TIMESTAMP '2000-01-01'),
      COALESCE(m.last_marketing_event, TIMESTAMP '2000-01-01')
    ) AS last_activity_ts
  FROM serverless_stable_1acr1x_catalog.af360_silver.silver_supporters s
  LEFT JOIN web  w ON s.supporter_id = w.supporter_id
  LEFT JOIN ecom e ON s.supporter_id = e.supporter_id
  LEFT JOIN tix  t ON s.supporter_id = t.supporter_id
  LEFT JOIN mkt  m ON s.supporter_id = m.supporter_id
),
scored AS (
  SELECT *,
    ROUND(total_ticket_spend + total_merchandise_spend, 2) AS total_customer_value,
    CASE WHEN last_purchase_ts = TIMESTAMP '2000-01-01' THEN 999
         ELSE DATEDIFF(ref_ts, last_purchase_ts) END AS days_since_last_purchase,
    CASE WHEN last_activity_ts = TIMESTAMP '2000-01-01' THEN 999
         ELSE DATEDIFF(ref_ts, last_activity_ts) END AS days_since_last_activity,
    -- Engagement score (0-100): breadth & recency of engagement
    LEAST(100, GREATEST(0, ROUND(
        website_sessions_30d * 3.0
      + product_views_30d    * 1.2
      + ticket_views_30d     * 2.0
      + marketing_opens_30d  * 2.0
      + matches_attended     * 5.0
      - GREATEST(0, (CASE WHEN last_activity_ts = TIMESTAMP '2000-01-01' THEN 999 ELSE DATEDIFF(ref_ts, last_activity_ts) END) - 30) * 0.3
    ))) AS engagement_score,
    -- Purchase intent baseline (0-100): forward-looking buy signal
    LEAST(100, GREATEST(0, ROUND(
        ticket_views_30d      * 6.0
      + product_views_30d     * 2.0
      + cart_abandons_30d     * 8.0
      + membership_views_30d  * 5.0
      + hospitality_views_30d * 6.0
      + marketing_clicks_30d  * 4.0
      + matches_attended      * 2.0
      - (CASE WHEN last_purchase_ts = TIMESTAMP '2000-01-01' THEN 60 ELSE DATEDIFF(ref_ts, last_purchase_ts) END) * 0.3
    ))) AS purchase_intent_score
  FROM base
)
SELECT
  supporter_id, first_name, age_band, country, city, membership_tier,
  favourite_player, favourite_product_category, registration_date,
  email_opt_in, season_ticket_holder,
  total_ticket_spend, total_merchandise_spend, total_customer_value,
  matches_attended, last_match_attended, ticket_purchases, merchandise_orders,
  website_sessions_30d, product_views_30d, ticket_views_30d, cart_abandons_30d,
  membership_views_30d, hospitality_views_30d,
  marketing_opens_30d, marketing_clicks_30d,
  days_since_last_purchase, days_since_last_activity,
  engagement_score, purchase_intent_score,
  -- Rule-based Next Best Action (priority order)
  CASE
    WHEN ticket_views_30d >= 3 AND ticket_purchases = 0
      THEN 'Match Ticket'
    WHEN matches_attended >= 4 AND total_customer_value >= 400
      THEN 'Hospitality'
    WHEN matches_attended >= 3 AND membership_tier IN ('None', 'Free')
      THEN 'Membership Upgrade'
    WHEN (product_views_30d >= 4 OR cart_abandons_30d >= 1)
      THEN 'Arsenal Shirt / Merchandise'
    WHEN membership_views_30d >= 1 AND membership_tier IN ('None', 'Free')
      THEN 'Membership Upgrade'
    WHEN days_since_last_activity >= 60
      THEN 'Re-engagement Campaign'
    WHEN hospitality_views_30d >= 1
      THEN 'Hospitality'
    ELSE 'Stadium Tour'
  END AS recommended_next_action,
  -- Baseline explanation (overwritten by GenAI in the ML step)
  CASE
    WHEN ticket_views_30d >= 3 AND ticket_purchases = 0
      THEN CONCAT(first_name, ' viewed match tickets ', ticket_views_30d, ' times in the last 30 days but has not purchased.')
    WHEN matches_attended >= 4 AND total_customer_value >= 400
      THEN CONCAT(first_name, ' attended ', matches_attended, ' matches and has spent £', CAST(ROUND(total_customer_value) AS INT), ' - a strong hospitality candidate.')
    WHEN matches_attended >= 3 AND membership_tier IN ('None', 'Free')
      THEN CONCAT(first_name, ' attended ', matches_attended, ' matches this season but is not a paying member.')
    WHEN (product_views_30d >= 4 OR cart_abandons_30d >= 1)
      THEN CONCAT(first_name, ' browsed merchandise ', product_views_30d, ' times with ', cart_abandons_30d, ' abandoned baskets recently.')
    WHEN membership_views_30d >= 1 AND membership_tier IN ('None', 'Free')
      THEN CONCAT(first_name, ' visited membership pages ', membership_views_30d, ' times in the last 30 days.')
    WHEN days_since_last_activity >= 60
      THEN CONCAT(first_name, ' has had no meaningful interaction for ', days_since_last_activity, ' days.')
    WHEN hospitality_views_30d >= 1
      THEN CONCAT(first_name, ' has shown interest in hospitality experiences recently.')
    ELSE CONCAT(first_name, ' is an engaged supporter - nurture with an experience offer.')
  END AS recommendation_reason,
  CAST('2025-09-20 12:00:00' AS TIMESTAMP) AS scored_at
FROM scored;

COMMENT ON TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360
  IS 'GOLD: Customer 360 - one row per supporter with engagement/intent features, rule-based Next Best Action, and (post-ML) model intent score + GenAI explanation.';

-- =============================================================================
-- gold_supporter_activity : normalised recent activity feed for the app
-- =============================================================================
CREATE OR REPLACE TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_activity AS
SELECT supporter_id, 'web'       AS channel, event_type AS activity_type, page_name AS activity_detail, event_timestamp AS activity_timestamp
FROM serverless_stable_1acr1x_catalog.af360_silver.silver_web_events
UNION ALL
SELECT supporter_id, 'merch'     AS channel, 'purchase' AS activity_type, product AS activity_detail, purchase_timestamp AS activity_timestamp
FROM serverless_stable_1acr1x_catalog.af360_silver.silver_ecommerce_orders
UNION ALL
SELECT supporter_id, 'ticketing' AS channel, CASE WHEN attended THEN 'attended' ELSE 'ticket_purchase' END AS activity_type, match AS activity_detail, purchase_timestamp AS activity_timestamp
FROM serverless_stable_1acr1x_catalog.af360_silver.silver_ticket_orders
UNION ALL
SELECT supporter_id, 'marketing' AS channel, CASE WHEN converted THEN 'converted' WHEN clicked THEN 'clicked' WHEN opened THEN 'opened' ELSE 'sent' END AS activity_type, campaign AS activity_detail, event_timestamp AS activity_timestamp
FROM serverless_stable_1acr1x_catalog.af360_silver.silver_marketing_events;

COMMENT ON TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_activity
  IS 'GOLD: normalised cross-channel supporter activity feed powering the Supporter 360 timeline in the app.';
