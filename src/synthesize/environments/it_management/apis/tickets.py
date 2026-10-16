"""
IT Ticket CRUD API for IT Service Management environment.

Business rules enforced here (agent must satisfy all of them):
  - Priority must be one of: low, medium, high
  - Ticket raiser must be an active employee
  - Assignee must be an active IT-category employee
  - Assignee cannot be the ticket raiser (no self-assignment)
  - Ticket status machine: open → assigned → resolved
  - Only open/assigned tickets can be assigned
  - Only assigned tickets can be resolved
  - Resolution must be non-empty (≥ 20 chars)
  - Only the original raiser can delete; only open tickets can be deleted

Auto-managed fields (not exposed as agent parameters):
  status, created_date, assigned_date, resolved_date
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from synthesize.environments.it_management.db.db import get_conn

VALID_PRIORITIES = {"low", "medium", "high"}
VALID_STATUSES = {"open", "assigned", "resolved", "closed"}
MIN_RESOLUTION_LEN = 20


def _today() -> str:
    return datetime.date.today().isoformat()


# ── Read operations ────────────────────────────────────────────────────────────


def get_ticket(ticket_id: str) -> Dict[str, Any]:
    """Return the full record for a ticket.

    Raises LookupError if ticket not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM it_ticket WHERE ticket_id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise LookupError(f"Ticket not found: {ticket_id!r}")
    return dict(row)


