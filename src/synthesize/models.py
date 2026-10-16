"""
Shared Pydantic models for synthesis run data.

These models are used by langfuse_pusher.py (writing to Langfuse datasets)
and benchmarking/ (reading from local .runs/ or Langfuse) to ensure
both sides agree on the data structure.

All models use extra="allow" (via _ExtensibleModel) so unknown fields pass
through without validation errors — forward-compatible as the schema evolves.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _ExtensibleModel(BaseModel):
    """Base class that silently accepts unknown fields (forward-compatible)."""

    model_config = ConfigDict(extra="allow")


class CheckResult(_ExtensibleModel):
    """Result of a single validation check."""

    category: str
    rule: str
    passed: bool
    violation_count: int


class Step(_ExtensibleModel):
    """A single tool call made by the agent during a trajectory."""

    tool: str  # API function name (e.g. "create_ticket", "assign_ticket")
    args: dict  # exact arguments passed — sufficient to replay the call
    result: dict | list | str | int | float | bool | None = None  # API return value or error message
    is_error: bool = False  # True if the API raised an exception (skip during DB reproduction)


class ValidationSummary(_ExtensibleModel):
    """Aggregated validation results for a synthesis run."""

    total_checks: int
    passed: int
    failed: int
    checks: list[CheckResult] = Field(
        default_factory=list
    )  # full per-check detail for per-check pass rates


class DatasetItemInput(_ExtensibleModel):
    """Input portion of a Langfuse dataset item — what the agent was given."""

    intent: str
    mode: str
    params: dict  # sampled scenario (e.g. {"ticket_id": "TKT-001", "raiser": {...}})
    steps: list[Step] = Field(default_factory=list)
    # One Step = one tool call: {tool, args, result, is_error}
    # Includes both read ops (list_employees) and write ops (create_ticket, ...)
    # DB reproduction: replay only non-error steps where tool is a write operation


class DatasetItemMetadata(_ExtensibleModel):
    """Metadata attached to each Langfuse dataset item."""

    env: str
    synthesizer: str
    run_name: str  # links back to .runs/<run_name>/
    timestamp: str  # run-level timestamp (trajectories don't carry per-item ts)
    success: bool  # True if all postconditions passed
    total_steps: int
    error_count: int
    recovery_count: int
    postconditions: dict[str, bool]
    validation_summary: ValidationSummary | None = None  # populated for local source


class DatasetItem(_ExtensibleModel):
    """A Langfuse dataset item representing one complete agent run."""

    input: DatasetItemInput
    expected_output: dict = Field(default_factory=lambda: {"success": True})
    metadata: DatasetItemMetadata
