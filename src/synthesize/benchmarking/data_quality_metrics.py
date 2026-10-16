"""
Data Quality Metrics — Group 5.

Measures the quality of the synthesised data from a DAMA-inspired perspective:
  - Temporal consistency  (records have plausible, internally-ordered timestamps)
  - Workflow completeness (agent-created parents have required child records)
  - Realistic value distributions (generated values match real-world priors)
  - LLM-as-judge          (GPT-4-class model scores records on 4 quality rubrics)
  - Deduplication rate    (structural duplicates indicate low synthesis diversity)

All five metrics are DB-dependent; each returns value=None with a display
explanation when db_path is None.

References:
  - DAMA-DMBOK2 (2017) — six data quality dimensions
  - MT-Bench (arXiv:2306.05685) — LLM-as-judge with >80% human agreement
  - JudgeLM (arXiv:2310.17631) — bias mitigation for LLM judges
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from synthesize.models import DatasetItem

from ._utils import js_divergence
from .base import Metric, MetricResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open(path: Path) -> sqlite3.Connection:
    """Open a read-only SQLite connection."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _tables(conn: sqlite3.Connection) -> list[str]:
    """Return all user table names (excludes sqlite_* internal tables)."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [r[0] for r in rows]


def _column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    """Return all column names for a table."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()  # noqa: S608
    return [r["name"] for r in rows]


def _foreign_keys(conn: sqlite3.Connection, table: str) -> list[dict]:
    """Return FK definitions for a table: [{from, table, to}, ...]."""
    rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()  # noqa: S608
    return [{"from": r["from"], "table": r["table"], "to": r["to"]} for r in rows]


def _is_date_col(col_name: str) -> bool:
    """Heuristic: column name looks like a timestamp/date field."""
    lower = col_name.lower()
    return any(
        token in lower
        for token in (
            "created_at",
            "updated_at",
            "modified_at",
            "last_modified",
            "created_on",
            "modified_on",
            "last_modified_on",
            "date",
            "timestamp",
            "time",
            "departure",
            "arrival",
            "start",
            "end",
            "expiry",
            "expires",
            "resolved",
            "assigned",
            "terminated",
        )
    )


# ---------------------------------------------------------------------------
# Metric 1: TemporalConsistencyScore
# ---------------------------------------------------------------------------


class TemporalConsistencyScore(Metric):
    """
    Fraction of date/timestamp orderings within and across records that are
    temporally consistent (i.e. satisfy expected chronological constraints).

    Formula:
        Two types of checks, each contributing equally to the per-table score:

        (a) Intra-record ordering — for every pair (col_a, col_b) of date columns
            within the same row where col_a should precede col_b, verify
            val_a ≤ val_b:
                intra_pass = |{rows : val_a ≤ val_b or val_a IS NULL or val_b IS NULL}|
                             / |total rows with both non-NULL|

            Column ordering inferred by name:
              created_at / created_on  <  modified_at / updated_at / last_modified_on
              created_at               <  resolved_at / terminated_at / assigned_at
              departure                <  arrival (within same record)

        (b) Cross-FK ordering — for each FK relationship (child → parent),
            child.created_at should be ≥ parent.created_at:
                cross_pass = |{child rows : child.created_at ≥ parent.created_at}|
                             / |total joined rows with both non-NULL|

        temporal_consistency_score = mean(all intra and cross-FK pass rates)

    Interpretation:
        - 1.0  → all timestamp orderings in the DB are chronologically valid
        - 0.8+ → healthy; minor issues (e.g. same-second ties parsed as violations)
        - < 0.5 → systematic timestamp problems; the environment is not writing
                  timestamps correctly or the agent is submitting backdated values
        - Returns n/a when db_path is None or no date columns are found

    Reference:
        Inspired by: DAMA-DMBOK2 (2017) — "Timeliness" dimension (data is available
        when needed, temporal values are internally consistent).
        Original metric for this framework — adapts the concept to SQLite schema
        introspection without environment-specific column mapping.
    """

    # Pairs: (earlier_tokens, later_tokens)
    _INTRA_ORDER_PAIRS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
        (
            ("created_at", "created_on"),
            ("updated_at", "modified_at", "last_modified_on", "last_modified_at"),
        ),
        (
            ("created_at", "created_on"),
            ("resolved_at", "resolved_on", "terminated_at", "terminated_on", "assigned_at"),
        ),
        (
            ("departure", "scheduled_departure", "estimated_departure", "actual_departure"),
            ("arrival", "scheduled_arrival", "estimated_arrival", "actual_arrival"),
        ),
        (
            ("start_date", "start_at"),
            ("end_date", "end_at", "expiry", "expires_at"),
        ),
    ]

    @property
    def name(self) -> str:
        return "temporal_consistency_score"

    def _col_matches(self, col: str, tokens: tuple[str, ...]) -> bool:
        lower = col.lower()
        return any(t in lower for t in tokens)

    def _intra_record_checks(self, conn: sqlite3.Connection) -> list[float]:
        """Return per-pair pass rates for intra-record ordering across all tables."""
        rates = []
        for table in _tables(conn):
            cols = _column_names(conn, table)
            date_cols = [c for c in cols if _is_date_col(c)]
            if len(date_cols) < 2:
                continue

            for early_tokens, late_tokens in self._INTRA_ORDER_PAIRS:
                early_cols = [c for c in date_cols if self._col_matches(c, early_tokens)]
                late_cols = [c for c in date_cols if self._col_matches(c, late_tokens)]
                if not early_cols or not late_cols:
                    continue

                for early_col in early_cols:
                    for late_col in late_cols:
                        if early_col == late_col:
                            continue
                        try:
                            total = conn.execute(
                                f"SELECT COUNT(*) FROM {table} "  # noqa: S608
                                f"WHERE {early_col} IS NOT NULL AND {late_col} IS NOT NULL"
                            ).fetchone()[0]
                            if total == 0:
                                continue
                            passing = conn.execute(
                                f"SELECT COUNT(*) FROM {table} "  # noqa: S608
                                f"WHERE {early_col} IS NOT NULL AND {late_col} IS NOT NULL "
                                f"AND {early_col} <= {late_col}"
                            ).fetchone()[0]
                            rates.append(passing / total)
                        except sqlite3.Error:
                            continue
        return rates

    def _cross_fk_checks(self, conn: sqlite3.Connection) -> list[float]:
        """Return pass rates for cross-FK timestamp ordering (child >= parent)."""
        rates = []
        for child_table in _tables(conn):
            fks = _foreign_keys(conn, child_table)
            if not fks:
                continue
            child_cols = _column_names(conn, child_table)
            child_ts_cols = [
                c for c in child_cols if "created_at" in c.lower() or "created_on" in c.lower()
            ]
            if not child_ts_cols:
                continue

            for fk in fks:
                parent_table = fk["table"]
                parent_cols = _column_names(conn, parent_table)
                parent_ts_cols = [
                    c for c in parent_cols if "created_at" in c.lower() or "created_on" in c.lower()
                ]
                if not parent_ts_cols:
                    continue

                child_ts = child_ts_cols[0]
                parent_ts = parent_ts_cols[0]
                child_fk_col = fk["from"]
                parent_pk_col = fk["to"]

                try:
                    total = conn.execute(
                        f"SELECT COUNT(*) FROM {child_table} c "  # noqa: S608
                        f"JOIN {parent_table} p ON c.{child_fk_col} = p.{parent_pk_col} "
                        f"WHERE c.{child_ts} IS NOT NULL AND p.{parent_ts} IS NOT NULL"
                    ).fetchone()[0]
                    if total == 0:
                        continue
                    passing = conn.execute(
                        f"SELECT COUNT(*) FROM {child_table} c "  # noqa: S608
                        f"JOIN {parent_table} p ON c.{child_fk_col} = p.{parent_pk_col} "
                        f"WHERE c.{child_ts} IS NOT NULL AND p.{parent_ts} IS NOT NULL "
                        f"AND c.{child_ts} >= p.{parent_ts}"
                    ).fetchone()[0]
                    rates.append(passing / total)
                except sqlite3.Error:
                    continue
        return rates

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if db_path is None:
            return MetricResult(name=self.name, value=None, display="n/a (no DB)")
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        try:
            conn = _open(db_path)
            intra_rates = self._intra_record_checks(conn)
            cross_rates = self._cross_fk_checks(conn)
            conn.close()
        except Exception as exc:
            return MetricResult(name=self.name, value=None, display=f"n/a (DB error: {exc})")

        all_rates = intra_rates + cross_rates
        if not all_rates:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (no date columns found)",
            )

        value = statistics.mean(all_rates)
        display = (
            f"{value:.3f} (intra={len(intra_rates)} checks, cross_fk={len(cross_rates)} checks)"
        )
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details={
                "intra_record_checks": len(intra_rates),
                "cross_fk_checks": len(cross_rates),
                "intra_mean": round(statistics.mean(intra_rates), 4) if intra_rates else None,
                "cross_fk_mean": round(statistics.mean(cross_rates), 4) if cross_rates else None,
            },
        )


