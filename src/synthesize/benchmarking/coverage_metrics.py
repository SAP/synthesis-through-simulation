"""
Group 2 — Data Coverage Metrics.

These metrics measure how well the agent-generated DB state covers the intended
value space. All require db_path and exclude seed data by comparing against
baseline.db (db_path.parent / "baseline.db").

Seed data exclusion convention:
    baseline_path = db_path.parent / "baseline.db"
    If present: subtract baseline counts from final counts to isolate agent rows.
    If absent: use full snapshot (note this in details["has_baseline"]).

All three are in ALL_METRICS (opt-in, DB-dependent).
"""

from __future__ import annotations

import re
import sqlite3
import statistics
from pathlib import Path

from synthesize.models import DatasetItem

from ._utils import normalized_entropy
from .base import Metric, MetricResult


def _get_agent_counter(
    conn: sqlite3.Connection,
    baseline_conn: sqlite3.Connection | None,
    table: str,
    col: str,
) -> dict[str, int]:
    """Return per-value counts for agent-generated rows only (baseline subtracted)."""
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT {col}, COUNT(*) FROM {table} WHERE {col} IS NOT NULL GROUP BY {col}"  # noqa: S608
    )
    final_dist: dict[str, int] = {str(k): v for k, v in cursor.fetchall()}

    if baseline_conn is None:
        return final_dist

    bcursor = baseline_conn.cursor()
    try:
        bcursor.execute(
            f"SELECT {col}, COUNT(*) FROM {table} WHERE {col} IS NOT NULL GROUP BY {col}"  # noqa: S608
        )
        baseline_dist: dict[str, int] = {str(k): v for k, v in bcursor.fetchall()}
    except sqlite3.Error:
        return final_dist

    agent_dist = {
        k: max(0, final_dist.get(k, 0) - baseline_dist.get(k, 0))
        for k in set(final_dist) | set(baseline_dist)
    }
    return {k: v for k, v in agent_dist.items() if v > 0}


def _open_baseline(db_path: Path) -> sqlite3.Connection | None:
    baseline_path = db_path.parent / "baseline.db"
    if baseline_path.exists():
        return sqlite3.connect(str(baseline_path))
    return None


