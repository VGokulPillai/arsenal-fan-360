-- =============================================================================
-- Arsenal Fan 360 :: LAKEBASE (PostgreSQL) operational serving schema
-- -----------------------------------------------------------------------------
-- Lakehouse = analytical data (Gold Delta)  ·  Lakebase = application state.
-- These tables are created + populated by lakebase/sync_supporters.py and are
-- read (and written) by the Arsenal Fan 360 Databricks App.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS fan360;
SET search_path TO fan360, public;

-- Operational supporter record (read by the app's Overview & Supporter 360)
CREATE TABLE IF NOT EXISTS fan360.supporter_profile (
    supporter_id                TEXT PRIMARY KEY,
    first_name                  TEXT,
    age_band                    TEXT,
    country                     TEXT,
    city                        TEXT,
    membership_tier             TEXT,
    favourite_player            TEXT,
    favourite_product_category  TEXT,
    season_ticket_holder        BOOLEAN,
    total_ticket_spend          DOUBLE PRECISION,
    total_merchandise_spend     DOUBLE PRECISION,
    total_customer_value        DOUBLE PRECISION,
    matches_attended            INT,
    ticket_views_30d            INT,
    product_views_30d           INT,
    cart_abandons_30d           INT,
    membership_views_30d        INT,
    marketing_opens_30d         INT,
    marketing_clicks_30d        INT,
    days_since_last_purchase    INT,
    days_since_last_activity    INT,
    engagement_score            INT,
    purchase_intent_score       INT
);

-- Current Next Best Action per supporter (model + GenAI enriched)
CREATE TABLE IF NOT EXISTS fan360.next_best_action (
    supporter_id           TEXT PRIMARY KEY,
    recommended_action     TEXT,
    recommendation_reason  TEXT,
    intent_score           INT,
    opportunity_type       TEXT,
    updated_at             TIMESTAMP DEFAULT now()
);

-- Write-back log: activations triggered from the application.
-- The AI Campaign Copilot writes a human-approved campaign brief here when the
-- marketer clicks "Approve & Add to Campaign" (nothing is auto-sent).
CREATE TABLE IF NOT EXISTS fan360.activation_history (
    activation_id       TEXT PRIMARY KEY,
    supporter_id        TEXT NOT NULL,
    recommended_action  TEXT,
    selected_action     TEXT,
    campaign            TEXT,
    created_at          TIMESTAMP DEFAULT now(),
    status              TEXT DEFAULT 'queued',
    -- AI Campaign Copilot write-back (human-approved)
    next_best_action    TEXT,
    campaign_objective  TEXT,
    recommended_channel TEXT,
    campaign_message    TEXT,
    approved_by_user    TEXT,
    approved_at         TIMESTAMP
);
