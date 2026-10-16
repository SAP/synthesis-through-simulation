"""
EnvScaler task generator for the airline environment.

Replicates EnvScaler ScenGenerator Step 2 (task description generation) using
the airline environment's tool registry and a real baseline DB snapshot as the
initial state.  Output is a JSON list of task strings saved to
scripts/envscaler_airline_tasks.json.

Usage:
    python scripts/envscaler_gen_tasks.py [--n 30] [--out scripts/envscaler_airline_tasks.json]

The generated tasks are consumed by run_envscaler_comparison.py, which feeds them
to our blind agent synthesizer and measures DF + VPR — allowing a direct comparison
with G0_blind.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

PROXY_BASE_URL = "http://localhost:4000"
MODEL = "gpt-4.1"

# Baseline DB to use as the initial state for task generation
BASELINE_DB = REPO_ROOT / "src" / "synthesize" / "environments" / "airline" / "db" / "airline_snapshot.db"

# ── EnvScaler Step-2 prompt template (verbatim from ScenGenerator) ────────────

_STEP2_TEMPLATE = """\
You are a task design expert, responsible for creating realistic, clear, and challenging tasks for a specific interactive environment.

You do not need to consider how the task will be executed; another execution expert will be responsible for completing it.

# Environment Introduction:
{env_introduction}

# Environment State Definition:
{env_state_definition}

# Supported Operation Interfaces:
{env_modify_operation}

# Environment Rules / Constraints:
{env_rule}

# Current Environment Initial State / Database:
{env_init_state}

# Task Design Requirements:
- **Realism**: The task must closely align with the current environment, reflect a plausible real-world scenario, and have a well-defined objective with business relevance.
- **Feasibility**:
    i. The task must be based on and constrained by the current initial state of the environment. For example, you cannot cancel a reservation that does not exist.
    ii. The task should be achievable through a combination of multiple operational interfaces supported by the environment. On one hand, the task description must include nessary information to enable successful completion (for example, if all tools only support actions by ID and can not get the ID anyway, the task should at least provide the ID). On the other hand, it should not include excessive information, so that the Agent is encouraged to use information query tools to obtain the necessary data rather than relying solely on the information provided in the task description.
    iii. Avoid tasks that require more than just the user interface. For example, timestamps might be automatically generated rather than modified through the user interface.
- **State Modification**: The goal of the task must involve modifying the current environment state/database; it cannot be limited to information queries only.
- **Challenge**: The task should be difficult enough that the agent needs to make multiple calls to information query tools and state modification tools to complete it. For example, the modification should have sufficient complexity (e.g., involving multiple objects, multiple attributes, or multi-condition combinations), and should not be achievable in a single simple step.
- **Compositionality**: The task must be composed of several distinct sub-tasks (No less than 50 words). Each sub-task must require multiple tool invocations to complete, ensuring layered complexity and interdependent steps across the task flow.
- **Clarity**: Use concise natural language to describe each sub-task. The description must be easy to understand and unambiguous. Since the ultimate goal is to modify the state, query tools are only part of the task-solving process and serve to provide information to the Agent; therefore, there is no need to include query requirements or intermediate steps in the task description.

Strictly follow the output format below:

# Analysis
[Your detailed step-by step reasoning and thought process, including environment description, current environment state, and supporting operation interfaces and so on.]

