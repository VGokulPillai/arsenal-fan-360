# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Ingestion — Bronze & Silver (Lakeflow medallion)
# MAGIC
# MAGIC - **Bronze** (`af360_bronze.*`): raw ingest of each CSV via `read_files`, plus `_source_file` /
# MAGIC   `_ingested_at` lineage columns. Nothing is dropped.
# MAGIC - **Silver** (`af360_silver.*`): cleaned & typed — `INITCAP` on country, trimmed tiers,
# MAGIC   missing `age_band` → `'Unknown'`, correct casts, and **de‑duplication** (30 duplicate
# MAGIC   ecommerce orders removed: 8,030 → 8,000).
# MAGIC
# MAGIC The SQL is committed at `lakeflow/bronze_pipeline.sql` and `lakeflow/silver_pipeline.sql`.

# COMMAND ----------

CATALOG = "serverless_stable_1acr1x_catalog"
for sql_file in ["../lakeflow/bronze_pipeline.sql", "../lakeflow/silver_pipeline.sql"]:
    with open(sql_file) as f:
        for stmt in [s.strip() for s in f.read().split(";") if s.strip()]:
            spark.sql(stmt)
    print("applied", sql_file)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 'bronze' layer, 'ecommerce' src, count(*) rows FROM serverless_stable_1acr1x_catalog.af360_bronze.bronze_ecommerce_orders
# MAGIC UNION ALL
# MAGIC SELECT 'silver', 'ecommerce', count(*) FROM serverless_stable_1acr1x_catalog.af360_silver.silver_ecommerce_orders;
# MAGIC -- expect 8,030 -> 8,000 (30 duplicates removed)

# COMMAND ----------

# MAGIC %md
# MAGIC ✅ Bronze (5 tables) and Silver (5 tables) populated. Evidence: `evidence/pipeline_output.txt`.
