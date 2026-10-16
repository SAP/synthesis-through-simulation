"""
Order management API for the E-commerce environment.

Business rules enforced:
  - Order status machine: pending → confirmed → shipped → delivered
                                         ↓ (from pending/confirmed)
                                       cancelled
  - Adding items is only allowed on pending orders
  - Cancelling is only allowed on pending or confirmed orders
  - total_amount = sum(quantity × unit_price) across all order items; kept in sync
  - Stock is decremented when an order is confirmed; restored on cancellation
  - Order items must reference active products with sufficient stock
  - quantity must be positive; unit_price must be positive

Auto-managed fields: status, total_amount, updated_date
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional

from synthesize.environments.ecommerce.db.db import get_conn


def _today() -> str:
    return datetime.date.today().isoformat()


def _oid() -> str:
    return "ORD-" + str(uuid.uuid4())[:8].upper()


def _iid() -> str:
    return "ITEM-" + str(uuid.uuid4())[:6].upper()


def _recalc_total(conn, order_id: str) -> float:
    total = conn.execute(
        "SELECT COALESCE(SUM(quantity * unit_price), 0) FROM order_item WHERE order_id = ?",
        (order_id,),
    ).fetchone()[0]
    conn.execute(
        "UPDATE shop_order SET total_amount = ?, updated_date = ? WHERE order_id = ?",
        (total, _today(), order_id),
    )
    return total


# ── Customer read ─────────────────────────────────────────────────────────────


def get_customer(customer_id: str) -> Dict[str, Any]:
    """Return a customer record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM customer WHERE customer_id = ?", (customer_id,)).fetchone()
    if row is None:
        raise LookupError(f"Customer not found: {customer_id!r}")
    return dict(row)


