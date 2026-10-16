"""
Airline synthesizers.

AirlineAgentSynthesizer — LLM agent executes airline reservation intents via Airline APIs.

Auto-discovered by synthesis_runner.py since it subclasses DefaultAgentSynthesizer
and lives in synthesize/synthesizer/.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional

from synthesize.environments.airline.apis import flights as flights_api
from synthesize.environments.airline.apis import payments as payments_api
from synthesize.environments.airline.apis import reservations as reservations_api
from synthesize.environments.airline.apis import users as users_api
from synthesize.environments.airline.db.db import get_conn
from synthesize.synthesizer.agent_synthesizer import IntentDef, Step
from synthesize.synthesizer.default_agent import DefaultAgentSynthesizer
from synthesize.synthesizer.generalist_synthesizer import GeneralistSynthesizer

# ── Tool registry ─────────────────────────────────────────────────────────────

AIRLINE_TOOL_REGISTRY: Dict[str, dict] = {
    # ── User lookups ─────────────────────────────────────────────────────────
    "get_user_details": {
        "fn": users_api.get_user_details,
        "description": (
            "Get full user details: membership level, address, payment methods, "
            "and saved passenger profiles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User ID, e.g. 'gold_alice_1'"},
            },
            "required": ["user_id"],
        },
    },
    "list_users": {
        "fn": users_api.list_users,
        "description": "List all users with optional membership filter (gold/silver/regular).",
        "input_schema": {
            "type": "object",
            "properties": {
                "membership": {
                    "type": "string",
                    "enum": ["gold", "silver", "regular"],
                    "description": "Optional membership filter",
                },
            },
            "required": [],
        },
    },
    "get_payment_methods": {
        "fn": payments_api.get_payment_methods,
        "description": "List all payment methods for a user (credit cards, gift cards, certificates).",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User ID"},
            },
            "required": ["user_id"],
        },
    },
    # ── Flight lookups ───────────────────────────────────────────────────────
    "list_all_airports": {
        "fn": flights_api.list_all_airports,
        "description": "List all supported airport codes and their full names.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "search_direct_flight": {
        "fn": flights_api.search_direct_flight,
        "description": (
            "Search for available direct flights between two airports on a given date. "
            "Returns flight numbers, scheduled times, available seats per cabin, and prices."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Origin airport IATA code, e.g. 'JFK'"},
                "destination": {
                    "type": "string",
                    "description": "Destination airport IATA code, e.g. 'LAX'",
                },
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
            },
            "required": ["origin", "destination", "date"],
        },
    },
    "search_onestop_flight": {
        "fn": flights_api.search_onestop_flight,
        "description": (
            "Search for one-stop connecting flights between two airports on a given date. "
            "Returns pairs of leg1 and leg2 flights."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Origin airport IATA code"},
                "destination": {"type": "string", "description": "Destination airport IATA code"},
                "date": {"type": "string", "description": "Departure date in YYYY-MM-DD format"},
            },
            "required": ["origin", "destination", "date"],
        },
    },
    "get_flight_status": {
        "fn": flights_api.get_flight_status,
        "description": (
            "Get the status and seat availability for a specific flight on a given date. "
            "Status can be: available, on time, flying, landed, cancelled, delayed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_number": {"type": "string", "description": "Flight number, e.g. 'HAT001'"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
            },
            "required": ["flight_number", "date"],
        },
    },
    # ── Reservation read ─────────────────────────────────────────────────────
    "get_reservation_details": {
        "fn": reservations_api.get_reservation_details,
        "description": (
            "Get full reservation details: flights, passengers, payment history, status. "
            "status=null means active; status='cancelled' means cancelled."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reservation_id": {
                    "type": "string",
                    "description": "Reservation ID, e.g. 'ZFA001'",
                },
            },
            "required": ["reservation_id"],
        },
    },
    "list_reservations": {
        "fn": reservations_api.list_reservations,
        "description": "List reservations for a user. Use status='active' to filter active only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User ID"},
                "status": {
                    "type": "string",
                    "enum": ["active", "cancelled"],
                    "description": "Filter by status",
                },
            },
            "required": [],
        },
    },
    # ── Reservation write ────────────────────────────────────────────────────
    "book_reservation": {
        "fn": reservations_api.book_reservation,
        "description": (
            "Book a new reservation. "
            "Business rules: max 5 passengers; max 1 certificate + 1 credit card + 3 gift cards; "
            "insurance = $30/passenger; baggage = $50/non-free bag; "
            "payment must exactly cover total price; "
            "all flights must be available with sufficient seats."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User ID"},
                "origin": {"type": "string", "description": "Origin airport IATA code"},
                "destination": {"type": "string", "description": "Destination airport IATA code"},
                "flight_type": {
                    "type": "string",
                    "enum": ["one_way", "round_trip"],
                    "description": "Trip type",
                },
                "cabin": {
                    "type": "string",
                    "enum": ["business", "economy", "basic_economy"],
                    "description": "Cabin class",
                },
                "flights": {
                    "type": "array",
                    "description": "List of flights. Each item: {flight_number, date}",
                    "items": {
                        "type": "object",
                        "properties": {
                            "flight_number": {"type": "string"},
                            "date": {"type": "string"},
                        },
                        "required": ["flight_number", "date"],
                    },
                },
                "passengers": {
                    "type": "array",
                    "description": "List of passengers. Each item: {first_name, last_name, dob}",
                    "items": {
                        "type": "object",
                        "properties": {
                            "first_name": {"type": "string"},
                            "last_name": {"type": "string"},
                            "dob": {"type": "string", "description": "Date of birth YYYY-MM-DD"},
                        },
                        "required": ["first_name", "last_name", "dob"],
                    },
                },
                "payment_methods": {
                    "type": "array",
                    "description": "Payment methods. Each item: {payment_id, amount}",
                    "items": {
                        "type": "object",
                        "properties": {
                            "payment_id": {"type": "string"},
                            "amount": {"type": "integer"},
                        },
                        "required": ["payment_id", "amount"],
                    },
                },
                "total_baggages": {"type": "integer", "description": "Total bags (including free)"},
                "nonfree_baggages": {
                    "type": "integer",
                    "description": "Number of paid bags ($50 each)",
                },
                "insurance": {
                    "type": "string",
                    "enum": ["yes", "no"],
                    "description": "Travel insurance ($30/passenger)",
                },
            },
            "required": [
                "user_id",
                "origin",
                "destination",
                "flight_type",
                "cabin",
                "flights",
                "passengers",
                "payment_methods",
            ],
        },
    },
    "cancel_reservation": {
        "fn": reservations_api.cancel_reservation,
        "description": (
            "Cancel a reservation and process refunds. "
            "Eligible when: booked within last 24hr, airline cancelled a flight, "
            "business cabin, or has insurance with covered reason "
            "(delayed/missed_connection/weather/medical/other). "
            "Cannot cancel already-flying or landed flights."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string", "description": "Reservation ID to cancel"},
                "reason": {
                    "type": "string",
                    "description": (
                        "Reason for cancellation. Required if using insurance eligibility. "
                        "Valid reasons: delayed, missed_connection, weather, medical, other"
                    ),
                },
            },
            "required": ["reservation_id"],
        },
    },
    "update_reservation_flights": {
        "fn": reservations_api.update_reservation_flights,
        "description": (
            "Update the flights (and optionally cabin class) of an active reservation. "
            "Cannot modify basic_economy reservations. "
            "Cannot change if any flight is flying/landed. "
            "Certificates cannot be used — use credit card or gift card. "
            "Price difference is charged/refunded to the provided payment method."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string"},
                "cabin": {
                    "type": "string",
                    "enum": ["business", "economy", "basic_economy"],
                    "description": "New cabin class (can differ from original if not basic_economy)",
                },
                "flights": {
                    "type": "array",
                    "description": "New list of flights. Each: {flight_number, date}",
                    "items": {
                        "type": "object",
                        "properties": {
                            "flight_number": {"type": "string"},
                            "date": {"type": "string"},
                        },
                        "required": ["flight_number", "date"],
                    },
                },
                "payment_id": {
                    "type": "string",
                    "description": "Payment method ID for any price difference (not a certificate)",
                },
            },
            "required": ["reservation_id", "cabin", "flights", "payment_id"],
        },
    },
    "update_reservation_baggages": {
        "fn": reservations_api.update_reservation_baggages,
        "description": (
            "Add checked bags to a reservation. $50 per additional non-free bag. "
            "Cannot reduce baggage count — only increase. "
            "Certificates cannot be used."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string"},
                "total_baggages": {"type": "integer", "description": "New total bag count"},
                "nonfree_baggages": {
                    "type": "integer",
                    "description": "New non-free bag count (must be >= current)",
                },
                "payment_id": {
                    "type": "string",
                    "description": "Payment method ID for baggage charge",
                },
            },
            "required": ["reservation_id", "total_baggages", "nonfree_baggages", "payment_id"],
        },
    },
    "update_reservation_passengers": {
        "fn": reservations_api.update_reservation_passengers,
        "description": (
            "Update passenger details (names, DOBs) on a reservation. "
            "Number of passengers cannot change — provide the same count as original."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reservation_id": {"type": "string"},
                "passengers": {
                    "type": "array",
                    "description": "Updated passenger list. Must have same count as original.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "first_name": {"type": "string"},
                            "last_name": {"type": "string"},
                            "dob": {"type": "string"},
                        },
                        "required": ["first_name", "last_name", "dob"],
                    },
                },
            },
            "required": ["reservation_id", "passengers"],
        },
    },
    "send_certificate": {
        "fn": payments_api.send_certificate,
        "description": (
            "Issue a travel certificate to a user as compensation. "
            "Standard amounts: $50, $100, $200."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "amount": {"type": "integer", "description": "Certificate value in dollars"},
            },
            "required": ["user_id", "amount"],
        },
    },
    "calculate": {
        "fn": lambda expression: {"result": eval(expression, {"__builtins__": {}})},  # noqa: PGH001
        "description": "Evaluate a simple arithmetic expression, e.g. '600 + 250 * 2'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression to evaluate",
                },
            },
            "required": ["expression"],
        },
    },
}

# ── Samplers ──────────────────────────────────────────────────────────────────


def _future_date(days_ahead: int = 7) -> str:
    """Return a date string N days from the seed reference date."""
    ref = date(2026, 4, 20)
    return (ref + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


def _sample_book_reservation() -> Optional[dict]:
    """
    Sample params for BOOK_RESERVATION.

    Returns only the validity anchors the agent cannot guess: user identity,
    a specific available flight, and that a payment method exists.  Fields the
    agent should choose freely (cabin class, passengers, insurance, bags) are
    intentionally omitted so the LLM drives synthesis diversity for those dimensions.

    Guarantees at least one cabin has available seats on the returned flight.
    """
    with get_conn() as conn:
        users = conn.execute("SELECT * FROM users ORDER BY RANDOM() LIMIT 5").fetchall()
        if not users:
            return None

        for user in users:
            uid = user["user_id"]
            cc = conn.execute(
                "SELECT * FROM payment_methods WHERE user_id = ? AND source = 'credit_card' LIMIT 1",
                (uid,),
            ).fetchone()
            if cc is None:
                continue

            flight_date = conn.execute(
                """
                SELECT f.flight_number, f.origin, f.destination, fd.date
                FROM flight_dates fd
                JOIN flights f ON fd.flight_number = f.flight_number
                WHERE fd.status = 'available'
                  AND fd.date >= '2026-04-22'
                  AND (fd.seats_business > 0 OR fd.seats_economy > 0 OR fd.seats_basic_economy > 0)
                ORDER BY RANDOM()
                LIMIT 1
                """
            ).fetchone()
            if flight_date is None:
                continue

            return {
                "user_id": uid,
                "origin": flight_date["origin"],
                "destination": flight_date["destination"],
                "flight_number": flight_date["flight_number"],
                "date": flight_date["date"],
            }
    return None


def _sample_cancel_reservation() -> Optional[dict]:
    """
    Sample an active reservation that satisfies at least one cancellation eligibility condition.

    Mirrors the exact eligibility logic in cancel_reservation() so the task is always
    possible — avoiding runs that fail purely because the sampler picked an ineligible
    reservation.  The four eligible conditions (any one suffices):
        (a) booked within last 24 hours
        (b) cabin is 'business'
        (c) has travel insurance ('yes')
        (d) an airline-cancelled flight exists on the reservation

    The task prompt deliberately omits which condition applies so the agent must
    inspect the reservation and determine the right cancellation reason itself.
    """
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT r.reservation_id, r.user_id, r.cabin, r.insurance
            FROM reservations r
            WHERE r.status IS NULL
              AND (
                  r.cabin = 'business'
                  OR r.insurance = 'yes'
                  OR r.created_at >= datetime('now', '-24 hours')
                  OR EXISTS (
                      SELECT 1 FROM reservation_flights rf
                      JOIN flight_dates fd
                        ON rf.flight_number = fd.flight_number AND rf.date = fd.date
                      WHERE rf.reservation_id = r.reservation_id
                        AND fd.status = 'cancelled'
                  )
              )
            ORDER BY RANDOM()
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return {
        "reservation_id": row["reservation_id"],
        "user_id": row["user_id"],
    }


def _sample_modify_reservation() -> Optional[dict]:
    """
    Sample an active non-basic-economy reservation for modification.

    Returns only the validity anchors: reservation_id and user_id.
    The modification type (baggages vs passengers) and payment method are
    intentionally omitted — the agent should inspect the reservation and
    decide what to modify and how to pay.
    """
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT r.reservation_id, r.user_id
            FROM reservations r
            WHERE r.status IS NULL
              AND r.cabin != 'basic_economy'
            ORDER BY RANDOM()
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return {
        "reservation_id": row["reservation_id"],
        "user_id": row["user_id"],
    }


# ── Postconditions ────────────────────────────────────────────────────────────


def _postcond_book(params: dict, steps: List[Step]) -> Dict[str, bool]:
    reservation_id = None
    for step in steps:
        if step.tool == "book_reservation" and not step.is_error:
            result = step.result
            if isinstance(result, dict):
                reservation_id = result.get("reservation_id")
            break

    if not reservation_id:
        return {
            "reservation_created": False,
            "has_flights": False,
            "has_passengers": False,
            "has_payment": False,
        }

    with get_conn() as conn:
        res = conn.execute(
            "SELECT * FROM reservations WHERE reservation_id = ?", (reservation_id,)
        ).fetchone()
        flight_count = conn.execute(
            "SELECT COUNT(*) FROM reservation_flights WHERE reservation_id = ?",
            (reservation_id,),
        ).fetchone()[0]
        pax_count = conn.execute(
            "SELECT COUNT(*) FROM reservation_passengers WHERE reservation_id = ?",
            (reservation_id,),
        ).fetchone()[0]
        payment_sum = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payment_history WHERE reservation_id = ?",
            (reservation_id,),
        ).fetchone()[0]

    return {
        "reservation_created": res is not None and res["status"] is None,
        "has_flights": flight_count > 0,
        "has_passengers": pax_count > 0,
        "has_payment": payment_sum > 0,
    }


def _postcond_cancel(params: dict, steps: List[Step]) -> Dict[str, bool]:
    reservation_id = params.get("reservation_id")
    if not reservation_id:
        # Try to find it from steps
        for step in steps:
            if step.tool == "cancel_reservation" and not step.is_error:
                result = step.result
                if isinstance(result, dict):
                    reservation_id = result.get("reservation_id")
                break
    if not reservation_id:
        return {"reservation_cancelled": False, "refund_created": False}

    with get_conn() as conn:
        res = conn.execute(
            "SELECT status FROM reservations WHERE reservation_id = ?", (reservation_id,)
        ).fetchone()
        refund = conn.execute(
            "SELECT 1 FROM payment_history WHERE reservation_id = ? AND amount < 0 LIMIT 1",
            (reservation_id,),
        ).fetchone()

    return {
        "reservation_cancelled": res is not None and res["status"] == "cancelled",
        "refund_created": refund is not None,
    }


def _postcond_modify(params: dict, steps: List[Step]) -> Dict[str, bool]:
    reservation_id = params.get("reservation_id")
    if not reservation_id:
        return {"modification_applied": False}

    for step in steps:
        tool = step.tool
        if (
            tool
            in (
                "update_reservation_flights",
                "update_reservation_baggages",
                "update_reservation_passengers",
            )
            and not step.is_error
        ):
            return {"modification_applied": True}

    return {"modification_applied": False}


# ── Intent definitions ─────────────────────────────────────────────────────────

AIRLINE_INTENTS: Dict[str, IntentDef] = {
    "BOOK_RESERVATION": IntentDef(
        name="BOOK_RESERVATION",
        brief="Book a new flight reservation for a user with selected flights, cabin, and payment.",
        informed_rules="""\
