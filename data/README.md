# Synthetic Supporter Data — design & realism

All Arsenal Fan 360 data is **100% synthetic** (no real supporter PII). The generator
(`generate_supporter_data.py`, Python standard library only) is **deterministic** for a
given `--seed`, so the whole pipeline is reproducible.

```bash
python3 data/generate_supporter_data.py --out data/raw_data --seed 7
```

It emits five raw source extracts and writes a computed profile to
[`../evidence/synthetic_data_profile.txt`](../evidence/synthetic_data_profile.txt).
Every statistic in that profile is **calculated from the generated records** — nothing is hard-coded.

| File | Valid rows | Represents |
|---|---|---|
| `supporters.csv` | 5,000 | CRM / membership dimension |
| `web_events.csv` | 20,000 | digital clickstream (arsenal.com / app) |
| `ecommerce_orders.csv` | 8,030 (incl. 30 dupes) | online store / merchandise |
| `ticket_orders.csv` | 5,000 | matchday ticketing |
| `marketing_events.csv` | 10,000 | email / campaign interactions |

## Personas drive behaviour (not random noise)

Each supporter is assigned a **persona** that shapes their web, purchase, attendance and
marketing behaviour. This is what makes the intent model and Next Best Action engine find
*real, explainable* signals rather than noise. Approximate mix (see profile for exact counts):

| Persona | ~share | Behavioural signature | Intended Next Best Action |
|---|---|---|---|
| `ticket_browser` | 14% | repeatedly views match tickets, rarely completes a purchase | **Match Ticket** |
| `cart_abandoner` | 13% | heavy product views + abandoned baskets | **Merchandise** |
| `loyal_attendee` | 12% | attends many matches, often **not** a paid member | **Membership Upgrade** |
| `big_spender` | 10% | high merch + hospitality spend, premium tiers | **Hospitality** |
| `lapsed` | 14% | activity skewed 60–365 days ago, low email opens | **Re-engagement** |
| `intl_merch` | 12% | non-UK, merch-heavy, low attendance | **Merchandise / Experience** cross-sell |
| `casual` | 25% | light, mixed activity | nurture / **Stadium Tour** |

## Intentional correlations (realistic, not perfect)

- **Membership ↔ attendance**: `loyal_attendee`s attend a lot but are seeded into low tiers
  (None/Free/Silver), creating a genuine membership-upgrade opportunity.
- **Value ↔ hospitality**: `big_spender`s carry the highest merch/ticket spend and premium
  tiers, so hospitality propensity tracks lifetime value.
- **Browsing ↔ intent**: ticket/product/membership page views in the last 30 days feed both
  the rule-based baseline and the ML intent score.
- **Opt-in & persona ↔ email engagement**: open/click/convert probabilities differ by persona
  (`loyal_attendee` ≈ 62% open, `lapsed` ≈ 12% open) — engagement is probabilistic, not perfect.
- **Country distribution**: ~55% UK, then US/Nigeria/India/Germany/Japan/etc., so international
  cross-sell cohorts are meaningful.

## Temporal realism

- **Recency weighting**: ~55% of web events fall in the last 30 days; active supporters skew
  recent while `lapsed` supporters are pushed 60–365 days into the past. The Gold layer computes
  30-day windows (`ticket_views_30d`, `product_views_30d`, …) and recency features
  (`days_since_last_activity`, `days_since_last_purchase`) directly from these timestamps.
- **Attendance vs. intent**: ticket *views* without a matching *purchase* are what flag ticket
  intent — the recency of those views matters, so timing is modelled, not flat.
- **Campaign engagement** clusters within the campaign send windows across the season.

## Data-quality edge cases (so pipeline expectations have something to catch)

The generator deliberately injects two classes of imperfect data:

**Dirty-but-usable (cleaned in Silver, not dropped):**
- inconsistent country casing (e.g. `LONDON`) → `INITCAP`
- leading/trailing whitespace on membership tier → `TRIM`
- missing `age_band` → coalesced to `Unknown`
- **30 duplicate ecommerce orders** → de-duplicated on `order_id`

**Malformed (DROP via Lakeflow expectations, preserved in quarantine tables):**
- `supporters`: 2 rows with missing `supporter_id`
- `web_events`: 5 rows (missing `supporter_id`, missing/`not-a-timestamp` `event_timestamp`, unknown `event_type`)
- `ecommerce_orders`: 4 rows (missing `order_id`/`supporter_id`, **negative revenue**)
- `ticket_orders`: 2 rows (missing `supporter_id`, **negative price**)
- `marketing_events`: 2 rows (missing `supporter_id`, missing timestamp)

These malformed rows are appended **after** all valid draws, so the 5,000 valid supporters and
their events stay byte-identical across runs. The declarative pipeline
(`../lakeflow/pipeline.py`) drops them via `@dp.expect_all_or_drop` and routes them to
`*_quarantine` tables; the counts show up in
[`../evidence/lakeflow_quality_results.txt`](../evidence/lakeflow_quality_results.txt).