def list_customers(is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
    """Return customers, optionally filtered by active status."""
    query = "SELECT * FROM customer WHERE 1=1"
    params: list = []
    if is_active is not None:
        query += " AND is_active = ?"
        params.append(1 if is_active else 0)
    query += " ORDER BY customer_id"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ── Order read ────────────────────────────────────────────────────────────────


def get_order(order_id: str) -> Dict[str, Any]:
    """Return an order record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM shop_order WHERE order_id = ?", (order_id,)).fetchone()
    if row is None:
        raise LookupError(f"Order not found: {order_id!r}")
    return dict(row)


def list_order_items(order_id: str) -> List[Dict[str, Any]]:
    """Return all items in an order."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM order_item WHERE order_id = ? ORDER BY order_item_id",
            (order_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_orders_for_customer(customer_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return orders for a customer, newest first."""
    query = "SELECT * FROM shop_order WHERE customer_id = ?"
    params: list = [customer_id]
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_date DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def list_orders(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all orders, optionally filtered by status."""
    query = "SELECT * FROM shop_order WHERE 1=1"
    params: list = []
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_date DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ── Order write ───────────────────────────────────────────────────────────────


def create_order(customer_id: str, shipping_address: str) -> Dict[str, Any]:
    """Create an empty pending order for a customer.

    Raises LookupError if customer not found.
    Raises ValueError if customer is inactive or shipping_address is empty.
    """
    if not shipping_address or not shipping_address.strip():
        raise ValueError("shipping_address must be non-empty")

    with get_conn() as conn:
        cust = conn.execute(
            "SELECT is_active FROM customer WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        if cust is None:
            raise LookupError(f"Customer not found: {customer_id!r}")
        if not cust["is_active"]:
            raise ValueError(f"Customer {customer_id!r} is not active")

        today = _today()
        order_id = _oid()
        conn.execute(
            """INSERT INTO shop_order
               (order_id, customer_id, status, total_amount, shipping_address, created_date, updated_date)
               VALUES (?, ?, 'pending', 0.0, ?, ?, ?)""",
            (order_id, customer_id, shipping_address.strip(), today, today),
        )
    return get_order(order_id)


def add_order_item(
    order_id: str, product_id: str, quantity: int
) -> Dict[str, Any]:
    """Add a product to a pending order.

    Stock is NOT decremented here — only on confirmation.

    Raises LookupError if order or product not found.
    Raises ValueError if order is not pending, quantity ≤ 0, or product is inactive.
    """
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")

    with get_conn() as conn:
        order = conn.execute("SELECT status FROM shop_order WHERE order_id = ?", (order_id,)).fetchone()
        if order is None:
            raise LookupError(f"Order not found: {order_id!r}")
        if order["status"] != "pending":
            raise ValueError(f"Cannot add items to {order['status']!r} order {order_id!r}")

        prod = conn.execute("SELECT * FROM product WHERE product_id = ?", (product_id,)).fetchone()
        if prod is None:
            raise LookupError(f"Product not found: {product_id!r}")
        if not prod["is_active"]:
            raise ValueError(f"Product {product_id!r} is not active")

        existing = conn.execute(
            "SELECT order_item_id, quantity FROM order_item WHERE order_id = ? AND product_id = ?",
            (order_id, product_id),
        ).fetchone()
        if existing:
            new_qty = existing["quantity"] + quantity
            conn.execute(
                "UPDATE order_item SET quantity = ? WHERE order_item_id = ?",
                (new_qty, existing["order_item_id"]),
            )
        else:
            conn.execute(
                """INSERT INTO order_item (order_item_id, order_id, product_id, quantity, unit_price)
                   VALUES (?, ?, ?, ?, ?)""",
                (_iid(), order_id, product_id, quantity, prod["price"]),
            )
        _recalc_total(conn, order_id)
    return get_order(order_id)


def remove_order_item(order_id: str, product_id: str) -> Dict[str, Any]:
    """Remove a product from a pending order.

    Raises LookupError if order or item not found.
    Raises ValueError if order is not pending.
    """
    with get_conn() as conn:
        order = conn.execute("SELECT status FROM shop_order WHERE order_id = ?", (order_id,)).fetchone()
        if order is None:
            raise LookupError(f"Order not found: {order_id!r}")
        if order["status"] != "pending":
            raise ValueError(f"Cannot remove items from {order['status']!r} order {order_id!r}")

        item = conn.execute(
            "SELECT order_item_id FROM order_item WHERE order_id = ? AND product_id = ?",
            (order_id, product_id),
        ).fetchone()
        if item is None:
            raise LookupError(f"Product {product_id!r} not in order {order_id!r}")

        conn.execute("DELETE FROM order_item WHERE order_item_id = ?", (item["order_item_id"],))
        _recalc_total(conn, order_id)
    return get_order(order_id)


def confirm_order(order_id: str) -> Dict[str, Any]:
    """Confirm a pending order and decrement stock for each item.

    Raises LookupError if order not found.
    Raises ValueError if order is not pending, has no items, or any product is out of stock.
    """
    with get_conn() as conn:
        order = conn.execute("SELECT status FROM shop_order WHERE order_id = ?", (order_id,)).fetchone()
        if order is None:
            raise LookupError(f"Order not found: {order_id!r}")
        if order["status"] != "pending":
            raise ValueError(f"Cannot confirm {order['status']!r} order {order_id!r}")

        items = conn.execute(
            "SELECT oi.*, p.stock_qty, p.name FROM order_item oi "
            "JOIN product p ON oi.product_id = p.product_id WHERE oi.order_id = ?",
            (order_id,),
        ).fetchall()
        if not items:
            raise ValueError(f"Cannot confirm order {order_id!r}: no items")

        for item in items:
            if item["stock_qty"] < item["quantity"]:
                raise ValueError(
                    f"Insufficient stock for {item['name']!r}: "
                    f"need {item['quantity']}, have {item['stock_qty']}"
                )

        for item in items:
            conn.execute(
                "UPDATE product SET stock_qty = stock_qty - ? WHERE product_id = ?",
                (item["quantity"], item["product_id"]),
            )
        conn.execute(
            "UPDATE shop_order SET status = 'confirmed', updated_date = ? WHERE order_id = ?",
            (_today(), order_id),
        )
    return get_order(order_id)


def ship_order(order_id: str) -> Dict[str, Any]:
    """Mark a confirmed order as shipped.

    Raises LookupError if not found.
    Raises ValueError if order is not confirmed.
    """
    with get_conn() as conn:
        order = conn.execute("SELECT status FROM shop_order WHERE order_id = ?", (order_id,)).fetchone()
        if order is None:
            raise LookupError(f"Order not found: {order_id!r}")
        if order["status"] != "confirmed":
            raise ValueError(f"Cannot ship {order['status']!r} order {order_id!r}")
        conn.execute(
            "UPDATE shop_order SET status = 'shipped', updated_date = ? WHERE order_id = ?",
            (_today(), order_id),
        )
    return get_order(order_id)


def deliver_order(order_id: str) -> Dict[str, Any]:
    """Mark a shipped order as delivered.

    Raises LookupError if not found.
    Raises ValueError if order is not shipped.
    """
    with get_conn() as conn:
        order = conn.execute("SELECT status FROM shop_order WHERE order_id = ?", (order_id,)).fetchone()
        if order is None:
            raise LookupError(f"Order not found: {order_id!r}")
        if order["status"] != "shipped":
            raise ValueError(f"Cannot deliver {order['status']!r} order {order_id!r}")
        conn.execute(
            "UPDATE shop_order SET status = 'delivered', updated_date = ? WHERE order_id = ?",
            (_today(), order_id),
        )
    return get_order(order_id)


def cancel_order(order_id: str) -> Dict[str, Any]:
    """Cancel a pending or confirmed order. Restores stock if confirmed.

    Raises LookupError if not found.
    Raises ValueError if order is shipped or delivered.
    """
    with get_conn() as conn:
        order = conn.execute("SELECT status FROM shop_order WHERE order_id = ?", (order_id,)).fetchone()
        if order is None:
            raise LookupError(f"Order not found: {order_id!r}")
        if order["status"] not in ("pending", "confirmed"):
            raise ValueError(
                f"Cannot cancel {order['status']!r} order {order_id!r} "
                f"(only pending or confirmed orders can be cancelled)"
            )

        if order["status"] == "confirmed":
            items = conn.execute(
                "SELECT product_id, quantity FROM order_item WHERE order_id = ?", (order_id,)
            ).fetchall()
            for item in items:
                conn.execute(
                    "UPDATE product SET stock_qty = stock_qty + ? WHERE product_id = ?",
                    (item["quantity"], item["product_id"]),
                )

        conn.execute(
            "UPDATE shop_order SET status = 'cancelled', updated_date = ? WHERE order_id = ?",
            (_today(), order_id),
        )
    return get_order(order_id)


def update_shipping_address(order_id: str, shipping_address: str) -> Dict[str, Any]:
    """Update the shipping address on a pending order.

    Raises LookupError if not found.
    Raises ValueError if order is not pending or address is empty.
    """
    if not shipping_address or not shipping_address.strip():
        raise ValueError("shipping_address must be non-empty")

    with get_conn() as conn:
        order = conn.execute("SELECT status FROM shop_order WHERE order_id = ?", (order_id,)).fetchone()
        if order is None:
            raise LookupError(f"Order not found: {order_id!r}")
        if order["status"] != "pending":
            raise ValueError(f"Cannot update address on {order['status']!r} order {order_id!r}")
        conn.execute(
            "UPDATE shop_order SET shipping_address = ?, updated_date = ? WHERE order_id = ?",
            (shipping_address.strip(), _today(), order_id),
        )
    return get_order(order_id)
