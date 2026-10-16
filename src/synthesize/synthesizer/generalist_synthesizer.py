"""
Generalist synthesizer for goal-directed data population.

GeneralistSynthesizer takes bootstrap intents and a tool registry and produces
an agent that:

  Phase 1 — Planning
    Calls read APIs to observe the current DB state, then selects the most
    appropriate intent from its library or proposes a new one.

  Phase 2 — Execution
    Executes the chosen intent via API calls. In blind mode the agent learns
    business rules from API error responses. In informed mode it has the full
    rules for each intent. In evolve mode, rules accumulate across runs as the
    agent builds up an IntentLibrary over time.

Three-way ablation design:
  blind   — briefs only, no rules, no cross-run learning
  informed — full bootstrap informed_rules, no cross-run learning
  evolve  — starts with briefs only; every N runs, an LLM extracts new rules
             from accumulated trajectories and updates the IntentLibrary so
             subsequent runs see progressively richer prompts.

Unlike directed synthesizers, the agent is not pre-assigned an intent — it
decides each run based on what the database currently needs.

Domain-agnostic: instantiate with any environment's tool registry and intents.
Subclasses override _infer_intent_from_steps() and _init_evolution() to wire
in environment-specific intent inference and evolution storage paths.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from synthesize.synthesizer.agent_synthesizer import IntentDef, Step, Trajectory
from synthesize.synthesizer.base import SynthesisResult
from synthesize.synthesizer.default_agent import (
    DefaultAgentSynthesizer,
    _make_client,
    run_agent,
)

if TYPE_CHECKING:
    from synthesize.evolution.engine import EvolutionEngine
    from synthesize.evolution.models import IntentLibrary

# Tool name prefixes that indicate read-only operations.
# Used to determine whether the agent executed a write during a run.
_READ_PREFIXES = ("get_", "list_", "search_", "find_", "calculate")


def _write_executed(steps: List[Step]) -> bool:
    """Return True if at least one successful write API call exists in steps."""
    return any(
        not s.is_error and not any(s.tool.startswith(p) for p in _READ_PREFIXES) for s in steps
    )


class GeneralistSynthesizer(DefaultAgentSynthesizer):
    """
    Domain-agnostic goal-directed synthesizer with optional evolve mode.

    Provide bootstrap_intents (dict of IntentDef) and a full tool_registry.
    The agent observes current DB state via read APIs, selects an intent, and
    executes it — all within one trajectory.

    In blind mode:   only intent names and briefs are shown; rules are learned
                     from API error responses during execution.
    In informed mode: full rules for every intent are included in the prompt.
    In evolve mode:  starts like blind, but every `evolve_every` runs the engine
                     extracts new rules from accumulated trajectories and updates
                     the IntentLibrary so later runs see progressively richer prompts.

    Evolution is lazily initialized on the first evolve-mode run. Subclasses
    must override _init_evolution() to supply environment-specific storage paths.
    """

    # Subclasses override this to map intent names → their write-tool sets.
    # Used to infer which intent the agent executed from its tool calls.
    # { "INTENT_NAME": {"write_tool_a", "write_tool_b"}, ... }
    INTENT_TO_WRITE_TOOLS: Dict[str, set] = {}

    def __init__(
        self,
        name: str,
        description: str,
        tool_registry: Dict[str, dict],
        bootstrap_intents: Dict[str, IntentDef],
        env_name: str = "enterprise",
        # Evolution fields — None means evolution is not active
        intent_library: Optional["IntentLibrary"] = None,
        evolution_engine: Optional["EvolutionEngine"] = None,
        evolve_every: int = 5,
        library_path: Optional[Path] = None,
    ) -> None:
        self.bootstrap_intents = bootstrap_intents
        self.intent_library = intent_library
        self.evolution_engine = evolution_engine
        self.evolve_every = evolve_every
        self.library_path = library_path
        self._run_count = (
            0  # counts evolve-mode runs; triggers extraction at multiples of evolve_every
        )

        # Build a single meta-intent that owns all tools and acts as the
        # registered entry point for the batch runner.
        all_tools = list(tool_registry.keys())
        meta_intent = IntentDef(
            name="POPULATE",
            brief="Populate the database with realistic, diverse data by selecting and executing an appropriate intent.",
            informed_rules="",  # unused — system prompt is built by _build_generalist_prompt
            tools=all_tools,
            sampler=lambda: {},  # agent self-directs; no pre-selection needed
            task_prompt=lambda p: (
                "Observe the current state of the database using the available read APIs. "
                "Based on what you find, select the most appropriate intent from your library "
                "or propose a new one. Then execute it."
            ),
            postconditions=lambda p, steps: {"write_executed": _write_executed(steps)},
        )

        super().__init__(
            name=name,
            description=description,
            tool_registry=tool_registry,
            intents={"POPULATE": meta_intent},
            env_name=env_name,
        )

    # ── CLI ───────────────────────────────────────────────────────────────────

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        try:
            parser.add_argument(
                "--intent",
                help="Intent to run (ignored for generalist synthesizers — agent self-selects).",
            )
        except argparse.ArgumentError:
            pass
        try:
            parser.add_argument(
                "--mode",
                choices=["blind", "informed", "evolve"],
                default="blind",
                help=(
                    "blind: no rules in prompt; "
                    "informed: full bootstrap rules; "
                    "evolve: blind start, rules accumulate across runs (default: blind)"
                ),
            )
        except argparse.ArgumentError:
            pass
        try:
            parser.add_argument(
                "--evolve-every",
                type=int,
                default=5,
                dest="evolve_every",
                help="In evolve mode: run LLM rule extraction every N trajectories (default: 5).",
            )
        except argparse.ArgumentError:
            pass

    def params_from_args(self, args: argparse.Namespace) -> dict:
        params = super().params_from_args(args)
        params["evolve_every"] = getattr(args, "evolve_every", 5)
        return params

    # ── System prompt ─────────────────────────────────────────────────────────

    def _build_generalist_prompt(self, mode: str) -> str:
        """Build the two-phase system prompt from the current intent library."""
        goal = (
            "Your purpose is to populate a realistic enterprise database with diverse, "
            "high-quality synthetic data through API interactions only — no direct database access.\n\n"
        )

        phases = (
            "You operate in two phases each run:\n\n"
            "Phase 1 — Planning:\n"
            "  • Call read APIs to observe the current state of the database.\n"
            "  • Review the intent library below.\n"
            "  • Select the most appropriate intent to execute, or propose a new intent\n"
            "    if the database needs an operation not yet in the library.\n"
            "  • State your chosen intent clearly before proceeding.\n\n"
            "Phase 2 — Execution:\n"
            "  • Execute the chosen intent using the available APIs.\n"
        )

        if mode in ("blind", "evolve"):
            phases += (
                "  • You have no prior knowledge of business rules — learn from API\n"
                "    error responses and adjust your approach accordingly.\n"
                "  • Note patterns in failures: they reveal constraints that apply to\n"
                "    future runs as well.\n\n"
            )
        else:  # informed
            phases += (
                "  • Apply the rules for your chosen intent precisely.\n"
                "  • Vary your parameter choices to maximise dataset diversity.\n\n"
            )

        library = self._format_intent_library(mode)

        return (
            goal
            + phases
            + "Intent Library:\n\n"
            + library
            + "\n\nWhen you have successfully completed the operation, say 'TASK COMPLETE' and stop."
        )

    def _format_intent_library(self, mode: str) -> str:
        """Format all intents for the system prompt.

        In evolve mode: reads from IntentLibrary (original + learned rules for
        intents with confidence >= 0.8).
        In blind/informed: reads from static bootstrap_intents.
        """
        if mode == "evolve" and self.intent_library is not None:
            parts = []
            for name, evolved in self.intent_library.intents.items():
                entry = f"**{name}**: {evolved.brief}"
                rules = evolved.informed_rules  # property: original + learned (conf >= 0.8)
                if rules:
                    entry += f"\nRules:\n{rules}"
                parts.append(entry)
            return "\n\n".join(parts)

        # blind / informed: use static bootstrap_intents
        parts = []
        for name, intent in self.bootstrap_intents.items():
            entry = f"**{name}**: {intent.brief}"
            if mode == "informed" and intent.informed_rules:
                entry += f"\nRules:\n{intent.informed_rules}"
            parts.append(entry)
        return "\n\n".join(parts)

    # ── Intent inference ──────────────────────────────────────────────────────

    def _infer_intent_from_steps(self, steps: List[Step]) -> str:
        """Infer which intent the agent executed from its write tool calls.

        Scores each intent in INTENT_TO_WRITE_TOOLS by how many of its write
        tools appear among the trajectory's successful steps. Returns the
        highest-scoring intent name, or "UNKNOWN" if nothing matches.

        Subclasses must populate INTENT_TO_WRITE_TOOLS for this to be useful.
        """
        if not self.INTENT_TO_WRITE_TOOLS:
            return "UNKNOWN"
        called = {s.tool for s in steps if not s.is_error}
        scores = {
            intent: len(tools & called) for intent, tools in self.INTENT_TO_WRITE_TOOLS.items()
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "UNKNOWN"

    # ── Evolution ─────────────────────────────────────────────────────────────

    def _init_evolution(self) -> None:
        """Initialize the evolution engine and intent library.

        Called lazily on the first evolve-mode run if evolution_engine is None.
        Subclasses must override this to supply environment-specific paths and
        set self.evolution_engine, self.intent_library, and self.library_path.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must override _init_evolution() to support evolve mode. "
            "Set self.evolution_engine, self.intent_library, and self.library_path."
        )

    def _record_and_evolve(self, traj: Trajectory) -> None:
        """Record a trajectory and trigger rule extraction every evolve_every runs."""
        assert self.evolution_engine is not None
        assert self.intent_library is not None

        # Infer the real intent from the agent's tool calls and stamp it on the trajectory
        inferred = self._infer_intent_from_steps(traj.steps)
        traj.intent = inferred

        self.evolution_engine.record_trajectory(traj, self.intent_library)
        self._run_count += 1

        if self._run_count % self.evolve_every == 0:
            evolved_intent = self.intent_library.get_intent(inferred)
            if evolved_intent is not None:
                changes = self.evolution_engine.evolve_intent(evolved_intent)
                new_rules = changes.get("rules_added", 0)
                updated = changes.get("rules_updated", 0)
                print(
                    f"  [evolve] run {self._run_count}: {inferred} "
                    f"+{new_rules} rules, ~{updated} updated"
                )
            if self.library_path is not None:
                self.intent_library.save(self.library_path)

    # ── Run override ──────────────────────────────────────────────────────────

    def run(self, params: dict) -> SynthesisResult:
        mode = params.get("mode", "blind")

        # Lazy evolution init on first evolve-mode call
        if mode == "evolve" and self.evolution_engine is None:
            self._init_evolution()
            # Propagate evolve_every from params if provided
            if "evolve_every" in params:
                self.evolve_every = int(params["evolve_every"])

        intent_def = self.intents["POPULATE"]
        run_params = {}

        client = _make_client()
        system_prompt = self._build_generalist_prompt(mode)

        traj = run_agent(
            intent_def,
            run_params,
            mode if mode != "evolve" else "blind",  # LLM sees "blind" prompt style in evolve mode
            client,
            self.tool_registry,
            self.env_name,
            system_prompt=system_prompt,
        )

        # In evolve mode: record trajectory and conditionally trigger rule extraction
        if mode == "evolve" and self.evolution_engine is not None:
            self._record_and_evolve(traj)

        return SynthesisResult(
            synthesizer=self.name,
            params={**params, "run_params": run_params},
            trajectories=[traj.to_dict()],
        )

    def sample_params(
        self, intent: Optional[str] = None, mode: str = "blind", **kwargs
    ) -> Optional[dict]:
        # Intent is always POPULATE — the agent selects the real intent itself
        evolve_every = kwargs.get("evolve_every", self.evolve_every)
        return {"intent": "POPULATE", "mode": mode, "run_params": {}, "evolve_every": evolve_every}
