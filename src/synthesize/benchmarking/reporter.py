"""
Benchmark report printer.

print_report() pretty-prints a list of MetricResults to stdout.
Supports metric grouping headers when using EXTENDED_METRICS or ALL_METRICS.
"""

from __future__ import annotations

from .base import MetricResult

# Prefix-to-group mapping — checked in order; first match wins.
_GROUP_PREFIXES: list[tuple[tuple[str, ...], str]] = [
    (("tool_usage", "tool_sequence", "unique_tool"), "Trajectory Diversity"),
    (("schema_field", "cross_table"), "Data Coverage"),
    (
        (
            "corrupt_success",
            "pass_k",
            "error_recovery",
            "intent_coverage",
            "api_endpoint",
            "error_type",
        ),
        "Simulation Effectiveness",
    ),
    (
        ("blind_vs", "vendi", "rule_discovery", "enum_balance", "argument_value"),
        "Synthesis Quality",
    ),
    (
        (
            "temporal_consistency",
            "workflow_completeness",
            "realistic_value",
            "llm_data_quality",
            "record_deduplication",
        ),
        "Data Quality",
    ),
]

_CORE_NAMES = {
    "success_rate",
    "avg_steps",
    "avg_errors",
    "recovery_rate",
    "postcondition_rates",
    "validation_pass_rate",
    "per_check_pass_rate",
}


def _get_group(metric_name: str) -> str | None:
    """Return group label for a metric name, or None for core metrics."""
    if metric_name in _CORE_NAMES:
        return None
    for prefixes, label in _GROUP_PREFIXES:
        for prefix in prefixes:
            if metric_name.startswith(prefix):
                return label
    return "Other"


def _format_detail_value(v: object, depth: int = 0) -> str:
    """Render a detail value as a short inline string."""
    if isinstance(v, dict):
        if depth >= 1:
            # Truncate nested dicts to a summary
            items = list(v.items())[:3]
            inner = ", ".join(f"{k}:{_format_detail_value(val, depth + 1)}" for k, val in items)
            suffix = f" +{len(v) - 3} more" if len(v) > 3 else ""
            return "{" + inner + suffix + "}"
        return ""  # handled by caller for depth=0
    if isinstance(v, list):
        items = v[:10]
        suffix = f" +{len(v) - 10} more" if len(v) > 10 else ""
        return str(items) + suffix
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def print_report(
    results: list[MetricResult],
    label: str = "",
    record_count: int = 0,
    detail_depth: int = 1,
) -> None:
    """Pretty-print benchmark results to stdout.

    Args:
        results:      list of MetricResult from compute_metrics()
        label:        run label shown in the header
        record_count: number of trajectories analysed
        detail_depth: how deep to render nested detail dicts (default 1 = one level)
    """
    width = 60
    border = "═" * width

    print(f"\n{border}")
    if label:
        print(f"  Benchmark: {label}")
    print(f"  Runs analysed: {record_count}")
    print(border)

    current_group: str | None = "__init__"  # sentinel: not started

    for r in results:
        group = _get_group(r.name)

        # Print group header when group changes (None = core, omit header)
        if group != current_group:
            current_group = group
            if group is not None:
                print(f"\n  ── {group} {'─' * max(0, width - 6 - len(group))}")

        print(f"  {r.name:<32} {r.display}")

        if r.details and detail_depth > 0:
            for k, v in sorted(r.details.items()):
                if isinstance(v, dict):
                    # Render nested dict: one sub-line per key (capped at 10)
                    print(f"    {k}:")
                    sub_items = list(v.items())[:10]
                    for sk, sv in sub_items:
                        sv_str = _format_detail_value(sv, depth=1)
                        print(f"      {str(sk):<38} {sv_str}")
                    if len(v) > 10:
                        print(f"      ... +{len(v) - 10} more")
                else:
                    v_str = _format_detail_value(v)
                    print(f"    {k:<44} {v_str}")

    print(f"\n{border}")
