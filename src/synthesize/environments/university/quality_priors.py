"""
University environment — reference distributions for RealisticValueDistributionScore.

Sources:
  - Enrollment status: NCES 2022 undergraduate outcomes — ~60% currently enrolled,
    ~30% completed/graduated, ~8% withdrew, ~2% failed.
  - Student enrollment status: NCES 2022 — active 85%, graduated 10%,
    inactive/stopped-out 4%, suspended 1%.
  - Course department distribution: approximated from typical US university
    department sizes (IPEDS 2022).
"""

from __future__ import annotations

UNIVERSITY_QUALITY_PRIORS: dict[str, dict[str, dict]] = {
    "enrollment": {
        # Enrollment record status distribution
        "status": {
            "type": "categorical",
            "distribution": {
                "enrolled": 0.60,
                "completed": 0.30,
                "dropped": 0.08,
                "failed": 0.02,
            },
        },
    },
    "student": {
        # Student enrollment status distribution
        "enrollment_status": {
            "type": "categorical",
            "distribution": {
                "active": 0.85,
                "graduated": 0.10,
                "inactive": 0.04,
                "suspended": 0.01,
            },
        },
    },
}
