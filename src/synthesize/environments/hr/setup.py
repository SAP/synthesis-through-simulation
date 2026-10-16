"""
setup.py — create a clean hr_barebone.db with schema + reference data only.

Run:
    python setup.py

No faker, no random employee generation. Inserts only the static master data
defined in db/reference_data.py, then reports row counts per reference table.
"""

import sqlite3
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
DB_PATH = ROOT / "db" / "hr_barebone.db"
SCHEMA_PATH = ROOT / "db" / "schema_hr_sqlite.sql"

# ── Reference data ────────────────────────────────────────────────────────────

from synthesize.environments.hr.db.reference_data import (  # noqa: E402
    BENEFIT_PLANS,
    BUSINESS_UNITS,
    CAREER_PATHS,
    COMPANIES,
    COMPETENCIES,
    COST_CENTERS,
    COUNTRIES,
    CURRENCIES,
    DEPARTMENTS,
    DIVISIONS,
    EVENT_REASONS,
    JOB_CODES,
    LEARNING_COURSES,
    LOCATIONS,
    ONBOARDING_PROGRAMS,
    PAY_COMPONENTS,
    PAY_GRADES,
    REVIEW_TEMPLATES,
    ROLES,
    SKILLS,
    TALENT_POOLS,
    TIME_OFF_TYPES,
)


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())


