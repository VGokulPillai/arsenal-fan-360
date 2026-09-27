# Databricks notebook source
# MAGIC %md
# MAGIC # Arsenal Fan 360 :: Intelligence Layer
# MAGIC **Purchase / engagement intent model + GenAI Next-Best-Action explanations**
# MAGIC
# MAGIC 1. Build a supervised label (`engaged_next_30d`) from Silver marketing signals.
# MAGIC 2. Train **Logistic Regression** and **XGBoost** on Gold Customer-360 features.
# MAGIC 3. Log both experiments/models to **MLflow**; select the best by AUC.
# MAGIC 4. Score every supporter -> `purchase_intent_score` (0-100).
# MAGIC 5. Recompute the rule-based **Next Best Action** and use a **Foundation Model**
# MAGIC    (GenAI) to write a natural-language recommendation reason.
# MAGIC 6. Write results back to the Gold Customer 360 and emit text evidence.

# COMMAND ----------
# MAGIC %pip install -q scikit-learn xgboost mlflow
# MAGIC dbutils.library.restartPython()

# COMMAND ----------
import numpy as np, pandas as pd, mlflow, mlflow.sklearn, mlflow.xgboost, json, os
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from xgboost import XGBClassifier

CAT = "serverless_stable_1acr1x_catalog"
GOLD = f"{CAT}.af360_gold.gold_supporter_360"
SILVER = f"{CAT}.af360_silver"
EVID = f"/Volumes/{CAT}/af360_gold/evidence"
REF = "TIMESTAMP '2025-09-20 12:00:00'"
evidence = {}

# COMMAND ----------
# MAGIC %md ## 1. Assemble training frame (features from Gold, label from Silver)

# COMMAND ----------
# Label: did the supporter CLICK or CONVERT a marketing campaign in the last 30 days?
label_df = spark.sql(f"""
  SELECT supporter_id,
         MAX(CASE WHEN (clicked OR converted)
                   AND event_timestamp >= {REF} - INTERVAL 30 DAYS THEN 1 ELSE 0 END) AS engaged_next_30d
  FROM {SILVER}.silver_marketing_events GROUP BY supporter_id
""")

feat_cols = ["matches_attended","total_ticket_spend","total_merchandise_spend","total_customer_value",
             "website_sessions_30d","product_views_30d","ticket_views_30d","cart_abandons_30d",
             "membership_views_30d","hospitality_views_30d","marketing_opens_30d",
             "days_since_last_purchase","days_since_last_activity","ticket_purchases","merchandise_orders"]

gold = spark.table(GOLD)
df = (gold.join(label_df, "supporter_id", "left").fillna({"engaged_next_30d": 0}))
pdf = df.select(["supporter_id","first_name","membership_tier"] + feat_cols + ["engaged_next_30d"]).toPandas()
print(f"Training rows: {len(pdf):,}")
print("Label balance:\n", pdf["engaged_next_30d"].value_counts())

# membership tier ordinal encode
tier_map = {"None":0,"Free":1,"Silver":2,"Gold":3,"Red Member":4}
pdf["membership_tier_ord"] = pdf["membership_tier"].map(tier_map).fillna(0)
X_cols = feat_cols + ["membership_tier_ord"]
X = pdf[X_cols].astype(float).values
y = pdf["engaged_next_30d"].astype(int).values
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

# COMMAND ----------
# MAGIC %md ## 2+3. Train + log Logistic Regression and XGBoost to MLflow

# COMMAND ----------
mlflow.set_experiment(f"/Users/{spark.sql('SELECT current_user()').collect()[0][0]}/arsenal_fan_360_intent")

def evaluate(model, name):
    p = model.predict_proba(X_te)[:, 1]
    pred = (p >= 0.5).astype(int)
    return {
        "model": name,
        "auc": round(roc_auc_score(y_te, p), 4),
        "accuracy": round(accuracy_score(y_te, pred), 4),
        "precision": round(precision_score(y_te, pred, zero_division=0), 4),
        "recall": round(recall_score(y_te, pred, zero_division=0), 4),
        "f1": round(f1_score(y_te, pred, zero_division=0), 4),
    }

results = {}
# --- Logistic Regression ---
with mlflow.start_run(run_name="logistic_regression") as run:
    lr = Pipeline([("scaler", StandardScaler()),
                   ("clf", LogisticRegression(max_iter=1000, class_weight="balanced"))])
    lr.fit(X_tr, y_tr)
    m = evaluate(lr, "logistic_regression")
    mlflow.log_params({"model_type": "logistic_regression", "class_weight": "balanced"})
    mlflow.log_metrics({k: v for k, v in m.items() if k != "model"})
    mlflow.sklearn.log_model(lr, "model", serialization_format="cloudpickle")
    results["logistic_regression"] = (lr, m, run.info.run_id)
    print("LogReg:", m)

