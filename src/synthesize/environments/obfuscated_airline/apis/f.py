"""
ObjectBs API for the Generic environment.
Adapted from the external mock_system/apis/object_bs.py.
Returns plain dicts (JSON-serialisable).
"""

from __future__ import annotations

from synthesize.environments.obfuscated_airline.db.db import get_conn

OBJECT_AS = [
    {"code": "NAME_A", "name": "Name A"},
    {"code": "NAME_B", "name": "Name B"},
    {"code": "NAME_C", "name": "Name C"},
    {"code": "NAME_D", "name": "Name D"},
    {"code": "NAME_E", "name": "Name E"},
    {"code": "NAME_F", "name": "Name F"},
    {"code": "NAME_G", "name": "Name G"},
    {"code": "NAME_H", "name": "Name H"},
]

OBJECT_B_DATE_STATUSES = ("status_a", "status_b", "status_c", "status_d", "status_e", "status_f")


def list_all_object_as() -> list[dict]:
    """List all supported object_a codes and names."""
    return OBJECT_AS


def get_object_b_status(object_b_number: str, property_l: str) -> dict:
    """Get the status of a specific object_b for a given property_l."""
    with get_conn() as conn:
        object_b = conn.execute(
            "SELECT * FROM object_bs WHERE object_b_number = ?", (object_b_number,)
        ).fetchone()
        if object_b is None:
            raise LookupError(f"ObjectB '{object_b_number}' not found")

        fd = conn.execute(
            "SELECT * FROM object_b_property_ls WHERE object_b_number = ? AND property_l = ?",
            (object_b_number, property_l),
        ).fetchone()
        if fd is None:
            raise LookupError(f"No data for object_b '{object_b_number}' for {property_l}")

    return {
        "object_b_number": object_b_number,
        "object_a_property_1": object_b["object_a_property_1"],
        "object_a_property_2": object_b["object_a_property_2"],
        "property_l": property_l,
        "status": fd["status"],
        "scheduled_property_c": object_b["scheduled_property_c"],
        "scheduled_property_d": object_b["scheduled_property_d"],
        "property_a_available": {
            "type_b": fd["property_a_type_b"],
            "type_a": fd["property_a_type_a"],
            "type_c": fd["property_a_type_c"],
        },
        "property_b": {
            "type_b": fd["property_b_type_b"],
            "type_a": fd["property_b_type_a"],
            "type_c": fd["property_b_type_c"],
        },
    }


def search_object_b(
    object_a_property_1: str,
    object_a_property_2: str,
    property_l: str,
) -> list[dict]:
    """
    Search for object_bs with two object_as for a given property_l.

    Returns object_bs with status='status_a' and their property_a/property_b info.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT f.object_b_number, f.object_a_property_1, f.object_a_property_2,
                   f.scheduled_property_c, f.scheduled_property_d,
                   fd.property_l, fd.status,
                   fd.property_a_type_b, fd.property_a_type_a, fd.property_a_type_c,
                   fd.property_b_type_b, fd.property_b_type_a, fd.property_b_type_c
            FROM object_bs f
            JOIN object_b_property_ls fd ON f.object_b_number = fd.object_b_number
            WHERE f.object_a_property_1 = ?
              AND f.object_a_property_2 = ?
              AND fd.property_l = ?
              AND fd.status = 'status_a'
            ORDER BY f.scheduled_property_c
            """,
            (object_a_property_1, object_a_property_2, property_l),
        ).fetchall()

    return [
        {
            "object_b_number": r["object_b_number"],
            "object_a_property_1": r["object_a_property_1"],
            "object_a_property_2": r["object_a_property_2"],
            "property_l": r["property_l"],
            "status": r["status"],
            "scheduled_property_c": r["scheduled_property_c"],
            "scheduled_property_d": r["scheduled_property_d"],
            "property_a_available": {
                "type_b": r["property_a_type_b"],
                "type_a": r["property_a_type_a"],
                "type_c": r["property_a_type_c"],
            },
            "property_b": {
                "type_b": r["property_b_type_b"],
                "type_a": r["property_b_type_a"],
                "type_c": r["property_b_type_c"],
            },
        }
        for r in rows
    ]


def search_object_b_pairs(
    object_a_property_1: str,
    object_a_property_2: str,
    property_l: str,
) -> list[dict]:
    """
    Search for object_b pairs for a given property_l.

    Returns pairs as [{"object_b_1": {...}, "object_b_2": {...}}, ...].
    """
    with get_conn() as conn:
        part1_rows = conn.execute(
            """
            SELECT f.object_b_number, f.object_a_property_1, f.object_a_property_2,
                   f.scheduled_property_c, f.scheduled_property_d,
                   fd.property_a_type_b, fd.property_a_type_a, fd.property_a_type_c,
                   fd.property_b_type_b, fd.property_b_type_a, fd.property_b_type_c
            FROM object_bs f
            JOIN object_b_property_ls fd ON f.object_b_number = fd.object_b_number
            WHERE f.object_a_property_1 = ?
              AND fd.property_l = ?
              AND fd.status = 'status_a'
            ORDER BY f.scheduled_property_c
            """,
            (object_a_property_1, property_l),
        ).fetchall()

    results = []
    for part1 in part1_rows:
        via_object_a = part1["object_a_property_2"]
        if via_object_a == object_a_property_2:
            continue  # skip same-endpoint

        arrival = part1["scheduled_property_d"]
        part2_property_l = property_l
        if "+1" in arrival:
            from datetime import date as _date
            from datetime import timedelta

            d = _date.fromisoformat(property_l)
            part2_property_l = (d + timedelta(days=1)).isoformat()
            arrival = arrival.replace("+1", "").strip()

        part2_object_bs = search_object_b(
            object_a_property_1=via_object_a,
            object_a_property_2=object_a_property_2,
            property_l=part2_property_l,
        )
        for part2 in part2_object_bs:
            if part2["scheduled_property_c"] >= arrival:
                results.append(
                    {
                        "object_b_1": {
                            "object_b_number": part1["object_b_number"],
                            "object_a_property_1": part1["object_a_property_1"],
                            "object_a_property_2": part1["object_a_property_2"],
                            "property_l": property_l,
                            "scheduled_property_c": part1["scheduled_property_c"],
                            "scheduled_property_d": part1["scheduled_property_d"],
                            "property_b": {
                                "type_b": part1["property_b_type_b"],
                                "type_a": part1["property_b_type_a"],
                                "type_c": part1["property_b_type_c"],
                            },
                        },
                        "object_b_2": part2,
                    }
                )

    return results
