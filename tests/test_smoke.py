"""Offline smoke tests — no LLM / network required.

These cover the framework scaffolding: package imports, the proxy-aware model
builder's routing logic, the CLI entry point, and per-environment
setup + validation. Live Generalist Populator runs (which call an LLM) are not
exercised here.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

# Every shipped environment initializes from schema + reference data.
ALL_ENVS = [
    "airline", "banking", "cloud", "ecommerce", "forum", "hr",
    "it_management", "obfuscated_airline", "pharmacy", "retail", "university",
]

# Environments whose seed baseline validates with zero violations. `banking`
# and `university` intentionally ship a few pre-existing violations (realistic
# "messy" enterprise state the populator must not worsen), so they are excluded
# from the zero-violation assertion.
CLEAN_ENVS = ["airline", "ecommerce", "it_management", "forum", "pharmacy", "retail"]


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "synthesize.cli", *args],
        capture_output=True,
        text=True,
    )


def test_package_imports():
    import synthesize  # noqa: F401
    from synthesize import synthesis_runner  # noqa: F401
    from synthesize.exploration.manifest import ExplorationManifest  # noqa: F401
    from synthesize.synthesizer.generalist_populator import GeneralistPopulator  # noqa: F401


def test_resolve_llm_api_defaults(monkeypatch):
    from synthesize.synthesizer._llm import resolve_llm_api

    monkeypatch.delenv("SYNTHESIZE_LLM_API", raising=False)
    assert resolve_llm_api("claude-4.5-opus") == "anthropic"
    assert resolve_llm_api("gpt-4.1") == "openai"
    assert resolve_llm_api("gemini-2.5-pro") == "openai"


def test_resolve_llm_api_override(monkeypatch):
    from synthesize.synthesizer._llm import resolve_llm_api

    # An explicit override wins even for a claude-* model (proxy compatibility).
    monkeypatch.setenv("SYNTHESIZE_LLM_API", "openai")
    assert resolve_llm_api("claude-4.5-opus") == "openai"
    monkeypatch.setenv("SYNTHESIZE_LLM_API", "anthropic")
    assert resolve_llm_api("gpt-4.1") == "anthropic"


def test_cli_help():
    proc = _run("--help")
    assert proc.returncode == 0
    assert "synthesize" in proc.stdout


def test_list_synthesizers_discovers_gp():
    proc = _run("--env", "airline", "list-synthesizers")
    assert proc.returncode == 0
    assert "generalist_populator" in proc.stdout


@pytest.mark.parametrize("env", ALL_ENVS)
def test_setup(env):
    setup = _run("--env", env, "setup")
    assert setup.returncode == 0, setup.stderr


@pytest.mark.parametrize("env", CLEAN_ENVS)
def test_validate_clean(env):
    _run("--env", env, "setup")
    validate = _run("--env", env, "validate")
    assert validate.returncode == 0, validate.stdout + validate.stderr
