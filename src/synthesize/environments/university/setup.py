"""
setup.py — create a clean university.db with schema + seed data.

Run via:
    python -m synthesize.environments.university.setup
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "db" / "university.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"

from synthesize.environments.university.db.reference_data import COURSES, STUDENTS  # noqa: E402


def setup(db_path: Path = DB_PATH) -> None:
    print("=== University Setup ===")
    print(f"DB: {db_path}")

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        print("\n[1/3] Creating schema...")
        conn.executescript(SCHEMA_PATH.read_text())
        print("      ✓ Done")

        print("[2/3] Inserting students...")
        conn.executemany(
            """INSERT INTO student (student_id, name, email, academic_program, enrollment_status, gpa, credits_completed)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            STUDENTS,
        )
        conn.commit()
        print("      ✓ Done")

        print("[3/3] Inserting courses...")
        conn.executemany(
            """INSERT INTO course (course_id, course_code, title, instructor, department, capacity, current_enrollment, credits, is_open)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            COURSES,
        )
        conn.commit()
        print("      ✓ Done")

        stu_count = conn.execute("SELECT COUNT(*) FROM student").fetchone()[0]
        crs_count = conn.execute("SELECT COUNT(*) FROM course").fetchone()[0]
        full_crs = conn.execute(
            "SELECT COUNT(*) FROM course WHERE current_enrollment >= capacity"
        ).fetchone()[0]
    finally:
        conn.close()

    print(f"\n  Students: {stu_count}")
    print(f"  Courses:  {crs_count} ({full_crs} full)")
    print(f"\n=== Clean DB ready: {db_path} ===\n")


if __name__ == "__main__":
    setup()