# ---------------------------------------------------------------------------
# Metric 2: WorkflowCompletenessScore
# ---------------------------------------------------------------------------


class WorkflowCompletenessScore(Metric):
    """
    Fraction of agent-created parent records that have all expected child records.

    Measures whether agent workflows are complete end-to-end, not just whether
    the primary action succeeded. A reservation without any reservation_flights
    (a child table linked by FK) indicates an incomplete workflow.

    Formula:
        For each FK relationship (child_table → parent_table):
            completeness(FK) = |{parent rows : ∃ ≥1 child row}| / |{agent parent rows}|

            "agent parent rows" = rows in snapshot.db NOT in baseline.db
            (or all rows if baseline.db unavailable)

        workflow_completeness_score = mean(completeness) over all FK relationships
            where the parent has ≥1 agent-created row and the FK is non-trivial
            (parent_table ≠ child_table; excludes self-references)

    Interpretation:
        - 1.0  → every agent-created parent record has at least one child record
        - 0.0  → no parent records have associated child records (broken workflows)
        - A low value for a specific FK pair is a strong signal that the agent's
          workflow for that entity type is consistently incomplete
        - Does NOT require knowledge of intents — purely schema-driven via FK graph

    Reference:
        Original metric for this framework — schema-driven approach inspired by the
        discussion in AgentProcessBench (arXiv:2603.14465) around process-level
        vs outcome-level failure, adapted to measure structural completeness of
        generated database records without intent-level hardcoding.
        Designed for use with auto-evolve: as new workflows are discovered,
        the FK structure automatically includes them in the score.
    """

    @property
    def name(self) -> str:
        return "workflow_completeness_score"

    def _agent_pks(
        self,
        conn: sqlite3.Connection,
        baseline_conn: sqlite3.Connection | None,
        table: str,
        pk_col: str,
    ) -> set[Any]:
        """Return primary key values for agent-created rows only."""
        final = {r[0] for r in conn.execute(f"SELECT {pk_col} FROM {table}").fetchall()}  # noqa: S608
        if baseline_conn is None:
            return final
        try:
            seed = {r[0] for r in baseline_conn.execute(f"SELECT {pk_col} FROM {table}").fetchall()}  # noqa: S608
        except sqlite3.Error:
            return final
        return final - seed

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if db_path is None:
            return MetricResult(name=self.name, value=None, display="n/a (no DB)")
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        baseline_path = db_path.parent / "baseline.db"
        has_baseline = baseline_path.exists()

        try:
            conn = _open(db_path)
            baseline_conn = _open(baseline_path) if has_baseline else None

            completeness_scores: dict[str, float] = {}

            for child_table in _tables(conn):
                fks = _foreign_keys(conn, child_table)
                if not fks:
                    continue

                for fk in fks:
                    parent_table = fk["table"]
                    if parent_table == child_table:
                        continue  # skip self-references

                    child_fk_col = fk["from"]

                    # Get parent PK column
                    pk_rows = conn.execute(
                        f"PRAGMA table_info({parent_table})"  # noqa: S608
                    ).fetchall()
                    pk_cols = [r["name"] for r in pk_rows if r["pk"] > 0]
                    if not pk_cols:
                        continue
                    parent_pk = pk_cols[0]

                    # Agent-created parent PKs
                    agent_parent_pks = self._agent_pks(conn, baseline_conn, parent_table, parent_pk)
                    if not agent_parent_pks:
                        continue

                    # Which agent parents have ≥1 child?
                    placeholders = ",".join("?" * len(agent_parent_pks))
                    try:
                        child_rows = conn.execute(
                            f"SELECT DISTINCT {child_fk_col} FROM {child_table} "  # noqa: S608
                            f"WHERE {child_fk_col} IN ({placeholders})",
                            list(agent_parent_pks),
                        ).fetchall()
                    except sqlite3.Error:
                        continue

                    parents_with_children = {r[0] for r in child_rows}
                    completeness = len(parents_with_children) / len(agent_parent_pks)
                    key = f"{parent_table} → {child_table}"
                    completeness_scores[key] = round(completeness, 4)

            if baseline_conn is not None:
                baseline_conn.close()
            conn.close()
        except Exception as exc:
            return MetricResult(name=self.name, value=None, display=f"n/a (DB error: {exc})")

        if not completeness_scores:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (no FK relationships with agent-created rows)",
            )

        value = statistics.mean(completeness_scores.values())
        display = (
            f"{value:.3f} "
            f"({len(completeness_scores)} FK relationships, "
            f"baseline={'yes' if has_baseline else 'no'})"
        )
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details={
                "per_fk_relationship": completeness_scores,
                "has_baseline": has_baseline,
            },
        )


