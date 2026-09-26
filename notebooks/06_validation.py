# Databricks notebook source
# MAGIC %md
# MAGIC # 06 · Validation
# MAGIC
# MAGIC End‑to‑end sanity checks across the platform. Full captured output lives in `evidence/`.

# COMMAND ----------

C = "serverless_stable_1acr1x_catalog"

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Row counts across the medallion
# MAGIC SELECT 'gold_supporter_360' t, count(*) n FROM serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360
# MAGIC UNION ALL SELECT 'gold_supporter_activity', count(*) FROM serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_activity;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Intent distribution (expect ~333 high / 1326 medium / 3341 low)
# MAGIC SELECT CASE WHEN purchase_intent_score >= 70 THEN '70-100 High'
# MAGIC             WHEN purchase_intent_score >= 40 THEN '40-69 Medium'
# MAGIC             ELSE '0-39 Low' END band, count(*) n
# MAGIC FROM serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360
# MAGIC GROUP BY 1 ORDER BY 1;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Next Best Action mix
# MAGIC SELECT recommended_next_action, count(*) n
# MAGIC FROM serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360
# MAGIC GROUP BY 1 ORDER BY n DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Hero supporter: Emile (S004917)
# MAGIC SELECT supporter_id, first_name, purchase_intent_score, recommended_next_action, recommendation_reason
# MAGIC FROM serverless_stable_1acr1x_catalog.af360_gold.gold_supporter_360
# MAGIC WHERE supporter_id = 'S004917';

# COMMAND ----------

# MAGIC %md
# MAGIC ✅ Validation complete. See `evidence/gold_query_results.txt`, `evidence/model_predictions.txt`,
# MAGIC `evidence/lakebase_results.txt`, `evidence/genie_queries.txt`, and `evidence/app_test_output.txt`.
