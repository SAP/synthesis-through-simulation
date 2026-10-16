"""
setup.py — create a clean forum.db with schema + seed data.

Run via:
    python -m synthesize.environments.forum.setup
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "db" / "forum.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"

from synthesize.environments.forum.db.reference_data import CATEGORIES, TAGS, USERS  # noqa: E402


def setup(db_path: Path = DB_PATH) -> None:
    print("=== Forum Setup ===")
    print(f"DB: {db_path}")

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        print("\n[1/4] Creating schema...")
        conn.executescript(SCHEMA_PATH.read_text())
        print("      ✓ Done")

        print("[2/4] Inserting users...")
        conn.executemany(
            """INSERT INTO forum_user (user_id, username, email, joined_date, reputation, role, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            USERS,
        )
        conn.commit()
        print("      ✓ Done")

        print("[3/4] Inserting categories...")
        conn.executemany(
            """INSERT INTO category (category_id, name, description, parent_category_id, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            CATEGORIES,
        )
        conn.commit()
        print("      ✓ Done")

        print("[4/4] Inserting tags...")
        conn.executemany(
            """INSERT INTO tag (tag_id, name, description, usage_count, is_approved)
               VALUES (?, ?, ?, 0, ?)""",
            TAGS,
        )
        conn.commit()
        print("      ✓ Done")

        user_count = conn.execute("SELECT COUNT(*) FROM forum_user").fetchone()[0]
        cat_count = conn.execute("SELECT COUNT(*) FROM category").fetchone()[0]
        tag_count = conn.execute("SELECT COUNT(*) FROM tag WHERE is_approved = 1").fetchone()[0]
    finally:
        conn.close()

    print(f"\n  Users:              {user_count}")
    print(f"  Categories:         {cat_count}")
    print(f"  Approved tags:      {tag_count}")
    print(f"\n=== Clean DB ready: {db_path} ===\n")


if __name__ == "__main__":
    setup()
