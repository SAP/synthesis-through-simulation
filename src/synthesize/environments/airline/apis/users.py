"""
Users API for the Airline environment.
Adapted from the external mock_system/apis/users.py.
Returns plain dicts (JSON-serialisable).
"""

from __future__ import annotations

from typing import Optional

from synthesize.environments.airline.db.db import get_conn

# ── Read Operations ──────────────────────────────────────────────────────────


def get_user_details(user_id: str) -> dict:
    """Get full user details including saved passengers and payment methods."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            raise LookupError(f"User '{user_id}' not found")

        pms = conn.execute(
            "SELECT * FROM payment_methods WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ).fetchall()
        passengers = conn.execute(
            "SELECT * FROM saved_passengers WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()

    return {
        "user_id": row["user_id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "email": row["email"],
        "dob": row["dob"],
        "membership": row["membership"],
        "address": {
            "address1": row["address1"],
            "address2": row["address2"],
            "city": row["city"],
            "state": row["state"],
            "country": row["country"],
            "zip": row["zip"],
        },
        "payment_methods": [
            {
                "payment_method_id": pm["payment_method_id"],
                "source": pm["source"],
                "brand": pm["brand"],
                "last_four": pm["last_four"],
                "amount": pm["amount"],
            }
            for pm in pms
        ],
        "saved_passengers": [
            {
                "id": p["id"],
                "first_name": p["first_name"],
                "last_name": p["last_name"],
                "dob": p["dob"],
            }
            for p in passengers
        ],
    }


def list_users(membership: Optional[str] = None) -> list[dict]:
    """List all users with optional membership filter."""
    query = "SELECT user_id, first_name, last_name, email, membership FROM users"
    params: list = []
    if membership is not None:
        if membership not in ("gold", "silver", "regular"):
            raise ValueError(
                f"Invalid membership: {membership!r}. Must be gold, silver, or regular"
            )
        query += " WHERE membership = ?"
        params.append(membership)
    query += " ORDER BY user_id"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        {
            "user_id": r["user_id"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "email": r["email"],
            "membership": r["membership"],
        }
        for r in rows
    ]


def get_saved_passengers(user_id: str) -> list[dict]:
    """Get the saved passenger profiles for a user."""
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone():
            raise LookupError(f"User '{user_id}' not found")
        rows = conn.execute(
            "SELECT * FROM saved_passengers WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    return [
        {"id": r["id"], "first_name": r["first_name"], "last_name": r["last_name"], "dob": r["dob"]}
        for r in rows
    ]
