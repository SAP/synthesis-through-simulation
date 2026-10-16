"""
Synthesis runner — orchestrator for data synthesis experiments.

Synthesizers are auto-discovered from the synthesizer/ package at startup.
To add a new synthesizer: create synthesizer/<name>.py with a class that
subclasses synthesizer.base.Synthesizer.  No changes here are needed.

Usage
-----
  synthesize --env hr setup
  synthesize --env hr list-synthesizers
  synthesize --env hr run --synthesizer agent --intent ADD_EMPLOYEE --mode informed
  synthesize --env hr batch --synthesizer agent --n 20 --mode informed
  synthesize --env hr validate

  synthesize --env it_management setup
  synthesize --env it_management run --synthesizer it_agent --intent FILE_TICKET --mode informed
  synthesize --env it_management batch --synthesizer it_agent --n 20 --mode blind
  synthesize --env it_management validate
"""

from __future__ import annotations

import argparse
import datetime
import importlib
import json
import pkgutil
import shutil
import sys
from pathlib import Path
from typing import Dict

from synthesize import synthesizer as _syn_pkg
from synthesize.environments.hr import validate as _hr_validate

# ── Module-level mutable env state (default: hr) ─────────────────────────────
from synthesize.environments.hr.db.db import DB_PATH as _HR_DB_PATH
from synthesize.synthesizer.base import Synthesizer
from synthesize.synthesizer.default_agent import DefaultAgentSynthesizer
from synthesize.synthesizer.generalist_synthesizer import GeneralistSynthesizer

DB_PATH = _HR_DB_PATH
_validate = _hr_validate
SNAPSHOT_PATH = DB_PATH.parent / "hr_snapshot.db"
_ENV = "hr"


def _init_env(env_name: str) -> None:
    """Update module-level DB_PATH, SNAPSHOT_PATH, and _validate for the given env."""
    global DB_PATH, SNAPSHOT_PATH, _validate, _ENV
    _ENV = env_name
    if env_name == "hr":
        DB_PATH = _HR_DB_PATH
        SNAPSHOT_PATH = DB_PATH.parent / "hr_snapshot.db"
        _validate = _hr_validate
    elif env_name == "it_management":
        from synthesize.environments.it_management import validate as _it_validate
        from synthesize.environments.it_management.db.db import DB_PATH as _it_db

        DB_PATH = _it_db
        SNAPSHOT_PATH = DB_PATH.parent / "it_management_snapshot.db"
        _validate = _it_validate
    elif env_name == "airline":
        from synthesize.environments.airline import validate as _airline_validate
        from synthesize.environments.airline.db.db import DB_PATH as _airline_db

        DB_PATH = _airline_db
        SNAPSHOT_PATH = DB_PATH.parent / "airline_snapshot.db"
        _validate = _airline_validate
    elif env_name == "banking":
        from synthesize.environments.banking import validate as _banking_validate
        from synthesize.environments.banking.db.db import DB_PATH as _banking_db

        DB_PATH = _banking_db
        SNAPSHOT_PATH = DB_PATH.parent / "banking_snapshot.db"
        _validate = _banking_validate
    elif env_name == "pharmacy":
        from synthesize.environments.pharmacy import validate as _pharmacy_validate
        from synthesize.environments.pharmacy.db.db import DB_PATH as _pharmacy_db

        DB_PATH = _pharmacy_db
        SNAPSHOT_PATH = DB_PATH.parent / "pharmacy_snapshot.db"
        _validate = _pharmacy_validate
    elif env_name == "university":
        from synthesize.environments.university import validate as _university_validate
        from synthesize.environments.university.db.db import DB_PATH as _university_db

        DB_PATH = _university_db
        SNAPSHOT_PATH = DB_PATH.parent / "university_snapshot.db"
        _validate = _university_validate
    elif env_name == "ecommerce":
        from synthesize.environments.ecommerce import validate as _ecommerce_validate
        from synthesize.environments.ecommerce.db.db import DB_PATH as _ecommerce_db

        DB_PATH = _ecommerce_db
        SNAPSHOT_PATH = DB_PATH.parent / "ecommerce_snapshot.db"
        _validate = _ecommerce_validate
    elif env_name == "forum":
        from synthesize.environments.forum import validate as _forum_validate
        from synthesize.environments.forum.db.db import DB_PATH as _forum_db

        DB_PATH = _forum_db
        SNAPSHOT_PATH = DB_PATH.parent / "forum_snapshot.db"
        _validate = _forum_validate
    elif env_name == "retail":
        from synthesize.environments.retail import validate as _retail_validate
        from synthesize.environments.retail.db.db import DB_PATH as _retail_db

        DB_PATH = _retail_db
        SNAPSHOT_PATH = DB_PATH.parent / "retail_snapshot.db"
        _validate = _retail_validate
    elif env_name == "cloud":
        from synthesize.environments.cloud import validate as _cloud_validate
        from synthesize.environments.cloud.db.cloud_db import DB_PATH as _cloud_db

        DB_PATH = _cloud_db
        SNAPSHOT_PATH = DB_PATH.parent / "cloud_snapshot.db"
        _validate = _cloud_validate
    elif env_name == "obfuscated_airline":
        from synthesize.environments.obfuscated_airline import validate as _oa_validate
        from synthesize.environments.obfuscated_airline.db.db import DB_PATH as _oa_db

        DB_PATH = _oa_db
        SNAPSHOT_PATH = DB_PATH.parent / "obfuscated_airline_snapshot.db"
        _validate = _oa_validate
    else:
        raise ValueError(
            f"Unknown environment: {env_name!r}. "
            f"Valid: hr, it_management, airline, banking, pharmacy, university, ecommerce, forum, retail, cloud, obfuscated_airline"
        )


