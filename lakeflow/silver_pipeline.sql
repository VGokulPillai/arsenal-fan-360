-- =============================================================================
-- Arsenal Fan 360 :: LAKEFLOW  ::  SILVER
-- -----------------------------------------------------------------------------
-- Clean & standardise Bronze into conformed Silver tables:
--   * cast timestamps / booleans / numerics
--   * standardise categories & casing (country, membership_tier, event_type)
--   * handle missing values
--   * de-duplicate transactions (ecommerce order_id, etc.)
-- Target: <cat>.af360_silver.silver_*
-- =============================================================================

-- ---- Supporters ------------------------------------------------------------
CREATE OR REPLACE TABLE serverless_stable_1acr1x_catalog.af360_silver.silver_supporters AS
WITH cleaned AS (
  SELECT
    CAST(supporter_id AS STRING)                                   AS supporter_id,
    INITCAP(TRIM(first_name))                                      AS first_name,
    NULLIF(TRIM(age_band), '')                                     AS age_band_raw,
    INITCAP(TRIM(country))                                         AS country,
    INITCAP(TRIM(city))                                            AS city,
    NULLIF(TRIM(membership_tier), '')                              AS membership_tier_raw,
    TRIM(favourite_player)                                         AS favourite_player,
    TRIM(favourite_product_category)                               AS favourite_product_category,
    CAST(registration_date AS DATE)                                AS registration_date,
    CAST(LOWER(CAST(email_opt_in AS STRING)) = 'true' AS BOOLEAN)  AS email_opt_in,
    CAST(LOWER(CAST(season_ticket_holder AS STRING)) = 'true' AS BOOLEAN) AS season_ticket_holder,
    ROW_NUMBER() OVER (PARTITION BY supporter_id ORDER BY registration_date) AS rn
  FROM serverless_stable_1acr1x_catalog.af360_bronze.bronze_supporters
  WHERE supporter_id IS NOT NULL
)
SELECT
  supporter_id,
  first_name,
  COALESCE(age_band_raw, 'Unknown')      AS age_band,
  country,
  city,
  COALESCE(membership_tier_raw, 'None')  AS membership_tier,
  favourite_player,
  favourite_product_category,
  registration_date,
  email_opt_in,
  season_ticket_holder
FROM cleaned
WHERE rn = 1;
COMMENT ON TABLE serverless_stable_1acr1x_catalog.af360_silver.silver_supporters
  IS 'SILVER: conformed supporter dimension. Standardised country/tier casing, missing age_band -> Unknown, de-duplicated on supporter_id.';

-- ---- Web events ------------------------------------------------------------
CREATE OR REPLACE TABLE serverless_stable_1acr1x_catalog.af360_silver.silver_web_events AS
SELECT DISTINCT
  CAST(supporter_id AS STRING)                 AS supporter_id,
  CAST(event_timestamp AS TIMESTAMP)           AS event_timestamp,
  TRIM(page_type)                              AS page_type,
  TRIM(page_name)                              AS page_name,
  NULLIF(TRIM(product_id), '')                 AS product_id,
  NULLIF(TRIM(match_id), '')                   AS match_id,
  TRIM(session_id)                             AS session_id,
  LOWER(TRIM(event_type))                      AS event_type
FROM serverless_stable_1acr1x_catalog.af360_bronze.bronze_web_events
WHERE supporter_id IS NOT NULL AND event_timestamp IS NOT NULL;
COMMENT ON TABLE serverless_stable_1acr1x_catalog.af360_silver.silver_web_events
  IS 'SILVER: conformed clickstream events. Casted timestamps, lower-cased event_type, de-duplicated.';

-- ---- Ecommerce orders (de-duplicated on order_id) --------------------------
CREATE OR REPLACE TABLE serverless_stable_1acr1x_catalog.af360_silver.silver_ecommerce_orders AS
WITH ranked AS (
  SELECT
    CAST(supporter_id AS STRING)               AS supporter_id,
    CAST(order_id AS STRING)                    AS order_id,
    TRIM(product)                               AS product,
    TRIM(category)                              AS category,
    CAST(quantity AS INT)                       AS quantity,
    CAST(revenue AS DOUBLE)                      AS revenue,
    CAST(purchase_timestamp AS TIMESTAMP)        AS purchase_timestamp,
    ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY purchase_timestamp) AS rn
  FROM serverless_stable_1acr1x_catalog.af360_bronze.bronze_ecommerce_orders
  WHERE supporter_id IS NOT NULL AND order_id IS NOT NULL
)
SELECT supporter_id, order_id, product, category, quantity, revenue, purchase_timestamp
FROM ranked WHERE rn = 1;
COMMENT ON TABLE serverless_stable_1acr1x_catalog.af360_silver.silver_ecommerce_orders
  IS 'SILVER: conformed merchandise orders. De-duplicated on order_id (removes replayed transactions).';

-- ---- Ticket orders ---------------------------------------------------------
CREATE OR REPLACE TABLE serverless_stable_1acr1x_catalog.af360_silver.silver_ticket_orders AS
SELECT DISTINCT
  CAST(supporter_id AS STRING)                 AS supporter_id,
  TRIM(match)                                  AS match,
  TRIM(competition)                            AS competition,
  TRIM(ticket_type)                            AS ticket_type,
  CAST(ticket_price AS DOUBLE)                 AS ticket_price,
  CAST(purchase_timestamp AS TIMESTAMP)         AS purchase_timestamp,
  CAST(LOWER(CAST(attended AS STRING)) = 'true' AS BOOLEAN) AS attended
FROM serverless_stable_1acr1x_catalog.af360_bronze.bronze_ticket_orders
WHERE supporter_id IS NOT NULL;
COMMENT ON TABLE serverless_stable_1acr1x_catalog.af360_silver.silver_ticket_orders
  IS 'SILVER: conformed matchday ticket transactions. Casted price/attended, de-duplicated.';

-- ---- Marketing events ------------------------------------------------------
CREATE OR REPLACE TABLE serverless_stable_1acr1x_catalog.af360_silver.silver_marketing_events AS
SELECT DISTINCT
  CAST(supporter_id AS STRING)                 AS supporter_id,
  TRIM(campaign)                               AS campaign,
  CAST(LOWER(CAST(sent AS STRING)) = 'true' AS BOOLEAN)      AS sent,
  CAST(LOWER(CAST(opened AS STRING)) = 'true' AS BOOLEAN)    AS opened,
  CAST(LOWER(CAST(clicked AS STRING)) = 'true' AS BOOLEAN)   AS clicked,
  CAST(LOWER(CAST(converted AS STRING)) = 'true' AS BOOLEAN) AS converted,
  CAST(timestamp AS TIMESTAMP)                 AS event_timestamp
FROM serverless_stable_1acr1x_catalog.af360_bronze.bronze_marketing_events
WHERE supporter_id IS NOT NULL;
COMMENT ON TABLE serverless_stable_1acr1x_catalog.af360_silver.silver_marketing_events
  IS 'SILVER: conformed marketing / campaign interactions. Casted booleans/timestamps, de-duplicated.';
