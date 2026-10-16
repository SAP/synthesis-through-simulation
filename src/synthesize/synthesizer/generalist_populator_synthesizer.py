"""
GeneralistPopulatorSynthesizer — Synthesizer adapter for GeneralistPopulator.

Wraps GeneralistPopulator (the 3-phase explore/plan/execute agent) in the
standard Synthesizer interface so it is auto-discovered by synthesis_runner.py
and available as --synthesizer generalist_populator.

The manifest is persisted at .runs/exploration/<env>/manifest.db across runs.
After each run the manifest is visualized as PNG + Mermaid and saved alongside
the exploration manifest for inspection.
"""

from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path

from synthesize.synthesizer.base import SynthesisResult, Synthesizer

# Maps environment slug → synthesizer module that exports TOOL_REGISTRY
_ENV_TO_MODULE: dict[str, str] = {
    "airline": "airline_synthesizer",
    "hr": "agent_synthesizer",
    "it_management": "it_synthesizer",
    "retail": "retail_synthesizer",
    "banking": "banking_synthesizer",
    "ecommerce": "ecommerce_synthesizer",
    "pharmacy": "pharmacy_synthesizer",
    "forum": "forum_synthesizer",
    "university": "university_synthesizer",
    "cloud": "cloud_synthesizer",
    "obfuscated_airline": "obfuscated_airline_synthesizer",
}


def _get_env_slug() -> str:
    """Return the active environment slug from synthesis_runner._ENV."""
    try:
        from synthesize import synthesis_runner

        return synthesis_runner._ENV or "airline"
    except Exception:
        return "airline"


def _load_tool_registry(env_slug: str) -> dict:
    """Dynamically load TOOL_REGISTRY for the given environment slug."""
    module_name = _ENV_TO_MODULE.get(env_slug, "airline_synthesizer")
    mod = importlib.import_module(f"synthesize.synthesizer.{module_name}")
    return mod.TOOL_REGISTRY


class GeneralistPopulatorSynthesizer(Synthesizer):
    """
    Synthesizer adapter for GeneralistPopulator.

    Explore/plan/execute loop: the agent classifies tools, infers entity
    dependencies, estimates distributions, then populates the DB — all without
    hardcoded intent definitions.

    Works across all supported environments by loading the active environment's
    TOOL_REGISTRY at run time.
    """

    name = "generalist_populator"
    description = "Domain-agnostic 3-phase agent (explore → plan → execute)"
    supports_batch = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        pass  # --explore-mode and --explore-runs are added globally by the runner

    def params_from_args(self, args: argparse.Namespace) -> dict:
        return {
            "explore_mode": getattr(args, "explore_mode", "staged"),
            "explore_runs": getattr(args, "explore_runs", 5),
            "enable_heuristics": not getattr(args, "no_heuristics", False),
            "enable_plan": not getattr(args, "no_plan", False),
            "enable_coverage": not getattr(args, "no_coverage", False),
        }

    def sample_params(self, **kwargs) -> dict:
        return {
            "explore_mode": kwargs.get("explore_mode", "staged"),
            "explore_runs": kwargs.get("explore_runs", 5),
            "enable_heuristics": kwargs.get("enable_heuristics", True),
            "enable_plan": kwargs.get("enable_plan", True),
            "enable_coverage": kwargs.get("enable_coverage", True),
        }

    def run(self, params: dict) -> SynthesisResult:
        from dotenv import load_dotenv

        from synthesize.exploration.manifest import ExplorationManifest
        from synthesize.synthesizer._llm import build_chat_model
        from synthesize.synthesizer.generalist_populator import GeneralistPopulator
        from synthesize.write_tools import count_successful_writes

        load_dotenv()

        env_slug = _get_env_slug()
        tool_registry = _load_tool_registry(env_slug)

        # Resolve manifest path (.runs/exploration/<env>/manifest.db)
        pkg_parent = Path(__file__).parents[3]
        runs_dir = (
            (pkg_parent / ".runs")
            if (pkg_parent / "pyproject.toml").exists()
            else (Path.cwd() / ".runs")
        )
        manifest_dir = runs_dir / "exploration" / env_slug
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / "manifest.db"

        _temperature = float(os.environ.get("SYNTHESIZE_TEMPERATURE", "1.0"))
        model = build_chat_model(temperature=_temperature)

        callbacks = []
        if all(
            k in os.environ
            for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
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
        agent = GeneralistPopulator(
            tool_registry=tool_registry,
            manifest=manifest,
            model=model,
            explore_mode=params.get("explore_mode", "staged"),
            explore_runs=params.get("explore_runs", 5),
            callbacks=callbacks,
            env_name=env_slug,
            enable_heuristics=params.get("enable_heuristics", True),
            enable_plan=params.get("enable_plan", True),
            enable_coverage=params.get("enable_coverage", True),
        )
        print(
            f"[GP config] env={env_slug} explore_mode={params.get('explore_mode', 'staged')} "
            f"explore_runs={params.get('explore_runs', 5)} "
            f"enable_heuristics={params.get('enable_heuristics', True)} "
            f"enable_plan={params.get('enable_plan', True)} "
            f"enable_coverage={params.get('enable_coverage', True)}",
            flush=True,
        )
        agent.register_tools()

        try:
            result = agent.run()
        finally:
            # Save manifest visualization after every run (best-effort)
            try:
                manifest.visualize(manifest_dir / "manifest_graph.png")
                mermaid_content = f"```mermaid\n{manifest.to_mermaid()}\n```\n"
                (manifest_dir / "manifest_graph.md").write_text(mermaid_content)
            except Exception:
                pass
            manifest.close()

        tool_calls = [tc.model_dump() for tc in result.tool_calls]
        error_count = sum(1 for tc in result.tool_calls if tc.is_error)
        successful_writes = count_successful_writes(tool_calls, env_slug)
        trajectory = {
            "run_id": result.run_id,
            "intent_name": result.intent_name,
            "task_description": result.task_description,
            "tool_calls": tool_calls,
            "final_message": result.final_message,
            "total_steps": len(tool_calls),
            "error_count": error_count,
            "successful_writes": successful_writes,
            # A trajectory succeeds if it ran cleanly and populated real data.
            "success": error_count == 0 and successful_writes >= 1,
        }
        return SynthesisResult(
            synthesizer=self.name,
            params=params,
            trajectories=[trajectory],
        )
