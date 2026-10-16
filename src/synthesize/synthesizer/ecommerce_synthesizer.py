"""
E-commerce synthesizers.

EcommerceAgentSynthesizer — LLM agent executes e-commerce order intents via Ecommerce APIs.

Auto-discovered by synthesis_runner.py since it subclasses DefaultAgentSynthesizer
and lives in synthesize/synthesizer/.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from synthesize.environments.ecommerce.apis.orders import (
    add_order_item,
    cancel_order,
    confirm_order,
    create_order,
    list_customers,
    list_order_items,
    list_orders,
    list_orders_for_customer,
    update_shipping_address,
)
from synthesize.environments.ecommerce.apis.products import (
    list_products,
    restock_product,
)
from synthesize.environments.ecommerce.db.db import get_conn
from synthesize.synthesizer.agent_synthesizer import IntentDef, Step
from synthesize.synthesizer.default_agent import DefaultAgentSynthesizer
from synthesize.synthesizer.generalist_synthesizer import GeneralistSynthesizer

# ── Tool registry ─────────────────────────────────────────────────────────────

ECOMMERCE_TOOL_REGISTRY: Dict[str, dict] = {
    "list_customers": {
        "fn": list_customers,
        "description": "List customers, optionally filtered by active status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "is_active": {"type": "boolean", "description": "Filter by active status"},
            },
            "required": [],
        },
    },
    "list_products": {
        "fn": list_products,
        "description": "List products with optional filters for category, stock, and active status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filter by category"},
                "in_stock": {"type": "boolean", "description": "Only in-stock products"},
                "is_active": {"type": "boolean", "description": "Only active products"},
            },
            "required": [],
        },
    },
    "list_orders": {
        "fn": list_orders,
        "description": "List all orders, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status"},
            },
            "required": [],
        },
    },
    "list_order_items": {
        "fn": list_order_items,
        "description": "List all items in an order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
            },
            "required": ["order_id"],
        },
    },
    "list_orders_for_customer": {
        "fn": list_orders_for_customer,
        "description": "List orders for a customer, newest first. Optional status filter.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "status": {"type": "string", "description": "Optional status filter"},
            },
            "required": ["customer_id"],
        },
    },
    "create_order": {
        "fn": create_order,
        "description": (
            "Create an empty pending order for an active customer. "
            "shipping_address must be non-empty."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "shipping_address": {"type": "string"},
            },
            "required": ["customer_id", "shipping_address"],
        },
    },
    "add_order_item": {
        "fn": add_order_item,
        "description": (
            "Add a product to a pending order. "
            "Stock is decremented only on confirmation, not here."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "product_id": {"type": "string"},
                "quantity": {"type": "integer", "description": "Must be positive"},
            },
            "required": ["order_id", "product_id", "quantity"],
        },
    },
    "confirm_order": {
        "fn": confirm_order,
        "description": (
            "Confirm a pending order. Decrements stock for each item. "
            "Order must have at least one item and all products must have sufficient stock."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
            },
            "required": ["order_id"],
        },
    },
    "cancel_order": {
        "fn": cancel_order,
        "description": (
            "Cancel a pending or confirmed order. "
            "Restores stock if the order was already confirmed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
            },
            "required": ["order_id"],
        },
    },
    "update_shipping_address": {
        "fn": update_shipping_address,
        "description": "Update the shipping address on a pending order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "shipping_address": {"type": "string", "description": "New shipping address"},
            },
            "required": ["order_id", "shipping_address"],
        },
    },
    "restock_product": {
        "fn": restock_product,
        "description": "Increase a product's stock quantity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "quantity": {"type": "integer", "description": "Units to add (must be positive)"},
            },
            "required": ["product_id", "quantity"],
        },
    },
}

# Generic alias required by GeneralistPopulatorSynthesizer
TOOL_REGISTRY = ECOMMERCE_TOOL_REGISTRY

# ── Samplers ──────────────────────────────────────────────────────────────────


def _sample_place_order() -> Optional[dict]:
    """Sample an active customer with available in-stock products."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT customer_id FROM customer WHERE is_active = 1 ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {"customer_id": row["customer_id"]}


