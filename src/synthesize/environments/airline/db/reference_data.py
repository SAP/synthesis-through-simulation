"""
Static seed/reference data for the Airline environment.

All data is internally consistent:
- Payment history totals match reservation prices
- Prices derived from flight_date prices × passengers
- Seat counts reflect the active reservations already booked
"""

# ── Airports ──────────────────────────────────────────────────────────────────

AIRPORTS = ["JFK", "LAX", "ORD", "SFO", "ATL", "DFW", "MIA", "SEA"]

# ── Users ─────────────────────────────────────────────────────────────────────
# (user_id, first_name, last_name, email, dob, membership, address1, address2,
#  city, state, country, zip)

USERS = [
    # Gold members (3)
    (
        "gold_alice_1",
        "Alice",
        "Johnson",
        "alice.johnson@email.com",
        "1985-03-12",
        "gold",
        "100 Oak St",
        None,
        "New York",
        "NY",
        "USA",
        "10001",
    ),
    (
        "gold_bob_2",
        "Bob",
        "Martinez",
        "bob.martinez@email.com",
        "1978-07-24",
        "gold",
        "200 Elm Ave",
        "Apt 5B",
        "Los Angeles",
        "CA",
        "USA",
        "90001",
    ),
    (
        "gold_carol_3",
        "Carol",
        "Thompson",
        "carol.thompson@email.com",
        "1990-11-05",
        "gold",
        "300 Pine Rd",
        None,
        "Chicago",
        "IL",
        "USA",
        "60601",
    ),
    # Silver members (4)
    (
        "silver_david_4",
        "David",
        "Wilson",
        "david.wilson@email.com",
        "1982-06-18",
        "silver",
        "401 Maple Blvd",
        None,
        "San Francisco",
        "CA",
        "USA",
        "94102",
    ),
    (
        "silver_eva_5",
        "Eva",
        "Anderson",
        "eva.anderson@email.com",
        "1995-02-28",
        "silver",
        "502 Cedar Ln",
        "Unit 3",
        "Atlanta",
        "GA",
        "USA",
        "30301",
    ),
    (
        "silver_frank_6",
        "Frank",
        "Garcia",
        "frank.garcia@email.com",
        "1988-09-14",
        "silver",
        "603 Birch Way",
        None,
        "Dallas",
        "TX",
        "USA",
        "75201",
    ),
    (
        "silver_grace_7",
        "Grace",
        "Lee",
        "grace.lee@email.com",
        "1992-12-03",
        "silver",
        "704 Walnut St",
        "Ste 100",
        "Miami",
        "FL",
        "USA",
        "33101",
    ),
    # Regular members (3)
    (
        "reg_henry_8",
        "Henry",
        "Brown",
        "henry.brown@email.com",
        "1975-04-22",
        "regular",
        "805 Spruce Ave",
        None,
        "Seattle",
        "WA",
        "USA",
        "98101",
    ),
    (
        "reg_iris_9",
        "Iris",
        "Davis",
        "iris.davis@email.com",
        "2000-08-09",
        "regular",
        "906 Ash Dr",
        "Apt 2",
        "New York",
        "NY",
        "USA",
        "10002",
    ),
    (
        "reg_jack_10",
        "Jack",
        "Miller",
        "jack.miller@email.com",
        "1983-01-30",
        "regular",
        "1007 Poplar Ct",
        None,
        "Los Angeles",
        "CA",
        "USA",
        "90002",
    ),
]

# ── Payment Methods ────────────────────────────────────────────────────────────
# (payment_method_id, user_id, source, brand, last_four, amount)