# --- XGBoost ---
with mlflow.start_run(run_name="xgboost") as run:
    pos = max(1, int((y_tr == 0).sum())) / max(1, int((y_tr == 1).sum()))
    xgb = XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.1,
                        subsample=0.9, colsample_bytree=0.9, eval_metric="logloss",
                        scale_pos_weight=pos, random_state=42)
    xgb.fit(X_tr, y_tr)
    m = evaluate(xgb, "xgboost")
    mlflow.log_params({"model_type": "xgboost", "n_estimators": 200, "max_depth": 4})
    mlflow.log_metrics({k: v for k, v in m.items() if k != "model"})
    mlflow.xgboost.log_model(xgb, "model")
    results["xgboost"] = (xgb, m, run.info.run_id)
    print("XGBoost:", m)

best_name = max(results, key=lambda k: results[k][1]["auc"])
best_model, best_metrics, best_run = results[best_name]
print("BEST MODEL:", best_name, best_metrics)

# feature importance (xgboost) / coef (lr)
if best_name == "xgboost":
    imp = sorted(zip(X_cols, best_model.feature_importances_), key=lambda x: -x[1])[:8]
else:
    coef = best_model.named_steps["clf"].coef_[0]
    imp = sorted(zip(X_cols, np.abs(coef)), key=lambda x: -x[1])[:8]

# COMMAND ----------
# MAGIC %md ## 4. Score every supporter -> purchase_intent_score (0-100)

# COMMAND ----------
pdf["intent_prob"] = best_model.predict_proba(X)[:, 1]
# blend model probability with a light behavioural boost so the 0-100 score
# spreads nicely and reflects strong recent intent signals
signal = (pdf["ticket_views_30d"] * 6 + pdf["cart_abandons_30d"] * 8
          + pdf["membership_views_30d"] * 5 + pdf["product_views_30d"] * 2
          + pdf["hospitality_views_30d"] * 6).clip(0, 100)
pdf["purchase_intent_score"] = (0.7 * (pdf["intent_prob"] * 100) + 0.3 * signal).round().clip(0, 100).astype(int)

def nba(r):
    if r.ticket_views_30d >= 2 and r.ticket_purchases == 0:
        return "Match Ticket"
    if r.total_customer_value >= 350 and r.matches_attended >= 3:
        return "Hospitality"
    if (r.matches_attended >= 2 or r.membership_views_30d >= 1) and r.membership_tier in ("None", "Free"):
        return "Membership Upgrade"
    if r.product_views_30d >= 3 or r.cart_abandons_30d >= 1:
        return "Arsenal Shirt / Merchandise"
    if r.hospitality_views_30d >= 1:
        return "Hospitality"
    if r.days_since_last_activity >= 60:
        return "Re-engagement Campaign"
    return "Stadium Tour"

pdf["recommended_next_action"] = pdf.apply(nba, axis=1)
print(pdf["recommended_next_action"].value_counts())
print("\nIntent score describe:\n", pdf["purchase_intent_score"].describe())

# COMMAND ----------
# MAGIC %md ## 5. GenAI recommendation reason (Foundation Model)

# COMMAND ----------
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
w = WorkspaceClient()
FM = "databricks-claude-sonnet-4-6"

def genai_reason(r):
    prompt = (
        "You are Arsenal FC's supporter marketing analyst. In ONE concise sentence "
        "(max 30 words, no preamble), explain why we recommend the action for this supporter. "
        f"Action: {r['recommended_next_action']}. "
        f"Supporter: {r['first_name']}, membership tier {r['membership_tier']}, "
        f"matches attended {int(r['matches_attended'])}, ticket views (30d) {int(r['ticket_views_30d'])}, "
        f"product views (30d) {int(r['product_views_30d'])}, abandoned baskets (30d) {int(r['cart_abandons_30d'])}, "
        f"membership page views (30d) {int(r['membership_views_30d'])}, "
        f"lifetime value £{r['total_customer_value']:.0f}, intent score {int(r['purchase_intent_score'])}/100."
    )
    try:
        resp = w.serving_endpoints.query(name=FM, messages=[
            ChatMessage(role=ChatMessageRole.USER, content=prompt)], max_tokens=80, temperature=0.4)
        return resp.choices[0].message.content.strip().replace("\n", " ")
    except Exception as e:
        return f"[genai_error] {str(e)[:80]}"

# generate GenAI reasons for the 120 highest-intent supporters (real LLM evidence);
# the remaining rows keep the templated Gold reason.
top = pdf.sort_values("purchase_intent_score", ascending=False).head(120).copy()
top["recommendation_reason"] = top.apply(genai_reason, axis=1)
reason_map = dict(zip(top["supporter_id"], top["recommendation_reason"]))
pdf["genai_reason"] = pdf["supporter_id"].map(reason_map)
print("Sample GenAI recommendations:")
for _, r in top.head(6).iterrows():
    print(f"  [{r['recommended_next_action']}] {r['first_name']} ({r['purchase_intent_score']}/100): {r['recommendation_reason']}")