# ── Synthesizer auto-discovery ────────────────────────────────────────────────
# Any module in synthesizer/ that defines a Synthesizer subclass is registered.

SYNTHESIZERS: Dict[str, Synthesizer] = {}

for _, _mod_name, _ in pkgutil.iter_modules(_syn_pkg.__path__):
    if _mod_name == "base":
        continue
    _mod = importlib.import_module(f"synthesize.synthesizer.{_mod_name}")
    for _obj in vars(_mod).values():
        if (
            isinstance(_obj, type)
            and issubclass(_obj, Synthesizer)
            and _obj is not Synthesizer
            and _obj is not DefaultAgentSynthesizer
            and _obj is not GeneralistSynthesizer
        ):
            _inst = _obj()
            SYNTHESIZERS[_inst.name] = _inst

_pkg_parent = Path(__file__).parents[2]
RUNS_DIR = (
    (_pkg_parent / ".runs") if (_pkg_parent / "pyproject.toml").exists() else (Path.cwd() / ".runs")
)
# For editable installs: parents[2] is the project root (contains pyproject.toml).
# For non-editable installs: fall back to CWD (run synthesize from project root).


# ── DB snapshot / reset ───────────────────────────────────────────────────────


def create_snapshot() -> None:
    """Copy the current DB to the snapshot file (preserves existing data)."""
    shutil.copy2(DB_PATH, SNAPSHOT_PATH)
    print(f"Snapshot created: {SNAPSHOT_PATH}")


def reset_db() -> None:
    """Restore the working DB from the snapshot."""
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(
            f"No snapshot found at {SNAPSHOT_PATH}. "
            f"Run 'synthesize --env {_ENV} setup' then "
            f"'synthesize --env {_ENV} snapshot' first."
        )
    shutil.copy2(SNAPSHOT_PATH, DB_PATH)


