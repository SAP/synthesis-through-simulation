"""
Concrete benchmark metric implementations.

To add a new metric:
  1. Subclass Metric (from .base) in the appropriate group file:
       diversity_metrics.py       — trajectory diversity
       effectiveness_metrics.py   — simulation effectiveness
       synthesis_quality_metrics.py — NeurIPS-level research metrics
       coverage_metrics.py        — DB-level coverage (seed-excluded, DB-dependent)
  2. Implement `name` (str property) and `compute(records, db_path)` -> MetricResult
  3. Add an instance to the appropriate registry at the bottom of this file:
       DEFAULT_METRICS  — core metrics (always run)
       EXTENDED_METRICS — DEFAULT + diversity + effectiveness (--metrics extended)
       ALL_METRICS      — EXTENDED + coverage + synthesis quality (--metrics all)

Each metric receives:
  - records: list[DatasetItem] — one item per trajectory (agent run)
  - db_path: Path | None — snapshot.db for the run (may be None)
"""

from __future__ import annotations

import statistics
from pathlib import Path

from synthesize.models import DatasetItem

from .base import Metric, MetricResult
from .coverage_metrics import (
    CrossTableReferentialDiversity,
    SchemaFieldCoverage,
)
from .data_quality_metrics import (
    DATA_QUALITY_METRICS,
    LLMDataQualityJudge,
    RealisticValueDistributionScore,
    RecordDeduplicationRate,
    TemporalConsistencyScore,
    WorkflowCompletenessScore,
)
from .diversity_metrics import ToolSequenceDiversity, ToolUsageDiversity, UniqueToolRatio
from .effectiveness_metrics import (
    ApiEndpointCoverage,
    CorruptSuccessRate,
    ErrorRecoveryEfficiency,
    ErrorTypeDiversity,
    IntentCoverage,
    PassK,
)
from .synthesis_quality_metrics import (
    ArgumentValueDiversity,
    BlindVsInformedGap,
    EnumBalanceScore,
    RuleDiscoveryRate,
    VendiDiversityScore,
)


class SuccessRate(Metric):
    """Fraction of runs where all postconditions passed."""

    @property
    def name(self) -> str:
        return "success_rate"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")
        n_success = sum(1 for r in records if r.metadata.success)
        n_total = len(records)
        pct = 100 * n_success / n_total
        return MetricResult(
            name=self.name,
            value=n_success / n_total,
            display=f"{n_success}/{n_total} ({pct:.1f}%)",
        )


class AvgSteps(Metric):
    """Average number of tool calls per run."""

    @property
    def name(self) -> str:
        return "avg_steps"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")
        steps = [r.metadata.total_steps for r in records]
        avg = statistics.mean(steps)
        std = statistics.stdev(steps) if len(steps) > 1 else 0.0
        return MetricResult(
            name=self.name,
            value=avg,
            display=f"{avg:.1f} (std {std:.1f})",
        )


class AvgErrors(Metric):
    """Average number of API errors (tool call failures) per run."""

    @property
    def name(self) -> str:
        return "avg_errors"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")
        errors = [r.metadata.error_count for r in records]
        avg = statistics.mean(errors)
        std = statistics.stdev(errors) if len(errors) > 1 else 0.0
        return MetricResult(
            name=self.name,
            value=avg,
            display=f"{avg:.1f} (std {std:.1f})",
        )


class RecoveryRate(Metric):
    """Fraction of runs-with-errors where the agent recovered (completed despite errors)."""

    @property
    def name(self) -> str:
        return "recovery_rate"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        runs_with_errors = [r for r in records if r.metadata.error_count > 0]
        if not runs_with_errors:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (no runs with errors)",
            )
        recoveries = sum(1 for r in runs_with_errors if r.metadata.success)
        pct = 100 * recoveries / len(runs_with_errors)
        return MetricResult(
            name=self.name,
            value=recoveries / len(runs_with_errors),
            display=f"{recoveries}/{len(runs_with_errors)} ({pct:.0f}%)",
        )


