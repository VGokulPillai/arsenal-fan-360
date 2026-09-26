"""Export the Gold Customer 360 + recent activity into JSON snapshots bundled
with the Databricks App (so the app always has data even before Lakebase loads).

Run AFTER the ML step so scores/reasons are final:
    python scripts/generate_snapshot.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dbsql as d  # noqa (reuse warehouse client)

CAT = "serverless_stable_1acr1x_catalog"
G = f"{CAT}.af360_gold.gold_supporter_360"
A = f"{CAT}.af360_gold.gold_supporter_activity"
OUT = os.path.join(os.path.dirname(__file__), "..", "app", "server", "data")
os.makedirs(OUT, exist_ok=True)

OPP = {
    "Match Ticket": "Ticket Intent", "Membership Upgrade": "Membership Opportunity",
    "Arsenal Shirt / Merchandise": "Merchandise Opportunity", "Hospitality": "Hospitality Opportunity",
    "Re-engagement Campaign": "Re-engagement", "Stadium Tour": "Experience",
}

cols = ["supporter_id","first_name","age_band","country","city","membership_tier",
        "favourite_player","favourite_product_category","season_ticket_holder",
        "total_ticket_spend","total_merchandise_spend","total_customer_value","matches_attended",
        "ticket_views_30d","product_views_30d","cart_abandons_30d","membership_views_30d",
        "marketing_opens_30d","marketing_clicks_30d","days_since_last_purchase",
        "days_since_last_activity","engagement_score","purchase_intent_score",
        "recommended_next_action","recommendation_reason"]

_, data = d.run(f"SELECT {','.join(cols)} FROM {G}")
profiles = []
for row in data:
    r = dict(zip(cols, row))
    r["recommended_action"] = r.pop("recommended_next_action")
    r["recommendation_reason"] = r.get("recommendation_reason")
    r["opportunity_type"] = OPP.get(r["recommended_action"], "Experience")
    # numeric casts
    for k in ["total_ticket_spend","total_merchandise_spend","total_customer_value"]:
        r[k] = float(r[k]) if r[k] is not None else 0.0
    for k in ["matches_attended","ticket_views_30d","product_views_30d","cart_abandons_30d",
              "membership_views_30d","marketing_opens_30d","marketing_clicks_30d",
              "days_since_last_purchase","days_since_last_activity","engagement_score","purchase_intent_score"]:
        r[k] = int(r[k]) if r[k] is not None else 0
    r["season_ticket_holder"] = str(r["season_ticket_holder"]).lower() == "true"
    profiles.append(r)

with open(os.path.join(OUT, "supporters_snapshot.json"), "w") as f:
    json.dump(profiles, f)
print(f"Wrote {len(profiles):,} supporter profiles -> supporters_snapshot.json")

# last 10 activities per supporter
_, adata = d.run(f"""
  SELECT supporter_id, channel, activity_type, activity_detail, CAST(activity_timestamp AS STRING)
  FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY supporter_id ORDER BY activity_timestamp DESC) rn
    FROM {A}
  ) WHERE rn <= 10
""")
activity: dict = {}
for sid, ch, at, det, ts in adata:
    activity.setdefault(sid, []).append(
        {"channel": ch, "activity_type": at, "activity_detail": det, "activity_timestamp": ts})
with open(os.path.join(OUT, "activity_snapshot.json"), "w") as f:
    json.dump(activity, f)
print(f"Wrote activity for {len(activity):,} supporters -> activity_snapshot.json")
