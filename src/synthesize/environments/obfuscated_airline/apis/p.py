"""
ObjectEs API for the Generic environment.
Covers object_e lookups and type_c issuance (send_type_c).
Returns plain dicts (JSON-serialisable).
"""

from __future__ import annotations

import uuid
from typing import Optional

from synthesize.environments.obfuscated_airline.db.db import get_conn

VALID_TYPES = ("i_a", "i_b", "i_c")


def get_object_es(property_id: str) -> list[dict]:
    """List all object_es for a object_f."""
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM object_fs WHERE property_id = ?", (property_id,)).fetchone():
            raise LookupError(f"Object_f '{property_id}' not found")
        rows = conn.execute(
            "SELECT * FROM object_es WHERE property_id = ? ORDER BY created_at",
            (property_id,),
        ).fetchall()
    return [
        {
            "object_e_id": r["object_e_id"],
            "property_i": r["property_i"],
            "property_j": r["property_j"],
            "property_k": r["property_k"],
            "amount": r["amount"],
        }
        for r in rows
    ]


def send_type_c(property_id: str, amount: int) -> dict:
    """
    Issue a type_c object_e for a object_f.

    Business rules:
    - Object_f must exist
    - Amount must be positive
    - Standard amounts are 50, 100, 200 (enforced by policy, not API)
    """
    if amount <= 0:
        raise ValueError(f"Amount must be positive, got {amount}")

    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM object_fs WHERE property_id = ?", (property_id,)).fetchone():
            raise LookupError(f"Object_f '{property_id}' not found")

        oe_id = f"i_c_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO object_es
               (object_e_id, property_id, property_i, amount)
               VALUES (?, ?, 'i_c', ?)""",
            (oe_id, property_id, amount),
        )
        row = conn.execute(
            "SELECT * FROM object_es WHERE object_e_id = ?",
            (oe_id,),
        ).fetchone()

    return {
        "object_e_id": row["object_e_id"],
        "property_id": row["property_id"],
        "property_i": row["property_i"],
        "amount": row["amount"],
        "message": f"Type_c of ${amount} issued to object_f {property_id}",
    }


def _get_object_e_row(conn, object_e_id: str, property_id: Optional[str] = None) -> dict:
    """Internal helper: get and validate an object_e row."""
    query = "SELECT * FROM object_es WHERE object_e_id = ?"
    params: list = [object_e_id]
    if property_id is not None:
        query += " AND property_id = ?"
        params.append(property_id)
    row = conn.execute(query, params).fetchone()
    if row is None:
        msg = f"Object_e '{object_e_id}' not found"
        if property_id:
            msg += f" for object_f '{property_id}'"
        raise LookupError(msg)
    return row
