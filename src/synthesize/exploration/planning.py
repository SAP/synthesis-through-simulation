"""
PlanningPhase: distribution-aware intent scheduling for GeneralistPopulator.

A single structured-output LLM call that decides what to create next,
using the ExplorationManifest to understand what exists and what is needed.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .manifest import ExplorationManifest


@dataclass
class PlanRecipe:
    """What the agent should do in the execute phase."""

    intent_name: str
    entity_creation_order: list[str]
    distribution_targets: dict[str, float]  # {intent_name: weight}
    reasoning: str
    task_description: str  # human-readable prompt for the execute agent

    def to_prompt(self) -> str:
        lines = [
            f"Chosen operation: {self.intent_name}",
            f"Entity creation order: {' → '.join(self.entity_creation_order) or 'no ordering constraints'}",
            f"Reasoning: {self.reasoning}",
        ]
        return "\n".join(lines)


class PlanningPhase:
    """
    Single structured-output LLM call for distribution-aware intent selection.
    """

    def __init__(
        self,
        manifest: "ExplorationManifest",
        env_name: str | None = None,
        enable_coverage: bool = True,
    ) -> None:
        self.manifest = manifest
        self.env_name = env_name
        self.enable_coverage = enable_coverage

    def plan(self, tool_registry: dict) -> PlanRecipe:
        context = self.manifest.to_prompt_context()
        weights = self.manifest.get_distribution_weights()
        recent_tasks = self.manifest.get_recent_tasks(n=10)
        total_cycles = self.manifest.get_total_cycles()

        try:
            entity_order = self.manifest.get_topological_order()
        except Exception:
            entity_order = []

        write_tools = [
            name for name, spec in tool_registry.items()
            if self.manifest.get_tool_kind(name) != "read"
        ]

        if self.enable_coverage:
            coverage_window = max(10, len(write_tools) * 2)
            coverage = self.manifest.get_intent_coverage(coverage_window)
            gap_intents = [t for t in write_tools if coverage.get(t, 0) == 0]
        else:
            coverage_window = 0
            coverage = {}
            gap_intents = []
            print("  [coverage] enforcement disabled — skipping gap_intents override", flush=True)

        priors_text = self._load_priors_text()
        heuristics = self.manifest.get_heuristics()
        prompt = self._build_prompt(
            context, weights, entity_order, tool_registry,
            recent_tasks, priors_text, coverage, coverage_window, gap_intents,
            heuristics=heuristics,
        )
        recipe = self._call_llm(prompt, entity_order, weights)

        # Hard override: if there are uncovered intents and we're past the
        # initial entity-building phase, force-select the first gap intent and
        # ask the LLM only for a concrete task_description.
        # Skipped when enable_coverage=False.
        if (
            self.enable_coverage
            and gap_intents
            and total_cycles >= len(write_tools)
            and recipe.intent_name not in gap_intents
        ):
            forced = gap_intents[0]
            forced_prompt = self._build_forced_prompt(forced, tool_registry, recent_tasks)
            recipe = self._call_llm_forced(forced, forced_prompt, entity_order, weights)

        return recipe

    def _load_priors_text(self) -> str:
        if not self.env_name:
            return ""
        try:
            import importlib
            mod = importlib.import_module(f"synthesize.environments.{self.env_name}.quality_priors")
            priors = None
            for attr in dir(mod):
                upper = attr.upper()
                if upper.endswith("_QUALITY_PRIORS") and "PAIRWISE" not in upper and "PROCESS" not in upper:
                    priors = getattr(mod, attr)
                    break
            if not priors:
                return ""
            lines = ["Reference distribution targets (your task parameters should help achieve these):"]
            for table, fields in priors.items():
                for col, spec in fields.items():
                    if spec.get("type") == "categorical":
                        dist_str = ", ".join(f"{k}={v:.0%}" for k, v in spec["distribution"].items())
                        lines.append(f"  {table}.{col}: {dist_str}")
            return "\n".join(lines)
        except Exception:
            return ""

    def _build_prompt(
        self,
        context: str,
        weights: dict[str, float],
        entity_order: list[str],
        tool_registry: dict,
        recent_tasks: list[dict] | None = None,
        priors_text: str = "",
        coverage: dict[str, int] | None = None,
        coverage_window: int = 10,
        gap_intents: list[str] | None = None,
        heuristics: list[dict] | None = None,
    ) -> str:
        write_tools = [
            name
            for name, spec in tool_registry.items()
            if self.manifest.get_tool_kind(name) != "read"
        ]
        weight_str = (
            "\n".join(f"  {k}: {v:.2f}" for k, v in sorted(weights.items(), key=lambda x: -x[1]))
            if weights
            else "  (no priors recorded yet)"
        )

        history_section = ""
        if recent_tasks:
            lines = [
                f"  Cycle {t['cycle']}: [{t['intent']}] {t['desc']}"
                for t in recent_tasks
            ]
            history_section = (
                "\nRecent task history (last " + str(len(recent_tasks)) + " cycles):\n"
                + "\n".join(lines)
                + "\n"
            )

        priors_section = f"\n{priors_text}\n" if priors_text else ""

        # Coverage section — show every write tool with its usage count and flag gaps
        coverage_lines = []
        if coverage is not None:
            for t in write_tools:
                count = coverage.get(t, 0)
                flag = "  ← UNCOVERED, MUST USE NEXT" if count == 0 else ""
                coverage_lines.append(f"  {t}: {count} uses in last {coverage_window} cycles{flag}")
        coverage_section = (
            "\nWrite operation coverage (last {} cycles):\n".format(coverage_window)
            + "\n".join(coverage_lines)
            + "\n"
        ) if coverage_lines else ""

        gap_instruction = (
            "- Distribution gap: compare the reference priors above to recent task history "
            "to identify which parameter values are underrepresented (e.g. if recent tasks "
            "only used t2.micro, target t2.large or t2.medium next). Specify exact target "
            "values in task_description."
            if priors_text
            else "- Which entities or attribute values are missing or underrepresented?"
        )

        if gap_intents:
            diversity_instruction = (
                f"- **COVERAGE REQUIREMENT**: The following write operations have NOT been used "
                f"in the last {coverage_window} cycles and MUST be prioritized: "
                f"{', '.join(gap_intents)}. Choose one of these unless entity prerequisites "
                f"genuinely do not exist yet."
            )
        elif recent_tasks:
            diversity_instruction = (
                "- Workflow diversity: avoid repeating the same intent with the same parameters "
                "as recent tasks — vary operation type, entity attributes, or workflow branch."
            )
        else:
            diversity_instruction = "- Which operation would most improve data diversity?"

        heuristics_section = ""
        if heuristics:
            lines = ["Execution tips learned from previous runs (YOU MUST embed these into "
                     "task_description so the execute agent follows them):"]
            for h in heuristics:
                lines.append(f"  - {h['pattern_name']}: {h['description']}")
            heuristics_section = "\n".join(lines) + "\n"

        return f"""\
