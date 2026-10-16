"""
ObjectCs API for the Generic environment.
Every business rule raises ValueError.

Policy summary enforced here:
  Topic 1
  - property_e must be consistent across all object_bs
  - max 5 object_ds
  - max 1 i_c, 1 i_a, 3 i_b per object_c
  - property_g amount = 30 per object_d
  - property_h fee = 50 per property_h item
  - object_es total must exactly cover total property_b

  Topic 2
  - cannot set to status_a an already-status_a object_c
  - cannot set to status_a if any object_b has status 'status_c' or 'status_d'
  - only eligible if: object_c created within last 24hr OR status_e object_b
    OR type_b property_e OR (has property_g + covered reason: reason_a/reason_b/reason_c/reason_d/reason_e)

  Topic 3 (update_object_c_object_bs)
  - type_c property_e cannot be modified
  - cannot change object_a_property_1, object_a_property_2, or object_b_type
  - cannot change property_e if any object_b is already 'status_c' or 'status_d'
  - i_c object_es cannot be used for updates

  Topic 4 (update_object_c_baggages)
  - can only increase property_h, not decrease (property_h must be >= current)
  - property_f must be >= property_h
  - i_c object_es cannot be used

  Topic 5 (update_object_c_object_ds)
  - object_d count must match original
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from synthesize.environments.obfuscated_airline.db.db import get_conn

# ── Internal helpers ─────────────────────────────────────────────────────────


def _load_res(conn, object_c_id: str) -> object:
    """Return the object_c sqlite3.Row or raise LookupError."""
    row = conn.execute(
        "SELECT * FROM object_cs WHERE object_c_id = ?",
        (object_c_id,),
    ).fetchone()
    if row is None:
        raise LookupError(f"ObjectC '{object_c_id}' not found")
    return row


def _load_object_c_full(conn, object_c_id: str) -> dict:
    """Build a full object_c dict with nested object_bs/object_ds/object_c_object_es."""
    row = conn.execute(
        "SELECT * FROM object_cs WHERE object_c_id = ?",
        (object_c_id,),
    ).fetchone()
    if row is None:
        return None  # type: ignore[return-value]

    object_bs = conn.execute(
        "SELECT * FROM object_c_object_bs WHERE object_c_id = ? ORDER BY id",
        (object_c_id,),
    ).fetchall()
    object_ds = conn.execute(
        "SELECT * FROM object_c_object_ds WHERE object_c_id = ? ORDER BY id",
        (object_c_id,),
    ).fetchall()
    values = conn.execute(
        "SELECT * FROM object_c_object_es WHERE object_c_id = ? ORDER BY id",
        (object_c_id,),
    ).fetchall()

    return {
        "object_c_id": row["object_c_id"],
        "property_id": row["property_id"],
        "object_a_property_1": row["object_a_property_1"],
        "object_a_property_2": row["object_a_property_2"],
        "object_b_type": row["object_b_type"],
        "property_e": row["property_e"],
        "property_f": row["property_f"],
        "property_h": row["property_h"],
        "property_g": row["property_g"],
        "status": row["status"],
        "created_at": row["created_at"],
        "object_bs": [
            {
                "id": f["id"],
                "object_b_number": f["object_b_number"],
                "object_a_property_1": f["object_a_property_1"],
                "object_a_property_2": f["object_a_property_2"],
                "property_l": f["property_l"],
                "property_b": f["property_b"],
            }
            for f in object_bs
        ],
        "object_ds": [
            {
                "id": p["id"],
                "property_n": p["property_n"],
                "property_o": p["property_o"],
                "property_m": p["property_m"],
            }
            for p in object_ds
        ],
        "object_c_object_es": [
            {
                "id": ch["id"],
                "object_e_id": ch["object_e_id"],
                "amount": ch["amount"],
                "created_at": ch["created_at"],
            }
            for ch in values
        ],
    }


def _fd_row(conn, object_b_number: str, property_l: str) -> object:
    row = conn.execute(
        "SELECT * FROM object_b_property_ls WHERE object_b_number = ? AND property_l = ?",
        (object_b_number, property_l),
    ).fetchone()
    if row is None:
        raise LookupError(f"ObjectB '{object_b_number}' not found for property_l {property_l}")
    return row


def _check_any_object_b_active(conn, object_c_id: str) -> bool:
    """Return True if any object_c object_b is currently 'status_c' or 'status_d'."""
    rows = conn.execute(
        """
        SELECT fd.status
        FROM object_c_object_bs rf
        JOIN object_b_property_ls fd ON rf.object_b_number = fd.object_b_number AND rf.property_l = fd.property_l
        WHERE rf.object_c_id = ?
        """,
        (object_c_id,),
    ).fetchall()
    return any(r["status"] in ("status_c", "status_d") for r in rows)


def _check_any_object_b_status_e(conn, object_c_id: str) -> bool:
    """Return True if any object_b in the object_c is status_e."""
    rows = conn.execute(
        """
        SELECT fd.status
        FROM object_c_object_bs rf
        JOIN object_b_property_ls fd ON rf.object_b_number = fd.object_b_number AND rf.property_l = fd.property_l
        WHERE rf.object_c_id = ?
        """,
        (object_c_id,),
    ).fetchall()
    return any(r["status"] == "status_e" for r in rows)


# ── Read Operations ──────────────────────────────────────────────────────────


def get_object_c_details(object_c_id: str) -> dict:
    """Get a object_c with full details (object_bs, object_ds, object_c_object_es)."""
    with get_conn() as conn:
        result = _load_object_c_full(conn, object_c_id)
    if result is None:
        raise LookupError(f"ObjectC '{object_c_id}' not found")
    return result


def list_object_cs(property_id: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
    """List object_cs. status='active' filters for non-status_a."""
    query = "SELECT object_c_id FROM object_cs WHERE 1=1"
    params: list = []
    if property_id is not None:
        query += " AND property_id = ?"
        params.append(property_id)
    if status is not None:
        if status == "active":
            query += " AND status IS NULL"
        else:
            query += " AND status = ?"
            params.append(status)
    query += " ORDER BY created_at DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_load_object_c_full(conn, r["object_c_id"]) for r in rows]


# ── Book ObjectC ─────────────────────────────────────────────────────────


def book_object_c(
    property_id: str,
    object_a_property_1: str,
    object_a_property_2: str,
    object_b_type: str,
    property_e: str,
    object_bs: List[Dict],
    object_ds: List[Dict],
    object_es: List[Dict],
    property_f: int = 0,
    property_h: int = 0,
    property_g: str = "no",
) -> dict:
    """
    Book a object_c with full business-rule validation.

    Business rules enforced:
    - object_b_type must be 'option_a' or 'option_b'
    - property_e must be 'type_b', 'type_a', or 'type_c'
    - property_g must be 'yes' or 'no'
    - max 5 object_ds
    - max 1 i_c, 1 i_a, 3 i_b in object_es
    - all object_bs must be 'available' with sufficient property_a
    - property_g amount = 30 per object_d
    - property_h amount = 50 per property_h item
    - object_es total must exactly equal total property_b
    - i_b / i_c amounts validated and deducted
    - i_c object_es consumed (deleted) on use
    - property_a counts decremented
    """
    if object_b_type not in ("option_a", "option_b"):
        raise ValueError(f"Invalid object_b_type: {object_b_type!r}. Must be 'option_a' or 'option_b'")
    if property_e not in ("type_b", "type_a", "type_c"):
        raise ValueError(
            f"Invalid property_e: {property_e!r}. Must be 'type_b', 'type_a', or 'type_c'"
        )
    if property_g not in ("yes", "no"):
        raise ValueError(f"Invalid property_g: {property_g!r}. Must be 'yes' or 'no'")
    if not object_bs:
        raise ValueError("At least one object_b is required")
    if not object_ds:
        raise ValueError("At least one object_d is required")
    if len(object_ds) > 5:
        raise ValueError(f"Maximum 5 object_ds allowed, got {len(object_ds)}")
    if property_f < property_h:
        raise ValueError(
            f"property_f ({property_f}) cannot be less than property_h ({property_h})"
        )

    num_object_ds = len(object_ds)

    with get_conn() as conn:
        # Validate object_f
        if not conn.execute("SELECT 1 FROM object_fs WHERE property_id = ?", (property_id,)).fetchone():
            raise LookupError(f"Object_f '{property_id}' not found")

        # Validate object_e counts (after loading property_i values)
        ic_count = 0
        ia_count = 0
        ib_count = 0
        oe_rows = {}
        for oe in object_es:
            oid = oe["object_e_id"]
            oe_row = conn.execute(
                "SELECT * FROM object_es WHERE object_e_id = ? AND property_id = ?",
                (oid, property_id),
            ).fetchone()
            if oe_row is None:
                raise LookupError(f"Object_e '{oid}' not found for object_f '{property_id}'")
            oe_rows[oid] = oe_row
            src = oe_row["property_i"]
            if src == "i_c":
                ic_count += 1
            elif src == "i_a":
                ia_count += 1
            elif src == "i_b":
                ib_count += 1

        if ic_count > 1:
            raise ValueError("Maximum 1 i_c allowed per object_c")
        if ia_count > 1:
            raise ValueError("Maximum 1 i_a allowed per object_c")
        if ib_count > 3:
            raise ValueError("Maximum 3 i_b allowed per object_c")

        # Validate object_bs and calculate total property_b
        total_property_b = 0
        object_b_records = []
        for fi in object_bs:
            fn = fi["object_b_number"]
            dt = fi["property_l"]
            fd_row = _fd_row(conn, fn, dt)

            if fd_row["status"] != "status_a":
                raise ValueError(
                    f"ObjectB '{fn}' on {dt} is not available (status: {fd_row['status']})"
                )

            seat_col = f"property_a_{property_e}"
            if fd_row[seat_col] < num_object_ds:
                raise ValueError(
                    f"Not enough {property_e} availability on object_b '{fn}' on {dt} "
                    f"(available: {fd_row[seat_col]}, requested: {num_object_ds})"
                )

            price_col = f"property_b_{property_e}"
            price = fd_row[price_col]

            object_b_row = conn.execute(
                "SELECT * FROM object_bs WHERE object_b_number = ?", (fn,)
            ).fetchone()
            if object_b_row is None:
                raise LookupError(f"ObjectB '{fn}' not found")

            object_b_records.append(
                {
                    "object_b_number": fn,
                    "object_a_property_1": object_b_row["object_a_property_1"],
                    "object_a_property_2": object_b_row["object_a_property_2"],
                    "property_l": dt,
                    "property_b": price,
                }
            )
            total_property_b += price * num_object_ds

        # property_g fee: $30 per object_d
        if property_g == "yes":
            total_property_b += 30 * num_object_ds

        # property_h fee: $50 per property_h item
        total_property_b += 50 * property_h

        # Validate totals
        total_object_es = sum(oe["amount"] for oe in object_es)
        if total_object_es != total_property_b:
            raise ValueError(
                f"Object_es total does not match total property_b. "
                f"Expected: {total_property_b}, provided: {total_object_es}"
            )

        # Validate i_b / i_c amounts
        for oe in object_es:
            oid = oe["object_e_id"]
            amount = oe["amount"]
            oe_row = oe_rows[oid]
            if oe_row["property_i"] in ("i_b", "i_c"):
                if oe_row["amount"] < amount:
                    raise ValueError(
                        f"Insufficient amount in object_e '{oid}': "
                        f"available {oe_row['amount']}, required {amount}"
                    )

        # All checks pass — deduct amounts and consume i_c object_es
        for oe in object_es:
            oid = oe["object_e_id"]
            amount = oe["amount"]
            oe_row = oe_rows[oid]
            if oe_row["property_i"] == "i_b":
                conn.execute(
                    "UPDATE object_es SET amount = amount - ? WHERE object_e_id = ?",
                    (amount, oid),
                )
            elif oe_row["property_i"] == "i_c":
                conn.execute("DELETE FROM object_es WHERE object_e_id = ?", (oid,))

        # Decrement property_a counts
        for fi in object_bs:
            fn = fi["object_b_number"]
            dt = fi["property_l"]
            seat_col = f"property_a_{property_e}"
            conn.execute(
                f"UPDATE object_b_property_ls SET {seat_col} = {seat_col} - ? "  # noqa: S608
                "WHERE object_b_number = ? AND property_l = ?",
                (num_object_ds, fn, dt),
            )

        # Generate object_c ID
        object_c_id = uuid.uuid4().hex[:6].upper()
        while conn.execute(
            "SELECT 1 FROM object_cs WHERE object_c_id = ?", (object_c_id,)
        ).fetchone():
            object_c_id = uuid.uuid4().hex[:6].upper()

        # Insert object_c
        conn.execute(
            """INSERT INTO object_cs
               (object_c_id, property_id, object_a_property_1, object_a_property_2, object_b_type,
                property_e, property_f, property_h, property_g)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                object_c_id,
                property_id,
                object_a_property_1,
                object_a_property_2,
                object_b_type,
                property_e,
                property_f,
                property_h,
                property_g,
            ),
        )
        for fr in object_b_records:
            conn.execute(
                """INSERT INTO object_c_object_bs
                   (object_c_id, object_b_number, object_a_property_1, object_a_property_2, property_l, property_b)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    object_c_id,
                    fr["object_b_number"],
                    fr["object_a_property_1"],
                    fr["object_a_property_2"],
                    fr["property_l"],
                    fr["property_b"],
                ),
            )
        for p in object_ds:
            conn.execute(
                """INSERT INTO object_c_object_ds
                   (object_c_id, property_n, property_o, property_m)
                   VALUES (?, ?, ?, ?)""",
                (object_c_id, p["property_n"], p["property_o"], p["property_m"]),
            )
        for oe in object_es:
            conn.execute(
                "INSERT INTO object_c_object_es (object_c_id, object_e_id, amount) VALUES (?, ?, ?)",
                (object_c_id, oe["object_e_id"], oe["amount"]),
            )

        return _load_object_c_full(conn, object_c_id)


# ── Set ObjectC to status_a ────────────────────────────────────────────────────────


def set_object_c_status_a(
    object_c_id: str,
    reason: str = "",
) -> dict:
    """
    Set object_c to status_a and add negative value entries.

    Business rules enforced:
    - Cannot set to status_a an already-status_a object_c
    - Cannot set to status_a if any object_b is currently 'status_c' or 'status_d'
    - Eligible if ANY of:
        (a) object_c was created within the last 24 hours
        (b) at least one object_b is status_e
        (c) property_e is 'type_b'
        (d) object_c has property_g AND reason is covered
            (covered reasons: reason_a, reason_b, reason_c, reason_d, reason_e)
    Negative values: negative value entries added for all original positive values.
    """
    with get_conn() as conn:
        res = _load_res(conn, object_c_id)

        if res["status"] == "status_a":
            raise ValueError(f"ObjectC '{object_c_id}' is already status_a")

        # Cannot set to status_a with in-progress object_bs
        if _check_any_object_b_active(conn, object_c_id):
            raise ValueError(
                "Cannot set object_c to status_a: one or more object_bs are currently active "
                "(status 'status_c' or 'status_d')"
            )

        # Check eligibility
        created_at_str = res["created_at"]
        try:
            created_at = datetime.fromisoformat(created_at_str)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            hours_since_creation = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
        except (ValueError, TypeError):
            hours_since_creation = 999  # treat as old object_c if can't parse

        covered_reasons = {"reason_a", "reason_b", "reason_c", "reason_d", "reason_e"}
        eligible = (
            hours_since_creation <= 24
            or _check_any_object_b_status_e(conn, object_c_id)
            or res["property_e"] == "type_b"
            or (res["property_g"] == "yes" and reason.lower() in covered_reasons)
        )
        if not eligible:
            raise ValueError(
                "Status_a update not eligible. Status_a update is allowed when: "
                "(1) object_c created within last 24 hours, "
                "(2) any object_b is status_e, "
                "(3) type_b property_e, or "
                "(4) has property_g with a covered reason "
                f"(reason_a, reason_b, reason_c, reason_d, reason_e). "
                f"Current reason provided: '{reason}'"
            )

        # Add negative value entries for all original positive values
        values = conn.execute(
            "SELECT * FROM object_c_object_es WHERE object_c_id = ? AND amount > 0",
            (object_c_id,),
        ).fetchall()
        for ch in values:
            conn.execute(
                "INSERT INTO object_c_object_es (object_c_id, object_e_id, amount) VALUES (?, ?, ?)",
                (object_c_id, ch["object_e_id"], -ch["amount"]),
            )

        conn.execute(
            "UPDATE object_cs SET status = 'status_a' WHERE object_c_id = ?",
            (object_c_id,),
        )

        return _load_object_c_full(conn, object_c_id)


# ── Update ObjectC ObjectBs ────────────────────────────────────────────────


def update_object_c_object_bs(
    object_c_id: str,
    property_e: str,
    object_bs: List[Dict],
    object_e_id: str,
) -> dict:
    """
    Update the object_bs (and optionally property_e) of a object_c.

    Business rules enforced:
    - ObjectC must be active (not status_a)
    - type_c object_cs cannot be modified
    - Cannot change if any object_b is currently 'status_c' or 'status_d'
    - property_e must be valid
    - Cannot change object_a_property_1, object_a_property_2, or object_b_type
    - i_c object_es cannot be used for updates
    - i_b amount must cover the property_b difference
    - New object_bs must be available with sufficient property_a
    """
    if property_e not in ("type_b", "type_a", "type_c"):
        raise ValueError(f"Invalid property_e: {property_e!r}")

    with get_conn() as conn:
        res = _load_res(conn, object_c_id)

        if res["status"] == "status_a":
            raise ValueError(f"ObjectC '{object_c_id}' is status_a and cannot be modified")

        if res["property_e"] == "type_c":
            raise ValueError(
                "type_c object_cs cannot be modified. "
                "Please set to status_a and create a new object_c if you need to change your object_bs."
            )

        if _check_any_object_b_active(conn, object_c_id):
            raise ValueError(
                "Cannot modify object_c: one or more object_bs are currently active "
                "(status 'status_c' or 'status_d')"
            )

        property_id = res["property_id"]

        # Validate object_e
        oe_row = conn.execute(
            "SELECT * FROM object_es WHERE object_e_id = ? AND property_id = ?",
            (object_e_id, property_id),
        ).fetchone()
        if oe_row is None:
            raise LookupError(f"Object_e '{object_e_id}' not found for object_f '{property_id}'")
        if oe_row["property_i"] == "i_c":
            raise ValueError("i_c object_es cannot be used to modify object_cs")

        current_object_bs = conn.execute(
            "SELECT * FROM object_c_object_bs WHERE object_c_id = ?",
            (object_c_id,),
        ).fetchall()
        object_ds = conn.execute(
            "SELECT COUNT(*) as cnt FROM object_c_object_ds WHERE object_c_id = ?",
            (object_c_id,),
        ).fetchone()
        num_object_ds = object_ds["cnt"]

        # Calculate new total property_b
        total_property_b = 0
        new_object_b_records = []
        for fi in object_bs:
            fn = fi["object_b_number"]
            dt = fi["property_l"]

            # Reuse existing object_b's property_b if same object_b+property_l+property_e
            matching = None
            if property_e == res["property_e"]:
                matching = next(
                    (
                        cf
                        for cf in current_object_bs
                        if cf["object_b_number"] == fn and cf["property_l"] == dt
                    ),
                    None,
                )

            if matching:
                price = matching["property_b"]
                object_b_row = conn.execute(
                    "SELECT * FROM object_bs WHERE object_b_number = ?", (fn,)
                ).fetchone()
                new_object_b_records.append(
                    {
                        "object_b_number": fn,
                        "object_a_property_1": object_b_row["object_a_property_1"]
                        if object_b_row
                        else matching["object_a_property_1"],
                        "object_a_property_2": object_b_row["object_a_property_2"]
                        if object_b_row
                        else matching["object_a_property_2"],
                        "property_l": dt,
                        "property_b": price,
                    }
                )
            else:
                fd_row = _fd_row(conn, fn, dt)
                if fd_row["status"] != "status_a":
                    raise ValueError(f"ObjectB '{fn}' on {dt} is not available")
                seat_col = f"property_a_{property_e}"
                if fd_row[seat_col] < num_object_ds:
                    raise ValueError(f"Not enough {property_e} availability on object_b '{fn}' on {dt}")
                object_b_row = conn.execute(
                    "SELECT * FROM object_bs WHERE object_b_number = ?", (fn,)
                ).fetchone()
                if object_b_row is None:
                    raise LookupError(f"ObjectB '{fn}' not found")
                price = fd_row[f"property_b_{property_e}"]
                new_object_b_records.append(
                    {
                        "object_b_number": fn,
                        "object_a_property_1": object_b_row["object_a_property_1"],
                        "object_a_property_2": object_b_row["object_a_property_2"],
                        "property_l": dt,
                        "property_b": price,
                    }
                )
            total_property_b += price * num_object_ds

        old_price = sum(cf["property_b"] for cf in current_object_bs) * num_object_ds
        price_diff = total_property_b - old_price

        # Validate i_b amount
        if oe_row["property_i"] == "i_b" and oe_row["amount"] < price_diff:
            raise ValueError(
                f"i_b amount insufficient: available {oe_row['amount']}, "
                f"additional value {price_diff}"
            )

        # Add value entry for the difference
        if price_diff != 0:
            if oe_row["property_i"] == "i_b":
                conn.execute(
                    "UPDATE object_es SET amount = amount - ? WHERE object_e_id = ?",
                    (price_diff, object_e_id),
                )
            conn.execute(
                "INSERT INTO object_c_object_es (object_c_id, object_e_id, amount) VALUES (?, ?, ?)",
                (object_c_id, object_e_id, price_diff),
            )

        # Replace object_b rows
        conn.execute(
            "DELETE FROM object_c_object_bs WHERE object_c_id = ?",
            (object_c_id,),
        )
        for fr in new_object_b_records:
            conn.execute(
                """INSERT INTO object_c_object_bs
                   (object_c_id, object_b_number, object_a_property_1, object_a_property_2, property_l, property_b)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    object_c_id,
                    fr["object_b_number"],
                    fr["object_a_property_1"],
                    fr["object_a_property_2"],
                    fr["property_l"],
                    fr["property_b"],
                ),
            )

        # Update property_e
        conn.execute(
            "UPDATE object_cs SET property_e = ? WHERE object_c_id = ?",
            (property_e, object_c_id),
        )

        return _load_object_c_full(conn, object_c_id)


