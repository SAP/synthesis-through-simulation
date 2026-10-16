"""
IT Service Management synthesizers.

ITAgentSynthesizer  — LLM agent executes IT ticket intents via IT Service Management APIs.
ITDirectSynthesizer — Programmatic synthesizer that bypasses rules (creates intentional violations).

Both are auto-discovered by synthesis_runner.py since they subclass Synthesizer and
live in synthesize/synthesizer/.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from synthesize.environments.it_management.apis import employees, tickets
from synthesize.environments.it_management.db.db import get_conn
from synthesize.synthesizer.agent_synthesizer import IntentDef, Step
from synthesize.synthesizer.base import SynthesisResult, Synthesizer
from synthesize.synthesizer.default_agent import DefaultAgentSynthesizer

# ── Tool registry ─────────────────────────────────────────────────────────────

IT_TOOL_REGISTRY: Dict[str, dict] = {
    # ── Employee lookups ─────────────────────────────────────────────────────
    "list_employees": {
        "fn": employees.list_employees,
        "description": "List all active employees with emp_id, name, email, category, and level.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "list_it_staff": {
        "fn": employees.list_it_staff,
        "description": "List all active IT-category employees. Only these employees can be assigned tickets.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "get_employee": {
        "fn": employees.get_employee,
        "description": "Get full details for a single employee by emp_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "emp_id": {"type": "string", "description": "Employee ID, e.g. 'emp_0431'"},
            },
            "required": ["emp_id"],
        },
    },
    "get_employee_by_email": {
        "fn": employees.get_employee_by_email,
        "description": "Look up an employee's emp_id by their email address.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Employee email address"},
            },
            "required": ["email"],
        },
    },
    # ── Ticket read ──────────────────────────────────────────────────────────
    "get_ticket": {
        "fn": tickets.get_ticket,
        "description": "Get the full record for a ticket by ticket_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket ID, e.g. 'TKT-001'"},
            },
            "required": ["ticket_id"],
        },
    },
    "list_tickets_by_priority": {
        "fn": tickets.list_tickets_by_priority,
        "description": "List all tickets with the given priority (low/medium/high).",
        "input_schema": {
            "type": "object",
            "properties": {
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Ticket priority",
                },
            },
            "required": ["priority"],
        },
    },
    "list_tickets_raised_by": {
        "fn": tickets.list_tickets_raised_by,
        "description": "List all tickets raised by the given employee.",
        "input_schema": {
            "type": "object",
            "properties": {
                "emp_id": {"type": "string", "description": "Employee ID of the ticket raiser"},
            },
            "required": ["emp_id"],
        },
    },
    "list_tickets_assigned_to": {
        "fn": tickets.list_tickets_assigned_to,
        "description": "List all tickets currently assigned to the given employee.",
        "input_schema": {
            "type": "object",
            "properties": {
                "emp_id": {"type": "string", "description": "Employee ID of the assignee"},
            },
            "required": ["emp_id"],
        },
    },
    # ── Ticket write ─────────────────────────────────────────────────────────
    "create_ticket": {
        "fn": tickets.create_ticket,
        "description": (
            "File a new IT support ticket. "
            "Auto-sets status='open', created_date=today. "
            "The raiser must be an active employee. ticket_id must be unique."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Unique ticket ID, e.g. 'TKT-001'"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Ticket priority",
                },
                "raised_by_emp_id": {
                    "type": "string",
                    "description": "emp_id of the employee filing the ticket",
                },
                "issue_title": {
                    "type": "string",
                    "description": "Short summary of the issue (non-empty)",
                },
                "issue_description": {
                    "type": "string",
                    "description": "Full description of the issue (non-empty)",
                },
            },
            "required": [
                "ticket_id",
                "priority",
                "raised_by_emp_id",
                "issue_title",
                "issue_description",
            ],
        },
    },
    "assign_ticket": {
        "fn": tickets.assign_ticket,
        "description": (
            "Assign an open ticket to an IT staff member. "
            "Auto-sets status='assigned', assigned_date=today. "
            "Assignee must be active IT-category staff and cannot be the ticket raiser."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket ID to assign"},
                "emp_id": {
                    "type": "string",
                    "description": "emp_id of the IT staff member to assign",
                },
            },
            "required": ["ticket_id", "emp_id"],
        },
    },
    "update_ticket": {
        "fn": tickets.update_ticket,
        "description": "Update priority, issue_title, and/or issue_description of an open or assigned ticket.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket ID to update"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "New priority (optional)",
                },
                "issue_title": {"type": "string", "description": "New issue title (optional)"},
                "issue_description": {
                    "type": "string",
                    "description": "New issue description (optional)",
                },
            },
            "required": ["ticket_id"],
        },
    },
    "resolve_ticket": {
        "fn": tickets.resolve_ticket,
        "description": (
            "Mark an assigned ticket as resolved. "
            "Auto-sets status='resolved', resolved_date=today. "
            "Resolution text must be at least 20 characters. "
            "Ticket must be in 'assigned' status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket ID to resolve"},
                "resolution": {
                    "type": "string",
                    "description": "Resolution text (≥ 20 characters)",
                },
            },
            "required": ["ticket_id", "resolution"],
        },
    },
    "delete_ticket": {
        "fn": tickets.delete_ticket,
        "description": "Delete an open ticket. Only the original raiser may delete; only open tickets can be deleted.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket ID to delete"},
                "emp_id": {
                    "type": "string",
                    "description": "emp_id of the employee requesting deletion (must be the raiser)",
                },
            },
            "required": ["ticket_id", "emp_id"],
        },
    },
}


# ── Samplers ──────────────────────────────────────────────────────────────────


def _sample_employee(category: Optional[str] = None) -> Optional[dict]:
    """Return a random active employee record (optionally filtered by category)."""
    with get_conn() as conn:
        if category:
            rows = conn.execute(
                "SELECT emp_id, name, email FROM employee WHERE is_active = 1 AND category = ? ORDER BY RANDOM() LIMIT 1",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT emp_id, name, email FROM employee WHERE is_active = 1 ORDER BY RANDOM() LIMIT 1"
            ).fetchall()
    return dict(rows[0]) if rows else None


def _next_ticket_id() -> str:
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM it_ticket").fetchone()[0]
    return f"TKT-{count + 1:04d}"


def _sample_open_ticket() -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT ticket_id, raised_by_emp_id FROM it_ticket WHERE status = 'open' ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def _sample_assigned_ticket() -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT ticket_id, raised_by_emp_id, assigned_emp_id FROM it_ticket WHERE status = 'assigned' ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


# ── Postconditions ────────────────────────────────────────────────────────────


def _find_tool_call(steps: List[Step], tool_name: str) -> Optional[Step]:
    return next((s for s in reversed(steps) if s.tool == tool_name and not s.is_error), None)


def _postcond_file_ticket(params: dict, steps: List[Step]) -> Dict[str, bool]:
    ticket_id = params.get("ticket_id")
    create_step = _find_tool_call(steps, "create_ticket")
    if not create_step:
        return {"create_ticket_called": False}
    # Verify ticket exists in DB with status='open'
    try:
        t = tickets.get_ticket(ticket_id)
        return {
            "create_ticket_called": True,
            "ticket_exists": True,
            "status_is_open": t["status"] == "open",
        }
    except LookupError:
        return {"create_ticket_called": True, "ticket_exists": False, "status_is_open": False}


def _postcond_assign_ticket(params: dict, steps: List[Step]) -> Dict[str, bool]:
    ticket_id = params.get("ticket_id")
    assign_step = _find_tool_call(steps, "assign_ticket")
    if not assign_step:
        return {"assign_ticket_called": False}
    try:
        t = tickets.get_ticket(ticket_id)
        return {
            "assign_ticket_called": True,
            "ticket_exists": True,
            "status_is_assigned": t["status"] == "assigned",
            "has_assignee": t["assigned_emp_id"] is not None,
        }
    except LookupError:
        return {
            "assign_ticket_called": True,
            "ticket_exists": False,
            "status_is_assigned": False,
            "has_assignee": False,
        }


def _postcond_resolve_ticket(params: dict, steps: List[Step]) -> Dict[str, bool]:
    ticket_id = params.get("ticket_id")
    resolve_step = _find_tool_call(steps, "resolve_ticket")
    if not resolve_step:
        return {"resolve_ticket_called": False}
    try:
        t = tickets.get_ticket(ticket_id)
        return {
            "resolve_ticket_called": True,
            "ticket_exists": True,
            "status_is_resolved": t["status"] == "resolved",
            "has_resolution": bool(t.get("resolution")),
            "has_resolved_date": t["resolved_date"] is not None,
        }
    except LookupError:
        return {
            "resolve_ticket_called": True,
            "ticket_exists": False,
            "status_is_resolved": False,
            "has_resolution": False,
            "has_resolved_date": False,
        }


def _postcond_full_lifecycle(params: dict, steps: List[Step]) -> Dict[str, bool]:
    ticket_id = params.get("ticket_id")
    created = _find_tool_call(steps, "create_ticket") is not None
    assigned = _find_tool_call(steps, "assign_ticket") is not None
    resolved = _find_tool_call(steps, "resolve_ticket") is not None
    if not created:
        return {
            "create_ticket_called": False,
            "assign_ticket_called": False,
            "resolve_ticket_called": False,
        }
    try:
        t = tickets.get_ticket(ticket_id)
        return {
            "create_ticket_called": created,
            "assign_ticket_called": assigned,
            "resolve_ticket_called": resolved,
            "final_status_resolved": t["status"] == "resolved",
        }
    except LookupError:
        return {
            "create_ticket_called": created,
            "assign_ticket_called": assigned,
            "resolve_ticket_called": resolved,
            "final_status_resolved": False,
        }


def _postcond_escalate_ticket(params: dict, steps: List[Step]) -> Dict[str, bool]:
    ticket_id = params.get("ticket_id")
    update_step = _find_tool_call(steps, "update_ticket")
    if not update_step:
        return {"update_ticket_called": False}
    try:
        t = tickets.get_ticket(ticket_id)
        return {
            "update_ticket_called": True,
            "ticket_exists": True,
            "priority_is_high": t["priority"] == "high",
        }
    except LookupError:
        return {"update_ticket_called": True, "ticket_exists": False, "priority_is_high": False}


def _postcond_reassign_ticket(params: dict, steps: List[Step]) -> Dict[str, bool]:
    ticket_id = params.get("ticket_id")
    new_assignee = params.get("new_assignee_emp_id")
    assign_step = _find_tool_call(steps, "assign_ticket")
    if not assign_step:
        return {"assign_ticket_called": False}
    try:
        t = tickets.get_ticket(ticket_id)
        return {
            "assign_ticket_called": True,
            "ticket_exists": True,
            "status_is_assigned": t["status"] == "assigned",
            "reassigned_to_new_emp": new_assignee is not None
            and t["assigned_emp_id"] == new_assignee,
        }
    except LookupError:
        return {
            "assign_ticket_called": True,
            "ticket_exists": False,
            "status_is_assigned": False,
            "reassigned_to_new_emp": False,
        }


# ── Intent definitions ────────────────────────────────────────────────────────

IT_INTENTS: Dict[str, IntentDef] = {}

IT_INTENTS["FILE_TICKET"] = IntentDef(
    name="FILE_TICKET",
    brief="An employee files a new IT support ticket with appropriate priority.",
    informed_rules=(
        "Business rules:\n"
        "1. ticket_id must be unique — use list_tickets_raised_by or get_ticket to check, "
        "or pick a unique ID yourself.\n"
        "2. priority must be one of: low, medium, high.\n"
        "3. raised_by_emp_id must be an active employee — use list_employees to find one.\n"
        "4. issue_title and issue_description must be non-empty.\n"
        "5. The ticket is created with status='open' and no assignee automatically.\n"
    ),
    tools=["list_employees", "list_tickets_raised_by", "create_ticket"],
    sampler=lambda: (
        lambda emp: (
            None
            if emp is None
            else {
                "ticket_id": _next_ticket_id(),
                "raiser": emp,
            }
        )
    )(_sample_employee()),
    task_prompt=lambda p: (
        f"File a new IT support ticket on behalf of {p['raiser']['name']} "
        f"({p['raiser']['emp_id']}). "
        f"Use ticket ID {p['ticket_id']}. "
        "Choose an appropriate priority and describe a realistic IT issue."
    ),
    postconditions=_postcond_file_ticket,
)

IT_INTENTS["ASSIGN_TICKET"] = IntentDef(
    name="ASSIGN_TICKET",
    brief="Assign an open IT ticket to an appropriate IT staff member.",
    informed_rules=(
        "Business rules:\n"
        "1. The assignee must be an active IT-category employee — use list_it_staff.\n"
        "2. The assignee cannot be the same person who raised the ticket (no self-assignment).\n"
        "3. Only open or already-assigned tickets can be (re)assigned.\n"
        "4. assigned_date and status='assigned' are set automatically.\n"
    ),
    tools=["list_it_staff", "get_ticket", "list_tickets_by_priority", "assign_ticket"],
    sampler=lambda: (lambda t: None if t is None else {**t})(_sample_open_ticket()),
    task_prompt=lambda p: (
        f"Assign ticket {p['ticket_id']} to an appropriate IT staff member. "
        "Check the ticket details first, then pick a suitable IT employee who is not the ticket raiser."
    ),
    postconditions=_postcond_assign_ticket,
)

IT_INTENTS["RESOLVE_TICKET"] = IntentDef(
    name="RESOLVE_TICKET",
    brief="Resolve an assigned IT ticket with a detailed resolution.",
    informed_rules=(
        "Business rules:\n"
        "1. Only tickets with status='assigned' can be resolved.\n"
        "2. The resolution text must be at least 20 characters.\n"
        "3. resolved_date and status='resolved' are set automatically.\n"
    ),
    tools=["get_ticket", "list_tickets_assigned_to", "resolve_ticket"],
    sampler=lambda: (lambda t: None if t is None else {**t})(_sample_assigned_ticket()),
    task_prompt=lambda p: (
        f"Resolve ticket {p['ticket_id']}. "
        "Check the ticket details first, then provide a detailed resolution describing how the issue was fixed."
    ),
    postconditions=_postcond_resolve_ticket,
)

IT_INTENTS["ESCALATE_TICKET"] = IntentDef(
    name="ESCALATE_TICKET",
    brief="Escalate an open or assigned ticket by raising its priority to high.",
    informed_rules=(
        "Business rules:\n"
        "1. Resolved or closed tickets cannot be updated.\n"
        "2. priority must be one of: low, medium, high.\n"
    ),
    tools=["get_ticket", "list_tickets_by_priority", "update_ticket"],
    sampler=lambda: (lambda t: None if t is None else {**t})(_sample_open_ticket()),
    task_prompt=lambda p: (
        f"Escalate ticket {p['ticket_id']} to high priority. "
        "Check the current ticket details first, then update the priority."
    ),
    postconditions=_postcond_escalate_ticket,
)

IT_INTENTS["REASSIGN_TICKET"] = IntentDef(
    name="REASSIGN_TICKET",
    brief="Reassign an already-assigned ticket to a different IT staff member.",
    informed_rules=(
        "Business rules:\n"
        "1. The new assignee must be an active IT-category employee.\n"
        "2. The new assignee cannot be the original ticket raiser.\n"
        "3. Only tickets in open or assigned status can be (re)assigned.\n"
    ),
    tools=["get_ticket", "list_it_staff", "assign_ticket"],
    sampler=lambda: (
        lambda t: (
            None
            if t is None
            else {
                **t,
                "new_assignee_emp_id": None,  # agent picks the new assignee
            }
        )
    )(_sample_assigned_ticket()),
    task_prompt=lambda p: (
        f"Reassign ticket {p['ticket_id']} (currently assigned to {p.get('assigned_emp_id', 'someone')}) "
        "to a different IT staff member. "
        "Check the ticket first, then pick a different IT employee who is not the ticket raiser."
    ),
    postconditions=_postcond_reassign_ticket,
)

IT_INTENTS["FULL_LIFECYCLE"] = IntentDef(
    name="FULL_LIFECYCLE",
    brief="Complete the full ticket lifecycle: file a new ticket, assign it, then resolve it.",
    informed_rules=(
        "Business rules:\n"
        "1. First create a ticket (status becomes 'open').\n"
        "2. Then assign it to an IT staff member (not the raiser) — status becomes 'assigned'.\n"
        "3. Finally resolve it with a detailed resolution (≥ 20 chars) — status becomes 'resolved'.\n"
        "4. priority must be one of: low, medium, high.\n"
        "5. All raised_by_emp_id and assigned emp_id values must be active employees.\n"
    ),
    tools=["list_employees", "list_it_staff", "create_ticket", "assign_ticket", "resolve_ticket"],
    sampler=lambda: (
        lambda emp: (
            None
            if emp is None
            else {
                "ticket_id": _next_ticket_id(),
                "raiser": emp,
            }
        )
    )(_sample_employee(category=None)),
    task_prompt=lambda p: (
        f"Complete the full ticket lifecycle for employee {p['raiser']['name']} "
        f"({p['raiser']['emp_id']}): "
        f"(1) file a new ticket with ID {p['ticket_id']}, "
        "(2) assign it to an appropriate IT staff member, "
        "(3) resolve it with a detailed resolution."
    ),
    postconditions=_postcond_full_lifecycle,
)


# ── Synthesizer classes ───────────────────────────────────────────────────────


class ITAgentSynthesizer(DefaultAgentSynthesizer):
    """
    LLM agent executes IT ticket intents via IT Service Management APIs.

    Wraps DefaultAgentSynthesizer with IT-specific tool_registry and intents.
    Exists as a class (not instance) for pkgutil auto-discovery in synthesis_runner.py.
    """

    def __init__(self) -> None:
        super().__init__(
            name="it_agent",
            description="LLM agent executes IT ticket intents via IT Service Management APIs",
            tool_registry=IT_TOOL_REGISTRY,
            intents=IT_INTENTS,
            env_name="IT Service Management",
        )


class ITDirectSynthesizer(Synthesizer):
    """
    Programmatic IT ticket synthesizer that bypasses API rules.

    Inserts data directly into the DB, intentionally creating rule violations
    (invalid priorities, self-assignments, missing resolutions, etc.) for use
    as a negative baseline in validation experiments.
    """

    name = "it_direct"
    description = "Direct IT ticket generation (bypasses rules, creates intentional violations)"
    supports_batch = False

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--n-tickets", type=int, default=20, help="Number of tickets to create (default: 20)"
        )

    def params_from_args(self, args) -> dict:
        return {"n_tickets": getattr(args, "n_tickets", 20)}

    def run(self, params: dict) -> SynthesisResult:
        import datetime
        import sqlite3

        from synthesize.environments.it_management.db.db import DB_PATH

        n = params.get("n_tickets", 20)
        seed = params.get("seed")
        if seed is not None:
            random.seed(seed)

        with get_conn() as conn:
            all_emp = conn.execute("SELECT emp_id FROM employee").fetchall()
            it_emp = conn.execute("SELECT emp_id FROM employee WHERE category = 'IT'").fetchall()

        all_ids = [r["emp_id"] for r in all_emp]
        it_ids = [r["emp_id"] for r in it_emp]

        violations = []
        inserted = 0

        direct_conn = sqlite3.connect(str(DB_PATH))
        direct_conn.execute("PRAGMA foreign_keys = OFF")

        try:
            for i in range(n):
                tid = f"TKT-DIRECT-{i + 1:04d}"
                # Intentionally invalid fields to create violations:
                priority = random.choice(
                    ["low", "medium", "high", "critical", "urgent"]
                )  # invalid sometimes
                raiser = random.choice(all_ids)
                today = datetime.date.today().isoformat()

                # Sometimes self-assign, sometimes assign non-IT staff, sometimes no resolution on resolved
                violation_type = random.choice(
                    ["self_assign", "non_it_assign", "missing_resolution", "valid"]
                )
                status = (
                    "resolved"
                    if violation_type == "missing_resolution"
                    else random.choice(["open", "assigned", "resolved"])
                )
                assignee = None
                resolution = None
                assigned_date = None
                resolved_date = None

                if violation_type == "self_assign":
                    assignee = raiser  # violation: self-assignment
                    status = "assigned"
                    assigned_date = today
                elif violation_type == "non_it_assign":
                    non_it = [e for e in all_ids if e not in it_ids]
                    if non_it:
                        assignee = random.choice(non_it)  # violation: non-IT assignee
                        status = "assigned"
                        assigned_date = today
                elif violation_type == "missing_resolution":
                    assignee = random.choice(it_ids)
                    assigned_date = today
                    # No resolution set — violation: resolved ticket has no resolution
                    resolved_date = today
                elif status in ("assigned", "resolved", "closed"):
                    assignee = random.choice(it_ids)
                    assigned_date = today
                    if status in ("resolved", "closed"):
                        resolution = "Issue was fixed by the IT team."
                        resolved_date = today

                try:
                    direct_conn.execute(
                        """INSERT INTO it_ticket
                           (ticket_id, priority, status, raised_by_emp_id, assigned_emp_id,
                            assigned_date, created_date, issue_title, issue_description,
                            resolution, resolved_date)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            tid,
                            priority,
                            status,
                            raiser,
                            assignee,
                            assigned_date,
                            today,
                            f"Issue {i + 1}",
                            f"Description of issue {i + 1}.",
                            resolution,
                            resolved_date,
                        ),
                    )
                    direct_conn.commit()
                    inserted += 1
                    violations.append({"ticket_id": tid, "violation_type": violation_type})
                except Exception:
                    pass  # skip if FK fails despite PRAGMA OFF
        finally:
            direct_conn.close()

        return SynthesisResult(
            synthesizer=self.name,
            params=params,
            trajectories=[{"inserted": inserted, "intended_violations": violations}],
        )


# Generic alias used by GeneralistPopulatorSynthesizer dynamic import
TOOL_REGISTRY = IT_TOOL_REGISTRY
