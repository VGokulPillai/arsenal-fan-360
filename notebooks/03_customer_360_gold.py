# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Customer 360 — Gold
# MAGIC
# MAGIC Builds the two Gold tables from Silver:
# MAGIC
# MAGIC - **`gold_supporter_360`** — one row per supporter with the full feature set: demographics,
# MAGIC   membership, RFM‑style spend, web/ticket/marketing behaviour (30‑day windows), recency,
# MAGIC   a baseline `engagement_score` and `purchase_intent_score`, and a rule‑based
# MAGIC   `recommended_next_action` + `recommendation_reason` (later refined by the ML/GenAI notebook).
# MAGIC - **`gold_supporter_activity`** — a unified activity feed (web + ecom + ticket + marketing) used
# MAGIC   for the app's supporter timeline.
# MAGIC
# MAGIC SQL committed at `lakeflow/gold_pipeline.sql`. Reference "today" = `2025-09-20 12:00:00`.

# COMMAND ----------

with open("../lakeflow/gold_pipeline.sql") as f:
    for stmt in [s.strip() for s in f.read().split(";") if s.strip()]:
        spark.sql(stmt)
print("gold pipeline applied")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) AS supporter_360_rows FROM serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360;      -- 5,000
# MAGIC -- gold_supporter_activity ~ 43,000 rows

# COMMAND ----------

# MAGIC %md
# MAGIC ✅ `gold_supporter_360` (5,000) and `gold_supporter_activity` (43,000). Next: governance in
# MAGIC `unity_catalog/governance.sql`, then ML/GenAI in notebook **04**.
