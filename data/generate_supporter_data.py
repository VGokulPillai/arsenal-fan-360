"""
Arsenal Fan 360 - Synthetic Supporter Data Generator
=====================================================

Generates realistic but 100% synthetic Arsenal supporter data for the
"Fan 360 - Next Best Action" prototype. No real PII is used.

Outputs 5 raw CSV files (one per source system) into ./raw_data:

    supporters.csv        ~5,000 rows   (CRM / membership)
    web_events.csv       ~20,000 rows   (digital / clickstream)
    ecommerce_orders.csv  ~8,000 rows   (retail / merchandise)
    ticket_orders.csv     ~5,000 rows   (ticketing)
    marketing_events.csv ~10,000 rows   (marketing / CRM campaigns)

The data intentionally contains behavioural "signals" so the downstream
intelligence layer has something meaningful to discover:

  * ticket-browsers who never buy          -> Match Ticket offer
  * shirt-browsers who abandon baskets     -> Merchandise reminder
  * frequent attendees who aren't members  -> Membership upgrade
  * high spend + high attendance           -> Hospitality opportunity
  * lapsed supporters                      -> Re-engagement campaign
  * international merch-only supporters     -> localised merch offers

Usage:
    python generate_supporter_data.py --out ./raw_data --seed 7
"""
from __future__ import annotations

import argparse
import csv
import os
import random
from datetime import datetime, timedelta

# ----------------------------------------------------------------------------
# Reference data
# ----------------------------------------------------------------------------
FIRST_NAMES = [
    "Alex", "Jordan", "Sam", "Charlie", "Morgan", "Taylor", "Jamie", "Riley",
    "Cameron", "Drew", "Reese", "Skyler", "Devon", "Harper", "Rowan", "Quinn",
    "Emile", "Bukayo", "Gabriel", "Martin", "Declan", "Kai", "Leah", "Beth",
    "Vivianne", "Katie", "Amara", "Noor", "Kenji", "Sofia", "Mateo", "Liam",
    "Olivia", "Chidi", "Priya", "Wei", "Hassan", "Ingrid", "Diego", "Yuki",
]

COUNTRIES = [
    ("United Kingdom", ["London", "Manchester", "Birmingham", "Leeds", "Bristol"], 0.55),
    ("United States", ["New York", "Los Angeles", "Chicago", "Boston", "Dallas"], 0.14),
    ("Nigeria", ["Lagos", "Abuja", "Kano"], 0.06),
    ("India", ["Mumbai", "Delhi", "Bengaluru"], 0.06),
    ("Germany", ["Berlin", "Munich", "Hamburg"], 0.04),
    ("Norway", ["Oslo", "Bergen"], 0.03),
    ("Nigeria", ["Ibadan"], 0.0),  # padding, weight handled below
    ("Japan", ["Tokyo", "Osaka"], 0.04),
    ("Canada", ["Toronto", "Vancouver"], 0.04),
    ("Australia", ["Sydney", "Melbourne"], 0.04),
]

AGE_BANDS = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
MEMBERSHIP_TIERS = ["None", "Free", "Silver", "Gold", "Red Member"]
PLAYERS = [
    "Bukayo Saka", "Martin Odegaard", "Declan Rice", "Gabriel Jesus",
    "William Saliba", "Gabriel Martinelli", "Kai Havertz", "Ben White",
    "Leah Williamson", "Beth Mead", "Vivianne Miedema",
]
PRODUCT_CATEGORIES = ["Home Shirt", "Away Shirt", "Third Kit", "Training Wear",
                      "Accessories", "Retro", "Kids", "Hospitality"]

MATCHES = [
    ("Arsenal vs Tottenham", "Premier League", 95),
    ("Arsenal vs Man City", "Premier League", 92),
    ("Arsenal vs Liverpool", "Premier League", 90),
    ("Arsenal vs Chelsea", "Premier League", 88),
    ("Arsenal vs Man United", "Premier League", 85),
    ("Arsenal vs Bayern Munich", "Champions League", 96),
    ("Arsenal vs Real Madrid", "Champions League", 97),
    ("Arsenal vs Brighton", "Premier League", 62),
    ("Arsenal vs Everton", "Premier League", 58),
    ("Arsenal vs Fulham", "Premier League", 55),
    ("Arsenal vs Sheffield Utd", "Carabao Cup", 45),
    ("Arsenal vs Luton", "Premier League", 50),
]

