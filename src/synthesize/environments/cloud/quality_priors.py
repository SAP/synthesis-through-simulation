"""
Cloud Computing Platform — reference distributions for DF computation.

Sources: AWS / cloud industry benchmarks (typical production workload mix).
"""

from __future__ import annotations

CLOUD_QUALITY_PRIORS: dict[str, dict[str, dict]] = {
    "instances": {
        "state": {
            "type": "categorical",
            "distribution": {
                "running": 0.55,
                "stopped": 0.35,
                "terminated": 0.10,
            },
        },
        "instance_type": {
            "type": "categorical",
            "distribution": {
                "t2.micro":  0.35,
                "t2.small":  0.25,
                "t2.medium": 0.20,
                "t2.large":  0.15,
                "t2.xlarge": 0.05,
            },
        },
        "region": {
            "type": "categorical",
            "distribution": {
                "us-east-1":    0.50,
                "eu-central-1": 0.30,
                "ap-south-1":   0.20,
            },
        },
    },
    "images": {
        "visibility": {
            "type": "categorical",
            "distribution": {
                "public":  0.60,
                "private": 0.40,
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Pairwise reference distributions
# ---------------------------------------------------------------------------
# instances.(state, region): state and region are independent (workload
# distribution and operational state are controlled independently).
# Joint = product of marginals; tests whether the GP preserves both
# distributions simultaneously.
# Source: AWS instance analytics 2023 — state and region marginals independent
# at fleet level.

CLOUD_PAIRWISE_PRIORS: dict = {
    "instances": {
        ("state", "region"): {
            "type": "categorical_joint",
            "distribution": {
                ("running",    "us-east-1"):    0.275,   # 0.55 × 0.50
                ("running",    "eu-central-1"): 0.165,   # 0.55 × 0.30
                ("running",    "ap-south-1"):   0.110,   # 0.55 × 0.20
                ("stopped",    "us-east-1"):    0.175,   # 0.35 × 0.50
                ("stopped",    "eu-central-1"): 0.105,   # 0.35 × 0.30
                ("stopped",    "ap-south-1"):   0.070,   # 0.35 × 0.20
                ("terminated", "us-east-1"):    0.050,   # 0.10 × 0.50
                ("terminated", "eu-central-1"): 0.030,   # 0.10 × 0.30
                ("terminated", "ap-south-1"):   0.020,   # 0.10 × 0.20
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Cross-table relational reference distributions
# ---------------------------------------------------------------------------
# vpcs → subnets: subnets per agent-created VPC.
# AWS best practice recommends one subnet per Availability Zone; most
# production VPCs use 2–3 AZs for redundancy.
# Source: AWS Well-Architected Framework 2023 — multi-AZ VPC guidance.

CLOUD_RELATIONAL_PRIORS: dict = {
    ("vpcs", "subnets", "vpc_id"): {
        "type": "child_count",
        "distribution": {1: 0.15, 2: 0.40, 3: 0.30, 4: 0.15},
        "max_bucket": 4,
    },
}
