"""Config + dual-mode auth for Arsenal Fan 360 (Databricks App vs local)."""
import os

IS_DATABRICKS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))

CATALOG = os.environ.get("CATALOG", "serverless_stable_1acr1x_catalog")
GOLD_SCHEMA = os.environ.get("GOLD_SCHEMA", "af360_gold")
WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "4484f27c707c5a31")
SERVING_ENDPOINT = os.environ.get("SERVING_ENDPOINT", "databricks-claude-sonnet-4-6")
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")

# Lakebase (auto-injected by Databricks Apps when a database resource is attached)
PG_HOST = os.environ.get("PGHOST", "")
PG_DATABASE = os.environ.get("PGDATABASE", "databricks_postgres")
PG_PORT = os.environ.get("PGPORT", "5432")
PG_USER = os.environ.get("PGUSER", "")
PG_SCHEMA = os.environ.get("PG_SCHEMA", "fan360")
LAKEBASE_INSTANCE = os.environ.get("LAKEBASE_INSTANCE", "arsenal-lakebase")


def get_workspace_client():
    from databricks.sdk import WorkspaceClient
    if IS_DATABRICKS_APP:
        return WorkspaceClient()
    profile = os.environ.get("DATABRICKS_PROFILE", os.environ.get("DBX_PROFILE", "DEFAULT"))
    return WorkspaceClient(profile=profile)
