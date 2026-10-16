"""
EnvScaler vs STS GP comparison runner for the Cloud Computing Platform.

Reads EnvScaler-generated task descriptions from scripts/envscaler_cloud_tasks.json,
runs each through our blind cloud agent, then computes DF and VPR on the resulting
DB snapshot.  Results are saved to scripts/envscaler_comparison_cloud_result.json.

Usage:
    python scripts/run_envscaler_comparison_cloud.py [--tasks scripts/envscaler_cloud_tasks.json]
                                                      [--n 20]
                                                      [--out scripts/envscaler_comparison_cloud_result.json]

Prerequisites:
    synthesize --env cloud setup && synthesize --env cloud snapshot
    python scripts/envscaler_gen_tasks_cloud.py
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Override model and endpoint — must happen before synthesizer imports
# since MODEL/PROXY_BASE_URL are read as module-level globals at import time.
os.environ["SYNTHESIZE_MODEL"] = "gpt-4.1"
os.environ["SYNTHESIZE_PROXY_BASE_URL"] = "http://localhost:4000"

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from synthesize.environments.cloud import validate as cloud_validate
from synthesize.environments.cloud.apis import cloud_apis
from synthesize.environments.cloud.db import cloud_db
from synthesize.environments.cloud.quality_priors import CLOUD_QUALITY_PRIORS
from synthesize.synthesizer.agent_synthesizer import IntentDef
from synthesize.synthesizer.cloud_synthesizer import TOOL_REGISTRY as CLOUD_TOOL_REGISTRY
from synthesize.synthesizer.default_agent import _make_client, run_agent

BASELINE_DB = cloud_db.DB_PATH.parent / "cloud_snapshot.db"

WRITE_TOOLS = {
    "launch_instance", "terminate_instance", "start_instance", "stop_instance",
    "create_security_group", "authorize_security_group_ingress", "authorize_security_group_egress",
    "create_vpc", "create_subnet", "register_custom_image",
    "modify_instance_attribute", "release_public_ip", "update_account_quota", "tag_resource",
}

ALL_TOOLS = list(CLOUD_TOOL_REGISTRY.keys())


# ── DF computation ─────────────────────────────────────────────────────────────

def _compute_df(snapshot_path: Path, baseline_path: Path) -> float:
    """Compute Distribution Fidelity by comparing new rows against reference distributions."""
    priors = CLOUD_QUALITY_PRIORS

    snap_conn = sqlite3.connect(str(snapshot_path))
    base_conn = sqlite3.connect(str(baseline_path))

    ln2 = math.log(2)
    similarities: list[float] = []

    for table, fields in priors.items():
        base_ids = {
            r[0] for r in base_conn.execute(f"SELECT rowid FROM {table}").fetchall()
        }
        # Use cursor description for col names (Python 3.13 sqlite3.Row rowid workaround)
        cur = snap_conn.execute(f"SELECT rowid, * FROM {table}")
        col_names = [d[0] for d in cur.description]
        new_rows = [
            dict(zip(col_names, row))
            for row in cur.fetchall()
            if row[0] not in base_ids
        ]
        if not new_rows:
            continue

        for col, spec in fields.items():
            col_values = [r[col] for r in new_rows if r.get(col) is not None]
            if not col_values:
                continue

            if spec["type"] == "categorical":
                ref_dist: dict[str, float] = spec["distribution"]
                observed: dict[str, int] = {}
                for v in col_values:
                    observed[str(v)] = observed.get(str(v), 0) + 1
                n = len(col_values)
                p_obs = {k: observed.get(k, 0) / n for k in ref_dist}
                m = {k: (p_obs[k] + ref_dist[k]) / 2 for k in ref_dist}

                def _kl(p: dict, q: dict) -> float:
                    s = 0.0
                    for k in p:
                        if p[k] > 0 and q[k] > 0:
                            s += p[k] * math.log(p[k] / q[k])
                    return s

                jsd = (_kl(p_obs, m) + _kl(ref_dist, m)) / 2
                similarities.append(1.0 - jsd / ln2)

    snap_conn.close()
    base_conn.close()
    return sum(similarities) / len(similarities) if similarities else 0.0


# ── VPR computation ────────────────────────────────────────────────────────────

def _compute_vpr(snapshot_path: Path) -> tuple[float, list[dict]]:
    cloud_validate.set_db(snapshot_path)
    results = cloud_validate.run(as_json=True)
    passed = sum(1 for r in results if r["status"] == "PASS")
    return passed / len(results) if results else 0.0, results


# ── Main runner ────────────────────────────────────────────────────────────────

def run_comparison(tasks_path: Path, n: int, out_path: Path) -> None:
    if not tasks_path.exists():
        print(f"ERROR: tasks file not found: {tasks_path}")
        print("Run: python scripts/envscaler_gen_tasks_cloud.py first.")
        sys.exit(1)

    if not BASELINE_DB.exists():
        print(f"ERROR: baseline DB not found: {BASELINE_DB}")
        print("Run: synthesize --env cloud setup && synthesize --env cloud snapshot")
        sys.exit(1)

    with open(tasks_path) as f:
        all_tasks = json.load(f)

    if len(all_tasks) < n:
        print(f"WARNING: only {len(all_tasks)} tasks available; running all of them.")
        n = len(all_tasks)

    tasks = all_tasks[:n]

    # ── Create run dir (compatible with compute_fidelity.py) ──────────────────
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = REPO_ROOT / ".runs" / f"cloud_envscaler_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Run dir: {run_dir}")

    baseline_db = run_dir / "baseline.db"
    working_db  = run_dir / "working.db"
    shutil.copy2(str(BASELINE_DB), str(baseline_db))
    shutil.copy2(str(BASELINE_DB), str(working_db))

    # Point cloud DB and API module at working copy
    cloud_db.DB_PATH = working_db
    cloud_apis.init_env(db_path=working_db)

    print(f"Running {n} EnvScaler tasks through blind cloud agent...")

    client = _make_client()
    trajectories = []
    traj_jsonl = run_dir / "trajectories.jsonl"

    with traj_jsonl.open("w") as traj_f:
        for i, task_item in enumerate(tasks):
            task_str = task_item["task"]
            task_id  = task_item.get("task_id", f"task_{i:03d}")
            print(f"\n[{i+1:2d}/{n}] {task_id}: {task_str[:80]}...")

            intent = IntentDef(
                name=task_id,
                brief=task_str[:80],
                informed_rules="",
                tools=ALL_TOOLS,
                sampler=lambda: {},
                task_prompt=lambda _, t=task_str: t,
                postconditions=lambda params, steps: {},
            )

            try:
                traj = run_agent(
                    intent_def=intent,
                    params={},
                    mode="blind",
                    client=client,
                    tool_registry=CLOUD_TOOL_REGISTRY,
                    env_name="cloud",
                )
                tool_calls = [{"tool": s.tool, "is_error": s.is_error, "result": s.result} for s in traj.steps]
                write_steps = [s for s in traj.steps if s.tool in WRITE_TOOLS]
                traj_dict = {
                    "task_id": task_id,
                    "task": task_str,
                    "success": traj.success,
                    "steps": len(traj.steps),
                    "tool_calls": tool_calls,
                    "errors": sum(1 for s in traj.steps if s.is_error),
                    "write_calls": len(write_steps),
                    "write_errors": sum(1 for s in write_steps if s.is_error),
                }
                trajectories.append(traj_dict)
                traj_f.write(json.dumps(traj_dict) + "\n")
                traj_f.flush()
                print(f"   steps={len(traj.steps)}, write_calls={traj_dict['write_calls']}, write_errors={traj_dict['write_errors']}")
            except Exception as e:
                print(f"   ERROR: {e}")
                err_dict = {"task_id": task_id, "task": task_str, "error": str(e), "tool_calls": []}
                trajectories.append(err_dict)
                traj_f.write(json.dumps(err_dict) + "\n")
                traj_f.flush()

    # snapshot.db = final state after all agent runs
    snapshot_db = run_dir / "snapshot.db"
    shutil.copy2(str(working_db), str(snapshot_db))

    print("\nComputing metrics...")
    df = _compute_df(snapshot_db, baseline_db)
    vpr, check_results = _compute_vpr(snapshot_db)

    base_conn = sqlite3.connect(str(baseline_db))
    snap_conn = sqlite3.connect(str(snapshot_db))
    record_delta = {}
    for tbl in ["instances", "vpcs", "subnets", "security_groups", "images"]:
        bc = base_conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        sc = snap_conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        if sc != bc:
            record_delta[tbl] = sc - bc
    base_conn.close()
    snap_conn.close()

    total_steps        = sum(t.get("steps", 0) for t in trajectories)
    total_write_calls  = sum(t.get("write_calls", 0) for t in trajectories)
    total_write_errors = sum(t.get("write_errors", 0) for t in trajectories)
    write_error_rate   = total_write_errors / total_write_calls if total_write_calls else 0.0

    result = {
        "run_at": datetime.utcnow().isoformat(),
        "env": "cloud",
        "n_tasks": n,
        "df": round(df, 4),
        "vpr": round(vpr, 4),
        "write_error_rate": round(write_error_rate, 4),
        "total_steps": total_steps,
        "total_write_calls": total_write_calls,
        "total_write_errors": total_write_errors,
        "record_delta": record_delta,
        "check_results": check_results,
        "trajectories": trajectories,
    }

    # report.json — lets compute_fidelity.py auto-detect env from run dir
    (run_dir / "report.json").write_text(json.dumps({"env": "cloud", **result}, indent=2))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    avg_steps = total_steps / n if n > 0 else 0
    print("\n" + "=" * 60)
    print("CLOUD ENV — ENVSCALER COMPARISON")
    print("=" * 60)
    print(f"{'Metric':<30} {'G0_envscaler':>14}")
    print("-" * 50)
    print(f"{'n tasks':<30} {n:>14}")
    print(f"{'DF':<30} {df:>14.4f}")
    print(f"{'VPR':<30} {vpr:>14.4f}")
    print(f"{'Write Error Rate':<30} {write_error_rate:>14.4f}")
    print(f"{'Avg steps/task':<30} {avg_steps:>14.1f}")
    print(f"{'Total steps':<30} {total_steps:>14}")
    print(f"{'Record delta':<30} {str(record_delta):>14}")
    print("-" * 50)
    print(f"\nRun dir  → {run_dir}")
    print(f"Results  → {out_path}")
    print("\nTo compute full fidelity metrics:")
    print(f"  python scripts/compute_fidelity.py --run-dir {run_dir}")


def main():
    parser = argparse.ArgumentParser(description="Run EnvScaler cloud comparison")
    parser.add_argument("--tasks", type=Path,
                        default=Path(__file__).parent / "envscaler_cloud_tasks.json")
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).parent / "envscaler_comparison_cloud_result.json")
    args = parser.parse_args()
    run_comparison(args.tasks, args.n, args.out)


if __name__ == "__main__":
    main()