def _get_text_columns(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Return (table, col) pairs for categorical-like TEXT columns.

    Includes TEXT/CHAR columns where:
      - at least 2 distinct values exist (entropy defined)
      - distinctness ratio ≤ 0.5  (n_distinct / n_total_rows ≤ 0.5)

    The ratio filter replaces the old hard upper cap of 50.  It scales with
    batch size: a column with 20 distinct values qualifies in a 50-row table
    but not in a 30-row table where every row is unique.  This filters out
    free-text fields (passenger names, descriptions) regardless of batch size.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    result = []
    for table in tables:
        try:
            cursor.execute(f"PRAGMA table_info({table})")  # noqa: S608
            cols = [(row[1], row[2]) for row in cursor.fetchall()]
            cursor.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            n_total = cursor.fetchone()[0]
            if n_total == 0:
                continue
            for col_name, col_type in cols:
                if "TEXT" not in col_type.upper() and "CHAR" not in col_type.upper():
                    continue
                cursor.execute(f"SELECT COUNT(DISTINCT {col_name}) FROM {table}")  # noqa: S608
                n_distinct = cursor.fetchone()[0]
                if n_distinct >= 2 and (n_distinct / n_total) <= 0.5:
                    result.append((table, col_name))
        except sqlite3.Error:
            continue
    return result


def _parse_check_constraints(conn: sqlite3.Connection) -> dict[tuple[str, str], list[str]]:
    """Return {(table, col): [valid_values]} for CHECK IN constraints."""
    cursor = conn.cursor()
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
    rows = cursor.fetchall()

    result: dict[tuple[str, str], list[str]] = {}
    for table_name, ddl in rows:
        if not ddl:
            continue
        # Match: col_name TYPE ... CHECK(col_name IN ("v1", "v2", ...))
        # The outer CHECK(...) may not have a closing ) in the first group if the DDL
        # has nested parens. Use a two-step approach: find col+type+CHECK prefix, then
        # look for the IN (...) list that follows.
        #
        # Pattern: capture column_name and then search for IN ( ... ) in the rest
        col_check_pattern = re.compile(
            r"(\w+)\s+\w+[^,\n]*?CHECK\s*\(\s*\1\s+IN\s*\(([^)]+)\)",
            re.IGNORECASE,
        )
        for m in col_check_pattern.finditer(ddl):
            col_name = m.group(1)
            inner = m.group(2)
            vals = re.findall(r"""["']([^"']+)["']""", inner)
            if vals:
                result[(table_name, col_name)] = vals
    return result


def _parse_fk_columns(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Return (table, col) pairs for all foreign-key columns."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    result = []
    for table in tables:
        try:
            cursor.execute(f"PRAGMA foreign_key_list({table})")  # noqa: S608
            for row in cursor.fetchall():
                # row: (id, seq, table, from_col, to_col, ...)
                result.append((table, row[3]))
        except sqlite3.Error:
            continue
    return result


class SchemaFieldCoverage(Metric):
    """
    Mean normalized entropy over categorical-like TEXT columns (agent rows only).

    A column qualifies if it is TEXT/CHAR type, has ≥ 2 distinct values, and its
    distinctness ratio (n_distinct / n_total_rows) is ≤ 0.5.  The ratio filter
    replaces the old hard cap of 50 distinct values — it scales with batch size and
    filters out free-text fields (names, descriptions) regardless of n.

    Formula:
        For each qualifying TEXT column:
            agent_counts = final_counts - baseline_counts  (seed-excluded)
            H_norm(col)  = H(agent_counts) / log(|distinct values in agent_counts|)

        schema_field_coverage = mean(H_norm) over qualifying columns

    Interpretation:
        - 1.0  → every qualifying column has a perfectly uniform agent-generated distribution
        - 0.0  → every qualifying column has only one distinct agent-generated value
        - 0.5–0.8 → healthy range; agent generates varied categorical values
        - Low values indicate the agent tends to reuse the same categorical values

    Reference:
        Inspired by: EnvScaler (arXiv:2601.05808) — topic diversity via Shannon entropy
        applied to synthesis scenario distributions; adapted here to measure per-column
        diversity of agent-generated categorical values in the DB schema.
    """

    @property
    def name(self) -> str:
        return "schema_field_coverage"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if db_path is None:
            return MetricResult(name=self.name, value=None, display="n/a (no DB)")
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        try:
            conn = sqlite3.connect(str(db_path))
            baseline_conn = _open_baseline(db_path)
            has_baseline = baseline_conn is not None

            text_cols = _get_text_columns(conn)
            entropies: dict[str, float] = {}

            for table, col in text_cols:
                agent_dist = _get_agent_counter(conn, baseline_conn, table, col)
                if not agent_dist or sum(agent_dist.values()) == 0:
                    continue
                h_norm = normalized_entropy(agent_dist)
                entropies[f"{table}.{col}"] = round(h_norm, 4)

            conn.close()
            if baseline_conn:
                baseline_conn.close()

            if not entropies:
                return MetricResult(
                    name=self.name,
                    value=None,
                    display="n/a (no qualifying text columns with agent rows)",
                )

            value = statistics.mean(entropies.values())
            display = f"{value:.3f} mean H_norm over {len(entropies)} text columns" + (
                " (seed-excluded)" if has_baseline else " (no baseline)"
            )
            return MetricResult(
                name=self.name,
                value=value,
                display=display,
                details={"per_column": entropies, "has_baseline": has_baseline},
            )
        except Exception as exc:
            return MetricResult(
                name=self.name,
                value=None,
                display=f"n/a (DB error: {exc})",
            )


class CrossTableReferentialDiversity(Metric):
    """
    Mean normalized entropy over foreign-key column distributions (agent rows only).

    Formula:
        For each FK column across all tables:
            agent_fk_counts = Counter(fk_values in snapshot) - Counter(fk_values in baseline)
            H_norm(fk_col)  = H(agent_fk_counts) / log(|distinct FK values|)

        cross_table_ref_diversity = mean(H_norm) over all FK columns

    Interpretation:
        - 1.0  → agent distributes references uniformly across all referenced entities
        - 0.0  → agent always references the same entity (degenerate)
        - High diversity means the generated data references a broad range of
          employees, tickets, users, etc. rather than clustering around a few
        - Low values indicate the agent tends to repeatedly act on the same entities

    Reference:
        Original metric for this framework — measures whether the synthesis generates
        diverse cross-table relationships. Enterprise data quality requires that
        generated records reference a variety of parent entities, not just a handful.
    """

    @property
    def name(self) -> str:
        return "cross_table_ref_diversity"

    def compute(self, records: list[DatasetItem], db_path: Path | None = None) -> MetricResult:
        if db_path is None:
            return MetricResult(name=self.name, value=None, display="n/a (no DB)")
        if not records:
            return MetricResult(name=self.name, value=None, display="n/a (no records)")

        try:
            conn = sqlite3.connect(str(db_path))
            baseline_conn = _open_baseline(db_path)
            has_baseline = baseline_conn is not None

            fk_cols = _parse_fk_columns(conn)
            entropies: dict[str, float] = {}

            for table, col in fk_cols:
                agent_dist = _get_agent_counter(conn, baseline_conn, table, col)
                if not agent_dist or sum(agent_dist.values()) == 0:
                    continue
                h_norm = normalized_entropy(agent_dist)
                entropies[f"{table}.{col}"] = round(h_norm, 4)

            conn.close()
            if baseline_conn:
                baseline_conn.close()

            if not entropies:
                return MetricResult(
                    name=self.name,
                    value=None,
                    display="n/a (no FK columns with agent rows)",
                )

            value = statistics.mean(entropies.values())
            display = f"{value:.3f} mean H_norm over {len(entropies)} FK columns" + (
                " (seed-excluded)" if has_baseline else " (no baseline)"
            )
            return MetricResult(
                name=self.name,
                value=value,
                display=display,
                details={"per_column": entropies, "has_baseline": has_baseline},
            )
        except Exception as exc:
            return MetricResult(
                name=self.name,
                value=None,
                display=f"n/a (DB error: {exc})",
            )