def _insert_reference_data(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")

    # fod_company
    conn.executemany(
        "INSERT INTO fod_company (company_code, company_name, country) VALUES (?,?,?)",
        [(r["code"], r["name"], r["country"]) for r in COMPANIES],
    )
    # fod_location
    conn.executemany(
        "INSERT INTO fod_location (location_code, location_name, city, state, country) VALUES (?,?,?,?,?)",
        [(r["code"], r["name"], r["city"], r["state"], r["country"]) for r in LOCATIONS],
    )
    # fod_division
    conn.executemany(
        "INSERT INTO fod_division (division_code, division_name) VALUES (?,?)",
        [(r["code"], r["name"]) for r in DIVISIONS],
    )
    # fod_department
    conn.executemany(
        "INSERT INTO fod_department (department_code, department_name, division_code) VALUES (?,?,?)",
        [(r["code"], r["name"], r["division"]) for r in DEPARTMENTS],
    )
    # fod_business_unit
    conn.executemany(
        "INSERT INTO fod_business_unit (bu_code, bu_name) VALUES (?,?)",
        [(r["code"], r["name"]) for r in BUSINESS_UNITS],
    )
    # fod_cost_center
    conn.executemany(
        "INSERT INTO fod_cost_center (cost_center_code, cost_center_name) VALUES (?,?)",
        [(r["code"], r["name"]) for r in COST_CENTERS],
    )
    # fod_job_code
    conn.executemany(
        "INSERT INTO fod_job_code (job_code, job_title, job_level, job_family) VALUES (?,?,?,?)",
        [(r["code"], r["title"], r["level"], r["family"]) for r in JOB_CODES],
    )
    # fod_pay_grade
    conn.executemany(
        "INSERT INTO fod_pay_grade (pay_grade_code, pay_grade_name, min_salary, max_salary) VALUES (?,?,?,?)",
        [(r["code"], r["name"], r["min_salary"], r["max_salary"]) for r in PAY_GRADES],
    )
    # fod_pay_component
    conn.executemany(
        "INSERT INTO fod_pay_component (pay_component_code, pay_component_name, component_type) VALUES (?,?,?)",
        [(r["code"], r["name"], r["type"]) for r in PAY_COMPONENTS],
    )
    # fod_event_reason
    conn.executemany(
        "INSERT INTO fod_event_reason (event_reason_code, event_reason_name, event_type) VALUES (?,?,?)",
        [(r["code"], r["name"], r["event_type"]) for r in EVENT_REASONS],
    )
    # fod_competency
    conn.executemany(
        "INSERT INTO fod_competency (competency_id, competency_name, competency_category) VALUES (?,?,?)",
        [(r["code"], r["name"], r["category"]) for r in COMPETENCIES],
    )
    # fod_country
    conn.executemany(
        "INSERT INTO fod_country (country_code, country_name) VALUES (?,?)",
        [(r["code"], r["name"]) for r in COUNTRIES],
    )
    # fod_currency
    conn.executemany(
        "INSERT INTO fod_currency (currency_code, currency_name) VALUES (?,?)",
        [(r["code"], r["name"]) for r in CURRENCIES],
    )
    # tm_time_off_type
    conn.executemany(
        "INSERT INTO tm_time_off_type (time_off_type_code, type_name, max_days_per_year) VALUES (?,?,?)",
        [(r["code"], r["name"], r["accrual_rate"]) for r in TIME_OFF_TYPES],
    )
    # ben_benefit_plan
    conn.executemany(
        "INSERT INTO ben_benefit_plan (plan_id, plan_name, plan_type, plan_year) VALUES (?,?,?,?)",
        [(r["code"], r["name"], r["type"], 2025) for r in BENEFIT_PLANS],
    )
    # lrn_course
    conn.executemany(
        "INSERT INTO lrn_course (course_id, course_code, course_title, duration_hours, course_type) VALUES (?,?,?,?,?)",
        [
            (r["code"], r["code"], r["name"], r["duration_hours"], r["type"])
            for r in LEARNING_COURSES
        ],
    )
    # tp_skill
    conn.executemany(
        "INSERT INTO tp_skill (skill_id, skill_name, skill_category) VALUES (?,?,?)",
        [(r["code"], r["name"], r["category"]) for r in SKILLS],
    )
    # user_role
    conn.executemany(
        "INSERT INTO user_role (role_id, role_name) VALUES (?,?)",
        [(r["code"], r["name"]) for r in ROLES],
    )
    # pm_review_template
    conn.executemany(
        "INSERT INTO pm_review_template (template_id, template_name, review_type, frequency, rating_scale) VALUES (?,?,?,?,?)",
        [
            (r["id"], r["name"], r["review_type"], r["frequency"], r["rating_scale"])
            for r in REVIEW_TEMPLATES
        ],
    )
    # suc_talent_pool
    conn.executemany(
        "INSERT INTO suc_talent_pool (talent_pool_id, pool_name, pool_type) VALUES (?,?,?)",
        [(f"TP{i:05d}", r["name"], r["type"]) for i, r in enumerate(TALENT_POOLS, 1)],
    )
    # car_career_path
    conn.executemany(
        "INSERT INTO car_career_path (path_id, path_name, from_job_code, to_job_code, typical_years) VALUES (?,?,?,?,?)",
        [
            (f"CP{i:05d}", r["name"], None, None, r["typical_years"])
            for i, r in enumerate(CAREER_PATHS, 1)
        ],
    )
    # onb_program
    conn.executemany(
        "INSERT INTO onb_program (program_id, program_name, duration_days) VALUES (?,?,?)",
        [
            (f"OBP{i:05d}", r["name"], r["duration_days"])
            for i, r in enumerate(ONBOARDING_PROGRAMS, 1)
        ],
    )

    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def _report(conn: sqlite3.Connection) -> None:
    tables = [
        "fod_company",
        "fod_location",
        "fod_division",
        "fod_department",
        "fod_business_unit",
        "fod_cost_center",
        "fod_job_code",
        "fod_pay_grade",
        "fod_pay_component",
        "fod_event_reason",
        "fod_competency",
        "fod_country",
        "fod_currency",
        "tm_time_off_type",
        "ben_benefit_plan",
        "lrn_course",
        "tp_skill",
        "user_role",
        "pm_review_template",
        "suc_talent_pool",
        "car_career_path",
        "onb_program",
    ]
    print("Reference table row counts:")
    for t in tables:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<35} {n:>3} rows")


def main() -> None:
    print("=== HR Setup ===")
    print(f"DB: {DB_PATH}")
    print()

    if not SCHEMA_PATH.exists():
        print(f"Error: schema not found at {SCHEMA_PATH}", file=sys.stderr)
        sys.exit(1)

    DB_PATH.unlink(missing_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    try:
        print("[1/2] Creating schema...")
        _create_schema(conn)
        print("      ✓ Done")

        print("[2/2] Inserting reference data...")
        _insert_reference_data(conn)
        print("      ✓ Done")
    finally:
        conn.close()

    print()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        _report(conn)
    finally:
        conn.close()

    print()
    print(f"=== Clean DB ready: {DB_PATH} ===")


if __name__ == "__main__":
    main()

# Alias for programmatic use
setup = main
