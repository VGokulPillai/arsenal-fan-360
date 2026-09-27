"""AI Campaign Copilot for Arsenal Fan 360.

Turns a supporter's Customer-360 facts + the recommended Next Best Action into a
grounded, human-reviewable **campaign brief**. The LLM is instructed to use ONLY
the supplied facts (no invented behaviour). A deterministic template is used as a
fallback so the app always produces a brief.

Workflow: signal -> ML intent -> NBA -> GenAI explanation -> **GenAI campaign brief**
-> human review -> approve & activate -> write back to Lakebase.
"""
import json, logging
from . import config, store

logger = logging.getLogger(__name__)

# channel / KPI defaults per action (grounding scaffold for the brief)
_ACTION_META = {
    "Match Ticket": ("Email / App Push", "Ticket conversion", "Revenue per targeted supporter"),
    "Membership Upgrade": ("Email / Direct Mail", "Membership conversion", "Membership revenue"),
    "Arsenal Shirt / Merchandise": ("Email / Retargeting", "Merchandise conversion", "Merchandise revenue"),
    "Hospitality": ("Account Manager Outreach / Email", "Hospitality utilisation", "Hospitality revenue"),
    "Re-engagement Campaign": ("Email / App Push", "Reactivation rate", "Retained supporter value"),
    "Stadium Tour": ("Email / App Push", "Experience uptake", "Engagement score"),
}


def _facts(sid: str):
    r = store._profiles.get(sid)
    if not r:
        return None
    return {
        "supporter_id": sid,
        "first_name": r.get("first_name"),
        "membership_tier": r.get("membership_tier"),
        "country": r.get("country"),
        "matches_attended": r.get("matches_attended") or 0,
        "ticket_views_30d": r.get("ticket_views_30d") or 0,
        "product_views_30d": r.get("product_views_30d") or 0,
        "cart_abandons_30d": r.get("cart_abandons_30d") or 0,
        "membership_views_30d": r.get("membership_views_30d") or 0,
        "marketing_opens_30d": r.get("marketing_opens_30d") or 0,
        "days_since_last_activity": r.get("days_since_last_activity"),
        "total_customer_value": round(r.get("total_customer_value") or 0),
        "purchase_intent_score": r.get("purchase_intent_score") or 0,
        "recommended_action": r.get("recommended_action"),
        "recommendation_reason": r.get("recommendation_reason"),
    }


def _template_brief(f: dict) -> dict:
    action = f["recommended_action"] or "Stadium Tour"
    channel, kpi, skpi = _ACTION_META.get(action, ("Email", "Engagement", "Revenue per supporter"))
    why = f.get("recommendation_reason") or (
        f"{f['first_name']} has an intent score of {f['purchase_intent_score']}/100 with recent relevant activity."
    )
    return {
        "recommended_action": action,
        "objective": f"Convert {f['first_name']}'s current intent into a {action.lower()} outcome.",
        "why_now": why,
        "recommended_channel": channel,
        "offer_angle": "Relevant, timely and brand-appropriate — grounded in this supporter's recent behaviour.",
        "suggested_message": f"Hi {f['first_name']}, based on your recent activity we've lined up something for you. "
                             f"Explore your {action.lower()} options with Arsenal.",
        "primary_kpi": kpi,
        "supporting_kpi": skpi,
        "risk_guardrail": "Do not over-target recently contacted supporters; respect email opt-in and contact frequency caps.",
        "generated_by": "template (LLM unavailable)",
    }


_SYSTEM = (
    "You are Arsenal FC's supporter marketing copilot. Given ONLY the supporter facts provided, "
    "write a concise, grounded campaign brief. Do NOT invent any behaviour, spend, or attributes "
    "that are not in the facts. Keep the tone brand-appropriate and professional. "
    "Return STRICT JSON with exactly these keys: objective, why_now, recommended_channel, "
    "offer_angle, suggested_message, primary_kpi, supporting_kpi, risk_guardrail. "
    "suggested_message must be <= 45 words."
)


def brief(sid: str) -> dict:
    f = _facts(sid)
    if not f:
        return {"error": "supporter not found"}
    action = f["recommended_action"] or "Stadium Tour"
    channel, kpi, skpi = _ACTION_META.get(action, ("Email", "Engagement", "Revenue per supporter"))
    prompt = (
        f"Supporter facts (the ONLY facts you may use):\n{json.dumps(f, indent=2)}\n\n"
        f"Recommended next best action: {action}.\n"
        f"Default channel: {channel}. Primary KPI: {kpi}. Supporting KPI: {skpi}.\n"
        "Write the campaign brief as strict JSON now."
    )
    try:
        from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
        w = config.get_workspace_client()
        resp = w.serving_endpoints.query(
            name=config.SERVING_ENDPOINT,
            messages=[
                ChatMessage(role=ChatMessageRole.SYSTEM, content=_SYSTEM),
                ChatMessage(role=ChatMessageRole.USER, content=prompt),
            ],
            max_tokens=400, temperature=0.4,
        )
        content = resp.choices[0].message.content.strip()
        # strip code fences if present
        if content.startswith("```"):
            content = content.split("```")[1].lstrip("json").strip() if "```" in content else content
        data = json.loads(content)
        out = {
            "recommended_action": action,
            "objective": data.get("objective", ""),
            "why_now": data.get("why_now", ""),
            "recommended_channel": data.get("recommended_channel", channel),
            "offer_angle": data.get("offer_angle", ""),
            "suggested_message": data.get("suggested_message", ""),
            "primary_kpi": data.get("primary_kpi", kpi),
            "supporting_kpi": data.get("supporting_kpi", skpi),
            "risk_guardrail": data.get("risk_guardrail", "Respect contact frequency caps and opt-in."),
            "generated_by": f"GenAI ({config.SERVING_ENDPOINT})",
        }
        out["disclaimer"] = "AI-generated campaign brief — human approval required. No campaign is sent automatically."
        return out
    except Exception as e:
        logger.warning("Copilot LLM failed, using template: %s", e)
        out = _template_brief(f)
        out["disclaimer"] = "AI-generated campaign brief — human approval required. No campaign is sent automatically."
        return out