You are planning the next data population task.

{context}
{priors_section}{coverage_section}
Available write operations: {", ".join(write_tools) or "(none classified yet)"}
Suggested intent frequency weights:
{weight_str}

Entity creation order (if known): {" → ".join(entity_order) or "(not determined)"}
{history_section}
{heuristics_section}Choose a task to perform next. The task may chain 2–4 write operations that form a \
natural workflow (preferred when it produces more realistic data). Examples of well-formed tasks \
(note: attribute targets are specific, but entity references are generic — agent finds IDs from DB):
  - "Launch a t2.large instance in eu-central-1 for any account that has an existing VPC there, \
tag it with env=prod, then stop it"
  - "Book a round-trip business class flight for any gold-tier user, selecting whatever routes \
are available"
  - "Find an active economy reservation and upgrade it to business class"
  - "Submit a job application for any open requisition, advance it to interview stage, then reject it"

Consider:
{gap_instruction}
{diversity_instruction}
- Follow the entity creation order — don't create child entities before their parents.
- Make task_description concrete for **attribute distributions**: specify target values \
like cabin class, instance type, status, or amount that align with the distribution targets \
above. Do NOT hardcode specific entity IDs, user IDs, routes, dates, flight numbers, or \
foreign-key values — the execute agent must discover those by querying the live database. \
Say "find a user with an economy reservation" not "user reg_iris_9 with reservation 88EDAF"; \
say "book a round-trip business class flight" not "book JFK→LAX on 2025-06-12".