def _sample_cancel_order() -> Optional[dict]:
    """Sample a pending or confirmed order for cancellation."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT o.order_id, o.customer_id FROM shop_order o
            WHERE o.status IN ('pending', 'confirmed')
            ORDER BY RANDOM() LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return {"order_id": row["order_id"], "customer_id": row["customer_id"]}


def _sample_update_shipping() -> Optional[dict]:
    """Sample a pending order to update shipping address."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT order_id, customer_id FROM shop_order WHERE status = 'pending' ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {"order_id": row["order_id"], "customer_id": row["customer_id"]}


def _sample_restock_product() -> Optional[dict]:
    """Sample a product with low stock (stock_qty < 10)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT product_id, name, stock_qty FROM product WHERE is_active = 1 AND stock_qty < 10 ORDER BY stock_qty ASC LIMIT 1"
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT product_id, name, stock_qty FROM product WHERE is_active = 1 ORDER BY RANDOM() LIMIT 1"
            ).fetchone()
    if row is None:
        return None
    return {"product_id": row["product_id"], "name": row["name"], "stock_qty": row["stock_qty"]}


# ── Postconditions ────────────────────────────────────────────────────────────


def _postcond_place_order(params: dict, steps: List[Step]) -> Dict[str, bool]:
    order_id = None
    for step in steps:
        if step.tool == "confirm_order" and not step.is_error:
            result = step.result
            if isinstance(result, dict):
                order_id = result.get("order_id")
            break
    if not order_id:
        # Try create_order
        for step in steps:
            if step.tool == "create_order" and not step.is_error:
                result = step.result
                if isinstance(result, dict):
                    order_id = result.get("order_id")
                break

    if not order_id:
        return {"order_confirmed": False, "items_added": False}

    with get_conn() as conn:
        order = conn.execute(
            "SELECT status FROM shop_order WHERE order_id = ?", (order_id,)
        ).fetchone()
        item_count = conn.execute(
            "SELECT COUNT(*) FROM order_item WHERE order_id = ?", (order_id,)
        ).fetchone()[0]

    return {
        "order_confirmed": order is not None and order["status"] == "confirmed",
        "items_added": item_count > 0,
    }


def _postcond_cancel_order(params: dict, steps: List[Step]) -> Dict[str, bool]:
    order_id = params.get("order_id")
    if not order_id:
        for step in steps:
            if step.tool == "cancel_order" and not step.is_error:
                result = step.result
                if isinstance(result, dict):
                    order_id = result.get("order_id")
                break
    if not order_id:
        return {"order_cancelled": False}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM shop_order WHERE order_id = ?", (order_id,)
        ).fetchone()

    return {"order_cancelled": row is not None and row["status"] == "cancelled"}


def _postcond_update_shipping(params: dict, steps: List[Step]) -> Dict[str, bool]:
    for step in steps:
        if step.tool == "update_shipping_address" and not step.is_error:
            return {"address_updated": True}
    return {"address_updated": False}


def _postcond_restock_product(params: dict, steps: List[Step]) -> Dict[str, bool]:
    for step in steps:
        if step.tool == "restock_product" and not step.is_error:
            return {"stock_increased": True}
    return {"stock_increased": False}


# ── Intent definitions ────────────────────────────────────────────────────────

ECOMMERCE_INTENTS: Dict[str, IntentDef] = {
    "PLACE_ORDER": IntentDef(
        name="PLACE_ORDER",
        brief="Create and confirm an order for a customer: add 1–3 products and confirm.",
        informed_rules="""\
E-commerce Order Rules:
- customer must be active (is_active=true)
- shipping_address must be non-empty
- Items can only be added to pending orders
- Product must be active and have sufficient stock_qty for the requested quantity
- confirm_order decrements stock; cancel restores it
- Only pending or confirmed orders can be cancelled
""",
        tools=[
            "list_customers",
            "list_products",
            "create_order",
            "add_order_item",
            "confirm_order",
        ],
        sampler=_sample_place_order,
        task_prompt=lambda p: (
            f"Create and confirm an order for customer '{p['customer_id']}'. "
            "Browse available in-stock products, create the order, add 1–3 products, then confirm it."
        ),
        postconditions=_postcond_place_order,
    ),
    "CANCEL_ORDER": IntentDef(
        name="CANCEL_ORDER",
        brief="Cancel a pending or confirmed order.",
        informed_rules="""\
