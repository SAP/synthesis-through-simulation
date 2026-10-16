"""
Exploration package for GeneralistPopulator.

Provides:
- ExplorationManifest: persistent SQLite knowledge store (tools, entities, deps, distributions)
- PlanningPhase: distribution-aware intent scheduling
- build_execute_system_prompt, EXPLORE_SYSTEM_PROMPT: LLM prompts
"""

from .manifest import ExplorationManifest
from .planning import PlanningPhase, PlanRecipe
from .prompts import EXPLORE_SYSTEM_PROMPT, EXPLORE_USER_PROMPT, build_execute_system_prompt

__all__ = [
    "ExplorationManifest",
    "PlanningPhase",
    "PlanRecipe",
    "EXPLORE_SYSTEM_PROMPT",
    "EXPLORE_USER_PROMPT",
    "build_execute_system_prompt",
]