def list_tickets_by_priority(priority: str) -> List[Dict[str, Any]]:
    """Return summary records for all tickets with the given priority.

    Raises ValueError if priority is invalid.
    """
    if priority not in VALID_PRIORITIES:
        raise ValueError(
            f"Invalid priority {priority!r}. Must be one of: {sorted(VALID_PRIORITIES)}"
        )
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT ticket_id, status, priority, raised_by_emp_id, assigned_emp_id, issue_title "
            "FROM it_ticket WHERE priority = ? ORDER BY ticket_id",
            (priority,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_tickets_raised_by(emp_id: str) -> List[Dict[str, Any]]:
    """Return all tickets raised by the given employee."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT ticket_id, status, priority, assigned_emp_id, issue_title, created_date "
            "FROM it_ticket WHERE raised_by_emp_id = ? ORDER BY ticket_id",
            (emp_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_tickets_assigned_to(emp_id: str) -> List[Dict[str, Any]]:
    """Return all tickets currently assigned to the given employee."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT ticket_id, status, priority, raised_by_emp_id, issue_title, assigned_date "
            "FROM it_ticket WHERE assigned_emp_id = ? ORDER BY ticket_id",
            (emp_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Write operations ───────────────────────────────────────────────────────────


def create_ticket(
    ticket_id: str,
    priority: str,
    raised_by_emp_id: str,
    issue_title: str,
    issue_description: str,
) -> Dict[str, Any]:
    """File a new IT ticket.

    Auto-sets: status='open', created_date=today, assigned_emp_id=NULL.

    Raises ValueError for invalid inputs.
    Raises LookupError if raised_by_emp_id is not a known active employee.
    """
    if not ticket_id or not ticket_id.strip():
        raise ValueError("ticket_id must be non-empty")
    if not issue_title or not issue_title.strip():
        raise ValueError("issue_title must be non-empty")
    if not issue_description or not issue_description.strip():
        raise ValueError("issue_description must be non-empty")
    if priority not in VALID_PRIORITIES:
        raise ValueError(
            f"Invalid priority {priority!r}. Must be one of: {sorted(VALID_PRIORITIES)}"
        )

    with get_conn() as conn:
        # Validate raiser
        raiser = conn.execute(
            "SELECT emp_id, is_active FROM employee WHERE emp_id = ?", (raised_by_emp_id,)
        ).fetchone()
        if raiser is None:
            raise LookupError(f"Employee not found: {raised_by_emp_id!r}")
        if not raiser["is_active"]:
            raise ValueError(f"Employee {raised_by_emp_id!r} is not active")

        # Check ticket_id uniqueness
        existing = conn.execute(
            "SELECT 1 FROM it_ticket WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if existing:
            raise ValueError(f"Ticket {ticket_id!r} already exists")

        today = _today()
        conn.execute(
            """INSERT INTO it_ticket
               (ticket_id, priority, status, raised_by_emp_id, assigned_emp_id,
                assigned_date, created_date, issue_title, issue_description, resolution, resolved_date)
               VALUES (?, ?, 'open', ?, NULL, NULL, ?, ?, ?, NULL, NULL)""",
            (
                ticket_id,
                priority,
                raised_by_emp_id,
                today,
                issue_title.strip(),
                issue_description.strip(),
            ),
        )
    return get_ticket(ticket_id)


def assign_ticket(ticket_id: str, emp_id: str) -> Dict[str, Any]:
    """Assign an open (or re-assign an already-assigned) ticket to an IT staff member.

    Auto-sets: status='assigned', assigned_date=today.

    Raises LookupError if ticket or employee not found.
    Raises ValueError if the ticket is already resolved/closed, the employee is not
    active IT staff, or the employee is the ticket raiser.
    """
    with get_conn() as conn:
        ticket = conn.execute(
            "SELECT * FROM it_ticket WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if ticket is None:
            raise LookupError(f"Ticket not found: {ticket_id!r}")
        if ticket["status"] in ("resolved", "closed"):
            raise ValueError(f"Cannot assign ticket {ticket_id!r}: status is {ticket['status']!r}")

        assignee = conn.execute(
            "SELECT emp_id, category, is_active FROM employee WHERE emp_id = ?", (emp_id,)
        ).fetchone()
        if assignee is None:
            raise LookupError(f"Employee not found: {emp_id!r}")
        if not assignee["is_active"]:
            raise ValueError(f"Employee {emp_id!r} is not active")
        if assignee["category"] != "IT":
            raise ValueError(
                f"Employee {emp_id!r} is not IT staff (category={assignee['category']!r})"
            )
        if emp_id == ticket["raised_by_emp_id"]:
            raise ValueError(
                f"Employee {emp_id!r} cannot be assigned their own ticket (self-assignment not allowed)"
            )

        conn.execute(
            "UPDATE it_ticket SET assigned_emp_id = ?, assigned_date = ?, status = 'assigned' WHERE ticket_id = ?",
            (emp_id, _today(), ticket_id),
        )
    return get_ticket(ticket_id)


def update_ticket(
    ticket_id: str,
    priority: Optional[str] = None,
    issue_title: Optional[str] = None,
    issue_description: Optional[str] = None,
) -> Dict[str, Any]:
    """Update mutable fields of a ticket (priority, issue_title, issue_description).

    Cannot update resolved or closed tickets.
    Raises LookupError if ticket not found.
    Raises ValueError if no fields provided, ticket is resolved/closed, or priority is invalid.
    """
    if priority is None and issue_title is None and issue_description is None:
        raise ValueError(
            "At least one of priority, issue_title, or issue_description must be provided"
        )
    if priority is not None and priority not in VALID_PRIORITIES:
        raise ValueError(
            f"Invalid priority {priority!r}. Must be one of: {sorted(VALID_PRIORITIES)}"
        )

    with get_conn() as conn:
        ticket = conn.execute(
            "SELECT status FROM it_ticket WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if ticket is None:
            raise LookupError(f"Ticket not found: {ticket_id!r}")
        if ticket["status"] in ("resolved", "closed"):
            raise ValueError(f"Cannot update ticket {ticket_id!r}: status is {ticket['status']!r}")

        updates = []
        values = []
        if priority is not None:
            updates.append("priority = ?")
            values.append(priority)
        if issue_title is not None:
            if not issue_title.strip():
                raise ValueError("issue_title must be non-empty")
            updates.append("issue_title = ?")
            values.append(issue_title.strip())
        if issue_description is not None:
            if not issue_description.strip():
                raise ValueError("issue_description must be non-empty")
            updates.append("issue_description = ?")
            values.append(issue_description.strip())

        values.append(ticket_id)
        conn.execute(f"UPDATE it_ticket SET {', '.join(updates)} WHERE ticket_id = ?", values)

    return get_ticket(ticket_id)


def resolve_ticket(ticket_id: str, resolution: str) -> Dict[str, Any]:
    """Mark a ticket as resolved with the provided resolution text.

    Auto-sets: status='resolved', resolved_date=today.

    Raises LookupError if ticket not found.
    Raises ValueError if ticket is not in 'assigned' status or resolution is too short.
    """
    if not resolution or len(resolution.strip()) < MIN_RESOLUTION_LEN:
        raise ValueError(
            f"Resolution must be at least {MIN_RESOLUTION_LEN} characters. "
            f"Got {len((resolution or '').strip())} chars."
        )

    with get_conn() as conn:
        ticket = conn.execute(
            "SELECT status FROM it_ticket WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if ticket is None:
            raise LookupError(f"Ticket not found: {ticket_id!r}")
        if ticket["status"] != "assigned":
            raise ValueError(
                f"Cannot resolve ticket {ticket_id!r}: must be in 'assigned' status, "
                f"but status is {ticket['status']!r}"
            )

        conn.execute(
            "UPDATE it_ticket SET resolution = ?, resolved_date = ?, status = 'resolved' WHERE ticket_id = ?",
            (resolution.strip(), _today(), ticket_id),
        )
    return get_ticket(ticket_id)


def delete_ticket(ticket_id: str, emp_id: str) -> Dict[str, Any]:
    """Delete a ticket. Only the original raiser may delete; only open tickets may be deleted.

    Returns the deleted ticket record.
    Raises LookupError if ticket not found.
    Raises ValueError if caller is not the raiser or ticket is not open.
    """
    with get_conn() as conn:
        ticket = conn.execute(
            "SELECT * FROM it_ticket WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if ticket is None:
            raise LookupError(f"Ticket not found: {ticket_id!r}")
        if ticket["raised_by_emp_id"] != emp_id:
            raise ValueError(
                f"Only the original raiser ({ticket['raised_by_emp_id']!r}) can delete ticket {ticket_id!r}"
            )
        if ticket["status"] != "open":
            raise ValueError(
                f"Cannot delete ticket {ticket_id!r}: only open tickets may be deleted "
                f"(status is {ticket['status']!r})"
            )
        deleted = dict(ticket)
        conn.execute("DELETE FROM it_ticket WHERE ticket_id = ?", (ticket_id,))
    return deleted
