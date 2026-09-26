# Genie Space — Arsenal Supporter Intelligence

The **Arsenal Supporter Intelligence** Genie Space lets marketing / commercial
users query the governed Gold Customer 360 in natural language.

## Configuration

| Setting | Value |
|---|---|
| Space name | `Arsenal Supporter Intelligence` |
| Warehouse | `Serverless Starter Warehouse` (`4484f27c707c5a31`) |
| Catalog | `serverless_stable_1acr1x_catalog` |
| Tables | `af360_gold.gold_supporter_360`, `af360_gold.gold_supporter_activity` |

The space is created programmatically by `genie/create_genie_space.py`, which
registers the two Gold tables and seeds curated sample questions + SQL
instructions. The resulting `space_id` is written into the app's
`GENIE_SPACE_ID` environment variable so the **Ask Arsenal** page embeds the
live Genie experience (with a local analytics fallback).

## General instructions given to Genie

> This space answers questions about Arsenal supporters. One row per supporter
> lives in `gold_supporter_360` (features, `purchase_intent_score` 0–100,
> `recommended_next_action`, `recommendation_reason`). `membership_tier` values
> `None`/`Free` mean the supporter is **not** a paying member.
> `gold_supporter_activity` holds the cross-channel activity feed.
> "High intent" means `purchase_intent_score >= 70`.

## Curated / verified example questions

See `example_questions.md` for the full list with verified SQL and real
result snippets captured from the warehouse.
