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
    "Ticket Intent": ("Viewed tickets multiple times but have not purchased.", "Match Ticket Offer",
                      "Ticketing / Fan Engagement", "Ticket conversion"),
    "Membership Opportunity": ("Frequent match attendees who are not currently members.", "Membership Upgrade",
                               "Head of Membership / Fan Engagement", "Membership conversion"),
    "Merchandise Opportunity": ("High product browsing or abandoned baskets.", "Merchandise Reminder",
                                "Retail / Ecommerce", "Merchandise revenue"),
    "Hospitality Opportunity": ("High spend and attendance — premium experience candidates.", "Hospitality Invite",
                                "Commercial / Hospitality", "Hospitality utilisation / revenue"),
    "Re-engagement": ("No meaningful interaction during the last 60 days.", "Re-engagement Campaign",
                      "CRM / Fan Engagement", "Reactivation rate"),
    "Experience": ("Engaged supporters to nurture with an experience offer.", "Stadium Tour",
                   "Fan Engagement", "Experience uptake"),
}

# Two explicit business personas (representative football-club executives — NOT
# real named Arsenal employees).
PERSONAS = {
    "economic_buyer": {
        "role": "Chief Commercial Officer",
        "kind": "Economic buyer",
        "pressures": [
            "Grow supporter revenue",
            "Improve ticket conversion",
            "Grow membership revenue",
            "Improve hospitality utilisation",
            "Increase revenue per supporter",
            "Reduce revenue lost from un-activated high-intent supporters",
        ],
    },
    "operational_owner": {
        "role": "Head of Fan Engagement / CRM",
        "kind": "Operational owner",
        "pressures": [
            "Identify high-intent supporters",
            "Prioritise campaign audiences",
            "Reduce generic blast campaigns",
            "Increase campaign conversion",
            "Re-engage lapsing supporters",
            "Activate supporters quickly",
        ],
    },
}

# Illustrative commercial assumptions (clearly labelled — NOT actual Arsenal
# financials). Tunable so the business case is transparent, not a hard-coded headline.
BUSINESS_CASE_ASSUMPTIONS = {
    "baseline_conversion_pct": 8.0,        # of addressable opportunity value converted without prioritisation
    "expected_uplift_pct": 25.0,           # relative conversion uplift from prioritised, AI-briefed activation
    "contribution_margin_pct": 60.0,       # gross contribution margin on incremental supporter value
    "annual_platform_cost_gbp": 120000,    # illustrative annual platform + team cost
    "representative_supporter_base": 250000,  # the demo profiles 5k supporters; a club's real CRM base is far larger
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
    agg: dict[str, dict] = {}
    for r in _rows():
        o = r.get("opportunity_type") or "Experience"
        a = agg.setdefault(o, {"count": 0, "value": 0.0, "intent_sum": 0})
        a["count"] += 1
        a["value"] += (r.get("total_customer_value") or 0)
        a["intent_sum"] += (r.get("purchase_intent_score") or 0)
    out = []
    for t, (desc, action, owner, kpi) in OPP_META.items():
        a = agg.get(t, {"count": 0, "value": 0.0, "intent_sum": 0})
        out.append({
            "type": t, "count": a["count"], "description": desc, "action": action,
            "owner": owner, "kpi": kpi,
            "value": round(a["value"]),
            "avg_intent": round(a["intent_sum"] / a["count"]) if a["count"] else 0,
        })
    return sorted(out, key=lambda x: -x["count"])


def executive():
    """Commercial command-centre metrics + illustrative business case.

    All 'observed' values are computed from the actual (synthetic) Gold data.
    """
    rows = _rows()
    total_value = sum(r.get("total_customer_value") or 0 for r in rows)
    high = [r for r in rows if (r.get("purchase_intent_score") or 0) >= 70]
    high_value = sum(r.get("total_customer_value") or 0 for r in high)

    def opp(otype):
        c = [r for r in rows if (r.get("opportunity_type") or "Experience") == otype]
        return {"count": len(c), "value": round(sum(r.get("total_customer_value") or 0 for r in c)),
                "avg_intent": round(sum(r.get("purchase_intent_score") or 0 for r in c) / len(c)) if c else 0}

    commercial_kpis = {
        "total_supporter_value": round(total_value),
        "high_intent_supporters": len(high),
        "high_intent_value": round(high_value),
        "membership_opportunity": opp("Membership Opportunity"),
        "hospitality_opportunity": opp("Hospitality Opportunity"),
        "reengagement_opportunity": opp("Re-engagement"),
        "ticket_intent": opp("Ticket Intent"),
        "merchandise_opportunity": opp("Merchandise Opportunity"),
    }

    # ---- Illustrative business case (labelled, assumption-driven) ----
    a = BUSINESS_CASE_ASSUMPTIONS
    # Addressable = supporter value tied to an ACTIONABLE commercial opportunity
    # (everything except the generic "Experience" nurture bucket), observed in the
    # synthetic sample, then scaled to a representative supporter base.
    actionable = [r for r in rows if (r.get("opportunity_type") or "Experience") != "Experience"]
    addressable_sample = sum(r.get("total_customer_value") or 0 for r in actionable)
    scale = (a["representative_supporter_base"] / len(rows)) if rows else 1.0
    addressable = addressable_sample * scale
    baseline_conv = a["baseline_conversion_pct"] / 100.0
    uplift = a["expected_uplift_pct"] / 100.0
    margin = a["contribution_margin_pct"] / 100.0
    cost = a["annual_platform_cost_gbp"]
    # incremental converted value = addressable × baseline conversion × relative uplift
    incremental_converted = addressable * baseline_conv * uplift
    incremental_contribution = incremental_converted * margin
    roi = (incremental_contribution - cost) / cost if cost else 0
    payback_months = (cost / (incremental_contribution / 12.0)) if incremental_contribution > 0 else None

    business_case = {
        "observed_from_data": {
            "high_intent_supporters": len(high),
            "actionable_opportunity_supporters": len(actionable),
            "addressable_supporter_value_sample": round(addressable_sample),
            "membership_opportunity_value": commercial_kpis["membership_opportunity"]["value"],
            "hospitality_opportunity_value": commercial_kpis["hospitality_opportunity"]["value"],
            "reengagement_opportunity_value": commercial_kpis["reengagement_opportunity"]["value"],
        },
        "assumptions": a,
        "illustrative_results": {
            "scaled_addressable_value": round(addressable),
            "incremental_converted_value": round(incremental_converted),
            "incremental_gross_contribution": round(incremental_contribution),
            "annual_platform_cost": cost,
            "roi_x": round(roi, 2),
            "roi_pct": round(roi * 100),
            "payback_months": round(payback_months, 1) if payback_months else None,
        },
        "disclaimer": "Illustrative scenario — not actual Arsenal financial performance. "
                      "Observed values are computed from synthetic supporter data (5,000-supporter sample); "
                      "the scenario scales the observed addressable opportunity to a representative supporter "
                      "base and applies the tunable assumptions above.",
    }
    return {"personas": PERSONAS, "commercial_kpis": commercial_kpis, "business_case": business_case}


def opportunity_supporters(otype, limit=50):
    rows = [r for r in _rows() if (r.get("opportunity_type") or "Experience") == otype]
    rows = sorted(rows, key=lambda r: -(r.get("purchase_intent_score") or 0))[:limit]
    return [{
        "supporter_id": r["supporter_id"], "first_name": r.get("first_name"),
        "membership_tier": r.get("membership_tier"), "country": r.get("country"),
        "purchase_intent_score": r.get("purchase_intent_score") or 0,
        "recommended_action": r.get("recommended_action"),
    } for r in rows]