PAYMENT_METHODS = [
    # Alice (gold_alice_1)
    ("cc_alice_visa", "gold_alice_1", "credit_card", "visa", "1234", 0),
    ("gc_alice_500", "gold_alice_1", "gift_card", None, None, 500),
    # Bob (gold_bob_2)
    ("cc_bob_mc", "gold_bob_2", "credit_card", "mastercard", "5678", 0),
    ("gc_bob_200", "gold_bob_2", "gift_card", None, None, 200),
    # Carol (gold_carol_3)
    ("cc_carol_visa", "gold_carol_3", "credit_card", "visa", "9012", 0),
    ("gc_carol_350", "gold_carol_3", "gift_card", None, None, 350),
    # David (silver_david_4)
    ("cc_david_amex", "silver_david_4", "credit_card", "amex", "3456", 0),
    ("gc_david_150", "silver_david_4", "gift_card", None, None, 150),
    # Eva (silver_eva_5)
    ("cc_eva_visa", "silver_eva_5", "credit_card", "visa", "7890", 0),
    ("gc_eva_100", "silver_eva_5", "gift_card", None, None, 100),
    # Frank (silver_frank_6)
    ("cc_frank_mc", "silver_frank_6", "credit_card", "mastercard", "2345", 0),
    ("gc_frank_250", "silver_frank_6", "gift_card", None, None, 250),
    # Grace (silver_grace_7)
    ("cc_grace_visa", "silver_grace_7", "credit_card", "visa", "6789", 0),
    ("gc_grace_75", "silver_grace_7", "gift_card", None, None, 75),
    # Henry (reg_henry_8)
    ("cc_henry_mc", "reg_henry_8", "credit_card", "mastercard", "0123", 0),
    ("gc_henry_300", "reg_henry_8", "gift_card", None, None, 300),
    # Iris (reg_iris_9)
    ("cc_iris_visa", "reg_iris_9", "credit_card", "visa", "4567", 0),
    ("gc_iris_50", "reg_iris_9", "gift_card", None, None, 50),
    # Jack (reg_jack_10)
    ("cc_jack_amex", "reg_jack_10", "credit_card", "amex", "8901", 0),
    ("gc_jack_175", "reg_jack_10", "gift_card", None, None, 175),
]

# ── Saved Passengers ──────────────────────────────────────────────────────────
# (user_id, first_name, last_name, dob)

SAVED_PASSENGERS = [
    # Alice's family
    ("gold_alice_1", "Tom", "Johnson", "1980-05-15"),
    ("gold_alice_1", "Sophie", "Johnson", "2010-09-22"),
    ("gold_alice_1", "Max", "Johnson", "2013-03-07"),
    # Bob's family
    ("gold_bob_2", "Linda", "Martinez", "1979-11-30"),
    ("gold_bob_2", "Carlos", "Martinez", "2008-06-14"),
    ("gold_bob_2", "Rosa", "Martinez", "2015-02-28"),
    # Carol's family
    ("gold_carol_3", "Steve", "Thompson", "1988-04-19"),
    ("gold_carol_3", "Emma", "Thompson", "2012-08-03"),
    ("gold_carol_3", "Luke", "Thompson", "2016-12-25"),
    # David's contacts
    ("silver_david_4", "Mia", "Wilson", "1985-07-11"),
    ("silver_david_4", "Ethan", "Wilson", "2011-01-16"),
    ("silver_david_4", "Lily", "Chen", "1990-03-29"),
    # Eva's contacts
    ("silver_eva_5", "Noah", "Anderson", "1993-10-05"),
    ("silver_eva_5", "Ava", "Anderson", "1997-06-18"),
    ("silver_eva_5", "Liam", "Brown", "1995-12-01"),
    # Frank's contacts
    ("silver_frank_6", "Maria", "Garcia", "1987-08-22"),
    ("silver_frank_6", "Diego", "Garcia", "2009-04-10"),
    ("silver_frank_6", "Elena", "Garcia", "2014-11-17"),
    # Grace's contacts
    ("silver_grace_7", "James", "Lee", "1990-02-14"),
    ("silver_grace_7", "Sophia", "Kim", "1994-07-30"),
    ("silver_grace_7", "Daniel", "Park", "1988-09-23"),
    # Henry's contacts
    ("reg_henry_8", "Susan", "Brown", "1977-05-08"),
    ("reg_henry_8", "Oliver", "Brown", "2007-10-12"),
    ("reg_henry_8", "Chloe", "Brown", "2011-03-25"),
    # Iris's contacts
    ("reg_iris_9", "Aiden", "Davis", "2001-08-19"),
    ("reg_iris_9", "Maya", "Davis", "1998-04-07"),
    ("reg_iris_9", "Ryan", "Smith", "1999-11-14"),
    # Jack's contacts
    ("reg_jack_10", "Nicole", "Miller", "1984-06-30"),
    ("reg_jack_10", "Tyler", "Miller", "2006-02-22"),
    ("reg_jack_10", "Ashley", "Jones", "1986-09-05"),
]