TICKET_TYPES = ["General Admission", "Club Level", "Family Enclosure",
                "Hospitality", "Away End"]

CAMPAIGNS = [
    "Season Ticket Renewal", "New Home Kit Launch", "Membership Drive",
    "Champions League Hospitality", "Black Friday Store", "Matchday Ticket Alert",
    "Stadium Tour Promo", "International Fan Club", "Re-engagement Winback",
]

WEB_PAGE_TYPES = {
    "viewed_match_ticket": ("Tickets", "Buy Match Tickets"),
    "viewed_home_shirt": ("Store", "2024/25 Home Shirt"),
    "viewed_away_shirt": ("Store", "2024/25 Away Shirt"),
    "added_to_cart": ("Store", "Cart"),
    "abandoned_cart": ("Store", "Cart Abandoned"),
    "viewed_membership": ("Membership", "Become a Member"),
    "viewed_hospitality": ("Hospitality", "Club Level & Boxes"),
    "viewed_stadium_tour": ("Experience", "Emirates Stadium Tour"),
    "viewed_fixtures": ("Fixtures", "Upcoming Fixtures"),
    "viewed_news": ("News", "Latest News"),
}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def weighted_country(rng: random.Random):
    roll = rng.random()
    cum = 0.0
    table = [
        ("United Kingdom", ["London", "Manchester", "Birmingham", "Leeds", "Bristol", "Liverpool"], 0.55),
        ("United States", ["New York", "Los Angeles", "Chicago", "Boston", "Dallas"], 0.14),
        ("Nigeria", ["Lagos", "Abuja", "Kano", "Ibadan"], 0.06),
        ("India", ["Mumbai", "Delhi", "Bengaluru"], 0.06),
        ("Germany", ["Berlin", "Munich", "Hamburg"], 0.04),
        ("Norway", ["Oslo", "Bergen"], 0.03),
        ("Japan", ["Tokyo", "Osaka"], 0.03),
        ("Canada", ["Toronto", "Vancouver"], 0.03),
        ("Australia", ["Sydney", "Melbourne"], 0.03),
        ("United Arab Emirates", ["Dubai", "Abu Dhabi"], 0.03),
    ]
    for country, cities, w in table:
        cum += w
        if roll <= cum:
            return country, rng.choice(cities)
    return "United Kingdom", "London"


def rand_ts(rng: random.Random, start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=rng.randint(0, int(delta.total_seconds())))


