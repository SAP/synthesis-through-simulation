"""
HR environment — reference distributions for distributional fidelity metrics.

Sources:
  - Employment status: typical corporate workforce — active employees dominate,
    small fraction terminated (annual attrition ~10-15%, SHRM 2023).
  - Job level distribution: IC-heavy pyramid typical for tech companies
    (Radford global tech survey 2023).
  - Department distribution: technology company headcount allocation
    (engineering-heavy, standard corporate ratios).
  - Application status: cross-sectional snapshot of a live ATS; distribution
    reflects a mix of open, in-progress, and resolved candidates
    (LinkedIn Talent Insights 2023; Greenhouse 2023 benchmark report).
  - Offer status: SHRM 2023 offer-acceptance-rate benchmark (~74% acceptance
    among resolved offers); remaining share split across Draft/Extended/Declined/Expired.
"""

from __future__ import annotations

HR_QUALITY_PRIORS: dict[str, dict[str, dict]] = {
    "emp_job": {
        # Employment status — most employees are active
        "employment_status": {
            "type": "categorical",
            "distribution": {
                "Active": 0.88,
                "Terminated": 0.12,
            },
        },
    },
    "tm_time_off_request": {
        # Time-off type distribution
        "time_off_type_code": {
            "type": "categorical",
            "distribution": {
                "VAC": 0.55,
                "SICK": 0.25,
                "PTO": 0.18,
                "BEREAVEMENT": 0.02,
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Process-outcome reference distributions
# ---------------------------------------------------------------------------
# These columns reflect the results of multi-step hiring workflows.  Their
# distributions are shaped by the synthesiser's operation-mix targeting
# (how many APPLY vs. REJECT vs. HIRE intents are called), making them the
# canonical measure of process fidelity in the HR environment.
#
# rcm_application.application_status — cross-sectional ATS snapshot
#   A live ATS always contains applications at every stage simultaneously.
#   The reference proportions reflect a tech-company ATS in steady-state
#   (LinkedIn Talent Insights 2023; Greenhouse 2023 benchmark report).
#
# rcm_offer.offer_status — offer pipeline snapshot
#   Among all offers ever extended: ~74% accepted (SHRM 2023 acceptance benchmark),
#   remainder split across Declined and Expired; Draft and Extended represent
#   offers currently in-flight.

# ---------------------------------------------------------------------------
# Pairwise reference distributions
# ---------------------------------------------------------------------------
# tm_time_off_request.(time_off_type_code, request_status): approval rates
# differ by leave type. Vacation and PTO requests are sometimes pending or
# rejected; sick leave and bereavement are almost always approved on submission.
# Marginals preserved: P(VAC)=0.55, P(SICK)=0.25, P(PTO)=0.18, P(BER)=0.02.
# Conditional approval rates: VAC 82%, SICK 92%, PTO 85%, BEREAVEMENT 99%.
# Source: SHRM 2023 leave management benchmark — approval rates by leave type.

HR_PAIRWISE_PRIORS: dict = {
    "tm_time_off_request": {
        ("time_off_type_code", "request_status"): {
            "type": "categorical_joint",
            "distribution": {
                ("VAC",         "Approved"):  0.451,   # 0.55 × 0.82
                ("VAC",         "Pending"):   0.060,   # 0.55 × 0.11
                ("VAC",         "Rejected"):  0.028,   # 0.55 × 0.05
                ("VAC",         "Cancelled"): 0.011,   # 0.55 × 0.02
                ("SICK",        "Approved"):  0.230,   # 0.25 × 0.92
                ("SICK",        "Pending"):   0.013,   # 0.25 × 0.05
                ("SICK",        "Rejected"):  0.005,   # 0.25 × 0.02
                ("SICK",        "Cancelled"): 0.002,   # 0.25 × 0.01
                ("PTO",         "Approved"):  0.153,   # 0.18 × 0.85
                ("PTO",         "Pending"):   0.018,   # 0.18 × 0.10
                ("PTO",         "Rejected"):  0.007,   # 0.18 × 0.04
                ("PTO",         "Cancelled"): 0.002,   # 0.18 × 0.01
                ("BEREAVEMENT", "Approved"):  0.020,   # 0.02 × 0.99
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Cross-table relational reference distributions
# ---------------------------------------------------------------------------
# per_person → tm_time_off_request: time-off requests per agent-created employee.
# New employees may have 0 requests; established employees typically submit
# 1–4 requests per year (vacation, sick, PTO).
# Source: SHRM 2023 — US workers average 7.6 PTO days/year across ~3 requests;
# applied at GP-run granularity (shorter window, skewed toward fewer requests).

HR_RELATIONAL_PRIORS: dict = {
    ("per_person", "tm_time_off_request", "person_id"): {
        "type": "child_count",
        "distribution": {0: 0.30, 1: 0.35, 2: 0.20, 3: 0.10, 4: 0.05},
        "max_bucket": 4,
    },
}

HR_PROCESS_PRIORS: dict[str, dict[str, dict]] = {
    "rcm_application": {
        "application_status": {
            "type": "categorical",
            "distribution": {
                "New":          0.28,
                "Under Review": 0.22,
                "Interview":    0.20,
                "Offer":        0.08,
                "Hired":        0.12,
                "Rejected":     0.10,
            },
        },
    },
    "rcm_offer": {
        "offer_status": {
            "type": "categorical",
            "distribution": {
                "Draft":    0.08,
                "Extended": 0.22,
                "Accepted": 0.52,
                "Declined": 0.13,
                "Expired":  0.05,
            },
        },
    },
}