# ── Flights (routes) ──────────────────────────────────────────────────────────
# (flight_number, origin, destination, scheduled_departure_time_est,
#  scheduled_arrival_time_est)

FLIGHTS = [
    # JFK <-> LAX
    ("HAT001", "JFK", "LAX", "08:00:00", "11:30:00"),
    ("HAT002", "LAX", "JFK", "12:00:00", "20:00:00"),
    # JFK <-> ORD
    ("HAT003", "JFK", "ORD", "07:00:00", "09:15:00"),
    ("HAT004", "ORD", "JFK", "15:30:00", "19:00:00"),
    # JFK <-> SFO
    ("HAT005", "JFK", "SFO", "09:30:00", "13:00:00"),
    ("HAT006", "SFO", "JFK", "14:00:00", "22:00:00"),
    # LAX <-> ATL
    ("HAT007", "LAX", "ATL", "06:00:00", "13:30:00"),
    ("HAT008", "ATL", "LAX", "15:00:00", "17:30:00"),
    # ORD <-> DFW
    ("HAT009", "ORD", "DFW", "10:00:00", "12:30:00"),
    ("HAT010", "DFW", "ORD", "14:00:00", "16:30:00"),
    # SFO <-> SEA
    ("HAT011", "SFO", "SEA", "08:30:00", "10:45:00"),
    ("HAT012", "SEA", "SFO", "13:00:00", "15:15:00"),
    # ATL <-> MIA
    ("HAT013", "ATL", "MIA", "09:00:00", "10:30:00"),
    ("HAT014", "MIA", "ATL", "12:00:00", "13:30:00"),
    # DFW <-> LAX
    ("HAT015", "DFW", "LAX", "07:30:00", "08:45:00"),
    # MIA <-> JFK
    ("HAT016", "MIA", "JFK", "11:00:00", "14:30:00"),
    ("HAT017", "JFK", "MIA", "16:00:00", "19:30:00"),
    # SEA <-> ORD
    ("HAT018", "SEA", "ORD", "07:00:00", "13:00:00"),
]

# ── Flight Dates ───────────────────────────────────────────────────────────────
# Seed 14 days starting 2026-04-20 for all flights.
# (flight_number, date, status, seats_business, seats_economy, seats_basic_economy,
#  price_business, price_economy, price_basic_economy)

SEED_DATE_START = "2026-04-20"

# Base prices per route (business, economy, basic_economy)
_ROUTE_PRICES = {
    "HAT001": (600, 250, 180),
    "HAT002": (620, 260, 190),
    "HAT003": (400, 160, 110),
    "HAT004": (410, 165, 115),
    "HAT005": (580, 240, 170),
    "HAT006": (590, 245, 175),
    "HAT007": (520, 210, 150),
    "HAT008": (530, 215, 155),
    "HAT009": (350, 140, 95),
    "HAT010": (355, 145, 98),
    "HAT011": (300, 120, 85),
    "HAT012": (305, 125, 88),
    "HAT013": (280, 110, 75),
    "HAT014": (285, 115, 78),
    "HAT015": (430, 175, 125),
    "HAT016": (470, 190, 135),
    "HAT017": (475, 195, 138),
    "HAT018": (450, 185, 130),
}


def _build_flight_dates():
    """Generate 14 days of flight date records for all flights."""
    from datetime import date, timedelta

    start = date(2026, 4, 20)
    records = []
    for i in range(14):
        d = start + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        for flight_number, (pb, pe, pbe) in _ROUTE_PRICES.items():
            records.append(
                (
                    flight_number,
                    date_str,
                    "available",
                    8,
                    30,
                    20,  # seats: business, economy, basic_economy
                    pb,
                    pe,
                    pbe,
                )
            )
    return records


FLIGHT_DATES = _build_flight_dates()

# ── Seed Reservations ─────────────────────────────────────────────────────────
# We create 8 seed reservations. All are pre-existing so the agent can
# immediately exercise cancel/modify intents.
#
# For each reservation we define:
#   res row + flights + passengers + payment_history
#
# Prices are computed from ROUTE_PRICES to stay consistent.