# ----------------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------------
def generate(out_dir: str, seed: int,
             n_supporters=5000, n_web=20000, n_ecom=8000,
             n_tickets=5000, n_marketing=10000):
    rng = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)

    now = datetime(2025, 9, 20, 12, 0, 0)
    window_start = now - timedelta(days=365)
    recent_start = now - timedelta(days=30)

    # ---- Supporters -------------------------------------------------------
    supporters = []
    # persona assignment drives downstream behaviour
    #   ticket_browser, cart_abandoner, loyal_attendee, big_spender,
    #   lapsed, intl_merch, casual
    persona_weights = [
        ("ticket_browser", 0.14),
        ("cart_abandoner", 0.13),
        ("loyal_attendee", 0.12),
        ("big_spender", 0.10),
        ("lapsed", 0.14),
        ("intl_merch", 0.12),
        ("casual", 0.25),
    ]

    def pick_persona():
        roll = rng.random()
        cum = 0.0
        for name, w in persona_weights:
            cum += w
            if roll <= cum:
                return name
        return "casual"

    personas = {}
    for i in range(1, n_supporters + 1):
        sid = f"S{i:06d}"
        persona = pick_persona()
        personas[sid] = persona
        country, city = weighted_country(rng)

        # membership tier depends on persona
        if persona == "loyal_attendee":
            tier = rng.choice(["None", "Free", "Silver"])  # attendee but not premium member
        elif persona == "big_spender":
            tier = rng.choice(["Gold", "Red Member", "Silver"])
        elif persona == "lapsed":
            tier = rng.choice(["None", "Free"])
        elif persona == "intl_merch":
            tier = rng.choice(["None", "Free", "Silver"])
        else:
            tier = rng.choices(MEMBERSHIP_TIERS, weights=[30, 25, 20, 15, 10])[0]

        season_ticket = tier in ("Gold", "Red Member") and rng.random() < 0.6
        reg_date = rand_ts(rng, datetime(2016, 1, 1), now - timedelta(days=30)).date()

        supporters.append({
            "supporter_id": sid,
            "first_name": rng.choice(FIRST_NAMES),
            "age_band": rng.choices(AGE_BANDS, weights=[18, 28, 22, 15, 10, 7])[0],
            "country": country,
            "city": city,
            "membership_tier": tier,
            "favourite_player": rng.choice(PLAYERS),
            "favourite_product_category": rng.choice(PRODUCT_CATEGORIES),
            "registration_date": reg_date.isoformat(),
            "email_opt_in": rng.random() < 0.82,
            "season_ticket_holder": season_ticket,
        })

    # inject a small number of intentional dirty rows to exercise Silver cleaning
    dirty = rng.sample(supporters, 40)
    for d in dirty[:20]:
        d["country"] = d["country"].upper()          # inconsistent casing
    for d in dirty[20:30]:
        d["membership_tier"] = "  " + d["membership_tier"] + " "  # whitespace
    for d in dirty[30:40]:
        d["age_band"] = ""                            # missing value

    _write_csv(os.path.join(out_dir, "supporters.csv"), supporters)

    sids = [s["supporter_id"] for s in supporters]

    # ---- Web events -------------------------------------------------------
    web = []
    order_id_seq = 1
    for _ in range(n_web):
        sid = rng.choice(sids)
        persona = personas[sid]
        # bias event type by persona
        if persona == "ticket_browser":
            et = rng.choices(list(WEB_PAGE_TYPES), weights=[45, 8, 6, 5, 3, 6, 4, 3, 12, 8])[0]
        elif persona == "cart_abandoner":
            et = rng.choices(list(WEB_PAGE_TYPES), weights=[6, 30, 22, 18, 14, 3, 2, 2, 2, 1])[0]
        elif persona == "loyal_attendee":
            et = rng.choices(list(WEB_PAGE_TYPES), weights=[20, 8, 6, 4, 2, 22, 6, 6, 18, 8])[0]
        elif persona == "intl_merch":
            et = rng.choices(list(WEB_PAGE_TYPES), weights=[4, 30, 26, 16, 8, 4, 2, 3, 4, 3])[0]
        elif persona == "lapsed":
            et = rng.choices(list(WEB_PAGE_TYPES), weights=[8, 6, 6, 4, 4, 6, 4, 6, 30, 26])[0]
        else:
            et = rng.choice(list(WEB_PAGE_TYPES))

        page_type, page_name = WEB_PAGE_TYPES[et]

        # recency: lapsed users skew old, others skew recent
        if persona == "lapsed":
            ts = rand_ts(rng, window_start, now - timedelta(days=60))
        elif rng.random() < 0.6:
            ts = rand_ts(rng, recent_start, now)   # 60% in last 30d
        else:
            ts = rand_ts(rng, window_start, now)

        web.append({
            "supporter_id": sid,
            "event_timestamp": ts.isoformat(sep=" "),
            "page_type": page_type,
            "page_name": page_name,
            "product_id": f"P{rng.randint(1000, 1099)}" if page_type == "Store" else "",
            "match_id": f"M{rng.randint(1, len(MATCHES)):03d}" if et == "viewed_match_ticket" else "",
            "session_id": f"SESS{rng.randint(100000, 999999)}",
            "event_type": et,
        })
    _write_csv(os.path.join(out_dir, "web_events.csv"), web)

    # ---- Ecommerce orders -------------------------------------------------
    ecom = []
    for _ in range(n_ecom):
        # big_spender & intl_merch dominate
        sid = rng.choice(sids)
        persona = personas[sid]
        # skip most orders for pure ticket_browsers / lapsed to keep signal
        if persona in ("ticket_browser", "lapsed") and rng.random() < 0.7:
            sid = rng.choice(sids)
            persona = personas[sid]

        cat = rng.choice(PRODUCT_CATEGORIES[:-1])  # exclude Hospitality from merch
        qty = rng.choices([1, 1, 1, 2, 3], weights=[50, 20, 15, 10, 5])[0]
        base_price = {
            "Home Shirt": 80, "Away Shirt": 80, "Third Kit": 75,
            "Training Wear": 55, "Accessories": 20, "Retro": 65, "Kids": 50,
        }.get(cat, 40)
        rev = round(base_price * qty * rng.uniform(0.9, 1.25), 2)
        ts = rand_ts(rng, window_start, now) if rng.random() < 0.55 else rand_ts(rng, recent_start, now)
        oid = f"O{order_id_seq:07d}"
        order_id_seq += 1
        ecom.append({
            "supporter_id": sid,
            "order_id": oid,
            "product": f"{cat} 2024/25",
            "category": cat,
            "quantity": qty,
            "revenue": rev,
            "purchase_timestamp": ts.isoformat(sep=" "),
        })
    # duplicate a handful of orders to test Silver de-duplication
    for dup in rng.sample(ecom, 30):
        ecom.append(dict(dup))
    _write_csv(os.path.join(out_dir, "ecommerce_orders.csv"), ecom)

    # ---- Ticket orders ----------------------------------------------------
    tickets = []
    for _ in range(n_tickets):
        sid = rng.choice(sids)
        persona = personas[sid]
        # loyal_attendee & big_spender buy more tickets; ticket_browser rarely buys
        if persona == "ticket_browser" and rng.random() < 0.85:
            sid = rng.choice(sids)
            persona = personas[sid]
        match, comp, appeal = rng.choice(MATCHES)
        ttype = rng.choices(TICKET_TYPES, weights=[45, 20, 15, 12, 8])[0]
        price = {
            "General Admission": 55, "Club Level": 120, "Family Enclosure": 45,
            "Hospitality": 350, "Away End": 40,
        }[ttype]
        price = round(price * rng.uniform(0.9, 1.3), 2)
        ts = rand_ts(rng, window_start, now)
        attended = rng.random() < (0.9 if persona in ("loyal_attendee", "big_spender") else 0.75)
        tickets.append({
            "supporter_id": sid,
            "match": match,
            "competition": comp,
            "ticket_type": ttype,
            "ticket_price": price,
            "purchase_timestamp": ts.isoformat(sep=" "),
            "attended": attended,
        })
    _write_csv(os.path.join(out_dir, "ticket_orders.csv"), tickets)

    # ---- Marketing events -------------------------------------------------
    marketing = []
    for _ in range(n_marketing):
        sid = rng.choice(sids)
        persona = personas[sid]
        campaign = rng.choice(CAMPAIGNS)
        sent = True
        # engagement depends on persona & opt-in
        opt_in = next(s["email_opt_in"] for s in supporters if s["supporter_id"] == sid) \
            if False else True  # optimisation: assume sent means reachable
        open_p = {
            "loyal_attendee": 0.62, "big_spender": 0.58, "ticket_browser": 0.5,
            "cart_abandoner": 0.48, "intl_merch": 0.45, "casual": 0.32, "lapsed": 0.12,
        }[persona]
        opened = rng.random() < open_p
        clicked = opened and rng.random() < 0.4
        converted = clicked and rng.random() < 0.22
        if persona == "lapsed":
            ts = rand_ts(rng, window_start, now - timedelta(days=45))
        else:
            ts = rand_ts(rng, window_start, now) if rng.random() < 0.5 else rand_ts(rng, recent_start, now)
        marketing.append({
            "supporter_id": sid,
            "campaign": campaign,
            "sent": sent,
            "opened": opened,
            "clicked": clicked,
            "converted": converted,
            "timestamp": ts.isoformat(sep=" "),
        })
    _write_csv(os.path.join(out_dir, "marketing_events.csv"), marketing)

    # ---- Summary ----------------------------------------------------------
    summary = {
        "supporters": len(supporters),
        "web_events": len(web),
        "ecommerce_orders": len(ecom),
        "ticket_orders": len(tickets),
        "marketing_events": len(marketing),
    }
    return summary


def _write_csv(path: str, rows: list[dict]):
    if not rows:
        return
    fields = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./raw_data")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    summary = generate(args.out, args.seed)
    print("=" * 60)
    print("Arsenal Fan 360 - synthetic data generated")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k:<20} {v:>8,} rows")
    print(f"\nOutput directory: {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
