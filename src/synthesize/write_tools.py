"""Canonical per-environment write-tool registry and success detection.

A *write tool* mutates database state; everything else is a read-only query.
This mapping is the single source of truth shared by the batch runner (to report
per-trajectory success) and the fidelity scripts (to compute the WO metric).

The sets mirror each environment's ``INTENT_TO_WRITE_TOOLS`` and are independent
of what the Generalist Populator happened to learn in a given run, so write
detection is correct even at ``K=0`` (no exploration).
"""

from __future__ import annotations

WRITE_TOOLS: dict[str, frozenset[str]] = {
    "airline": frozenset({
        "book_reservation", "cancel_reservation",
        "update_reservation_flights", "update_reservation_baggages",
        "update_reservation_passengers",
    }),
    "retail": frozenset({
        "create_order", "add_order_item", "add_payment_record",
        "update_order_status", "set_return_details", "set_exchange_details",
    }),
    "banking": frozenset({
        "open_account", "deposit", "withdraw", "transfer",
    }),
    "ecommerce": frozenset({
        "create_order", "add_order_item", "confirm_order",
        "cancel_order", "update_shipping_address", "restock_product",
    }),
    "pharmacy": frozenset({
        "create_prescription", "fill_prescription", "cancel_prescription",
    }),
    "forum": frozenset({
        "create_thread", "create_post", "close_thread",
    }),
    "university": frozenset({
        "enroll_student", "drop_student", "add_to_waitlist",
    }),
    "it_management": frozenset({
        "create_ticket", "assign_ticket", "resolve_ticket", "update_ticket",
    }),
    "cloud": frozenset({
        "create_vpc", "create_subnet", "create_security_group",
        "launch_instance", "start_instance", "stop_instance", "terminate_instance",
    }),
    "hr": frozenset({
        "create_employee", "update_job", "terminate_employee",
        "create_time_off_request", "approve_time_off_request",
        "create_requisition", "create_candidate", "create_application",
        "update_application", "create_offer", "update_offer", "update_review",
    }),
    "obfuscated_airline": frozenset({
        "book_object_c", "set_object_c_status_a",
        "update_object_c_object_bs", "update_object_c_baggages",
        "update_object_c_object_ds",
    }),
}


def write_tools_for(env: str) -> frozenset[str]:
    """Return the set of write-tool names for ``env`` (empty if unknown)."""
    return WRITE_TOOLS.get(env, frozenset())


def is_successful_write(tc: dict, write_tools: frozenset[str]) -> bool:
    """True iff tool call ``tc`` targets a write tool and did not error."""
    if tc.get("tool") not in write_tools:
        return False
    if tc.get("is_error", False):
        return False
    # Fallback for older trajectories that encoded errors in the result string.
    result = tc.get("result", "")
    if isinstance(result, str) and result.lower().startswith("error"):
        return False
    return True


def count_successful_writes(tool_calls: list[dict], env: str) -> int:
    """Count successful write operations in a trajectory's ``tool_calls``."""
    write_tools = write_tools_for(env)
    return sum(1 for tc in tool_calls if is_successful_write(tc, write_tools))