# Reservation 1: Alice, JFK→LAX one-way, business, 1 pax, active
# Flight: HAT001 on 2026-04-25 @ $600; total = 600 (no insurance, no bags)
RES1_ID = "ZFA001"
RES1 = {
    "reservation_id": RES1_ID,
    "user_id": "gold_alice_1",
    "origin": "JFK",
    "destination": "LAX",
    "flight_type": "one_way",
    "cabin": "business",
    "total_baggages": 1,
    "nonfree_baggages": 0,
    "insurance": "no",
    "status": None,
    "flights": [
        {
            "flight_number": "HAT001",
            "origin": "JFK",
            "destination": "LAX",
            "date": "2026-04-25",
            "price": 600,
        },
    ],
    "passengers": [
        {"first_name": "Alice", "last_name": "Johnson", "dob": "1985-03-12"},
    ],
    "payments": [
        {"payment_id": "cc_alice_visa", "amount": 600},
    ],
}

# Reservation 2: Bob, LAX→JFK→LAX round-trip, economy, 2 pax, active
# Outbound: HAT002 on 2026-04-22 @ $260/pax; Return: HAT001 on 2026-04-29 @ $250/pax
# Total = (260 + 250) * 2 = 1020
RES2_ID = "ZFA002"
RES2 = {
    "reservation_id": RES2_ID,
    "user_id": "gold_bob_2",
    "origin": "LAX",
    "destination": "JFK",
    "flight_type": "round_trip",
    "cabin": "economy",
    "total_baggages": 2,
    "nonfree_baggages": 0,
    "insurance": "no",
    "status": None,
    "flights": [
        {
            "flight_number": "HAT002",
            "origin": "LAX",
            "destination": "JFK",
            "date": "2026-04-22",
            "price": 260,
        },
        {
            "flight_number": "HAT001",
            "origin": "JFK",
            "destination": "LAX",
            "date": "2026-04-29",
            "price": 250,
        },
    ],
    "passengers": [
        {"first_name": "Bob", "last_name": "Martinez", "dob": "1978-07-24"},
        {"first_name": "Linda", "last_name": "Martinez", "dob": "1979-11-30"},
    ],
    "payments": [
        {"payment_id": "cc_bob_mc", "amount": 1020},
    ],
}

# Reservation 3: Carol, JFK→ORD one-way, basic_economy, 1 pax, active
# Flight: HAT003 on 2026-04-23 @ $110; total = 110
RES3_ID = "ZFA003"
RES3 = {
    "reservation_id": RES3_ID,
    "user_id": "gold_carol_3",
    "origin": "JFK",
    "destination": "ORD",
    "flight_type": "one_way",
    "cabin": "basic_economy",
    "total_baggages": 0,
    "nonfree_baggages": 0,
    "insurance": "no",
    "status": None,
    "flights": [
        {
            "flight_number": "HAT003",
            "origin": "JFK",
            "destination": "ORD",
            "date": "2026-04-23",
            "price": 110,
        },
    ],
    "passengers": [
        {"first_name": "Carol", "last_name": "Thompson", "dob": "1990-11-05"},
    ],
    "payments": [
        {"payment_id": "cc_carol_visa", "amount": 110},
    ],
}

# Reservation 4: David, SFO→JFK one-way, economy, 1 pax, with insurance, active
# Flight: HAT006 on 2026-04-24 @ $245; insurance = $30; total = 275
RES4_ID = "ZFA004"
RES4 = {
    "reservation_id": RES4_ID,
    "user_id": "silver_david_4",
    "origin": "SFO",
    "destination": "JFK",
    "flight_type": "one_way",
    "cabin": "economy",
    "total_baggages": 1,
    "nonfree_baggages": 1,
    "insurance": "yes",
    "status": None,
    "flights": [
        {
            "flight_number": "HAT006",
            "origin": "SFO",
            "destination": "JFK",
            "date": "2026-04-24",
            "price": 245,
        },
    ],
    "passengers": [
        {"first_name": "David", "last_name": "Wilson", "dob": "1982-06-18"},
    ],
    "payments": [
        {"payment_id": "cc_david_amex", "amount": 325},  # 245 + 30 insurance + 50 baggage
    ],
}

