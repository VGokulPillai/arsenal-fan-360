"""Ask Arsenal - natural language supporter intelligence.

Primary path: Databricks Genie Space conversation API (if GENIE_SPACE_ID set).
Fallback path: a local analytics resolver over the in-memory supporter store so
the experience always works in a demo.
"""
import logging, time
from . import config, store

logger = logging.getLogger(__name__)

SUGGESTIONS = [
    # executive / commercial questions (CCO + Head of Fan Engagement)
    "How much supporter value sits in high-intent supporters?",
    "How much commercial value is associated with non-members?",
    "How many frequent attendees are not currently members?",
    "How much supporter value is currently flagged for hospitality?",
    "How many lapsing supporters should we re-engage?",
    "What are the biggest commercial opportunities by supporter value?",
]


def _rows():
    return list(store._profiles.values())


def _fmt(rows, cols):
    return [{c: r.get(c) for c in cols} for r in rows]


def _local_resolver(question: str):
    """Pattern-match a question to a computed answer + rows over supporter data."""
    q = question.lower()
    rows = _rows()

    if "highest intent" in q or "high intent" in q or "top" in q and "intent" in q:
        top = sorted(rows, key=lambda r: -(r.get("purchase_intent_score") or 0))[:10]
        data = _fmt(top, ["supporter_id", "first_name", "membership_tier", "purchase_intent_score", "recommended_action"])
        return f"The **top {len(data)} supporters by purchase intent** range from {data[0]['purchase_intent_score']} down to {data[-1]['purchase_intent_score']}/100. Most are candidates for their recommended next best action.", data

    if "ticket" in q and ("buy" in q or "likely" in q or "intent" in q or "purchas" in q):
        c = [r for r in rows if (r.get("ticket_views_30d") or 0) >= 2 and (r.get("recommended_action") == "Match Ticket" or (r.get("opportunity_type") == "Ticket Intent"))]
        c = sorted(c, key=lambda r: -(r.get("purchase_intent_score") or 0))[:15]
        data = _fmt(c, ["supporter_id", "first_name", "ticket_views_30d", "purchase_intent_score"])
        return f"**{len([r for r in rows if r.get('opportunity_type')=='Ticket Intent'])} supporters** show strong ticket intent (repeated ticket views, no recent purchase). Top prospects shown below.", data

    if "non-member" in q or ("member" in q and "attend" in q):
        c = [r for r in rows if r.get("membership_tier") in ("None", "Free")]
        c = sorted(c, key=lambda r: -(r.get("matches_attended") or 0))[:15]
        data = _fmt(c, ["supporter_id", "first_name", "membership_tier", "matches_attended", "purchase_intent_score"])
        return "**Non-members who attend the most matches** are prime Membership Upgrade targets:", data

    if "abandon" in q or "basket" in q or "cart" in q:
        c = [r for r in rows if (r.get("cart_abandons_30d") or 0) >= 1]
        c = sorted(c, key=lambda r: -(r.get("cart_abandons_30d") or 0))[:15]
        data = _fmt(c, ["supporter_id", "first_name", "cart_abandons_30d", "product_views_30d", "purchase_intent_score"])
        return f"**{len([r for r in rows if (r.get('cart_abandons_30d') or 0) >= 1])} supporters** abandoned a merchandise basket in the last 30 days:", data

    if "revenue" in q and "member" in q:
        mem = [r for r in rows if r.get("membership_tier") not in ("None", "Free")]
        non = [r for r in rows if r.get("membership_tier") in ("None", "Free")]
        mv = sum(r.get("total_customer_value") or 0 for r in mem)
        nv = sum(r.get("total_customer_value") or 0 for r in non)
        data = [{"segment": "Members", "supporters": len(mem), "revenue_gbp": round(mv)},
                {"segment": "Non-members", "supporters": len(non), "revenue_gbp": round(nv)}]
        return f"**Members** contributed £{round(mv):,} across {len(mem):,} supporters; **non-members** £{round(nv):,} across {len(non):,}.", data

    if "membership" in q and ("campaign" in q or "should" in q):
        c = [r for r in rows if r.get("recommended_action") == "Membership Upgrade"]
        c = sorted(c, key=lambda r: -(r.get("purchase_intent_score") or 0))[:15]
        data = _fmt(c, ["supporter_id", "first_name", "matches_attended", "membership_views_30d", "purchase_intent_score"])
        return f"**{len([r for r in rows if r.get('recommended_action')=='Membership Upgrade'])} supporters** should receive a membership campaign:", data

    if "opportunit" in q or "commercial" in q:
        opp = store.opportunities()
        data = [{"opportunity": o["type"], "supporters": o["count"], "recommended": o["action"]} for o in opp]
        return "The **biggest commercial opportunities** right now, ranked by supporter count:", data

    if "international" in q or "merch" in q:
        intl = [r for r in rows if r.get("country") not in ("United Kingdom",)]
        c = sorted(intl, key=lambda r: -(r.get("total_merchandise_spend") or 0))[:15]
        data = _fmt(c, ["supporter_id", "first_name", "country", "total_merchandise_spend"])
        return "**International supporters** ranked by merchandise spend:", data

    # default: high intent
    top = sorted(rows, key=lambda r: -(r.get("purchase_intent_score") or 0))[:10]
    data = _fmt(top, ["supporter_id", "first_name", "membership_tier", "purchase_intent_score", "recommended_action"])
    return "Here are our current highest-intent supporters — ask about tickets, membership, merchandise or revenue for more.", data


def _genie_space(question: str):
    """Query a real Genie Space (best-effort)."""
    if not config.GENIE_SPACE_ID:
        return None
    try:
        w = config.get_workspace_client()
        g = w.genie
        conv = g.start_conversation_and_wait(space_id=config.GENIE_SPACE_ID, content=question)
        # extract text + attachments
        text_parts, rows = [], []
        msg = conv.message if hasattr(conv, "message") else conv
        for att in (getattr(msg, "attachments", None) or []):
            if getattr(att, "text", None) and att.text.content:
                text_parts.append(att.text.content)
            if getattr(att, "query", None):
                res = g.get_message_query_result(config.GENIE_SPACE_ID, conv.conversation_id, msg.id)
                sr = res.statement_response
                if sr and sr.result and sr.result.data_array:
                    cols = [c.name for c in sr.manifest.schema.columns]
                    rows = [dict(zip(cols, r)) for r in sr.result.data_array[:15]]
                    if att.query.description:
                        text_parts.append(att.query.description)
        answer = "\n\n".join(text_parts) or "See results below."
        return {"answer": answer, "source": "Databricks Genie Space", "rows": rows}
    except Exception as e:
        logger.warning("Genie space query failed, using local resolver: %s", e)
        return None


def ask(question: str):
    res = _genie_space(question)
    if res:
        return res
    answer, rows = _local_resolver(question)
    return {"answer": answer, "source": "Arsenal Fan 360 analytics (Genie fallback)", "rows": rows}
