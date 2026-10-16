"""
Payments API for the Airline environment.
Covers payment method lookups and certificate issuance (send_certificate).
Returns plain dicts (JSON-serialisable).
"""

from __future__ import annotations

import uuid
from typing import Optional

from synthesize.environments.airline.db.db import get_conn

VALID_SOURCES = ("credit_card", "gift_card", "certificate")


def get_payment_methods(user_id: str) -> list[dict]:
    """List all payment methods for a user."""
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone():
            raise LookupError(f"User '{user_id}' not found")
        rows = conn.execute(
            "SELECT * FROM payment_methods WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ).fetchall()
    return [
        {
            "payment_method_id": r["payment_method_id"],
            "source": r["source"],
            "brand": r["brand"],
            "last_four": r["last_four"],
            "amount": r["amount"],
        }
        for r in rows
    ]


def send_certificate(user_id: str, amount: int) -> dict:
    """
    Issue a travel certificate as compensation for a user.

    Business rules:
    - User must exist
    - Amount must be positive
    - Standard certificate amounts are 50, 100, 200 (enforced by policy, not API)
    """
    if amount <= 0:
        raise ValueError(f"Certificate amount must be positive, got {amount}")

    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone():
            raise LookupError(f"User '{user_id}' not found")

        pm_id = f"certificate_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO payment_methods
               (payment_method_id, user_id, source, amount)
               VALUES (?, ?, 'certificate', ?)""",
            (pm_id, user_id, amount),
        )
        row = conn.execute(
            "SELECT * FROM payment_methods WHERE payment_method_id = ?",
            (pm_id,),
        ).fetchone()

    return {
        "payment_method_id": row["payment_method_id"],
        "user_id": row["user_id"],
        "source": row["source"],
        "amount": row["amount"],
        "message": f"Certificate of ${amount} issued to user {user_id}",
    }


def _get_payment_method_row(conn, payment_method_id: str, user_id: Optional[str] = None) -> dict:
    """Internal helper: get and validate a payment method row."""
    query = "SELECT * FROM payment_methods WHERE payment_method_id = ?"
    params: list = [payment_method_id]
    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)
    row = conn.execute(query, params).fetchone()
    if row is None:
        msg = f"Payment method '{payment_method_id}' not found"
        if user_id:
            msg += f" for user '{user_id}'"
        raise LookupError(msg)
    return row
