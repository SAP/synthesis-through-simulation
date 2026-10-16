"""
Compute MDF, PDF, CDF, and WO for a finished (or in-progress) synthesis run.

  MDF — Marginal Distribution Fidelity    (RealisticValueDistributionScore)
  PDF — Pairwise Distribution Fidelity    (PairwiseFidelityScore)
  CDF — Cross-table Distribution Fidelity (CrossTableRelationalFidelityScore)
  WO  — Avg Successful Write Operations per Trajectory

DB resolution order (first match wins):
  1. <run_dir>/snapshot.db  +  <run_dir>/baseline.db   (finished run)
  2. env's db.py DB_PATH  +  <env>_snapshot.db next to it  (fallback / mid-run)
     (handles non-standard names like hr_barebone.db automatically)

Usage:
  # Single finished run (env auto-detected from dir name or report.json)
  python scripts/compute_fidelity.py --run-dir .runs/airline_batch_informed_20260502_184905

  # Explicit env (useful for mid-run check against live env DB)
  python scripts/compute_fidelity.py --env airline

  # All run dirs for one env
  python scripts/compute_fidelity.py --env airline --all-runs

  # Save results to JSON
  python scripts/compute_fidelity.py --run-dir .runs/airline_batch_... --out outputs/fidelity.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from synthesize.benchmarking._utils import js_divergence

N_BOOT = 1000
ALPHA = 0.05

# ---------------------------------------------------------------------------
# Write-tool registry (per environment)
# Derived from each GeneralistSynthesizer.INTENT_TO_WRITE_TOOLS — these are
# the only tools that mutate DB state; everything else is a read-only query.
# ---------------------------------------------------------------------------

_WRITE_TOOLS: dict[str, frozenset[str]] = {
    "airline": frozenset({
        "book_reservation", "cancel_reservation",
        "update_reservation_flights", "update_reservation_baggages",
        "update_reservation_passengers",
    }),
    "retail": frozenset({
        "create_order", "add_order_item", "add_payment_record",
        "update_order_status", "set_return_details", "set_exchange_details",
    }),
    "banking": frozenset({
        "open_account", "deposit", "withdraw", "transfer",
    }),
    "ecommerce": frozenset({
        "create_order", "add_order_item", "confirm_order",
        "cancel_order", "update_shipping_address", "restock_product",
    }),
    "pharmacy": frozenset({
        "create_prescription", "fill_prescription", "cancel_prescription",
    }),
    "forum": frozenset({
        "create_thread", "create_post", "close_thread",
    }),
    "university": frozenset({
        "enroll_student", "drop_student", "add_to_waitlist",
    }),
    "it_management": frozenset({
        "create_ticket", "assign_ticket", "resolve_ticket", "update_ticket",
    }),
    "cloud": frozenset({
        "create_vpc", "create_subnet", "create_security_group",
        "launch_instance", "start_instance", "stop_instance", "terminate_instance",
    }),
    "hr": frozenset({
        "create_employee", "update_job", "terminate_employee",
        "create_time_off_request", "approve_time_off_request",
        "create_requisition", "create_candidate", "create_application",
        "update_application", "create_offer", "update_offer", "update_review",
    }),
    "obfuscated_airline": frozenset({
        "book_object_c", "set_object_c_status_a",
        "update_object_c_object_bs", "update_object_c_baggages",
        "update_object_c_object_ds",
    }),
}


# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------


def _jsd_sim(agent: dict, ref_dist: dict) -> float | None:
    total = sum(agent.values())
    if total == 0:
        return None
    ref = {k: int(v * total) for k, v in ref_dist.items()}
    return max(0.0, 1.0 - js_divergence(agent, ref) / math.log(2))


def _boot_field(vals: list, ref_dist: dict) -> tuple[float | None, float | None]:
    if not vals:
        return None, None
    sims = sorted(filter(None, (
        _jsd_sim(dict(Counter(random.choices(vals, k=len(vals)))), ref_dist)
        for _ in range(N_BOOT)
    )))
    if not sims:
        return None, None
    return sims[int(ALPHA / 2 * len(sims))], sims[int((1 - ALPHA / 2) * len(sims))]


def _boot_mean(
    values: list[float],
    field_cis: list[tuple[float | None, float | None]] | None = None,
) -> tuple[float, float]:
    # When only one field is registered, resampling field-level estimates is
    # degenerate (the single element is always selected, giving zero-width CI).
    # Fall back to the per-field row-level bootstrap CI, which correctly reflects
    # sampling uncertainty from the underlying generated rows.
    if len(values) < 2:
        if field_cis and len(field_cis) == 1 and field_cis[0][0] is not None:
            return field_cis[0]
        return values[0], values[0]
    boot = sorted(
        sum(random.choices(values, k=len(values))) / len(values)
        for _ in range(N_BOOT)
    )
    return boot[int(ALPHA / 2 * N_BOOT)], boot[int((1 - ALPHA / 2) * N_BOOT)]


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _open(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    return c


def _resolve_dbs(run_dir: Path | None, env: str) -> tuple[Path, Path]:
    """Return (current_db, baseline_db) paths."""
    if run_dir is not None:
        snap = run_dir / "snapshot.db"
        base = run_dir / "baseline.db"
        if snap.exists() and base.exists():
            return snap, base
    # Fallback: env live DB vs snapshot.
    # Ask the env's db module for the canonical DB_PATH rather than guessing the filename,
    # because some environments use non-standard names (e.g. HR uses hr_barebone.db).
    env_dir = REPO_ROOT / "src" / "synthesize" / "environments" / env / "db"
    current = None
    try:
        import importlib
        db_mod_name = f"synthesize.environments.{env}.db.db"
        # cloud uses cloud_db module
        if env == "cloud":
            db_mod_name = f"synthesize.environments.{env}.db.cloud_db"
        db_mod = importlib.import_module(db_mod_name)
        current = Path(db_mod.DB_PATH)
    except Exception:
        pass
    # Conventional fallback: {env}.db
    if current is None or not current.exists():
        current = env_dir / f"{env}.db"
    if not current.exists():
        raise FileNotFoundError(f"No DB found for env '{env}' at {current}")
    # Snapshot: {env}_snapshot.db sits next to the live DB
    baseline = current.parent / f"{env}_snapshot.db"
    return current, baseline if baseline.exists() else None


def _detect_env(run_dir: Path) -> str | None:
    """Infer env from report.json or run dir name."""
    report = run_dir / "report.json"
    if report.exists():
        try:
            data = json.loads(report.read_text())
            if env := data.get("env"):
                return env
        except Exception:
            pass
    # Fall back to dir name prefix (e.g. "airline_batch_...")
    name = run_dir.name
    known = ["airline", "retail", "banking", "hr", "ecommerce", "pharmacy",
             "forum", "university", "it_management", "cloud"]
    for e in known:
        if name.startswith(e + "_") or name == e:
            return e
    return None


# ---------------------------------------------------------------------------
# Write-ops metric
# ---------------------------------------------------------------------------


def _find_trajectories(run_dir: Path | None, env: str) -> Path | None:
    """Return path to trajectories.jsonl for this run/env, or None if not found."""
    if run_dir is not None:
        p = run_dir / "trajectories.jsonl"
        return p if p.exists() else None
    # Fall back to the most recent run dir for this env under REPO_ROOT/.runs
    runs_root = REPO_ROOT / ".runs"
    if not runs_root.exists():
        return None
    candidates = sorted(
        d for d in runs_root.iterdir()
        if d.is_dir() and d.name.startswith(env + "_")
    )
    for rd in reversed(candidates):
        p = rd / "trajectories.jsonl"
        if p.exists():
            return p
    return None


def _is_successful_write(tc: dict, write_tools: frozenset) -> bool:
    """A write call is successful iff it targets a write tool and did not error."""
    if tc.get("tool") not in write_tools:
        return False
    if tc.get("is_error", False):
        return False
    # Fallback for older GP trajectories that encode errors in the result string
    result = tc.get("result", "")
    if isinstance(result, str) and result.lower().startswith("error"):
        return False
    return True


def _compute_write_ops(run_dir: Path | None, env: str) -> dict:
    """Avg successful write operations per trajectory."""
    traj_path = _find_trajectories(run_dir, env)
    if traj_path is None:
        return {"mean": None, "std": None, "n_trajectories": 0,
                "note": "no trajectories.jsonl found"}

    write_tools = _WRITE_TOOLS.get(env, frozenset())
    if not write_tools:
        return {"mean": None, "std": None, "n_trajectories": 0,
                "note": f"no write tools registered for env '{env}'"}

    counts: list[int] = []
    with traj_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            tool_calls = record.get("tool_calls", [])
            n = sum(1 for tc in tool_calls if _is_successful_write(tc, write_tools))
            counts.append(n)

    if not counts:
        return {"mean": None, "std": None, "n_trajectories": 0,
                "note": "trajectories file is empty"}

    n = len(counts)
    mean = sum(counts) / n
    variance = sum((c - mean) ** 2 for c in counts) / n
    std = math.sqrt(variance)
    return {
        "mean": round(mean, 3),
        "std": round(std, 3),
        "n_trajectories": n,
        "min": min(counts),
        "max": max(counts),
        "zero_frac": round(sum(1 for c in counts if c == 0) / n, 3),
    }


# ---------------------------------------------------------------------------
# Compute each metric
# ---------------------------------------------------------------------------


def _compute_mdf(env: str, conn: sqlite3.Connection, base: sqlite3.Connection | None) -> dict:
    """Marginal Distribution Fidelity — per-field JSD similarity."""
    import importlib
    mod = importlib.import_module(f"synthesize.environments.{env}.quality_priors")
    priors = None
    for attr in dir(mod):
        up = attr.upper()
        if up.endswith("_QUALITY_PRIORS") and "PAIRWISE" not in up and "PROCESS" not in up:
            priors = getattr(mod, attr)
    if priors is None:
        return {"score": None, "fields": {}, "note": "no MDF priors registered"}

    fields: dict[str, dict] = {}
    for table, cols in priors.items():
        for col, spec in cols.items():
            if spec.get("type") != "categorical":
                continue
            ref = spec["distribution"]
            try:
                final = dict(conn.execute(
                    f"SELECT {col}, COUNT(*) FROM {table} WHERE {col} IS NOT NULL GROUP BY {col}"
                ).fetchall())
                bcnt = dict(base.execute(
                    f"SELECT {col}, COUNT(*) FROM {table} WHERE {col} IS NOT NULL GROUP BY {col}"
                ).fetchall()) if base else {}
            except sqlite3.Error:
                continue
            agent = {k: max(0, final.get(k, 0) - bcnt.get(k, 0)) for k in set(final) | set(bcnt)}
            agent = {k: v for k, v in agent.items() if v > 0}
            if not agent:
                continue
            vals = [k for k, cnt in agent.items() for _ in range(cnt)]
            point = _jsd_sim(agent, ref)
            lo, hi = _boot_field(vals, ref)
            fields[f"{table}.{col}"] = {"point": round(point, 4), "ci_lo": round(lo, 4) if lo else None,
                                         "ci_hi": round(hi, 4) if hi else None, "n": len(vals)}

    if not fields:
        return {"score": None, "fields": {}, "note": "no agent rows for registered fields"}
    points = [v["point"] for v in fields.values()]
    field_cis = [(v["ci_lo"], v["ci_hi"]) for v in fields.values()]
    m = sum(points) / len(points)
    lo, hi = _boot_mean(points, field_cis)
    return {"score": round(m, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4), "fields": fields}


def _compute_pdf(env: str, conn: sqlite3.Connection, base: sqlite3.Connection | None) -> dict:
    """Pairwise Distribution Fidelity — cross-column joint JSD similarity."""
    import importlib
    mod = importlib.import_module(f"synthesize.environments.{env}.quality_priors")
    pairwise = None
    for attr in dir(mod):
        if attr.upper().endswith("_PAIRWISE_PRIORS"):
            pairwise = getattr(mod, attr)
    if pairwise is None:
        return {"score": None, "pairs": {}, "note": "no PDF priors registered"}

    pairs: dict[str, dict] = {}
    for table, pair_specs in pairwise.items():
        for (c1, c2), spec in pair_specs.items():
            if spec.get("type") != "categorical_joint":
                continue
            ref = {tuple(k) if isinstance(k, list) else k: v for k, v in spec["distribution"].items()}
            try:
                rows = conn.execute(
                    f"SELECT {c1},{c2},COUNT(*) FROM {table} "
                    f"WHERE {c1} IS NOT NULL AND {c2} IS NOT NULL GROUP BY {c1},{c2}"
                ).fetchall()
                brows = base.execute(
                    f"SELECT {c1},{c2},COUNT(*) FROM {table} "
                    f"WHERE {c1} IS NOT NULL AND {c2} IS NOT NULL GROUP BY {c1},{c2}"
                ).fetchall() if base else []
            except sqlite3.Error:
                continue
            final = {(r[0], r[1]): r[2] for r in rows}
            bcnt = {(r[0], r[1]): r[2] for r in brows}
            agent = {k: max(0, final.get(k, 0) - bcnt.get(k, 0)) for k in set(final) | set(bcnt)}
            agent = {k: v for k, v in agent.items() if v > 0}
            if not agent:
                continue
            vals = [k for k, cnt in agent.items() for _ in range(cnt)]
            point = _jsd_sim(agent, ref)
            lo, hi = _boot_field(vals, ref)
            key = f"{table}.({c1},{c2})"
            pairs[key] = {"point": round(point, 4), "ci_lo": round(lo, 4) if lo else None,
                          "ci_hi": round(hi, 4) if hi else None, "n": len(vals)}

    if not pairs:
        return {"score": None, "pairs": {}, "note": "no agent rows for registered pairs"}
    points = [v["point"] for v in pairs.values()]
    field_cis = [(v["ci_lo"], v["ci_hi"]) for v in pairs.values()]
    m = sum(points) / len(points)
    lo, hi = _boot_mean(points, field_cis)
    return {"score": round(m, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4), "pairs": pairs}


def _compute_cdf(env: str, conn: sqlite3.Connection, base: sqlite3.Connection | None) -> dict:
    """Cross-table Distribution Fidelity — FK child-count JSD similarity."""
    import importlib
    mod = importlib.import_module(f"synthesize.environments.{env}.quality_priors")
    relational = None
    for attr in dir(mod):
        if attr.upper().endswith("_RELATIONAL_PRIORS"):
            relational = getattr(mod, attr)
    if relational is None:
        return {"score": None, "relationships": {}, "note": "no CDF priors registered"}

    relationships: dict[str, dict] = {}
    for (parent_tbl, child_tbl, fk_col), spec in relational.items():
        if spec.get("type") != "child_count":
            continue
        ref = {int(k): v for k, v in spec["distribution"].items()}
        max_bucket = spec.get("max_bucket", max(ref.keys()))

        pk_rows = conn.execute(f"PRAGMA table_info({parent_tbl})").fetchall()  # noqa: S608
        parent_pk = next((r["name"] for r in pk_rows if r["pk"] > 0), None)
        if not parent_pk:
            continue

        try:
            all_pks = {r[0] for r in conn.execute(
                f"SELECT {parent_pk} FROM {parent_tbl}"  # noqa: S608
            ).fetchall()}
            seed_pks = {r[0] for r in base.execute(
                f"SELECT {parent_pk} FROM {parent_tbl}"  # noqa: S608
            ).fetchall()} if base else set()
            agent_pks = all_pks - seed_pks
            if not agent_pks:
                continue
            phs = ",".join("?" * len(agent_pks))
            child_map = {r[0]: r[1] for r in conn.execute(
                f"SELECT {fk_col}, COUNT(*) FROM {child_tbl} "  # noqa: S608
                f"WHERE {fk_col} IN ({phs}) GROUP BY {fk_col}",
                list(agent_pks),
            ).fetchall()}
        except sqlite3.Error:
            continue

        obs_vals = [min(child_map.get(pk, 0), max_bucket) for pk in agent_pks]
        agent = dict(Counter(obs_vals))
        point = _jsd_sim(agent, ref)
        lo, hi = _boot_field(obs_vals, ref)
        rel_key = f"{parent_tbl}→{child_tbl}"
        relationships[rel_key] = {
            "point": round(point, 4),
            "ci_lo": round(lo, 4) if lo else None,
            "ci_hi": round(hi, 4) if hi else None,
            "n_parents": len(agent_pks),
            "observed_counts": dict(sorted(agent.items())),
        }

    if not relationships:
        return {"score": None, "relationships": {}, "note": "no agent rows for registered FK pairs"}
    points = [v["point"] for v in relationships.values()]
    field_cis = [(v["ci_lo"], v["ci_hi"]) for v in relationships.values()]
    m = sum(points) / len(points)
    lo, hi = _boot_mean(points, field_cis)
    return {"score": round(m, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
            "relationships": relationships}


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _print_results(env: str, run_label: str, mdf: dict, pdf: dict, cdf: dict, wo: dict) -> None:
    def _fmt_score(d: dict) -> str:
        if d.get("score") is None:
            return f"n/a  ({d.get('note', '')})"
        lo, hi = d.get("ci_lo"), d.get("ci_hi")
        ci = f"  95% CI [{lo:.4f}, {hi:.4f}]" if lo is not None else ""
        return f"{d['score']:.4f}{ci}"

    def _fmt_wo(d: dict) -> str:
        if d.get("mean") is None:
            return f"n/a  ({d.get('note', '')})"
        return (
            f"{d['mean']:.2f} ± {d['std']:.2f}"
            f"  (n={d['n_trajectories']}, min={d['min']}, max={d['max']},"
            f" zero_frac={d['zero_frac']:.2f})"
        )

    print(f"\n{'='*68}")
    print(f"  {env.upper()}  —  {run_label}")
    print(f"{'='*68}")
    print(f"  MDF  {_fmt_score(mdf)}")
    print(f"  PDF  {_fmt_score(pdf)}")
    print(f"  CDF  {_fmt_score(cdf)}")
    print(f"  WO   {_fmt_wo(wo)}")

    for label, result, key in [
        ("MDF fields", mdf, "fields"),
        ("PDF pairs", pdf, "pairs"),
        ("CDF relationships", cdf, "relationships"),
    ]:
        items = result.get(key, {})
        if not items:
            continue
        print(f"\n  {label}:")
        for name, v in items.items():
            lo, hi = v.get("ci_lo"), v.get("ci_hi")
            ci = f"[{lo:.4f}, {hi:.4f}]" if lo else "n/a"
            n = v.get("n") or v.get("n_parents", "?")
            obs = f"  obs={v['observed_counts']}" if "observed_counts" in v else ""
            print(f"    {name:<42} {v['point']:.4f}  {ci}  n={n}{obs}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def compute_for_run(run_dir: Path | None, env: str, seed: int = 42) -> dict:
    random.seed(seed)
    current_db, baseline_db = _resolve_dbs(run_dir, env)
    conn = _open(current_db)
    base = _open(baseline_db) if baseline_db and baseline_db.exists() else None

    try:
        mdf = _compute_mdf(env, conn, base)
        pdf = _compute_pdf(env, conn, base)
        cdf = _compute_cdf(env, conn, base)
    finally:
        conn.close()
        if base:
            base.close()

    wo = _compute_write_ops(run_dir, env)
    label = run_dir.name if run_dir else f"live {env} DB"
    return {"env": env, "run": label, "mdf": mdf, "pdf": pdf, "cdf": cdf, "wo": wo}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute MDF / PDF / CDF fidelity metrics")
    parser.add_argument("--run-dir", help="Path to a specific run directory")
    parser.add_argument("--env", help="Environment slug (auto-detected if --run-dir given)")
    parser.add_argument("--all-runs", action="store_true",
                        help="Compute for all run dirs matching --env")
    parser.add_argument("--seed", type=int, default=42, help="Bootstrap random seed")
    parser.add_argument("--out", help="Save results to this JSON file")
    args = parser.parse_args()

    runs_dir = REPO_ROOT / ".runs"
    results = []

    if args.all_runs:
        if not args.env:
            sys.exit("--all-runs requires --env")
        run_dirs = sorted(
            d for d in runs_dir.iterdir()
            if d.is_dir() and d.name.startswith(args.env + "_")
        )
        if not run_dirs:
            sys.exit(f"No run dirs found for env '{args.env}'")
        for rd in run_dirs:
            r = compute_for_run(rd, args.env, seed=args.seed)
            _print_results(r["env"], r["run"], r["mdf"], r["pdf"], r["cdf"], r["wo"])

    elif args.run_dir:
        rd = Path(args.run_dir)
        if not rd.exists():
            sys.exit(f"Run dir not found: {rd}")
        env = args.env or _detect_env(rd)
        if not env:
            sys.exit("Could not detect env from run dir name — pass --env explicitly")
        r = compute_for_run(rd, env, seed=args.seed)
        _print_results(r["env"], r["run"], r["mdf"], r["pdf"], r["cdf"], r["wo"])
        results.append(r)

    elif args.env:
        r = compute_for_run(None, args.env, seed=args.seed)
        _print_results(r["env"], r["run"], r["mdf"], r["pdf"], r["cdf"], r["wo"])
        results.append(r)

    else:
        parser.print_help()
        sys.exit(1)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w") as f:
            json.dump(results if len(results) > 1 else results[0], f, indent=2)
        print(f"\nSaved → {out}")


if __name__ == "__main__":
    main()
