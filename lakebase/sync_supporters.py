# Databricks notebook source
# MAGIC %md
# MAGIC # Arsenal Fan 360 :: Lakebase Operational Serving
# MAGIC Sync the Gold Customer 360 into **Lakebase (PostgreSQL)** operational tables that
# MAGIC power the Arsenal Fan 360 app, and demonstrate application write-back
# MAGIC (`activation_history`).
# MAGIC
# MAGIC * `supporter_profile`   - operational supporter record (read by the app)
# MAGIC * `next_best_action`    - current recommendation per supporter
# MAGIC * `activation_history`  - write-back log of activations triggered from the app
# MAGIC
# MAGIC Lakehouse = analytical data (Gold)  ·  Lakebase = application state / operational interaction.

# COMMAND ----------
# MAGIC %pip install -q psycopg2-binary "databricks-sdk>=0.40.0"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------
import os, uuid, datetime, psycopg2, psycopg2.extras
from databricks.sdk import WorkspaceClient

CAT = "serverless_stable_1acr1x_catalog"
INSTANCE = "arsenal-lakebase"
PG_DB = "databricks_postgres"          # Lakebase default database
SCHEMA = "fan360"
EVID = f"/Volumes/{CAT}/af360_gold/evidence"

w = WorkspaceClient()
me = spark.sql("SELECT current_user()").collect()[0][0]

# read-write DNS + OAuth credential (works across SDK versions)
DEFAULT_HOST = "ep-gentle-credit-d83j1tqb.database.us-east-2.cloud.databricks.com"
host, token = DEFAULT_HOST, None
try:
    inst = w.database.get_database_instance(name=INSTANCE)
    host = inst.read_write_dns
    cred = w.database.generate_database_credential(
        request_id=str(uuid.uuid4()), instance_names=[INSTANCE])
    token = cred.token
except Exception as e1:
    print("w.database unavailable, trying w.postgres:", str(e1)[:80])
    try:
        cred = w.postgres.generate_database_credential(
            request_id=str(uuid.uuid4()), instance_names=[INSTANCE])
        token = cred.token
    except Exception as e2:
        print("w.postgres failed, using workspace token:", str(e2)[:80])
        token = w.config.authenticate().get("Authorization", "").replace("Bearer ", "")
print("Lakebase host:", host)

conn = psycopg2.connect(host=host, port=5432, dbname=PG_DB, user=me,
                        password=token, sslmode="require")
conn.autocommit = True
cur = conn.cursor()
print("Connected to Lakebase as", me)

# COMMAND ----------
# MAGIC %md ## 1. Create operational schema + tables

