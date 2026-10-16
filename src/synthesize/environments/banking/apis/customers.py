"""
Customer read/write API for the Retail Banking environment.

Business rules enforced:
  - id_type must be one of: passport, driver_license, national_id
  - email and id_number must be unique across all customers
  - Deactivated customers cannot open new accounts
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional

from synthesize.environments.banking.db.db import get_conn

VALID_ID_TYPES = {"passport", "driver_license", "national_id"}


def _today() -> str:
    return datetime.date.today().isoformat()


def list_customers(is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
    """Return all customers, optionally filtered by active status."""
    query = "SELECT * FROM customer WHERE 1=1"
    params: list = []
    if is_active is not None:
        query += " AND is_active = ?"
        params.append(1 if is_active else 0)
    query += " ORDER BY customer_id"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_customer(customer_id: str) -> Dict[str, Any]:
    """Return a single customer by ID.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customer WHERE customer_id = ?", (customer_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"Customer not found: {customer_id!r}")
    return dict(row)


def get_customer_by_email(email: str) -> Dict[str, Any]:
    """Return a customer by email address.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM customer WHERE email = ?", (email,)
        ).fetchone()
    if row is None:
        raise LookupError(f"No customer with email: {email!r}")
    return dict(row)


def create_customer(
    name: str,
    email: str,
    id_type: str,
    id_number: str,
    phone: Optional[str] = None,
    address: Optional[str] = None,
) -> Dict[str, Any]:
    """Register a new bank customer.

    Raises ValueError for invalid inputs or duplicate email/id_number.
    """
    if not name or not name.strip():
        raise ValueError("name must be non-empty")
    if not email or not email.strip():
        raise ValueError("email must be non-empty")
    if id_type not in VALID_ID_TYPES:
        raise ValueError(f"id_type must be one of {sorted(VALID_ID_TYPES)}, got {id_type!r}")
    if not id_number or not id_number.strip():
        raise ValueError("id_number must be non-empty")

    customer_id = str(uuid.uuid4())[:8].upper()
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM customer WHERE email = ?", (email,)).fetchone():
            raise ValueError(f"Email already registered: {email!r}")
        if conn.execute("SELECT 1 FROM customer WHERE id_number = ?", (id_number,)).fetchone():
            raise ValueError(f"ID number already registered: {id_number!r}")
        conn.execute(
            """INSERT INTO customer
               (customer_id, name, email, phone, address, id_type, id_number, is_active, created_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (customer_id, name.strip(), email.strip(), phone, address, id_type, id_number.strip(), _today()),
        )
    return get_customer(customer_id)


def update_customer(
    customer_id: str,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    email: Optional[str] = None,
) -> Dict[str, Any]:
    """Update mutable contact fields for a customer.

    Raises LookupError if customer not found.
    Raises ValueError if new email is already taken.
    """
    if phone is None and address is None and email is None:
        raise ValueError("At least one of phone, address, or email must be provided")

    with get_conn() as conn:
        row = conn.execute(
            "SELECT customer_id FROM customer WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Customer not found: {customer_id!r}")

        if email is not None:
            conflict = conn.execute(
                "SELECT 1 FROM customer WHERE email = ? AND customer_id != ?", (email, customer_id)
            ).fetchone()
            if conflict:
                raise ValueError(f"Email already in use: {email!r}")

        updates, values = [], []
        if phone is not None:
            updates.append("phone = ?")
            values.append(phone)
        if address is not None:
            updates.append("address = ?")
            values.append(address)
        if email is not None:
            updates.append("email = ?")
            values.append(email.strip())
        values.append(customer_id)
        conn.execute(f"UPDATE customer SET {', '.join(updates)} WHERE customer_id = ?", values)
    return get_customer(customer_id)


def deactivate_customer(customer_id: str) -> Dict[str, Any]:
    """Mark a customer as inactive.

    Raises LookupError if not found.
    Raises ValueError if customer has any active accounts.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT is_active FROM customer WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Customer not found: {customer_id!r}")
        if not row["is_active"]:
            raise ValueError(f"Customer {customer_id!r} is already inactive")

        active_accounts = conn.execute(
            "SELECT COUNT(*) FROM account WHERE customer_id = ? AND status = 'active'",
            (customer_id,),
        ).fetchone()[0]
        if active_accounts > 0:
            raise ValueError(
                f"Cannot deactivate customer {customer_id!r}: they have {active_accounts} active account(s)"
            )
        conn.execute("UPDATE customer SET is_active = 0 WHERE customer_id = ?", (customer_id,))
    return get_customer(customer_id)
