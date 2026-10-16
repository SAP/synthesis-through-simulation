"""
setup.py — create a clean pharmacy.db with schema + seed data.

Run via:
    python -m synthesize.environments.pharmacy.setup
"""

import sqlite3
from pathlib import Path

from synthesize.environments.pharmacy.db.reference_data import MEDICATIONS, PATIENTS, PHYSICIANS

ROOT = Path(__file__).parent
DB_PATH = ROOT / "db" / "pharmacy.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"


def setup(db_path: Path = DB_PATH) -> None:
    print("=== Pharmacy Setup ===")
    print(f"DB: {db_path}")

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        print("\n[1/4] Creating schema...")
        conn.executescript(SCHEMA_PATH.read_text())
        print("      ✓ Done")

        print("[2/4] Inserting patients...")
        conn.executemany(
            """INSERT INTO patient (patient_id, name, date_of_birth, email, phone, medical_history, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            PATIENTS,
        )
        conn.commit()
        print("      ✓ Done")

        print("[3/4] Inserting physicians...")
        conn.executemany(
            """INSERT INTO physician (physician_id, name, license_number, email, affiliated_clinic, specialty, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            PHYSICIANS,
        )
        conn.commit()
        print("      ✓ Done")

        print("[4/4] Inserting medications...")
        conn.executemany(
            """INSERT INTO medication (medication_id, name, form, strength, manufacturer, classification, storage_requirements, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
            MEDICATIONS,
        )
        conn.commit()
        print("      ✓ Done")

        pat_count = conn.execute("SELECT COUNT(*) FROM patient").fetchone()[0]
        phy_count = conn.execute("SELECT COUNT(*) FROM physician").fetchone()[0]
        med_count = conn.execute("SELECT COUNT(*) FROM medication").fetchone()[0]
    finally:
        conn.close()

    print(f"\n  Patients:    {pat_count}")
    print(f"  Physicians:  {phy_count}")
    print(f"  Medications: {med_count}")
    print(f"\n=== Clean DB ready: {db_path} ===\n")


if __name__ == "__main__":
    setup()
