"""
Group 1 — Trajectory Diversity Metrics.

These metrics measure how varied the agent's tool usage behaviour is across runs.
All are DB-independent and included in EXTENDED_METRICS.

Scope caveat for ToolSequenceDiversity:
    IntentDef.tools constrains which tools can be called per intent, so within-intent
    sequence variety is naturally bounded by task structure — not purely agent behaviour.
    This metric is most informative when comparing across different intents in a
    mixed-intent batch. Within single-intent batches, treat it as a lower bound.
"""

from __future__ import annotations

import statistics
from collections import Counter
from pathlib import Path

from synthesize.models import DatasetItem

from ._utils import (
    normalized_entropy,
    shannon_entropy,
    tool_bigrams,
    tool_sequence,
)
from .base import Metric, MetricResult


class ToolUsageDiversity(Metric):
    """
    Normalized Shannon entropy over the distribution of tool calls across all runs.

    Formula:
        Let counts(t) = total number of times tool t was called across all runs.
        tool_usage_diversity = H_norm(counts)
                             = H(counts) / log(|distinct tools|)
        where H(X) = -∑ p(x) · log p(x)

    Interpretation:
        - 1.0  → all tools called equally often (maximum breadth)
        - 0.0  → only one tool ever called (degenerate behaviour)
        - 0.6–0.9 → healthy range; agent uses most tools with reasonable variety
        - Low values indicate the agent over-relies on a narrow subset of tools

    Reference:
        Inspired by: EnvScaler (arXiv:2601.05808) — topic diversity via Shannon entropy
        applied to synthesis scenario distributions; adapted here to tool-call distributions.
    """

    @property
    def name(self) -> str:
        return "tool_usage_diversity"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        counter: Counter = Counter(s.tool for r in records for s in r.input.steps)
        if not counter:
            return MetricResult(name=self.name, value=None, display="n/a (no tool calls)")

        value = normalized_entropy(counter)
        h_raw = shannon_entropy(counter)
        display = (
            f"{value:.3f} (H={h_raw:.2f} over {len(counter)} tools, "
            f"{sum(counter.values())} total calls)"
        )
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details=dict(counter),
        )


class ToolSequenceDiversity(Metric):
    """
    Fraction of runs with unique tool-call sequences, plus bigram coverage.

    Formula:
        sequence_uniqueness = |distinct tool sequences| / N
        bigram_coverage     = |observed (tool_i, tool_{i+1}) pairs|
                              ─────────────────────────────────────
                              |all tools|²   (maximum possible bigrams)
        value = sequence_uniqueness  (primary signal)

    Interpretation:
        - sequence_uniqueness = 1.0 → every run takes a different tool path
        - sequence_uniqueness = 0.0 → all runs identical (no exploration)
        - bigram_coverage indicates how many distinct tool transitions were observed
        - NOTE: naturally bounded within a single intent by IntentDef.tools —
          most informative for mixed-intent batches; n_intents_in_batch is reported

    Reference:
        Inspired by: UniToolCall (arXiv:2604.11557) — structural diversity of
        tool interaction patterns in agentic benchmarks; adapted here to measure
        sequence-level rather than invocation-level diversity.
    """

    @property
    def name(self) -> str:
        return "tool_sequence_diversity"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        seqs = [tool_sequence(r.input.steps) for r in records]
        n_unique = len(set(seqs))
        n_total = len(seqs)

        all_tools = {s.tool for r in records for s in r.input.steps}
        observed_bigrams = {bg for r in records for bg in tool_bigrams(r.input.steps)}
        possible_bigrams = len(all_tools) ** 2

        bigram_coverage = len(observed_bigrams) / possible_bigrams if possible_bigrams > 0 else 0.0
        intent_counts: Counter = Counter(r.input.intent for r in records)
        n_intents = len(intent_counts)

        value = n_unique / n_total
        display = (
            f"{n_unique}/{n_total} unique seqs ({value:.3f}), bigram_cov={bigram_coverage:.3f}"
        )
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details={
                "unique_sequences": n_unique,
                "total_runs": n_total,
                "bigram_coverage": round(bigram_coverage, 4),
                "observed_bigrams": len(observed_bigrams),
                "n_intents_in_batch": n_intents,
            },
        )


class UniqueToolRatio(Metric):
    """
    Mean per-run ratio of distinct tools used to total steps taken.

    Formula:
        unique_tool_ratio(r) = |{distinct tools in r}| / max(|steps in r|, 1)
        unique_tool_ratio    = mean over all records

        Also reported separately for successful and failed runs to enable
        the quality split described in Endless Terminals.

    Interpretation:
        - 1.0  → every step calls a different tool (maximum exploration within a run)
        - ~0.5 → agent uses each tool about twice on average
        - The Endless Terminals paper finds 0.49 for successful runs vs 0.18 for failures —
          a high ratio correlates with task success
        - Low values may indicate the agent is stuck in retry loops on the same tool

    Reference:
        Direct use: Endless Terminals (arXiv:2601.16443) — unique command ratio
        distinguishes successful from failed agent runs (0.49 vs 0.18); adapted here
        from shell commands to tool API calls.
    """

    @property
    def name(self) -> str:
        return "unique_tool_ratio"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        ratios = [
            len({s.tool for s in r.input.steps}) / max(len(r.input.steps), 1) for r in records
        ]
        value = statistics.mean(ratios)

        success_ratios = [v for v, r in zip(ratios, records) if r.metadata.success]
        fail_ratios = [v for v, r in zip(ratios, records) if not r.metadata.success]

        details: dict = {"overall_mean": round(value, 4)}
        if success_ratios:
            details["successful_mean"] = round(statistics.mean(success_ratios), 4)
        if fail_ratios:
            details["failed_mean"] = round(statistics.mean(fail_ratios), 4)

        display = f"{value:.3f} mean unique-tool ratio (n={len(records)})"
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details=details,
        )