# Task
[Only the Task description, without any other analysis or explanation.]
"""

# ── Airline environment descriptor ────────────────────────────────────────────

AIRLINE_ENV_ITEM = {
    "env_class_name": "AirlineEnv",
    "environment_introduction": (
        "An airline reservation management system. Users can search for flights, "
        "book reservations, manage passengers and baggage, apply travel insurance, "
        "and cancel reservations subject to business rules. The system tracks users "
        "with membership tiers (gold/silver/regular), flight schedules across multiple "
        "airports, and payment methods (credit card, gift card, certificate)."
    ),
    "state_space_definition": (
        "users: {user_id, first_name, last_name, email, dob, membership (gold/silver/regular), address fields}\n"
        "payment_methods: {payment_method_id, user_id, source (credit_card/gift_card/certificate), brand, last_four, amount}\n"
        "flights: {flight_number, origin, destination, scheduled_departure_time_est, scheduled_arrival_time_est}\n"
        "flight_dates: {flight_number, date, status (available/on_time/flying/landed/cancelled/delayed), seats per cabin, prices per cabin}\n"
        "reservations: {reservation_id (starts with Z), user_id, origin, destination, flight_type (one_way/round_trip), "
        "cabin (business/economy/basic_economy), total_baggages, nonfree_baggages, insurance (yes/no), status (NULL=active/cancelled)}\n"
        "reservation_flights: {reservation_id, flight_number, origin, destination, date, price}\n"
        "reservation_passengers: {reservation_id, first_name, last_name, dob}\n"
        "saved_passengers: {user_id, first_name, last_name, dob}\n"
        "payment_history: {reservation_id, payment_id, amount}"
    ),
    "operation_list": [
        {
            "operation_name": "list_users",
            "operation_type": "query",
            "operation_description": "List all users with optional membership filter (gold/silver/regular).",
        },
        {
            "operation_name": "get_user_details",
            "operation_type": "query",
            "operation_description": "Get full user details including saved passengers and payment methods.",
        },
        {
            "operation_name": "get_payment_methods",
            "operation_type": "query",
            "operation_description": "List all payment methods for a user.",
        },
        {
            "operation_name": "list_all_airports",
            "operation_type": "query",
            "operation_description": "List all supported airport codes and names.",
        },
        {
            "operation_name": "search_direct_flight",
            "operation_type": "query",
            "operation_description": (
                "Search for available direct flights between two airports on a given date. "
                "Returns flight number, cabin availability and prices."
            ),
        },
        {
            "operation_name": "search_onestop_flight",
            "operation_type": "query",
            "operation_description": (
                "Search for one-stop (connecting) flights between two airports on a given date."
            ),
        },
        {
            "operation_name": "get_flight_status",
            "operation_type": "query",
            "operation_description": "Get the status and seat availability of a specific flight on a given date.",
        },
        {
            "operation_name": "list_reservations",
            "operation_type": "query",
            "operation_description": "List reservations for a user. status='active' filters non-cancelled.",
        },
        {
            "operation_name": "get_reservation_details",
            "operation_type": "query",
            "operation_description": "Get full details of a reservation including flights, passengers, and payment history.",
        },
        {
            "operation_name": "book_reservation",
            "operation_type": "write",
            "operation_description": (
                "Book a new reservation. Requires: user_id, flights list (flight_number, date, price), "
                "passengers list (first_name, last_name, dob), cabin, payment_methods list "
                "(payment_method_id, amount), flight_type (one_way/round_trip), "
                "total_baggages, nonfree_baggages, insurance (yes/no)."
            ),
        },
        {
            "operation_name": "cancel_reservation",
            "operation_type": "write",
            "operation_description": (
                "Cancel an active reservation. Issues refunds to original payment methods. "
                "Fails if any flight is currently flying or already landed."
            ),
        },
        {
            "operation_name": "update_reservation_flights",
            "operation_type": "write",
            "operation_description": (
                "Change the flights on an active reservation. The new flights must be on the "
                "same routes; payment difference is charged or refunded automatically."
            ),
        },
        {
            "operation_name": "update_reservation_baggages",
            "operation_type": "write",
            "operation_description": (
                "Update baggage counts on an active reservation. "
                "nonfree_baggages must not exceed total_baggages. "
                "Additional fees charged or refunded automatically."
            ),
        },
        {
            "operation_name": "update_reservation_passengers",
            "operation_type": "write",
            "operation_description": (
                "Replace the passenger list on an active reservation. "
                "basic_economy reservations are limited to 3 passengers; others up to 9."
            ),
        },
        {
            "operation_name": "send_certificate",
            "operation_type": "write",
            "operation_description": (
                "Send a travel certificate (credit voucher) to a user's account. "
                "A user may hold at most one active certificate at a time."
            ),
        },
    ],
    "constraints_rules": [
        "Reservation status is NULL (active) or 'cancelled'. Active = status IS NULL.",
        "flight_type must be 'one_way' or 'round_trip'.",
        "cabin must be 'business', 'economy', or 'basic_economy'.",
        "insurance must be 'yes' or 'no'.",
        "nonfree_baggages must be <= total_baggages.",
        "basic_economy reservations: max 3 passengers; all other cabins: max 9 passengers.",
        "Active reservations must have at least one payment record.",
        "Cancelled reservations must have a refund payment record.",
        "All payment_method_id values in payment_history must exist in payment_methods.",
        "All flight_number values in reservation_flights must exist in flights.",
        "Cancellation only allowed if no flight in the reservation is currently flying or landed.",
        "A user may hold at most one certificate (source='certificate') payment method at a time.",
    ],
}


# ── DB state reader ────────────────────────────────────────────────────────────

def _read_db_state(db_path: Path) -> dict:
    """Read key tables from the baseline DB and return a compact JSON-serialisable dict."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    def _rows(sql: str) -> list[dict]:
        return [dict(r) for r in conn.execute(sql).fetchall()]

    state = {
        "users": _rows("SELECT user_id, first_name, last_name, membership FROM users"),
        "payment_methods": _rows(
            "SELECT payment_method_id, user_id, source, brand, last_four, amount FROM payment_methods"
        ),
        "flights": _rows("SELECT flight_number, origin, destination FROM flights"),
        "reservations": _rows(
            "SELECT reservation_id, user_id, flight_type, cabin, total_baggages, "
            "insurance, status FROM reservations"
        ),
        "reservation_passengers": _rows(
            "SELECT reservation_id, first_name, last_name FROM reservation_passengers"
        ),
    }
    conn.close()
    return state