# COMMAND ----------
# MAGIC %md ## 6. Publish scores to a dedicated gold_supporter_scores table
# MAGIC The base Customer 360 (`gold_supporter_360`) is owned by the Lakeflow
# MAGIC Spark Declarative Pipeline (materialized view), so we do **not** mutate it
# MAGIC here. Instead the ML layer writes its own `gold_supporter_scores` table,
# MAGIC which the operational layer (Lakebase sync / app snapshot) JOINs back to
# MAGIC the 360 on `supporter_id`. This keeps a clean separation: SDP owns the
# MAGIC curated 360, ML owns the intelligence overlay.

# COMMAND ----------
score_sdf = spark.createDataFrame(
    pdf[["supporter_id","purchase_intent_score","recommended_next_action","genai_reason","intent_prob"]]
    .rename(columns={"intent_prob": "model_intent_prob", "genai_reason": "recommendation_reason"})
)
score_sdf.createOrReplaceTempView("v_scores")
spark.sql(f"CREATE OR REPLACE TABLE {CAT}.af360_gold.gold_supporter_scores AS SELECT * FROM v_scores")
print("gold_supporter_scores written (intent score + NBA + GenAI reason). "
      "gold_supporter_360 left intact — it is owned by the Lakeflow SDP.")

# COMMAND ----------
# MAGIC %md ## Emit text evidence to the Unity Catalog evidence Volume

# COMMAND ----------
lines = []
lines.append("=" * 74)
lines.append("ARSENAL FAN 360 :: ML MODEL METRICS  (MLflow logged)")
lines.append("=" * 74)
for name in ("logistic_regression", "xgboost"):
    _, m, rid = results[name]
    lines.append(f"\n[{name}]  mlflow_run_id={rid}")
    for k in ("auc", "accuracy", "precision", "recall", "f1"):
        lines.append(f"    {k:<10} {m[k]}")
lines.append(f"\nBEST MODEL: {best_name}  (AUC={best_metrics['auc']})")
lines.append(f"Label positive rate: {y.mean():.3f}  | rows={len(y):,}  test={len(y_te):,}")
lines.append("\nTop feature importances:")
for f, v in imp:
    lines.append(f"    {f:<26} {v:.4f}")
cm = confusion_matrix(y_te, (best_model.predict_proba(X_te)[:,1] >= 0.5).astype(int))
lines.append(f"\nConfusion matrix (test) [tn fp / fn tp]:\n{cm}")
dbutils.fs.put(f"{EVID}/ml_model_metrics.txt", "\n".join(lines) + "\n", True)

# predictions + NBA distribution
p = []
p.append("=" * 74); p.append("ARSENAL FAN 360 :: MODEL PREDICTIONS & NEXT BEST ACTION"); p.append("=" * 74)
p.append("\nPurchase intent score distribution:")
p.append(pdf["purchase_intent_score"].describe().round(2).to_string())
p.append("\nIntent bands:")
bands = pd.cut(pdf["purchase_intent_score"], [-1,39,69,100], labels=["0-39 Low","40-69 Medium","70-100 High"])
p.append(bands.value_counts().sort_index().to_string())
p.append("\nRecommended Next Best Action distribution:")
p.append(pdf["recommended_next_action"].value_counts().to_string())
p.append("\nTop 15 highest-intent supporters:")
cols = ["supporter_id","first_name","membership_tier","matches_attended","ticket_views_30d",
        "product_views_30d","total_customer_value","purchase_intent_score","recommended_next_action"]
p.append(pdf.sort_values("purchase_intent_score", ascending=False).head(15)[cols].to_string(index=False))
dbutils.fs.put(f"{EVID}/model_predictions.txt", "\n".join(p) + "\n", True)

# genai evidence
g = []
g.append("=" * 74); g.append("ARSENAL FAN 360 :: GenAI NEXT-BEST-ACTION EXPLANATIONS"); g.append(f"Foundation Model endpoint: {FM}"); g.append("=" * 74)
for _, r in top.head(25).iterrows():
    g.append(f"\n[{r['recommended_next_action']}] {r['first_name']} ({r['membership_tier']}) - intent {r['purchase_intent_score']}/100")
    g.append(f"  Why: {r['recommendation_reason']}")
dbutils.fs.put(f"{EVID}/genai_recommendations.txt", "\n".join(g) + "\n", True)

print("Evidence written to", EVID)
dbutils.notebook.exit(json.dumps({"best_model": best_name, **best_metrics,
                                   "rows_scored": int(len(pdf))}))
