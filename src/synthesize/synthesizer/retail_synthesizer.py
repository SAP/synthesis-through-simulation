"""
Retail synthesizers.

RetailAgentSynthesizer — LLM agent executes retail order intents via Retail APIs.

Auto-discovered by synthesis_runner.py since it subclasses DefaultAgentSynthesizer
and lives in synthesize/synthesizer/.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from synthesize.environments.retail.apis import orders as orders_api
from synthesize.environments.retail.apis import payment_methods as pm_api
from synthesize.environments.retail.apis import products as products_api
from synthesize.environments.retail.apis import users as users_api
from synthesize.environments.retail.db.db import get_conn
from synthesize.synthesizer.agent_synthesizer import IntentDef, Step
from synthesize.synthesizer.default_agent import DefaultAgentSynthesizer
from synthesize.synthesizer.generalist_synthesizer import GeneralistSynthesizer

# ── Tool registry ─────────────────────────────────────────────────────────────

RETAIL_TOOL_REGISTRY: Dict[str, dict] = {
    "list_users": {
        "fn": users_api.list_users,
        "description": "List all users with pagination.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results (default 50)"},
                "offset": {"type": "integer", "description": "Pagination offset"},
            },
            "required": [],
        },
    },
    "list_products": {
        "fn": products_api.list_products,
        "description": "List all products.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results (default 50)"},
                "offset": {"type": "integer", "description": "Pagination offset"},
            },
            "required": [],
        },
    },
    "list_variants": {
        "fn": products_api.list_variants,
        "description": "List product variants, optionally filtered by product_id or availability.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Filter by product"},
                "available_only": {"type": "boolean", "description": "Only available variants"},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
            },
            "required": [],
        },
    },
    "list_orders": {
        "fn": orders_api.list_orders,
        "description": "List orders with optional user_id and status filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Filter by user"},
                "status": {"type": "string", "description": "Filter by status"},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
            },
            "required": [],
        },
    },
    "list_user_orders": {
        "fn": orders_api.list_user_orders,
        "description": "List all orders for a user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User ID"},
            },
            "required": ["user_id"],
        },
    },
    "get_order_details": {
        "fn": orders_api.get_order_details,
        "description": "Get full order details: items, fulfillments, and payment history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID, e.g. '#W0000001'"},
            },
            "required": ["order_id"],
        },
    },
    "list_payment_methods": {
        "fn": pm_api.list_payment_methods,
        "description": "List payment methods with optional user_id and source filters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Filter by user"},
                "source": {"type": "string", "description": "Filter by source (credit_card, paypal, gift_card)"},
            },
            "required": [],
        },
    },
    "list_user_payment_methods": {
        "fn": pm_api.list_user_payment_methods,
        "description": "List all payment methods for a user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User ID"},
            },
            "required": ["user_id"],
        },
    },
    "create_order": {
        "fn": orders_api.create_order,
        "description": (
            "Create a new order. order_id must start with '#W'. "
            "Address fields are required."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID starting with '#W', e.g. '#W0000001'"},
                "user_id": {"type": "string", "description": "User ID"},
                "address1": {"type": "string"},
                "city": {"type": "string"},
                "state": {"type": "string"},
                "country": {"type": "string"},
                "zip_code": {"type": "string"},
                "address2": {"type": "string", "description": "Optional second address line"},
                "status": {"type": "string", "description": "Initial status (default: pending)"},
            },
            "required": ["order_id", "user_id", "address1", "city", "state", "country", "zip_code"],
        },
    },
    "add_order_item": {
        "fn": orders_api.add_order_item,
        "description": "Add an item to an existing order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "product_id": {"type": "string"},
                "item_id": {"type": "string", "description": "Variant item_id"},
                "name": {"type": "string", "description": "Product name"},
                "price": {"type": "number", "description": "Item price (must be positive)"},
                "options": {"type": "object", "description": "Optional variant options dict"},
            },
            "required": ["order_id", "product_id", "item_id", "name", "price"],
        },
    },
    "add_payment_record": {
        "fn": orders_api.add_payment_record,
        "description": (
            "Add a payment or refund record to an order. "
            "transaction_type must be 'payment' or 'refund'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "transaction_type": {
                    "type": "string",
                    "enum": ["payment", "refund"],
                },
                "amount": {"type": "number", "description": "Amount (must be positive)"},
                "payment_method_id": {"type": "string", "description": "Payment method ID"},
            },
            "required": ["order_id", "transaction_type", "amount", "payment_method_id"],
        },
    },
    "update_order_status": {
        "fn": orders_api.update_order_status,
        "description": (
            "Update order status. When cancelling, cancel_reason is required "
            "(one of: 'no longer needed', 'ordered by mistake')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": [
                        "pending",
                        "pending (item modified)",
                        "processed",
                        "delivered",
                        "cancelled",
                        "exchange requested",
                        "return requested",
                    ],
                },
                "cancel_reason": {
                    "type": "string",
                    "enum": ["no longer needed", "ordered by mistake"],
                    "description": "Required when status='cancelled'",
                },
            },
            "required": ["order_id", "status"],
        },
    },
    "set_return_details": {
        "fn": orders_api.set_return_details,
        "description": "Record return details and set order status to 'return requested'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "return_items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of item_ids being returned",
                },
                "return_payment_method_id": {"type": "string", "description": "Refund payment method"},
            },
            "required": ["order_id", "return_items", "return_payment_method_id"],
        },
    },
    "set_exchange_details": {
        "fn": orders_api.set_exchange_details,
        "description": "Record exchange details and set order status to 'exchange requested'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "exchange_items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "item_ids being exchanged",
                },
                "exchange_new_items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New item_ids to replace them",
                },
                "exchange_payment_method_id": {"type": "string"},
                "exchange_price_difference": {"type": "number"},
            },
            "required": [
                "order_id",
                "exchange_items",
                "exchange_new_items",
                "exchange_payment_method_id",
                "exchange_price_difference",
            ],
        },
    },
}

# Generic alias required by GeneralistPopulatorSynthesizer
TOOL_REGISTRY = RETAIL_TOOL_REGISTRY

# ── Samplers ──────────────────────────────────────────────────────────────────


def _sample_place_order() -> Optional[dict]:
    """Sample a user with a payment method for placing a new order."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT u.user_id, u.address1, u.city, u.state, u.country, u.zip
            FROM users u
            WHERE EXISTS (
                SELECT 1 FROM payment_methods pm WHERE pm.user_id = u.user_id LIMIT 1
            )
            ORDER BY RANDOM() LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return {"user_id": row["user_id"]}


