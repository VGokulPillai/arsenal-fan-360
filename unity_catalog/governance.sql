-- =============================================================================
-- Arsenal Fan 360 :: UNITY CATALOG GOVERNANCE
-- -----------------------------------------------------------------------------
-- Everything the app, ML, and Genie consume is governed by Unity Catalog.
-- This script documents the Customer 360 gold table (column-level comments),
-- classifies sensitive-looking synthetic attributes with governance tags, and
-- shows how access could be controlled.
--
-- Catalog: serverless_stable_1acr1x_catalog   (CREATE CATALOG requires
--          metastore admin; the prototype uses the workspace catalog with
--          dedicated af360_* schemas: bronze / silver / gold / ops)
-- =============================================================================

-- ---- Schema documentation --------------------------------------------------
COMMENT ON SCHEMA serverless_stable_1acr1x_catalog.af360_bronze IS 'Arsenal Fan 360 - Bronze (raw landed source extracts).';
COMMENT ON SCHEMA serverless_stable_1acr1x_catalog.af360_silver IS 'Arsenal Fan 360 - Silver (cleaned, conformed).';
COMMENT ON SCHEMA serverless_stable_1acr1x_catalog.af360_gold   IS 'Arsenal Fan 360 - Gold (Customer 360, ML/GenAI enriched).';
COMMENT ON SCHEMA serverless_stable_1acr1x_catalog.af360_ops    IS 'Arsenal Fan 360 - Operational mirror of Lakebase serving tables.';

-- ---- Column-level documentation on the Customer 360 ------------------------
ALTER TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360 ALTER COLUMN supporter_id            COMMENT 'Synthetic surrogate supporter key (no real PII).';
ALTER TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360 ALTER COLUMN membership_tier         COMMENT 'Current membership tier: None/Free/Silver/Gold/Red Member.';
ALTER TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360 ALTER COLUMN total_customer_value    COMMENT 'Lifetime ticket + merchandise spend (GBP).';
ALTER TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360 ALTER COLUMN engagement_score        COMMENT 'Breadth/recency engagement index 0-100.';
ALTER TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360 ALTER COLUMN purchase_intent_score   COMMENT 'Likelihood (0-100) of purchase/engagement in next 30 days. Rule-based baseline, overwritten by ML model.';
ALTER TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360 ALTER COLUMN recommended_next_action COMMENT 'Next Best Action label served to marketing/commercial teams.';
ALTER TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360 ALTER COLUMN recommendation_reason   COMMENT 'Natural-language justification (GenAI generated).';

-- ---- Governance tags (classification of sensitive-looking attributes) ------
ALTER TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360 SET TAGS ('domain' = 'sales', 'data_product' = 'analytics');
ALTER TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360 ALTER COLUMN first_name SET TAGS ('classification' = 'confidential', 'pii_type' = 'name');
ALTER TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360 ALTER COLUMN city       SET TAGS ('classification' = 'confidential', 'pii_type' = 'address');
ALTER TABLE serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360 ALTER COLUMN purchase_intent_score SET TAGS ('classification' = 'internal');

-- Tag the gold schema as the certified serving layer for Genie & the app
ALTER SCHEMA serverless_stable_1acr1x_catalog.af360_gold SET TAGS ('certified' = 'true', 'consumers' = 'app_genie_ml');
