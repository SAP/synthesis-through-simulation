"""
IT Management environment — reference distributions for RealisticValueDistributionScore.

Sources:
  - Ticket priority: industry ITSM benchmarks (HDI 2023) — most tickets are
    medium priority; high-priority tickets are rare emergencies.
  - Ticket status: the resolve_ticket API is the terminal state — there is no
    close_ticket API, so 'closed' is structurally unreachable. Reference reflects
    a cross-sectional snapshot: open awaiting assignment, assigned in-progress,
    resolved (terminal). HDI 2023 first-contact-resolution rate ~50%.
"""

from __future__ import annotations

IT_MANAGEMENT_QUALITY_PRIORS: dict[str, dict[str, dict]] = {
    "it_ticket": {
        # Priority distribution across all tickets
        "priority": {
            "type": "categorical",
            "distribution": {
                "low": 0.30,
                "medium": 0.50,
                "high": 0.20,
            },
        },
        # Status distribution — resolved is terminal (no close_ticket API exists)
        "status": {
            "type": "categorical",
            "distribution": {
                "open": 0.20,
                "assigned": 0.30,
                "resolved": 0.50,
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Pairwise reference distributions
# ---------------------------------------------------------------------------
# it_ticket.(priority, status): high-priority tickets get assigned and resolved
# faster; low-priority tickets linger open longer.
# Marginals: P(open)=0.195≈0.20, P(assigned)=0.31≈0.30, P(resolved)=0.495≈0.50.
# Conditional rates: P(resolved|high)=0.55, P(resolved|medium)=0.50,
# P(resolved|low)=0.45 — urgency drives faster resolution.
# Source: HDI 2023 service desk benchmark — priority × resolution-rate breakdown.

IT_MANAGEMENT_PAIRWISE_PRIORS: dict = {
    "it_ticket": {
        ("priority", "status"): {
            "type": "categorical_joint",
            "distribution": {
                ("high",   "open"):     0.020,   # 0.20 × 0.10
                ("high",   "assigned"): 0.070,   # 0.20 × 0.35
                ("high",   "resolved"): 0.110,   # 0.20 × 0.55
                ("medium", "open"):     0.100,   # 0.50 × 0.20
                ("medium", "assigned"): 0.150,   # 0.50 × 0.30
                ("medium", "resolved"): 0.250,   # 0.50 × 0.50
                ("low",    "open"):     0.075,   # 0.30 × 0.25
                ("low",    "assigned"): 0.090,   # 0.30 × 0.30
                ("low",    "resolved"): 0.135,   # 0.30 × 0.45
            },
        },
    },
}