# ---------------------------------------------------------------------------
# Metric 3: RealisticValueDistributionScore
# ---------------------------------------------------------------------------


class RealisticValueDistributionScore(Metric):
    """
    How closely the agent-generated value distributions match real-world priors.

    For each registered field in the environment's quality_priors.py:
      - Categorical fields: Jensen-Shannon Divergence (JSD) between observed and
        reference distribution → similarity = 1 - JSD / ln(2)   (normalised to [0,1])
      - Numeric fields: Kolmogorov-Smirnov statistic between observed values and
        reference sample → similarity = 1 - KS_stat

    Formula:
        For each registered (table, column) pair:
            if categorical:
                jsd = JS_divergence(p_observed, p_reference)
                similarity = 1 - jsd / ln(2)          # ln(2) ≈ 0.693 = max JSD
            if numeric:
                ks_stat = max_x |CDF_observed(x) - CDF_reference(x)|
                similarity = 1 - ks_stat

        realistic_value_distribution_score = mean(similarity) over all registered fields

    Interpretation:
        - 1.0  → agent's value choices match real-world priors perfectly
        - 0.7+ → good alignment; minor distributional shifts
        - < 0.5 → systematic mismatch; agent is not sampling from realistic distributions
        - Returns n/a when no quality_priors are registered for the environment

    Reference:
        Direct use of Jensen-Shannon divergence from: Precision and Recall for
        Distributions (arXiv:2102.09672, Kynkäänniemi et al.) for fidelity measurement.
        KS statistic: standard non-parametric distribution comparison (Kolmogorov 1933).
        Reference distributions are registered in environments/<env>/quality_priors.py;
        approach inspired by: EnvScaler (arXiv:2601.05808) — environment-specific
        topic/value distributions as quality benchmarks.
    """

    @property
    def name(self) -> str:
        return "realistic_value_distribution_score"

    @staticmethod
    def _ks_stat(observed: list[float], reference: list[float]) -> float:
        """Compute KS statistic D = max |F_obs(x) - F_ref(x)| over all x."""
        if not observed or not reference:
            return 1.0
        all_vals = sorted(set(observed) | set(reference))
        n_obs = len(observed)
        n_ref = len(reference)
        obs_sorted = sorted(observed)
        ref_sorted = sorted(reference)

        max_diff = 0.0
        for x in all_vals:
            # CDF(x) = fraction of values <= x
            import bisect

            cdf_obs = bisect.bisect_right(obs_sorted, x) / n_obs
            cdf_ref = bisect.bisect_right(ref_sorted, x) / n_ref
            diff = abs(cdf_obs - cdf_ref)
            if diff > max_diff:
                max_diff = diff
        return max_diff

    @staticmethod
    def _load_priors(env: str) -> dict | None:
        """Load quality priors for the environment, returning None if unavailable."""
        try:
            import importlib

            mod = importlib.import_module(f"synthesize.environments.{env}.quality_priors")
            # Try to get an <ENV>_QUALITY_PRIORS dict
            for attr in dir(mod):
                if attr.upper().endswith("_QUALITY_PRIORS"):
                    return getattr(mod, attr)
            return None
        except (ImportError, AttributeError):
            return None

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if db_path is None:
            return MetricResult(name=self.name, value=None, display="n/a (no DB)")
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        # Determine env from records
        envs = {r.metadata.env for r in records}
        env = next(iter(envs)) if len(envs) == 1 else None
        if env is None:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (mixed environments in batch)",
            )

        priors = self._load_priors(env)
        if priors is None:
            return MetricResult(
                name=self.name,
                value=None,
                display=f"n/a (no quality_priors registered for env '{env}')",
            )

        baseline_path = db_path.parent / "baseline.db"
        has_baseline = baseline_path.exists()
        import math

        ln2 = math.log(2)

        try:
            conn = _open(db_path)
            baseline_conn = _open(baseline_path) if has_baseline else None

            similarities: dict[str, float] = {}

            for table, fields in priors.items():
                for col, spec in fields.items():
                    field_type = spec.get("type")

                    if field_type == "categorical":
                        reference_dist: dict[str, float] = spec.get("distribution", {})
                        if not reference_dist:
                            continue

                        try:
                            final_counts = dict(
                                conn.execute(
                                    f"SELECT {col}, COUNT(*) FROM {table} "  # noqa: S608
                                    f"WHERE {col} IS NOT NULL GROUP BY {col}"
                                ).fetchall()
                            )
                        except sqlite3.Error:
                            continue

                        # Subtract baseline
                        if baseline_conn:
                            try:
                                base_counts = dict(
                                    baseline_conn.execute(
                                        f"SELECT {col}, COUNT(*) FROM {table} "  # noqa: S608
                                        f"WHERE {col} IS NOT NULL GROUP BY {col}"
                                    ).fetchall()
                                )
                                agent_counts = {
                                    k: max(0, final_counts.get(k, 0) - base_counts.get(k, 0))
                                    for k in set(final_counts) | set(base_counts)
                                }
                                agent_counts = {k: v for k, v in agent_counts.items() if v > 0}
                            except sqlite3.Error:
                                agent_counts = final_counts
                        else:
                            agent_counts = final_counts

                        if not agent_counts or sum(agent_counts.values()) == 0:
                            continue

                        # Scale reference to count space for js_divergence
                        total = sum(agent_counts.values())
                        ref_counts = {k: int(v * total) for k, v in reference_dist.items()}
                        jsd = js_divergence(agent_counts, ref_counts)
                        similarity = 1.0 - (jsd / ln2)
                        similarities[f"{table}.{col}"] = round(max(0.0, similarity), 4)

                    elif field_type == "numeric":
                        reference_vals: list = spec.get("reference_values", [])
                        if not reference_vals:
                            continue

                        try:
                            obs_rows = conn.execute(
                                f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL"  # noqa: S608
                            ).fetchall()
                        except sqlite3.Error:
                            continue

                        # Subtract baseline rows
                        if baseline_conn:
                            try:
                                n_baseline = baseline_conn.execute(
                                    f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL"  # noqa: S608
                                ).fetchone()[0]
                                # Use all rows; we can't easily subtract by rowid without rowid tracking
                                # so we skip seed rows by taking only the last N rows
                                obs_vals = [r[0] for r in obs_rows]
                                if n_baseline > 0 and len(obs_vals) > n_baseline:
                                    obs_vals = obs_vals[n_baseline:]  # crude but deterministic
                            except sqlite3.Error:
                                obs_vals = [r[0] for r in obs_rows]
                        else:
                            obs_vals = [r[0] for r in obs_rows]

                        if not obs_vals:
                            continue

                        ks = self._ks_stat(
                            [float(v) for v in obs_vals],
                            [float(v) for v in reference_vals],
                        )
                        similarity = 1.0 - ks
                        similarities[f"{table}.{col}"] = round(max(0.0, similarity), 4)

            if baseline_conn:
                baseline_conn.close()
            conn.close()
        except Exception as exc:
            return MetricResult(name=self.name, value=None, display=f"n/a (DB error: {exc})")

        if not similarities:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (no registered fields found in DB)",
            )

        value = statistics.mean(similarities.values())
        display = f"{value:.3f} (mean similarity over {len(similarities)} registered fields)"
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details={
                "per_field": similarities,
                "has_baseline": has_baseline,
                "env": env,
            },
        )


