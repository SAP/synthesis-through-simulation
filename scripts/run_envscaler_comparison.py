"""
EnvScaler vs STS blind-agent comparison runner.

Reads EnvScaler-generated task descriptions from scripts/envscaler_airline_tasks.json,
runs each through our blind airline agent (same infrastructure as G0_blind), then
computes DF and VPR on the resulting DB snapshot.

Results are saved to scripts/envscaler_comparison_result.json and printed as a
comparison table alongside the known G0_blind numbers.

Usage:
    python scripts/run_envscaler_comparison.py [--tasks scripts/envscaler_airline_tasks.json]
                                               [--n 20]
                                               [--out scripts/envscaler_comparison_result.json]

Prerequisites:
    python scripts/envscaler_gen_tasks.py  (generates the tasks file)
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

# Import synthesizer internals
# Import DF metric and validator
from synthesize.environments.airline import validate as airline_validate

# Import airline tools
from synthesize.environments.airline.apis import flights as flights_api
from synthesize.environments.airline.apis import payments as payments_api
from synthesize.environments.airline.apis import reservations as reservations_api
from synthesize.environments.airline.apis import users as users_api
from synthesize.environments.airline.db import db as airline_db
from synthesize.environments.airline.quality_priors import AIRLINE_QUALITY_PRIORS
from synthesize.synthesizer.agent_synthesizer import IntentDef
from synthesize.synthesizer.default_agent import _make_client, run_agent

BASELINE_DB = REPO_ROOT / "src" / "synthesize" / "environments" / "airline" / "db" / "airline_snapshot.db"

# Known G0_blind numbers for comparison (from paper Table 3)
G0_BLIND_DF = 0.454
G0_BLIND_VPR = 1.0  # 100%

# ── Tool registry (all airline tools — same as G0_blind) ─────────────────────

AIRLINE_TOOL_REGISTRY = {
    "get_user_details": {
        "fn": users_api.get_user_details,
        "description": "Get full user details including saved passengers and payment methods.",
        "input_schema": {
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
            "required": ["user_id"],
        },
    },
    "list_users": {
        "fn": users_api.list_users,
        "description": "List all users with optional membership filter (gold/silver/regular).",
        "input_schema": {
            "type": "object",
            "properties": {
                "membership": {
                    "type": "string",
                    "enum": ["gold", "silver", "regular"],
                }
            },
            "required": [],
        },
    },
    "get_payment_methods": {
        "fn": payments_api.get_payment_methods,
        "description": "List all payment methods for a user.",
        "input_schema": {
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
            "required": ["user_id"],
        },
    },
    "list_all_airports": {
        "fn": flights_api.list_all_airports,
        "description": "List all supported airport codes and names.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "search_direct_flight": {
        "fn": flights_api.search_direct_flight,
        "description": (
            "Search for available direct flights between two airports on a given date. "
            "Returns flight numbers, available seats per cabin, and prices."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["origin", "destination", "date"],
        },
    },
    "search_onestop_flight": {
        "fn": flights_api.search_onestop_flight,
        "description": "Search for one-stop connecting flights between two airports on a given date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["origin", "destination", "date"],
        },
    },
    "get_flight_status": {
        "fn": flights_api.get_flight_status,
        "description": "Get the status and availability of a specific flight on a given date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_number": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["flight_number", "date"],
        },
    },
    "list_reservations": {
        "fn": reservations_api.list_reservations,
        "description": "List reservations. Optionally filter by user_id or status ('active').",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "status": {"type": "string", "enum": ["active", "cancelled"]},
            },
            "required": [],
        },
    },
    "get_reservation_details": {
        "fn": reservations_api.get_reservation_details,
        "description": "Get full reservation details including flights, passengers, and payment history.",
        "input_schema": {
            "type": "object",
            "properties": {"reservation_id": {"type": "string"}},
            "required": ["reservation_id"],
        },
    },
    "book_reservation": {
        "fn": reservations_api.book_reservation,
        "description": (
            "Book a new reservation. Requires user_id, flights, passengers, cabin, "
            "payment_methods, flight_type (one_way/round_trip), total_baggages, "
            "nonfree_baggages, insurance (yes/no)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "flights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "flight_number": {"type": "string"},
                            "date": {"type": "string"},
                            "price": {"type": "integer"},
                        },
                        "required": ["flight_number", "date", "price"],
                    },
                },
                "passengers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "first_name": {"type": "string"},
                            "last_name": {"type": "string"},
                            "dob": {"type": "string"},
                        },
                        "required": ["first_name", "last_name", "dob"],
                    },
                },
                "cabin": {"type": "string", "enum": ["business", "economy", "basic_economy"]},
                "payment_methods": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "payment_method_id": {"type": "string"},
                            "amount": {"type": "integer"},
                        },
                        "required": ["payment_method_id", "amount"],
                    },
                },
                "flight_type": {"type": "string", "enum": ["one_way", "round_trip"]},
                "total_baggages": {"type": "integer"},
                "nonfree_baggages": {"type": "integer"},
                "insurance": {"type": "string", "enum": ["yes", "no"]},
            },
            "required": [
                "user_id", "flights", "passengers", "cabin",
                "payment_methods", "flight_type", "total_baggages",
                "nonfree_baggages", "insurance",
            ],
        },
    },
    "cancel_reservation": {
        "fn": reservations_api.cancel_reservation,
        "description": "Cancel an active reservation. Issues refunds to original payment methods.",
        "input_schema": {
            "type": "object",
            "properties": {"reservation_id": {"type": "string"}},
            "required": ["reservation_id"],
        },
    },
    "update_reservation_flights": {
        "fn": reservations_api.update_reservation_flights,
        "description": "Change the flights on an active reservation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string"},
                "flights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "flight_number": {"type": "string"},
                            "date": {"type": "string"},
                            "price": {"type": "integer"},
                        },
                        "required": ["flight_number", "date", "price"],
                    },
                },
                "payment_id": {"type": "string"},
            },
            "required": ["reservation_id", "flights", "payment_id"],
        },
    },
    "update_reservation_baggages": {
        "fn": reservations_api.update_reservation_baggages,
        "description": "Update baggage counts on an active reservation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string"},
                "total_baggages": {"type": "integer"},
                "nonfree_baggages": {"type": "integer"},
                "payment_id": {"type": "string"},
            },
            "required": ["reservation_id", "total_baggages", "nonfree_baggages", "payment_id"],
        },
    },
    "update_reservation_passengers": {
        "fn": reservations_api.update_reservation_passengers,
        "description": "Replace the passenger list on an active reservation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string"},
                "passengers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "first_name": {"type": "string"},
                            "last_name": {"type": "string"},
                            "dob": {"type": "string"},
                        },
                        "required": ["first_name", "last_name", "dob"],
                    },
                },
            },
            "required": ["reservation_id", "passengers"],
        },
    },
    "send_certificate": {
        "fn": payments_api.send_certificate,
        "description": "Send a travel certificate to a user's account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "amount": {"type": "integer"},
            },
            "required": ["user_id", "amount"],
        },
    },
}

ALL_TOOLS = list(AIRLINE_TOOL_REGISTRY.keys())
WRITE_TOOLS = {
    "book_reservation", "cancel_reservation", "update_reservation_flights",
    "update_reservation_baggages", "update_reservation_passengers", "send_certificate",
}


# ── DF computation ─────────────────────────────────────────────────────────────

def _compute_df(snapshot_path: Path, baseline_path: Path) -> float:
    """
    Compute Distribution Fidelity between baseline and snapshot using the same
    method as RealisticValueDistributionScore (JSD for categorical, KS for numeric).
    Only the NEW rows (added since baseline) are evaluated.
    """
    priors = AIRLINE_QUALITY_PRIORS
    snap_conn = sqlite3.connect(str(snapshot_path))
    base_conn = sqlite3.connect(str(baseline_path))
    base_conn.row_factory = sqlite3.Row

    ln2 = math.log(2)
    similarities: list[float] = []

    for table, fields in priors.items():
        # Get new row IDs added since baseline
        base_ids = {
            r[0] for r in base_conn.execute(f"SELECT rowid FROM {table}").fetchall()
        }
        # Fetch via cursor so we can use positional index for rowid (sqlite3.Row
        # doesn't reliably expose "rowid" as a named key in Python 3.13+)
        cur = snap_conn.execute(f"SELECT rowid, * FROM {table}")
        col_names = [d[0] for d in cur.description]  # ["rowid", col1, col2, ...]
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
                # JSD
                m = {k: (p_obs[k] + ref_dist[k]) / 2 for k in ref_dist}
                def _kl(p: dict, q: dict) -> float:
                    s = 0.0
                    for k in p:
                        if p[k] > 0 and q[k] > 0:
                            s += p[k] * math.log(p[k] / q[k])
                    return s
                jsd = (_kl(p_obs, m) + _kl(ref_dist, m)) / 2
                similarities.append(1.0 - jsd / ln2)

            elif spec["type"] == "numeric":
                ref_vals: list[float] = spec["reference_values"]
                obs_vals = sorted([float(v) for v in col_values])
                ref_sorted = sorted([float(v) for v in ref_vals])
                # KS statistic
                all_vals = sorted(set(obs_vals) | set(ref_sorted))
                import bisect
                max_diff = 0.0
                for x in all_vals:
                    cdf_obs = bisect.bisect_right(obs_vals, x) / len(obs_vals)
                    cdf_ref = bisect.bisect_right(ref_sorted, x) / len(ref_sorted)
                    max_diff = max(max_diff, abs(cdf_obs - cdf_ref))
                similarities.append(1.0 - max_diff)

    snap_conn.close()
    base_conn.close()
    return sum(similarities) / len(similarities) if similarities else 0.0


# ── VPR computation ────────────────────────────────────────────────────────────

def _compute_vpr(snapshot_path: Path) -> tuple[float, list[dict]]:
    """Run the airline validator against the snapshot DB and return (vpr, check_results)."""
    airline_validate.set_db(snapshot_path)
    results = airline_validate.run(as_json=True)
    passed = sum(1 for r in results if r["status"] == "PASS")
    return passed / len(results) if results else 0.0, results


# ── Main runner ────────────────────────────────────────────────────────────────

def run_comparison(tasks_path: Path, n: int, out_path: Path) -> None:
    if not tasks_path.exists():
        print(f"ERROR: tasks file not found: {tasks_path}")
        print("Run: python scripts/envscaler_gen_tasks.py first.")
        sys.exit(1)

    with open(tasks_path) as f:
        all_tasks = json.load(f)

    if len(all_tasks) < n:
        print(f"WARNING: only {len(all_tasks)} tasks available; running all of them.")
        n = len(all_tasks)

    tasks = all_tasks[:n]

    # ── Create run dir (same layout as batch runs, compatible with compute_fidelity.py) ──
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = REPO_ROOT / ".runs" / f"airline_envscaler_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Run dir: {run_dir}")

    # baseline.db = seed state (never modified)
    baseline_db = run_dir / "baseline.db"
    working_db  = run_dir / "working.db"
    shutil.copy2(str(BASELINE_DB), str(baseline_db))
    shutil.copy2(str(BASELINE_DB), str(working_db))

    # Point all airline API modules at the working DB
    airline_db.DB_PATH = working_db

    print(f"Running {n} EnvScaler tasks through blind airline agent...")

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
                    tool_registry=AIRLINE_TOOL_REGISTRY,
                    env_name="airline",
                )
                tool_calls = [{"tool": s.tool, "is_error": s.is_error} for s in traj.steps]
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

    # Compute metrics
    print("\nComputing metrics...")
    df = _compute_df(snapshot_db, baseline_db)
    vpr, check_results = _compute_vpr(snapshot_db)

    # Count new records
    base_conn = sqlite3.connect(str(baseline_db))
    snap_conn = sqlite3.connect(str(snapshot_db))
    record_delta = {}
    for tbl in ["reservations", "reservation_flights", "reservation_passengers", "payment_history", "payment_methods"]:
        bc = base_conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        sc = snap_conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        if sc != bc:
            record_delta[tbl] = sc - bc
    base_conn.close()
    snap_conn.close()

    # ── Results ──────────────────────────────────────────────────────────────
    total_write_calls  = sum(t.get("write_calls", 0) for t in trajectories)
    total_write_errors = sum(t.get("write_errors", 0) for t in trajectories)
    write_error_rate   = total_write_errors / total_write_calls if total_write_calls else 0.0
    new_reservations   = record_delta.get("reservations", 0)

    result = {
        "run_at": datetime.utcnow().isoformat(),
        "env": "airline",
        "n_tasks": n,
        "df": round(df, 4),
        "vpr": round(vpr, 4),
        "write_error_rate": round(write_error_rate, 4),
        "new_reservations": new_reservations,
        "total_write_calls": total_write_calls,
        "total_write_errors": total_write_errors,
        "record_delta": record_delta,
        "check_results": check_results,
        "trajectories": trajectories,
        "comparison": {
            "G0_blind_df": G0_BLIND_DF,
            "G0_blind_vpr": G0_BLIND_VPR,
            "G0_envscaler_df": round(df, 4),
            "G0_envscaler_vpr": round(vpr, 4),
            "G0_envscaler_write_error_rate": round(write_error_rate, 4),
        },
    }

    # report.json — lets compute_fidelity.py auto-detect env from run dir
    (run_dir / "report.json").write_text(json.dumps({"env": "airline", **result}, indent=2))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    # ── Print comparison table ────────────────────────────────────────────────
    G0_BLIND_WER      = 0.0
    G0_BLIND_NEW_RESV = 20
    GP_STAR_WER       = 0.643
    GP_STAR_DF        = 0.808
    GP_STAR_NEW_RESV  = 20

    print("\n" + "=" * 72)
    print("ENVSCALER vs STS COMPARISON")
    print("=" * 72)
    print(f"{'System':<28} {'DF':>6} {'VPR':>6} {'Write err rate':>16} {'New resv':>10}")
    print("-" * 72)
    print(f"{'G0_blind (STS intents)':<28} {G0_BLIND_DF:>6.3f} {'100%':>6} {G0_BLIND_WER:>16.1%} {G0_BLIND_NEW_RESV:>10}")
    print(f"{'G0_envscaler (EnvScaler)':<28} {df:>6.3f} {vpr:>6.1%} {write_error_rate:>16.1%} {new_reservations:>10}")
    print(f"{'GP* (STS)':<28} {GP_STAR_DF:>6.3f} {'100%':>6} {GP_STAR_WER:>16.1%} {GP_STAR_NEW_RESV:>10}")
    print("=" * 72)
    print(f"Write calls: {total_write_calls} total, {total_write_errors} failed")
    print(f"New records: {record_delta}")
    print(f"\nRun dir  → {run_dir}")
    print(f"Results  → {out_path}")
    print("\nTo compute full fidelity metrics:")
    print(f"  python scripts/compute_fidelity.py --run-dir {run_dir}")


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run EnvScaler tasks through the STS blind agent and compare DF/VPR."
    )
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path(__file__).parent / "envscaler_airline_tasks.json",
        help="Path to task JSON generated by envscaler_gen_tasks.py",
    )
    parser.add_argument("--n", type=int, default=20, help="Number of tasks to run (default: 20)")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent / "envscaler_comparison_result.json",
        help="Output JSON path for results",
    )
    args = parser.parse_args()
    run_comparison(args.tasks, args.n, args.out)
