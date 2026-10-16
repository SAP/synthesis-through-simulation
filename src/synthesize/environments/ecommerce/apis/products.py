"""
Product catalog API for the E-commerce environment.

Business rules enforced:
  - price must be positive
  - stock_qty must be non-negative
  - Deactivated products cannot be added to new orders
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from synthesize.environments.ecommerce.db.db import get_conn


def _prod_id() -> str:
    return "PROD-" + str(uuid.uuid4())[:6].upper()


def get_product(product_id: str) -> Dict[str, Any]:
    """Return a product record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM product WHERE product_id = ?", (product_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"Product not found: {product_id!r}")
    return dict(row)


def list_products(
    category: Optional[str] = None,
    in_stock: Optional[bool] = None,
    is_active: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Return products with optional filters."""
    query = "SELECT * FROM product WHERE 1=1"
    params: list = []
    if category is not None:
        query += " AND category = ?"
        params.append(category)
    if in_stock is True:
        query += " AND stock_qty > 0"
    elif in_stock is False:
        query += " AND stock_qty = 0"
    if is_active is not None:
        query += " AND is_active = ?"
        params.append(1 if is_active else 0)
    query += " ORDER BY product_id"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def create_product(
    name: str,
    category: str,
    price: float,
    stock_qty: int = 0,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a new product to the catalog.

    Raises ValueError for invalid inputs.
    """
    if not name or not name.strip():
        raise ValueError("name must be non-empty")
    if not category or not category.strip():
        raise ValueError("category must be non-empty")
    if price <= 0:
        raise ValueError(f"price must be positive, got {price}")
    if stock_qty < 0:
        raise ValueError(f"stock_qty cannot be negative, got {stock_qty}")

    product_id = _prod_id()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO product (product_id, name, category, price, stock_qty, description, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (product_id, name.strip(), category.strip(), price, stock_qty, description),
        )
    return get_product(product_id)


def update_product(
    product_id: str,
    price: Optional[float] = None,
    stock_qty: Optional[int] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Update mutable product fields.

    Raises LookupError if not found.
    Raises ValueError for invalid values.
    """
    if price is None and stock_qty is None and description is None:
        raise ValueError("At least one field must be provided")
    with get_conn() as conn:
        row = conn.execute("SELECT product_id FROM product WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            raise LookupError(f"Product not found: {product_id!r}")

        updates, values = [], []
        if price is not None:
            if price <= 0:
                raise ValueError(f"price must be positive, got {price}")
            updates.append("price = ?")
            values.append(price)
        if stock_qty is not None:
            if stock_qty < 0:
                raise ValueError(f"stock_qty cannot be negative, got {stock_qty}")
            updates.append("stock_qty = ?")
            values.append(stock_qty)
        if description is not None:
            updates.append("description = ?")
            values.append(description)
        values.append(product_id)
        conn.execute(f"UPDATE product SET {', '.join(updates)} WHERE product_id = ?", values)
    return get_product(product_id)


def deactivate_product(product_id: str) -> Dict[str, Any]:
    """Mark a product as inactive (no longer sold).

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT is_active FROM product WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            raise LookupError(f"Product not found: {product_id!r}")
        if not row["is_active"]:
            raise ValueError(f"Product {product_id!r} is already inactive")
        conn.execute("UPDATE product SET is_active = 0 WHERE product_id = ?", (product_id,))
    return get_product(product_id)


def restock_product(product_id: str, quantity: int) -> Dict[str, Any]:
    """Increase a product's stock quantity.

    Raises LookupError if not found.
    Raises ValueError if quantity ≤ 0.
    """
    if quantity <= 0:
        raise ValueError(f"Restock quantity must be positive, got {quantity}")
    with get_conn() as conn:
        row = conn.execute("SELECT is_active FROM product WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            raise LookupError(f"Product not found: {product_id!r}")
        conn.execute(
            "UPDATE product SET stock_qty = stock_qty + ? WHERE product_id = ?",
            (quantity, product_id),
        )
    return get_product(product_id)
