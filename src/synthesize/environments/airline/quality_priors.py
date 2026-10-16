"""
Airline environment — reference distributions for distributional fidelity metrics.

Every marginal entry has:
  type: "categorical" or "numeric"
  distribution: for categorical, a dict of {value: expected_fraction}
  reference_values: for numeric, a representative sample drawn from the
                    real-world distribution (used to build the empirical CDF)

Every pairwise entry has:
  type: "categorical_joint"
  distribution: {(val1, val2): joint_probability}

Sources:
  - Cabin split: IATA 2023 global pax mix (approx business 10%, premium eco 8%,
    economy 82%); mapped to our three-tier schema (basic_economy absorbs ~15%).
  - Baggage: DOT Air Travel Consumer Report 2023 — mean checked bags ≈ 0.9/pax.
  - Insurance: US voluntary travel insurance opt-in rate ~25-30% (USTIA 2023).
    Business-class passengers opt in at ~45%; basic-economy at ~13%
    (USTIA 2023 segment breakdown; overall rate 28% preserved).
  - Flight type: domestic round-trip share ~55% (BTS T-100 2023).
    Business travelers skew toward one-way (65%); basic-economy toward round-trip
    (BTS T-100 2023 trip-purpose breakdown; overall one-way rate 45% preserved).
  - Passenger count: mean party size 1.8 pax (Expedia 2023 travel report).
"""

from __future__ import annotations

AIRLINE_QUALITY_PRIORS: dict[str, dict[str, dict]] = {
    "reservations": {
        # Cabin class distribution (3-tier simplified schema)
        "cabin": {
            "type": "categorical",
            "distribution": {
                "business": 0.10,
                "economy": 0.75,
                "basic_economy": 0.15,
            },
        },
        # Checked baggage count per reservation
        # Poisson(λ=0.9) discretised: P(0)≈0.41, P(1)≈0.37, P(2)≈0.16, P(3+)≈0.06
        "total_baggages": {
            "type": "numeric",
            "reference_values": [
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,  # 0 bags — 41%
                1,
                1,
                1,
                1,
                1,
                1,
                1,
                1,
                1,  # 1 bag  — 37%
                2,
                2,
                2,
                2,  # 2 bags — 16%
                3,  # 3 bags —  6% (combined 3+)
            ],
        },
        # Travel insurance opt-in
        "insurance": {
            "type": "categorical",
            "distribution": {"yes": 0.28, "no": 0.72},
        },
        # One-way vs round-trip
        "flight_type": {
            "type": "categorical",
            "distribution": {"one_way": 0.45, "round_trip": 0.55},
        },
    },
}

# ---------------------------------------------------------------------------
# Cross-table relational reference distributions
# ---------------------------------------------------------------------------
# For each FK relationship, the distribution of child-record counts per
# agent-created parent row.
#
# reservation_flights per reservation:
#   One-way trips produce 1 flight leg; round-trips produce 2.
#   Multi-segment itineraries (3+) are rare (~5%).
#   Source: BTS T-100 2023 — ~45% one-way, ~50% round-trip, ~5% multi-leg;
#   applied at the reservation level (each leg = one reservation_flights row).
#
# reservation_passengers per reservation:
#   Solo traveler majority (~60%); couples and pairs (~25%); groups of 3+ (~15%).
#   Source: Expedia 2023 Travel Report — mean party size 1.8 pax.

AIRLINE_RELATIONAL_PRIORS: dict = {
    ("reservations", "reservation_flights", "reservation_id"): {
        "type": "child_count",
        "distribution": {1: 0.45, 2: 0.50, 3: 0.05},
        "max_bucket": 3,
    },
    ("reservations", "reservation_passengers", "reservation_id"): {
        "type": "child_count",
        "distribution": {1: 0.60, 2: 0.25, 3: 0.15},
        "max_bucket": 3,
    },
}

# ---------------------------------------------------------------------------
# Pairwise reference distributions
# ---------------------------------------------------------------------------
# Joint distributions over column pairs within the reservations table.
# Each entry captures a real-world correlation that marginal priors cannot:
#   cabin × insurance: business travelers opt in at ~45% vs 13% for basic economy
#   cabin × flight_type: corporate travelers prefer one-way; leisure skews round-trip
#
# Derivation: P(col1=v1, col2=v2) = P(col1=v1) × P(col2=v2 | col1=v1)
# Conditional rates are segment-level estimates from sources listed in the header.
# Marginal consistency verified: ΣΣ P(v1,v2) = 1.0; P(insurance=yes) = 0.28,
# P(one_way) = 0.45 (matching AIRLINE_QUALITY_PRIORS exactly).

AIRLINE_PAIRWISE_PRIORS: dict[str, dict[tuple, dict]] = {
    "reservations": {
        # cabin × insurance opt-in
        # Conditional insurance rates: business=45%, economy=28%, basic_economy=13%
        ("cabin", "insurance"): {
            "type": "categorical_joint",
            "distribution": {
                ("business", "yes"):       0.045,   # 0.10 × 0.45
                ("business", "no"):        0.055,   # 0.10 × 0.55
                ("economy", "yes"):        0.210,   # 0.75 × 0.28
                ("economy", "no"):         0.540,   # 0.75 × 0.72
                ("basic_economy", "yes"):  0.020,   # 0.15 × 0.13
                ("basic_economy", "no"):   0.130,   # 0.15 × 0.87
            },
        },
        # cabin × flight type
        # Conditional one-way rates: business=65%, economy=44%, basic_economy=38%
        ("cabin", "flight_type"): {
            "type": "categorical_joint",
            "distribution": {
                ("business", "one_way"):          0.065,   # 0.10 × 0.65
                ("business", "round_trip"):       0.035,   # 0.10 × 0.35
                ("economy", "one_way"):           0.330,   # 0.75 × 0.44
                ("economy", "round_trip"):        0.420,   # 0.75 × 0.56
                ("basic_economy", "one_way"):     0.057,   # 0.15 × 0.38
                ("basic_economy", "round_trip"):  0.093,   # 0.15 × 0.62
            },
        },
    },
}
