"""
Payment Methods API for Retail environment.
Manages credit cards, gift cards, and PayPal payment methods.

Business rules enforced:
  - user_id must reference a valid user
  - payment_method_id must be unique
  - source must be 'credit_card', 'gift_card', or 'paypal'
  - credit_card requires brand and last_four
  - gift_card balance cannot go negative
"""

from __future__ import annotations

from typing import Dict, List, Optional

from synthesize.environments.retail.db.db import get_conn

VALID_SOURCES = ("credit_card", "gift_card", "paypal")


def _row_to_dict(row) -> dict:
    return dict(row)


# ── Read Operations ───────────────────────────────────────────────────────────


def get_payment_method(payment_method_id: str) -> Optional[Dict]:
    """Get payment method by ID."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM payment_methods WHERE payment_method_id = ?",
            (payment_method_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_user_payment_method(user_id: str, payment_method_id: str) -> Optional[Dict]:
    """Get a payment method belonging to a specific user."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM payment_methods WHERE user_id = ? AND payment_method_id = ?",
            (user_id, payment_method_id),
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_payment_methods(
    user_id: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """List payment methods with optional filters."""
    query = "SELECT * FROM payment_methods WHERE 1=1"
    params: list = []

    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)
    if source is not None:
        query += " AND source = ?"
        params.append(source)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_user_payment_methods(user_id: str) -> List[Dict]:
    """List all payment methods for a user."""
    return list_payment_methods(user_id=user_id)


# ── Write Operations ──────────────────────────────────────────────────────────


def _check_user_exists(conn, user_id: str) -> None:
    if not conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone():
        raise LookupError(f"User '{user_id}' not found")


def _check_pm_unique(conn, payment_method_id: str) -> None:
    if conn.execute(
        "SELECT 1 FROM payment_methods WHERE payment_method_id = ?",
        (payment_method_id,),
    ).fetchone():
        raise ValueError(f"Payment method '{payment_method_id}' already exists")


def create_credit_card(
    payment_method_id: str,
    user_id: str,
    brand: str,
    last_four: str,
) -> Dict:
    """
    Create a credit card payment method.

    Args:
        payment_method_id: Unique ID (format: 'credit_card_NNNNNNN')
        user_id: Owning user
        brand: Card brand (visa, mastercard, amex, discover, etc.)
        last_four: Last 4 digits of card number
    """
    with get_conn() as conn:
        _check_user_exists(conn, user_id)
        _check_pm_unique(conn, payment_method_id)

        conn.execute(
            """INSERT INTO payment_methods (payment_method_id, user_id, source, brand, last_four)
               VALUES (?, ?, 'credit_card', ?, ?)""",
            (payment_method_id, user_id, brand, last_four),
        )
        row = conn.execute(
            "SELECT * FROM payment_methods WHERE payment_method_id = ?",
            (payment_method_id,),
        ).fetchone()
    return _row_to_dict(row)


def create_gift_card(
    payment_method_id: str,
    user_id: str,
    balance: float,
) -> Dict:
    """
    Create a gift card payment method.

    Args:
        payment_method_id: Unique ID (format: 'gift_card_NNNNNNN')
        user_id: Owning user
        balance: Initial balance (must be >= 0)
    """
    if balance < 0:
        raise ValueError(f"Gift card balance cannot be negative: {balance}")

    with get_conn() as conn:
        _check_user_exists(conn, user_id)
        _check_pm_unique(conn, payment_method_id)

        conn.execute(
            """INSERT INTO payment_methods (payment_method_id, user_id, source, balance)
               VALUES (?, ?, 'gift_card', ?)""",
            (payment_method_id, user_id, balance),
        )
        row = conn.execute(
            "SELECT * FROM payment_methods WHERE payment_method_id = ?",
            (payment_method_id,),
        ).fetchone()
    return _row_to_dict(row)


def create_paypal(
    payment_method_id: str,
    user_id: str,
) -> Dict:
    """
    Create a PayPal payment method.

    Args:
        payment_method_id: Unique ID (format: 'paypal_NNNNNNN')
        user_id: Owning user
    """
    with get_conn() as conn:
        _check_user_exists(conn, user_id)
        _check_pm_unique(conn, payment_method_id)

        conn.execute(
            "INSERT INTO payment_methods (payment_method_id, user_id, source) VALUES (?, ?, 'paypal')",
            (payment_method_id, user_id),
        )
        row = conn.execute(
            "SELECT * FROM payment_methods WHERE payment_method_id = ?",
            (payment_method_id,),
        ).fetchone()
    return _row_to_dict(row)


def update_gift_card_balance(payment_method_id: str, balance: float) -> Dict:
    """Set gift card balance to an absolute value."""
    if balance < 0:
        raise ValueError(f"Gift card balance cannot be negative: {balance}")

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM payment_methods WHERE payment_method_id = ?",
            (payment_method_id,),
        ).fetchone()
        if row is None:
            raise LookupError(f"Payment method '{payment_method_id}' not found")
        if row["source"] != "gift_card":
            raise ValueError(f"Payment method '{payment_method_id}' is not a gift card")

        conn.execute(
            "UPDATE payment_methods SET balance = ? WHERE payment_method_id = ?",
            (round(balance, 2), payment_method_id),
        )
        row = conn.execute(
            "SELECT * FROM payment_methods WHERE payment_method_id = ?",
            (payment_method_id,),
        ).fetchone()
    return _row_to_dict(row)


def add_to_gift_card_balance(payment_method_id: str, amount: float) -> Dict:
    """Add to gift card balance (used for refunds)."""
    pm = get_payment_method(payment_method_id)
    if pm is None:
        raise LookupError(f"Payment method '{payment_method_id}' not found")
    if pm["source"] != "gift_card":
        raise ValueError(f"Payment method '{payment_method_id}' is not a gift card")
    return update_gift_card_balance(payment_method_id, (pm["balance"] or 0) + amount)


def deduct_from_gift_card_balance(payment_method_id: str, amount: float) -> Dict:
    """Deduct from gift card balance (used for payments). Raises if insufficient."""
    pm = get_payment_method(payment_method_id)
    if pm is None:
        raise LookupError(f"Payment method '{payment_method_id}' not found")
    if pm["source"] != "gift_card":
        raise ValueError(f"Payment method '{payment_method_id}' is not a gift card")

    current = pm["balance"] or 0
    if current < amount:
        raise ValueError(
            f"Insufficient gift card balance: {current:.2f} < {amount:.2f}"
        )
    return update_gift_card_balance(payment_method_id, current - amount)


def delete_payment_method(payment_method_id: str) -> bool:
    """Delete a payment method."""
    with get_conn() as conn:
        result = conn.execute(
            "DELETE FROM payment_methods WHERE payment_method_id = ?",
            (payment_method_id,),
        )
        return result.rowcount > 0