Airline Booking Business Rules:
- flight_type must be 'one_way' or 'round_trip'
- cabin must be 'business', 'economy', or 'basic_economy'
- Maximum 5 passengers per reservation
- Payment methods per reservation: max 1 certificate, max 1 credit card, max 3 gift cards
- All flights must have status='available' with enough seats for the requested cabin
- Price per flight: use get_flight_status or search_direct_flight to get current prices
- Insurance fee: $30 per passenger (if insurance='yes')
- Non-free baggage fee: $50 per non-free bag
- Total payment provided must EXACTLY equal: (sum of flight prices × passengers) + insurance + baggage fees
- Gift card and certificate balances are validated; certificates are consumed (deleted) on use
- Free baggage allowance per passenger (does not cost extra):
    gold tier:    business=3 free, economy=2 free, basic_economy=2 free
    silver tier:  business=2 free, economy=2 free, basic_economy=1 free
    regular tier: business=1 free, economy=0 free, basic_economy=0 free
- basic_economy restrictions: no seat upgrades, no same-day changes, no refunds
- Vary your choices across runs: use different cabin classes, passenger counts,
  payment methods, and add-on combinations to generate a diverse dataset
""",
        tools=[
            "get_user_details",
            "list_users",
            "get_payment_methods",
            "list_all_airports",
            "search_direct_flight",
            "search_onestop_flight",
            "get_flight_status",
            "book_reservation",
            "calculate",
        ],
        sampler=_sample_book_reservation,
        task_prompt=lambda p: (
            f"Book a flight for user '{p['user_id']}' "
            f"from {p['origin']} to {p['destination']} "
            f"on {p['date']} (flight {p['flight_number']}). "
            "Look up the user's saved passengers and payment methods, then choose: "
            "cabin class (economy/business/first), which passenger(s) to include, "
            "which payment method to use, and whether to add travel insurance or extra bags."
        ),
        postconditions=_postcond_book,
    ),
    "CANCEL_RESERVATION": IntentDef(
        name="CANCEL_RESERVATION",
        brief="Cancel an existing active reservation and process refunds.",
        informed_rules="""\
