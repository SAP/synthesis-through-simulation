"""
Products API for Retail environment.
Manages products (e.g., 'Laptop Pro 15') and their variants (specific
configurations with price and availability).

Business rules enforced:
  - product_id must be unique
  - item_id must be unique
  - variant product_id must reference a valid product
  - variant price must be positive
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from synthesize.environments.retail.db.db import get_conn


def _product_row_to_dict(row) -> dict:
    return dict(row)


def _variant_row_to_dict(row) -> dict:
    d = dict(row)
    d["options"] = json.loads(d["options"]) if d["options"] else {}
    d["available"] = bool(d["available"])
    return d


# ── Product Read Operations ───────────────────────────────────────────────────


def get_product(product_id: str) -> Optional[Dict]:
    """Get product by ID."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
    return _product_row_to_dict(row) if row else None


def get_product_with_variants(product_id: str) -> Optional[Dict]:
    """Get product with all its variants keyed by item_id."""
    product = get_product(product_id)
    if product is None:
        return None
    variants = list_variants(product_id=product_id)
    return {"product": product, "variants": {v["item_id"]: v for v in variants}}


def list_products(limit: int = 50, offset: int = 0) -> List[Dict]:
    """List all products."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM products ORDER BY name ASC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_product_row_to_dict(r) for r in rows]


def list_all_product_types() -> Dict[str, str]:
    """Return {name: product_id} mapping for all products."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name, product_id FROM products ORDER BY name ASC"
        ).fetchall()
    return {r["name"]: r["product_id"] for r in rows}


# ── Product Write Operations ──────────────────────────────────────────────────


def create_product(product_id: str, name: str) -> Dict:
    """
    Create a new product.

    Business rules:
      - product_id must be unique
    """
    with get_conn() as conn:
        if conn.execute(
            "SELECT 1 FROM products WHERE product_id = ?", (product_id,)
        ).fetchone():
            raise ValueError(f"Product '{product_id}' already exists")

        conn.execute(
            "INSERT INTO products (product_id, name) VALUES (?, ?)",
            (product_id, name),
        )
        row = conn.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
    return _product_row_to_dict(row)


def update_product(product_id: str, name: Optional[str] = None) -> Dict:
    """Update product name."""
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM products WHERE product_id = ?", (product_id,)
        ).fetchone():
            raise LookupError(f"Product '{product_id}' not found")

        if name is not None:
            conn.execute(
                "UPDATE products SET name = ? WHERE product_id = ?", (name, product_id)
            )
        row = conn.execute(
            "SELECT * FROM products WHERE product_id = ?", (product_id,)
        ).fetchone()
    return _product_row_to_dict(row)


def delete_product(product_id: str) -> bool:
    """Delete a product and all its variants (cascade)."""
    with get_conn() as conn:
        result = conn.execute(
            "DELETE FROM products WHERE product_id = ?", (product_id,)
        )
        return result.rowcount > 0


# ── Variant Read Operations ───────────────────────────────────────────────────


def get_variant(item_id: str) -> Optional[Dict]:
    """Get variant by item_id."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM variants WHERE item_id = ?", (item_id,)
        ).fetchone()
    return _variant_row_to_dict(row) if row else None


def list_variants(
    product_id: Optional[str] = None,
    available_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict]:
    """List variants with optional filters."""
    query = "SELECT * FROM variants WHERE 1=1"
    params: list = []

    if product_id is not None:
        query += " AND product_id = ?"
        params.append(product_id)
    if available_only:
        query += " AND available = 1"

    query += " ORDER BY price ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_variant_row_to_dict(r) for r in rows]


# ── Variant Write Operations ──────────────────────────────────────────────────


def create_variant(
    item_id: str,
    product_id: str,
    price: float,
    options: Optional[Dict[str, str]] = None,
    available: bool = True,
) -> Dict:
    """
    Create a variant for an existing product.

    Business rules:
      - item_id must be unique
      - product_id must reference a valid product
      - price must be positive
    """
    if price <= 0:
        raise ValueError(f"Variant price must be positive, got {price}")

    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM products WHERE product_id = ?", (product_id,)
        ).fetchone():
            raise LookupError(f"Product '{product_id}' not found")

        if conn.execute(
            "SELECT 1 FROM variants WHERE item_id = ?", (item_id,)
        ).fetchone():
            raise ValueError(f"Variant '{item_id}' already exists")

        conn.execute(
            "INSERT INTO variants (item_id, product_id, options, available, price) VALUES (?, ?, ?, ?, ?)",
            (item_id, product_id, json.dumps(options or {}), int(available), price),
        )
        row = conn.execute(
            "SELECT * FROM variants WHERE item_id = ?", (item_id,)
        ).fetchone()
    return _variant_row_to_dict(row)


def update_variant(
    item_id: str,
    price: Optional[float] = None,
    options: Optional[Dict[str, str]] = None,
    available: Optional[bool] = None,
) -> Dict:
    """Update variant price, options, or availability."""
    if price is not None and price <= 0:
        raise ValueError(f"Variant price must be positive, got {price}")

    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM variants WHERE item_id = ?", (item_id,)
        ).fetchone():
            raise LookupError(f"Variant '{item_id}' not found")

        updates: dict = {}
        if price is not None:
            updates["price"] = price
        if options is not None:
            updates["options"] = json.dumps(options)
        if available is not None:
            updates["available"] = int(available)

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [item_id]
            conn.execute(f"UPDATE variants SET {set_clause} WHERE item_id = ?", values)

        row = conn.execute(
            "SELECT * FROM variants WHERE item_id = ?", (item_id,)
        ).fetchone()
    return _variant_row_to_dict(row)


def delete_variant(item_id: str) -> bool:
    """Delete a variant."""
    with get_conn() as conn:
        result = conn.execute("DELETE FROM variants WHERE item_id = ?", (item_id,))
        return result.rowcount > 0
