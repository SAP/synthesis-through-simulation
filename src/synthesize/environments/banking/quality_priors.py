"""
Banking environment — reference distributions for RealisticValueDistributionScore.

Sources:
  - Account type mix: FDIC 2022 survey — checking 50%, savings 38%, loan 12%.
  - Transaction type: retail banking activity mix (deposits ~25%, withdrawals ~40%,
    transfers ~34%, fees ~1%) based on FRB payments study 2022.
"""

from __future__ import annotations

BANKING_QUALITY_PRIORS: dict[str, dict[str, dict]] = {
    "account": {
        # Account type distribution
        "account_type": {
            "type": "categorical",
            "distribution": {
                "checking": 0.50,
                "savings": 0.40,
                "loan": 0.10,
            },
        },
    },
    "txn": {
        # Transaction type distribution across all accounts
        "txn_type": {
            "type": "categorical",
            "distribution": {
                "deposit": 0.25,
                "withdrawal": 0.40,
                "transfer_in": 0.17,
                "transfer_out": 0.17,
                "fee": 0.01,
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Pairwise reference distributions
# ---------------------------------------------------------------------------
# account.(account_type, overdraft_allowed): overdraft protection is common
# for checking accounts (~40%), rare for savings (~5%), never for loans.
# Source: FDIC 2023 overdraft survey — segment-level opt-in rates.
# Marginal consistency: P(overdraft=1) = 0.50×0.40 + 0.40×0.05 = 0.22.

BANKING_PAIRWISE_PRIORS: dict = {
    "account": {
        ("account_type", "overdraft_allowed"): {
            "type": "categorical_joint",
            "distribution": {
                ("checking", 1): 0.20,   # 0.50 × 0.40
                ("checking", 0): 0.30,   # 0.50 × 0.60
                ("savings",  1): 0.02,   # 0.40 × 0.05
                ("savings",  0): 0.38,   # 0.40 × 0.95
                ("loan",     0): 0.10,   # 0.10 × 1.00
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Cross-table relational reference distributions
# ---------------------------------------------------------------------------
# account → txn: transaction volume per agent-created account.
# Retail banking accounts accumulate 5–30 transactions over the GP's run
# window; a small fraction of heavily-used accounts attract 30+ operations.
# Source: FRB payments study 2022 — mean ~18 debit transactions/account/month.

BANKING_RELATIONAL_PRIORS: dict = {
    ("account", "txn", "account_id"): {
        "type": "child_count",
        "distribution": {1: 0.10, 2: 0.10, 3: 0.10, 5: 0.15, 10: 0.20, 20: 0.20, 30: 0.15},
        "max_bucket": 30,
    },
}
