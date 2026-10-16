"""
setup.py — create a clean obfuscated_airline.db with schema + seed data.

Run via:
    python -m synthesize.environments.obfuscated_airline.setup
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "db" / "obfuscated_airline.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"

from synthesize.environments.obfuscated_airline.db.reference_data import (  # noqa: E402
    OBJECT_B_PROPERTY_LS,
    OBJECT_BS,
    OBJECT_CS,
    OBJECT_ES,
    OBJECT_FS,
    SAVED_OBJECT_DS,
)


def setup(db_path: Path = DB_PATH) -> None:
    print("=== Generic Setup ===")
    print(f"DB: {db_path}")

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        print("\n[1/7] Creating schema...")
        conn.executescript(SCHEMA_PATH.read_text())
        print("      ✓ Done")

        print("[2/7] Inserting object_fs...")
        conn.executemany(
            """INSERT INTO object_fs
               (property_id, property_n, property_o, property_p, property_m, property_q,
                property_r, property_s, property_t, property_u, property_v, property_w)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            OBJECT_FS,
        )
        print(f"      ✓ {len(OBJECT_FS)} object_fs")

        print("[3/7] Inserting object_es...")
        conn.executemany(
            """INSERT INTO object_es
               (object_e_id, property_id, property_i, property_j, property_k, amount)
               VALUES (?, ?, ?, ?, ?, ?)""",
            OBJECT_ES,
        )
        print(f"      ✓ {len(OBJECT_ES)} object_es")

        print("[4/7] Inserting saved object_ds...")
        conn.executemany(
            """INSERT INTO saved_object_ds (property_id, property_n, property_o, property_m)
               VALUES (?, ?, ?, ?)""",
            SAVED_OBJECT_DS,
        )
        print(f"      ✓ {len(SAVED_OBJECT_DS)} saved object_ds")

        print("[5/7] Inserting object_bs...")
        conn.executemany(
            """INSERT INTO object_bs
               (object_b_number, object_a_property_1, object_a_property_2,
                scheduled_property_c, scheduled_property_d)
               VALUES (?, ?, ?, ?, ?)""",
            OBJECT_BS,
        )
        print(f"      ✓ {len(OBJECT_BS)} object_bs")

        print("[6/7] Inserting object_b property_ls...")
        conn.executemany(
            """INSERT INTO object_b_property_ls
               (object_b_number, property_l, status,
                property_a_type_b, property_a_type_a, property_a_type_c,
                property_b_type_b, property_b_type_a, property_b_type_c)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            OBJECT_B_PROPERTY_LS,
        )
        print(f"      ✓ {len(OBJECT_B_PROPERTY_LS)} object_b property_l records")

        print("[7/7] Inserting seed object_cs...")
        for res in OBJECT_CS:
            conn.execute(
                """INSERT INTO object_cs
                   (object_c_id, property_id, object_a_property_1, object_a_property_2, object_b_type,
                    property_e, property_f, property_h, property_g, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    res["object_c_id"],
                    res["property_id"],
                    res["object_a_property_1"],
                    res["object_a_property_2"],
                    res["object_b_type"],
                    res["property_e"],
                    res["property_f"],
                    res["property_h"],
                    res["property_g"],
                    res["status"],
                ),
            )
            for f in res["object_bs"]:
                conn.execute(
                    """INSERT INTO object_c_object_bs
                       (object_c_id, object_b_number, object_a_property_1, object_a_property_2, property_l, property_b)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        res["object_c_id"],
                        f["object_b_number"],
                        f["object_a_property_1"],
                        f["object_a_property_2"],
                        f["property_l"],
                        f["property_b"],
                    ),
                )
            for p in res["object_ds"]:
                conn.execute(
                    """INSERT INTO object_c_object_ds
                       (object_c_id, property_n, property_o, property_m)
                       VALUES (?, ?, ?, ?)""",
                    (res["object_c_id"], p["property_n"], p["property_o"], p["property_m"]),
                )
            for pm in res["object_c_object_es"]:
                conn.execute(
                    """INSERT INTO object_c_object_es (object_c_id, object_e_id, amount)
                       VALUES (?, ?, ?)""",
                    (res["object_c_id"], pm["object_e_id"], pm["amount"]),
                )

        conn.commit()

        active = conn.execute("SELECT COUNT(*) FROM object_cs WHERE status IS NULL").fetchone()[
            0
        ]
        status_a_count = conn.execute(
            "SELECT COUNT(*) FROM object_cs WHERE status = 'status_a'"
        ).fetchone()[0]
        print(f"      ✓ {len(OBJECT_CS)} object_cs ({active} active, {status_a_count} status_a)")

    finally:
        conn.close()

    print(f"\n=== Clean DB ready: {db_path} ===\n")


if __name__ == "__main__":
    setup()
