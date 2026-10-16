"""
Group 4 — Synthesis Quality Metrics.

These metrics answer the core research questions:
  - Does informed mode outperform blind mode? (BlindVsInformedGap)
  - Do agents successfully discover rules from errors? (RuleDiscoveryRate)
  - How diverse are the generated datasets? (VendiDiversityScore)
  - How varied are the argument values the agent chose? (ArgumentValueDiversity)
  - How evenly are enum values distributed in generated data? (EnumBalanceScore — DB-dep., categorical only)

All except EnumBalanceScore are DB-independent and included in ALL_METRICS.
EnumBalanceScore is DB-dependent and also in ALL_METRICS.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from pathlib import Path

from synthesize.models import DatasetItem

from ._utils import jaccard_similarity, js_divergence, normalized_entropy
from .base import Metric, MetricResult


class BlindVsInformedGap(Metric):
    """
    Difference in success rate between informed and blind agent modes.

    Formula:
        SR(mode) = |{r : r.success=True ∧ r.mode=mode}| / |{r : r.mode=mode}|
        blind_vs_informed_gap = SR(informed) - SR(blind)

        Also computed per intent to show which intents have the largest gaps.

    Interpretation:
        - Positive gap → informed mode helps (agent benefits from knowing the rules)
        - 0.0          → mode makes no difference (rules are trivially discoverable)
        - Negative gap → blind mode somehow outperforms (unusual; worth investigating)
        - > 0.3        → a 30pp gap means the rules are hard to discover from errors alone
        - Returns n/a when both modes are not present in the dataset

    Reference:
        Original metric for this framework — the core thesis metric measuring whether
        rule injection into the agent system prompt makes a material difference to
        task success, which is the central empirical claim of the paper.
    """

    @property
    def name(self) -> str:
        return "blind_vs_informed_gap"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        blind = [r for r in records if r.input.mode == "blind"]
        informed = [r for r in records if r.input.mode == "informed"]

        if not blind or not informed:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (need both blind and informed runs)",
            )

        blind_sr = statistics.mean(r.metadata.success for r in blind)
        informed_sr = statistics.mean(r.metadata.success for r in informed)
        gap = informed_sr - blind_sr

        # Per-intent breakdown
        per_intent: dict[str, dict] = {}
        intents = {r.input.intent for r in records}
        for intent in intents:
            b = [r for r in blind if r.input.intent == intent]
            i = [r for r in informed if r.input.intent == intent]
            if b and i:
                b_sr = statistics.mean(r.metadata.success for r in b)
                i_sr = statistics.mean(r.metadata.success for r in i)
                per_intent[intent] = {
                    "blind_sr": round(b_sr, 3),
                    "informed_sr": round(i_sr, 3),
                    "gap": round(i_sr - b_sr, 3),
                }

        display = (
            f"{gap:+.1%} (informed={informed_sr:.1%} n={len(informed)}, "
            f"blind={blind_sr:.1%} n={len(blind)})"
        )
        return MetricResult(
            name=self.name,
            value=gap,
            display=display,
            details={
                "informed_sr": round(informed_sr, 4),
                "blind_sr": round(blind_sr, 4),
                "gap": round(gap, 4),
                "per_intent": per_intent,
            },
        )


class VendiDiversityScore(Metric):
    """
    Vendi Score approximation measuring trajectory diversity via Frobenius effective rank.

    Formula:
        Exact Vendi Score: VS = exp(H(eigenvalues(K/n)))
        where K[i,j] = Jaccard(tool_set_i, tool_set_j)  (kernel matrix)

        Approximation (no numpy): Frobenius effective rank, normalised by n
            VS_raw  = n² / ‖K‖²_F   where  ‖K‖²_F = ∑_{i,j} K[i,j]²
            VS_norm = VS_raw / n  ∈ (0, 1]

        Normalising by n makes the metric batch-size independent: a batch of 15 and a
        batch of 50 with the same level of diversity produce the same score.
        Capped at N=200 records for O(n²) tractability.

        Range: (0, 1]  — identical runs → 1/n ≈ 0; maximally diverse runs → 1.0

    Interpretation:
        - VS ≈ 0   → all trajectories use identical tool sets (no diversity)
        - VS = 1.0 → every trajectory uses a completely distinct tool set (maximum)
        - NOTE: Jaccard over tool sets is high within a single intent (same IntentDef.tools
          available). Most meaningful for mixed-intent batches; n_intents_in_batch reported.

    Reference:
        Direct use: Vendi Score (arXiv:2210.02410, Friedman & Dieng, NeurIPS 2023) —
        reference-free diversity metric via matrix eigenvalue entropy.
        Frobenius effective-rank approximation avoids numpy eigendecomposition while
        preserving the intuition. Also inspired by: EnvScaler (arXiv:2601.05808)
        for the application context of measuring synthesis batch diversity.
    """

    @property
    def name(self) -> str:
        return "vendi_diversity_score"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        sample = records[:200]  # cap for O(n²) computation
        n = len(sample)
        tool_sets = [frozenset(s.tool for s in r.input.steps) for r in sample]

        # Compute ‖K‖²_F = ∑_{i,j} K[i,j]²
        frobenius_sq = sum(
            jaccard_similarity(tool_sets[i], tool_sets[j]) ** 2 for i in range(n) for j in range(n)
        )

        effective_rank = (n * n) / frobenius_sq if frobenius_sq > 0 else float(n)
        normalized = effective_rank / n  # batch-size independent, range (0, 1]

        # Average pairwise similarity
        total_sim = sum(
            jaccard_similarity(tool_sets[i], tool_sets[j]) for i in range(n) for j in range(n)
        )
        avg_sim = total_sim / (n * n)

        intent_counts: Counter = Counter(r.input.intent for r in sample)
        n_intents = len(intent_counts)

        display = (
            f"{normalized:.3f} "
            f"(Vendi/n, effective_rank={effective_rank:.2f}, n={n}, avg_sim={avg_sim:.3f})"
        )
        return MetricResult(
            name=self.name,
            value=round(normalized, 4),
            display=display,
            details={
                "vendi_normalized": round(normalized, 4),
                "effective_rank": round(effective_rank, 4),
                "avg_pairwise_similarity": round(avg_sim, 4),
                "n_records_used": n,
                "n_intents_in_batch": n_intents,
                "method": "frobenius_effective_rank",
            },
        )


class RuleDiscoveryRate(Metric):
    """
    Fraction of errors from which the agent appears to have discovered the underlying rule.

    Formula:
        For each error on tool T at step i:
            "discovered" = True  iff  tool T is not called with an error again (at any j > i)

        rule_discovery_rate = |discovered errors| / |total errors|

        Note: this is intentionally similar to ErrorRecoveryEfficiency but framed as
        "rule learning" rather than "error avoidance" — the distinction is conceptual
        for reporting purposes (same formula, different interpretation context).

    Interpretation:
        - 1.0  → every error leads to a permanent rule adaptation
        - 0.0  → no errors lead to rule adaptation (agent never learns)
        - More meaningful in blind mode (agent has no prior rule knowledge)
        - Comparing blind vs informed gives the baseline for rule_discovery_rate

    Reference:
        Original metric for this framework — inspired by blind-mode learning dynamics
        in τ-bench (arXiv:2406.12045). Measures whether the agent treats API errors as
        learning signals about policy constraints, which is the central hypothesis of
        the blind-mode synthesis approach.
    """

    @property
    def name(self) -> str:
        return "rule_discovery_rate"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        total_errors = 0
        discovered = 0

        for r in records:
            steps = r.input.steps
            error_positions = [(i, s.tool) for i, s in enumerate(steps) if s.is_error]
            for idx, tool in error_positions:
                total_errors += 1
                future_same_tool_errors = [
                    e for e in error_positions if e[0] > idx and e[1] == tool
                ]
                if not future_same_tool_errors:
                    discovered += 1

        if total_errors == 0:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (no errors in dataset)",
            )

        # Per-mode breakdown
        mode_stats: dict[str, dict] = {}
        for mode in ("blind", "informed"):
            mode_records = [r for r in records if r.input.mode == mode]
            if mode_records:
                m_total = 0
                m_disc = 0
                for r in mode_records:
                    steps = r.input.steps
                    errs = [(i, s.tool) for i, s in enumerate(steps) if s.is_error]
                    for idx, tool in errs:
                        m_total += 1
                        if not [e for e in errs if e[0] > idx and e[1] == tool]:
                            m_disc += 1
                if m_total:
                    mode_stats[mode] = {
                        "rate": round(m_disc / m_total, 4),
                        "discovered": m_disc,
                        "total_errors": m_total,
                    }

        value = discovered / total_errors
        display = f"{discovered}/{total_errors} errors lead to rule adaptation ({value:.1%})"
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details={"discovered": discovered, "total_errors": total_errors, **mode_stats},
        )


class EnumBalanceScore(Metric):
    """
    How evenly the agent distributes values across CHECK-constrained enum columns.

    Scope: categorical (enum) columns only — columns with CHECK(col IN (...)) constraints.
    Numeric columns are not covered; use RealisticValueDistributionScore for those.

    Formula:
        For each CHECK-constrained enum column in the DB (agent rows only):
            p_obs  = observed distribution over enum values (agent rows)
            p_uni  = uniform distribution over all valid enum values

            JSD(p_obs, p_uni) = 0.5·KL(p_obs‖M) + 0.5·KL(p_uni‖M),  M = 0.5·(p_obs+p_uni)

        enum_balance_score = 1 - mean(JSD) over all enum columns

        Requires db_path. Excludes seed rows via baseline.db convention
        (baseline_path = db_path.parent / "baseline.db").

    Interpretation:
        - 1.0  → agent distributes values uniformly across all enum options (fully balanced)
        - 0.5  → moderate skew toward some values
        - 0.0  → agent always picks the same enum value (completely unbalanced)
        - Note: uniform is not always the real-world reference distribution. For
          real-world fidelity use RealisticValueDistributionScore with quality_priors.py.
        - Per-column JSD shown in details to identify which columns are skewed.

    Reference:
        Inspired by: Precision and Recall for Distributions (arXiv:2102.09672) —
        adapted to measure categorical balance via JSD against a uniform reference.
    """

    @property
    def name(self) -> str:
        return "enum_balance_score"

    @staticmethod
    def _parse_enum_values(ddl: str, col_name: str) -> list[str] | None:
        """Extract enum values for col_name from a SQLite DDL CHECK IN constraint."""
        import re

        # Match: col_name TYPE ... CHECK(col_name IN ("v1", "v2", ...))
        pattern = re.compile(
            rf"{re.escape(col_name)}\s+\w+[^,\n]*?CHECK\s*\(\s*{re.escape(col_name)}\s+IN\s*\(([^)]+)\)",
            re.IGNORECASE,
        )
        m = pattern.search(ddl)
        if not m:
            return None
        inner = m.group(1)
        values = re.findall(r"""["']([^"']+)["']""", inner)
        return values if values else None

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if db_path is None:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (no DB)",
            )
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        import sqlite3

        baseline_path = db_path.parent / "baseline.db"
        has_baseline = baseline_path.exists()

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Get all tables and their CHECK constraints
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            jsd_scores: dict[str, float] = {}

            for table in tables:
                # Get CHECK constraints from table DDL
                cursor.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
                )
                row = cursor.fetchone()
                if not row or not row[0]:
                    continue
                ddl = row[0]

                import re

                # Find all column names that appear to have CHECK constraints
                col_matches = re.findall(
                    r"(\w+)\s+\w+[^,\n]*?CHECK\s*\(\1\s+IN\s*\(", ddl, re.IGNORECASE
                )
                for col_name in col_matches:
                    enum_vals = self._parse_enum_values(ddl, col_name)
                    if not enum_vals:
                        continue

                    # Get final distribution
                    try:
                        cursor.execute(
                            f"SELECT {col_name}, COUNT(*) FROM {table} WHERE {col_name} IS NOT NULL GROUP BY {col_name}"  # noqa: S608
                        )
                        final_dist = dict(cursor.fetchall())
                    except sqlite3.Error:
                        continue

                    # Subtract baseline if available
                    if has_baseline:
                        try:
                            baseline_conn = sqlite3.connect(str(baseline_path))
                            bcursor = baseline_conn.cursor()
                            bcursor.execute(
                                f"SELECT {col_name}, COUNT(*) FROM {table} WHERE {col_name} IS NOT NULL GROUP BY {col_name}"  # noqa: S608
                            )
                            baseline_dist = dict(bcursor.fetchall())
                            baseline_conn.close()
                            # Agent-only distribution
                            agent_dist = {
                                k: max(0, final_dist.get(k, 0) - baseline_dist.get(k, 0))
                                for k in set(final_dist) | set(baseline_dist)
                            }
                            agent_dist = {k: v for k, v in agent_dist.items() if v > 0}
                        except sqlite3.Error:
                            agent_dist = final_dist
                    else:
                        agent_dist = final_dist

                    if not agent_dist or sum(agent_dist.values()) == 0:
                        continue

                    # Uniform reference over known enum values
                    uniform_dist = {v: 1 for v in enum_vals}
                    jsd = js_divergence(agent_dist, uniform_dist)
                    jsd_scores[f"{table}.{col_name}"] = round(jsd, 4)

            conn.close()

            if not jsd_scores:
                return MetricResult(
                    name=self.name,
                    value=None,
                    display="n/a (no enum columns found)",
                )

            mean_jsd = statistics.mean(jsd_scores.values())
            value = 1.0 - mean_jsd
            display = (
                f"{value:.3f} (1 - mean_JSD={mean_jsd:.3f} over {len(jsd_scores)} enum columns)"
            )
            return MetricResult(
                name=self.name,
                value=value,
                display=display,
                details={"jsd_per_column": jsd_scores, "has_baseline": has_baseline},
            )
        except Exception as exc:
            return MetricResult(
                name=self.name,
                value=None,
                display=f"n/a (DB error: {exc})",
            )


class ArgumentValueDiversity(Metric):
    """
    Mean normalized entropy over argument values per (tool, argument) slot.

    Formula:
        For each distinct (tool_name, arg_name) slot across all steps:
            counts(v) = number of times value v was passed for that slot
            H_norm(slot) = H(counts) / log(|distinct values|)

        argument_value_diversity = mean(H_norm) over all (tool, arg) slots
            (only slots with ≥ 2 distinct values contribute)

    Interpretation:
        - 1.0  → every argument slot receives all its values with equal frequency
        - 0.0  → every argument slot always receives the same value (degenerate)
        - 0.4–0.7 → healthy range; agent varies arguments reasonably
        - Low values indicate the agent is using formulaic arguments rather than
          exploring the space of valid input combinations

    Reference:
        Inspired by: UniToolCall (arXiv:2604.11557) — diverse parameter values
        in tool invocations as a quality signal for agentic interaction datasets.
    """

    @property
    def name(self) -> str:
        return "argument_value_diversity"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        # Collect per-(tool, arg) value counts
        slot_counts: dict[tuple[str, str], Counter] = defaultdict(Counter)

        for r in records:
            for s in r.input.steps:
                for arg_name, arg_val in s.args.items():
                    # Use string representation as the value key
                    slot_counts[(s.tool, arg_name)][str(arg_val)] += 1

        if not slot_counts:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (no tool arguments found)",
            )

        entropies = []
        per_slot: dict[str, float] = {}

        for (tool, arg), counter in slot_counts.items():
            n_distinct = len(counter)
            if n_distinct < 2:
                continue  # Skip slots that never vary
            h_norm = normalized_entropy(counter)
            entropies.append(h_norm)
            per_slot[f"{tool}.{arg}"] = round(h_norm, 4)

        if not entropies:
            return MetricResult(
                name=self.name,
                value=0.0,
                display="0.000 (all argument slots constant)",
                details={"varying_slots": 0},
            )

        value = statistics.mean(entropies)
        display = f"{value:.3f} mean H_norm over {len(entropies)} varying (tool, arg) slots"
        # Show only top/bottom 5 by entropy to keep details manageable
        sorted_slots = sorted(per_slot.items(), key=lambda x: x[1], reverse=True)
        top5 = dict(sorted_slots[:5])
        bottom5 = dict(sorted_slots[-5:]) if len(sorted_slots) > 5 else {}

        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details={
                "varying_slots": len(entropies),
                "total_slots": len(slot_counts),
                "top5_diverse": top5,
                "bottom5_diverse": bottom5,
            },
        )