def _save_run(
    label: str,
    trajectories: list | None = None,
    synthesizer_name: str = "",
    run_dir: Path | None = None,
) -> Path:
    """Save run artifacts to .runs/<env>_<label>_<ts>/ and push to Langfuse if configured."""
    if run_dir is None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = f"{_ENV}_{label}_{ts}"
        run_dir = RUNS_DIR / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        run_name = run_dir.name
        ts = run_name.rsplit("_", 2)[-2] + "_" + run_name.rsplit("_", 1)[-1]

    # DB snapshot (end state)
    shutil.copy2(DB_PATH, run_dir / "snapshot.db")
    print(f"\nDB snapshot saved: {run_dir / 'snapshot.db'}")

    # Baseline snapshot (pre-run state — used by coverage metrics to exclude seed data)
    if SNAPSHOT_PATH.exists():
        shutil.copy2(SNAPSHOT_PATH, run_dir / "baseline.db")
        print(f"Baseline snapshot: {run_dir / 'baseline.db'}")

    # Validation report — full per-check results (not just summary)
    _validate.set_db(run_dir / "snapshot.db")
    results = _validate.run(as_json=False, show_sample=3)
    _validate.set_db(DB_PATH)

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = total - passed

    report = {
        "env": _ENV,
        "synthesizer": synthesizer_name,
        "label": label,
        "run_name": run_name,
        "timestamp": ts,
        "summary": {"total_checks": total, "passed": passed, "failed": failed},
        "checks": results,
    }
    (run_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"Validation report: {run_dir / 'report.json'}  ({passed}/{total} checks passed)")

    # Trajectories — written here only for non-batch callers (cmd_run etc.)
    # cmd_batch streams them to disk during the run, so trajectories is None there.
    traj_path = run_dir / "trajectories.jsonl"
    if trajectories:
        with open(traj_path, "w") as f:
            for t in trajectories:
                f.write(json.dumps(t, default=str) + "\n")
        print(f"Trajectories saved to {traj_path}")
    elif traj_path.exists():
        print(f"Trajectories saved to {traj_path}")

    # Push to Langfuse (opt-in, no-op if keys not set or credentials invalid)
    try:
        from synthesize.langfuse_pusher import push_run_to_langfuse
        lf_trajs = trajectories
        if lf_trajs is None and traj_path.exists():
            import json as _json
            lf_trajs = [_json.loads(line) for line in traj_path.read_text().splitlines() if line.strip()]
        push_run_to_langfuse(lf_trajs or [], report, _ENV, run_name, synthesizer_name)
    except Exception as _lf_err:
        print(f"[Langfuse] skipped: {_lf_err}")

    return run_dir


# ── CLI commands ──────────────────────────────────────────────────────────────


def cmd_setup(_args) -> None:
    """Initialize (or re-initialize) the environment DB."""
    if _ENV == "hr":
        from synthesize.environments.hr.setup import setup

        setup()
    elif _ENV == "it_management":
        from synthesize.environments.it_management.setup import setup

        setup()
    elif _ENV == "airline":
        from synthesize.environments.airline.setup import setup

        setup()
    elif _ENV == "banking":
        from synthesize.environments.banking.setup import setup

        setup()
    elif _ENV == "pharmacy":
        from synthesize.environments.pharmacy.setup import setup

        setup()
    elif _ENV == "university":
        from synthesize.environments.university.setup import setup

        setup()
    elif _ENV == "ecommerce":
        from synthesize.environments.ecommerce.setup import setup

        setup()
    elif _ENV == "forum":
        from synthesize.environments.forum.setup import setup

        setup()
    elif _ENV == "retail":
        from synthesize.environments.retail.setup import setup

        setup()
    elif _ENV == "cloud":
        from synthesize.environments.cloud.setup import setup

        setup()
    elif _ENV == "obfuscated_airline":
        from synthesize.environments.obfuscated_airline.setup import setup

        setup()
    else:
        print(f"Error: no setup defined for env {_ENV!r}")
        sys.exit(1)


def cmd_validate(_args) -> None:
    """Run all validation checks against the current DB."""
    results = _validate.run(as_json=False, show_sample=3)
    failed = sum(1 for r in results if r["status"] == "FAIL")
    sys.exit(1 if failed else 0)


def cmd_list_synthesizers(_args) -> None:
    print(f"{'Synthesizer':<20} {'Batch':<7} Description")
    print("-" * 70)
    for name, synth in sorted(SYNTHESIZERS.items()):
        batch_flag = "yes" if synth.supports_batch else "no"
        print(f"  {name:<18} {batch_flag:<7} {synth.description}")


