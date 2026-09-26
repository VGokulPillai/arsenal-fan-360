-- =============================================================================
-- Arsenal Fan 360 :: LAKEFLOW  ::  BRONZE
-- -----------------------------------------------------------------------------
-- Ingest raw supporter source extracts from the Unity Catalog landing Volume
-- into governed Bronze Delta tables. Raw is preserved as-is (string typed)
-- plus ingestion lineage metadata (_source_file, _ingested_at).
--
-- Source  : /Volumes/<cat>/af360_bronze/landing/<source>/
-- Target  : <cat>.af360_bronze.bronze_*
-- Engine  : Databricks SQL Warehouse (read_files / Auto Loader compatible)
-- =============================================================================

-- ---- Supporters (CRM / membership) -----------------------------------------
CREATE OR REPLACE TABLE serverless_stable_1acr1x_catalog.af360_bronze.bronze_supporters AS
SELECT *,
       _metadata.file_path AS _source_file,
       current_timestamp() AS _ingested_at
FROM read_files(
  '/Volumes/serverless_stable_1acr1x_catalog/af360_bronze/landing/supporters/',
  format => 'csv', header => true, inferSchema => true
);
COMMENT ON TABLE serverless_stable_1acr1x_catalog.af360_bronze.bronze_supporters
  IS 'BRONZE: raw supporter/membership records as landed from the CRM extract (synthetic).';

-- ---- Web / clickstream events ----------------------------------------------
CREATE OR REPLACE TABLE serverless_stable_1acr1x_catalog.af360_bronze.bronze_web_events AS
SELECT *,
       _metadata.file_path AS _source_file,
       current_timestamp() AS _ingested_at
FROM read_files(
  '/Volumes/serverless_stable_1acr1x_catalog/af360_bronze/landing/web_events/',
  format => 'csv', header => true, inferSchema => true
);
COMMENT ON TABLE serverless_stable_1acr1x_catalog.af360_bronze.bronze_web_events
  IS 'BRONZE: raw digital clickstream events (arsenal.com) as landed (synthetic).';

-- ---- Ecommerce / merchandise orders ----------------------------------------
CREATE OR REPLACE TABLE serverless_stable_1acr1x_catalog.af360_bronze.bronze_ecommerce_orders AS
SELECT *,
       _metadata.file_path AS _source_file,
       current_timestamp() AS _ingested_at
FROM read_files(
  '/Volumes/serverless_stable_1acr1x_catalog/af360_bronze/landing/ecommerce_orders/',
  format => 'csv', header => true, inferSchema => true
);
COMMENT ON TABLE serverless_stable_1acr1x_catalog.af360_bronze.bronze_ecommerce_orders
  IS 'BRONZE: raw online store / merchandise orders as landed (synthetic).';

-- ---- Ticketing orders ------------------------------------------------------
CREATE OR REPLACE TABLE serverless_stable_1acr1x_catalog.af360_bronze.bronze_ticket_orders AS
SELECT *,
       _metadata.file_path AS _source_file,
       current_timestamp() AS _ingested_at
FROM read_files(
  '/Volumes/serverless_stable_1acr1x_catalog/af360_bronze/landing/ticket_orders/',
  format => 'csv', header => true, inferSchema => true
);
COMMENT ON TABLE serverless_stable_1acr1x_catalog.af360_bronze.bronze_ticket_orders
  IS 'BRONZE: raw matchday ticket transactions as landed (synthetic).';

-- ---- Marketing / campaign interactions -------------------------------------
CREATE OR REPLACE TABLE serverless_stable_1acr1x_catalog.af360_bronze.bronze_marketing_events AS
SELECT *,
       _metadata.file_path AS _source_file,
       current_timestamp() AS _ingested_at
FROM read_files(
  '/Volumes/serverless_stable_1acr1x_catalog/af360_bronze/landing/marketing_events/',
  format => 'csv', header => true, inferSchema => true
);
COMMENT ON TABLE serverless_stable_1acr1x_catalog.af360_bronze.bronze_marketing_events
  IS 'BRONZE: raw email / marketing campaign interactions as landed (synthetic).';