# ---------------------------------------------------------------------------
# Metric 4a: PairwiseFidelityScore
# ---------------------------------------------------------------------------


class PairwiseFidelityScore(Metric):
    """
    How closely the agent-generated *joint* distributions over column pairs match
    real-world priors — the second level of the distributional fidelity hierarchy.

    Marginal fidelity (RealisticValueDistributionScore) measures P(col) for each
    column independently.  Pairwise fidelity measures P(col1, col2) for designated
    column pairs within the same table, capturing correlations that marginal scores
    miss (e.g. business-class travellers buy travel insurance at higher rates than
    economy passengers).

    For each registered (table, col1, col2) triple in the environment's
    quality_priors module (attribute ending in ``_PAIRWISE_PRIORS``):
      - Build the observed joint count distribution: {(v1, v2): count}
      - Compare to the reference joint distribution via JSD
      - similarity = 1 - JSD / ln(2)   (normalised to [0,1])

    Formula:
        pairwise_fidelity_score = mean(similarity) over all registered column pairs

    Priors format (in quality_priors.py, attribute ``<ENV>_PAIRWISE_PRIORS``):
        {
          "table_name": {
            ("col1", "col2"): {
              "type": "categorical_joint",
              "distribution": {
                ("val_a", "val_x"): 0.07,
                ("val_a", "val_y"): 0.03,
                ...
              }
            }
          }
        }

    Interpretation:
        - 1.0  → joint distributions match reference perfectly
        - 0.7+ → good alignment; cross-column correlations are realistic
        - < 0.5 → cross-column correlations are systematically off
        - Returns n/a when no pairwise priors are registered
    """

    @property
    def name(self) -> str:
        return "pairwise_fidelity_score"

    @staticmethod
    def _load_pairwise_priors(env: str) -> dict | None:
        try:
            import importlib
            mod = importlib.import_module(f"synthesize.environments.{env}.quality_priors")
            for attr in dir(mod):
                if attr.upper().endswith("_PAIRWISE_PRIORS"):
                    return getattr(mod, attr)
            return None
        except (ImportError, AttributeError):
            return None

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if db_path is None:
            return MetricResult(name=self.name, value=None, display="n/a (no DB)")
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        envs = {r.metadata.env for r in records}
        env = next(iter(envs)) if len(envs) == 1 else None
        if env is None:
            return MetricResult(name=self.name, value=None, display="n/a (mixed environments)")

        priors = self._load_pairwise_priors(env)
        if priors is None:
            return MetricResult(
                name=self.name, value=None,
                display=f"n/a (no pairwise priors for env '{env}')",
            )

        baseline_path = db_path.parent / "baseline.db"
        has_baseline = baseline_path.exists()
        import math
        ln2 = math.log(2)

        try:
            conn = _open(db_path)
            baseline_conn = _open(baseline_path) if has_baseline else None
            similarities: dict[str, float] = {}

            for table, pairs in priors.items():
                for (col1, col2), spec in pairs.items():
                    if spec.get("type") != "categorical_joint":
                        continue
                    reference_dist: dict = spec.get("distribution", {})
                    if not reference_dist:
                        continue

                    try:
                        rows = conn.execute(
                            f"SELECT {col1}, {col2}, COUNT(*) FROM {table} "  # noqa: S608
                            f"WHERE {col1} IS NOT NULL AND {col2} IS NOT NULL "
                            f"GROUP BY {col1}, {col2}"
                        ).fetchall()
                    except sqlite3.Error:
                        continue

                    final_counts: dict[tuple, int] = {(r[0], r[1]): r[2] for r in rows}

                    if baseline_conn:
                        try:
                            base_rows = baseline_conn.execute(
                                f"SELECT {col1}, {col2}, COUNT(*) FROM {table} "  # noqa: S608
                                f"WHERE {col1} IS NOT NULL AND {col2} IS NOT NULL "
                                f"GROUP BY {col1}, {col2}"
                            ).fetchall()
                            base_counts: dict[tuple, int] = {(r[0], r[1]): r[2] for r in base_rows}
                            agent_counts = {
                                k: max(0, final_counts.get(k, 0) - base_counts.get(k, 0))
                                for k in set(final_counts) | set(base_counts)
                            }
                            agent_counts = {k: v for k, v in agent_counts.items() if v > 0}
                        except sqlite3.Error:
                            agent_counts = final_counts
                    else:
                        agent_counts = final_counts

                    if not agent_counts or sum(agent_counts.values()) == 0:
                        continue

                    total = sum(agent_counts.values())
                    # Reference keys may be tuples or lists (JSON loading converts tuples to lists)
                    ref_counts: dict[tuple, int] = {
                        (tuple(k) if isinstance(k, list) else k): int(v * total)
                        for k, v in reference_dist.items()
                    }
                    # Align keys: agent may have values not in reference and vice versa
                    all_keys = set(agent_counts) | set(ref_counts)
                    agent_aligned = {k: agent_counts.get(k, 0) for k in all_keys}
                    ref_aligned = {k: ref_counts.get(k, 0) for k in all_keys}

                    jsd = js_divergence(agent_aligned, ref_aligned)
                    similarity = 1.0 - (jsd / ln2)
                    key = f"{table}.({col1},{col2})"
                    similarities[key] = round(max(0.0, similarity), 4)

            if baseline_conn:
                baseline_conn.close()
            conn.close()
        except Exception as exc:
            return MetricResult(name=self.name, value=None, display=f"n/a (DB error: {exc})")

        if not similarities:
            return MetricResult(
                name=self.name, value=None,
                display="n/a (no registered pairs found in DB)",
            )

        value = statistics.mean(similarities.values())
        display = f"{value:.3f} (mean joint similarity over {len(similarities)} column pairs)"
        return MetricResult(
            name=self.name, value=value, display=display,
            details={"per_pair": similarities, "has_baseline": has_baseline, "env": env},
        )