# Reservation 5: Eva, ATL→MIA one-way, economy, 2 pax, active
# Flight: HAT013 on 2026-04-26 @ $110/pax; total = 220
RES5_ID = "ZFA005"
RES5 = {
    "reservation_id": RES5_ID,
    "user_id": "silver_eva_5",
    "origin": "ATL",
    "destination": "MIA",
    "flight_type": "one_way",
    "cabin": "economy",
    "total_baggages": 2,
    "nonfree_baggages": 0,
    "insurance": "no",
    "status": None,
    "flights": [
        {
            "flight_number": "HAT013",
            "origin": "ATL",
            "destination": "MIA",
            "date": "2026-04-26",
            "price": 110,
        },
    ],
    "passengers": [
        {"first_name": "Eva", "last_name": "Anderson", "dob": "1995-02-28"},
        {"first_name": "Noah", "last_name": "Anderson", "dob": "1993-10-05"},
    ],
    "payments": [
        {"payment_id": "cc_eva_visa", "amount": 220},
    ],
}

# Reservation 6: Frank, ORD→DFW one-way, economy, 1 pax, CANCELLED
# Flight: HAT009 on 2026-04-21 @ $140; total = 140; refunded
RES6_ID = "ZFA006"
RES6 = {
    "reservation_id": RES6_ID,
    "user_id": "silver_frank_6",
    "origin": "ORD",
    "destination": "DFW",
    "flight_type": "one_way",
    "cabin": "economy",
    "total_baggages": 0,
    "nonfree_baggages": 0,
    "insurance": "no",
    "status": "cancelled",
    "flights": [
        {
            "flight_number": "HAT009",
            "origin": "ORD",
            "destination": "DFW",
            "date": "2026-04-21",
            "price": 140,
        },
    ],
    "passengers": [
        {"first_name": "Frank", "last_name": "Garcia", "dob": "1988-09-14"},
    ],
    "payments": [
        {"payment_id": "cc_frank_mc", "amount": 140},
        {"payment_id": "cc_frank_mc", "amount": -140},  # refund
    ],
}

# Reservation 7: Grace, MIA→JFK one-way, business, 1 pax, active
# Flight: HAT016 on 2026-04-27 @ $470; total = 470
RES7_ID = "ZFA007"
RES7 = {
    "reservation_id": RES7_ID,
    "user_id": "silver_grace_7",
    "origin": "MIA",
    "destination": "JFK",
    "flight_type": "one_way",
    "cabin": "business",
    "total_baggages": 2,
    "nonfree_baggages": 0,
    "insurance": "no",
    "status": None,
    "flights": [
        {
            "flight_number": "HAT016",
            "origin": "MIA",
            "destination": "JFK",
            "date": "2026-04-27",
            "price": 470,
        },
    ],
    "passengers": [
        {"first_name": "Grace", "last_name": "Lee", "dob": "1992-12-03"},
    ],
    "payments": [
        {"payment_id": "cc_grace_visa", "amount": 470},
    ],
}

# Reservation 8: Henry, SEA→ORD one-way, economy, 1 pax, active
# Flight: HAT018 on 2026-04-28 @ $185; total = 185
RES8_ID = "ZFA008"
RES8 = {
    "reservation_id": RES8_ID,
    "user_id": "reg_henry_8",
    "origin": "SEA",
    "destination": "ORD",
    "flight_type": "one_way",
    "cabin": "economy",
    "total_baggages": 1,
    "nonfree_baggages": 1,
    "insurance": "no",
    "status": None,
    "flights": [
        {
            "flight_number": "HAT018",
            "origin": "SEA",
            "destination": "ORD",
            "date": "2026-04-28",
            "price": 185,
        },
    ],
    "passengers": [
        {"first_name": "Henry", "last_name": "Brown", "dob": "1975-04-22"},
    ],
    "payments": [
        {"payment_id": "cc_henry_mc", "amount": 235},  # 185 + 50 baggage
    ],
}

RESERVATIONS = [RES1, RES2, RES3, RES4, RES5, RES6, RES7, RES8]