# ── Update ObjectC Baggages ───────────────────────────────────────────────


def update_object_c_baggages(
    object_c_id: str,
    property_f: int,
    property_h: int,
    object_e_id: str,
) -> dict:
    """
    Update property_h count on a object_c.

    Business rules enforced:
    - ObjectC must be active
    - property_h cannot decrease (can only increase)
    - property_f must be >= property_h
    - fee = 50 per additional property_h item
    - i_c object_es cannot be used
    - i_b amount must cover the value
    """
    if property_f < property_h:
        raise ValueError(
            f"property_f ({property_f}) cannot be less than property_h ({property_h})"
        )

    with get_conn() as conn:
        res = _load_res(conn, object_c_id)

        if res["status"] == "status_a":
            raise ValueError(f"ObjectC '{object_c_id}' is status_a")

        if property_h < res["property_h"]:
            raise ValueError(
                f"Cannot reduce property_h count. "
                f"Current: {res['property_h']}, requested: {property_h}. "
                "property_h can only be increased, not decreased."
            )

        property_id = res["property_id"]
        oe_row = conn.execute(
            "SELECT * FROM object_es WHERE object_e_id = ? AND property_id = ?",
            (object_e_id, property_id),
        ).fetchone()
        if oe_row is None:
            raise LookupError(f"Object_e '{object_e_id}' not found for object_f '{property_id}'")
        if oe_row["property_i"] == "i_c":
            raise ValueError("i_c object_es cannot be used to modify object_cs")

        additional_property_h = property_h - res["property_h"]
        value = 50 * additional_property_h

        if oe_row["property_i"] == "i_b" and oe_row["amount"] < value:
            raise ValueError(
                f"i_b amount insufficient: available {oe_row['amount']}, value {value}"
            )

        if value > 0:
            if oe_row["property_i"] == "i_b":
                conn.execute(
                    "UPDATE object_es SET amount = amount - ? WHERE object_e_id = ?",
                    (value, object_e_id),
                )
            conn.execute(
                "INSERT INTO object_c_object_es (object_c_id, object_e_id, amount) VALUES (?, ?, ?)",
                (object_c_id, object_e_id, value),
            )

        conn.execute(
            "UPDATE object_cs SET property_f = ?, property_h = ? WHERE object_c_id = ?",
            (property_f, property_h, object_c_id),
        )

        return _load_object_c_full(conn, object_c_id)


