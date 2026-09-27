"""Lakebase (PostgreSQL) access for Arsenal Fan 360 operational serving.

Uses Databricks SDK OAuth token rotation for auth. Gracefully degrades to an
in-memory activation log when Lakebase is not reachable, so the app always runs.
"""
import logging, os, uuid, datetime
from . import config

logger = logging.getLogger(__name__)

try:
    import psycopg2, psycopg2.extras
    HAS_PG = True
except Exception:
    HAS_PG = False

_pg_ok = None
_mem_activations: list[dict] = []


def _password() -> str:
    """Fresh OAuth token for Lakebase."""
    if config.PG_USER and __import__("os").environ.get("PGPASSWORD"):
        return __import__("os").environ["PGPASSWORD"]
    try:
        w = config.get_workspace_client()
        try:
            cred = w.database.generate_database_credential(
                request_id=str(uuid.uuid4()), instance_names=[config.LAKEBASE_INSTANCE])
            return cred.token
        except Exception:
            headers = w.config.authenticate()
            return headers.get("Authorization", "").replace("Bearer ", "")
    except Exception as e:
        logger.warning("Lakebase token failed: %s", e)
        return ""


def _connect():
    if not HAS_PG:
        return None
    # Databricks Apps inject PGHOST/PGUSER/PGDATABASE/PGSSLMODE when a `database`
    # resource is attached; the password is a short-lived OAuth token we mint via
    # the SDK. A `postgresql://` URI in DB_CONNECTION_STRING is used only if valid.
    dsn = os.environ.get("DB_CONNECTION_STRING", "") or os.environ.get("LAKEBASE_URL", "")
    if dsn and not dsn.startswith("postgres"):
        dsn = ""  # injected value is a bare host, not a usable libpq DSN
    try:
        if dsn:
            conn = psycopg2.connect(dsn, connect_timeout=8)
        elif config.PG_HOST:
            conn = psycopg2.connect(
                host=config.PG_HOST, port=config.PG_PORT, dbname=config.PG_DATABASE,
                user=config.PG_USER or None, password=_password() or None,
                sslmode=os.environ.get("PGSSLMODE", "require"), connect_timeout=8)
        else:
            return None
        cur = conn.cursor()
        cur.execute(f"SET search_path TO {config.PG_SCHEMA}, public;")
        cur.close()
        return conn
    except Exception as e:
        logger.warning("Lakebase connect failed: %s", e)
        return None


def available() -> bool:
    global _pg_ok
    if _pg_ok is None:
        c = _connect()
        _pg_ok = c is not None
        if c:
            c.close()
    return _pg_ok


def ensure_schema() -> None:
    """Idempotently ensure the AI Campaign Copilot write-back columns exist.

    Safe to call on every startup; if Lakebase is unreachable this is a no-op.
    """
    conn = _connect()
    if not conn:
        return
    try:
        cur = conn.cursor()
        for col, coltype in [
            ("next_best_action", "TEXT"), ("campaign_objective", "TEXT"),
            ("recommended_channel", "TEXT"), ("campaign_message", "TEXT"),
            ("approved_by_user", "TEXT"), ("approved_at", "TIMESTAMP"),
        ]:
            cur.execute(
                f"ALTER TABLE {config.PG_SCHEMA}.activation_history "
                f"ADD COLUMN IF NOT EXISTS {col} {coltype};")
        conn.commit(); cur.close(); conn.close()
        logger.info("Lakebase activation_history schema ensured.")
    except Exception as e:
        logger.warning("Lakebase ensure_schema skipped: %s", e)


def load_profiles() -> list[dict]:
    """Read supporter_profile + next_best_action from Lakebase (or [] if unavailable)."""
    conn = _connect()
    if not conn:
        return []
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"""
            SELECT p.*, n.recommended_action, n.recommendation_reason,
                   n.opportunity_type, n.intent_score
            FROM {config.PG_SCHEMA}.supporter_profile p
            JOIN {config.PG_SCHEMA}.next_best_action n USING (supporter_id)
        """)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close(); conn.close()
        return rows
    except Exception as e:
        logger.warning("Lakebase load_profiles failed: %s", e)
        return []


def write_activation(supporter_id, next_best_action, campaign_objective="",
                     recommended_channel="", campaign_message="", approved_by_user="marketing_user") -> dict:
    """Write an approved AI-Campaign-Copilot activation to Lakebase (or in-memory fallback)."""
    act = {
        "activation_id": f"act-{uuid.uuid4().hex[:10]}",
        "supporter_id": supporter_id,
        "next_best_action": next_best_action,
        "campaign_objective": campaign_objective,
        "recommended_channel": recommended_channel,
        "campaign_message": campaign_message,
        "approved_by_user": approved_by_user,
        "approved_at": datetime.datetime.utcnow().isoformat(),
        "status": "queued",
    }
    conn = _connect()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {config.PG_SCHEMA}.activation_history
                  (activation_id, supporter_id, recommended_action, selected_action, campaign, status,
                   next_best_action, campaign_objective, recommended_channel, campaign_message, approved_by_user, approved_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
            """, (act["activation_id"], supporter_id, next_best_action, next_best_action,
                  campaign_objective, "queued", next_best_action, campaign_objective,
                  recommended_channel, campaign_message, approved_by_user))
            conn.commit(); cur.close(); conn.close()
            act["store"] = "Databricks Lakebase"
            return act
        except Exception as e:
            logger.warning("Lakebase write failed: %s", e)
    _mem_activations.insert(0, act)
    act["store"] = "in-memory (Lakebase unavailable)"
    return act


def recent_activations(limit=20) -> list[dict]:
    conn = _connect()
    if conn:
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(f"SELECT * FROM {config.PG_SCHEMA}.activation_history ORDER BY COALESCE(approved_at, created_at) DESC LIMIT %s", (limit,))
            rows = [dict(r) for r in cur.fetchall()]
            cur.close(); conn.close()
            for r in rows:
                r["created_at"] = str(r.get("created_at"))
                r["approved_at"] = str(r.get("approved_at"))
            return rows
        except Exception as e:
            logger.warning("Lakebase recent_activations failed: %s", e)
    return _mem_activations[:limit]
