"""
setup.py — create a clean retail.db with schema + seed data.

Run via:
    python -m synthesize.environments.retail.setup
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "db" / "retail.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"

from synthesize.environments.retail.db.reference_data import (  # noqa: E402
    ORDER_FULFILLMENTS,
    ORDER_ITEMS,
    ORDERS,
    PAYMENT_HISTORY,
    PAYMENT_METHODS,
    PRODUCTS,
    USERS,
    VARIANTS,
)


def setup(db_path: Path = DB_PATH) -> None:
    print("=== Retail Setup ===")
    print(f"DB: {db_path}")

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        print("\n[1/8] Creating schema...")
        conn.executescript(SCHEMA_PATH.read_text())
        print("      ✓ Done")

        print("[2/8] Inserting products...")
        conn.executemany(
            "INSERT INTO products (product_id, name) VALUES (?, ?)",
            PRODUCTS,
        )
        print("      ✓ Done")

        print("[3/8] Inserting variants...")
        conn.executemany(
            "INSERT INTO variants (item_id, product_id, options, available, price) VALUES (?, ?, ?, ?, ?)",
            VARIANTS,
        )
        print("      ✓ Done")

        print("[4/8] Inserting users...")
        conn.executemany(
            "INSERT INTO users (user_id, first_name, last_name, email, address1, address2, city, state, country, zip) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            USERS,
        )
        print("      ✓ Done")

        print("[5/8] Inserting payment methods...")
        conn.executemany(
            "INSERT INTO payment_methods (payment_method_id, user_id, source, brand, last_four, balance) VALUES (?, ?, ?, ?, ?, ?)",
            PAYMENT_METHODS,
        )
        print("      ✓ Done")

        print("[6/8] Inserting orders...")
        conn.executemany(
            """INSERT INTO orders (
                order_id, user_id, address1, address2, city, state, country, zip,
                status, cancel_reason, exchange_items, exchange_new_items,
                exchange_payment_method_id, exchange_price_difference,
                return_items, return_payment_method_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ORDERS,
        )
        print("      ✓ Done")

        print("[7/8] Inserting order items and fulfillments...")
        conn.executemany(
            "INSERT INTO order_items (order_id, product_id, item_id, name, price, options) VALUES (?, ?, ?, ?, ?, ?)",
            ORDER_ITEMS,
        )
        conn.executemany(
            "INSERT INTO order_fulfillments (order_id, tracking_ids, item_ids) VALUES (?, ?, ?)",
            ORDER_FULFILLMENTS,
        )
        print("      ✓ Done")

        print("[8/8] Inserting payment history...")
        conn.executemany(
            "INSERT INTO payment_history (order_id, transaction_type, amount, payment_method_id) VALUES (?, ?, ?, ?)",
            PAYMENT_HISTORY,
        )
        conn.commit()
        print("      ✓ Done")

        n_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        n_variants = conn.execute("SELECT COUNT(*) FROM variants").fetchone()[0]
        n_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        n_pms = conn.execute("SELECT COUNT(*) FROM payment_methods").fetchone()[0]
        n_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    finally:
        conn.close()

    print(f"\n  Products: {n_products} ({n_variants} variants)")
    print(f"  Users: {n_users} ({n_pms} payment methods)")
    print(f"  Orders: {n_orders}")
    print(f"\n=== Clean DB ready: {db_path} ===\n")


if __name__ == "__main__":
    setup()