# ── Update ObjectC ObjectDs ─────────────────────────────────────────────


def update_object_c_object_ds(
    object_c_id: str,
    object_ds: List[Dict],
) -> dict:
    """
    Update object_d details on a object_c.

    Business rules enforced:
    - ObjectC must be active
    - Number of object_ds must match the original count (cannot add/remove object_ds)
    """
    with get_conn() as conn:
        res = _load_res(conn, object_c_id)

        if res["status"] == "status_a":
            raise ValueError(f"ObjectC '{object_c_id}' is status_a")

        current_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM object_c_object_ds WHERE object_c_id = ?",
            (object_c_id,),
        ).fetchone()["cnt"]

        if len(object_ds) != current_count:
            raise ValueError(
                f"ObjectD count cannot change. "
                f"Original: {current_count}, provided: {len(object_ds)}. "
                "You can only update object_d details, not add or remove object_ds."
            )

        conn.execute(
            "DELETE FROM object_c_object_ds WHERE object_c_id = ?",
            (object_c_id,),
        )
        for p in object_ds:
            conn.execute(
                """INSERT INTO object_c_object_ds
                   (object_c_id, property_n, property_o, property_m)
                   VALUES (?, ?, ?, ?)""",
                (object_c_id, p["property_n"], p["property_o"], p["property_m"]),
            )

        return _load_object_c_full(conn, object_c_id)
