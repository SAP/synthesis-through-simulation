"""
Orders API for Retail environment.
Manages orders, their items, fulfillments, and payment history.

Business rules enforced:
  - order_id must be unique and start with '#W'
  - user_id must reference a valid user
  - status must be a valid order status
  - cancel_reason required (and only allowed) on cancelled orders
  - exchange/return fields must all be present or all absent
  - payment transaction_type must be 'payment' or 'refund'

Auto-managed fields: created_at
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from synthesize.environments.retail.db.db import get_conn

VALID_STATUSES = [
    "pending",
    "pending (item modified)",
    "processed",
    "delivered",
    "cancelled",
    "exchange requested",
    "return requested",
]

CANCEL_REASONS = ["no longer needed", "ordered by mistake"]


def _order_row_to_dict(row) -> dict:
    d = dict(row)
    d["exchange_items"] = json.loads(d["exchange_items"]) if d["exchange_items"] else None
    d["exchange_new_items"] = json.loads(d["exchange_new_items"]) if d["exchange_new_items"] else None
    d["return_items"] = json.loads(d["return_items"]) if d["return_items"] else None
    return d


def _item_row_to_dict(row) -> dict:
    d = dict(row)
    d["options"] = json.loads(d["options"]) if d["options"] else {}
    return d


def _fulfillment_row_to_dict(row) -> dict:
    d = dict(row)
    d["tracking_ids"] = json.loads(d["tracking_ids"]) if d["tracking_ids"] else []
    d["item_ids"] = json.loads(d["item_ids"]) if d["item_ids"] else []
    return d


def _payment_row_to_dict(row) -> dict:
    return dict(row)


# ── Order Read Operations ─────────────────────────────────────────────────────


def get_order(order_id: str) -> Optional[Dict]:
    """Get order by ID."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    return _order_row_to_dict(row) if row else None


def get_order_details(order_id: str) -> Optional[Dict]:
    """Get order with items, fulfillments, and payment history."""
    order = get_order(order_id)
    if order is None:
        return None
    return {
        "order": order,
        "items": get_order_items(order_id),
        "fulfillments": get_order_fulfillments(order_id),
        "payment_history": get_payment_history(order_id),
    }


def list_orders(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """List orders with optional filters."""
    query = "SELECT * FROM orders WHERE 1=1"
    params: list = []

    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)
    if status is not None:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_order_row_to_dict(r) for r in rows]


def list_user_orders(user_id: str) -> List[Dict]:
    """List all orders for a user."""
    return list_orders(user_id=user_id)


# ── Order Write Operations ────────────────────────────────────────────────────


def create_order(
    order_id: str,
    user_id: str,
    address1: str,
    city: str,
    state: str,
    country: str,
    zip_code: str,
    address2: Optional[str] = None,
    status: str = "pending",
) -> Dict:
    """
    Create a new order.

    Business rules:
      - order_id must be unique and start with '#W' (e.g. '#W0000001')
      - user_id must reference a valid user
      - status defaults to 'pending'
    """
    if not order_id.startswith("#W"):
        raise ValueError(f"order_id must start with '#W', got '{order_id}'")
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}")

    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        ).fetchone():
            raise LookupError(f"User '{user_id}' not found")

        if conn.execute(
            "SELECT 1 FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone():
            raise ValueError(f"Order '{order_id}' already exists")

        conn.execute(
            """INSERT INTO orders (order_id, user_id, address1, address2, city, state, country, zip, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (order_id, user_id, address1, address2, city, state, country, zip_code, status),
        )
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    return _order_row_to_dict(row)


def update_order_status(
    order_id: str,
    status: str,
    cancel_reason: Optional[str] = None,
) -> Dict:
    """
    Update order status.

    Business rules:
      - status must be valid
      - cancel_reason required when status='cancelled'
      - cancel_reason must not be set for other statuses
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}")
    if status == "cancelled" and cancel_reason not in CANCEL_REASONS:
        raise ValueError(
            f"cancel_reason required for cancellation; must be one of {CANCEL_REASONS}"
        )
    if status != "cancelled" and cancel_reason is not None:
        raise ValueError("cancel_reason can only be set when status='cancelled'")

    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone():
            raise LookupError(f"Order '{order_id}' not found")

        updates: dict = {"status": status}
        if cancel_reason is not None:
            updates["cancel_reason"] = cancel_reason

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE orders SET {set_clause} WHERE order_id = ?",
            list(updates.values()) + [order_id],
        )
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    return _order_row_to_dict(row)


def update_order_address(
    order_id: str,
    address1: str,
    city: str,
    state: str,
    country: str,
    zip_code: str,
    address2: Optional[str] = None,
) -> Dict:
    """Update the shipping address on an order."""
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone():
            raise LookupError(f"Order '{order_id}' not found")

        conn.execute(
            """UPDATE orders SET address1=?, address2=?, city=?, state=?, country=?, zip=?
               WHERE order_id=?""",
            (address1, address2, city, state, country, zip_code, order_id),
        )
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    return _order_row_to_dict(row)


def set_exchange_details(
    order_id: str,
    exchange_items: List[str],
    exchange_new_items: List[str],
    exchange_payment_method_id: str,
    exchange_price_difference: float,
) -> Dict:
    """
    Record exchange details and set status to 'exchange requested'.

    Business rules:
      - All exchange fields must be provided together
    """
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone():
            raise LookupError(f"Order '{order_id}' not found")

        conn.execute(
            """UPDATE orders SET
                   exchange_items=?, exchange_new_items=?,
                   exchange_payment_method_id=?, exchange_price_difference=?,
                   status='exchange requested'
               WHERE order_id=?""",
            (
                json.dumps(sorted(exchange_items)),
                json.dumps(sorted(exchange_new_items)),
                exchange_payment_method_id,
                exchange_price_difference,
                order_id,
            ),
        )
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    return _order_row_to_dict(row)


