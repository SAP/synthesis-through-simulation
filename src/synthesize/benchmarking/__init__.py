"""
Benchmarking package for synthesis-through-simulation.

Public API:
  compute_metrics(records, metrics=DEFAULT_METRICS, db_path=None) → list[MetricResult]
  load_from_local(runs_dir, run_dir=None, env=None, intent=None, mode=None) → list[DatasetItem]
  load_from_langfuse(dataset_name) → list[DatasetItem]
  reproduce_db(item, env, out_path=None) → Path

Metric registries:
  DEFAULT_METRICS       — 7 core metrics (always run)
  EXTENDED_METRICS      — DEFAULT + trajectory diversity + simulation effectiveness (16 total)
  ALL_METRICS           — EXTENDED + DB coverage + synthesis quality + data quality (31 total)
  DATA_QUALITY_METRICS  — 5 DAMA-inspired data quality metrics (DB-dependent)

To add a new metric:
  1. Subclass Metric in the appropriate group file under benchmarking/
  2. Implement `name` property and `compute(records, db_path)` method
  3. Add an instance to the appropriate registry in benchmarking/metrics.py

See .claude/skills/add-metric/SKILL.md for step-by-step guidance.
"""

from __future__ import annotations

from pathlib import Path

from synthesize.models import DatasetItem

from .base import Metric, MetricResult
from .loaders import load_from_langfuse, load_from_local
from .metrics import ALL_METRICS, DATA_QUALITY_METRICS, DEFAULT_METRICS, EXTENDED_METRICS
from .reproduce import reproduce_db

__all__ = [
    "DatasetItem",
    "Metric",
    "MetricResult",
    "DEFAULT_METRICS",
    "EXTENDED_METRICS",
    "ALL_METRICS",
    "DATA_QUALITY_METRICS",
    "compute_metrics",
    "load_from_local",
    "load_from_langfuse",
    "reproduce_db",
]


def compute_metrics(
    records: list[DatasetItem],
    metrics: list[Metric] | None = None,
    db_path: Path | None = None,
) -> list[MetricResult]:
    """Run all metrics against records. Returns one MetricResult per metric.

    Args:
        records:  list[DatasetItem] — one item per trajectory (agent run)
        metrics:  metrics to compute (default: DEFAULT_METRICS)
        db_path:  Path to snapshot.db for this run.
                  For local source: .runs/<run_name>/snapshot.db
                  For Langfuse source: pass a reproduced DB path or None.
                  DB-dependent metrics return value=None when db_path is None.
    """
    if metrics is None:
        metrics = DEFAULT_METRICS
    return [m.compute(records, db_path=db_path) for m in metrics]