def cmd_list_intents(args) -> None:
    synth_name = getattr(args, "synthesizer", None) or ("agent" if _ENV == "hr" else "it_agent")
    synth = SYNTHESIZERS.get(synth_name)
    if synth is None:
        print(f"Synthesizer {synth_name!r} not found. Available: {', '.join(sorted(SYNTHESIZERS))}")
        return
    intents = synth.list_intents() or []
    if not intents:
        print(f"Synthesizer {synth_name!r} has no intents.")
        return
    # Resolve intent definitions from synthesizer
    intent_defs = getattr(synth, "intents", None)
    if intent_defs is None:
        # Fall back to HR's module-level INTENTS for the legacy AgentSynthesizer
        from synthesize.synthesizer.agent_synthesizer import INTENTS as _HR_INTENTS

        intent_defs = _HR_INTENTS
    print(f"{'Intent':<25} Description")
    print("-" * 80)
    for name in intents:
        idef = intent_defs.get(name)
        brief = (idef.brief[:54] + "…" if len(idef.brief) > 55 else idef.brief) if idef else ""
        print(f"  {name:<23} {brief}")


def cmd_run(args) -> None:
    synth_name = args.synthesizer
    if synth_name not in SYNTHESIZERS:
        print(
            f"Error: unknown synthesizer {synth_name!r}. "
            f"Available: {', '.join(sorted(SYNTHESIZERS))}"
        )
        sys.exit(1)

    synth = SYNTHESIZERS[synth_name]

    if not args.no_reset:
        reset_db()
        print("DB reset to snapshot baseline.")

    if args.seed is not None:
        import random

        random.seed(args.seed)

    params = synth.params_from_args(args)
    if args.seed is not None:
        params["seed"] = args.seed

    # For agent-style synthesizers: sample run_params via the synthesizer's own sampler.
    if "intent" in params and params.get("intent") and "run_params" not in params:
        intent_name = params["intent"].upper()
        mode = params.get("mode", "blind")
        sampled = synth.sample_params(intent=intent_name, mode=mode)
        if sampled is None:
            print(f"Error: no eligible records in DB for intent {intent_name!r}.")
            sys.exit(1)
        run_params = sampled.get("run_params", {})
        params["run_params"] = run_params
        print(f"Intent : {intent_name}")
        print(f"Mode   : {mode}")
        print(f"Params : {json.dumps(run_params, default=str, indent=2)}")
        print()

    result = synth.run(params)

    # Print trajectory summary (agent synthesizer).
    if result.trajectories:
        for traj in result.trajectories:
            if "success" in traj:
                print(f"Success      : {traj['success']}")
                print(f"Steps        : {traj.get('total_steps', 'n/a')}")
                print(f"Errors       : {traj.get('error_count', 'n/a')}")
                print(f"Recoveries   : {traj.get('recovery_count', 'n/a')}")
                if "postconditions" in traj:
                    print("Postconditions:")
                    for check, ok in traj["postconditions"].items():
                        print(f"  {'✓' if ok else '✗'} {check}")

    # Build run label.
    if result.trajectories and "intent" in result.trajectories[0]:
        intent = result.trajectories[0].get("intent", synth_name)
        mode = result.trajectories[0].get("mode", "")
        label = f"{intent}_{mode}"
    else:
        label = synth_name

    _save_run(label, trajectories=result.trajectories or None, synthesizer_name=synth_name)


