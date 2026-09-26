"""In-memory supporter store for Arsenal Fan 360.

Loads the operational supporter view from Lakebase when available, otherwise
from a bundled Gold snapshot (so the app always runs). Computes the Overview,
Opportunities and Supporter 360 payloads.
"""
import json, os, logging
from . import db

logger = logging.getLogger(__name__)
_DATA = os.path.join(os.path.dirname(__file__), "data")

_profiles: dict[str, dict] = {}
_activity: dict[str, list] = {}
_source = "unknown"

OPP_META = {
    "Ticket Intent": ("Viewed tickets multiple times but have not purchased.", "Match Ticket Offer"),
    "Membership Opportunity": ("Frequent match attendees who are not currently members.", "Membership Upgrade"),
    "Merchandise Opportunity": ("High product browsing or abandoned baskets.", "Merchandise Reminder"),
    "Hospitality Opportunity": ("High spend and attendance — premium experience candidates.", "Hospitality Invite"),
    "Re-engagement": ("No meaningful interaction during the last 60 days.", "Re-engagement Campaign"),
    "Experience": ("Engaged supporters to nurture with an experience offer.", "Stadium Tour"),
}


def _load_snapshot():
    global _profiles, _activity, _source
    with open(os.path.join(_DATA, "supporters_snapshot.json")) as f:
        rows = json.load(f)
    _profiles = {r["supporter_id"]: r for r in rows}
    try:
        with open(os.path.join(_DATA, "activity_snapshot.json")) as f:
            _activity = json.load(f)
    except Exception:
        _activity = {}
    _source = "Gold snapshot (Delta Customer 360)"


def init():
    global _profiles, _source
    rows = db.load_profiles() if db.available() else []
    if rows:
        _profiles = {r["supporter_id"]: r for r in rows}
        _source = "Databricks Lakebase (operational)"
        try:
            with open(os.path.join(_DATA, "activity_snapshot.json")) as f:
                globals()["_activity"] = json.load(f)
        except Exception:
            pass
        logger.info("Loaded %d supporters from Lakebase", len(_profiles))
    else:
        _load_snapshot()
        logger.info("Loaded %d supporters from snapshot", len(_profiles))


def source() -> str:
    return _source


def _rows():
    return list(_profiles.values())


def overview():
    rows = _rows()
    n = len(rows)
    high = sum(1 for r in rows if (r.get("purchase_intent_score") or 0) >= 70)
    revenue = sum((r.get("total_customer_value") or 0) for r in rows)
    matches = sum((r.get("matches_attended") or 0) for r in rows)

    def band(s):
        s = s or 0
        return "70-100 High" if s >= 70 else "40-69 Medium" if s >= 40 else "0-39 Low"
    dist = {"0-39 Low": 0, "40-69 Medium": 0, "70-100 High": 0}
    actions: dict[str, int] = {}
    opp_counts: dict[str, int] = {}
    for r in rows:
        dist[band(r.get("purchase_intent_score"))] += 1
        a = r.get("recommended_action") or "Stadium Tour"
        actions[a] = actions.get(a, 0) + 1
        o = r.get("opportunity_type") or "Experience"
        opp_counts[o] = opp_counts.get(o, 0) + 1

    members = [r for r in rows if (r.get("membership_tier") not in ("None", "Free"))]
    non_members = [r for r in rows if (r.get("membership_tier") in ("None", "Free"))]
    rev_seg = [
        {"segment": "Members", "value": sum(r.get("total_customer_value") or 0 for r in members)},
        {"segment": "Non-members", "value": sum(r.get("total_customer_value") or 0 for r in non_members)},
    ]
    # engagement trend proxy (buckets by days_since_last_activity -> recency weeks)
    trend = []
    for wk in range(8, 0, -1):
        lo, hi = (wk - 1) * 7, wk * 7
        bucket = [r for r in rows if lo <= (r.get("days_since_last_activity") or 999) < hi]
        avg = round(sum(r.get("engagement_score") or 0 for r in bucket) / len(bucket)) if bucket else 0
        trend.append({"label": f"-{wk}w", "score": avg})

    open_opps = sum(v for k, v in opp_counts.items() if k != "Experience")
    return {
        "kpis": {
            "total_supporters": n,
            "high_intent": high,
            "revenue": round(revenue),
            "matches_attended": matches,
            "open_opportunities": open_opps,
        },
        "intent_distribution": [{"band": k, "count": v} for k, v in dist.items()],
        "actions": sorted([{"action": k, "count": v} for k, v in actions.items()], key=lambda x: -x["count"]),
        "revenue_by_segment": rev_seg,
        "engagement_trend": trend,
        "data_source": _source,
    }


def search(q="", limit=25):
    q = (q or "").lower().strip()
    rows = _rows()
    if q:
        rows = [r for r in rows if q in r["supporter_id"].lower() or q in (r.get("first_name") or "").lower()]
    rows = sorted(rows, key=lambda r: -(r.get("purchase_intent_score") or 0))[:limit]
    return [{
        "supporter_id": r["supporter_id"], "first_name": r.get("first_name"),
        "membership_tier": r.get("membership_tier"), "country": r.get("country"),
        "purchase_intent_score": r.get("purchase_intent_score") or 0,
        "recommended_action": r.get("recommended_action"),
    } for r in rows]


def detail(sid):
    r = _profiles.get(sid)
    if not r:
        return None
    return {
        "profile": r,
        "intent": r.get("purchase_intent_score") or 0,
        "engagement": r.get("engagement_score") or 0,
        "nba": {
            "action": r.get("recommended_action"),
            "reason": r.get("recommendation_reason"),
            "opportunity_type": r.get("opportunity_type") or "Experience",
        },
        "activity": _activity.get(sid, []),
    }


def opportunities():
    counts: dict[str, int] = {}
    for r in _rows():
        o = r.get("opportunity_type") or "Experience"
        counts[o] = counts.get(o, 0) + 1
    out = []
    for t, (desc, action) in OPP_META.items():
        out.append({"type": t, "count": counts.get(t, 0), "description": desc, "action": action})
    return sorted(out, key=lambda x: -x["count"])


def opportunity_supporters(otype, limit=50):
    rows = [r for r in _rows() if (r.get("opportunity_type") or "Experience") == otype]
    rows = sorted(rows, key=lambda r: -(r.get("purchase_intent_score") or 0))[:limit]
    return [{
        "supporter_id": r["supporter_id"], "first_name": r.get("first_name"),
        "membership_tier": r.get("membership_tier"), "country": r.get("country"),
        "purchase_intent_score": r.get("purchase_intent_score") or 0,
        "recommended_action": r.get("recommended_action"),
    } for r in rows]
