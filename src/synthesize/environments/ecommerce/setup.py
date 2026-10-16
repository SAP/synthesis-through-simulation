"""
setup.py — create a clean ecommerce.db with schema + seed data.

Run via:
    python -m synthesize.environments.ecommerce.setup
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "db" / "ecommerce.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"

from synthesize.environments.ecommerce.db.reference_data import CUSTOMERS, PRODUCTS  # noqa: E402


def setup(db_path: Path = DB_PATH) -> None:
    print("=== E-commerce Setup ===")
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
            """INSERT INTO customer (customer_id, name, email, phone, address, is_active, created_date)
               VALUES (?, ?, ?, ?, ?, 1, '2023-01-01')""",
            CUSTOMERS,
        )
        conn.commit()
        print("      ✓ Done")

        print("[3/3] Inserting products...")
        conn.executemany(
            """INSERT INTO product (product_id, name, category, price, stock_qty, description, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            PRODUCTS,
        )
        conn.commit()
        print("      ✓ Done")

        cust_count = conn.execute("SELECT COUNT(*) FROM customer").fetchone()[0]
        prod_count = conn.execute("SELECT COUNT(*) FROM product").fetchone()[0]
    finally:
        conn.close()

    print(f"\n  Customers: {cust_count}")
    print(f"  Products:  {prod_count}")
    print(f"\n=== Clean DB ready: {db_path} ===\n")


if __name__ == "__main__":
    setup()