def _sample_cancel_order() -> Optional[dict]:
    """Sample a pending or processed order that can be cancelled."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT order_id, user_id FROM orders
            WHERE status IN ('pending', 'pending (item modified)', 'processed')
            ORDER BY RANDOM() LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return {"order_id": row["order_id"], "user_id": row["user_id"]}


def _sample_request_return() -> Optional[dict]:
    """Sample a delivered order for a return request."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT o.order_id, o.user_id
            FROM orders o
            WHERE o.status = 'delivered'
              AND EXISTS (
                  SELECT 1 FROM order_items oi WHERE oi.order_id = o.order_id
              )
            ORDER BY RANDOM() LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return {"order_id": row["order_id"], "user_id": row["user_id"]}


def _sample_request_exchange() -> Optional[dict]:
    """Sample a delivered order for an exchange request."""
    return _sample_request_return()


# ── Postconditions ────────────────────────────────────────────────────────────


def _postcond_place_order(params: dict, steps: List[Step]) -> Dict[str, bool]:
    order_id = None
    for step in steps:
        if step.tool == "create_order" and not step.is_error:
            result = step.result
            if isinstance(result, dict):
                order_id = result.get("order_id")
            break
    if not order_id:
        return {"order_created": False, "item_added": False, "payment_recorded": False}

    with get_conn() as conn:
        order = conn.execute(
            "SELECT order_id FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        item_count = conn.execute(
            "SELECT COUNT(*) FROM order_items WHERE order_id = ?", (order_id,)
        ).fetchone()[0]
        payment_count = conn.execute(
            "SELECT COUNT(*) FROM payment_history WHERE order_id = ?", (order_id,)
        ).fetchone()[0]

    return {
        "order_created": order is not None,
        "item_added": item_count > 0,
        "payment_recorded": payment_count > 0,
    }


def _postcond_cancel_order(params: dict, steps: List[Step]) -> Dict[str, bool]:
    order_id = params.get("order_id")
    if not order_id:
        for step in steps:
            if step.tool == "update_order_status" and not step.is_error:
                result = step.result
                if isinstance(result, dict):
                    order_id = result.get("order_id")
                break
    if not order_id:
        return {"status_is_cancelled": False}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()

    return {"status_is_cancelled": row is not None and row["status"] == "cancelled"}


def _postcond_request_return(params: dict, steps: List[Step]) -> Dict[str, bool]:
    order_id = params.get("order_id")
    if not order_id:
        for step in steps:
            if step.tool == "set_return_details" and not step.is_error:
                result = step.result
                if isinstance(result, dict):
                    order_id = result.get("order_id")
                break
    if not order_id:
        return {"return_requested_set": False}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()

    return {"return_requested_set": row is not None and row["status"] == "return requested"}


def _postcond_request_exchange(params: dict, steps: List[Step]) -> Dict[str, bool]:
    order_id = params.get("order_id")
    if not order_id:
        for step in steps:
            if step.tool == "set_exchange_details" and not step.is_error:
                result = step.result
                if isinstance(result, dict):
                    order_id = result.get("order_id")
                break
    if not order_id:
        return {"exchange_requested_set": False}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()

    return {"exchange_requested_set": row is not None and row["status"] == "exchange requested"}


# ── Intent definitions ────────────────────────────────────────────────────────