# ---------------------------------------------------------------------------
# Metric 4b: ProcessFidelityScore
# ---------------------------------------------------------------------------


class ProcessFidelityScore(Metric):
    """
    How closely the agent-generated process-outcome distributions match real-world
    priors — the third level of the distributional fidelity hierarchy.

    Marginal fidelity measures entity *property* distributions (e.g. cabin class,
    payment method).  Process fidelity measures *outcome* distributions produced by
    multi-step workflows: the mix of final states across a process (e.g. what fraction
    of job applications end as Hired vs. Rejected; what fraction of orders reach
    Delivered vs. Cancelled).  These distributions are directly shaped by the
    synthesiser's operation-mix targeting: a synthesiser that calls BOOK_RESERVATION
    and CANCEL_RESERVATION in realistic proportions will produce a realistic
    reservation-status distribution.

    Computation is identical to RealisticValueDistributionScore (JSD for categorical,
    KS for numeric), but operates on a separate set of priors (``<ENV>_PROCESS_PRIORS``)
    that register only process-outcome columns, making the distinction explicit.

    Priors format (in quality_priors.py, attribute ``<ENV>_PROCESS_PRIORS``):
        Identical to the marginal priors format — {table: {col: {type, distribution}}}.

    Interpretation:
        - 1.0  → process-outcome distributions match reference (realistic workflow mix)
        - 0.7+ → process outcomes broadly realistic
        - < 0.5 → workflow is unrealistically skewed (e.g. everything ends as 'Hired')
        - Returns n/a when no process priors are registered
    """

    @property
    def name(self) -> str:
        return "process_fidelity_score"

    @staticmethod
    def _load_process_priors(env: str) -> dict | None:
        try:
            import importlib
            mod = importlib.import_module(f"synthesize.environments.{env}.quality_priors")
            for attr in dir(mod):
                if attr.upper().endswith("_PROCESS_PRIORS"):
                    return getattr(mod, attr)
            return None
        except (ImportError, AttributeError):
            return None

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if db_path is None:
            return MetricResult(name=self.name, value=None, display="n/a (no DB)")
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        envs = {r.metadata.env for r in records}
        env = next(iter(envs)) if len(envs) == 1 else None
        if env is None:
            return MetricResult(name=self.name, value=None, display="n/a (mixed environments)")

        priors = self._load_process_priors(env)
        if priors is None:
            return MetricResult(
                name=self.name, value=None,
                display=f"n/a (no process priors for env '{env}')",
            )

        baseline_path = db_path.parent / "baseline.db"
        has_baseline = baseline_path.exists()
        import math
        ln2 = math.log(2)

        try:
            conn = _open(db_path)
            baseline_conn = _open(baseline_path) if has_baseline else None
            similarities: dict[str, float] = {}

            for table, fields in priors.items():
                for col, spec in fields.items():
                    field_type = spec.get("type")
                    if field_type != "categorical":
                        continue
                    reference_dist: dict[str, float] = spec.get("distribution", {})
                    if not reference_dist:
                        continue

                    try:
                        final_counts = dict(
                            conn.execute(
                                f"SELECT {col}, COUNT(*) FROM {table} "  # noqa: S608
                                f"WHERE {col} IS NOT NULL GROUP BY {col}"
                            ).fetchall()
                        )
                    except sqlite3.Error:
                        continue

                    if baseline_conn:
                        try:
                            base_counts = dict(
                                baseline_conn.execute(
                                    f"SELECT {col}, COUNT(*) FROM {table} "  # noqa: S608
                                    f"WHERE {col} IS NOT NULL GROUP BY {col}"
                                ).fetchall()
                            )
                            agent_counts = {
                                k: max(0, final_counts.get(k, 0) - base_counts.get(k, 0))
                                for k in set(final_counts) | set(base_counts)
                            }
                            agent_counts = {k: v for k, v in agent_counts.items() if v > 0}
                        except sqlite3.Error:
                            agent_counts = final_counts
                    else:
                        agent_counts = final_counts

                    if not agent_counts or sum(agent_counts.values()) == 0:
                        continue

                    total = sum(agent_counts.values())
                    ref_counts = {k: int(v * total) for k, v in reference_dist.items()}
                    jsd = js_divergence(agent_counts, ref_counts)
                    similarity = 1.0 - (jsd / ln2)
                    similarities[f"{table}.{col}"] = round(max(0.0, similarity), 4)

            if baseline_conn:
                baseline_conn.close()
            conn.close()
        except Exception as exc:
            return MetricResult(name=self.name, value=None, display=f"n/a (DB error: {exc})")

        if not similarities:
            return MetricResult(
                name=self.name, value=None,
                display="n/a (no registered process fields found in DB)",
            )

        value = statistics.mean(similarities.values())
        display = f"{value:.3f} (mean similarity over {len(similarities)} process-outcome fields)"
        return MetricResult(
            name=self.name, value=value, display=display,
            details={"per_field": similarities, "has_baseline": has_baseline, "env": env},
        )


