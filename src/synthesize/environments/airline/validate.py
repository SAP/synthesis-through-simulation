"""
Validation script: checks all business rules against the Airline DB.

Run directly:
    python -m synthesize.environments.airline.validate
    python -m synthesize.environments.airline.validate --db path/to/airline.db
    python -m synthesize.environments.airline.validate --json
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent / "db" / "airline.db"
DB_PATH = _DEFAULT_DB


def set_db(path: Path) -> None:
    """Point the validator at a different DB file."""
    global DB_PATH
    DB_PATH = Path(path)


def conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def rows(sql: str, params: tuple = ()) -> list:
    c = conn()
    result = c.execute(sql, params).fetchall()
    c.close()
    return [dict(r) for r in result]


def scalar(sql: str, params: tuple = ()) -> int:
    c = conn()
    result = c.execute(sql, params).fetchone()[0]
    c.close()
    return result


# ── Check registry ────────────────────────────────────────────────────────────

CHECKS = []


def check(category: str, rule: str):
    def decorator(fn):
        CHECKS.append({"category": category, "rule": rule, "fn": fn})
        return fn

    return decorator


# ── Reservation checks ────────────────────────────────────────────────────────


@check("Reservations", "Status must be NULL (active) or 'cancelled'")
def check_reservation_status():
    return rows(
        "SELECT reservation_id, status FROM reservations "
        "WHERE status IS NOT NULL AND status != 'cancelled'"
    )


@check("Reservations", "cabin must be business/economy/basic_economy")
def check_reservation_cabin():
    return rows(
        "SELECT reservation_id, cabin FROM reservations "
        "WHERE cabin NOT IN ('business', 'economy', 'basic_economy')"
    )


@check("Reservations", "flight_type must be one_way or round_trip")
def check_reservation_flight_type():
    return rows(
        "SELECT reservation_id, flight_type FROM reservations "
        "WHERE flight_type NOT IN ('one_way', 'round_trip')"
    )


@check("Reservations", "insurance must be yes or no")
def check_reservation_insurance():
    return rows(
        "SELECT reservation_id, insurance FROM reservations WHERE insurance NOT IN ('yes', 'no')"
    )


@check("Reservations", "nonfree_baggages must be <= total_baggages")
def check_baggage_counts():
    return rows(
        "SELECT reservation_id, total_baggages, nonfree_baggages FROM reservations "
        "WHERE nonfree_baggages > total_baggages"
    )


@check("Reservations", "No reservation has more than 5 passengers")
def check_max_passengers():
    return rows(
        """
        SELECT reservation_id, COUNT(*) AS passenger_count
        FROM reservation_passengers
        GROUP BY reservation_id
        HAVING COUNT(*) > 5
        """
    )


@check("Reservations", "All user_id references point to known users")
def check_user_fk():
    return rows(
        """
        SELECT r.reservation_id, r.user_id
        FROM reservations r
        LEFT JOIN users u ON r.user_id = u.user_id
        WHERE u.user_id IS NULL
        """
    )


# ── Payment checks ────────────────────────────────────────────────────────────


@check("Payments", "Active reservations have positive net payment")
def check_active_reservation_payments():
    return rows(
        """
        SELECT r.reservation_id,
               COALESCE(SUM(ph.amount), 0) AS net_payment
        FROM reservations r
        LEFT JOIN payment_history ph ON r.reservation_id = ph.reservation_id
        WHERE r.status IS NULL
        GROUP BY r.reservation_id
        HAVING COALESCE(SUM(ph.amount), 0) <= 0
        """
    )


@check("Payments", "Cancelled reservations have at least one refund entry (negative amount)")
def check_cancelled_have_refunds():
    return rows(
        """
        SELECT r.reservation_id
        FROM reservations r
        WHERE r.status = 'cancelled'
          AND NOT EXISTS (
              SELECT 1 FROM payment_history ph
              WHERE ph.reservation_id = r.reservation_id AND ph.amount < 0
          )
        """
    )


@check(
    "Payments",
    "All payment_id references in payment_history point to known payment methods or belong to the reservation's user",
)
def check_payment_method_fk():
    # payment methods can be deleted (certificates consumed); we just check
    # that payment_history entries with positive amounts reference a method
    # that either still exists or was a certificate (already consumed).
    # This is a best-effort check: flag history entries whose payment_id
    # starts with 'certificate_' yet has no matching row AND the amount > 0.
    return rows(
        """
        SELECT ph.id, ph.reservation_id, ph.payment_id, ph.amount
        FROM payment_history ph
        LEFT JOIN payment_methods pm ON ph.payment_id = pm.payment_method_id
        WHERE pm.payment_method_id IS NULL
          AND ph.payment_id NOT LIKE 'certificate_%'
          AND ph.amount > 0
        """
    )


# ── Flight checks ─────────────────────────────────────────────────────────────


@check("Flights", "All flight_number references in reservation_flights point to known flights")
def check_flight_fk():
    return rows(
        """
        SELECT rf.id, rf.reservation_id, rf.flight_number
        FROM reservation_flights rf
        LEFT JOIN flights f ON rf.flight_number = f.flight_number
        WHERE f.flight_number IS NULL
        """
    )


@check("Flights", "flight_dates status must be a valid value")
def check_flight_date_status():
    return rows(
        "SELECT flight_number, date, status FROM flight_dates "
        "WHERE status NOT IN ('available', 'on time', 'flying', 'landed', 'cancelled', 'delayed')"
    )


@check("Flights", "flight_dates seat counts must be non-negative")
def check_flight_date_seats():
    return rows(
        "SELECT flight_number, date, seats_business, seats_economy, seats_basic_economy "
        "FROM flight_dates "
        "WHERE seats_business < 0 OR seats_economy < 0 OR seats_basic_economy < 0"
    )


# ── Runner ────────────────────────────────────────────────────────────────────


def run(as_json: bool = False, show_sample: int = 3) -> list:
    results = []
    for chk in CHECKS:
        violations = chk["fn"]()
        status = "PASS" if not violations else "FAIL"
        results.append(
            {
                "category": chk["category"],
                "rule": chk["rule"],
                "status": status,
                "violation_count": len(violations),
                "sample": violations[:show_sample] if show_sample else [],
            }
        )
        if not as_json:
            mark = "\033[32m✓\033[0m" if status == "PASS" else "\033[31m✗\033[0m"
            print(f"  {mark}  [{chk['category']}] {chk['rule']}")
            if violations and show_sample:
                for v in violations[:show_sample]:
                    print(f"       ↳ {v}")

    if not as_json:
        total = len(results)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = total - passed
        print("\n" + "─" * 60)
        print(f"  Checks:  {total}")
        print(f"  Passed:  \033[32m✓\033[0m {passed}")
        print(f"  Failed:    {failed}")
        if failed:
            print("\n  Failing checks:")
            for r in results:
                if r["status"] == "FAIL":
                    print(
                        f"    \033[31m✗\033[0m  [{r['category']}] {r['rule']}  ({r['violation_count']} violations)"
                    )
        print("─" * 60)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Airline DB business rules")
    parser.add_argument("--db", type=Path, default=None, help="Path to DB file")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    args = parser.parse_args()

    if args.db:
        set_db(args.db)

    results = run(as_json=args.json, show_sample=3)

    if args.json:
        print(json.dumps(results, indent=2))

    failed = sum(1 for r in results if r["status"] == "FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
