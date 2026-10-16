"""
Abstract base class for benchmark metrics.

To add a new metric:
  1. Subclass Metric in metrics.py (or a new file)
  2. Implement the `name` property and `compute()` method
  3. Add an instance to DEFAULT_METRICS in metrics.py

See metrics.py for concrete examples.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import Field

from synthesize.models import DatasetItem, _ExtensibleModel


class MetricResult(_ExtensibleModel):
    """Result returned by a single metric computation."""

    name: str
    value: float | None  # primary numeric value (None if DB unavailable for DB-dependent metrics)
    display: str  # formatted string for reports (e.g. "18/20 (90.0%)")
    details: dict = Field(default_factory=dict)  # optional breakdown (e.g. per-check pass rates)


class Metric(ABC):
    """Abstract base class for benchmark metrics.

    records: list[DatasetItem]
        - One DatasetItem = one complete agent run (one intent execution)
        - DatasetItem.input.steps = API calls made within that run
        - list[DatasetItem] = all runs from a synthesis batch (e.g. n=20 → 20 items)

    db_path: Path | None
        The snapshot.db for the synthesis run (one DB for the whole batch, not per item).
        None if unavailable or not needed by this metric.
        DB-dependent metrics should return MetricResult(value=None, display="n/a (no DB)")
        when db_path is None.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier shown in benchmark reports."""
        ...

    @abstractmethod
    def compute(
        self,
        records: list[DatasetItem],
        db_path: Path | None = None,
    ) -> MetricResult:
        """Compute metric from DatasetItem records. Must be side-effect-free."""
        ...
