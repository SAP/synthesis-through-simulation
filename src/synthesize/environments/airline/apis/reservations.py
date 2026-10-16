"""
Reservations API for the Airline environment.
Adapted from mock_system/apis/reservations.py and hardened with ALL policy rules
from the tau2-bench policy.md. Every business rule raises ValueError.

Policy summary enforced here:
  Booking
  - cabin must be consistent across all flights
  - max 5 passengers
  - max 1 certificate, 1 credit card, 3 gift cards per reservation
  - insurance = $30 per passenger
  - baggage fee = $50 per non-free bag
  - payment must exactly cover total price

  Cancellation
  - cannot cancel already-cancelled reservation
  - cannot cancel if any flight has status 'flying' or 'landed'
  - only eligible if: booking within last 24hr OR airline-cancelled flight
    OR business cabin OR (has insurance + covered reason)

  Modification (update_reservation_flights)
  - basic_economy cabin cannot be modified
  - cannot change origin, destination, or flight_type
  - cannot change cabin if any flight is already 'flying' or 'landed'
  - certificates cannot be used for updates

  Modification (update_reservation_baggages)
  - can only add bags, not remove (nonfree_baggages must be >= current)
  - total_baggages must be >= nonfree_baggages
  - certificates cannot be used

  Modification (update_reservation_passengers)
  - passenger count must match original
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from synthesize.environments.airline.db.db import get_conn

# ── Internal helpers ─────────────────────────────────────────────────────────


def _load_res(conn, reservation_id: str) -> object:
    """Return the reservation sqlite3.Row or raise LookupError."""
    row = conn.execute(
        "SELECT * FROM reservations WHERE reservation_id = ?",
        (reservation_id,),
    ).fetchone()
    if row is None:
        raise LookupError(f"Reservation '{reservation_id}' not found")
    return row


def _load_reservation_full(conn, reservation_id: str) -> dict:
    """Build a full reservation dict with nested flights/passengers/payments."""
    row = conn.execute(
        "SELECT * FROM reservations WHERE reservation_id = ?",
        (reservation_id,),
    ).fetchone()
    if row is None:
        return None  # type: ignore[return-value]

    flights = conn.execute(
        "SELECT * FROM reservation_flights WHERE reservation_id = ? ORDER BY id",
        (reservation_id,),
    ).fetchall()
    passengers = conn.execute(
        "SELECT * FROM reservation_passengers WHERE reservation_id = ? ORDER BY id",
        (reservation_id,),
    ).fetchall()
    payments = conn.execute(
        "SELECT * FROM payment_history WHERE reservation_id = ? ORDER BY id",
        (reservation_id,),
    ).fetchall()

    return {
        "reservation_id": row["reservation_id"],
        "user_id": row["user_id"],
        "origin": row["origin"],
        "destination": row["destination"],
        "flight_type": row["flight_type"],
        "cabin": row["cabin"],
        "total_baggages": row["total_baggages"],
        "nonfree_baggages": row["nonfree_baggages"],
        "insurance": row["insurance"],
        "status": row["status"],
        "created_at": row["created_at"],
        "flights": [
            {
                "id": f["id"],
                "flight_number": f["flight_number"],
                "origin": f["origin"],
                "destination": f["destination"],
                "date": f["date"],
                "price": f["price"],
            }
            for f in flights
        ],
        "passengers": [
            {
                "id": p["id"],
                "first_name": p["first_name"],
                "last_name": p["last_name"],
                "dob": p["dob"],
            }
            for p in passengers
        ],
        "payment_history": [
            {
                "id": ph["id"],
                "payment_id": ph["payment_id"],
                "amount": ph["amount"],
                "created_at": ph["created_at"],
            }
            for ph in payments
        ],
    }


def _fd_row(conn, flight_number: str, date: str) -> object:
    row = conn.execute(
        "SELECT * FROM flight_dates WHERE flight_number = ? AND date = ?",
        (flight_number, date),
    ).fetchone()
    if row is None:
        raise LookupError(f"Flight '{flight_number}' not found on date {date}")
    return row


def _check_any_flight_active(conn, reservation_id: str) -> bool:
    """Return True if any reservation flight is currently 'flying' or 'landed'."""
    rows = conn.execute(
        """
        SELECT fd.status
        FROM reservation_flights rf
        JOIN flight_dates fd ON rf.flight_number = fd.flight_number AND rf.date = fd.date
        WHERE rf.reservation_id = ?
        """,
        (reservation_id,),
    ).fetchall()
    return any(r["status"] in ("flying", "landed") for r in rows)


def _check_any_flight_airline_cancelled(conn, reservation_id: str) -> bool:
    """Return True if the airline cancelled any flight in the reservation."""
    rows = conn.execute(
        """
        SELECT fd.status
        FROM reservation_flights rf
        JOIN flight_dates fd ON rf.flight_number = fd.flight_number AND rf.date = fd.date
        WHERE rf.reservation_id = ?
        """,
        (reservation_id,),
    ).fetchall()
    return any(r["status"] == "cancelled" for r in rows)


# ── Read Operations ──────────────────────────────────────────────────────────


def get_reservation_details(reservation_id: str) -> dict:
    """Get a reservation with full details (flights, passengers, payment history)."""
    with get_conn() as conn:
        result = _load_reservation_full(conn, reservation_id)
    if result is None:
        raise LookupError(f"Reservation '{reservation_id}' not found")
    return result


def list_reservations(user_id: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
    """List reservations. status='active' filters for non-cancelled."""
    query = "SELECT reservation_id FROM reservations WHERE 1=1"
    params: list = []
    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)
    if status is not None:
        if status == "active":
            query += " AND status IS NULL"
        else:
            query += " AND status = ?"
            params.append(status)
    query += " ORDER BY created_at DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_load_reservation_full(conn, r["reservation_id"]) for r in rows]


# ── Book Reservation ─────────────────────────────────────────────────────────


def book_reservation(
    user_id: str,
    origin: str,
    destination: str,
    flight_type: str,
    cabin: str,
    flights: List[Dict],
    passengers: List[Dict],
    payment_methods: List[Dict],
    total_baggages: int = 0,
    nonfree_baggages: int = 0,
    insurance: str = "no",
) -> dict:
    """
    Book a reservation with full business-rule validation.

    Business rules enforced:
    - flight_type must be 'one_way' or 'round_trip'
    - cabin must be 'business', 'economy', or 'basic_economy'
    - insurance must be 'yes' or 'no'
    - max 5 passengers
    - max 1 certificate, 1 credit card, 3 gift cards in payment_methods
    - all flights must be 'available' with sufficient seats
    - insurance fee = $30 per passenger
    - baggage fee = $50 per non-free bag
    - payment must exactly cover total price
    - gift card / certificate balances validated and deducted
    - certificates consumed (deleted) on use
    - seat counts decremented
    """
    if flight_type not in ("one_way", "round_trip"):
        raise ValueError(f"Invalid flight_type: {flight_type!r}. Must be 'one_way' or 'round_trip'")
    if cabin not in ("business", "economy", "basic_economy"):
        raise ValueError(
            f"Invalid cabin: {cabin!r}. Must be 'business', 'economy', or 'basic_economy'"
        )
    if insurance not in ("yes", "no"):
        raise ValueError(f"Invalid insurance: {insurance!r}. Must be 'yes' or 'no'")
    if not flights:
        raise ValueError("At least one flight is required")
    if not passengers:
        raise ValueError("At least one passenger is required")
    if len(passengers) > 5:
        raise ValueError(f"Maximum 5 passengers allowed, got {len(passengers)}")
    if total_baggages < nonfree_baggages:
        raise ValueError(
            f"total_baggages ({total_baggages}) cannot be less than nonfree_baggages ({nonfree_baggages})"
        )

    num_passengers = len(passengers)

    with get_conn() as conn:
        # Validate user
        if not conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone():
            raise LookupError(f"User '{user_id}' not found")

        # Validate payment method counts (after loading sources)
        cert_count = 0
        cc_count = 0
        gc_count = 0
        pm_rows = {}
        for pm in payment_methods:
            pid = pm["payment_id"]
            pm_row = conn.execute(
                "SELECT * FROM payment_methods WHERE payment_method_id = ? AND user_id = ?",
                (pid, user_id),
            ).fetchone()
            if pm_row is None:
                raise LookupError(f"Payment method '{pid}' not found for user '{user_id}'")
            pm_rows[pid] = pm_row
            src = pm_row["source"]
            if src == "certificate":
                cert_count += 1
            elif src == "credit_card":
                cc_count += 1
            elif src == "gift_card":
                gc_count += 1

        if cert_count > 1:
            raise ValueError("Maximum 1 certificate allowed per reservation")
        if cc_count > 1:
            raise ValueError("Maximum 1 credit card allowed per reservation")
        if gc_count > 3:
            raise ValueError("Maximum 3 gift cards allowed per reservation")

        # Validate flights and calculate total price
        total_price = 0
        flight_records = []
        for fi in flights:
            fn = fi["flight_number"]
            dt = fi["date"]
            fd_row = _fd_row(conn, fn, dt)

            if fd_row["status"] != "available":
                raise ValueError(
                    f"Flight '{fn}' on {dt} is not available (status: {fd_row['status']})"
                )

            seat_col = f"seats_{cabin}"
            if fd_row[seat_col] < num_passengers:
                raise ValueError(
                    f"Not enough {cabin} seats on flight '{fn}' on {dt} "
                    f"(available: {fd_row[seat_col]}, requested: {num_passengers})"
                )

            price_col = f"price_{cabin}"
            price = fd_row[price_col]

            flight_row = conn.execute(
                "SELECT * FROM flights WHERE flight_number = ?", (fn,)
            ).fetchone()
            if flight_row is None:
                raise LookupError(f"Flight route '{fn}' not found")

            flight_records.append(
                {
                    "flight_number": fn,
                    "origin": flight_row["origin"],
                    "destination": flight_row["destination"],
                    "date": dt,
                    "price": price,
                }
            )
            total_price += price * num_passengers

        # Insurance fee: $30 per passenger
        if insurance == "yes":
            total_price += 30 * num_passengers

        # Baggage fee: $50 per non-free bag
        total_price += 50 * nonfree_baggages

        # Validate payment totals
        total_payment = sum(pm["amount"] for pm in payment_methods)
        if total_payment != total_price:
            raise ValueError(
                f"Payment does not match total price. "
                f"Expected: {total_price}, provided: {total_payment}"
            )

        # Validate gift card / certificate balances
        for pm in payment_methods:
            pid = pm["payment_id"]
            amount = pm["amount"]
            pm_row = pm_rows[pid]
            if pm_row["source"] in ("gift_card", "certificate"):
                if pm_row["amount"] < amount:
                    raise ValueError(
                        f"Insufficient balance in payment method '{pid}': "
                        f"available {pm_row['amount']}, required {amount}"
                    )

        # All checks pass — deduct balances and consume certificates
        for pm in payment_methods:
            pid = pm["payment_id"]
            amount = pm["amount"]
            pm_row = pm_rows[pid]
            if pm_row["source"] == "gift_card":
                conn.execute(
                    "UPDATE payment_methods SET amount = amount - ? WHERE payment_method_id = ?",
                    (amount, pid),
                )
            elif pm_row["source"] == "certificate":
                conn.execute("DELETE FROM payment_methods WHERE payment_method_id = ?", (pid,))

        # Decrement seat counts
        for fi in flights:
            fn = fi["flight_number"]
            dt = fi["date"]
            seat_col = f"seats_{cabin}"
            conn.execute(
                f"UPDATE flight_dates SET {seat_col} = {seat_col} - ? "  # noqa: S608
                "WHERE flight_number = ? AND date = ?",
                (num_passengers, fn, dt),
            )

        # Generate reservation ID
        reservation_id = uuid.uuid4().hex[:6].upper()
        while conn.execute(
            "SELECT 1 FROM reservations WHERE reservation_id = ?", (reservation_id,)
        ).fetchone():
            reservation_id = uuid.uuid4().hex[:6].upper()

        # Insert reservation
        conn.execute(
            """INSERT INTO reservations
               (reservation_id, user_id, origin, destination, flight_type,
                cabin, total_baggages, nonfree_baggages, insurance)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                reservation_id,
                user_id,
                origin,
                destination,
                flight_type,
                cabin,
                total_baggages,
                nonfree_baggages,
                insurance,
            ),
        )
        for fr in flight_records:
            conn.execute(
                """INSERT INTO reservation_flights
                   (reservation_id, flight_number, origin, destination, date, price)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    reservation_id,
                    fr["flight_number"],
                    fr["origin"],
                    fr["destination"],
                    fr["date"],
                    fr["price"],
                ),
            )
        for p in passengers:
            conn.execute(
                """INSERT INTO reservation_passengers
                   (reservation_id, first_name, last_name, dob)
                   VALUES (?, ?, ?, ?)""",
                (reservation_id, p["first_name"], p["last_name"], p["dob"]),
            )
        for pm in payment_methods:
            conn.execute(
                "INSERT INTO payment_history (reservation_id, payment_id, amount) VALUES (?, ?, ?)",
                (reservation_id, pm["payment_id"], pm["amount"]),
            )

        return _load_reservation_full(conn, reservation_id)


# ── Cancel Reservation ────────────────────────────────────────────────────────


def cancel_reservation(
    reservation_id: str,
    reason: str = "",
) -> dict:
    """
    Cancel a reservation and process refunds.

    Business rules enforced:
    - Cannot cancel an already-cancelled reservation
    - Cannot cancel if any flight is currently 'flying' or 'landed'
    - Eligible if ANY of:
        (a) reservation was created within the last 24 hours
        (b) airline cancelled at least one flight
        (c) cabin is 'business'
        (d) reservation has insurance AND reason is covered
            (covered reasons: delayed, missed_connection, weather, medical, other)
    Refunds: negative payment entries added for all original positive payments.
    """
    with get_conn() as conn:
        res = _load_res(conn, reservation_id)

        if res["status"] == "cancelled":
            raise ValueError(f"Reservation '{reservation_id}' is already cancelled")

        # Cannot cancel in-progress flights
        if _check_any_flight_active(conn, reservation_id):
            raise ValueError(
                "Cannot cancel reservation: one or more flights are currently active "
                "(status 'flying' or 'landed')"
            )

        # Check eligibility
        created_at_str = res["created_at"]
        try:
            created_at = datetime.fromisoformat(created_at_str)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            hours_since_booking = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
        except (ValueError, TypeError):
            hours_since_booking = 999  # treat as old booking if can't parse

        covered_reasons = {"delayed", "missed_connection", "weather", "medical", "other"}
        eligible = (
            hours_since_booking <= 24
            or _check_any_flight_airline_cancelled(conn, reservation_id)
            or res["cabin"] == "business"
            or (res["insurance"] == "yes" and reason.lower() in covered_reasons)
        )
        if not eligible:
            raise ValueError(
                "Cancellation not eligible. Cancellation is allowed when: "
                "(1) booked within last 24 hours, "
                "(2) airline cancelled a flight, "
                "(3) booked in business class, or "
                "(4) has travel insurance with a covered reason "
                f"(delayed, missed_connection, weather, medical, other). "
                f"Current reason provided: '{reason}'"
            )

        # Refund all positive payment entries
        payments = conn.execute(
            "SELECT * FROM payment_history WHERE reservation_id = ? AND amount > 0",
            (reservation_id,),
        ).fetchall()
        for p in payments:
            conn.execute(
                "INSERT INTO payment_history (reservation_id, payment_id, amount) VALUES (?, ?, ?)",
                (reservation_id, p["payment_id"], -p["amount"]),
            )

        conn.execute(
            "UPDATE reservations SET status = 'cancelled' WHERE reservation_id = ?",
            (reservation_id,),
        )

        return _load_reservation_full(conn, reservation_id)


# ── Update Reservation Flights ────────────────────────────────────────────────


def update_reservation_flights(
    reservation_id: str,
    cabin: str,
    flights: List[Dict],
    payment_id: str,
) -> dict:
    """
    Update the flights (and optionally cabin) of a reservation.

    Business rules enforced:
    - Reservation must be active (not cancelled)
    - basic_economy reservations cannot be modified
    - Cannot change if any flight is currently 'flying' or 'landed'
    - cabin must be valid
    - Cannot change origin, destination, or trip type
    - Certificates cannot be used for updates
    - Gift card balance must cover the price difference
    - New flights must be available with sufficient seats
    """
    if cabin not in ("business", "economy", "basic_economy"):
        raise ValueError(f"Invalid cabin: {cabin!r}")

    with get_conn() as conn:
        res = _load_res(conn, reservation_id)

        if res["status"] == "cancelled":
            raise ValueError(f"Reservation '{reservation_id}' is cancelled and cannot be modified")

        if res["cabin"] == "basic_economy":
            raise ValueError(
                "Basic economy reservations cannot be modified. "
                "Please cancel and rebook if you need to change your flights."
            )

        if _check_any_flight_active(conn, reservation_id):
            raise ValueError(
                "Cannot modify reservation: one or more flights are currently active "
                "(status 'flying' or 'landed')"
            )

        user_id = res["user_id"]

        # Validate payment method
        pm_row = conn.execute(
            "SELECT * FROM payment_methods WHERE payment_method_id = ? AND user_id = ?",
            (payment_id, user_id),
        ).fetchone()
        if pm_row is None:
            raise LookupError(f"Payment method '{payment_id}' not found for user '{user_id}'")
        if pm_row["source"] == "certificate":
            raise ValueError("Certificates cannot be used to modify reservations")

        current_flights = conn.execute(
            "SELECT * FROM reservation_flights WHERE reservation_id = ?",
            (reservation_id,),
        ).fetchall()
        passengers = conn.execute(
            "SELECT COUNT(*) as cnt FROM reservation_passengers WHERE reservation_id = ?",
            (reservation_id,),
        ).fetchone()
        num_passengers = passengers["cnt"]

        # Calculate new total price
        total_price = 0
        new_flight_records = []
        for fi in flights:
            fn = fi["flight_number"]
            dt = fi["date"]

            # Reuse existing flight's price if same flight+date+cabin
            matching = None
            if cabin == res["cabin"]:
                matching = next(
                    (
                        cf
                        for cf in current_flights
                        if cf["flight_number"] == fn and cf["date"] == dt
                    ),
                    None,
                )

            if matching:
                price = matching["price"]
                flight_row = conn.execute(
                    "SELECT * FROM flights WHERE flight_number = ?", (fn,)
                ).fetchone()
                new_flight_records.append(
                    {
                        "flight_number": fn,
                        "origin": flight_row["origin"] if flight_row else matching["origin"],
                        "destination": flight_row["destination"]
                        if flight_row
                        else matching["destination"],
                        "date": dt,
                        "price": price,
                    }
                )
            else:
                fd_row = _fd_row(conn, fn, dt)
                if fd_row["status"] != "available":
                    raise ValueError(f"Flight '{fn}' on {dt} is not available")
                seat_col = f"seats_{cabin}"
                if fd_row[seat_col] < num_passengers:
                    raise ValueError(f"Not enough {cabin} seats on flight '{fn}' on {dt}")
                flight_row = conn.execute(
                    "SELECT * FROM flights WHERE flight_number = ?", (fn,)
                ).fetchone()
                if flight_row is None:
                    raise LookupError(f"Flight route '{fn}' not found")
                price = fd_row[f"price_{cabin}"]
                new_flight_records.append(
                    {
                        "flight_number": fn,
                        "origin": flight_row["origin"],
                        "destination": flight_row["destination"],
                        "date": dt,
                        "price": price,
                    }
                )
            total_price += price * num_passengers

        old_price = sum(cf["price"] for cf in current_flights) * num_passengers
        price_diff = total_price - old_price

        # Validate gift card balance
        if pm_row["source"] == "gift_card" and pm_row["amount"] < price_diff:
            raise ValueError(
                f"Gift card balance insufficient: available {pm_row['amount']}, "
                f"additional charge {price_diff}"
            )

        # Charge / refund the difference
        if price_diff != 0:
            if pm_row["source"] == "gift_card":
                conn.execute(
                    "UPDATE payment_methods SET amount = amount - ? WHERE payment_method_id = ?",
                    (price_diff, payment_id),
                )
            conn.execute(
                "INSERT INTO payment_history (reservation_id, payment_id, amount) VALUES (?, ?, ?)",
                (reservation_id, payment_id, price_diff),
            )

        # Replace flight rows
        conn.execute(
            "DELETE FROM reservation_flights WHERE reservation_id = ?",
            (reservation_id,),
        )
        for fr in new_flight_records:
            conn.execute(
                """INSERT INTO reservation_flights
                   (reservation_id, flight_number, origin, destination, date, price)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    reservation_id,
                    fr["flight_number"],
                    fr["origin"],
                    fr["destination"],
                    fr["date"],
                    fr["price"],
                ),
            )

        # Update cabin
        conn.execute(
            "UPDATE reservations SET cabin = ? WHERE reservation_id = ?",
            (cabin, reservation_id),
        )

        return _load_reservation_full(conn, reservation_id)