class PostconditionRates(Metric):
    """Per-postcondition pass rate across all runs."""

    @property
    def name(self) -> str:
        return "postcondition_rates"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)", details={})

        # Aggregate pass counts per postcondition key
        totals: dict[str, int] = {}
        passes: dict[str, int] = {}
        for r in records:
            for key, ok in r.metadata.postconditions.items():
                totals[key] = totals.get(key, 0) + 1
                if ok:
                    passes[key] = passes.get(key, 0) + 1

        rates = {k: passes.get(k, 0) / totals[k] for k in totals}
        total_passes = sum(passes.get(k, 0) for k in totals)
        overall = total_passes / sum(totals.values()) if totals else 0.0
        details_display = {k: f"{v * 100:.1f}%" for k, v in sorted(rates.items())}

        return MetricResult(
            name=self.name,
            value=overall,
            display=f"{overall * 100:.1f}% avg across {len(rates)} conditions",
            details=details_display,
        )


class ValidationPassRate(Metric):
    """Average fraction of validation checks that pass per run."""

    @property
    def name(self) -> str:
        return "validation_pass_rate"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        run_rates = []
        for r in records:
            vs = r.metadata.validation_summary
            if vs and vs.total_checks > 0:
                run_rates.append(vs.passed / vs.total_checks)

        if not run_rates:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (no validation data)",
            )
        avg = statistics.mean(run_rates)
        return MetricResult(
            name=self.name,
            value=avg,
            display=f"{avg * 100:.1f}%",
        )


class PerCheckPassRate(Metric):
    """Per-validation-rule pass rate across all runs."""

    @property
    def name(self) -> str:
        return "per_check_pass_rate"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        totals: dict[str, int] = {}
        passes: dict[str, int] = {}

        for r in records:
            vs = r.metadata.validation_summary
            if not vs:
                continue
            for chk in vs.checks:
                key = f"{chk.category}: {chk.rule}"
                totals[key] = totals.get(key, 0) + 1
                if chk.passed:
                    passes[key] = passes.get(key, 0) + 1

        if not totals:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (no check data)",
                details={},
            )

        rates = {k: passes.get(k, 0) / totals[k] for k in totals}
        total_passes = sum(passes.get(k, 0) for k in totals)
        overall = total_passes / sum(totals.values())
        details_display = {k: f"{v * 100:.1f}%" for k, v in sorted(rates.items())}

        return MetricResult(
            name=self.name,
            value=overall,
            display=f"{overall * 100:.1f}% avg across {len(rates)} checks",
            details=details_display,
        )


DEFAULT_METRICS: list[Metric] = [
    SuccessRate(),
    AvgSteps(),
    AvgErrors(),
    RecoveryRate(),
    PostconditionRates(),
    ValidationPassRate(),
    PerCheckPassRate(),
]

# EXTENDED_METRICS: DEFAULT + trajectory diversity + simulation effectiveness
# Use with: synthesize benchmark --metrics extended
EXTENDED_METRICS: list[Metric] = DEFAULT_METRICS + [
    # Trajectory diversity (3)
    ToolUsageDiversity(),
    ToolSequenceDiversity(),
    UniqueToolRatio(),
    # Simulation effectiveness (6)
    CorruptSuccessRate(),
    PassK(),
    ErrorRecoveryEfficiency(),
    IntentCoverage(),
    ApiEndpointCoverage(),
    ErrorTypeDiversity(),
]

# ALL_METRICS: EXTENDED + DB-level coverage + synthesis quality + data quality
# Use with: synthesize benchmark --metrics all
ALL_METRICS: list[Metric] = EXTENDED_METRICS + [
    # Data coverage (DB-dependent, seed-excluded)
    SchemaFieldCoverage(),
    CrossTableReferentialDiversity(),
    # Synthesis quality (5)
    BlindVsInformedGap(),
    RuleDiscoveryRate(),
    VendiDiversityScore(),
    ArgumentValueDiversity(),
    EnumBalanceScore(),
    # Data quality (5) — DB-dependent, DAMA-inspired
    TemporalConsistencyScore(),
    WorkflowCompletenessScore(),
    RealisticValueDistributionScore(),
    LLMDataQualityJudge(),
    RecordDeduplicationRate(),
]

# Re-export DATA_QUALITY_METRICS for direct import
__all__ = [
    "DEFAULT_METRICS",
    "EXTENDED_METRICS",
    "ALL_METRICS",
    "DATA_QUALITY_METRICS",
]
