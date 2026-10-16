"""
Ecommerce environment — reference distributions for RealisticValueDistributionScore.

Sources:
  - Order status: typical B2C e-commerce lifecycle — most orders reach delivered
    state; ~10% cancellation rate (Statista 2023 e-commerce returns/cancellations).
  - Product category: based on global e-commerce category share (Statista 2023).
"""

from __future__ import annotations

ECOMMERCE_QUALITY_PRIORS: dict[str, dict[str, dict]] = {
    "shop_order": {
        # Order status distribution — restricted to states reachable via current tool
        # registry (create_order→pending, confirm_order→confirmed, cancel_order→cancelled).
        # ship_order and deliver_order are not registered, so shipped/delivered are
        # excluded and the remaining weights are renormalized (0.15+0.10+0.10 = 0.35).
        "status": {
            "type": "categorical",
            "distribution": {
                "pending": 0.429,
                "confirmed": 0.286,
                "cancelled": 0.285,
            },
        },
    },
    "product": {
        # Product category distribution (approximation from seed data proportions)
        "category": {
            "type": "categorical",
            "distribution": {
                "Electronics": 0.20,
                "Footwear": 0.12,
                "Appliances": 0.10,
                "Sports": 0.10,
                "Bags": 0.08,
                "Kitchen": 0.08,
                "Office": 0.08,
                "Books": 0.07,
                "Accessories": 0.06,
                "Health": 0.04,
                "Stationery": 0.04,
                "Travel": 0.03,
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Cross-table relational reference distributions
# ---------------------------------------------------------------------------
# shop_order → order_item: items per order (basket size).
# Typical B2C e-commerce: ~40% single-item orders, ~30% two items, remainder
# three or more. Source: Salesforce Commerce Cloud 2023 Shopping Index —
# mean items/order = 1.9.

ECOMMERCE_RELATIONAL_PRIORS: dict = {
    ("shop_order", "order_item", "order_id"): {
        "type": "child_count",
        "distribution": {1: 0.40, 2: 0.30, 3: 0.20, 4: 0.10},
        "max_bucket": 4,
    },
}
