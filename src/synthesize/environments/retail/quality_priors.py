"""
Retail environment — reference distributions for distributional fidelity metrics.

Sources:
  - Order status mix: typical e-commerce fulfillment pipeline proportions
    (NRF 2023: ~8% cancellation rate, ~18% return/exchange rate of delivered orders).
  - Payment source: Statista 2023 US online payment share (credit card 55%,
    PayPal 30%, gift card/store credit 15%).
  - Transaction type: refund rate ~20% of payment volume (industry average).
"""

from __future__ import annotations

RETAIL_QUALITY_PRIORS: dict[str, dict[str, dict]] = {
    "orders": {
        # Order lifecycle status distribution
        "status": {
            "type": "categorical",
            "distribution": {
                "pending": 0.25,
                "processed": 0.45,
                "delivered": 0.20,
                "cancelled": 0.08,
                "exchange requested": 0.01,
                "return requested": 0.01,
            },
        },
    },
    "payment_methods": {
        # Payment method source distribution
        "source": {
            "type": "categorical",
            "distribution": {
                "credit_card": 0.55,
                "paypal": 0.30,
                "gift_card": 0.15,
            },
        },
    },
    "payment_history": {
        # Transaction type: most are payments, ~20% refunds
        "transaction_type": {
            "type": "categorical",
            "distribution": {
                "payment": 0.80,
                "refund": 0.20,
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Process-outcome reference distributions
# ---------------------------------------------------------------------------
# orders.status captures the outcome of the full order lifecycle process
# (place → process → fulfil → deliver, with cancel/exchange/return branches).
# Its distribution is directly shaped by how many PLACE_ORDER, CANCEL_ORDER,
# PROCESS_RETURN etc. intents the synthesiser executes — making it the canonical
# process fidelity signal for the retail environment.
# Same reference proportions as the marginal priors; registered separately so
# process fidelity is reported as a distinct metric from entity-property fidelity.
#
# Source: NRF 2023 e-commerce fulfillment benchmark (same as marginal priors).

# ---------------------------------------------------------------------------
# Pairwise reference distributions
# ---------------------------------------------------------------------------
# orders.(status, cancel_reason): WHERE NOT NULL isolates cancelled orders,
# measuring the split between cancellation reasons the GP generates.
# Reference: NRF 2023 consumer survey — ~60% "no longer needed", ~40% "mistake".

RETAIL_PAIRWISE_PRIORS: dict = {
    "orders": {
        ("status", "cancel_reason"): {
            "type": "categorical_joint",
            "distribution": {
                ("cancelled", "no longer needed"): 0.60,
                ("cancelled", "ordered by mistake"): 0.40,
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Cross-table relational reference distributions
# ---------------------------------------------------------------------------
# order_items per order: typical e-commerce basket size.
#   ~40% of orders contain a single item, ~35% two items, ~25% three or more.
#   Source: Salesforce Commerce Cloud 2023 Shopping Index — mean items/order = 1.9.
#
# payment_history per order: almost all orders have exactly one payment event;
#   refunds or split payments occasionally add a second record.
#   Source: internal retail benchmark — ~90% single transaction, ~10% two.

RETAIL_RELATIONAL_PRIORS: dict = {
    ("orders", "order_items", "order_id"): {
        "type": "child_count",
        "distribution": {1: 0.40, 2: 0.35, 3: 0.25},
        "max_bucket": 3,
    },
    ("orders", "payment_history", "order_id"): {
        "type": "child_count",
        "distribution": {1: 0.90, 2: 0.10},
        "max_bucket": 2,
    },
}

# ---------------------------------------------------------------------------
# Process-outcome reference distributions
# ---------------------------------------------------------------------------
RETAIL_PROCESS_PRIORS: dict[str, dict[str, dict]] = {
    "orders": {
        "status": {
            "type": "categorical",
            "distribution": {
                "pending":           0.25,
                "processed":         0.45,
                "delivered":         0.20,
                "cancelled":         0.08,
                "exchange requested": 0.01,
                "return requested":   0.01,
            },
        },
    },
}