E-commerce Cancellation Rules:
- Only pending or confirmed orders can be cancelled (not shipped or delivered)
- Cancelling a confirmed order restores stock
""",
        tools=[
            "list_orders_for_customer",
            "cancel_order",
        ],
        sampler=_sample_cancel_order,
        task_prompt=lambda p: (
            f"Cancel order '{p['order_id']}' for customer '{p['customer_id']}'."
        ),
        postconditions=_postcond_cancel_order,
    ),
    "UPDATE_SHIPPING": IntentDef(
        name="UPDATE_SHIPPING",
        brief="Update the shipping address on a pending order.",
        informed_rules="""\
E-commerce Shipping Update Rules:
- Only pending orders can have their shipping address updated
- shipping_address must be non-empty
""",
        tools=[
            "list_orders_for_customer",
            "update_shipping_address",
        ],
        sampler=_sample_update_shipping,
        task_prompt=lambda p: (
            f"Update the shipping address on order '{p['order_id']}' "
            f"for customer '{p['customer_id']}'. Provide a new valid address."
        ),
        postconditions=_postcond_update_shipping,
    ),
    "RESTOCK_PRODUCT": IntentDef(
        name="RESTOCK_PRODUCT",
        brief="Restock a product with low inventory.",
        informed_rules="""\
E-commerce Restock Rules:
- quantity must be positive
- Product must exist and be active
- Stock quantity is incremented by the given amount
""",
        tools=[
            "list_products",
            "restock_product",
        ],
        sampler=_sample_restock_product,
        task_prompt=lambda p: (
            f"Restock product '{p['product_id']}' ({p['name']}, current stock: {p['stock_qty']}). "
            "Add a sufficient number of units."
        ),
        postconditions=_postcond_restock_product,
    ),
}

# ── Synthesizer classes ───────────────────────────────────────────────────────


class EcommerceAgentSynthesizer(DefaultAgentSynthesizer):
    def __init__(self) -> None:
        super().__init__(
            name="ecommerce_agent",
            description="LLM agent executes e-commerce order intents via Ecommerce APIs",
            tool_registry=ECOMMERCE_TOOL_REGISTRY,
            intents=ECOMMERCE_INTENTS,
            env_name="E-commerce",
        )


class EcommerceGeneralistSynthesizer(GeneralistSynthesizer):
    INTENT_TO_WRITE_TOOLS = {
        "PLACE_ORDER": {"create_order", "add_order_item", "confirm_order"},
        "CANCEL_ORDER": {"cancel_order"},
        "UPDATE_SHIPPING": {"update_shipping_address"},
        "RESTOCK_PRODUCT": {"restock_product"},
    }

    def __init__(self) -> None:
        super().__init__(
            name="ecommerce_generalist",
            description=(
                "Goal-directed agent that observes DB state, selects an appropriate intent "
                "from the bootstrap library, and executes it — no pre-assigned task."
            ),
            tool_registry=ECOMMERCE_TOOL_REGISTRY,
            bootstrap_intents=ECOMMERCE_INTENTS,
            env_name="E-commerce",
        )

    def _init_evolution(self) -> None:
        from pathlib import Path

        from synthesize.evolution.analyzer import TrajectoryAnalyzer
        from synthesize.evolution.engine import EvolutionEngine
        from synthesize.evolution.models import EvolvedIntent, IntentLibrary
        from synthesize.evolution.store import TrajectoryStore
        from synthesize.synthesizer.agent_synthesizer import MODEL, PROXY_BASE_URL

        runs_root = Path(".runs") / "evolution" / "ecommerce"
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
            for name, intent_def in ECOMMERCE_INTENTS.items():
                library.add_intent(EvolvedIntent.from_intent_def(intent_def))

        self.evolution_engine = engine
        self.intent_library = library
        self.library_path = library_path
