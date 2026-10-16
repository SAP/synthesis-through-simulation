"""
Shared utility functions for benchmarking metrics.

No external dependencies — stdlib math + collections.Counter only.
All functions are pure (side-effect-free).
"""

from __future__ import annotations

import math
from collections import Counter

from synthesize.models import Step


def shannon_entropy(counts: Counter | dict) -> float:
    """Compute Shannon entropy H = -∑ p(x) · log(p(x)) in nats.

    Returns 0.0 for empty or single-element distributions.
    """
    total = sum(counts.values())
    if total == 0:
        return 0.0
    h = 0.0
    for v in counts.values():
        if v > 0:
            p = v / total
            h -= p * math.log(p)
    return h


def normalized_entropy(counts: Counter | dict) -> float:
    """Compute normalized entropy H_norm = H(X) / log(|X|), range [0, 1].

    Returns 0.0 for empty or single-element distributions (no diversity).
    Returns 1.0 for perfectly uniform distributions (maximum diversity).
    """
    n = len([v for v in counts.values() if v > 0])
    if n <= 1:
        return 0.0
    h = shannon_entropy(counts)
    return h / math.log(n)


def tool_sequence(steps: list[Step]) -> tuple[str, ...]:
    """Return the ordered sequence of tool names as a hashable tuple."""
    return tuple(s.tool for s in steps)


def tool_bigrams(steps: list[Step]) -> list[tuple[str, str]]:
    """Return consecutive (tool_i, tool_{i+1}) pairs from a step list."""
    tools = [s.tool for s in steps]
    return [(tools[i], tools[i + 1]) for i in range(len(tools) - 1)]


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity |A ∩ B| / |A ∪ B|.

    Returns 1.0 when both sets are empty (identical empty sets).
    """
    if not set_a and not set_b:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def kl_divergence(p: dict, q: dict, epsilon: float = 1e-10) -> float:
    """Compute KL(P||Q) = ∑ P(x) · log(P(x) / Q(x)), epsilon-smoothed.

    Both dicts are treated as unnormalised count distributions.
    All keys from P must appear in Q (epsilon-smoothed if missing).
    """
    p_total = sum(p.values())
    q_total = sum(q.values())
    if p_total == 0:
        return 0.0

    result = 0.0
    for k, pv in p.items():
        if pv == 0:
            continue
        p_prob = pv / p_total
        q_prob = q.get(k, 0) / q_total if q_total > 0 else 0.0
        q_prob = max(q_prob, epsilon)
        result += p_prob * math.log(p_prob / q_prob)
    return result


def js_divergence(p: dict, q: dict) -> float:
    """Compute Jensen-Shannon divergence JSD(P, Q) = 0.5·KL(P||M) + 0.5·KL(Q||M).

    M = 0.5·(P + Q). Bounded [0, ln(2)]. Returns 0.0 for identical distributions.
    """
    # Build merged key set
    all_keys = set(p) | set(q)
    p_total = sum(p.values()) or 1
    q_total = sum(q.values()) or 1

    # Normalise
    p_norm = {k: p.get(k, 0) / p_total for k in all_keys}
    q_norm = {k: q.get(k, 0) / q_total for k in all_keys}

    # Mixture M
    m = {k: 0.5 * (p_norm[k] + q_norm[k]) for k in all_keys}

    kl_pm = kl_divergence(p_norm, m)
    kl_qm = kl_divergence(q_norm, m)
    return 0.5 * kl_pm + 0.5 * kl_qm