def cmd_batch(args) -> None:
    synth_name = args.synthesizer
    if synth_name not in SYNTHESIZERS:
        print(f"Error: unknown synthesizer {synth_name!r}.")
        sys.exit(1)

    synth = SYNTHESIZERS[synth_name]
    if not synth.supports_batch:
        print(f"Error: synthesizer {synth_name!r} does not support batch mode.")
        sys.exit(1)

    if not args.no_reset:
        reset_db()
        print("DB reset to snapshot baseline.")

    if args.seed is not None:
        import random

        random.seed(args.seed)

    intent_filter = args.intent.upper() if args.intent else None
    mode = args.mode

    trajectories = []
    success_count = 0
    total = args.n

    # Pre-create run directory so trajectories can be streamed as they complete.
    intent_label_pre = intent_filter or "batch"
    ts_pre = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name_pre = f"{_ENV}_{intent_label_pre}_{mode}_{ts_pre}"
    run_dir_pre = RUNS_DIR / run_name_pre
    run_dir_pre.mkdir(parents=True, exist_ok=True)
    traj_path = run_dir_pre / "trajectories.jsonl"
    print(f"Streaming trajectories → {traj_path}")

    traj_file = open(traj_path, "w")  # noqa: WPS515
    try:
        for i in range(total):
            sampled = synth.sample_params(
                intent=intent_filter,
                mode=mode,
                evolve_every=getattr(args, "evolve_every", 5),
                explore_mode=getattr(args, "explore_mode", "staged"),
                explore_runs=getattr(args, "explore_runs", 5),
                enable_heuristics=not getattr(args, "no_heuristics", False),
                enable_plan=not getattr(args, "no_plan", False),
                enable_coverage=not getattr(args, "no_coverage", False),
            )
            if sampled is None:
                print(f"[{i + 1}/{total}] skip — no eligible records")
                continue

            if args.seed is not None:
                sampled["seed"] = args.seed + i

            intent_label = sampled.get("intent", synth_name)
            print(f"[{i + 1}/{total}] {intent_label} ({mode}) ...", end=" ", flush=True)
            try:
                result = synth.run(sampled)
                if result.trajectories:
                    traj = result.trajectories[0]
                    if "success" in traj:
                        mark = "✓" if traj["success"] else "✗"
                        print(
                            f"{mark}  writes={traj.get('successful_writes', '?')} "
                            f"steps={traj.get('total_steps', '?')} errors={traj.get('error_count', '?')}"
                        )
                        if traj.get("success"):
                            success_count += 1
                    else:
                        print("done")
                    trajectories.append(traj)
                    # Stream to disk immediately so it's readable mid-run
                    traj_file.write(json.dumps(traj, default=str) + "\n")
                    traj_file.flush()
                else:
                    print("done")
            except Exception as exc:
                print(f"ERROR: {exc}")
    finally:
        traj_file.close()

    completed = len(trajectories)
    if not trajectories:
        print(
            f"\nWarning: no state changes — all {total} runs were skipped or errored. DB is unchanged."
        )
        return

    print(f"\nCompleted: {completed}/{total}  Success rate: {success_count}/{completed}")

    intent_label = intent_filter or "batch"
    _save_run(
        f"{intent_label}_{mode}",
        trajectories=None,  # already streamed to traj_path above
        synthesizer_name=synth_name,
        run_dir=run_dir_pre,
    )


# ── Entry point ───────────────────────────────────────────────────────────────


def cmd_benchmark(args) -> None:
    """Compute benchmark metrics over synthesis runs."""
    from synthesize.benchmarking import (
        ALL_METRICS,
        DEFAULT_METRICS,
        EXTENDED_METRICS,
        compute_metrics,
        load_from_langfuse,
        load_from_local,
    )
    from synthesize.benchmarking.reporter import print_report

    # Resolve metrics suite
    metrics_choice = getattr(args, "metrics", "default")
    if metrics_choice == "extended":
        metrics = EXTENDED_METRICS
    elif metrics_choice == "all":
        metrics = ALL_METRICS
    else:
        metrics = DEFAULT_METRICS

    if args.source == "local":
        run_dir = Path(args.run_dir) if args.run_dir else None
        records = load_from_local(
            runs_dir=RUNS_DIR,
            run_dir=run_dir,
            env=_ENV if not run_dir else None,
            intent=args.intent.upper() if args.intent else None,
            mode=args.mode,
        )
        if not records:
            print("No matching runs found in .runs/")
            return
        db_path = (
            (run_dir / "snapshot.db") if run_dir and (run_dir / "snapshot.db").exists() else None
        )
        results = compute_metrics(records, metrics=metrics, db_path=db_path)
        label = args.run_dir or f"{_ENV}/{args.intent or '*'}/{args.mode or '*'}"
        print_report(results, label=label, record_count=len(records))
    elif args.source == "langfuse":
        if not args.dataset:
            print("Error: --dataset is required for --source langfuse")
            return
        if args.reproduce_db:
            from synthesize.benchmarking.reproduce import reproduce_db

            records = load_from_langfuse(args.dataset)
            item = next((r for r in records if str(r.metadata.run_name) == args.reproduce_db), None)
            if item is None:
                available = [str(r.metadata.run_name) for r in records if r.metadata.run_name]
                print(f"Item {args.reproduce_db!r} not found in dataset {args.dataset!r}.")
                if available:
                    print(f"  Available run names: {', '.join(available[:10])}")
                return
            run_name_safe = args.reproduce_db.replace("/", "_").replace(" ", "_")
            out_path = RUNS_DIR / f"reproduced_{run_name_safe}.db"
            RUNS_DIR.mkdir(parents=True, exist_ok=True)
            try:
                db_path = reproduce_db(item, _ENV, out_path=out_path)
            except NotImplementedError as exc:
                print(f"Error: {exc}")
                return
            print(f"Reproduced DB: {db_path}")
            return
        from synthesize.benchmarking.evaluator import run_langfuse_evaluation

        results, record_count = run_langfuse_evaluation(dataset_name=args.dataset)
        print_report(results, label=args.dataset, record_count=record_count)


