"""
Multi-table baseline evaluation for STS paper (NeurIPS 2026).

Evaluates two multi-table synthesizers:
  - SDV HMA (Hierarchical Modeling Algorithm): fits a generative model over a full
    multi-table schema with FK relationships, then generates the whole schema jointly.
  - REaLTabFormer (relational mode): trains a GPT-2 parent model on the root table,
    then trains a seq2seq child model conditioned on parent rows via FK join.

Training source: src/synthesize/environments/<env>/db/<env>_snapshot.db
(seed-only, before any agent trajectory — same as tabular_baseline_eval.py)

Environments covered:
  - airline:  users → reservations → {reservation_flights, reservation_passengers,
                                       payment_history}
  - banking:  customer → account  (txn has 0 seed rows — skipped)
  - retail:   users → orders → {order_items, payment_history}

The 7 remaining environments have zero rows in all primary write tables and are
inapplicable for both methods (same constraint as single-table baselines).

Metrics:
  MDF  — Marginal Distribution Fidelity on the root write table (JSD-based)
  PDF  — Pairwise Distribution Fidelity on the root write table
  CDF  — Cross-table child-count fidelity (JSD-based, against relational priors)
  FK   — Referential integrity within the generated dataset (internal consistency)

Usage:
    python scripts/multitable_baseline_eval.py [--n-parent 20] [--epochs 100]
    python scripts/multitable_baseline_eval.py --skip-rtf       # HMA only
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sqlite3
import sys
import tempfile
import time
import warnings
from pathlib import Path
from typing import Any

import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

ENV_BASE = ROOT / "src" / "synthesize" / "environments"

# ── JSD similarity (shared with tabular_baseline_eval.py) ─────────────────────

def jsd_similarity(p: dict, q: dict) -> float:
    all_keys = set(p) | set(q)
    tp = sum(p.values()) or 1
    tq = sum(q.values()) or 1
    pn = {k: p.get(k, 0) / tp for k in all_keys}
    qn = {k: q.get(k, 0) / tq for k in all_keys}
    m  = {k: 0.5 * (pn[k] + qn[k]) for k in all_keys}

    def kl(a: dict, b: dict) -> float:
        s = 0.0
        for k in all_keys:
            if a[k] > 0:
                s += a[k] * math.log(a[k] / (b[k] if b[k] > 0 else 1e-12))
        return s

    jsd = 0.5 * kl(pn, m) + 0.5 * kl(qn, m)
    return max(0.0, min(1.0, 1.0 - jsd / math.log(2)))


# ── DB helpers ─────────────────────────────────────────────────────────────────

def load_table(db: Path, table: str) -> pd.DataFrame:
    conn = sqlite3.connect(db)
    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)  # noqa: S608
    conn.close()
    return df


# ── Metric helpers ─────────────────────────────────────────────────────────────

def compute_mdf(df: pd.DataFrame, quality_priors: dict, table: str) -> dict[str, float]:
    if table not in quality_priors:
        return {}
    scores: dict[str, float] = {}
    for col, spec in quality_priors[table].items():
        if col not in df.columns:
            continue
        if spec["type"] == "categorical":
            actual = df[col].dropna().value_counts().to_dict()
            scores[col] = jsd_similarity(actual, spec["distribution"])
        elif spec["type"] == "numeric":
            from scipy.stats import ks_2samp
            gen_vals = df[col].dropna().tolist()
            if gen_vals:
                stat, _ = ks_2samp(gen_vals, spec["reference_values"])
                scores[col] = max(0.0, 1.0 - stat)
    return scores


def compute_pdf(df: pd.DataFrame, pairwise_priors: dict, table: str) -> dict[str, float]:
    if not pairwise_priors or table not in pairwise_priors:
        return {}
    scores: dict[str, float] = {}
    for cols, spec in pairwise_priors[table].items():
        c1, c2 = cols
        if c1 not in df.columns or c2 not in df.columns:
            continue
        actual = (
            df[[c1, c2]].dropna()
            .apply(lambda r: (str(r[c1]), str(r[c2])), axis=1)
            .value_counts().to_dict()
        )
        ref_str = {(str(k[0]), str(k[1])): v for k, v in spec["distribution"].items()}
        scores[f"{c1}×{c2}"] = jsd_similarity(actual, ref_str)
    return scores


def compute_cdf(
    parent_df: pd.DataFrame,
    child_df: pd.DataFrame,
    parent_pk: str,
    child_fk: str,
    relational_prior: dict,
    n_max: int,
) -> float:
    """Child-count distribution fidelity for one FK relationship."""
    parent_ids = set(parent_df[parent_pk].dropna())
    counts = child_df[child_fk].value_counts().to_dict() if child_fk in child_df.columns else {}
    child_counts_per_parent = {pid: counts.get(pid, 0) for pid in parent_ids}
    bucket_counts: dict[int, int] = {}
    for cnt in child_counts_per_parent.values():
        b = min(cnt, n_max)
        bucket_counts[b] = bucket_counts.get(b, 0) + 1
    ref = {int(k): v for k, v in relational_prior.items()}
    return jsd_similarity(bucket_counts, ref)


def check_fk_internal(parent_df: pd.DataFrame, child_df: pd.DataFrame,
                       parent_pk: str, child_fk: str) -> dict:
    """FK internal consistency: child FK values all appear in generated parent PKs."""
    if child_fk not in child_df.columns or parent_pk not in parent_df.columns:
        return {"pass_rate": None, "violations": None, "note": "column missing"}
    valid_pks = set(parent_df[parent_pk].dropna())
    violations = (~child_df[child_fk].isin(valid_pks)).sum()
    n = len(child_df)
    return {"pass_rate": float(1 - violations / n) if n else 1.0, "violations": int(violations), "n": n}


# ── Environment config ─────────────────────────────────────────────────────────

ENV_CONFIG: dict[str, dict[str, Any]] = {
    "airline": {
        "db": ENV_BASE / "airline" / "db" / "airline_snapshot.db",
        # Tables to include in multi-table synthesis (ordered root→leaf)
        "tables": ["users", "reservations", "reservation_flights",
                   "reservation_passengers", "payment_history"],
        "pks": {
            "users": "user_id",
            "reservations": "reservation_id",
            "reservation_flights": "id",
            "reservation_passengers": "id",
            "payment_history": "id",
        },
        "fks": [
            # (child_table, child_fk, parent_table, parent_pk)
            ("reservations",          "user_id",        "users",        "user_id"),
            ("reservation_flights",   "reservation_id", "reservations", "reservation_id"),
            ("reservation_passengers","reservation_id", "reservations", "reservation_id"),
            ("payment_history",       "reservation_id", "reservations", "reservation_id"),
        ],
        # Root write table for MDF/PDF
        "root_write_table": "reservations",
        "drop_cols": {
            "reservations": ["reservation_id", "created_at"],
        },
        "quality_priors_module": "synthesize.environments.airline.quality_priors",
        "quality_priors_attr":   "AIRLINE_QUALITY_PRIORS",
        "pairwise_priors_attr":  "AIRLINE_PAIRWISE_PRIORS",
        # CDF: the one FK pair with registered relational priors
        "cdf_checks": [
            {
                "parent_table": "reservations",
                "child_table":  "reservation_flights",
                "parent_pk":    "reservation_id",
                "child_fk":     "reservation_id",
                "n_max": 3,
                "prior": {1: 0.45, 2: 0.50, 3: 0.05},
                "label": "reservations→reservation_flights",
            },
        ],
        # REaLTabFormer: which parent-child pair to model (simplest single path)
        "rtf_parent_table": "reservations",
        "rtf_child_table":  "reservation_flights",
        "rtf_join_on":      "reservation_id",
        "validate_module":  "synthesize.environments.airline.validate",
    },
    "hr": {
        # Use hr_barebone.db: per_person (166) and emp_job (179) have seed rows;
        # hr_snapshot.db has 0 rows in all write tables.
        "db": ENV_BASE / "hr" / "db" / "hr_barebone.db",
        "tables": ["per_person", "emp_job"],
        "pks": {
            "per_person": "person_id",
            "emp_job":    "job_info_id",
        },
        "fks": [
            ("emp_job", "person_id", "per_person", "person_id"),
        ],
        "root_write_table": "emp_job",
        "drop_cols": {
            "emp_job": ["job_info_id", "user_id", "created_on", "last_modified_on",
                        "probation_end_date"],
        },
        "quality_priors_module": "synthesize.environments.hr.quality_priors",
        "quality_priors_attr":   "HR_QUALITY_PRIORS",
        "pairwise_priors_attr":  None,
        # CDF: per_person → emp_job child-count prior (computed from barebone DB)
        # 154/166 persons have 1 job, 11/166 have 2, 1/166 have 3.
        "cdf_checks": [
            {
                "parent_table": "per_person",
                "child_table":  "emp_job",
                "parent_pk":    "person_id",
                "child_fk":     "person_id",
                "n_max": 3,
                "prior": {1: 0.928, 2: 0.066, 3: 0.006},
                "label": "per_person→emp_job",
            },
        ],
        "rtf_parent_table": "per_person",
        "rtf_child_table":  "emp_job",
        "rtf_join_on":      "person_id",
    },
    "retail": {
        "db": ENV_BASE / "retail" / "db" / "retail_snapshot.db",
        "tables": ["users", "orders", "order_items", "payment_history"],
        "pks": {
            "users": "user_id",
            "orders": "order_id",
            "order_items": "id",
            "payment_history": "id",
        },
        "fks": [
            ("orders",          "user_id",  "users",  "user_id"),
            ("order_items",     "order_id", "orders", "order_id"),
            ("payment_history", "order_id", "orders", "order_id"),
        ],
        "root_write_table": "orders",
        "drop_cols": {
            "orders": ["order_id", "created_at", "exchange_items", "exchange_new_items",
                       "exchange_payment_method_id", "exchange_price_difference",
                       "return_items", "return_payment_method_id"],
        },
        "quality_priors_module": "synthesize.environments.retail.quality_priors",
        "quality_priors_attr":   "RETAIL_QUALITY_PRIORS",
        "pairwise_priors_attr":  None,
        "cdf_checks": [
            {
                "parent_table": "orders",
                "child_table":  "order_items",
                "parent_pk":    "order_id",
                "child_fk":     "order_id",
                "n_max": 3,
                "prior": {1: 0.40, 2: 0.35, 3: 0.25},
                "label": "orders→order_items",
            },
        ],
        "rtf_parent_table": "orders",
        "rtf_child_table":  "order_items",
        "rtf_join_on":      "order_id",
        "validate_module":  "synthesize.environments.retail.validate",
    },
    "banking": {
        # Use banking_snapshot.db: 12 customer seed rows + 20 account seed rows.
        # txn has 0 rows in snapshot so is excluded; multitable eval covers
        # the customer→account relationship which is what STS banking reports.
        "db": ENV_BASE / "banking" / "db" / "banking_snapshot.db",
        "tables": ["customer", "account"],
        "pks": {
            "customer": "customer_id",
            "account":  "account_id",
        },
        "fks": [
            ("account", "customer_id", "customer", "customer_id"),
        ],
        "root_write_table": "account",
        "drop_cols": {
            "account": ["account_id", "opening_date"],
        },
        "quality_priors_module": "synthesize.environments.banking.quality_priors",
        "quality_priors_attr":   "BANKING_QUALITY_PRIORS",
        "pairwise_priors_attr":  "BANKING_PAIRWISE_PRIORS",
        # CDF prior computed from banking_snapshot.db: 4/12 customers have 1 account,
        # 8/12 have 2 accounts.
        "cdf_checks": [
            {
                "parent_table": "customer",
                "child_table":  "account",
                "parent_pk":    "customer_id",
                "child_fk":     "customer_id",
                "n_max": 2,
                "prior": {1: 0.333, 2: 0.667},
                "label": "customer→account",
            },
        ],
        "rtf_parent_table": "customer",
        "rtf_child_table":  "account",
        "rtf_join_on":      "customer_id",
        "validate_module":  "synthesize.environments.banking.validate",
    },
}


# ── SDV HMA evaluation ─────────────────────────────────────────────────────────

def eval_hma(env_name: str, n_parent: int) -> dict:
    from sdv.metadata import Metadata
    from sdv.multi_table import HMASynthesizer

    cfg = ENV_CONFIG[env_name]
    db  = cfg["db"]

    print(f"\n  [HMA] Loading tables for {env_name}...")
    tables_data: dict[str, pd.DataFrame] = {}
    for t in cfg["tables"]:
        df = load_table(db, t)
        if len(df) == 0:
            print(f"    WARNING: {t} has 0 rows — skipping HMA for {env_name}")
            return {"env": env_name, "model": "HMA", "applicable": False,
                    "reason": f"{t} has 0 rows"}
        tables_data[t] = df
        print(f"    {t}: {len(df)} rows")

    # Build Metadata: detect column types from data, then set PKs and relationships.
    # detect_from_dataframes auto-detects sdtype='id' for ID-patterned columns and
    # may auto-detect relationships; we clear and re-add them explicitly for control.
    metadata = Metadata.detect_from_dataframes(tables_data)
    for t in cfg["tables"]:
        metadata.set_primary_key(cfg["pks"][t], table_name=t)
    # Clear any auto-detected relationships and add ours explicitly
    metadata.relationships = []
    for child_t, child_fk, parent_t, parent_pk in cfg["fks"]:
        metadata.add_relationship(parent_t, child_t, parent_pk, child_fk)

    print(f"  [HMA] Fitting HMASynthesizer on {env_name}...")
    t0 = time.time()
    synth = HMASynthesizer(metadata, verbose=False)
    synth.fit(tables_data)
    fit_time = time.time() - t0
    print(f"  [HMA] Fit done in {fit_time:.1f}s. Sampling {n_parent} parent rows...")

    t0 = time.time()
    # scale=N means generate N× as many rows as the training set
    root_table = cfg["tables"][0]
    n_seed_root = len(tables_data[root_table])
    scale = n_parent / n_seed_root if n_seed_root > 0 else 1.0
    generated = synth.sample(scale=scale)
    sample_time = time.time() - t0

    gen_target = generated.get(cfg["root_write_table"], pd.DataFrame())
    print(f"  [HMA] Sampled in {sample_time:.1f}s. Generated rows: "
          + ", ".join(f"{t}={len(generated.get(t, []))}" for t in cfg["tables"]))

    return _compute_metrics(env_name, "HMA", cfg, generated, gen_target, fit_time, sample_time)


# ── REaLTabFormer evaluation ───────────────────────────────────────────────────

def eval_realtabformer(env_name: str, n_parent: int, epochs: int) -> dict:
    from realtabformer import REaLTabFormer

    cfg = ENV_CONFIG[env_name]
    db  = cfg["db"]

    parent_table = cfg["rtf_parent_table"]
    child_table  = cfg["rtf_child_table"]
    join_on      = cfg["rtf_join_on"]

    parent_df = load_table(db, parent_table)
    child_df  = load_table(db, child_table)

    if len(parent_df) == 0 or len(child_df) == 0:
        return {"env": env_name, "model": "REaLTabFormer", "applicable": False,
                "reason": f"0 rows in {parent_table} or {child_table}"}

    print(f"\n  [RTF] {env_name}: parent={parent_table}({len(parent_df)}), "
          f"child={child_table}({len(child_df)}), epochs={epochs}")

    # Clean up any leftover checkpoints from prior runs
    parent_save_dir = Path(f"/tmp/rtf_{env_name}_parent")
    for d in ["rtf_checkpoints", "rtf_samples", "rtf_full_save"]:
        if Path(d).exists():
            shutil.rmtree(d)
    if parent_save_dir.exists():
        shutil.rmtree(parent_save_dir)

    # ── Step 1: train TABULAR parent model ─────────────────────────────────
    parent_pk = cfg["pks"][parent_table]
    parent_train = parent_df.drop(columns=cfg.get("drop_cols", {}).get(parent_table, []),
                                   errors="ignore")

    print(f"  [RTF] Training tabular parent model ({parent_table}, {len(parent_train)} rows)...")
    t0 = time.time()
    parent_model = REaLTabFormer(
        model_type="tabular",
        epochs=epochs,
        batch_size=8,
        early_stopping_patience=10,
        random_state=42,
    )
    parent_model.fit(parent_train, device="cpu")
    parent_model.save(parent_save_dir, allow_overwrite=True)
    # save() appends experiment_id as a subdirectory; resolve the actual path
    parent_actual_dir = parent_save_dir / parent_model.experiment_id
    parent_fit_time = time.time() - t0
    print(f"  [RTF] Parent fit: {parent_fit_time:.1f}s")

    # ── Step 2: generate synthetic parent rows ──────────────────────────────
    synthetic_parents = parent_model.sample(n_samples=n_parent, device="cpu")
    if parent_pk not in synthetic_parents.columns:
        synthetic_parents.insert(0, parent_pk, [f"SYN_{i:04d}" for i in range(len(synthetic_parents))])
    print(f"  [RTF] Generated {len(synthetic_parents)} parent rows")

    # ── Step 3: train RELATIONAL child model ───────────────────────────────
    # Relational mode uses the saved parent model as encoder.
    child_train = child_df.copy()
    if join_on not in child_train.columns:
        return {"env": env_name, "model": "REaLTabFormer", "error":
                f"join_on column '{join_on}' missing from child table"}

    print(f"  [RTF] Training relational child model ({child_table}, {len(child_train)} rows)...")
    t0 = time.time()
    child_model = REaLTabFormer(
        model_type="relational",
        parent_realtabformer_path=parent_actual_dir,
        freeze_parent_model=True,
        epochs=epochs,
        batch_size=8,
        early_stopping_patience=10,
        random_state=42,
    )
    child_model.fit(child_train, in_df=parent_df, join_on=join_on, device="cpu")
    child_fit_time = time.time() - t0
    print(f"  [RTF] Child fit: {child_fit_time:.1f}s")

    # ── Step 4: sample child rows conditioned on synthetic parents ──────────
    t0 = time.time()
    synthetic_children = child_model.sample(
        input_unique_ids=synthetic_parents[parent_pk],
        input_df=synthetic_parents,
        device="cpu",
    )
    # RTF places the FK in the DataFrame index — promote it to a column
    if join_on not in synthetic_children.columns:
        synthetic_children.index.name = join_on
        synthetic_children = synthetic_children.reset_index()
    sample_time = time.time() - t0
    print(f"  [RTF] Generated {len(synthetic_children)} child rows in {sample_time:.1f}s")

    # Build generated dict for unified metric computation
    generated = {
        parent_table: synthetic_parents,
        child_table:  synthetic_children,
    }
    gen_target = generated.get(cfg["root_write_table"], pd.DataFrame())
    fit_time   = parent_fit_time + child_fit_time

    # Clean up checkpoints
    for d in ["rtf_checkpoints", "rtf_samples", "rtf_full_save"]:
        if Path(d).exists():
            shutil.rmtree(d, ignore_errors=True)
    if parent_save_dir.exists():
        shutil.rmtree(parent_save_dir, ignore_errors=True)

    return _compute_metrics(env_name, "REaLTabFormer", cfg, generated, gen_target, fit_time, sample_time)


# ── VPR via validate.py (same metric as GP bench_generalist_ablation.py) ──────

def compute_vpr_via_validate(
    synth_df: pd.DataFrame,
    cfg: dict,
    snapshot_db: Path,
    table: str,
) -> dict[str, Any]:
    """Run environment validate.py on a temp DB with generated root-write-table rows appended.

    Inserts only the generated target table rows (same approach as tabular_baseline_eval.py)
    so the comparison is apples-to-apples: both single and multi-table methods are tested on
    whether their generated rows integrate with the real seed database context.

    Returns {"vpr": float, "checks_passed": int, "checks_total": int}.
    VPR = checks_passed / checks_total — identical to GP's bench_generalist_ablation.py.
    If validate_module is not configured, returns {"vpr": None, "note": "..."}.
    """
    import importlib

    validate_module_name = cfg.get("validate_module")
    if not validate_module_name:
        return {"vpr": None, "note": "no validate_module configured"}

    validate = importlib.import_module(validate_module_name)

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        shutil.copy2(snapshot_db, tmp_path)
        conn = sqlite3.connect(tmp_path)
        try:
            synth_df.to_sql(table, conn, if_exists="append", index=False)
        except Exception as e:
            conn.close()
            return {"vpr": None, "note": f"insert failed: {type(e).__name__}"}
        conn.close()

        validate.set_db(tmp_path)
        check_results = validate.run(as_json=True)

        checks_total = len(check_results)
        checks_passed = sum(1 for r in check_results if r["status"] == "PASS")
        vpr = checks_passed / checks_total if checks_total else 1.0
        return {"vpr": vpr, "checks_passed": checks_passed, "checks_total": checks_total}
    finally:
        tmp_path.unlink(missing_ok=True)


# ── Shared metric computation ──────────────────────────────────────────────────

def _compute_metrics(
    env_name: str,
    model_name: str,
    cfg: dict,
    generated: dict[str, pd.DataFrame],
    gen_target: pd.DataFrame,
    fit_time: float,
    sample_time: float,
) -> dict:
    import importlib
    mod = importlib.import_module(cfg["quality_priors_module"])
    quality_priors  = getattr(mod, cfg["quality_priors_attr"])
    pairwise_priors = getattr(mod, cfg["pairwise_priors_attr"]) if cfg.get("pairwise_priors_attr") else None

    target_table = cfg["root_write_table"]
    result: dict[str, Any] = {
        "env": env_name,
        "model": model_name,
        "applicable": True,
        "n_generated": {t: len(df) for t, df in generated.items()},
        "fit_time_s": round(fit_time, 1),
        "sample_time_s": round(sample_time, 1),
    }

    if gen_target.empty:
        result["error"] = f"No rows generated for {target_table}"
        return result

    # MDF
    mdf_scores = compute_mdf(gen_target, quality_priors, target_table)
    result["mdf_per_col"] = mdf_scores
    result["mdf"] = float(sum(mdf_scores.values()) / len(mdf_scores)) if mdf_scores else None

    # PDF
    pdf_scores = compute_pdf(gen_target, pairwise_priors, target_table)
    result["pdf_per_pair"] = pdf_scores
    result["pdf"] = float(sum(pdf_scores.values()) / len(pdf_scores)) if pdf_scores else None

    # CDF
    cdf_scores: dict[str, float] = {}
    for ck in cfg["cdf_checks"]:
        parent_df = generated.get(ck["parent_table"], pd.DataFrame())
        child_df  = generated.get(ck["child_table"],  pd.DataFrame())
        if parent_df.empty or child_df.empty:
            cdf_scores[ck["label"]] = None
            continue
        score = compute_cdf(
            parent_df, child_df,
            ck["parent_pk"], ck["child_fk"],
            ck["prior"], ck["n_max"],
        )
        cdf_scores[ck["label"]] = score
    result["cdf_per_rel"] = cdf_scores
    valid_cdf = [v for v in cdf_scores.values() if v is not None]
    result["cdf"] = float(sum(valid_cdf) / len(valid_cdf)) if valid_cdf else None

    # FK internal consistency
    fk_checks: dict[str, dict] = {}
    for child_t, child_fk, parent_t, parent_pk in cfg["fks"]:
        parent_gen = generated.get(parent_t, pd.DataFrame())
        child_gen  = generated.get(child_t,  pd.DataFrame())
        if parent_gen.empty or child_gen.empty:
            continue
        key = f"{child_t}.{child_fk}→{parent_t}"
        fk_checks[key] = check_fk_internal(parent_gen, child_gen, parent_pk, child_fk)
    result["fk_internal"] = fk_checks

    # VPR via validate.py (same check-level metric as GP and tabular baselines)
    vpr_result = compute_vpr_via_validate(gen_target, cfg, cfg["db"], target_table)
    result["vpr"] = vpr_result.get("vpr")
    result["vpr_checks_passed"] = vpr_result.get("checks_passed")
    result["vpr_checks_total"] = vpr_result.get("checks_total")
    if "note" in vpr_result:
        result["vpr_note"] = vpr_result["note"]

    return result


# ── Summary printing ───────────────────────────────────────────────────────────

def print_summary(results: list[dict]) -> None:
    print(f"\n{'='*80}")
    print("SUMMARY: SDV HMA + REaLTabFormer MULTI-TABLE BASELINES")
    print(f"{'='*80}")
    print(f"{'Env':<12} {'Model':<14} {'MDF':>7} {'PDF':>7} {'CDF':>7} {'FK-int':>7} {'VPR':>7} {'Fit(s)':>7}")
    print("-" * 80)

    applicable = [r for r in results if r.get("applicable")]
    for r in applicable:
        if "error" in r:
            print(f"{r['env']:<12} {r['model']:<14}  ERROR: {r['error'][:40]}")
            continue
        mdf = f"{r['mdf']:.3f}"   if r.get("mdf") is not None else "n/a"
        pdf = f"{r['pdf']:.3f}"   if r.get("pdf") is not None else "n/a"
        cdf = f"{r['cdf']:.3f}"   if r.get("cdf") is not None else "n/a"
        vpr = f"{r['vpr']:.3f}"   if r.get("vpr") is not None else "n/a"
        # FK internal consistency: fraction of child tables with 100% pass
        fk_vals = [v["pass_rate"] for v in r.get("fk_internal", {}).values()
                   if v.get("pass_rate") is not None]
        fk_str = f"{sum(fk_vals)/len(fk_vals):.3f}" if fk_vals else "n/a"
        passed = r.get("vpr_checks_passed")
        total  = r.get("vpr_checks_total")
        vpr_detail = f" ({passed}/{total})" if passed is not None else ""
        print(f"{r['env']:<12} {r['model']:<14} {mdf:>7} {pdf:>7} {cdf:>7} {fk_str:>7} {vpr:>7}{vpr_detail}  fit={r.get('fit_time_s','?')}s")

    # GP reference (K=0 baseline for comparable environments)
    print("-" * 80)
    gp_ref = [
        ("airline", "GP (K=0)",  "0.951", "0.813", "0.970", "1.000", "1.000"),
        ("retail",  "GP (K=0)",  "0.896", "n/a",   "0.918", "1.000", "1.000"),
    ]
    for env, model, mdf, pdf, cdf, fk, vpr in gp_ref:
        print(f"{env:<12} {model:<14} {mdf:>7} {pdf:>7} {cdf:>7} {fk:>7} {vpr:>7}  (agent)")

    print()
    print("FK-int = internal FK consistency (child FK values reference a generated parent PK).")
    print("VPR    = validate.py check-level metric, same as GP scoring (checks_passed/checks_total).")
    print("         FK checks fail for statistical synthesizers because generated parent IDs")
    print("         are synthetic and do not exist in the real seed database.")
    print("GP VPR = 1.000 because GP queries the live DB for valid IDs at write time.")
    print()

    # Per-FK detail
    print("FK internal consistency detail:")
    for r in applicable:
        if "error" in r or not r.get("fk_internal"):
            continue
        for key, chk in r["fk_internal"].items():
            pr = chk.get("pass_rate")
            viol = chk.get("violations", "?")
            n    = chk.get("n", "?")
            icon = "✓" if pr == 1.0 else "✗" if pr == 0.0 else "~"
            print(f"  {r['model']:<14} {r['env']:<10} {icon} {key}: "
                  f"{viol} violations / {n}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-table baseline eval for STS paper")
    parser.add_argument("--n-parent", type=int, default=20,
                        help="synthetic parent rows to generate per env (default: 20)")
    parser.add_argument("--epochs", type=int, default=5,
                        help="REaLTabFormer training epochs per critic round (default: 5). "
                             "The sensitivity-checking loop runs ~5 rounds, so effective "
                             "total epochs = epochs × rounds. Keep ≤10 for tiny seed datasets.")
    parser.add_argument("--envs", nargs="+", default=sorted(ENV_CONFIG.keys()))
    parser.add_argument("--skip-rtf", action="store_true",
                        help="skip REaLTabFormer (run HMA only)")
    args = parser.parse_args()

    results: list[dict] = []

    for env in args.envs:
        if env not in ENV_CONFIG:
            print(f"WARNING: unknown env '{env}', skipping")
            continue
        print(f"\n{'─'*60}")
        print(f"Environment: {env}")
        print(f"{'─'*60}")

        # SDV HMA
        try:
            r = eval_hma(env, args.n_parent)
        except Exception as e:
            r = {"env": env, "model": "HMA", "applicable": True, "error": str(e)}
            print(f"  [HMA] ERROR: {e}")
        results.append(r)

        # REaLTabFormer
        if not args.skip_rtf:
            try:
                r = eval_realtabformer(env, args.n_parent, args.epochs)
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                r = {"env": env, "model": "REaLTabFormer", "applicable": True, "error": str(e)}
                print(f"  [RTF] ERROR: {e}")
                print(tb)
            results.append(r)

    print_summary(results)

    out_dir = ROOT / "summaries" / "evaluation_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "multitable_baseline_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_json}")


if __name__ == "__main__":
    main()
