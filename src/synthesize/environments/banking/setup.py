"""
setup.py — create a clean banking.db with schema + seed data.

Run via:
    python -m synthesize.environments.banking.setup
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "db" / "banking.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"

from synthesize.environments.banking.db.reference_data import ACCOUNTS, CUSTOMERS  # noqa: E402


def setup(db_path: Path = DB_PATH) -> None:
    print("=== Banking Setup ===")
    print(f"DB: {db_path}")

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        print("\n[1/3] Creating schema...")
        conn.executescript(SCHEMA_PATH.read_text())
        print("      ✓ Done")

        print("[2/3] Inserting customers...")
        conn.executemany(
            """INSERT INTO customer (customer_id, name, email, phone, address, id_type, id_number, is_active, created_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, '2020-01-01')""",
            CUSTOMERS,
        )
        conn.commit()
        print("      ✓ Done")

        print("[3/3] Inserting accounts...")
        conn.executemany(
            """INSERT INTO account (account_id, customer_id, account_type, balance, currency, status, overdraft_allowed, opening_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ACCOUNTS,
        )
        conn.commit()
        print("      ✓ Done")

        cust_count = conn.execute("SELECT COUNT(*) FROM customer").fetchone()[0]
        acc_count = conn.execute("SELECT COUNT(*) FROM account").fetchone()[0]
    finally:
        conn.close()

    print(f"\n  Customers: {cust_count}")
    print(f"  Accounts:  {acc_count}")
    print(f"\n=== Clean DB ready: {db_path} ===\n")


if __name__ == "__main__":
    setup()
