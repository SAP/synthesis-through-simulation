"""
Flights API for the Airline environment.
Adapted from the external mock_system/apis/flights.py.
Returns plain dicts (JSON-serialisable).
"""

from __future__ import annotations

from synthesize.environments.airline.db.db import get_conn

AIRPORTS = [
    {"code": "ATL", "name": "Hartsfield-Jackson Atlanta International"},
    {"code": "DFW", "name": "Dallas/Fort Worth International"},
    {"code": "JFK", "name": "John F. Kennedy International"},
    {"code": "LAX", "name": "Los Angeles International"},
    {"code": "MIA", "name": "Miami International"},
    {"code": "ORD", "name": "O'Hare International"},
    {"code": "SEA", "name": "Seattle-Tacoma International"},
    {"code": "SFO", "name": "San Francisco International"},
]

VALID_STATUSES = ("available", "on time", "flying", "landed", "cancelled", "delayed")


def list_all_airports() -> list[dict]:
    """List all supported airport codes and names."""
    return AIRPORTS


def get_flight_status(flight_number: str, date: str) -> dict:
    """Get the status and availability of a specific flight on a given date."""
    with get_conn() as conn:
        flight = conn.execute(
            "SELECT * FROM flights WHERE flight_number = ?", (flight_number,)
        ).fetchone()
        if flight is None:
            raise LookupError(f"Flight '{flight_number}' not found")

        fd = conn.execute(
            "SELECT * FROM flight_dates WHERE flight_number = ? AND date = ?",
            (flight_number, date),
        ).fetchone()
        if fd is None:
            raise LookupError(f"No data for flight '{flight_number}' on {date}")

    return {
        "flight_number": flight_number,
        "origin": flight["origin"],
        "destination": flight["destination"],
        "date": date,
        "status": fd["status"],
        "scheduled_departure_time_est": flight["scheduled_departure_time_est"],
        "scheduled_arrival_time_est": flight["scheduled_arrival_time_est"],
        "seats_available": {
            "business": fd["seats_business"],
            "economy": fd["seats_economy"],
            "basic_economy": fd["seats_basic_economy"],
        },
        "prices": {
            "business": fd["price_business"],
            "economy": fd["price_economy"],
            "basic_economy": fd["price_basic_economy"],
        },
    }


def search_direct_flight(
    origin: str,
    destination: str,
    date: str,
) -> list[dict]:
    """
    Search for available direct flights between two airports on a given date.

    Returns flights with status='available' and their seat/price info.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT f.flight_number, f.origin, f.destination,
                   f.scheduled_departure_time_est, f.scheduled_arrival_time_est,
                   fd.date, fd.status,
                   fd.seats_business, fd.seats_economy, fd.seats_basic_economy,
                   fd.price_business, fd.price_economy, fd.price_basic_economy
            FROM flights f
            JOIN flight_dates fd ON f.flight_number = fd.flight_number
            WHERE f.origin = ?
              AND f.destination = ?
              AND fd.date = ?
              AND fd.status = 'available'
            ORDER BY f.scheduled_departure_time_est
            """,
            (origin, destination, date),
        ).fetchall()

    return [
        {
            "flight_number": r["flight_number"],
            "origin": r["origin"],
            "destination": r["destination"],
            "date": r["date"],
            "status": r["status"],
            "scheduled_departure_time_est": r["scheduled_departure_time_est"],
            "scheduled_arrival_time_est": r["scheduled_arrival_time_est"],
            "seats_available": {
                "business": r["seats_business"],
                "economy": r["seats_economy"],
                "basic_economy": r["seats_basic_economy"],
            },
            "prices": {
                "business": r["price_business"],
                "economy": r["price_economy"],
                "basic_economy": r["price_basic_economy"],
            },
        }
        for r in rows
    ]


def search_onestop_flight(
    origin: str,
    destination: str,
    date: str,
) -> list[dict]:
    """
    Search for one-stop connecting flights between two airports on a given date.

    Returns pairs of legs as [{"leg1": {...}, "leg2": {...}}, ...].
    """
    with get_conn() as conn:
        leg1_rows = conn.execute(
            """
            SELECT f.flight_number, f.origin, f.destination,
                   f.scheduled_departure_time_est, f.scheduled_arrival_time_est,
                   fd.date, fd.seats_business, fd.seats_economy, fd.seats_basic_economy,
                   fd.price_business, fd.price_economy, fd.price_basic_economy
            FROM flights f
            JOIN flight_dates fd ON f.flight_number = fd.flight_number
            WHERE f.origin = ?
              AND fd.date = ?
              AND fd.status = 'available'
            ORDER BY f.scheduled_departure_time_est
            """,
            (origin, date),
        ).fetchall()

    results = []
    for leg1 in leg1_rows:
        connecting = leg1["destination"]
        if connecting == destination:
            continue  # skip directs

        arrival = leg1["scheduled_arrival_time_est"]
        leg2_date = date
        if "+1" in arrival:
            # next-day arrival: advance the date by 1
            from datetime import date as _date
            from datetime import timedelta

            d = _date.fromisoformat(date)
            leg2_date = (d + timedelta(days=1)).isoformat()
            arrival = arrival.replace("+1", "").strip()

        leg2_flights = search_direct_flight(
            origin=connecting,
            destination=destination,
            date=leg2_date,
        )
        # Filter leg2 departures that leave after leg1 arrives
        for leg2 in leg2_flights:
            if leg2["scheduled_departure_time_est"] >= arrival:
                results.append(
                    {
                        "leg1": {
                            "flight_number": leg1["flight_number"],
                            "origin": leg1["origin"],
                            "destination": leg1["destination"],
                            "date": date,
                            "scheduled_departure_time_est": leg1["scheduled_departure_time_est"],
                            "scheduled_arrival_time_est": leg1["scheduled_arrival_time_est"],
                            "prices": {
                                "business": leg1["price_business"],
                                "economy": leg1["price_economy"],
                                "basic_economy": leg1["price_basic_economy"],
                            },
                        },
                        "leg2": leg2,
                    }
                )

    return results
