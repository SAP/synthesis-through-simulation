"""
ExplorationManifest: persistent SQLite knowledge store for the GeneralistPopulator.

Stores tool classifications, entity dependency graph, and distribution priors.
All knowledge is built by the agent during the explore phase — no schema files required.

Vector search via sqlite-vec (always-on, lazy embedding generation).
Graph traversal via stdlib graphlib.TopologicalSorter.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import urllib.request
from graphlib import TopologicalSorter
from pathlib import Path
from typing import Optional

import sqlite_vec

# ── Embedding helper ─────────────────────────────────────────────────────────

_EMBEDDING_DIM = 3072  # text-embedding-3-large full dim


def _embed(text: str) -> list[float]:
    """Call the LiteLLM proxy embedding endpoint. Raises on failure."""
    base_url = os.environ["SYNTHESIZE_PROXY_BASE_URL"].rstrip("/")
    model = os.environ["SYNTHESIZE_EMBEDDING_MODEL"]
    payload = json.dumps({"model": model, "input": text}).encode()
    req = urllib.request.Request(
        f"{base_url}/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        return resp["data"][0]["embedding"]
    except Exception as exc:
        raise RuntimeError(
            f"Embedding endpoint failed ({base_url}): {exc}. "
            "Check SYNTHESIZE_PROXY_BASE_URL and SYNTHESIZE_EMBEDDING_MODEL in .env."
        ) from exc


# ── Schema DDL ───────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS tools (
    name             TEXT PRIMARY KEY,
    kind             TEXT,          -- 'read' | 'write' | 'unknown'
    input_schema_json TEXT,
    description      TEXT,
    error_patterns_json TEXT DEFAULT '[]',
    success_count    INTEGER DEFAULT 0,
    fail_count       INTEGER DEFAULT 0,
    last_seen        TEXT
);

CREATE TABLE IF NOT EXISTS entities (
    name             TEXT PRIMARY KEY,
    create_tool      TEXT,
    sample_record_json TEXT,
    depends_on_json  TEXT DEFAULT '[]'
);

-- Adjacency list: parent must be created before child
CREATE TABLE IF NOT EXISTS dependency_edges (
    parent_entity TEXT NOT NULL,
    child_entity  TEXT NOT NULL,
    evidence      TEXT,
    confidence    REAL DEFAULT 1.0,
    PRIMARY KEY (parent_entity, child_entity)
);

CREATE TABLE IF NOT EXISTS distribution_priors (
    intent_name  TEXT PRIMARY KEY,
    call_weight  REAL DEFAULT 1.0,
    observations INTEGER DEFAULT 0,
    reasoning    TEXT
);

-- Ordered log of executed tasks — used by the planner to avoid repetition
CREATE TABLE IF NOT EXISTS task_history (
    cycle_num        INTEGER PRIMARY KEY,
    intent_name      TEXT NOT NULL,
    task_description TEXT NOT NULL,
    executed_at      TEXT DEFAULT (datetime('now'))
);

-- Execution heuristics distilled from successful trajectories
CREATE TABLE IF NOT EXISTS heuristics (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_name         TEXT NOT NULL UNIQUE,
    description          TEXT NOT NULL,
    trigger_tools_json   TEXT DEFAULT '[]',
    use_count            INTEGER DEFAULT 0,
    discovered_at_cycle  INTEGER,
    created_at           TEXT DEFAULT (datetime('now'))
);
"""

_VEC_DDL = f"CREATE VIRTUAL TABLE IF NOT EXISTS tool_embeddings USING vec0(embedding FLOAT[{_EMBEDDING_DIM}])"


# ── Main class ───────────────────────────────────────────────────────────────


