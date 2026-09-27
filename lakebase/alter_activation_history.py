# Databricks notebook source
# MAGIC %pip install -q psycopg2-binary "databricks-sdk>=0.40.0"
# MAGIC dbutils.library.restartPython()

# COMMAND ----------
import uuid, psycopg2
from databricks.sdk import WorkspaceClient

INSTANCE = "arsenal-lakebase"
PG_DB = "databricks_postgres"
SCHEMA = "fan360"

w = WorkspaceClient()
me = spark.sql("SELECT current_user()").collect()[0][0]
inst = w.database.get_database_instance(name=INSTANCE)
host = inst.read_write_dns
cred = w.database.generate_database_credential(request_id=str(uuid.uuid4()), instance_names=[INSTANCE])
conn = psycopg2.connect(host=host, port=5432, dbname=PG_DB, user=me, password=cred.token, sslmode="require")
conn.autocommit = True
cur = conn.cursor()
cur.execute(f"SET search_path TO {SCHEMA}, public;")

# add AI Campaign Copilot write-back columns (owner-level ALTER)
for col, t in [("next_best_action", "TEXT"), ("campaign_objective", "TEXT"),
               ("recommended_channel", "TEXT"), ("campaign_message", "TEXT"),
               ("approved_by_user", "TEXT"), ("approved_at", "TIMESTAMP")]:
    cur.execute(f"ALTER TABLE {SCHEMA}.activation_history ADD COLUMN IF NOT EXISTS {col} {t};")

# make sure the app service principal can write these columns
for stmt in [
    f"GRANT USAGE ON SCHEMA {SCHEMA} TO PUBLIC;",
    f"GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA {SCHEMA} TO PUBLIC;",
]:
    try:
        cur.execute(stmt)
    except Exception as e:
        print("grant skipped:", str(e)[:80])

cur.execute("""SELECT column_name FROM information_schema.columns
               WHERE table_schema='fan360' AND table_name='activation_history' ORDER BY ordinal_position;""")
cols = [r[0] for r in cur.fetchall()]
print("activation_history columns:", cols)
cur.close(); conn.close()
dbutils.notebook.exit("alter_ok:" + ",".join(cols))
