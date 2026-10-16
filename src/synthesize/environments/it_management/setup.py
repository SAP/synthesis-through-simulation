"""
setup.py — create a clean it_management.db with schema + seed employees.

Run via:
    python -m synthesize.environments.it_management.setup
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "db" / "it_management.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"

from synthesize.environments.it_management.db.reference_data import EMPLOYEES  # noqa: E402


def setup(db_path: Path = DB_PATH) -> None:
    print("=== IT Management Setup ===")
    print(f"DB: {db_path}")

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        print("\n[1/2] Creating schema...")
        conn.executescript(SCHEMA_PATH.read_text())
        print("      ✓ Done")

        print("[2/2] Inserting seed employees...")
        conn.executemany(
            """INSERT INTO employee (emp_id, name, email, category, level, salary, doj, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            EMPLOYEES,
        )
        conn.commit()
        print("      ✓ Done")

        it_count = conn.execute("SELECT COUNT(*) FROM employee WHERE category = 'IT'").fetchone()[0]
        total_count = conn.execute("SELECT COUNT(*) FROM employee").fetchone()[0]
    finally:
        conn.close()

    print(f"\n  Employees seeded: {total_count} total ({it_count} IT staff)")
    print(f"\n=== Clean DB ready: {db_path} ===\n")


if __name__ == "__main__":
    setup()