def cmd_explore_dispatch(args) -> None:
    """Dispatch explore sub-subcommands for the GeneralistPopulator manifest."""
    manifest_dir = RUNS_DIR / "exploration" / _ENV
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "manifest.db"

    subcmd = args.explore_command
    if subcmd == "show":
        if not manifest_path.exists():
            print(f"No manifest found at {manifest_path}. Run the generalist_populator first.")
            return
        from synthesize.exploration.manifest import ExplorationManifest

        m = ExplorationManifest(manifest_path)
        try:
            print(m.to_prompt_context())
        finally:
            m.close()
    elif subcmd == "reset":
        if manifest_path.exists():
            manifest_path.unlink()
            print(f"Manifest reset: {manifest_path}")
        else:
            print(f"No manifest to reset at {manifest_path}")
    else:
        print(f"Unknown explore subcommand: {subcmd!r}")
        sys.exit(1)


def cmd_evolve_dispatch(args) -> None:
    """Dispatch evolution sub-subcommands."""
    from synthesize.evolution import cli as evolve_cli

    evolve_dir = RUNS_DIR / "evolution" / _ENV
    evolve_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(evolve_dir / "trajectories.db")
    library_path = str(evolve_dir / "intent_library.json")

    # Resolve synthesizer: default to the first one matching the env
    synth_name = getattr(args, "synthesizer", None)
    if synth_name:
        synth = SYNTHESIZERS.get(synth_name)
        if synth is None:
            print(f"Error: synthesizer {synth_name!r} not found. Available: {sorted(SYNTHESIZERS)}")
            sys.exit(1)
    else:
        # Pick first DefaultAgentSynthesizer for the current env
        from synthesize.synthesizer.default_agent import DefaultAgentSynthesizer

        candidates = [s for s in SYNTHESIZERS.values() if isinstance(s, DefaultAgentSynthesizer)]
        if not candidates:
            print("Error: no agent synthesizer found for evolution.")
            sys.exit(1)
        synth = candidates[0]

    subcmd = args.evolve_command
    if subcmd == "init":
        evolve_cli.cmd_init(args, synth, db_path, library_path)
    elif subcmd == "run":
        evolve_cli.cmd_run(args, synth, db_path, library_path)
    elif subcmd == "evolve":
        evolve_cli.cmd_evolve(args, synth, db_path, library_path)
    elif subcmd == "loop":
        evolve_cli.cmd_loop(args, synth, db_path, library_path)
    elif subcmd == "show":
        evolve_cli.cmd_show(args, synth, db_path, library_path)
    elif subcmd == "compare":
        evolve_cli.cmd_compare(args, synth, db_path, library_path)
    elif subcmd == "stats":
        evolve_cli.cmd_stats(args, synth, db_path, library_path)
    elif subcmd == "report":
        evolve_cli.cmd_report(args, synth, db_path, library_path)
    elif subcmd == "export":
        evolve_cli.cmd_export(args, synth, db_path, library_path)
    else:
        print(f"Unknown evolve subcommand: {subcmd!r}")
        sys.exit(1)


