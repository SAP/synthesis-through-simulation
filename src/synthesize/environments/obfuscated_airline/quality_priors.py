"""
Generic environment — reference distributions for RealisticValueDistributionScore.

Reference distributions used by the RealisticValueDistributionScore metric.
Distributions are domain-independent; values derive from population-level priors
for the environment.

Every entry has:
  type: "categorical" or "numeric"
  distribution: for categorical, a dict of {value: expected_fraction}
  reference_values: for numeric, a representative sample drawn from the
                    distribution (used to build the empirical CDF)
"""

from __future__ import annotations

GENERIC_QUALITY_PRIORS: dict[str, dict[str, dict]] = {
    "object_cs": {
        # Tier class distribution (type_b 10%, type_a 75%, type_c 15%)
        "property_e": {
            "type": "categorical",
            "distribution": {
                "type_b": 0.10,
                "type_a": 0.75,
                "type_c": 0.15,
            },
        },
        # total property_f count distribution (Poisson λ≈0.9)
        # P(0)≈0.41, P(1)≈0.37, P(2)≈0.16, P(3+)≈0.06
        "property_f": {
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
                0,  # 0 — 41%
                1,
                1,
                1,
                1,
                1,
                1,
                1,
                1,
                1,  # 1 — 37%
                2,
                2,
                2,
                2,  # 2 — 16%
                3,  # 3 —  6% (combined 3+)
            ],
        },
        # property_g field distribution
        "property_g": {
            "type": "categorical",
            "distribution": {"yes": 0.28, "no": 0.72},
        },
        # object_b_type field distribution
        "object_b_type": {
            "type": "categorical",
            "distribution": {"option_a": 0.45, "option_b": 0.55},
        },
    },
}

# object_c_object_bs = reservation_flights; object_c_object_ds = reservation_passengers
GENERIC_RELATIONAL_PRIORS: dict = {
    ("object_cs", "object_c_object_bs", "object_c_id"): {
        "type": "child_count",
        "distribution": {1: 0.45, 2: 0.50, 3: 0.05},
        "max_bucket": 3,
    },
    ("object_cs", "object_c_object_ds", "object_c_id"): {
        "type": "child_count",
        "distribution": {1: 0.60, 2: 0.25, 3: 0.15},
        "max_bucket": 3,
    },
}

# property_e = cabin, property_g = insurance, object_b_type = flight_type
GENERIC_PAIRWISE_PRIORS: dict[str, dict[tuple, dict]] = {
    "object_cs": {
        ("property_e", "property_g"): {
            "type": "categorical_joint",
            "distribution": {
                ("type_b", "yes"):  0.045,
                ("type_b", "no"):   0.055,
                ("type_a", "yes"):  0.210,
                ("type_a", "no"):   0.540,
                ("type_c", "yes"):  0.020,
                ("type_c", "no"):   0.130,
            },
        },
        ("property_e", "object_b_type"): {
            "type": "categorical_joint",
            "distribution": {
                ("type_b", "option_a"):  0.065,
                ("type_b", "option_b"):  0.035,
                ("type_a", "option_a"):  0.330,
                ("type_a", "option_b"):  0.420,
                ("type_c", "option_a"):  0.057,
                ("type_c", "option_b"):  0.093,
            },
        },
    },
}
