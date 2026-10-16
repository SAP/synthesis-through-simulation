"""
Langfuse evaluation run — computes benchmark metrics for a dataset and logs per-item scores.

run_langfuse_evaluation() follows the same compute pipeline as local benchmarking
(load → compute_metrics → log scores), with the additional step of logging
per-item scores back to Langfuse traces so they appear under each trace's scores.

Note: scores are attached to individual traces via lf.score(trace_id=...).
Named dataset-run grouping (the "Runs" tab in the Langfuse UI) requires
additional dataset_run_item API calls which are not yet implemented here.

Scores logged per item:
  - success: 1.0 or 0.0
  - total_steps: int
  - error_count: int
  - recovery_count: int
  - postcondition.<name>: 1.0 or 0.0 per postcondition
"""

from __future__ import annotations

import os

from synthesize.models import DatasetItem

from .base import Metric, MetricResult
from .loaders import _parse_langfuse_item
from .metrics import DEFAULT_METRICS


def run_langfuse_evaluation(
    dataset_name: str,
    metrics: list[Metric] | None = None,
) -> tuple[list[MetricResult], int]:
    """Load a Langfuse dataset, compute metrics, and log per-item scores back.

    Pipeline:
      1. Fetch dataset items from Langfuse
      2. compute_metrics(records, metrics) → list[MetricResult]
      3. Log per-item scores back to individual Langfuse traces
      4. Return (list[MetricResult], record_count)

    Note: scores are attached to individual traces. Named dataset-run grouping
    (Langfuse "Runs" tab) requires additional API calls not yet implemented.
    """
    from . import compute_metrics

    if metrics is None:
        metrics = DEFAULT_METRICS

    try:
        from langfuse import Langfuse
    except ImportError:
        print("langfuse not installed. Install with: uv pip install -e '.[langfuse]'")
        return [], 0

    from dotenv import load_dotenv

    load_dotenv()
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    if not public_key:
        print("LANGFUSE_PUBLIC_KEY not set in .env — cannot create evaluation run.")
        return [], 0

    lf = Langfuse(
        public_key=public_key,
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )

    # Fetch dataset once and parse items in sync to guarantee ordering alignment
    dataset = lf.get_dataset(dataset_name)
    raw_items = list(dataset.items)
    records = [_parse_langfuse_item(raw) for raw in raw_items]
    if not records:
        print(f"No items found in dataset {dataset_name!r}")
        return [], 0

    results = compute_metrics(records, metrics=metrics)

    # Log per-item scores back to Langfuse
    try:
        for raw_item, item in zip(raw_items, records):
            trace_id = getattr(raw_item, "trace_id", None)
            if not trace_id:
                continue
            scores = _item_scores(item)
            for score_name, score_value in scores.items():
                lf.score(
                    name=score_name,
                    value=score_value,
                    data_type="NUMERIC",
                    trace_id=trace_id,
                )
        print(f"  Logged scores to {len(raw_items)} Langfuse traces on dataset {dataset_name!r}")
    except Exception as exc:
        print(f"  Warning: could not log Langfuse scores: {exc}")

    return results, len(records)


def _item_scores(item: DatasetItem) -> dict[str, float]:
    """Compute per-item numeric scores for Langfuse."""
    scores: dict[str, float] = {
        "success": 1.0 if item.metadata.success else 0.0,
        "total_steps": float(item.metadata.total_steps),
        "error_count": float(item.metadata.error_count),
        "recovery_count": float(item.metadata.recovery_count),
    }
    for key, ok in item.metadata.postconditions.items():
        scores[f"postcondition.{key}"] = 1.0 if ok else 0.0
    return scores
