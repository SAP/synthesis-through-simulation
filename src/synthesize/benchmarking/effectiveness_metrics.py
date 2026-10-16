"""
Group 3 — Simulation Effectiveness Metrics.

These metrics measure how effectively the agent interacts with the policy-enforcing
environment: reliability across multiple runs, procedure correctness, error learning,
tool coverage, and exploration of the rule space.

All are DB-independent and included in EXTENDED_METRICS.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from pathlib import Path

from synthesize.models import DatasetItem

from ._utils import normalized_entropy, shannon_entropy
from .base import Metric, MetricResult


class CorruptSuccessRate(Metric):
    """
    Fraction of nominally successful runs that have hidden procedural failures.

    Formula:
        corrupt_success_rate = |{r : r.success=True ∧ r.validation_summary.failed > 0}|
                               ─────────────────────────────────────────────────────────
                                           |{r : r.success=True}|

        Postcondition fallback (when validation_summary is absent):
            A run is "corrupt" if success=True but any postcondition is False.

    Interpretation:
        - 0.0  → all successful runs are also procedurally clean (ideal)
        - > 0.1 → more than 10% of successes are procedurally flawed — concerning
        - 1.0  → every "success" hides validation failures (synthesis is unreliable)

    Reference:
        Direct use: Procedure-Aware Evaluation (PAE), arXiv:2603.03116 —
        "corrupt successes" concept: agent achieves outcome postconditions but
        violates intermediate procedure constraints.
    """

    @property
    def name(self) -> str:
        return "corrupt_success_rate"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        successes = [r for r in records if r.metadata.success]
        if not successes:
            return MetricResult(
                name=self.name,
                value=0.0,
                display="0/0 successes",
                details={"corrupt_count": 0, "success_count": 0},
            )

        corrupt = 0
        for r in successes:
            vs = r.metadata.validation_summary
            if vs is not None:
                if vs.failed > 0:
                    corrupt += 1
            else:
                # Fallback: postcondition False despite success=True
                if any(not v for v in r.metadata.postconditions.values()):
                    corrupt += 1

        value = corrupt / len(successes)
        display = (
            f"{corrupt}/{len(successes)} successful runs have validation failures ({value:.1%})"
        )
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details={"corrupt_count": corrupt, "success_count": len(successes)},
        )


class PassK(Metric):
    """
    Per-intent pass^k reliability: fraction of intents where ALL k runs succeed.

    Formula:
        pass^k  = mean over intents of  [∀ r ∈ group(intent): r.success]
        pass^1  = mean over intents of  [∃ r ∈ group(intent): r.success]
        k_avg   = mean group size across all intents

    Interpretation:
        - pass^k = 1.0 → every intent succeeds on every single run (perfectly reliable)
        - pass^k = 0.0 → no intent ever succeeds consistently across all its runs
        - pass^1 ≫ pass^k → the agent sometimes succeeds but is unreliable (high variance)
        - pass^k ≈ pass^1 → success is consistent; small gap means high reliability
        - Most meaningful when multiple runs per intent exist (k_avg > 1)

    Reference:
        Direct use: τ-bench (arXiv:2406.12045) — pass^k reliability metric for
        agentic task completion across k independent runs of the same intent.
    """

    @property
    def name(self) -> str:
        return "pass_k"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        groups: dict[str, list[DatasetItem]] = defaultdict(list)
        for r in records:
            groups[r.input.intent].append(r)

        pass_k_flags = [all(r.metadata.success for r in g) for g in groups.values()]
        pass_1_flags = [any(r.metadata.success for r in g) for g in groups.values()]

        pass_k = statistics.mean(pass_k_flags)
        pass_1 = statistics.mean(pass_1_flags)
        k_avg = statistics.mean(len(g) for g in groups.values())

        display = (
            f"pass^k={pass_k:.1%} ({sum(pass_k_flags)}/{len(groups)} intents), "
            f"pass^1={pass_1:.1%}, k_avg={k_avg:.1f}"
        )
        per_intent = {
            intent: {
                "k": len(g),
                "all_pass": all(r.metadata.success for r in g),
                "any_pass": any(r.metadata.success for r in g),
            }
            for intent, g in groups.items()
        }
        return MetricResult(
            name=self.name,
            value=pass_k,
            display=display,
            details={"pass_k": pass_k, "pass_1": pass_1, "k_avg": k_avg, "per_intent": per_intent},
        )


class ErrorRecoveryEfficiency(Metric):
    """
    Fraction of errors from which the agent successfully learned and did not repeat.

    Formula:
        For each error (tool T errored at step i):
            "learned" = True  iff  no subsequent step j > i also errors on tool T

        error_recovery_efficiency = |learned errors| / |total errors|

    Interpretation:
        - 1.0  → the agent never repeats the same error on the same tool (perfect learning)
        - 0.0  → the agent always repeats errors without adapting
        - 0.5–0.8 → typical range; agent learns from most but not all errors
        - Should be higher in blind mode (forced to learn) than informed mode

    Reference:
        Inspired by: AgentProcessBench (arXiv:2603.14465) — step-level process quality
        labels for distinguishing process failure from outcome failure. Extends the
        existing RecoveryRate metric (run-level) to a finer error-level signal.
    """

    @property
    def name(self) -> str:
        return "error_recovery_efficiency"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        total_errors = 0
        learned = 0

        for r in records:
            steps = r.input.steps
            error_positions = [(i, s.tool) for i, s in enumerate(steps) if s.is_error]
            for idx, tool in error_positions:
                total_errors += 1
                future_same_tool_errors = [
                    e for e in error_positions if e[0] > idx and e[1] == tool
                ]
                if not future_same_tool_errors:
                    learned += 1

        if total_errors == 0:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (no errors in dataset)",
            )

        value = learned / total_errors
        display = f"{learned}/{total_errors} errors not repeated ({value:.1%})"
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details={"learned": learned, "total_errors": total_errors},
        )


class IntentCoverage(Metric):
    """
    Normalized entropy over the distribution of intents in the batch.

    Formula:
        intent_coverage = H_norm(intent_counts)
                        = H(intent_counts) / log(|distinct intents|)
        where H(X) = -∑ p(x) · log p(x)

    Interpretation:
        - 1.0  → perfectly uniform coverage across all intents (ideal for evaluation)
        - 0.0  → all runs use the same intent (trivially 0 for single-intent batches)
        - NOTE: returns 1.0 trivially for single-intent batches — most meaningful for
          mixed-intent batches; per-intent breakdown always shown in details

    Reference:
        Inspired by: EnvScaler (arXiv:2601.05808) — topic diversity via Shannon entropy
        applied to the distribution of synthesis scenarios, adapted here to intent coverage.
    """

    @property
    def name(self) -> str:
        return "intent_coverage"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        intent_counts: Counter = Counter(r.input.intent for r in records)
        n_intents = len(intent_counts)

        if n_intents == 1:
            intent_name = next(iter(intent_counts))
            return MetricResult(
                name=self.name,
                value=1.0,
                display=f"1.0 (single intent: {intent_name}, n={len(records)})",
                details=dict(intent_counts),
            )

        value = normalized_entropy(intent_counts)
        h_raw = shannon_entropy(intent_counts)
        display = f"{value:.3f} (H={h_raw:.2f} over {n_intents} intents)"
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details=dict(intent_counts),
        )


class ApiEndpointCoverage(Metric):
    """
    Per-intent fraction of available tools actually used, averaged across intents.

    Formula:
        available(intent) = ⋃ {tools called in any run for that intent}
            (proxy for IntentDef.tools — any tool observed for an intent is available)

        per_run_coverage(r) = |{tools called in r}| / |available(intent(r))|

        api_endpoint_coverage = mean over intents of mean(per_run_coverage)

    Interpretation:
        - 1.0  → every run calls every available tool for its intent (full breadth)
        - 0.5  → runs on average call half the tools available for their intent
        - Low values indicate the agent is over-relying on a subset of tools
        - Most interpretable when batches have many runs per intent (k ≥ 5)

    Reference:
        Original metric for this framework — directly grounded in the IntentDef.tools
        structure that constrains which tools each intent can use. Measures whether
        the agent explores the full tool API available to it.
    """

    @property
    def name(self) -> str:
        return "api_endpoint_coverage"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        # Group by intent
        groups: dict[str, list[DatasetItem]] = defaultdict(list)
        for r in records:
            groups[r.input.intent].append(r)

        coverages = []
        details: dict[str, dict] = {}

        for intent, group in groups.items():
            # All tools ever called for this intent = proxy for available tools
            available = {s.tool for r in group for s in r.input.steps}
            if not available:
                continue
            per_run = [len({s.tool for s in r.input.steps}) / len(available) for r in group]
            intent_mean = statistics.mean(per_run) if per_run else 0.0
            coverages.append(intent_mean)
            details[intent] = {
                "available_tools": len(available),
                "avg_used_fraction": round(intent_mean, 3),
                "tools": sorted(available),
            }

        if not coverages:
            return MetricResult(name=self.name, value=None, display="n/a (no tool calls)")

        value = statistics.mean(coverages)
        display = f"{value:.3f} avg tool coverage across {len(groups)} intent(s)"
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details=details,
        )


class ErrorTypeDiversity(Metric):
    """
    Normalized Shannon entropy over the categories of API errors encountered.

    Formula:
        Categories are inferred from error message content via keyword matching:
            "not found" / "does not exist" / "unknown" / "no such" → reference
            "invalid" / "must be" / "not a valid"                  → validation
            "already" / "cannot" / "not allowed" / "only allowed"  → transition_or_constraint
            (other)                                                → other

        error_type_diversity = H_norm(category_counts)
                             = H(category_counts) / log(|distinct categories|)

    Interpretation:
        - 1.0  → errors spread uniformly across all categories (broad rule space explored)
        - 0.0  → all errors are the same type (narrow exploration)
        - Returns n/a when there are no errors in the dataset
        - Higher values in blind mode are expected (agent explores more of the error space)

    Reference:
        Original metric for this framework — measures how broadly the agent has explored
        the policy enforcement space. The API raises ValueError with typed messages;
        this metric quantifies how many distinct rule categories were discovered.
    """

    @property
    def name(self) -> str:
        return "error_type_diversity"

    @staticmethod
    def _categorise(msg: str) -> str:
        m = msg.lower()
        if any(w in m for w in ("not found", "does not exist", "unknown", "no such")):
            return "reference"
        if any(w in m for w in ("invalid", "must be", "not a valid", "must be one of")):
            return "validation"
        if any(w in m for w in ("already", "cannot", "not allowed", "only allowed")):
            return "transition_or_constraint"
        return "other"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        error_messages = [str(s.result) for r in records for s in r.input.steps if s.is_error]
        if not error_messages:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (no errors in dataset)",
            )

        counter: Counter = Counter(self._categorise(m) for m in error_messages)
        value = normalized_entropy(counter)
        h_raw = shannon_entropy(counter)
        display = (
            f"{value:.3f} over {len(counter)} error categories "
            f"({len(error_messages)} errors, H={h_raw:.2f})"
        )
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details=dict(counter),
        )
