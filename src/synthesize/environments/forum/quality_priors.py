"""
Forum environment — reference distributions for RealisticValueDistributionScore.

Sources:
  - User role distribution: typical moderated online community — heavy member
    majority, small moderator tier, rare admins (Reddit/Discourse community
    moderation ratios, 2023).
  - Thread status: most threads remain open; ~10% closed by moderators;
    ~2% deleted (spam/policy violations).
"""

from __future__ import annotations

FORUM_QUALITY_PRIORS: dict[str, dict[str, dict]] = {
    "forum_user": {
        # User role distribution
        "role": {
            "type": "categorical",
            "distribution": {
                "member": 0.80,
                "moderator": 0.15,
                "admin": 0.05,
            },
        },
    },
    "thread": {
        # Thread status distribution
        "status": {
            "type": "categorical",
            "distribution": {
                "open": 0.88,
                "closed": 0.10,
                "deleted": 0.02,
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Cross-table relational reference distributions
# ---------------------------------------------------------------------------
# thread → post: replies per thread.
# Most forum threads have an opening post plus a handful of replies; long
# threads (10+ posts) are less common.
# Source: Discourse community benchmarks 2023 — median thread length ≈ 3 posts,
# 80th percentile ≈ 7 posts.

FORUM_RELATIONAL_PRIORS: dict = {
    ("thread", "post", "thread_id"): {
        "type": "child_count",
        "distribution": {1: 0.25, 2: 0.25, 3: 0.20, 4: 0.15, 5: 0.08, 7: 0.05, 10: 0.02},
        "max_bucket": 10,
    },
}