# COMMAND ----------
cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};")
cur.execute(f"SET search_path TO {SCHEMA}, public;")
cur.execute(f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.supporter_profile (
    supporter_id TEXT PRIMARY KEY,
    first_name TEXT, age_band TEXT, country TEXT, city TEXT,
    membership_tier TEXT, favourite_player TEXT, favourite_product_category TEXT,
    season_ticket_holder BOOLEAN,
    total_ticket_spend DOUBLE PRECISION, total_merchandise_spend DOUBLE PRECISION,
    total_customer_value DOUBLE PRECISION, matches_attended INT,
    ticket_views_30d INT, product_views_30d INT, cart_abandons_30d INT,
    membership_views_30d INT, marketing_opens_30d INT, marketing_clicks_30d INT,
    days_since_last_purchase INT, days_since_last_activity INT,
    engagement_score INT, purchase_intent_score INT
);
""")
cur.execute(f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.next_best_action (
    supporter_id TEXT PRIMARY KEY,
    recommended_action TEXT, recommendation_reason TEXT,
    intent_score INT, opportunity_type TEXT,
    updated_at TIMESTAMP DEFAULT now()
);
""")
cur.execute(f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.activation_history (
    activation_id TEXT PRIMARY KEY,
    supporter_id TEXT NOT NULL,
    recommended_action TEXT,
    selected_action TEXT,
    campaign TEXT,
    created_at TIMESTAMP DEFAULT now(),
    status TEXT DEFAULT 'queued'
);
""")
# make readable/writable by the app service principal (auto-provisioned role)
for stmt in [
    f"GRANT USAGE ON SCHEMA {SCHEMA} TO PUBLIC;",
    f"GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA {SCHEMA} TO PUBLIC;",
    f"ALTER DEFAULT PRIVILEGES IN SCHEMA {SCHEMA} GRANT SELECT, INSERT, UPDATE ON TABLES TO PUBLIC;",
]:
    try: cur.execute(stmt)
    except Exception as e: print("grant skipped:", str(e)[:80])
print("Schema + tables ready.")

# COMMAND ----------
# MAGIC %md ## 2. Sync Gold Customer 360 -> Lakebase operational tables

# COMMAND ----------
def opportunity_type(a):
    return {
        "Match Ticket": "Ticket Intent",
        "Membership Upgrade": "Membership Opportunity",
        "Arsenal Shirt / Merchandise": "Merchandise Opportunity",
        "Hospitality": "Hospitality Opportunity",
        "Re-engagement Campaign": "Re-engagement",
        "Stadium Tour": "Experience",
    }.get(a, "Experience")

gold = spark.table(f"{CAT}.af360_gold.gold_supporter_360").toPandas()
print("Gold rows to sync:", len(gold))

prof_rows = [(
    r.supporter_id, r.first_name, r.age_band, r.country, r.city, r.membership_tier,
    r.favourite_player, r.favourite_product_category, bool(r.season_ticket_holder),
    float(r.total_ticket_spend), float(r.total_merchandise_spend), float(r.total_customer_value),
    int(r.matches_attended), int(r.ticket_views_30d), int(r.product_views_30d),
    int(r.cart_abandons_30d), int(r.membership_views_30d), int(r.marketing_opens_30d),
    int(r.marketing_clicks_30d), int(r.days_since_last_purchase), int(r.days_since_last_activity),
    int(r.engagement_score), int(r.purchase_intent_score)
) for r in gold.itertuples()]

nba_rows = [(
    r.supporter_id, r.recommended_next_action, r.recommendation_reason,
    int(r.purchase_intent_score), opportunity_type(r.recommended_next_action)
) for r in gold.itertuples()]

cur.execute(f"TRUNCATE {SCHEMA}.supporter_profile, {SCHEMA}.next_best_action;")
psycopg2.extras.execute_values(cur, f"""
    INSERT INTO {SCHEMA}.supporter_profile VALUES %s
""", prof_rows, page_size=1000)
psycopg2.extras.execute_values(cur, f"""
    INSERT INTO {SCHEMA}.next_best_action
      (supporter_id, recommended_action, recommendation_reason, intent_score, opportunity_type)
    VALUES %s
""", nba_rows, page_size=1000)
print("Inserted supporter_profile:", len(prof_rows), " next_best_action:", len(nba_rows))

# COMMAND ----------
# MAGIC %md ## 3. Demonstrate application write-back (activation_history)

# COMMAND ----------
# pick the hero: highest-intent non-member with a Membership Upgrade action
cur.execute(f"""
  SELECT p.supporter_id, p.first_name, n.recommended_action, n.intent_score
  FROM {SCHEMA}.supporter_profile p JOIN {SCHEMA}.next_best_action n USING (supporter_id)
  WHERE p.membership_tier IN ('None','Free')
  ORDER BY n.intent_score DESC LIMIT 1;
""")
hero = cur.fetchone()
print("Hero supporter:", hero)

act_id = f"act-{uuid.uuid4().hex[:10]}"
cur.execute(f"""
  INSERT INTO {SCHEMA}.activation_history
    (activation_id, supporter_id, recommended_action, selected_action, campaign, status)
  VALUES (%s, %s, %s, %s, %s, %s)
""", (act_id, hero[0], hero[2], hero[2], "Autumn Membership Drive", "queued"))
print("Wrote activation:", act_id)

cur.execute(f"SELECT * FROM {SCHEMA}.activation_history ORDER BY created_at DESC LIMIT 5;")
recent = cur.fetchall()

# COMMAND ----------
# MAGIC %md ## Evidence

# COMMAND ----------
lines = []
lines.append("=" * 74)
lines.append("ARSENAL FAN 360 :: LAKEBASE OPERATIONAL SERVING")
lines.append(f"Instance: {INSTANCE}  host: {host}  db: {PG_DB}  schema: {SCHEMA}")
lines.append("=" * 74)
cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.supporter_profile"); lines.append(f"supporter_profile rows : {cur.fetchone()[0]:,}")
cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.next_best_action");  lines.append(f"next_best_action rows  : {cur.fetchone()[0]:,}")
cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.activation_history");lines.append(f"activation_history rows: {cur.fetchone()[0]:,}")

lines.append("\n-- Sample supporter_profile (top intent) --")
cur.execute(f"""SELECT supporter_id, first_name, membership_tier, matches_attended,
  total_customer_value, purchase_intent_score FROM {SCHEMA}.supporter_profile
  ORDER BY purchase_intent_score DESC LIMIT 8;""")
for row in cur.fetchall(): lines.append("  " + " | ".join(str(x) for x in row))

lines.append("\n-- Sample next_best_action --")
cur.execute(f"""SELECT supporter_id, recommended_action, opportunity_type, intent_score
  FROM {SCHEMA}.next_best_action ORDER BY intent_score DESC LIMIT 8;""")
for row in cur.fetchall(): lines.append("  " + " | ".join(str(x) for x in row))

lines.append("\n-- Opportunity type distribution --")
cur.execute(f"SELECT opportunity_type, COUNT(*) FROM {SCHEMA}.next_best_action GROUP BY 1 ORDER BY 2 DESC;")
for row in cur.fetchall(): lines.append(f"  {row[0]:<26} {row[1]:>6}")

lines.append("\n-- activation_history (write-back from app) --")
for row in recent: lines.append("  " + " | ".join(str(x) for x in row))

report = "\n".join(lines) + "\n"
dbutils.fs.put(f"{EVID}/lakebase_results.txt", report, True)
print(report)
cur.close(); conn.close()
dbutils.notebook.exit("lakebase_sync_ok")