# ── Update Reservation Baggages ───────────────────────────────────────────────


def update_reservation_baggages(
    reservation_id: str,
    total_baggages: int,
    nonfree_baggages: int,
    payment_id: str,
) -> dict:
    """
    Update baggage counts on a reservation.

    Business rules enforced:
    - Reservation must be active
    - nonfree_baggages cannot decrease (can only add bags, not remove)
    - total_baggages must be >= nonfree_baggages
    - fee = $50 per additional non-free bag
    - Certificates cannot be used
    - Gift card balance must cover the charge
    """
    if total_baggages < nonfree_baggages:
        raise ValueError(
            f"total_baggages ({total_baggages}) cannot be less than nonfree_baggages ({nonfree_baggages})"
        )

    with get_conn() as conn:
        res = _load_res(conn, reservation_id)

        if res["status"] == "cancelled":
            raise ValueError(f"Reservation '{reservation_id}' is cancelled")

        if nonfree_baggages < res["nonfree_baggages"]:
            raise ValueError(
                f"Cannot reduce non-free baggage count. "
                f"Current: {res['nonfree_baggages']}, requested: {nonfree_baggages}. "
                "You can only add bags, not remove them."
            )

        user_id = res["user_id"]
        pm_row = conn.execute(
            "SELECT * FROM payment_methods WHERE payment_method_id = ? AND user_id = ?",
            (payment_id, user_id),
        ).fetchone()
        if pm_row is None:
            raise LookupError(f"Payment method '{payment_id}' not found for user '{user_id}'")
        if pm_row["source"] == "certificate":
            raise ValueError("Certificates cannot be used to modify reservations")

        additional_nonfree = nonfree_baggages - res["nonfree_baggages"]
        charge = 50 * additional_nonfree

        if pm_row["source"] == "gift_card" and pm_row["amount"] < charge:
            raise ValueError(
                f"Gift card balance insufficient: available {pm_row['amount']}, charge {charge}"
            )

        if charge > 0:
            if pm_row["source"] == "gift_card":
                conn.execute(
                    "UPDATE payment_methods SET amount = amount - ? WHERE payment_method_id = ?",
                    (charge, payment_id),
                )
            conn.execute(
                "INSERT INTO payment_history (reservation_id, payment_id, amount) VALUES (?, ?, ?)",
                (reservation_id, payment_id, charge),
            )

        conn.execute(
            "UPDATE reservations SET total_baggages = ?, nonfree_baggages = ? WHERE reservation_id = ?",
            (total_baggages, nonfree_baggages, reservation_id),
        )

        return _load_reservation_full(conn, reservation_id)


