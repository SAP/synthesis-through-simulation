"""
Users API for Retail environment.

Business rules enforced:
  - user_id must be unique
  - email must be unique
"""

from __future__ import annotations

from typing import Dict, List, Optional

from synthesize.environments.retail.db.db import get_conn


def _row_to_dict(row) -> dict:
    return dict(row)


# ── Read Operations ───────────────────────────────────────────────────────────


def get_user(user_id: str) -> Optional[Dict]:
    """Get user by ID."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def find_user_by_email(email: str) -> Optional[Dict]:
    """Find user by email address."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def find_user_by_name_zip(first_name: str, last_name: str, zip_code: str) -> Optional[Dict]:
    """Find user by first name, last name, and zip code."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM users
            WHERE LOWER(first_name) = LOWER(?)
              AND LOWER(last_name) = LOWER(?)
              AND zip = ?
            """,
            (first_name, last_name, zip_code),
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_users(limit: int = 50, offset: int = 0) -> List[Dict]:
    """List users with pagination."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


# ── Write Operations ──────────────────────────────────────────────────────────


def create_user(
    user_id: str,
    first_name: str,
    last_name: str,
    email: str,
    address1: str,
    city: str,
    state: str,
    country: str,
    zip_code: str,
    address2: Optional[str] = None,
) -> Dict:
    """
    Create a new user.

    Business rules:
      - user_id must be unique (format: 'first_last_nnn', e.g. 'sara_doe_496')
      - email must be unique
    """
    with get_conn() as conn:
        if conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        ).fetchone():
            raise ValueError(f"User '{user_id}' already exists")

        if conn.execute(
            "SELECT 1 FROM users WHERE LOWER(email) = LOWER(?)", (email,)
        ).fetchone():
            raise ValueError(f"Email '{email}' is already registered")

        conn.execute(
            """
            INSERT INTO users (
                user_id, first_name, last_name, email,
                address1, address2, city, state, country, zip
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, first_name, last_name, email,
             address1, address2, city, state, country, zip_code),
        )
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    return _row_to_dict(row)


def update_user(
    user_id: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    address1: Optional[str] = None,
    address2: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    country: Optional[str] = None,
    zip_code: Optional[str] = None,
) -> Dict:
    """Update user fields (only provided fields are changed)."""
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        ).fetchone():
            raise LookupError(f"User '{user_id}' not found")

        updates: dict = {}
        if first_name is not None:
            updates["first_name"] = first_name
        if last_name is not None:
            updates["last_name"] = last_name
        if email is not None:
            updates["email"] = email
        if address1 is not None:
            updates["address1"] = address1
        if address2 is not None:
            updates["address2"] = address2
        if city is not None:
            updates["city"] = city
        if state is not None:
            updates["state"] = state
        if country is not None:
            updates["country"] = country
        if zip_code is not None:
            updates["zip"] = zip_code

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [user_id]
            conn.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)

        row = conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    return _row_to_dict(row)


def update_user_address(
    user_id: str,
    address1: str,
    city: str,
    state: str,
    country: str,
    zip_code: str,
    address2: Optional[str] = None,
) -> Dict:
    """Update user's default address."""
    return update_user(
        user_id=user_id,
        address1=address1,
        address2=address2,
        city=city,
        state=state,
        country=country,
        zip_code=zip_code,
    )


def delete_user(user_id: str) -> bool:
    """Delete a user and all associated data (cascade)."""
    with get_conn() as conn:
        result = conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        return result.rowcount > 0
