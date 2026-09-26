# Verified Genie Questions — Arsenal Supporter Intelligence

Space ID: `01f1b9fe891814be841d05a418e8b32d` · Warehouse: `Serverless Starter Warehouse`
Tables: `af360_gold.gold_supporter_360`, `af360_gold.gold_supporter_activity`

The questions below were run against the **live Genie Space** and returned the
results shown. Full transcript (NL answer + generated SQL + rows) is committed
in [`../evidence/genie_queries.txt`](../evidence/genie_queries.txt).

---

### 1. "What are the top 10 supporters by purchase intent?"
Genie generated a `RANK() OVER (ORDER BY purchase_intent_score DESC)` query and returned:

| supporter_id | first_name | intent | recommended_next_action |
|---|---|---|---|
| S004917 | Emile | 82 | Match Ticket |
| S003160 | Martin | 80 | Arsenal Shirt / Merchandise |
| S000246 | Gabriel | 78 | Arsenal Shirt / Merchandise |
| S001915 | Kenji | 78 | Membership Upgrade |
| … | … | … | … |

### 2. "Which non-members attended the most matches?"
Genie filtered `membership_tier IN ('None','Free')` and ranked by `matches_attended`:
> Top non-member: **Drew (S004309)** — tier None — **6 matches attended**.

### 3. "How much revenue came from members versus non-members?"
```sql
SELECT CASE WHEN membership_tier IN ('None','Free') THEN 'Non-member' ELSE 'Member' END AS membership_status,
       SUM(total_customer_value) AS total_revenue
FROM gold_supporter_360 GROUP BY 1
```
> Members **£501,764.99** · Non-members **£673,441.98**.

### 4. "Which supporters should receive a membership campaign?"
Genie returned non-members ordered by intent with the GenAI reason, e.g.
> **Kenji (S001915)** — None, intent 78 — *"recent membership page views and abandoned basket suggest he's close to purchasing."*

---

## Other supported / suggested questions

- "Which supporters viewed match tickets at least three times this month but haven't purchased?"
- "Which supporters abandoned a merchandise basket?"
- "Which merchandise category is most popular among international supporters?"
- "What are the biggest commercial opportunities right now?"

These are wired as the space's sample questions and are also handled by the app's
**Ask Arsenal** page (which embeds this Genie space, with a local analytics fallback).