RETAIL_INTENTS: Dict[str, IntentDef] = {
    "PLACE_ORDER": IntentDef(
        name="PLACE_ORDER",
        brief="Place a new order for a user: create order, add 1–2 items, and record payment.",
        informed_rules="""\
Retail Order Business Rules:
- order_id must be unique and start with '#W' (e.g. '#W0000001')
- user_id must reference a valid user
- Use the user's saved address for the shipping address
- Add at least one item from available variants (available=true)
- Record a payment using one of the user's payment methods
- item price must be positive; match the variant's actual price
- payment transaction_type must be 'payment' for new orders
- Vary cabin, item count, and payment method across runs
""",
        tools=[
            "list_users",
            "list_products",
            "list_variants",
            "list_user_payment_methods",
            "create_order",
            "add_order_item",
            "add_payment_record",
        ],
        sampler=_sample_place_order,
        task_prompt=lambda p: (
            f"Place a new order for user '{p['user_id']}'. "
            "Look up the user's address and payment methods, browse available products and variants, "
            "create an order, add 1–2 items, and record a payment."
        ),
        postconditions=_postcond_place_order,
    ),
    "CANCEL_ORDER": IntentDef(
        name="CANCEL_ORDER",
        brief="Cancel a pending or processed order.",
        informed_rules="""\
Retail Order Cancellation Rules:
- Only pending, pending (item modified), or processed orders can be cancelled
- cancel_reason is required and must be one of: 'no longer needed', 'ordered by mistake'
- Status must be set to 'cancelled'
""",
        tools=[
            "list_user_orders",
            "get_order_details",
            "update_order_status",
        ],
        sampler=_sample_cancel_order,
        task_prompt=lambda p: (
            f"Cancel order '{p['order_id']}' for user '{p['user_id']}'. "
            "Check the order details, then cancel it with an appropriate reason."
        ),
        postconditions=_postcond_cancel_order,
    ),
    "REQUEST_RETURN": IntentDef(
        name="REQUEST_RETURN",
        brief="Submit a return request for a delivered order.",
        informed_rules="""\
Retail Return Rules:
- Only delivered orders can have a return requested
- Must provide return_items (list of item_ids) and a return_payment_method_id
- Sets order status to 'return requested'
""",
        tools=[
            "list_user_orders",
            "get_order_details",
            "list_user_payment_methods",
            "set_return_details",
        ],
        sampler=_sample_request_return,
        task_prompt=lambda p: (
            f"Submit a return request for order '{p['order_id']}' (user '{p['user_id']}'). "
            "Look up the order items and pick a payment method for the refund."
        ),
        postconditions=_postcond_request_return,
    ),
    "REQUEST_EXCHANGE": IntentDef(
        name="REQUEST_EXCHANGE",
        brief="Submit an exchange request for a delivered order.",
        informed_rules="""\
Retail Exchange Rules:
- Only delivered orders can have an exchange requested
- Must provide exchange_items, exchange_new_items, exchange_payment_method_id, and exchange_price_difference
- exchange_new_items must be available variants different from the originals
- Sets order status to 'exchange requested'
""",
        tools=[
            "list_user_orders",
            "get_order_details",
            "list_products",
            "list_variants",
            "list_user_payment_methods",
            "set_exchange_details",
        ],
        sampler=_sample_request_exchange,
        task_prompt=lambda p: (
            f"Submit an exchange request for order '{p['order_id']}' (user '{p['user_id']}'). "
            "Look up the order items and choose different variants to swap them for."
        ),
        postconditions=_postcond_request_exchange,
    ),
}

# ── Synthesizer classes ───────────────────────────────────────────────────────


class RetailAgentSynthesizer(DefaultAgentSynthesizer):
    def __init__(self) -> None:
        super().__init__(
            name="retail_agent",
            description="LLM agent executes retail order intents via Retail APIs",
            tool_registry=RETAIL_TOOL_REGISTRY,
            intents=RETAIL_INTENTS,
            env_name="Retail",
        )


class RetailGeneralistSynthesizer(GeneralistSynthesizer):
    INTENT_TO_WRITE_TOOLS = {
        "PLACE_ORDER": {"create_order", "add_order_item", "add_payment_record"},
        "CANCEL_ORDER": {"update_order_status"},
        "REQUEST_RETURN": {"set_return_details"},
        "REQUEST_EXCHANGE": {"set_exchange_details"},
    }

    def __init__(self) -> None:
        super().__init__(
            name="retail_generalist",
            description=(
                "Goal-directed agent that observes DB state, selects an appropriate intent "
                "from the bootstrap library, and executes it — no pre-assigned task."
            ),
            tool_registry=RETAIL_TOOL_REGISTRY,
            bootstrap_intents=RETAIL_INTENTS,
            env_name="Retail",
        )

    def _init_evolution(self) -> None:
        from pathlib import Path

        from synthesize.evolution.analyzer import TrajectoryAnalyzer
        from synthesize.evolution.engine import EvolutionEngine
        from synthesize.evolution.models import EvolvedIntent, IntentLibrary
        from synthesize.evolution.store import TrajectoryStore
        from synthesize.synthesizer.agent_synthesizer import MODEL, PROXY_BASE_URL

        runs_root = Path(".runs") / "evolution" / "retail"
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
            for name, intent_def in RETAIL_INTENTS.items():
                library.add_intent(EvolvedIntent.from_intent_def(intent_def))

        self.evolution_engine = engine
        self.intent_library = library
        self.library_path = library_path
