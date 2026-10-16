"""
Opt-in Langfuse dataset pusher.

Pushes synthesis run trajectories to Langfuse datasets for cross-run visibility,
comparison, and benchmarking. Silently no-ops if:
  - langfuse is not installed
  - LANGFUSE_PUBLIC_KEY is not set in the environment

One dataset per {env}_{intent}_{mode} (persistent, accumulates over time).
One dataset item per trajectory (one complete agent run / intent execution).

Install: uv pip install -e ".[langfuse]"
Configure: add LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY to .env
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from synthesize.models import (
    CheckResult,
    DatasetItem,
    DatasetItemInput,
    DatasetItemMetadata,
    Step,
    ValidationSummary,
)


def push_run_to_langfuse(
    trajectories: list[dict],
    report: dict,
    env: str,
    run_name: str,
    synthesizer: str,
) -> None:
    """Push trajectories to Langfuse datasets. No-op if LANGFUSE_PUBLIC_KEY is not set."""
    try:
        from langfuse import Langfuse
    except ImportError:
        return

    load_dotenv()
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    if not public_key:
        return

    lf = Langfuse(
        public_key=public_key,
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )

    ts = report.get("timestamp", "")
    validation_summary = None
    if report.get("summary"):
        summary = report["summary"]
        checks = [
            CheckResult(
                category=c.get("category", ""),
                rule=c.get("rule", ""),
                passed=c.get("status") == "PASS",
                violation_count=c.get("violation_count", 0),
            )
            for c in report.get("checks", [])
        ]
        validation_summary = ValidationSummary(
            total_checks=summary.get("total_checks", 0),
            passed=summary.get("passed", 0),
            failed=summary.get("failed", 0),
            checks=checks,
        )

    pushed = 0
    created_datasets: set[str] = set()
    for traj in trajectories:
        if "intent" not in traj:
            continue

        dataset_name = f"{env}_{traj['intent']}_{traj.get('mode', '')}"

        item = DatasetItem(
            input=DatasetItemInput(
                intent=traj["intent"],
                mode=traj.get("mode", ""),
                params=traj.get("params", {}),
                steps=[Step(**s) for s in traj.get("steps", [])],
            ),
            metadata=DatasetItemMetadata(
                env=env,
                synthesizer=synthesizer,
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

        if dataset_name not in created_datasets:
            lf.create_dataset(name=dataset_name)  # no-op if already exists
            created_datasets.add(dataset_name)
        lf.create_dataset_item(
            dataset_name=dataset_name,
            input=item.input.model_dump(),
            expected_output={"success": True},  # synthesis always targets success
            metadata=item.metadata.model_dump(),
        )
        pushed += 1

    if pushed:
        print(f"  Pushed {pushed} item(s) to Langfuse.")
