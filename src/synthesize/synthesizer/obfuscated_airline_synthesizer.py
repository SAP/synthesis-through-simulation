"""
Obfuscated Airline synthesizer.

Uses the same domain as Airline but with all semantic names removed —
tables, columns, and values are replaced with generic identifiers (object_X,
property_Y, etc.).  Exposes TOOL_REGISTRY for GeneralistPopulatorSynthesizer.
"""

from __future__ import annotations

from typing import Dict

from synthesize.environments.obfuscated_airline.apis import f as f_api
from synthesize.environments.obfuscated_airline.apis import p as p_api
from synthesize.environments.obfuscated_airline.apis import r as r_api
from synthesize.environments.obfuscated_airline.apis import u as u_api

TOOL_REGISTRY: Dict[str, dict] = {
    # ── Object_f (user) lookups ───────────────────────────────────────────────
    "get_object_f_details": {
        "fn": u_api.get_object_f_details,
        "description": "Get full details for an object_f by property_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string", "description": "Object_f identifier"},
            },
            "required": ["property_id"],
        },
    },
    "list_object_fs": {
        "fn": u_api.list_object_fs,
        "description": "List object_fs with optional property_q filter.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_q": {
                    "type": "string",
                    "enum": ["value_g", "value_s", "value_r"],
                    "description": "Optional property_q filter",
                },
            },
            "required": [],
        },
    },
    "get_saved_object_ds": {
        "fn": u_api.get_saved_object_ds,
        "description": "Get saved object_d profiles for an object_f.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string"},
            },
            "required": ["property_id"],
        },
    },
    # ── Object_e (payment) lookups ────────────────────────────────────────────
    "get_object_es": {
        "fn": p_api.get_object_es,
        "description": "List all object_es for an object_f.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string"},
            },
            "required": ["property_id"],
        },
    },
    "send_type_c": {
        "fn": p_api.send_type_c,
        "description": "Issue a type_c object_e for an object_f. Standard amounts: 50, 100, 200.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string"},
                "amount": {"type": "integer"},
            },
            "required": ["property_id", "amount"],
        },
    },
    # ── Object_b (flight) lookups ─────────────────────────────────────────────
    "list_all_object_as": {
        "fn": f_api.list_all_object_as,
        "description": "List all object_a codes and names.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "search_object_b": {
        "fn": f_api.search_object_b,
        "description": "Search for object_bs between two object_as on a property_l.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_a_property_1": {"type": "string"},
                "object_a_property_2": {"type": "string"},
                "property_l": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["object_a_property_1", "object_a_property_2", "property_l"],
        },
    },
    "search_object_b_pairs": {
        "fn": f_api.search_object_b_pairs,
        "description": "Search for connecting object_b pairs between two object_as on a property_l.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_a_property_1": {"type": "string"},
                "object_a_property_2": {"type": "string"},
                "property_l": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["object_a_property_1", "object_a_property_2", "property_l"],
        },
    },
    "get_object_b_status": {
        "fn": f_api.get_object_b_status,
        "description": "Get status and availability for a specific object_b on a property_l.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_b_number": {"type": "string"},
                "property_l": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["object_b_number", "property_l"],
        },
    },
    # ── Object_c (reservation) read ───────────────────────────────────────────
    "get_object_c_details": {
        "fn": r_api.get_object_c_details,
        "description": "Get full details for an object_c by object_c_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_c_id": {"type": "string"},
            },
            "required": ["object_c_id"],
        },
    },
    "list_object_cs": {
        "fn": r_api.list_object_cs,
        "description": "List object_cs for an object_f. Optionally filter by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["active", "status_a"],
                    "description": "Filter by status",
                },
            },
            "required": [],
        },
    },
    # ── Object_c (reservation) write ──────────────────────────────────────────
    "book_object_c": {
        "fn": r_api.book_object_c,
        "description": (
            "Create a new object_c. "
            "Requires: property_id, object_a_property_1/2, object_b_type, property_e, "
            "object_bs (list of {object_b_number, property_l, property_b}), "
            "object_ds (list of {property_n, property_o, property_m}), "
            "object_es (list of {object_e_id, amount}), property_f, property_h, property_g."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string"},
                "object_a_property_1": {"type": "string"},
                "object_a_property_2": {"type": "string"},
                "object_b_type": {"type": "string", "enum": ["option_a", "option_b"]},
                "property_e": {"type": "string", "enum": ["type_b", "type_a", "type_c"]},
                "object_bs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "object_b_number": {"type": "string"},
                            "object_a_property_1": {"type": "string"},
                            "object_a_property_2": {"type": "string"},
                            "property_l": {"type": "string"},
                            "property_b": {"type": "integer"},
                        },
                        "required": ["object_b_number", "object_a_property_1", "object_a_property_2", "property_l", "property_b"],
                    },
                },
                "object_ds": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "property_n": {"type": "string"},
                            "property_o": {"type": "string"},
                            "property_m": {"type": "string", "description": "YYYY-MM-DD"},
                        },
                        "required": ["property_n", "property_o", "property_m"],
                    },
                },
                "object_es": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "object_e_id": {"type": "string"},
                            "amount": {"type": "integer"},
                        },
                        "required": ["object_e_id", "amount"],
                    },
                },
                "property_f": {"type": "integer"},
                "property_h": {"type": "integer"},
                "property_g": {"type": "string", "enum": ["yes", "no"]},
            },
            "required": [
                "property_id",
                "object_a_property_1",
                "object_a_property_2",
                "object_b_type",
                "property_e",
                "object_bs",
                "object_ds",
                "object_es",
                "property_f",
                "property_h",
                "property_g",
            ],
        },
    },
    "set_object_c_status_a": {
        "fn": r_api.set_object_c_status_a,
        "description": "Set an object_c status to status_a (cancel it) and process refunds.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_c_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["object_c_id"],
        },
    },
    "update_object_c_object_bs": {
        "fn": r_api.update_object_c_object_bs,
        "description": "Update the object_bs (and optionally property_e) of an active object_c.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_c_id": {"type": "string"},
                "property_e": {"type": "string", "enum": ["type_b", "type_a", "type_c"]},
                "object_bs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "object_b_number": {"type": "string"},
                            "property_l": {"type": "string"},
                        },
                        "required": ["object_b_number", "property_l"],
                    },
                },
                "object_e_id": {"type": "string"},
            },
            "required": ["object_c_id", "property_e", "object_bs", "object_e_id"],
        },
    },
    "update_object_c_baggages": {
        "fn": r_api.update_object_c_baggages,
        "description": "Add property_f/property_h to an object_c. Can only increase, not decrease.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_c_id": {"type": "string"},
                "property_f": {"type": "integer"},
                "property_h": {"type": "integer"},
                "object_e_id": {"type": "string"},
            },
            "required": ["object_c_id", "property_f", "property_h", "object_e_id"],
        },
    },
    "update_object_c_object_ds": {
        "fn": r_api.update_object_c_object_ds,
        "description": "Update object_d details on an object_c. Count cannot change.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_c_id": {"type": "string"},
                "object_ds": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "property_n": {"type": "string"},
                            "property_o": {"type": "string"},
                            "property_m": {"type": "string"},
                        },
                        "required": ["property_n", "property_o", "property_m"],
                    },
                },
            },
            "required": ["object_c_id", "object_ds"],
        },
    },
    "calculate": {
        "fn": lambda expression: {"result": eval(expression, {"__builtins__": {}})},  # noqa: PGH001
        "description": "Evaluate a simple arithmetic expression.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string"},
            },
            "required": ["expression"],
        },
    },
}