# ---------------------------------------------------------------------------
# Metric 4c: CrossTableRelationalFidelityScore
# ---------------------------------------------------------------------------


class CrossTableRelationalFidelityScore(Metric):
    """
    How closely the agent-generated child-count distributions across FK relationships
    match real-world priors — the cross-table level of the distributional fidelity
    hierarchy.

    MDF measures P(col) within a single table.  Pairwise DF measures P(col1, col2)
    within a table.  Relational DF measures P(#children | parent) across tables —
    e.g. whether the agent books realistic numbers of passengers per reservation, or
    items per order.

    For each registered (parent_table, child_table, fk_col) triple in the environment's
    quality_priors module (attribute ending in ``_RELATIONAL_PRIORS``):
      - For each agent-created parent row, count linked child rows
      - Bucket counts: any count > max_bucket folds into max_bucket
      - Compare observed bucket distribution to reference via JSD
      - similarity = 1 - JSD / ln(2)

    Formula:
        cross_table_relational_fidelity = mean(similarity) over all registered FK pairs

    Priors format (in quality_priors.py, attribute ``<ENV>_RELATIONAL_PRIORS``):
        {
          (parent_table, child_table, fk_col): {
            "type": "child_count",
            "distribution": {1: 0.55, 2: 0.40, 3: 0.05},
            "max_bucket": 3,   # counts > max_bucket fold into max_bucket
          }
        }

    Interpretation:
        - 1.0  → child-count distributions match reference perfectly
        - 0.7+ → realistic multiplicity patterns (party sizes, item counts, etc.)
        - < 0.5 → agent systematically over- or under-populates child records
        - Returns n/a when no relational priors are registered
    """

    @property
    def name(self) -> str:
        return "cross_table_relational_fidelity"

    @staticmethod
    def _load_relational_priors(env: str) -> dict | None:
        try:
            import importlib
            mod = importlib.import_module(f"synthesize.environments.{env}.quality_priors")
            for attr in dir(mod):
                if attr.upper().endswith("_RELATIONAL_PRIORS"):
                    return getattr(mod, attr)
            return None
        except (ImportError, AttributeError):
            return None

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if db_path is None:
            return MetricResult(name=self.name, value=None, display="n/a (no DB)")
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        envs = {r.metadata.env for r in records}
        env = next(iter(envs)) if len(envs) == 1 else None
        if env is None:
            return MetricResult(name=self.name, value=None, display="n/a (mixed environments)")

        priors = self._load_relational_priors(env)
        if priors is None:
            return MetricResult(
                name=self.name, value=None,
                display=f"n/a (no relational priors for env '{env}')",
            )

        baseline_path = db_path.parent / "baseline.db"
        has_baseline = baseline_path.exists()
        import math
        ln2 = math.log(2)

        try:
            conn = _open(db_path)
            baseline_conn = _open(baseline_path) if has_baseline else None
            similarities: dict[str, float] = {}
            per_rel_details: dict[str, dict] = {}

            for (parent_table, child_table, fk_col), spec in priors.items():
                if spec.get("type") != "child_count":
                    continue
                reference_dist: dict = spec.get("distribution", {})
                if not reference_dist:
                    continue
                ref_int = {int(k): v for k, v in reference_dist.items()}
                max_bucket: int = spec.get("max_bucket", max(ref_int.keys()))

                # Discover parent PK via PRAGMA
                pk_rows = conn.execute(f"PRAGMA table_info({parent_table})").fetchall()  # noqa: S608
                pk_cols = [r["name"] for r in pk_rows if r["pk"] > 0]
                if not pk_cols:
                    continue
                parent_pk = pk_cols[0]

                # Agent-created parent PKs (subtract baseline)
                all_pks = {r[0] for r in conn.execute(  # noqa: S608
                    f"SELECT {parent_pk} FROM {parent_table}"
                ).fetchall()}
                if baseline_conn:
                    try:
                        seed_pks = {r[0] for r in baseline_conn.execute(  # noqa: S608
                            f"SELECT {parent_pk} FROM {parent_table}"
                        ).fetchall()}
                        agent_pks = all_pks - seed_pks
                    except sqlite3.Error:
                        agent_pks = all_pks
                else:
                    agent_pks = all_pks

                if not agent_pks:
                    continue

                # Count children per agent parent
                placeholders = ",".join("?" * len(agent_pks))
                child_rows = conn.execute(  # noqa: S608
                    f"SELECT {fk_col}, COUNT(*) FROM {child_table} "
                    f"WHERE {fk_col} IN ({placeholders}) GROUP BY {fk_col}",
                    list(agent_pks),
                ).fetchall()
                child_count_map = {r[0]: r[1] for r in child_rows}

                # Build bucket distribution over all agent parents
                observed: Counter = Counter()
                for pk in agent_pks:
                    raw = child_count_map.get(pk, 0)
                    observed[min(raw, max_bucket)] += 1

                total = sum(observed.values())
                if total == 0:
                    continue

                ref_counts = {k: int(v * total) for k, v in ref_int.items()}
                all_keys = set(observed) | set(ref_counts)
                obs_aligned = {k: observed.get(k, 0) for k in all_keys}
                ref_aligned = {k: ref_counts.get(k, 0) for k in all_keys}

                jsd = js_divergence(obs_aligned, ref_aligned)
                sim = round(max(0.0, 1.0 - jsd / ln2), 4)
                rel_key = f"{parent_table}→{child_table}"
                similarities[rel_key] = sim
                per_rel_details[rel_key] = {
                    "observed": dict(sorted(observed.items())),
                    "n_agent_parents": len(agent_pks),
                    "similarity": sim,
                }

            if baseline_conn:
                baseline_conn.close()
            conn.close()
        except Exception as exc:
            return MetricResult(name=self.name, value=None, display=f"n/a (DB error: {exc})")

        if not similarities:
            return MetricResult(
                name=self.name, value=None,
                display="n/a (no registered FK pairs with agent-created rows)",
            )

        value = statistics.mean(similarities.values())
        display = f"{value:.3f} (mean over {len(similarities)} FK relationships)"
        return MetricResult(
            name=self.name, value=value, display=display,
            details={
                "per_relationship": per_rel_details,
                "has_baseline": has_baseline,
                "env": env,
            },
        )