def main() -> None:
    # Pre-parse --env before the subcommand so env-specific routing is in effect.
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument(
        "--env",
        choices=["hr", "it_management", "airline", "banking", "pharmacy", "university", "ecommerce", "forum", "retail", "cloud", "obfuscated_airline"],
        default="hr",
        help="Target environment (default: hr)",
    )
    pre_args, remaining_argv = pre_parser.parse_known_args()
    _init_env(pre_args.env)

    parser = argparse.ArgumentParser(
        description="Synthesis runner — orchestrates synthesizers and validates output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[pre_parser],
    )
    sub = parser.add_subparsers(dest="command")

    # setup
    sub.add_parser("setup", help="Initialize (or re-initialize) the environment DB")

    # validate
    sub.add_parser("validate", help="Run all validation checks against the current DB")

    # snapshot
    sub.add_parser(
        "snapshot",
        help="Save current DB as-is to the snapshot (preserves existing data)",
    )

    # list-synthesizers
    sub.add_parser("list-synthesizers", help="List all auto-discovered synthesizers")

    # list-intents
    li_p = sub.add_parser("list-intents", help="List intents for an agent synthesizer")
    li_p.add_argument(
        "--synthesizer",
        choices=sorted(SYNTHESIZERS),
        default=None,
        help="Which synthesizer to list intents for (default: agent or it_agent based on --env)",
    )

    # run
    run_p = sub.add_parser("run", help="Run a single synthesis (resets DB to snapshot first)")
    run_p.add_argument(
        "--synthesizer",
        required=True,
        choices=sorted(SYNTHESIZERS),
        help=f"Which synthesizer to use. Available: {', '.join(sorted(SYNTHESIZERS))}",
    )
    run_p.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    run_p.add_argument(
        "--no-reset", action="store_true", help="Skip DB reset (use current DB state)"
    )
    for synth in SYNTHESIZERS.values():
        synth.add_arguments(run_p)
    run_p.add_argument(
        "--explore-mode",
        choices=["explore", "staged", "interleaved"],
        default="staged",
        dest="explore_mode",
        help="Generalist populator explore mode (default: staged)",
    )
    run_p.add_argument(
        "--explore-runs",
        type=int,
        default=5,
        dest="explore_runs",
        help="Number of explore-phase runs before switching to execute (default: 5)",
    )

    # batch
    batch_p = sub.add_parser(
        "batch",
        help="Run N synthesis iterations against the same accumulating DB",
    )
    batch_p.add_argument(
        "--synthesizer",
        required=True,
        choices=[n for n, s in SYNTHESIZERS.items() if s.supports_batch],
        help=f"Which synthesizer to use. Available: {', '.join(n for n, s in SYNTHESIZERS.items() if s.supports_batch)}",
    )
    batch_p.add_argument("--n", type=int, default=10, help="Number of runs")
    batch_p.add_argument(
        "--mode",
        choices=["blind", "informed", "evolve"],
        default="informed",
        help="Agent mode: blind, informed, or evolve (default: informed)",
    )
    batch_p.add_argument("--intent", help="If set, only run this intent (else cycles through all)")
    batch_p.add_argument("--seed", type=int, default=None)
    batch_p.add_argument(
        "--no-reset", action="store_true", help="Skip DB reset (use current DB state)"
    )
    batch_p.add_argument(
        "--evolve-every",
        type=int,
        default=5,
        dest="evolve_every",
        help="In evolve mode: trigger rule extraction every N runs (default: 5)",
    )
    batch_p.add_argument(
        "--explore-mode",
        choices=["explore", "staged", "interleaved"],
        default="staged",
        dest="explore_mode",
        help="Generalist populator explore mode (default: staged)",
    )
    batch_p.add_argument(
        "--explore-runs",
        type=int,
        default=5,
        dest="explore_runs",
        help="Number of explore-phase runs before switching to execute (default: 5)",
    )
    batch_p.add_argument(
        "--no-heuristics",
        action="store_true",
        dest="no_heuristics",
        help="Disable heuristic extraction and injection (ablation: isolate heuristic contribution)",
    )
    batch_p.add_argument(
        "--no-plan",
        action="store_true",
        dest="no_plan",
        help="Disable structured plan LLM call — use generic task description (ablation: isolate PLAN contribution)",
    )
    batch_p.add_argument(
        "--no-coverage",
        action="store_true",
        dest="no_coverage",
        help="Disable coverage enforcement hard override in plan phase (ablation: isolate coverage contribution)",
    )

    # benchmark
    bench_p = sub.add_parser("benchmark", help="Compute metrics over synthesis runs")
    bench_p.add_argument(
        "--source",
        choices=["local", "langfuse"],
        default="local",
        help="Data source: local .runs/ or Langfuse dataset (default: local)",
    )
    bench_p.add_argument(
        "--run-dir",
        help="Single run directory to benchmark (local source only)",
    )
    bench_p.add_argument("--intent", help="Filter by intent (local source only)")
    bench_p.add_argument(
        "--mode",
        choices=["blind", "informed", "evolve"],
        default=None,
        help="Filter by mode (local source only)",
    )
    bench_p.add_argument("--dataset", help="Langfuse dataset name (langfuse source only)")
    bench_p.add_argument(
        "--reproduce-db",
        help="Reproduce a DB from a Langfuse dataset item by run_name (langfuse source only)",
    )
    bench_p.add_argument(
        "--metrics",
        choices=["default", "extended", "all"],
        default="default",
        help=(
            "Metric suite to use: "
            "default (7 core metrics), "
            "extended (+ diversity + effectiveness), "
            "all (full NeurIPS suite incl. DB coverage)"
        ),
    )

    # explore
    explore_p = sub.add_parser(
        "explore",
        help="Manage the GeneralistPopulator exploration manifest for this environment",
    )
    explore_sub = explore_p.add_subparsers(dest="explore_command", required=True)
    explore_sub.add_parser("show", help="Print current manifest state (tools, deps, priors)")
    explore_sub.add_parser("reset", help="Delete the manifest DB (forces re-exploration)")

    # evolve
    evolve_p = sub.add_parser(
        "evolve",
        help="Auto-evolving intents: discover rules from agent trajectories",
    )
    evolve_p.add_argument(
        "--synthesizer",
        choices=sorted(SYNTHESIZERS),
        default=None,
        help="Synthesizer to use (default: first agent synthesizer for --env)",
    )
    evolve_sub = evolve_p.add_subparsers(dest="evolve_command", required=True)

    evolve_sub.add_parser("init", help="Initialize intent library from synthesizer")

    e_run = evolve_sub.add_parser("run", help="Run synthesis and record trajectories")
    e_run.add_argument("--intent", help="Intent to run (default: cycle all)")
    e_run.add_argument("--count", type=int, default=12, help="Number of runs")
    e_run.add_argument("--mode", choices=["blind", "informed"], default="blind")

    evolve_sub.add_parser("evolve", help="Discover intents + learn rules")

    e_loop = evolve_sub.add_parser("loop", help="Full evolution loop")
    e_loop.add_argument("--generations", type=int, default=2, help="Number of generations")
    e_loop.add_argument("--batch", type=int, default=18, help="Trajectories per generation")
    e_loop.add_argument("--mode", choices=["blind", "informed"], default="blind")
    e_loop.add_argument(
        "--append", action="store_true", help="Append to existing library (default: reset)"
    )

    e_show = evolve_sub.add_parser("show", help="Show intent details")
    e_show.add_argument("intent", help="Intent name")

    e_compare = evolve_sub.add_parser("compare", help="Compare original vs learned rules")
    e_compare.add_argument("intent", help="Intent name")

    evolve_sub.add_parser("stats", help="Show statistics")
    evolve_sub.add_parser("report", help="Generate evolution report")

    e_export = evolve_sub.add_parser("export", help="Export library to JSON")
    e_export.add_argument("--output", help="Output path")

    args = parser.parse_args(remaining_argv)

    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "snapshot":
        create_snapshot()
    elif args.command == "list-synthesizers":
        cmd_list_synthesizers(args)
    elif args.command == "list-intents":
        cmd_list_intents(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "batch":
        cmd_batch(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)
    elif args.command == "evolve":
        cmd_evolve_dispatch(args)
    elif args.command == "explore":
        cmd_explore_dispatch(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