Airline Cancellation Business Rules:
- Cancellation is only eligible when ANY of:
    (a) Reservation was booked within the last 24 hours
    (b) The airline cancelled at least one flight in the reservation
    (c) The cabin class is 'business'
    (d) The reservation has insurance='yes' AND the reason is one of:
        delayed, missed_connection, weather, medical, other
- Cannot cancel if any flight in the reservation is currently 'flying' or 'landed'
- Cannot cancel an already-cancelled reservation
- On cancellation, all positive payment entries are reversed (refunded)
- Refund method: same payment method as original payment
- Compensation certificates may be issued separately via send_certificate
""",
        tools=[
            "get_user_details",
            "get_reservation_details",
            "list_reservations",
            "get_flight_status",
            "cancel_reservation",
            "send_certificate",
        ],
        sampler=_sample_cancel_reservation,
        task_prompt=lambda p: (
            f"Cancel reservation '{p['reservation_id']}' for user '{p['user_id']}'. "
            "Look up the reservation details to determine why it is eligible for cancellation, "
            "provide an appropriate reason, and process the cancellation."
        ),
        postconditions=_postcond_cancel,
    ),
    "MODIFY_RESERVATION": IntentDef(
        name="MODIFY_RESERVATION",
        brief="Modify baggage or passenger details on an existing active reservation.",
        informed_rules="""\
