"""Create the 'Arsenal Supporter Intelligence' Genie Space over the Gold tables.

Genie Space creation APIs are in preview and vary by workspace. This script
attempts the REST API and prints the resulting space_id (to set as
GENIE_SPACE_ID for the app). If the API is unavailable it prints the manual
setup steps. Either way the app's Ask Arsenal page works via its analytics
fallback, and verified example questions are captured in example_questions.md.
"""
import json
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

PROFILE = "fe-vm-serverless-stable-1acr1x"
WAREHOUSE = "4484f27c707c5a31"
CAT = "serverless_stable_1acr1x_catalog"
TABLES = [f"{CAT}.af360_gold.gold_supporter_360", f"{CAT}.af360_gold.gold_supporter_activity"]

INSTRUCTION = (
    "This space answers questions about Arsenal supporters. One row per supporter "
    "lives in gold_supporter_360 (features, purchase_intent_score 0-100, "
    "recommended_next_action, recommendation_reason). membership_tier values 'None'/'Free' "
    "mean the supporter is NOT a paying member. 'High intent' means purchase_intent_score >= 70. "
    "gold_supporter_activity holds the cross-channel activity feed."
)
SAMPLE_QS = [
    "What are the top 10 supporters by purchase intent?",
    "Which non-members attended the most matches?",
    "Which supporters abandoned a merchandise basket in the last 30 days?",
    "Which supporters should receive a membership campaign?",
    "How much revenue came from members versus non-members?",
]


def main():
    w = WorkspaceClient(config=Config(profile=PROFILE))
    body = {
        "title": "Arsenal Supporter Intelligence",
        "description": "Natural-language analysis of the Arsenal Fan 360 Customer 360.",
        "warehouse_id": WAREHOUSE,
        "table_identifiers": TABLES,
        "instructions": INSTRUCTION,
        "sample_questions": SAMPLE_QS,
    }
    for path in ("/api/2.0/genie/spaces", "/api/2.0/data-rooms"):
        try:
            resp = w.api_client.do("POST", path, body=body)
            sid = resp.get("space_id") or resp.get("id")
            print(f"[OK] Created Genie space via {path}: space_id={sid}")
            print(f"Set app env GENIE_SPACE_ID={sid}")
            return
        except Exception as e:
            print(f"[skip] {path}: {str(e)[:120]}")
    print("\nGenie Space REST creation not available in this workspace.")
    print("Manual setup: Databricks UI > Genie > New Space > add tables:")
    for t in TABLES:
        print("   -", t)
    print("Then set GENIE_SPACE_ID in app.yaml. The app already works via fallback.")


if __name__ == "__main__":
    main()
