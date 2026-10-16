"""
setup.py — create a clean airline.db with schema + seed data.

Run via:
    python -m synthesize.environments.airline.setup
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "db" / "airline.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"

from synthesize.environments.airline.db.reference_data import (  # noqa: E402
    FLIGHT_DATES,
    FLIGHTS,
    PAYMENT_METHODS,
    RESERVATIONS,
    SAVED_PASSENGERS,
    USERS,
)


def setup(db_path: Path = DB_PATH) -> None:
    print("=== Airline Setup ===")
    print(f"DB: {db_path}")

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        print("\n[1/7] Creating schema...")
        conn.executescript(SCHEMA_PATH.read_text())
        print("      ✓ Done")

        print("[2/7] Inserting users...")
        conn.executemany(
            """INSERT INTO users
               (user_id, first_name, last_name, email, dob, membership,
                address1, address2, city, state, country, zip)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            USERS,
        )
        print(f"      ✓ {len(USERS)} users")

        print("[3/7] Inserting payment methods...")
        conn.executemany(
            """INSERT INTO payment_methods
               (payment_method_id, user_id, source, brand, last_four, amount)
               VALUES (?, ?, ?, ?, ?, ?)""",
            PAYMENT_METHODS,
        )
        print(f"      ✓ {len(PAYMENT_METHODS)} payment methods")

        print("[4/7] Inserting saved passengers...")
        conn.executemany(
            """INSERT INTO saved_passengers (user_id, first_name, last_name, dob)
               VALUES (?, ?, ?, ?)""",
            SAVED_PASSENGERS,
        )
        print(f"      ✓ {len(SAVED_PASSENGERS)} saved passengers")

        print("[5/7] Inserting flights...")
        conn.executemany(
            """INSERT INTO flights
               (flight_number, origin, destination,
                scheduled_departure_time_est, scheduled_arrival_time_est)
               VALUES (?, ?, ?, ?, ?)""",
            FLIGHTS,
        )
        print(f"      ✓ {len(FLIGHTS)} flight routes")

        print("[6/7] Inserting flight dates...")
        conn.executemany(
            """INSERT INTO flight_dates
               (flight_number, date, status,
                seats_business, seats_economy, seats_basic_economy,
                price_business, price_economy, price_basic_economy)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            FLIGHT_DATES,
        )
        print(f"      ✓ {len(FLIGHT_DATES)} flight date records")

        print("[7/7] Inserting seed reservations...")
        for res in RESERVATIONS:
            conn.execute(
                """INSERT INTO reservations
                   (reservation_id, user_id, origin, destination, flight_type,
                    cabin, total_baggages, nonfree_baggages, insurance, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    res["reservation_id"],
                    res["user_id"],
                    res["origin"],
                    res["destination"],
                    res["flight_type"],
                    res["cabin"],
                    res["total_baggages"],
                    res["nonfree_baggages"],
                    res["insurance"],
                    res["status"],
                ),
            )
            for f in res["flights"]:
                conn.execute(
                    """INSERT INTO reservation_flights
                       (reservation_id, flight_number, origin, destination, date, price)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        res["reservation_id"],
                        f["flight_number"],
                        f["origin"],
                        f["destination"],
                        f["date"],
                        f["price"],
                    ),
                )
            for p in res["passengers"]:
                conn.execute(
                    """INSERT INTO reservation_passengers
                       (reservation_id, first_name, last_name, dob)
                       VALUES (?, ?, ?, ?)""",
                    (res["reservation_id"], p["first_name"], p["last_name"], p["dob"]),
                )
            for pm in res["payments"]:
                conn.execute(
                    """INSERT INTO payment_history (reservation_id, payment_id, amount)
                       VALUES (?, ?, ?)""",
                    (res["reservation_id"], pm["payment_id"], pm["amount"]),
                )

        conn.commit()

        active = conn.execute("SELECT COUNT(*) FROM reservations WHERE status IS NULL").fetchone()[
            0
        ]
        cancelled = conn.execute(
            "SELECT COUNT(*) FROM reservations WHERE status = 'cancelled'"
        ).fetchone()[0]
        print(f"      ✓ {len(RESERVATIONS)} reservations ({active} active, {cancelled} cancelled)")

    finally:
        conn.close()

    print(f"\n=== Clean DB ready: {db_path} ===\n")


if __name__ == "__main__":
    setup()
