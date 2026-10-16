"""
Validation script: checks all business rules against the IT Management DB.

Each check function returns a list of violation dicts.
Run directly:
    python -m synthesize.environments.it_management.validate
    python -m synthesize.environments.it_management.validate --db path/to/it_management.db
    python -m synthesize.environments.it_management.validate --json
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent / "db" / "it_management.db"
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


# ── Checks ────────────────────────────────────────────────────────────────────


@check("IT Tickets", "Priority must be low/medium/high")
def check_priority():
    return rows(
        "SELECT ticket_id, priority FROM it_ticket WHERE priority NOT IN ('low', 'medium', 'high')"
    )


@check("IT Tickets", "Status must be open/assigned/resolved/closed")
def check_status():
    return rows(
        "SELECT ticket_id, status FROM it_ticket WHERE status NOT IN ('open', 'assigned', 'resolved', 'closed')"
    )


@check("IT Tickets", "Open tickets have no assignee")
def check_open_no_assignee():
    return rows(
        "SELECT ticket_id, status, assigned_emp_id FROM it_ticket "
        "WHERE status = 'open' AND assigned_emp_id IS NOT NULL"
    )


@check("IT Tickets", "Assigned/resolved/closed tickets have an assignee")
def check_non_open_has_assignee():
    return rows(
        "SELECT ticket_id, status FROM it_ticket "
        "WHERE status IN ('assigned', 'resolved', 'closed') AND assigned_emp_id IS NULL"
    )


@check("IT Tickets", "Resolved/closed tickets have non-empty resolution")
def check_resolved_has_resolution():
    return rows(
        "SELECT ticket_id, status, resolution FROM it_ticket "
        "WHERE status IN ('resolved', 'closed') AND (resolution IS NULL OR TRIM(resolution) = '')"
    )


@check("IT Tickets", "No self-assignment (raised_by_emp_id ≠ assigned_emp_id)")
def check_no_self_assignment():
    return rows(
        "SELECT ticket_id, raised_by_emp_id, assigned_emp_id FROM it_ticket "
        "WHERE assigned_emp_id IS NOT NULL AND raised_by_emp_id = assigned_emp_id"
    )


@check("IT Tickets", "All assignees are IT-category employees")
def check_assignee_is_it_staff():
    return rows(
        """SELECT t.ticket_id, t.assigned_emp_id, e.category
           FROM it_ticket t
           JOIN employee e ON t.assigned_emp_id = e.emp_id
           WHERE t.assigned_emp_id IS NOT NULL AND e.category != 'IT'"""
    )


@check("IT Tickets", "assigned_date >= created_date where both present")
def check_assigned_date_order():
    return rows(
        "SELECT ticket_id, created_date, assigned_date FROM it_ticket "
        "WHERE assigned_date IS NOT NULL AND created_date IS NOT NULL AND assigned_date < created_date"
    )


@check("IT Tickets", "Resolved tickets have resolved_date")
def check_resolved_has_date():
    return rows(
        "SELECT ticket_id, status, resolved_date FROM it_ticket "
        "WHERE status IN ('resolved', 'closed') AND resolved_date IS NULL"
    )


@check("IT Tickets", "All employee references point to known active employees")
def check_employee_refs():
    violations = []
    violations += rows(
        """SELECT t.ticket_id, 'raised_by_emp_id' AS field, t.raised_by_emp_id AS emp_id
           FROM it_ticket t
           LEFT JOIN employee e ON t.raised_by_emp_id = e.emp_id
           WHERE e.emp_id IS NULL OR e.is_active = 0"""
    )
    violations += rows(
        """SELECT t.ticket_id, 'assigned_emp_id' AS field, t.assigned_emp_id AS emp_id
           FROM it_ticket t
           LEFT JOIN employee e ON t.assigned_emp_id = e.emp_id
           WHERE t.assigned_emp_id IS NOT NULL AND (e.emp_id IS NULL OR e.is_active = 0)"""
    )
    return violations


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
    parser = argparse.ArgumentParser(description="Validate IT Management DB business rules")
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
