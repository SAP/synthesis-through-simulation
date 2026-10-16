"""
Validation script: business rules for the University DB.

Run directly:
    python -m synthesize.environments.university.validate
    python -m synthesize.environments.university.validate --db path/to/university.db
    python -m synthesize.environments.university.validate --json
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent / "db" / "university.db"
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


@check("Enrollments", "enrollment status must be enrolled/dropped/completed/failed")
def check_enrollment_status():
    return rows(
        "SELECT enrollment_id, status FROM enrollment "
        "WHERE status NOT IN ('enrolled', 'dropped', 'completed', 'failed')"
    )


@check("Enrollments", "Dropped enrollments have dropped_date")
def check_dropped_has_date():
    return rows(
        "SELECT enrollment_id, status, dropped_date FROM enrollment "
        "WHERE status = 'dropped' AND dropped_date IS NULL"
    )


@check("Enrollments", "Active enrollments have no dropped_date")
def check_enrolled_no_drop_date():
    return rows(
        "SELECT enrollment_id, status, dropped_date FROM enrollment "
        "WHERE status = 'enrolled' AND dropped_date IS NOT NULL"
    )


@check("Enrollments", "Student cannot be both enrolled and waitlisted for the same course")
def check_no_enrolled_and_waitlisted():
    return rows(
        """SELECT e.student_id, e.course_id
           FROM enrollment e
           JOIN waitlist w ON e.student_id = w.student_id AND e.course_id = w.course_id
           WHERE e.status = 'enrolled'"""
    )


@check("Enrollments", "All enrollments reference known students")
def check_enrollment_student_fk():
    return rows(
        """SELECT e.enrollment_id, e.student_id
           FROM enrollment e
           LEFT JOIN student s ON e.student_id = s.student_id
           WHERE s.student_id IS NULL"""
    )


@check("Enrollments", "All enrollments reference known courses")
def check_enrollment_course_fk():
    return rows(
        """SELECT e.enrollment_id, e.course_id
           FROM enrollment e
           LEFT JOIN course c ON e.course_id = c.course_id
           WHERE c.course_id IS NULL"""
    )


@check("Courses", "current_enrollment matches active enrollment rows")
def check_enrollment_count_consistent():
    return rows(
        """SELECT c.course_id, c.current_enrollment AS stored,
                  COUNT(e.enrollment_id) AS actual
           FROM course c
           LEFT JOIN enrollment e ON c.course_id = e.course_id AND e.status = 'enrolled'
           GROUP BY c.course_id
           HAVING stored != actual"""
    )


@check("Courses", "current_enrollment cannot exceed capacity")
def check_enrollment_not_over_capacity():
    return rows(
        "SELECT course_id, capacity, current_enrollment FROM course "
        "WHERE current_enrollment > capacity"
    )


@check("Courses", "course capacity must be positive")
def check_capacity_positive():
    return rows("SELECT course_id, capacity FROM course WHERE capacity <= 0")


@check("Waitlist", "Waitlist entries only for full courses")
def check_waitlist_only_full_courses():
    return rows(
        """SELECT w.waitlist_id, w.course_id, c.capacity, c.current_enrollment
           FROM waitlist w
           JOIN course c ON w.course_id = c.course_id
           WHERE c.current_enrollment < c.capacity"""
    )


@check("Waitlist", "Waitlist positions are unique per course")
def check_waitlist_positions_unique():
    return rows(
        """SELECT course_id, position, COUNT(*) AS cnt
           FROM waitlist
           GROUP BY course_id, position
           HAVING cnt > 1"""
    )


@check("Waitlist", "All waitlist entries reference known students and courses")
def check_waitlist_fks():
    violations = []
    violations += rows(
        """SELECT w.waitlist_id, w.student_id
           FROM waitlist w
           LEFT JOIN student s ON w.student_id = s.student_id
           WHERE s.student_id IS NULL"""
    )
    violations += rows(
        """SELECT w.waitlist_id, w.course_id
           FROM waitlist w
           LEFT JOIN course c ON w.course_id = c.course_id
           WHERE c.course_id IS NULL"""
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
                    print(f"    \033[31m✗\033[0m  [{r['category']}] {r['rule']}  ({r['violation_count']} violations)")
        print("─" * 60)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate University DB business rules")
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