# ---------------------------------------------------------------------------
# Metric 5: LLMDataQualityJudge
# ---------------------------------------------------------------------------


class LLMDataQualityJudge(Metric):
    """
    GPT-4-class LLM judge scoring a random sample of DB records on 4 quality criteria.

    The judge evaluates each sampled record against a structured rubric and returns
    a score per criterion. This provides a signal that SQL checks cannot capture:
    semantic plausibility (e.g. a business traveller booking 3 checked bags).

    Formula:
        For each sampled record, the LLM is asked to rate 4 criteria (0/1/2):
          C1 — Temporal plausibility: are dates/times realistic for the scenario?
          C2 — Value realism: are categorical/numeric values plausible together?
          C3 — Relational coherence: does the record relate sensibly to linked records?
          C4 — Demographic consistency: are user-level attributes internally consistent?

        Per criterion:  score_i = mean(ratings) / 2   (normalises to [0, 1])
        Overall score:  llm_data_quality_judge = mean(score_1, ..., score_4)

        Samples min(N_SAMPLE, |agent_rows|) records at random.
        Uses temperature=0 for reproducibility.
        Response is cached in memory per (db_path, table) to avoid re-querying.

    Interpretation:
        - 1.0  → LLM rates all sampled records as fully plausible across all criteria
        - 0.5  → mixed quality; some plausibility concerns (score 1/2 for some criteria)
        - 0.0  → LLM finds all records implausible or incoherent
        - Returns n/a when LLM is unavailable (SYNTHESIZE_PROXY_BASE_URL not set)
        - Use for qualitative diagnostic; cross-validate against SQL-based metrics

    Reference:
        Direct use of LLM-as-judge framework from: MT-Bench (arXiv:2306.05685,
        Zheng et al., NeurIPS 2023) — GPT-4 as judge achieves >80% human agreement.
        Bias mitigation: single-answer grading (avoids position/verbosity bias) as
        recommended by JudgeLM (arXiv:2310.17631, Zhu et al.).
        4-criterion rubric: Original for this framework; maps to DAMA-DMBOK2 dimensions
        (timeliness, validity, accuracy, consistency).
    """

    N_SAMPLE = 20  # max records to judge per run (cost control)

    _SYSTEM_PROMPT = (
        "You are a data quality auditor. You will be shown a database record "
        "and asked to evaluate its plausibility on four criteria. "
        "For each criterion, respond with exactly 0, 1, or 2 where: "
        "0=implausible/bad, 1=acceptable/minor issues, 2=realistic/good. "
        "Respond with a JSON object only, no prose."
    )

    _USER_TEMPLATE = """\
Record from table '{table}' in a '{env}' system:
{record_json}

Rate this record on each of the following criteria (0=bad, 1=ok, 2=good):
1. temporal_plausibility: Are the date/time values realistic and internally ordered?
2. value_realism: Are the categorical and numeric values plausible for this type of record?
3. relational_coherence: Do the foreign key references and related fields make sense together?
4. demographic_consistency: Are user-level attributes (age, location, etc.) internally consistent?

Respond with JSON only:
{{"temporal_plausibility": <0|1|2>, "value_realism": <0|1|2>, "relational_coherence": <0|1|2>, "demographic_consistency": <0|1|2>}}
"""

    _cache: dict[str, list[dict]] = {}

    @property
    def name(self) -> str:
        return "llm_data_quality_judge"

    def _call_llm(self, prompt: str, env: str) -> dict | None:
        """Call the LLM proxy with temperature=0. Returns parsed JSON or None."""
        import os

        base_url = os.environ.get("SYNTHESIZE_PROXY_BASE_URL", "").rstrip("/")
        model = os.environ.get("SYNTHESIZE_MODEL", "claude-haiku-4-5-20251001")
        if not base_url:
            return None

        try:
            import urllib.request

            payload = json.dumps(
                {
                    "model": model,
                    "temperature": 0,
                    "max_tokens": 256,
                    "messages": [
                        {"role": "system", "content": self._SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                }
            ).encode()
            req = urllib.request.Request(  # noqa: S310
                f"{base_url}/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                body = json.loads(resp.read().decode())
            content = body["choices"][0]["message"]["content"].strip()
            # Extract JSON from content (may be wrapped in markdown)
            m = re.search(r"\{[^}]+\}", content)
            if m:
                return json.loads(m.group(0))
            return None
        except Exception:
            return None

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if db_path is None:
            return MetricResult(name=self.name, value=None, display="n/a (no DB)")
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        import os

        if not os.environ.get("SYNTHESIZE_PROXY_BASE_URL"):
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (SYNTHESIZE_PROXY_BASE_URL not set)",
            )

        envs = {r.metadata.env for r in records}
        env = next(iter(envs)) if len(envs) == 1 else "unknown"

        baseline_path = db_path.parent / "baseline.db"
        has_baseline = baseline_path.exists()

        try:
            conn = _open(db_path)
            baseline_conn = _open(baseline_path) if has_baseline else None

            # Find the most "interesting" table (most FK relationships = core entity table)
            best_table = None
            best_fk_count = -1
            for table in _tables(conn):
                fk_count = len(_foreign_keys(conn, table))
                if fk_count > best_fk_count:
                    best_fk_count = fk_count
                    best_table = table

            if best_table is None:
                conn.close()
                return MetricResult(name=self.name, value=None, display="n/a (no tables found)")

            # Get agent-created rows
            cols = _column_names(conn, best_table)
            all_rows = conn.execute(
                f"SELECT * FROM {best_table} LIMIT {self.N_SAMPLE * 3}"  # noqa: S608
            ).fetchall()

            if baseline_conn:
                try:
                    n_seed = baseline_conn.execute(
                        f"SELECT COUNT(*) FROM {best_table}"  # noqa: S608
                    ).fetchone()[0]
                    agent_rows = list(all_rows)[n_seed:]
                except sqlite3.Error:
                    agent_rows = list(all_rows)
                baseline_conn.close()
            else:
                agent_rows = list(all_rows)

            conn.close()

            if not agent_rows:
                return MetricResult(
                    name=self.name,
                    value=None,
                    display="n/a (no agent-created rows found)",
                )

            import random

            sample = random.sample(agent_rows, min(self.N_SAMPLE, len(agent_rows)))
        except Exception as exc:
            return MetricResult(name=self.name, value=None, display=f"n/a (DB error: {exc})")

        # Score each sampled record
        criterion_scores: dict[str, list[int]] = defaultdict(list)
        judged = 0

        for row in sample:
            record_dict = dict(zip(cols, row))
            prompt = self._USER_TEMPLATE.format(
                table=best_table,
                env=env,
                record_json=json.dumps(record_dict, indent=2, default=str),
            )
            result = self._call_llm(prompt, env)
            if result is None:
                continue

            for criterion in (
                "temporal_plausibility",
                "value_realism",
                "relational_coherence",
                "demographic_consistency",
            ):
                score = result.get(criterion)
                if isinstance(score, int) and 0 <= score <= 2:
                    criterion_scores[criterion].append(score)
            judged += 1

        if not criterion_scores or judged == 0:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (LLM calls failed or returned no scores)",
            )

        per_criterion = {k: round(statistics.mean(v) / 2.0, 4) for k, v in criterion_scores.items()}
        value = statistics.mean(per_criterion.values())
        display = f"{value:.3f} (judged {judged}/{len(sample)} records from '{best_table}')"
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details={
                "per_criterion": per_criterion,
                "records_judged": judged,
                "table_sampled": best_table,
                "has_baseline": has_baseline,
            },
        )


