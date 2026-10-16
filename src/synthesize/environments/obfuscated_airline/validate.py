"""
Validation script: checks all business rules against the Generic DB.

Run directly:
    python -m synthesize.environments.obfuscated_airline.validate
    python -m synthesize.environments.obfuscated_airline.validate --db path/to/obfuscated_airline.db
    python -m synthesize.environments.obfuscated_airline.validate --json
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent / "db" / "obfuscated_airline.db"
DB_PATH = _DEFAULT_DB


def set_db(path: Path) -> None:
    """Point the validator at a different DB file."""
    global DB_PATH
    DB_PATH = Path(path)


def conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def rows(sql: str, params: tuple = ()) -> list:
    c = conn()
    result = c.execute(sql, params).fetchall()
    c.close()
    return [dict(r) for r in result]


def scalar(sql: str, params: tuple = ()) -> int:
    c = conn()
    result = c.execute(sql, params).fetchone()[0]
    c.close()
    return result


# ── Check registry ────────────────────────────────────────────────────────────

CHECKS = []


def check(category: str, rule: str):
    def decorator(fn):
        CHECKS.append({"category": category, "rule": rule, "fn": fn})
        return fn

    return decorator


# ── ObjectC checks ────────────────────────────────────────────────────────


@check("ObjectCs", "Status must be NULL (active) or 'status_a'")
def check_object_c_status():
    return rows(
        "SELECT object_c_id, status FROM object_cs "
        "WHERE status IS NOT NULL AND status != 'status_a'"
    )


@check("ObjectCs", "property_e must be type_b/type_a/type_c")
def check_object_c_property_e():
    return rows(
        "SELECT object_c_id, property_e FROM object_cs "
        "WHERE property_e NOT IN ('type_b', 'type_a', 'type_c')"
    )


@check("ObjectCs", "object_b_type must be option_a or option_b")
def check_object_c_object_b_type():
    return rows(
        "SELECT object_c_id, object_b_type FROM object_cs "
        "WHERE object_b_type NOT IN ('option_a', 'option_b')"
    )


@check("ObjectCs", "property_g must be yes or no")
def check_object_c_property_g():
    return rows(
        "SELECT object_c_id, property_g FROM object_cs WHERE property_g NOT IN ('yes', 'no')"
    )


@check("ObjectCs", "property_h must be <= property_f")
def check_object_c_property_h():
    return rows(
        "SELECT object_c_id, property_f, property_h FROM object_cs "
        "WHERE property_h > property_f"
    )


@check("ObjectCs", "No object_c has more than 5 object_ds")
def check_max_object_ds():
    return rows(
        """
        SELECT object_c_id, COUNT(*) AS object_d_count
        FROM object_c_object_ds
        GROUP BY object_c_id
        HAVING COUNT(*) > 5
        """
    )


@check("ObjectCs", "All property_id references point to known object_fs")
def check_object_f_fk():
    return rows(
        """
        SELECT r.object_c_id, r.property_id
        FROM object_cs r
        LEFT JOIN object_fs u ON r.property_id = u.property_id
        WHERE u.property_id IS NULL
        """
    )


# ── Payment checks ────────────────────────────────────────────────────────────


@check("ObjectEs", "Active object_cs have positive net value")
def check_active_object_c_object_es():
    return rows(
        """
        SELECT r.object_c_id,
               COALESCE(SUM(ch.amount), 0) AS net_value
        FROM object_cs r
        LEFT JOIN object_c_object_es ch ON r.object_c_id = ch.object_c_id
        WHERE r.status IS NULL
        GROUP BY r.object_c_id
        HAVING COALESCE(SUM(ch.amount), 0) <= 0
        """
    )


@check("ObjectEs", "Status_a object_cs have at least one negative value entry")
def check_status_a_have_negative_values():
    return rows(
        """
        SELECT r.object_c_id
        FROM object_cs r
        WHERE r.status = 'status_a'
          AND NOT EXISTS (
              SELECT 1 FROM object_c_object_es ch
              WHERE ch.object_c_id = r.object_c_id AND ch.amount < 0
          )
        """
    )


@check(
    "ObjectEs",
    "All object_e_id references in object_c_object_es point to known object_es or belong to the object_c's object_f",
)
def check_object_e_fk():
    # object_es can be deleted (i_c methods consumed); we just check
    # that object_c_object_es entries with positive amounts reference an object_e
    # that either still exists or was an i_c (already consumed).
    # This is a best-effort check: flag entries whose object_e_id
    # starts with 'i_c_' yet has no matching row AND the amount > 0.
    return rows(
        """
        SELECT ch.id, ch.object_c_id, ch.object_e_id, ch.amount
        FROM object_c_object_es ch
        LEFT JOIN object_es oe ON ch.object_e_id = oe.object_e_id
        WHERE oe.object_e_id IS NULL
          AND ch.object_e_id NOT LIKE 'i_c_%'
          AND ch.amount > 0
        """
    )


# ── ObjectB checks ─────────────────────────────────────────────────────────────


@check("ObjectBs", "All object_b_number references in object_c_object_bs point to known object_bs")
def check_object_b_fk():
    return rows(
        """
        SELECT rf.id, rf.object_c_id, rf.object_b_number
        FROM object_c_object_bs rf
        LEFT JOIN object_bs f ON rf.object_b_number = f.object_b_number
        WHERE f.object_b_number IS NULL
        """
    )


@check("ObjectBs", "object_b_dates status must be a valid value")
def check_object_b_date_status():
    return rows(
        "SELECT object_b_number, property_l, status FROM object_b_property_ls "
        "WHERE status NOT IN ('status_a', 'status_b', 'status_c', 'status_d', 'status_e', 'status_f')"
    )


@check("ObjectBs", "property_a_type values must be non-negative")
def check_object_b_date_property_a():
    return rows(
        "SELECT object_b_number, property_l, property_a_type_b, property_a_type_a, property_a_type_c "
        "FROM object_b_property_ls "
        "WHERE property_a_type_b < 0 OR property_a_type_a < 0 OR property_a_type_c < 0"
    )


# ── Runner ────────────────────────────────────────────────────────────────────


def run(as_json: bool = False, show_sample: int = 3) -> list:
    results = []
    for chk in CHECKS:
        violations = chk["fn"]()
        status = "PASS" if not violations else "FAIL"
        results.append(
            {
                "category": chk["category"],
                "rule": chk["rule"],
                "status": status,
                "violation_count": len(violations),
                "sample": violations[:show_sample] if show_sample else [],
            }
        )
        if not as_json:
            mark = "\033[32m✓\033[0m" if status == "PASS" else "\033[31m✗\033[0m"
            print(f"  {mark}  [{chk['category']}] {chk['rule']}")
            if violations and show_sample:
                for v in violations[:show_sample]:
                    print(f"       ↳ {v}")

    if not as_json:
        total = len(results)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = total - passed
        print("\n" + "─" * 60)
        print(f"  Checks:  {total}")
        print(f"  Passed:  \033[32m✓\033[0m {passed}")
        print(f"  Failed:    {failed}")
        if failed:
            print("\n  Failing checks:")
            for r in results:
                if r["status"] == "FAIL":
                    print(
                        f"    \033[31m✗\033[0m  [{r['category']}] {r['rule']}  ({r['violation_count']} violations)"
                    )
        print("─" * 60)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Generic DB business rules")
    parser.add_argument("--db", type=Path, default=None, help="Path to DB file")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    args = parser.parse_args()

    if args.db:
        set_db(args.db)

    results = run(as_json=args.json, show_sample=3)

    if args.json:
        print(json.dumps(results, indent=2))

    failed = sum(1 for r in results if r["status"] == "FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