class ExplorationManifest:
    """
    Persistent SQLite store for tool knowledge, entity dependency graph,
    and distribution priors. Populated by the agent during explore phase.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Load sqlite-vec extension for vector search
        self._conn.enable_load_extension(True)
        sqlite_vec.load(self._conn)
        self._conn.enable_load_extension(False)
        self._conn.executescript(_DDL)
        self._conn.execute(_VEC_DDL)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ── Tool API ─────────────────────────────────────────────────────────────

    def register_tool(self, name: str, description: str, input_schema: dict) -> None:
        """Register a tool (idempotent). Generates embedding lazily."""
        from datetime import datetime, timezone

        with self._lock:
            existing = self._conn.execute(
                "SELECT name FROM tools WHERE name = ?", (name,)
            ).fetchone()

            self._conn.execute(
                """INSERT INTO tools (name, kind, input_schema_json, description, last_seen)
                   VALUES (?, 'unknown', ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET last_seen=excluded.last_seen""",
                (
                    name,
                    json.dumps(input_schema),
                    description,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self._conn.commit()

        if existing is None:
            # New tool — generate and store embedding (outside lock for network call)
            embedding = _embed(f"{name}: {description}")
            with self._lock:
                self._conn.execute(
                    "INSERT INTO tool_embeddings(rowid, embedding) VALUES ((SELECT rowid FROM tools WHERE name=?), ?)",
                    (name, json.dumps(embedding)),
                )
                self._conn.commit()

    def update_tool_classification(self, tool_name: str, kind: str) -> None:
        """Set a tool's kind to 'read', 'write', or 'unknown'."""
        if kind not in ("read", "write", "unknown"):
            raise ValueError(f"kind must be 'read', 'write', or 'unknown'; got {kind!r}")
        with self._lock:
            self._conn.execute("UPDATE tools SET kind = ? WHERE name = ?", (kind, tool_name))
            self._conn.commit()

    def get_tool_kind(self, tool_name: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT kind FROM tools WHERE name = ?", (tool_name,)
            ).fetchone()
        return row["kind"] if row else None

    def get_all_tools(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute("SELECT * FROM tools").fetchall()]

    def search_tools(self, query: str, k: int = 20) -> list[dict]:
        """KNN vector search: return top-k tools most relevant to query."""
        embedding = _embed(query)
        with self._lock:
            rows = self._conn.execute(
                """SELECT t.name, t.kind, t.description, t.input_schema_json,
                          distance
                   FROM tool_embeddings AS e
                   JOIN tools AS t ON t.rowid = e.rowid
                   WHERE embedding MATCH ? AND k = ?
                   ORDER BY distance""",
                (json.dumps(embedding), k),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Entity / dependency API ───────────────────────────────────────────────

    def update_entity_dependency(
        self, parent: str, child: str, evidence: str = "", confidence: float = 1.0
    ) -> None:
        """Record that `parent` entity must exist before `child` can be created."""
        with self._lock:
            for entity in (parent, child):
                self._conn.execute(
                    "INSERT OR IGNORE INTO entities (name) VALUES (?)", (entity,)
                )
            self._conn.execute(
                """INSERT INTO dependency_edges (parent_entity, child_entity, evidence, confidence)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(parent_entity, child_entity) DO UPDATE SET
                       evidence=excluded.evidence, confidence=excluded.confidence""",
                (parent, child, evidence, confidence),
            )
            self._conn.commit()

    def get_topological_order(self) -> list[str]:
        """Return entity creation order (parents before children). Raises on cycles."""
        with self._lock:
            edges = self._conn.execute(
                "SELECT parent_entity, child_entity FROM dependency_edges"
            ).fetchall()
        graph: dict[str, set[str]] = {}
        for parent, child in edges:
            graph.setdefault(child, set()).add(parent)
        return list(TopologicalSorter(graph).static_order())

    # ── Distribution priors API ───────────────────────────────────────────────

    def update_distribution_prior(
        self, intent_name: str, call_weight: float, reasoning: str = ""
    ) -> None:
        """Update the relative call weight for an intent."""
        with self._lock:
            self._conn.execute(
                """INSERT INTO distribution_priors (intent_name, call_weight, observations, reasoning)
                   VALUES (?, ?, 1, ?)
                   ON CONFLICT(intent_name) DO UPDATE SET
                       call_weight=excluded.call_weight,
                       observations=observations+1,
                       reasoning=excluded.reasoning""",
                (intent_name, call_weight, reasoning),
            )
            self._conn.commit()

    def get_distribution_weights(self) -> dict[str, float]:
        """Return softmax-normalised intent weights."""
        import math

        with self._lock:
            rows = self._conn.execute(
                "SELECT intent_name, call_weight FROM distribution_priors"
            ).fetchall()
        if not rows:
            return {}
        raw = {r["intent_name"]: r["call_weight"] for r in rows}
        # Softmax normalisation
        max_w = max(raw.values())
        exp_w = {k: math.exp(v - max_w) for k, v in raw.items()}
        total = sum(exp_w.values())
        return {k: v / total for k, v in exp_w.items()}

    def record_task(self, cycle_num: int, intent_name: str, task_description: str) -> None:
        """Append a completed task to the history log.

        cycle_num is used as a hint but the actual stored value is always
        MAX(cycle_num)+1 from the table, so the log stays correct even when
        multiple short-lived GeneralistPopulator instances share one manifest
        (e.g. during batch runs where _run_count resets to 1 each call).
        """
        with self._lock:
            next_cycle = self._conn.execute(
                "SELECT COALESCE(MAX(cycle_num), 0) + 1 FROM task_history"
            ).fetchone()[0]
            self._conn.execute(
                "INSERT INTO task_history (cycle_num, intent_name, task_description) "
                "VALUES (?, ?, ?)",
                (next_cycle, intent_name, task_description),
            )
            self._conn.commit()

    def get_recent_tasks(self, n: int = 5) -> list[dict]:
        """Return the n most recent tasks in chronological order (oldest first)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT cycle_num, intent_name, task_description FROM task_history "
                "ORDER BY cycle_num DESC LIMIT ?",
                (n,),
            ).fetchall()
        return [
            {"cycle": r["cycle_num"], "intent": r["intent_name"], "desc": r["task_description"]}
            for r in reversed(rows)
        ]

    def get_intent_coverage(self, window: int) -> dict[str, int]:
        """Return count of each intent used in the last `window` cycles."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT intent_name, COUNT(*) as cnt FROM task_history "
                "WHERE cycle_num > (SELECT COALESCE(MAX(cycle_num), 0) FROM task_history) - ? "
                "GROUP BY intent_name",
                (window,),
            ).fetchall()
        return {r["intent_name"]: r["cnt"] for r in rows}

    def get_total_cycles(self) -> int:
        """Return total number of completed cycles."""
        with self._lock:
            result = self._conn.execute(
                "SELECT COALESCE(MAX(cycle_num), 0) FROM task_history"
            ).fetchone()
        return result[0]

    # ── Heuristics API ───────────────────────────────────────────────────────

    def add_heuristic(
        self,
        pattern_name: str,
        description: str,
        trigger_tools: list[str] | None = None,
        cycle: int | None = None,
    ) -> bool:
        """Store an execution heuristic. Returns True if new, False if already recorded."""
        with self._lock:
            existing = self._conn.execute(
                "SELECT id FROM heuristics WHERE pattern_name = ?", (pattern_name,)
            ).fetchone()
            if existing:
                return False
            self._conn.execute(
                "INSERT INTO heuristics "
                "(pattern_name, description, trigger_tools_json, discovered_at_cycle) "
                "VALUES (?, ?, ?, ?)",
                (pattern_name, description, json.dumps(trigger_tools or []), cycle),
            )
            self._conn.commit()
        return True

    def get_heuristics(self, trigger_tools: list[str] | None = None) -> list[dict]:
        """Return heuristics relevant to the given tool set (or all if trigger_tools is None)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT pattern_name, description, trigger_tools_json, use_count "
                "FROM heuristics ORDER BY use_count DESC, id ASC"
            ).fetchall()
        results = []
        for r in rows:
            h = dict(r)
            h["trigger_tools"] = json.loads(h.pop("trigger_tools_json"))
            if (
                trigger_tools is None
                or not h["trigger_tools"]
                or any(t in trigger_tools for t in h["trigger_tools"])
            ):
                results.append(h)
        return results

    def record_heuristic_use(self, pattern_name: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE heuristics SET use_count = use_count + 1 WHERE pattern_name = ?",
                (pattern_name,),
            )
            self._conn.commit()

    def to_heuristics_prompt(self, trigger_tools: list[str] | None = None) -> str:
        """Return a formatted heuristics block for injection into execute agent prompts."""
        heuristics = self.get_heuristics(trigger_tools)
        if not heuristics:
            return ""
        lines = ["## Tips from previous runs"]
        for h in heuristics:
            lines.append(f"- **{h['pattern_name']}**: {h['description']}")
        return "\n".join(lines)

    # ── Manifest state ───────────────────────────────────────────────────────

    def is_explored(self) -> bool:
        """True if at least one tool has been classified (not 'unknown')."""
        with self._lock:
            count = self._conn.execute(
                "SELECT COUNT(*) FROM tools WHERE kind != 'unknown'"
            ).fetchone()[0]
        return count > 0

    def to_prompt_context(self) -> str:
        """Format manifest state as a context block for injection into prompts."""
        tools = self.get_all_tools()
        read_tools = [t for t in tools if t["kind"] == "read"]
        write_tools = [t for t in tools if t["kind"] == "write"]
        unknown_tools = [t for t in tools if t["kind"] == "unknown"]

        with self._lock:
            edges = self._conn.execute(
                "SELECT parent_entity, child_entity, confidence FROM dependency_edges ORDER BY confidence DESC"
            ).fetchall()

            priors = self._conn.execute(
                "SELECT intent_name, call_weight, reasoning FROM distribution_priors ORDER BY call_weight DESC"
            ).fetchall()

        parts = ["## Exploration Manifest\n"]

        if read_tools:
            parts.append(f"### Read tools ({len(read_tools)})")
            parts.extend(f"- {t['name']}: {t['description']}" for t in read_tools)

        if write_tools:
            parts.append(f"\n### Write tools ({len(write_tools)})")
            for t in write_tools:
                schema = json.loads(t["input_schema_json"] or "{}")
                required = schema.get("required", [])
                parts.append(f"- {t['name']}({', '.join(required)}): {t['description']}")

        if unknown_tools:
            parts.append(f"\n### Unclassified tools ({len(unknown_tools)})")
            parts.extend(f"- {t['name']}" for t in unknown_tools)

        if edges:
            parts.append("\n### Entity dependency order (parents before children)")
            try:
                order = self.get_topological_order()
                parts.append(" → ".join(order))
            except Exception:
                parts.extend(f"- {r[0]} → {r[1]}" for r in edges)

        if priors:
            parts.append("\n### Distribution priors (relative call weights)")
            for r in priors:
                parts.append(
                    f"- {r['intent_name']}: weight={r['call_weight']:.2f} — {r['reasoning']}"
                )

        return "\n".join(parts)

    # ── Manifest tools (exposed to the agent) ────────────────────────────────

    def as_langchain_tools(self) -> list:
        """Return manifest operations as LangChain StructuredTool objects."""
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, Field

        manifest = self  # capture for closures

        class ClassifyToolInput(BaseModel):
            tool_name: str = Field(description="Name of the tool to classify")
            kind: str = Field(description="Classification: 'read', 'write', or 'unknown'")

        class EntityDepInput(BaseModel):
            parent: str = Field(description="Entity that must exist first")
            child: str = Field(description="Entity that depends on parent")
            evidence: str = Field(default="", description="Why this dependency exists")

        class DistribPriorInput(BaseModel):
            intent_name: str = Field(description="Name of the intent/operation")
            call_weight: float = Field(
                description="Relative frequency weight (higher = call more often)"
            )
            reasoning: str = Field(default="", description="Why this weight was chosen")

        class GetContextInput(BaseModel):
            pass

        return [
            StructuredTool.from_function(
                func=lambda tool_name, kind: (
                    manifest.update_tool_classification(tool_name, kind) or "OK"
                ),
                name="update_tool_classification",
                description="Record whether a tool is a read tool, write tool, or unknown",
                args_schema=ClassifyToolInput,
                handle_tool_error=True,
            ),
            StructuredTool.from_function(
                func=lambda parent, child, evidence="": (
                    manifest.update_entity_dependency(parent, child, evidence) or "OK"
                ),
                name="update_entity_dependency",
                description="Record that one entity type must exist before another can be created",
                args_schema=EntityDepInput,
                handle_tool_error=True,
            ),
            StructuredTool.from_function(
                func=lambda intent_name, call_weight, reasoning="": (
                    manifest.update_distribution_prior(intent_name, call_weight, reasoning) or "OK"
                ),
                name="update_distribution_prior",
                description="Record the relative frequency with which an operation should be performed",
                args_schema=DistribPriorInput,
                handle_tool_error=True,
            ),
            StructuredTool.from_function(
                func=lambda: manifest.to_prompt_context(),
                name="get_exploration_context",
                description="Get a summary of everything learned so far about this environment",
                args_schema=GetContextInput,
                handle_tool_error=True,
            ),
        ]

    # ── Visualization ─────────────────────────────────────────────────────────

    def to_mermaid(self) -> str:
        """Return a Mermaid graph LR diagram of the entity dependency graph and tool classifications."""
        lines = ["graph LR"]

        with self._lock:
            edges = self._conn.execute(
                "SELECT parent_entity, child_entity, confidence FROM dependency_edges ORDER BY confidence DESC"
            ).fetchall()
        for parent, child, conf in edges:
            label = f"{conf * 100:.0f}% conf"
            # sanitise node IDs (replace spaces/dots)
            pid = parent.replace(" ", "_").replace(".", "_")
            cid = child.replace(" ", "_").replace(".", "_")
            lines.append(f'    {pid}["{parent}"] -->|"{label}"| {cid}["{child}"]')

        tools = self.get_all_tools()
        reads = [t["name"] for t in tools if t["kind"] == "read"]
        writes = [t["name"] for t in tools if t["kind"] == "write"]
        unknowns = [t["name"] for t in tools if t["kind"] == "unknown"]

        if reads:
            lines.append(f'\n    subgraph READ["{len(reads)} read tools"]')
            for n in reads[:10]:
                nid = n.replace(" ", "_")
                lines.append(f'        {nid}("{n}")')
            lines.append("    end")

        if writes:
            lines.append(f'\n    subgraph WRITE["{len(writes)} write tools"]')
            for n in writes[:10]:
                nid = n.replace(" ", "_")
                lines.append(f'        {nid}("{n}")')
            lines.append("    end")

        with self._lock:
            priors = self._conn.execute(
                "SELECT intent_name, call_weight FROM distribution_priors ORDER BY call_weight DESC"
            ).fetchall()
        if priors:
            lines.append('\n    subgraph PRIORS["Distribution priors"]')
            for intent, weight in priors:
                nid = intent.replace(" ", "_")
                lines.append(f'        {nid}["{intent}: {weight:.2f}"]')
            lines.append("    end")

        if unknowns:
            lines.append(f'\n    subgraph UNKNOWN["{len(unknowns)} unclassified tools"]')
            for n in unknowns[:5]:
                nid = n.replace(" ", "_")
                lines.append(f'        {nid}("{n}")')
            if len(unknowns) > 5:
                lines.append(f'        more["... +{len(unknowns) - 5} more"]')
            lines.append("    end")

        return "\n".join(lines)

    def visualize(self, output_path: Optional[Path] = None) -> None:
        """
        Three-panel matplotlib figure:
          Top-left:  entity dependency digraph (networkx)
          Top-right: distribution priors bar chart
          Bottom:    tool classification table (name | kind | required args)

        Saves to output_path if provided, otherwise calls plt.show().
        Silently skips if matplotlib or networkx are not installed.
        """
        try:
            import matplotlib.patches as mpatches
            import matplotlib.pyplot as plt
            import networkx as nx
        except ImportError:
            return

        fig = plt.figure(figsize=(14, 11))
        fig.suptitle("ExplorationManifest — Learned Knowledge", fontsize=14, fontweight="bold")

        # ── Top-left: entity dependency graph ─────────────────────────────
        ax_graph = fig.add_subplot(2, 2, 1)
        ax_graph.set_title("Entity Dependency Graph", fontsize=11)

        edges = self._conn.execute(
            "SELECT parent_entity, child_entity, confidence FROM dependency_edges"
        ).fetchall()
        G = nx.DiGraph()
        for parent, child, conf in edges:
            G.add_edge(parent, child, weight=conf)

        if G.nodes:
            pos = nx.spring_layout(G, seed=42)
            nx.draw_networkx_nodes(G, pos, ax=ax_graph, node_color="#4C9BE8", node_size=800)
            nx.draw_networkx_labels(G, pos, ax=ax_graph, font_size=8, font_color="white")
            nx.draw_networkx_edges(
                G, pos, ax=ax_graph, arrows=True, arrowsize=20,
                edge_color="#555", width=1.5, connectionstyle="arc3,rad=0.1",
            )
            edge_labels = {(p, c): f"{w:.0%}" for p, c, w in edges}
            nx.draw_networkx_edge_labels(G, pos, edge_labels, ax=ax_graph, font_size=7)
        else:
            ax_graph.text(0.5, 0.5, "No entity dependencies recorded yet",
                          ha="center", va="center", transform=ax_graph.transAxes, color="gray")
        ax_graph.axis("off")

        # ── Top-right: distribution priors bar chart ───────────────────────
        ax_bar = fig.add_subplot(2, 2, 2)
        ax_bar.set_title("Distribution Priors (call weights)", fontsize=11)

        priors = self._conn.execute(
            "SELECT intent_name, call_weight FROM distribution_priors ORDER BY call_weight DESC"
        ).fetchall()
        if priors:
            names = [r[0] for r in priors]
            weights = [r[1] for r in priors]
            colours = plt.cm.viridis([w / max(weights) for w in weights])  # type: ignore[attr-defined]
            bars = ax_bar.barh(names, weights, color=colours)
            ax_bar.bar_label(bars, fmt="%.2f", padding=3, fontsize=8)
            ax_bar.set_xlabel("Call weight")
            ax_bar.invert_yaxis()
        else:
            ax_bar.text(0.5, 0.5, "No distribution priors recorded yet",
                        ha="center", va="center", transform=ax_bar.transAxes, color="gray")

        # ── Bottom: tool classification table ─────────────────────────────
        ax_table = fig.add_subplot(2, 1, 2)
        ax_table.set_title("Tool Classifications", fontsize=11)
        ax_table.axis("off")

        tools = self.get_all_tools()
        if tools:
            col_labels = ["Tool name", "Kind", "Required args"]
            table_data = []
            row_colours = []
            kind_colour = {"read": "#D4EDDA", "write": "#F8D7DA", "unknown": "#FFF3CD"}
            for t in tools:
                schema = json.loads(t.get("input_schema_json") or "{}")
                required = ", ".join(schema.get("required", [])) or "—"
                table_data.append([t["name"], t["kind"], required])
                row_colours.append([kind_colour.get(t["kind"], "#FFFFFF")] * 3)

            tbl = ax_table.table(
                cellText=table_data,
                colLabels=col_labels,
                cellColours=row_colours,
                loc="center",
                cellLoc="left",
            )
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(8)
            tbl.auto_set_column_width([0, 1, 2])

            legend_patches = [
                mpatches.Patch(color="#D4EDDA", label="read"),
                mpatches.Patch(color="#F8D7DA", label="write"),
                mpatches.Patch(color="#FFF3CD", label="unknown"),
            ]
            ax_table.legend(handles=legend_patches, loc="upper right", fontsize=8)
        else:
            ax_table.text(0.5, 0.5, "No tools registered yet",
                          ha="center", va="center", transform=ax_table.transAxes, color="gray")

        plt.tight_layout()
        if output_path is not None:
            plt.savefig(str(output_path), dpi=150, bbox_inches="tight")
            plt.close(fig)
        else:
            plt.show()