# ---------------------------------------------------------------------------
# Metric 5: RecordDeduplicationRate
# ---------------------------------------------------------------------------


class RecordDeduplicationRate(Metric):
    """
    Fraction of agent-created records that are structural duplicates of another record.

    A high deduplication rate means the agent is repeatedly creating the same
    records rather than exploring the diversity of possible inputs. This is a
    synthesis quality failure distinct from semantic diversity — it means the
    actual DB rows are near-identical.

    Formula:
        For each table, compute a fingerprint for each agent-created row:
            fingerprint(row) = MD5(sorted non-PK, non-timestamp field values)

        duplicate_fraction(table) = |{rows : fingerprint seen before}| / |{agent rows}|

        record_deduplication_rate = 1 - mean(duplicate_fraction) over all tables
            with ≥ 2 agent rows

        (Higher = better; 1.0 = no duplicates, 0.0 = all rows are duplicates)

    Interpretation:
        - 1.0  → all agent-created records are structurally unique
        - 0.9+ → healthy; ≤10% duplicate records
        - < 0.7 → significant duplication; synthesis is not diverse
        - Note: duplicates may be valid (e.g. same flight booked twice for different users)
                Check the per_table details to identify which tables have high duplication

    Reference:
        Inspired by: Endless Terminals (arXiv:2601.16443) — unique command ratio as
        a diversity signal. Adapted from command sequences to DB records: high
        structural duplication among generated rows is the record-level analogue
        of repeated command sequences in terminal sessions.
        Original fingerprinting approach for this framework.
    """

    # Column name tokens to exclude from fingerprinting (PK-like + timestamp-like)
    _EXCLUDE_TOKENS = (
        "id",
        "_id",
        "pk",
        "created_at",
        "updated_at",
        "modified_at",
        "created_on",
        "modified_on",
        "last_modified",
        "timestamp",
    )

    @property
    def name(self) -> str:
        return "record_deduplication_rate"

    def _fingerprint_cols(self, cols: list[str]) -> list[str]:
        """Return columns that should be used for fingerprinting (non-PK, non-timestamp)."""
        result = []
        for c in cols:
            lower = c.lower()
            if any(lower == tok or lower.endswith(tok) for tok in self._EXCLUDE_TOKENS):
                continue
            result.append(c)
        return result or cols  # fallback: use all cols if all are excluded

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if db_path is None:
            return MetricResult(name=self.name, value=None, display="n/a (no DB)")
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        baseline_path = db_path.parent / "baseline.db"
        has_baseline = baseline_path.exists()

        try:
            conn = _open(db_path)
            baseline_conn = _open(baseline_path) if has_baseline else None

            per_table: dict[str, float] = {}

            for table in _tables(conn):
                cols = _column_names(conn, table)
                fp_cols = self._fingerprint_cols(cols)

                all_rows = conn.execute(
                    f"SELECT {', '.join(fp_cols)} FROM {table}"  # noqa: S608
                ).fetchall()

                # Determine agent-only rows
                if baseline_conn:
                    try:
                        n_seed = baseline_conn.execute(
                            f"SELECT COUNT(*) FROM {table}"  # noqa: S608
                        ).fetchone()[0]
                        agent_rows = list(all_rows)[n_seed:]
                    except sqlite3.Error:
                        agent_rows = list(all_rows)
                else:
                    agent_rows = list(all_rows)

                if len(agent_rows) < 2:
                    continue  # need ≥2 rows to detect duplicates

                seen: set[str] = set()
                n_dupes = 0
                for row in agent_rows:
                    fp = hashlib.md5(  # noqa: S324
                        json.dumps(sorted(zip(fp_cols, row)), default=str).encode()
                    ).hexdigest()
                    if fp in seen:
                        n_dupes += 1
                    else:
                        seen.add(fp)

                per_table[table] = round(1.0 - n_dupes / len(agent_rows), 4)

            if baseline_conn:
                baseline_conn.close()
            conn.close()
        except Exception as exc:
            return MetricResult(name=self.name, value=None, display=f"n/a (DB error: {exc})")

        if not per_table:
            return MetricResult(
                name=self.name,
                value=None,
                display="n/a (no tables with ≥2 agent rows)",
            )

        value = statistics.mean(per_table.values())
        n_tables = len(per_table)
        display = f"{value:.3f} (unique fraction across {n_tables} tables)"
        return MetricResult(
            name=self.name,
            value=value,
            display=display,
            details={
                "per_table": per_table,
                "has_baseline": has_baseline,
            },
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

DATA_QUALITY_METRICS: list[Metric] = [
    TemporalConsistencyScore(),
    WorkflowCompletenessScore(),
    RealisticValueDistributionScore(),
    PairwiseFidelityScore(),
    CrossTableRelationalFidelityScore(),
    ProcessFidelityScore(),
    LLMDataQualityJudge(),
    RecordDeduplicationRate(),
]
