"""
Object_fs API for the Generic environment.
Adapted from the external mock_system/apis/object_fs.py.
Returns plain dicts (JSON-serialisable).
"""

from __future__ import annotations

from typing import Optional

from synthesize.environments.obfuscated_airline.db.db import get_conn

# ── Read Operations ──────────────────────────────────────────────────────────


def get_object_f_details(property_id: str) -> dict:
    """Get full object_f details including saved object_ds and object_es."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM object_fs WHERE property_id = ?", (property_id,)).fetchone()
        if row is None:
            raise LookupError(f"Object_f '{property_id}' not found")

        pms = conn.execute(
            "SELECT * FROM object_es WHERE property_id = ? ORDER BY created_at",
            (property_id,),
        ).fetchall()
        object_ds = conn.execute(
            "SELECT * FROM saved_object_ds WHERE property_id = ? ORDER BY id",
            (property_id,),
        ).fetchall()

    return {
        "property_id": row["property_id"],
        "property_n": row["property_n"],
        "property_o": row["property_o"],
        "property_p": row["property_p"],
        "property_m": row["property_m"],
        "property_q": row["property_q"],
        "property_r_to_w": {
            "property_r": row["property_r"],
            "property_s": row["property_s"],
            "property_t": row["property_t"],
            "property_u": row["property_u"],
            "property_v": row["property_v"],
            "property_w": row["property_w"],
        },
        "object_es": [
            {
                "object_e_id": pm["object_e_id"],
                "property_i": pm["property_i"],
                "property_j": pm["property_j"],
                "property_k": pm["property_k"],
                "amount": pm["amount"],
            }
            for pm in pms
        ],
        "saved_object_ds": [
            {
                "id": p["id"],
                "property_n": p["property_n"],
                "property_o": p["property_o"],
                "property_m": p["property_m"],
            }
            for p in object_ds
        ],
    }


def list_object_fs(property_q: Optional[str] = None) -> list[dict]:
    """List all object_fs with optional property_q filter."""
    query = "SELECT property_id, property_n, property_o, property_p, property_q FROM object_fs"
    params: list = []
    if property_q is not None:
        if property_q not in ("value_g", "value_s", "value_r"):
            raise ValueError(
                f"Invalid property_q: {property_q!r}. Must be value_g, value_s, or value_r"
            )
        query += " WHERE property_q = ?"
        params.append(property_q)
    query += " ORDER BY property_id"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        {
            "property_id": r["property_id"],
            "property_n": r["property_n"],
            "property_o": r["property_o"],
            "property_p": r["property_p"],
            "property_q": r["property_q"],
        }
        for r in rows
    ]


def get_saved_object_ds(property_id: str) -> list[dict]:
    """Get the saved object_d profiles for a object_f."""
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM object_fs WHERE property_id = ?", (property_id,)).fetchone():
            raise LookupError(f"Object_f '{property_id}' not found")
        rows = conn.execute(
            "SELECT * FROM saved_object_ds WHERE property_id = ? ORDER BY id",
            (property_id,),
        ).fetchall()
    return [
        {"id": r["id"], "property_n": r["property_n"], "property_o": r["property_o"], "property_m": r["property_m"]}
        for r in rows
    ]