# ── Task generation ────────────────────────────────────────────────────────────

def _build_prompt(env_item: dict, init_state: dict) -> str:
    op_lines = []
    for i, op in enumerate(env_item["operation_list"]):
        op_lines.append(
            f"{i}.\nOperation Name: {op['operation_name']}\n"
            f"Operation Type: {op['operation_type']}\n"
            f"Description: {op['operation_description']}"
        )
    op_str = "\n".join(op_lines)
    rule_str = "- " + "\n- ".join(env_item["constraints_rules"])
    return _STEP2_TEMPLATE.format(
        env_introduction=env_item["environment_introduction"],
        env_state_definition=env_item["state_space_definition"],
        env_modify_operation=op_str,
        env_rule=rule_str,
        env_init_state=json.dumps(init_state, indent=2),
    )


def _parse_task(response: str) -> tuple[bool, str | None]:
    if "</think>" in response:
        response = response.split("</think>")[1]
    if "# Analysis" in response:
        response = response.split("# Analysis")[1]
        if "# Task" in response:
            task = response.split("# Task")[1].strip("\n* ")
            return True, task
    return False, None


def generate_tasks(n: int, out_path: Path) -> None:
    client = OpenAI(base_url=PROXY_BASE_URL, api_key="anything")
    init_state = _read_db_state(BASELINE_DB)
    prompt = _build_prompt(AIRLINE_ENV_ITEM, init_state)

    tasks = []
    task_attempts = 0
    max_task_attempts = n * 3

    print(f"Generating {n} EnvScaler tasks for airline environment...")
    print(f"  Model: {MODEL}  |  Baseline DB: {BASELINE_DB.name}")

    while len(tasks) < n and task_attempts < max_task_attempts:
        task_attempts += 1
        task = None
        for retry in range(3):
            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    max_tokens=1024,
                    temperature=0.7,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.choices[0].message.content or ""
                parsed_success, task = _parse_task(raw)
                if parsed_success:
                    break
                print(f"  [attempt {task_attempts}, retry {retry + 1}] parse failed...")
            except Exception as e:
                print(f"  [attempt {task_attempts}, retry {retry + 1}] error: {e}")

        if task:
            tasks.append({
                "task_id": f"envscaler_{len(tasks):03d}",
                "task": task,
                "generated_at": datetime.utcnow().isoformat(),
            })
            print(f"  [{len(tasks):2d}/{n}] OK — {task[:80]}...")
        else:
            print(f"  [attempt {task_attempts}] failed after 3 retries, skipping...")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(tasks, f, indent=2)

    print(f"\nSaved {len(tasks)} tasks → {out_path}")
    if len(tasks) < n:
        print(f"WARNING: only generated {len(tasks)}/{n} tasks after {task_attempts} attempts.")


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate EnvScaler-style tasks for the airline environment.")
    parser.add_argument("--n", type=int, default=30, help="Number of tasks to generate (default: 30)")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent / "envscaler_airline_tasks.json",
        help="Output JSON file path",
    )
    args = parser.parse_args()
    generate_tasks(args.n, args.out)