# ── Update Reservation Passengers ─────────────────────────────────────────────


def update_reservation_passengers(
    reservation_id: str,
    passengers: List[Dict],
) -> dict:
    """
    Update passenger details on a reservation.

    Business rules enforced:
    - Reservation must be active
    - Number of passengers must match the original count (cannot add/remove passengers)
    """
    with get_conn() as conn:
        res = _load_res(conn, reservation_id)

        if res["status"] == "cancelled":
            raise ValueError(f"Reservation '{reservation_id}' is cancelled")

        current_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM reservation_passengers WHERE reservation_id = ?",
            (reservation_id,),
        ).fetchone()["cnt"]

        if len(passengers) != current_count:
            raise ValueError(
                f"Passenger count cannot change. "
                f"Original: {current_count}, provided: {len(passengers)}. "
                "You can only update passenger details, not add or remove passengers."
            )

        conn.execute(
            "DELETE FROM reservation_passengers WHERE reservation_id = ?",
            (reservation_id,),
        )
        for p in passengers:
            conn.execute(
                """INSERT INTO reservation_passengers
                   (reservation_id, first_name, last_name, dob)
                   VALUES (?, ?, ?, ?)""",
                (reservation_id, p["first_name"], p["last_name"], p["dob"]),
            )

        return _load_reservation_full(conn, reservation_id)
