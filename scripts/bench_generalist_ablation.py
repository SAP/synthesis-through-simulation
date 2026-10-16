"""
Generalist Populator ablation benchmark.

Runs the G0_blind baseline (fresh batch) and the generalist_populator synthesizer
with varying explore_runs budgets, benchmarks each against DB quality metrics,
and prints a comparison table. All conditions are run fresh from the same DB
snapshot so results are directly comparable.

Usage:
    python3 scripts/bench_generalist_ablation.py [--explore-runs 0,1,3,5,10,20] [--n 20]
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))


# ── Write tool classification (airline environment) ───────────────────────────
# Used to compute Write Utilisation: fraction of tool calls that produce output.
# Read tools gather context; write tools mutate state and create records.
AIRLINE_WRITE_TOOLS = {
    "book_reservation",
    "cancel_reservation",
    "modify_flight",
    "update_baggages",
    "update_passengers",
    "issue_certificate",
}


# ── Inline bench_db_only logic (avoids subprocess for python3) ───────────────


def _h_norm(counts: dict) -> float:
    total = sum(counts.values())
    n_cats = len([v for v in counts.values() if v > 0])
    if total == 0 or n_cats <= 1:
        return 0.0
    h = -sum((v / total) * math.log(v / total) for v in counts.values() if v > 0)
    return h / math.log(n_cats)


def _jsd(obs: dict, valid_vals: list) -> float:
    total = sum(obs.values()) or 1
    uniform = 1 / len(valid_vals)
    result = 0.0
    for v in valid_vals:
        p = obs.get(v, 0) / total
        q = uniform
        m = 0.5 * (p + q)
        if p > 0:
            result += 0.5 * p * math.log(p / m)
        result += 0.5 * q * math.log(q / m)
    return result


def benchmark_run_dir(run_dir: Path) -> dict:
    """Extract benchmark metrics from a run dir. Returns a flat dict."""

    traj_file = run_dir / "trajectories.jsonl"
    if not traj_file.exists():
        return {"error": "no trajectories.jsonl"}

    items = [json.loads(line) for line in traj_file.read_text().splitlines() if line.strip()]
    n = len(items)
    if n == 0:
        return {"error": "empty trajectories"}

    # Handle both G0 format (steps/success/total_steps) and GP format (tool_calls)
    def _get_steps(item: dict) -> list:
        return item.get("steps") or item.get("tool_calls") or []

    def _is_success(item: dict) -> bool:
        if "success" in item:
            return bool(item["success"])
        # GP format: success if at least one non-error tool call exists
        tcs = _get_steps(item)
        return len(tcs) > 0 and any(not tc.get("is_error", False) for tc in tcs)

    successes = sum(1 for i in items if _is_success(i))
    avg_steps = statistics.mean(
        i.get("total_steps", len(_get_steps(i))) for i in items
    )
    avg_errors = statistics.mean(
        i.get("error_count", sum(1 for s in _get_steps(i) if s.get("is_error")))
        for i in items
    )
    tool_counts: Counter = Counter(
        s["tool"] for i in items for s in _get_steps(i) if "tool" in s
    )
    tool_div = _h_norm(dict(tool_counts))

    # Write Utilisation: fraction of calls that mutate state (vs. read/gather)
    total_calls = sum(tool_counts.values())
    write_calls = sum(v for k, v in tool_counts.items() if k in AIRLINE_WRITE_TOOLS)
    write_utilisation = round(write_calls / total_calls, 4) if total_calls else None

    report_file = run_dir / "report.json"
    checks_passed = checks_total = 0
    if report_file.exists():
        rep = json.load(report_file.open())
        checks_passed = rep.get("summary", {}).get("passed", 0)
        checks_total = rep.get("summary", {}).get("total_checks", 0)

    db_path = run_dir / "snapshot.db"
    baseline_path = run_dir / "baseline.db"
    db_metrics: dict = {}

    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        bconn = sqlite3.connect(str(baseline_path)) if baseline_path.exists() else None

        def agent_set(table: str, col: str) -> set:
            final = {r[0] for r in conn.execute(f"SELECT {col} FROM {table}").fetchall()}
            if bconn:
                seed = {r[0] for r in bconn.execute(f"SELECT {col} FROM {table}").fetchall()}
                return final - seed
            return final

        agent_res = agent_set("reservations", "reservation_id")

        fk_pairs = [
            ("reservation_flights", "reservation_id"),
            ("reservation_passengers", "reservation_id"),
            ("payment_history", "reservation_id"),
        ]
        wf_scores = {}
        for child, fk in fk_pairs:
            if not agent_res:
                wf_scores[child] = None
                continue
            children = {
                r[0]
                for r in conn.execute(
                    f"SELECT DISTINCT {fk} FROM {child} WHERE {fk} IN "
                    f"({','.join(['?']*len(agent_res))})",
                    list(agent_res),
                ).fetchall()
            }
            wf_scores[child] = round(len(children) / len(agent_res), 4)
        wf_complete = (
            statistics.mean(v for v in wf_scores.values() if v is not None)
            if any(v is not None for v in wf_scores.values())
            else None
        )

        enum_defs = {
            "cabin": ["business", "economy", "basic_economy"],
            "flight_type": ["one_way", "round_trip"],
            "insurance": ["yes", "no"],
        }
        fidelity = {}
        for col, valid in enum_defs.items():
            final_dist = dict(
                conn.execute(
                    f"SELECT {col}, COUNT(*) FROM reservations WHERE {col} IS NOT NULL GROUP BY {col}"
                ).fetchall()
            )
            if bconn:
                base_dist = dict(
                    bconn.execute(
                        f"SELECT {col}, COUNT(*) FROM reservations WHERE {col} IS NOT NULL GROUP BY {col}"
                    ).fetchall()
                )
                agent_dist = {
                    k: max(0, final_dist.get(k, 0) - base_dist.get(k, 0))
                    for k in set(final_dist) | set(base_dist)
                }
                agent_dist = {k: v for k, v in agent_dist.items() if v > 0}
            else:
                agent_dist = final_dist
            if agent_dist:
                d = _jsd(agent_dist, valid)
                fidelity[col] = round(max(0.0, 1.0 - d / math.log(2)), 4)

        dedup: dict[str, float] = {}
        for table in [
            "reservations",
            "reservation_flights",
            "reservation_passengers",
            "payment_history",
        ]:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            n_seed = 0
            if bconn:
                try:
                    n_seed = bconn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except Exception:
                    pass
            agent_rows = rows[n_seed:]
            if len(agent_rows) < 2:
                continue
            seen: set = set()
            dupes = 0
            for row in agent_rows:
                fp = __import__("hashlib").md5(
                    json.dumps(row[1:], default=str).encode()
                ).hexdigest()
                if fp in seen:
                    dupes += 1
                else:
                    seen.add(fp)
            dedup[table] = round(1 - dupes / len(agent_rows), 4)

        # Baggage KS similarity
        bags_sim = None
        try:
            ref_bags = [0] * 10 + [1] * 9 + [2] * 4 + [3]
            obs_q = conn.execute(
                "SELECT total_baggages FROM reservations WHERE total_baggages IS NOT NULL"
            ).fetchall()
            n_seed_b = 0
            if bconn:
                n_seed_b = bconn.execute(
                    "SELECT COUNT(*) FROM reservations WHERE total_baggages IS NOT NULL"
                ).fetchone()[0]
            obs_bags = [r[0] for r in obs_q][n_seed_b:]
            if obs_bags:
                import bisect

                obs_s = sorted(obs_bags)
                ref_s = sorted(ref_bags)
                all_v = sorted(set(obs_bags) | set(ref_bags))
                ks = max(
                    abs(
                        bisect.bisect_right(obs_s, x) / len(obs_s)
                        - bisect.bisect_right(ref_s, x) / len(ref_s)
                    )
                    for x in all_v
                )
                bags_sim = round(1 - ks, 4)
        except Exception:
            pass

        # Cabin L1 similarity
        cabin_sim = None
        try:
            ref_cabin = {"business": 0.10, "economy": 0.75, "basic_economy": 0.15}
            final_cabin = dict(
                conn.execute(
                    "SELECT cabin, COUNT(*) FROM reservations WHERE cabin IS NOT NULL GROUP BY cabin"
                ).fetchall()
            )
            if bconn:
                seed_cabin = dict(
                    bconn.execute(
                        "SELECT cabin, COUNT(*) FROM reservations WHERE cabin IS NOT NULL GROUP BY cabin"
                    ).fetchall()
                )
                agent_cabin: dict = {
                    k: max(0, final_cabin.get(k, 0) - seed_cabin.get(k, 0))
                    for k in set(final_cabin) | set(seed_cabin)
                }
                agent_cabin = {k: v for k, v in agent_cabin.items() if v > 0}
            else:
                agent_cabin = final_cabin
            if agent_cabin:
                total_a = sum(agent_cabin.values())
                obs_fracs = {k: agent_cabin.get(k, 0) / total_a for k in ref_cabin}
                cabin_sim = round(
                    1 - sum(abs(obs_fracs.get(k, 0) - ref_cabin[k]) for k in ref_cabin) / 2, 4
                )
        except Exception:
            pass

        db_metrics = {
            "agent_reservations": len(agent_res),
            "workflow_completeness": round(wf_complete, 4) if wf_complete is not None else None,
            "mean_data_fidelity": round(statistics.mean(fidelity.values()), 4) if fidelity else None,
            "mean_deduplication": round(statistics.mean(dedup.values()), 4) if dedup else None,
            "baggage_dist_similarity": bags_sim,
            "cabin_dist_similarity": cabin_sim,
            # DF = mean of all reference-field similarities (environment-provided priors)
            "dist_fidelity": round((bags_sim + cabin_sim) / 2, 4)
            if bags_sim is not None and cabin_sim is not None
            else None,
            # FPS = DF / SR — quality gained per tool call
            "fidelity_per_step": round(
                ((bags_sim + cabin_sim) / 2) / avg_steps, 4
            )
            if bags_sim is not None and cabin_sim is not None and avg_steps > 0
            else None,
        }
        conn.close()
        if bconn:
            bconn.close()

    return {
        "n": n,
        "success_rate": round(successes / n, 4) if n else 0,
        "avg_steps": round(avg_steps, 2),
        "avg_errors": round(avg_errors, 2),
        "tool_usage_diversity": round(tool_div, 4),
        "write_utilisation": write_utilisation,
        "validation_pass_rate": round(checks_passed / checks_total, 4) if checks_total else None,
        **db_metrics,
    }


# ── Ablation runner ───────────────────────────────────────────────────────────


def reset_manifest(manifest_path: Path) -> None:
    if manifest_path.exists():
        manifest_path.unlink()
    print(f"  Manifest reset: {manifest_path}")


def reset_db() -> None:
    subprocess.run(
        [sys.executable, "-m", "synthesize.cli", "--env", "airline", "setup"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, "-m", "synthesize.cli", "--env", "airline", "snapshot"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    print("  DB reset + snapshotted")


def run_batch_blind(n: int) -> Path:
    """Run a blind (G0) batch and return the run dir."""
    import time

    before = time.time()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "synthesize.cli",
            "--env",
            "airline",
            "batch",
            "--synthesizer",
            "airline_agent",
            "--n",
            str(n),
            "--mode",
            "blind",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    runs_root = ROOT / ".runs"
    candidates = [
        d
        for d in runs_root.iterdir()
        if d.is_dir()
        and d.name.startswith("airline_")
        and d.stat().st_mtime > before
    ]
    if not candidates:
        raise RuntimeError(
            f"No run dir created after G0_blind invocation.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)


def run_batch(n: int, explore_runs: int) -> Path:
    """Run a batch and return the run dir."""
    import time

    before = time.time()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "synthesize.cli",
            "--env",
            "airline",
            "batch",
            "--synthesizer",
            "generalist_populator",
            "--n",
            str(n),
            "--explore-mode",
            "staged",
            "--explore-runs",
            str(explore_runs),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    # Find the run dir created by this batch invocation.
    # The CLI names batch dirs as airline_batch_informed_<ts>/
    runs_root = ROOT / ".runs"
    candidates = [
        d
        for d in runs_root.iterdir()
        if d.is_dir()
        and d.name.startswith("airline_")
        and d.stat().st_mtime > before
    ]
    if not candidates:
        raise RuntimeError(
            f"No run dir created after batch invocation.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)


def print_comparison_table(rows: list[dict]) -> None:
    metrics = [
        ("dist_fidelity", "Dist fidelity (DF)"),
        ("mean_data_fidelity", "Categorical div (CD)"),
        ("write_utilisation", "Write utilisation (WU)"),
        ("fidelity_per_step", "Fidelity/step (FPS)"),
        ("tool_usage_diversity", "API diversity (AD)"),
        ("avg_steps", "Avg steps (SR)"),
        ("workflow_completeness", "Workflow completeness"),
        ("baggage_dist_similarity", "  baggage sim"),
        ("cabin_dist_similarity", "  cabin sim"),
        ("validation_pass_rate", "Validation pass"),
    ]
    labels = [r["label"] for r in rows]

    # Header
    col_w = 14
    label_w = 26
    header = f"{'Metric':<{label_w}}" + "".join(f"{lbl:>{col_w}}" for lbl in labels)
    print("\n" + "=" * len(header))
    print(header)
    print("=" * len(header))

    for key, display in metrics:
        vals = [r.get(key) for r in rows]
        # highlight best (max) in each row
        numeric = [v for v in vals if v is not None]
        best = max(numeric) if numeric else None
        row_str = f"{display:<{label_w}}"
        for v in vals:
            if v is None:
                cell = "n/a"
            elif isinstance(v, float):
                cell = f"{v:.3f}"
                if v == best:
                    cell = f"*{cell}*"
            else:
                cell = str(v)
            row_str += f"{cell:>{col_w}}"
        print(row_str)

    print("=" * len(header))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generalist Populator ablation benchmark")
    parser.add_argument(
        "--explore-runs",
        default="0,1,3,5,10,20",
        help="Comma-separated list of explore_runs values to test (default: 0,1,3,5,10,20)",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=20,
        help="Number of synthesis runs per condition (default: 20)",
    )
    parser.add_argument(
        "--skip-g0",
        action="store_true",
        help="Skip the G0_blind baseline condition",
    )
    args = parser.parse_args()

    explore_runs_list = [int(x.strip()) for x in args.explore_runs.split(",")]
    manifest_path = ROOT / ".runs" / "exploration" / "airline" / "manifest.db"

    all_rows: list[dict] = []

    # G0_blind baseline — run fresh so DB state and benchmark code match GP conditions
    if not args.skip_g0:
        label = "G0_blind"
        print("\n── G0_blind baseline ──")
        try:
            reset_db()
            print(f"  Running blind batch (n={args.n}) …")
            run_dir = run_batch_blind(args.n)
            print(f"  Run dir: {run_dir.name}")
            metrics = benchmark_run_dir(run_dir)
            metrics["run_dir"] = run_dir.name
            all_rows.append({"label": label, **metrics})
        except Exception as exc:
            print(f"  ERROR: {exc}")
            all_rows.append({"label": label, "error": str(exc)})

    # Ablation
    for er in explore_runs_list:
        label = f"gp_explore{er}"
        print(f"\n── explore_runs={er} ({label}) ──")
        try:
            reset_manifest(manifest_path)
            reset_db()
            print(f"  Running batch (n={args.n}) …")
            run_dir = run_batch(args.n, er)
            print(f"  Run dir: {run_dir.name}")
            metrics = benchmark_run_dir(run_dir)
            metrics["run_dir"] = run_dir.name
            all_rows.append({"label": label, **metrics})
        except Exception as exc:
            print(f"  ERROR: {exc}")
            all_rows.append({"label": label, "error": str(exc)})

    print_comparison_table([r for r in all_rows if "error" not in r])

    out_path = ROOT / "summaries" / "evaluation_reports" / "generalist_ablation_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_rows, indent=2))
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
