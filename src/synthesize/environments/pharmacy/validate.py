"""
Validation script: business rules for the Pharmacy DB.

Run directly:
    python -m synthesize.environments.pharmacy.validate
    python -m synthesize.environments.pharmacy.validate --db path/to/pharmacy.db
    python -m synthesize.environments.pharmacy.validate --json
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent / "db" / "pharmacy.db"
DB_PATH = _DEFAULT_DB


def set_db(path: Path) -> None:
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


CHECKS = []


def check(category: str, rule: str):
    def decorator(fn):
        CHECKS.append({"category": category, "rule": rule, "fn": fn})
        return fn

    return decorator


# ── Checks ────────────────────────────────────────────────────────────────────


@check("Prescriptions", "status must be pending/filled/on_hold/cancelled/expired")
def check_prescription_status():
    return rows(
        "SELECT prescription_id, status FROM prescription "
        "WHERE status NOT IN ('pending', 'filled', 'on_hold', 'cancelled', 'expired')"
    )


@check("Prescriptions", "Filled prescriptions have date_filled")
def check_filled_has_date():
    return rows(
        "SELECT prescription_id, status, date_filled FROM prescription "
        "WHERE status = 'filled' AND date_filled IS NULL"
    )


@check("Prescriptions", "Non-filled prescriptions have no date_filled")
def check_non_filled_no_date():
    return rows(
        "SELECT prescription_id, status, date_filled FROM prescription "
        "WHERE status != 'filled' AND date_filled IS NOT NULL"
    )


@check("Prescriptions", "All prescriptions reference active patients")
def check_patient_fk():
    return rows(
        """SELECT p.prescription_id, p.patient_id
           FROM prescription p
           LEFT JOIN patient pt ON p.patient_id = pt.patient_id
           WHERE pt.patient_id IS NULL OR pt.is_active = 0"""
    )


@check("Prescriptions", "All prescriptions reference active physicians")
def check_physician_fk():
    return rows(
        """SELECT p.prescription_id, p.physician_id
           FROM prescription p
           LEFT JOIN physician ph ON p.physician_id = ph.physician_id
           WHERE ph.physician_id IS NULL OR ph.is_active = 0"""
    )


@check("Prescriptions", "All prescriptions reference active medications")
def check_medication_fk():
    return rows(
        """SELECT p.prescription_id, p.medication_id
           FROM prescription p
           LEFT JOIN medication m ON p.medication_id = m.medication_id
           WHERE m.medication_id IS NULL OR m.is_active = 0"""
    )


@check("Prescriptions", "refills_remaining must be non-negative")
def check_refills_non_negative():
    return rows(
        "SELECT prescription_id, refills_remaining FROM prescription WHERE refills_remaining < 0"
    )


@check("Prescriptions", "dosage must be non-empty")
def check_dosage_non_empty():
    return rows(
        "SELECT prescription_id, dosage FROM prescription "
        "WHERE dosage IS NULL OR TRIM(dosage) = ''"
    )


@check("Prescriptions", "instructions must be non-empty")
def check_instructions_non_empty():
    return rows(
        "SELECT prescription_id, instructions FROM prescription "
        "WHERE instructions IS NULL OR TRIM(instructions) = ''"
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
                    print(f"    \033[31m✗\033[0m  [{r['category']}] {r['rule']}  ({r['violation_count']} violations)")
        print("─" * 60)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Pharmacy DB business rules")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.db:
        set_db(args.db)

    results = run(as_json=args.json, show_sample=3)

    if args.json:
        print(json.dumps(results, indent=2))

    sys.exit(1 if any(r["status"] == "FAIL" for r in results) else 0)


if __name__ == "__main__":
    main()