def set_return_details(
    order_id: str,
    return_items: List[str],
    return_payment_method_id: str,
) -> Dict:
    """
    Record return details and set status to 'return requested'.

    Business rules:
      - Both return_items and return_payment_method_id must be provided
    """
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone():
            raise LookupError(f"Order '{order_id}' not found")

        conn.execute(
            """UPDATE orders SET
                   return_items=?, return_payment_method_id=?,
                   status='return requested'
               WHERE order_id=?""",
            (json.dumps(sorted(return_items)), return_payment_method_id, order_id),
        )
        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
    return _order_row_to_dict(row)


def delete_order(order_id: str) -> bool:
    """Delete an order and all related data (cascade)."""
    with get_conn() as conn:
        result = conn.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
        return result.rowcount > 0


# ── Order Items ───────────────────────────────────────────────────────────────


def get_order_items(order_id: str) -> List[Dict]:
    """Get all items in an order."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
        ).fetchall()
    return [_item_row_to_dict(r) for r in rows]


def add_order_item(
    order_id: str,
    product_id: str,
    item_id: str,
    name: str,
    price: float,
    options: Optional[Dict[str, str]] = None,
) -> Dict:
    """
    Add an item to an order.

    Business rules:
      - order must exist
      - price must be positive
    """
    if price <= 0:
        raise ValueError(f"Item price must be positive, got {price}")

    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone():
            raise LookupError(f"Order '{order_id}' not found")

        cursor = conn.execute(
            """INSERT INTO order_items (order_id, product_id, item_id, name, price, options)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (order_id, product_id, item_id, name, price, json.dumps(options or {})),
        )
        row = conn.execute(
            "SELECT * FROM order_items WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return _item_row_to_dict(row)


def update_order_item(
    item_record_id: int,
    item_id: Optional[str] = None,
    price: Optional[float] = None,
    options: Optional[Dict[str, str]] = None,
) -> Dict:
    """Update an order item (e.g., after variant modification)."""
    if price is not None and price <= 0:
        raise ValueError(f"Item price must be positive, got {price}")

    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM order_items WHERE id = ?", (item_record_id,)
        ).fetchone():
            raise LookupError(f"Order item {item_record_id} not found")

        updates: dict = {}
        if item_id is not None:
            updates["item_id"] = item_id
        if price is not None:
            updates["price"] = price
        if options is not None:
            updates["options"] = json.dumps(options)

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE order_items SET {set_clause} WHERE id = ?",
                list(updates.values()) + [item_record_id],
            )
        row = conn.execute(
            "SELECT * FROM order_items WHERE id = ?", (item_record_id,)
        ).fetchone()
    return _item_row_to_dict(row)


def delete_order_item(item_record_id: int) -> bool:
    """Delete an order item by its record ID."""
    with get_conn() as conn:
        result = conn.execute(
            "DELETE FROM order_items WHERE id = ?", (item_record_id,)
        )
        return result.rowcount > 0


# ── Order Fulfillments ────────────────────────────────────────────────────────


def get_order_fulfillments(order_id: str) -> List[Dict]:
    """Get all fulfillments for an order."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM order_fulfillments WHERE order_id = ?", (order_id,)
        ).fetchall()
    return [_fulfillment_row_to_dict(r) for r in rows]


def add_order_fulfillment(
    order_id: str,
    tracking_ids: List[str],
    item_ids: List[str],
) -> Dict:
    """Add a fulfillment/shipment record to an order."""
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone():
            raise LookupError(f"Order '{order_id}' not found")

        cursor = conn.execute(
            "INSERT INTO order_fulfillments (order_id, tracking_ids, item_ids) VALUES (?, ?, ?)",
            (order_id, json.dumps(tracking_ids), json.dumps(item_ids)),
        )
        row = conn.execute(
            "SELECT * FROM order_fulfillments WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return _fulfillment_row_to_dict(row)


# ── Payment History ───────────────────────────────────────────────────────────


def get_payment_history(order_id: str) -> List[Dict]:
    """Get payment history for an order (oldest first)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM payment_history WHERE order_id = ? ORDER BY created_at ASC",
            (order_id,),
        ).fetchall()
    return [_payment_row_to_dict(r) for r in rows]


def add_payment_record(
    order_id: str,
    transaction_type: str,
    amount: float,
    payment_method_id: str,
) -> Dict:
    """
    Add a payment or refund record to an order.

    Business rules:
      - transaction_type must be 'payment' or 'refund'
      - amount must be positive
      - order must exist
    """
    if transaction_type not in ("payment", "refund"):
        raise ValueError(
            f"Invalid transaction_type '{transaction_type}'. Must be 'payment' or 'refund'"
        )
    if amount <= 0:
        raise ValueError(f"Payment amount must be positive, got {amount}")

    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone():
            raise LookupError(f"Order '{order_id}' not found")

        cursor = conn.execute(
            """INSERT INTO payment_history (order_id, transaction_type, amount, payment_method_id)
               VALUES (?, ?, ?, ?)""",
            (order_id, transaction_type, amount, payment_method_id),
        )
        row = conn.execute(
            "SELECT * FROM payment_history WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return _payment_row_to_dict(row)
