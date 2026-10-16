"""
Base class and result dataclass for all synthesizers.

To register a new synthesizer, create a module in synthesizer/ that defines
a concrete subclass of Synthesizer.  synthesis_runner.py auto-discovers it
at startup via pkgutil — no changes to the runner are needed.
"""

from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SynthesisResult:
    """Metadata returned by a synthesizer after populating the DB."""

    synthesizer: str
    params: Dict[str, Any]
    # Step-by-step trajectory records (agent synthesizer only).
    trajectories: Optional[List[dict]] = None


class Synthesizer(ABC):
    """
    Abstract base for all synthesizers.

    Subclass contract
    -----------------
    - Set ``name`` (used as the ``--synthesizer`` CLI value).
    - Set ``description`` (one-line, shown by ``list-synthesizers``).
    - Implement ``run(params)``.
    - Optionally override ``add_arguments``, ``params_from_args``,
      ``sample_params``, and ``list_intents``.
    """

    #: Short identifier, used as the ``--synthesizer`` CLI value.
    name: str
    #: One-line description shown by list-synthesizers.
    description: str
    #: Set to True for synthesizers that support the ``batch`` command
    #: (i.e. can be run N times against the same accumulating DB).
    supports_batch: bool = False

    # ── CLI integration ───────────────────────────────────────────────────────

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add synthesizer-specific CLI arguments to *parser*."""

    def params_from_args(self, args: argparse.Namespace) -> dict:
        """Extract this synthesizer's run params from parsed CLI *args*."""
        return {}

    # ── Sampling (used by the batch command) ──────────────────────────────────

    def sample_params(self, **kwargs) -> Optional[dict]:
        """
        Return a randomly-sampled params dict for one run, or None if no
        eligible records exist in the DB.  Used by the batch command to
        generate per-run params automatically.
        """
        return self.params_from_args(argparse.Namespace(**kwargs))

    # ── Core interface ────────────────────────────────────────────────────────

    @abstractmethod
    def run(self, params: dict) -> SynthesisResult:
        """
        Populate the working DB (``db.DB_PATH``) with synthetic data.

        The caller (synthesis_runner) is responsible for resetting the DB to
        a clean baseline before calling ``run()``.

        Returns a ``SynthesisResult`` with metadata about what was generated.
        """

    # ── Optional introspection ────────────────────────────────────────────────

    def list_intents(self) -> Optional[List[str]]:
        """Return supported intent names, or None if the concept doesn't apply."""
        return None
