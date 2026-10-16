"""
GeneralistPopulator: domain-agnostic data population agent.

Three-phase loop using Deep Agents (LangGraph):
  Phase 1 — EXPLORE: classify tools, build entity dependency graph, estimate distributions
  Phase 2 — PLAN:    choose what to create next (single structured LLM call)
  Phase 3 — EXECUTE: populate data via write tools

All three phases are overridable. Subclasses may replace any phase independently.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Literal, Optional
from uuid import uuid4

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from synthesize.exploration.manifest import ExplorationManifest
from synthesize.exploration.planning import PlanningPhase, PlanRecipe
from synthesize.exploration.prompts import (
    EXPLORE_SYSTEM_PROMPT,
    EXPLORE_USER_PROMPT,
    build_execute_system_prompt,
)

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


# ── Write-guard helper ────────────────────────────────────────────────────────


def _block_write_tool(tool: StructuredTool) -> StructuredTool:
    """Wrap a write tool so calls return a rejection message — schema preserved."""

    def blocked(**kwargs: Any) -> str:
        args_str = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        return (
            f"[explore_mode] '{tool.name}({args_str})' is BLOCKED — write tools cannot "
            f"execute during exploration. Classify it with update_tool_classification."
        )

    return StructuredTool.from_function(
        func=blocked,
        name=tool.name,
        description=tool.description + "  ⚠️ WRITE — blocked during exploration",
        args_schema=tool.args_schema,
    )


# ── RunResult ─────────────────────────────────────────────────────────────────


class ToolCall(BaseModel):
    tool: str
    args: dict
    result: str
    is_error: bool = False


class RunResult(BaseModel):
    run_id: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    final_message: str = ""
    task_description: str = ""
    intent_name: str = ""

    @classmethod
    def from_messages(cls, messages: list, run_id: str | None = None) -> "RunResult":
        """Convert Deep Agents message history into a RunResult."""
        tool_calls: list[ToolCall] = []
        pending: dict[str, dict] = {}

        for msg in messages:
            if isinstance(msg, AIMessage):
                for tc in msg.tool_calls or []:
                    pending[tc["id"]] = {"tool": tc["name"], "args": tc["args"]}
            elif isinstance(msg, ToolMessage):
                call = pending.pop(msg.tool_call_id, {})
                tool_calls.append(
                    ToolCall(
                        tool=call.get("tool", "unknown"),
                        args=call.get("args", {}),
                        result=str(msg.content),
                        is_error=getattr(msg, "status", "success") == "error",
                    )
                )

        final = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and isinstance(msg.content, str) and msg.content.strip():
                final = msg.content.strip()
                break

        return cls(
            run_id=run_id or str(uuid4()),
            tool_calls=tool_calls,
            final_message=final,
        )


# ── Schema conversion helper ──────────────────────────────────────────────────


def _json_schema_to_pydantic(name: str, schema: dict) -> type[BaseModel]:
    """Dynamically build a Pydantic model from a JSON Schema dict."""
    props = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    annotations: dict[str, Any] = {}
    defaults: dict[str, Any] = {}

    _SCALAR_MAP: dict[str, type] = {
        "integer": int,
        "number": float,
        "boolean": bool,
        "string": str,
        "object": dict,
    }

    for field_name, field_schema in props.items():
        field_type = field_schema.get("type", "string")
        py_type: Any

        if field_type == "array":
            items = field_schema.get("items", {})
            item_type = items.get("type", "string")
            inner = _SCALAR_MAP.get(item_type, Any)
            py_type = List[inner]
        else:
            py_type = _SCALAR_MAP.get(field_type, Any)

        if field_name not in required_fields:
            py_type = Optional[py_type]
            defaults[field_name] = None
        annotations[field_name] = py_type

    namespace: dict[str, Any] = {"__annotations__": annotations, **defaults}
    return type(name, (BaseModel,), namespace)


# ── GeneralistPopulator ───────────────────────────────────────────────────────


class GeneralistPopulator:
    """
    Domain-agnostic data population agent with 3 overridable phases.
    Uses Deep Agents (LangGraph) for the agent loop.

    Usage:
        from langchain_anthropic import ChatAnthropic

        model = ChatAnthropic(model=..., base_url=..., api_key="placeholder")
        manifest = ExplorationManifest(Path(".runs/exploration/myenv/manifest.db"))
        agent = GeneralistPopulator(
            tool_registry={"get_users": {...}, "create_user": {...}},
            manifest=manifest,
            model=model,
        )
        agent.register_tools()
        result = agent.run()
    """

    def __init__(
        self,
        tool_registry: dict[str, dict],
        manifest: ExplorationManifest,
        model: "BaseChatModel",
        explore_mode: Literal["explore", "staged", "interleaved"] = "staged",
        explore_runs: int = 5,
        callbacks: list = (),
        env_name: str | None = None,
        enable_heuristics: bool = True,
        enable_plan: bool = True,
        enable_coverage: bool = True,
    ) -> None:
        self.tool_registry = tool_registry
        self.manifest = manifest
        self.model = model
        self.explore_mode = explore_mode
        self.explore_runs = explore_runs
        self.callbacks = list(callbacks)
        self.env_name = env_name
        self.enable_heuristics = enable_heuristics
        self.enable_plan = enable_plan
        self.enable_coverage = enable_coverage
        self._run_count = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def register_tools(self) -> None:
        """Register all tools in the manifest (generates embeddings lazily)."""
        for name, spec in self.tool_registry.items():
            self.manifest.register_tool(
                name=name,
                description=spec.get("description", ""),
                input_schema=spec.get("input_schema", {}),
            )

    def run(self) -> RunResult:
        """Run one full populate cycle: explore → plan → execute."""
        self._run_count += 1
        if self._should_explore():
            self.explore()
        recipe = self.plan(self.manifest)
        result = self.execute(recipe)
        result.task_description = recipe.task_description
        result.intent_name = recipe.intent_name
        self.manifest.record_task(
            cycle_num=self._run_count,
            intent_name=recipe.intent_name,
            task_description=recipe.task_description,
        )
        if result.tool_calls and self.enable_heuristics:
            self._maybe_extract_heuristics(result)
        elif result.tool_calls and not self.enable_heuristics:
            print("  [heuristics] disabled — skipping extraction", flush=True)
        return result

    # ── Phase hooks (subclasses override these) ───────────────────────────────

    def explore(self) -> ExplorationManifest:
        """
        Phase 1: Classify tools and build entity dependency graph.
        Default: Deep Agents loop with write tools wrapped as no-ops.
        """
        agent = self._build_explore_agent()
        self._run_with_write_guard(agent, prompt=EXPLORE_USER_PROMPT)
        return self.manifest

    def plan(self, manifest: ExplorationManifest) -> PlanRecipe:
        """
        Phase 2: Choose what to create and in what order.
        Default: single structured LLM call using manifest context.
        """
        if not self.enable_plan:
            print("  [plan] disabled — using generic task description", flush=True)
            try:
                entity_order = manifest.get_topological_order()
            except Exception:
                entity_order = []
            return PlanRecipe(
                intent_name="POPULATE",
                entity_creation_order=entity_order,
                distribution_targets=manifest.get_distribution_weights(),
                reasoning="no-plan ablation: generic task",
                task_description=(
                    "Populate the database with realistic, diverse data. "
                    "Use the available write tools to create new records, "
                    "following the entity dependency order from the manifest. "
                    "Vary your choices across different record types and attribute values."
                ),
            )
        return PlanningPhase(
            manifest, env_name=self.env_name, enable_coverage=self.enable_coverage
        ).plan(self.tool_registry)

    def execute(self, recipe: PlanRecipe) -> RunResult:
        """
        Phase 3: Execute the chosen recipe via API calls.
        Default: Deep Agents loop with full tool access.
        """
        agent = self._build_execute_agent(recipe)
        return self._run_agent(agent, prompt=recipe.task_description)

    # ── Internal helpers (overridable for advanced customisation) ─────────────

    def _should_explore(self) -> bool:
        # Use the persistent manifest cycle count so the K budget is shared across
        # trajectories (each trajectory creates a new instance, resetting _run_count).
        total_done = self.manifest.get_total_cycles()
        if self.explore_mode == "explore":
            result = total_done < self.explore_runs
        elif self.explore_mode == "staged":
            # K=0 → never explore; K>0 → explore until manifest is populated AND
            # budget of K exploration-preceding cycles is consumed.
            result = self.explore_runs > 0 and (
                not self.manifest.is_explored() or total_done < self.explore_runs
            )
        elif self.explore_mode == "interleaved":
            result = True
        else:
            result = False
        print(
            f"[_should_explore] mode={self.explore_mode} K={self.explore_runs} "
            f"total_done={total_done} is_explored={self.manifest.is_explored()} "
            f"→ {result}",
            flush=True,
        )
        return result

    def _build_explore_agent(self) -> Any:
        """Build Deep Agents with write tools replaced by rejection wrappers."""
        from deepagents import create_deep_agent

        env_tools = self._as_langchain_tools()
        manifest_tools = self.manifest.as_langchain_tools()

        guarded = [
            _block_write_tool(t)
            if (t.name in self.tool_registry and self.manifest.get_tool_kind(t.name) != "read")
            else t
            for t in env_tools
        ]
        return create_deep_agent(
            model=self.model,
            tools=guarded + manifest_tools,
            system_prompt=EXPLORE_SYSTEM_PROMPT,
        )

    def _build_execute_agent(self, recipe: PlanRecipe) -> Any:
        """Build Deep Agents with full tool access."""
        from deepagents import create_deep_agent

        # Inject all stored heuristics — no trigger filtering since heuristics are few
        # and always relevant to the environment (trigger_tools classification is unreliable
        # because search tools are 'read' but heuristics about them are still useful).
        heuristics_block = self.manifest.to_heuristics_prompt() if self.enable_heuristics else ""
        manifest_parts = self.manifest.to_prompt_context() + "\n\n" + recipe.to_prompt()
        if heuristics_block:
            manifest_parts += "\n\n" + heuristics_block
            for h in self.manifest.get_heuristics():
                self.manifest.record_heuristic_use(h["pattern_name"])

        system_prompt = build_execute_system_prompt(manifest_context=manifest_parts)
        return create_deep_agent(
            model=self.model,
            tools=self._as_langchain_tools(),
            system_prompt=system_prompt,
        )

    def _run_with_write_guard(self, agent: Any, prompt: str) -> None:
        """Run explore agent — write tools return rejection messages, no interrupts."""
        config = {"configurable": {"thread_id": str(uuid4())}}
        agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config=config,
            callbacks=self.callbacks or None,
        )

    def _run_agent(self, agent: Any, prompt: str) -> RunResult:
        """Run execute agent to completion, return RunResult with extracted tool calls."""
        run_id = str(uuid4())
        config = {"configurable": {"thread_id": run_id}}
        result = agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config=config,
            callbacks=self.callbacks or None,
        )
        messages = result if isinstance(result, list) else result.get("messages", [])
        return RunResult.from_messages(messages, run_id=run_id)

    def _maybe_extract_heuristics(self, result: RunResult) -> None:
        """Best-effort: ask an LLM if this trajectory reveals a reusable discovery pattern."""
        if len(result.tool_calls) < 5:
            return  # too short to contain a non-obvious pattern

        # Include truncated results so the LLM can see which calls were pivotal
        lines = []
        for i, tc in enumerate(result.tool_calls):
            status = "FAIL" if tc.is_error else "ok"
            result_snippet = (tc.result or "")[:120].replace("\n", " ")
            lines.append(f"  {i + 1:2d}. {tc.tool} [{status}] → {result_snippet}")
        sequence = "\n".join(lines)

        prompt = (
            f"Task: {result.task_description}\n\n"
            f"Tool call sequence:\n{sequence}\n\n"
            "Identify whether the agent discovered a SHORTCUT late in the trajectory "
            "that dramatically reduced failed attempts — a call it made after many failures "
            "whose result then unlocked subsequent successful calls.\n\n"
            "The tip should tell future agents to make that shortcut call FIRST, "
            "before the exhaustive search loop, so they avoid the wasted attempts.\n\n"
            "Do NOT flag exhaustive enumeration or brute-force search as a useful pattern — "
            "those are the problem, not the solution.\n\n"
            "Only respond with has_heuristic=true if there is a clear, concrete shortcut "
            "that a future agent could apply at the START of a similar task.\n\n"
            'Respond with JSON: {"has_heuristic": true, "pattern_name": "short_slug", '
            '"description": "concise tip telling the agent what to call FIRST and why", '
            '"trigger_tools": ["write_tool_this_helps"]}\n'
            'or: {"has_heuristic": false}'
        )
        try:
            base_url = os.environ["SYNTHESIZE_PROXY_BASE_URL"].rstrip("/")
            model = os.environ["SYNTHESIZE_MODEL"]
            payload = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 300,
            }).encode()
            req = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
            content = resp["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                lines = content.splitlines()
                content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            parsed = json.loads(content)
            if parsed.get("has_heuristic"):
                stored = self.manifest.add_heuristic(
                    pattern_name=parsed["pattern_name"],
                    description=parsed["description"],
                    trigger_tools=parsed.get("trigger_tools", []),
                    cycle=self._run_count,
                )
                if stored:
                    print(f"  [heuristic] Learned: {parsed['pattern_name']}")
        except Exception:
            pass  # best-effort only

    def _as_langchain_tools(self) -> list:
        """Wrap tool_registry entries as LangChain StructuredTool objects.

        Each tool function is wrapped to:
        1. Always return a JSON string (prevents Anthropic API errors with
           empty-list content in ToolMessages).
        2. Catch all exceptions and return error messages as strings (prevents
           LangGraph parallel tool execution from dropping tool results when
           one tool raises).
        """
        import json

        tools = []
        for name, spec in self.tool_registry.items():
            schema = _json_schema_to_pydantic(f"{name}_Input", spec.get("input_schema", {}))
            fn = spec["fn"]

            def _make_safe_wrapper(inner_fn, tool_name):  # noqa: E301 — closure factory
                def wrapper(**kwargs):
                    try:
                        result = inner_fn(**kwargs)
                    except Exception as exc:
                        return f"Error calling {tool_name}: {type(exc).__name__}: {exc}"
                    if isinstance(result, str):
                        return result
                    return json.dumps(result, default=str)
                return wrapper

            tools.append(
                StructuredTool.from_function(
                    func=_make_safe_wrapper(fn, name),
                    name=name,
                    description=spec.get("description", ""),
                    args_schema=schema,
                )
            )
        return tools


# ── Factory helper ─────────────────────────────────────────────────────────────


def make_generalist_populator(
    tool_registry: dict[str, dict],
    manifest_path: Path,
    explore_mode: Literal["explore", "staged", "interleaved"] = "staged",
    explore_runs: int = 5,
) -> GeneralistPopulator:
    """Convenience factory: builds model + manifest + Langfuse callbacks from env vars."""
    from dotenv import load_dotenv

    from synthesize.synthesizer._llm import build_chat_model

    load_dotenv()

    model = build_chat_model()

    callbacks = []
    if all(
        k in os.environ for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
    ):
        from langfuse.callback import CallbackHandler as LangfuseHandler

        callbacks.append(
            LangfuseHandler(
                public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
                secret_key=os.environ["LANGFUSE_SECRET_KEY"],
                host=os.environ["LANGFUSE_BASE_URL"],
            )
        )

    manifest = ExplorationManifest(manifest_path)

    return GeneralistPopulator(
        tool_registry=tool_registry,
        manifest=manifest,
        model=model,
        explore_mode=explore_mode,
        explore_runs=explore_runs,
        callbacks=callbacks,
    )