Respond with a JSON object:
{{
  "intent_name": "<primary operation name, or a short workflow label>",
  "reasoning": "<why this task and which distribution gaps it addresses>",
  "task_description": "<concrete multi-step task with target attribute values but generic entity references — the agent discovers specific IDs from the DB>"
}}
"""

    def _build_forced_prompt(self, forced_intent: str, tool_registry: dict, recent_tasks: list[dict] | None) -> str:
        """Prompt for generating a task_description for a forced intent."""
        tool_desc = tool_registry.get(forced_intent, {}).get("description", "")
        history = ""
        if recent_tasks:
            history = "Recent tasks for context:\n" + "\n".join(
                f"  [{t['intent']}] {t['desc'][:80]}" for t in recent_tasks[-5:]
            )
        return f"""\
You must generate a concrete task using the operation: {forced_intent}

Tool description: {tool_desc}

{history}

Write a specific, realistic task_description for {forced_intent} that:
- Specifies target attribute values (types, statuses, amounts, class) that make the task
  concrete and diverse
- Does NOT hardcode specific entity IDs, user IDs, routes, dates, or foreign-key values —
  the agent must discover those by querying the live database
- May chain 1–3 related write operations if that makes the task more realistic
- Differs from recent tasks in its attribute targets (not just different IDs)

Respond with JSON:
{{
  "reasoning": "<why this specific task>",
  "task_description": "<concrete task with attribute targets but generic entity references>"
}}
"""

    def _call_llm_forced(
        self,
        forced_intent: str,
        prompt: str,
        entity_order: list[str],
        weights: dict[str, float],
    ) -> PlanRecipe:
        """Call LLM to generate a task_description for a pre-selected intent."""
        base_url = os.environ["SYNTHESIZE_PROXY_BASE_URL"].rstrip("/")
        model = os.environ["SYNTHESIZE_MODEL"]
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }).encode()
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
            content = resp["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                lines = content.splitlines()
                content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            parsed = json.loads(content)
        except Exception as exc:
            raise RuntimeError(f"PlanningPhase forced LLM call failed: {exc}") from exc

        return PlanRecipe(
            intent_name=forced_intent,
            entity_creation_order=entity_order,
            distribution_targets=weights,
            reasoning=parsed.get("reasoning", f"Coverage enforcement: {forced_intent} was uncovered"),
            task_description=parsed.get("task_description", f"Use {forced_intent} to populate data."),
        )

    def _call_llm(
        self,
        prompt: str,
        entity_order: list[str],
        weights: dict[str, float],
    ) -> PlanRecipe:
        base_url = os.environ["SYNTHESIZE_PROXY_BASE_URL"].rstrip("/")
        model = os.environ["SYNTHESIZE_MODEL"]

        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            }
        ).encode()
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
            content = resp["choices"][0]["message"]["content"].strip()
            # Strip markdown code fences if present
            if content.startswith("```"):
                lines = content.splitlines()
                content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            parsed = json.loads(content)
        except Exception as exc:
            raise RuntimeError(f"PlanningPhase LLM call failed: {exc}") from exc

        return PlanRecipe(
            intent_name=parsed.get("intent_name", "UNKNOWN"),
            entity_creation_order=entity_order,
            distribution_targets=weights,
            reasoning=parsed.get("reasoning", ""),
            task_description=parsed.get(
                "task_description", "Populate data using available write tools."
            ),
        )