Airline Modification Business Rules:
- Basic economy ('basic_economy') reservations CANNOT be modified (flights, cabin, or other)
- Cannot modify if any flight is currently 'flying' or 'landed'
- Cannot change origin, destination, or trip type (one_way/round_trip)
- Baggage updates: can only ADD bags, not remove. Non-free bags cost $50 each.
    Certificates cannot be used for payment — use credit card or gift card.
- Passenger updates: passenger count CANNOT change. You can only update names/DOBs.
- Flight/cabin updates: new cabin must be valid; certificates cannot be used as payment.
    If changing cabin, new flights must have enough seats in the new cabin.
""",
        tools=[
            "get_user_details",
            "get_reservation_details",
            "list_reservations",
            "get_payment_methods",
            "search_direct_flight",
            "get_flight_status",
            "update_reservation_flights",
            "update_reservation_baggages",
            "update_reservation_passengers",
            "calculate",
        ],
        sampler=_sample_modify_reservation,
        task_prompt=lambda p: (
            f"Modify reservation '{p['reservation_id']}' for user '{p['user_id']}'. "
            "Look up the reservation details, then make an appropriate modification — "
            "either update the passenger details or adjust the baggage allowance. "
            "Use a suitable payment method for any additional charges."
        ),
        postconditions=_postcond_modify,
    ),
}

# ── Synthesizer class ─────────────────────────────────────────────────────────


class AirlineAgentSynthesizer(DefaultAgentSynthesizer):
    def __init__(self) -> None:
        super().__init__(
            name="airline_agent",
            description="LLM agent executes airline reservation intents via Airline APIs",
            tool_registry=AIRLINE_TOOL_REGISTRY,
            intents=AIRLINE_INTENTS,
            env_name="Airline Reservations",
        )


class AirlineGeneralistSynthesizer(GeneralistSynthesizer):
    # Maps intent names → the write tools that belong to each intent.
    # Used to infer which intent the agent executed from its successful tool calls.
    INTENT_TO_WRITE_TOOLS = {
        "BOOK_RESERVATION": {"book_reservation"},
        "CANCEL_RESERVATION": {"cancel_reservation"},
        "MODIFY_RESERVATION": {
            "update_reservation_flights",
            "update_reservation_baggages",
            "update_reservation_passengers",
        },
    }

    def __init__(self) -> None:
        super().__init__(
            name="airline_generalist",
            description=(
                "Goal-directed agent that observes DB state, selects an appropriate intent "
                "from the bootstrap library, and executes it — no pre-assigned task. "
                "Supports blind / informed / evolve modes."
            ),
            tool_registry=AIRLINE_TOOL_REGISTRY,
            bootstrap_intents=AIRLINE_INTENTS,
            env_name="Airline Reservations",
        )

    def _init_evolution(self) -> None:
        """Set up the airline evolution engine and intent library."""
        from pathlib import Path

        from synthesize.evolution.analyzer import TrajectoryAnalyzer
        from synthesize.evolution.engine import EvolutionEngine
        from synthesize.evolution.models import EvolvedIntent, IntentLibrary
        from synthesize.evolution.store import TrajectoryStore
        from synthesize.synthesizer.agent_synthesizer import MODEL, PROXY_BASE_URL

        runs_root = Path(".runs") / "evolution" / "airline"
        runs_root.mkdir(parents=True, exist_ok=True)

        store = TrajectoryStore(runs_root / "trajectories.db")
        analyzer = TrajectoryAnalyzer(
            model=MODEL,
            base_url=PROXY_BASE_URL,
            api_key="anything",
        )
        engine = EvolutionEngine(store=store, analyzer=analyzer)

        library_path = runs_root / "intent_library.json"
        if library_path.exists():
            library = IntentLibrary.load(library_path)
        else:
            library = IntentLibrary()
            for name, intent_def in AIRLINE_INTENTS.items():
                library.add_intent(EvolvedIntent.from_intent_def(intent_def))

        self.evolution_engine = engine
        self.intent_library = library
        self.library_path = library_path


# Generic alias used by GeneralistPopulatorSynthesizer dynamic import
TOOL_REGISTRY = AIRLINE_TOOL_REGISTRY
