"""Lakebase (PostgreSQL) access for Arsenal Fan 360 operational serving.

Uses Databricks SDK OAuth token rotation for auth. Gracefully degrades to an
in-memory activation log when Lakebase is not reachable, so the app always runs.
"""
import logging, uuid, datetime
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
    if not HAS_PG or not config.PG_HOST:
        return None
    try:
        conn = psycopg2.connect(
            host=config.PG_HOST, port=config.PG_PORT, dbname=config.PG_DATABASE,
            user=config.PG_USER or None, password=_password() or None,
            sslmode="require", connect_timeout=8)
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


def write_activation(supporter_id, recommended_action, selected_action, campaign) -> dict:
    """Write an activation to Lakebase (or in-memory fallback)."""
    act = {
        "activation_id": f"act-{uuid.uuid4().hex[:10]}",
        "supporter_id": supporter_id,
        "recommended_action": recommended_action,
        "selected_action": selected_action,
        "campaign": campaign,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "status": "queued",
    }
    conn = _connect()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {config.PG_SCHEMA}.activation_history
                  (activation_id, supporter_id, recommended_action, selected_action, campaign, status)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (act["activation_id"], supporter_id, recommended_action, selected_action, campaign, "queued"))
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
            cur.execute(f"SELECT * FROM {config.PG_SCHEMA}.activation_history ORDER BY created_at DESC LIMIT %s", (limit,))
            rows = [dict(r) for r in cur.fetchall()]
            cur.close(); conn.close()
            for r in rows:
                r["created_at"] = str(r.get("created_at"))
            return rows
        except Exception as e:
            logger.warning("Lakebase recent_activations failed: %s", e)
    return _mem_activations[:limit]
