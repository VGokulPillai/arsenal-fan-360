# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Generate synthetic supporter data
# MAGIC
# MAGIC Produces 5 raw datasets for **Arsenal Fan 360** (100% synthetic — no real PII):
# MAGIC
# MAGIC | file | rows | grain |
# MAGIC |---|---|---|
# MAGIC | `supporters.csv` | 5,000 | one row per supporter |
# MAGIC | `web_events.csv` | 20,000 | web/app sessions & page views |
# MAGIC | `ecommerce_orders.csv` | 8,000 (+30 dup) | merch orders |
# MAGIC | `ticket_orders.csv` | 5,000 | match ticket purchases |
# MAGIC | `marketing_events.csv` | 10,000 | email sends / opens / clicks |
# MAGIC
# MAGIC Behavioural cohorts are deliberately injected (ticket browsers, cart abandoners,
# MAGIC non‑member attendees, big spenders, lapsed, international buyers) plus dirty rows
# MAGIC and duplicate orders so the Silver layer's cleaning is demonstrable.

# COMMAND ----------

# MAGIC %pip install faker

# COMMAND ----------

# Run the committed generator (see data/generate_supporter_data.py in the repo).
# Locally:  python3 data/generate_supporter_data.py --out data/raw_data --seed 7
# In the workspace, run the generator then upload the CSVs to the UC Volume landing zone:
LANDING = "/Volumes/serverless_stable_1acr1x_catalog/af360_bronze/landing"

# COMMAND ----------

# MAGIC %sh
# MAGIC ls -la /Volumes/serverless_stable_1acr1x_catalog/af360_bronze/landing/*/ 2>/dev/null || echo "upload CSVs to the landing volume"

# COMMAND ----------

# MAGIC %md
# MAGIC ✅ Output: 5 CSVs staged in the Bronze landing volume, ready for ingestion in notebook **02**.
