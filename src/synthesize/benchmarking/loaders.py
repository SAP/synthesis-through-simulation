"""
Data loaders for the benchmarking module.

load_from_local()   — scan .runs/ directories, load trajectories.jsonl + report.json
load_from_langfuse() — fetch dataset items from a Langfuse dataset

Both return list[DatasetItem] — uniform interface for compute_metrics().
"""

from __future__ import annotations

import json
from pathlib import Path

from synthesize.models import (
    CheckResult,
    DatasetItem,
    DatasetItemInput,
    DatasetItemMetadata,
    Step,
    ValidationSummary,
)


def load_from_local(
    runs_dir: Path,
    run_dir: Path | None = None,
    env: str | None = None,
    intent: str | None = None,
    mode: str | None = None,
) -> list[DatasetItem]:
    """Load DatasetItems from local .runs/ directories.

    If run_dir is provided, load only that specific run.
    Otherwise, scan runs_dir for directories matching env/intent/mode filters.
    """
    if run_dir is not None:
        return _load_run_dir(run_dir)

    if not runs_dir.exists():
        return []

    items: list[DatasetItem] = []
    for d in sorted(runs_dir.iterdir()):
        if not d.is_dir():
            continue
        # Skip benchmark result directories
        if "benchmark" in d.name:
            continue
        # Apply env filter: directory name starts with "<env>_"
        if env and not d.name.startswith(f"{env}_"):
            continue
        # Apply intent/mode filters: read from report.json for precise matching.
        # Directory-name substring checks are unreliable — intent names can share prefixes
        # (e.g. "FILE" is a substring of "FILE_TICKET"), and env/intent contain underscores.
        # The label field in report.json has format "{intent}_{mode}".
        if intent or mode:
            _report_path = d / "report.json"
            if not _report_path.exists():
                continue
            try:
                _label = json.loads(_report_path.read_text()).get("label", "")
            except Exception:
                continue
            if mode and not _label.endswith(f"_{mode}"):
                continue
            if intent:
                # Strip mode suffix to get the intent portion for exact comparison.
                _intent_label = _label
                for _sfx in ("_blind", "_informed"):
                    if _intent_label.lower().endswith(_sfx):
                        _intent_label = _intent_label[: -len(_sfx)]
                        break
                if _intent_label.upper() != intent.upper():
                    continue
        items.extend(_load_run_dir(d))

    return items


def _load_run_dir(run_dir: Path) -> list[DatasetItem]:
    """Load all DatasetItems from a single run directory."""
    traj_path = run_dir / "trajectories.jsonl"
    report_path = run_dir / "report.json"

    if not traj_path.exists():
        return []

    report: dict = {}
    if report_path.exists():
        report = json.loads(report_path.read_text())

    validation_summary = _parse_validation_summary(report)
    run_name = report.get("run_name", run_dir.name)
    ts = report.get("timestamp", "")

    items = []
    with open(traj_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            traj = json.loads(line)
            # GP synthesizer saves {run_id, tool_calls, final_message} — normalise to agent format
            if "intent" not in traj and "tool_calls" in traj:
                traj = {
                    "intent": "POPULATE",
                    "mode": report.get("label", "").split("_")[-1] or "informed",
                    "params": {},
                    "success": True,
                    "postconditions": {},
                    "total_steps": len(traj["tool_calls"]),
                    "error_count": sum(1 for tc in traj["tool_calls"] if tc.get("is_error")),
                    "recovery_count": 0,
                    "steps": traj["tool_calls"],
                }
            if "intent" not in traj:
                continue
            item = DatasetItem(
                input=DatasetItemInput(
                    intent=traj["intent"],
                    mode=traj.get("mode", ""),
                    params=traj.get("params", {}),
                    steps=[Step(**s) for s in traj.get("steps", [])],
                ),
                metadata=DatasetItemMetadata(
                    env=report.get("env", ""),
                    synthesizer=report.get("synthesizer", ""),
                    run_name=run_name,
                    timestamp=ts,
                    success=traj.get("success", False),
                    total_steps=traj.get("total_steps", 0),
                    error_count=traj.get("error_count", 0),
                    recovery_count=traj.get("recovery_count", 0),
                    postconditions=traj.get("postconditions", {}),
                    validation_summary=validation_summary,
                ),
            )
            items.append(item)

    return items


def _parse_validation_summary(report: dict) -> ValidationSummary | None:
    summary = report.get("summary")
    if not summary:
        return None
    checks = [
        CheckResult(
            category=c.get("category", ""),
            rule=c.get("rule", ""),
            passed=c.get("status") == "PASS",
            violation_count=c.get("violation_count", 0),
        )
        for c in report.get("checks", [])
    ]
    return ValidationSummary(
        total_checks=summary.get("total_checks", 0),
        passed=summary.get("passed", 0),
        failed=summary.get("failed", 0),
        checks=checks,
    )


def load_from_langfuse(dataset_name: str) -> list[DatasetItem]:
    """Fetch all items from a Langfuse dataset. Returns [] if Langfuse is unavailable."""
    try:
        from langfuse import Langfuse
    except ImportError:
        print("langfuse not installed. Install with: uv pip install -e '.[langfuse]'")
        return []

    import os

    from dotenv import load_dotenv

    load_dotenv()
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    if not public_key:
        print("LANGFUSE_PUBLIC_KEY not set in .env")
        return []

    lf = Langfuse(
        public_key=public_key,
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    dataset = lf.get_dataset(dataset_name)
    return [_parse_langfuse_item(raw) for raw in dataset.items]


def _parse_langfuse_item(raw) -> DatasetItem:
    """Parse a single Langfuse dataset item into a DatasetItem."""
    inp = raw.input or {}
    meta = raw.metadata or {}

    vs_data = meta.get("validation_summary")
    validation_summary = None
    if vs_data:
        checks = [CheckResult(**c) for c in vs_data.get("checks", [])]
        validation_summary = ValidationSummary(
            total_checks=vs_data.get("total_checks", 0),
            passed=vs_data.get("passed", 0),
            failed=vs_data.get("failed", 0),
            checks=checks,
        )

    return DatasetItem(
        input=DatasetItemInput(
            intent=inp.get("intent", ""),
            mode=inp.get("mode", ""),
            params=inp.get("params", {}),
            steps=[Step(**s) for s in inp.get("steps", [])],
        ),
        metadata=DatasetItemMetadata(
            env=meta.get("env", ""),
            synthesizer=meta.get("synthesizer", ""),
            run_name=meta.get("run_name", ""),
            timestamp=meta.get("timestamp", ""),
            success=meta.get("success", False),
            total_steps=meta.get("total_steps", 0),
            error_count=meta.get("error_count", 0),
            recovery_count=meta.get("recovery_count", 0),
            postconditions=meta.get("postconditions", {}),
            validation_summary=validation_summary,
        ),
    )
