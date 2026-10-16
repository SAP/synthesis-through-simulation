"""
Agent-based synthesizer.

An LLM agent executes structured intents against the policy-enforcing HR
mock API.  Coherent data emerges as a byproduct; every row is written through
the same business-rule enforcement that a real system would apply.

Modes
-----
blind    — agent receives only the task description; learns from API errors.
informed — agent receives full business rules in the system prompt.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json

# ── Model / proxy config ──────────────────────────────────────────────────────
import os
import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI

from synthesize.environments.hr.apis import employees as emp
from synthesize.environments.hr.apis import organization as org
from synthesize.environments.hr.apis import performance as pm
from synthesize.environments.hr.apis import recruiting as rcm
from synthesize.environments.hr.apis import time_management as tm
from synthesize.environments.hr.db.db import get_conn
from synthesize.synthesizer.base import SynthesisResult, Synthesizer

load_dotenv()

MODEL = os.getenv("SYNTHESIZE_MODEL", "claude-4.5-opus")
PROXY_BASE_URL = os.getenv("SYNTHESIZE_PROXY_BASE_URL", "http://localhost:4100")
MAX_STEPS = int(os.getenv("SYNTHESIZE_MAX_STEPS", "40"))


def _make_client() -> OpenAI:
    return OpenAI(base_url=PROXY_BASE_URL, api_key="anything")


# ── Serialization ─────────────────────────────────────────────────────────────


def _serialize(obj: Any) -> Any:
    """Recursively convert dataclasses, dates, and other non-JSON types."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    return obj


# ── Trajectory dataclasses ────────────────────────────────────────────────────


@dataclass
class Step:
    tool: str
    args: Dict[str, Any]
    result: Any
    is_error: bool


@dataclass
class Trajectory:
    intent: str
    mode: str
    params: Dict[str, Any]
    steps: List[Step]
    success: bool
    postconditions: Dict[str, bool]
    total_steps: int = 0
    error_count: int = 0
    recovery_count: int = 0

    def compute_metrics(self) -> None:
        self.total_steps = len(self.steps)
        self.error_count = sum(1 for s in self.steps if s.is_error)
        prev_was_error: Dict[str, bool] = {}
        for s in self.steps:
            if s.tool in prev_was_error and prev_was_error[s.tool] and not s.is_error:
                self.recovery_count += 1
            prev_was_error[s.tool] = s.is_error

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "mode": self.mode,
            "params": self.params,
            "success": self.success,
            "postconditions": self.postconditions,
            "total_steps": self.total_steps,
            "error_count": self.error_count,
            "recovery_count": self.recovery_count,
            "steps": [
                {"tool": s.tool, "args": s.args, "result": s.result, "is_error": s.is_error}
                for s in self.steps
            ],
        }


# ── Intent definition ─────────────────────────────────────────────────────────


@dataclass
class IntentDef:
    name: str
    brief: str
    informed_rules: str
    tools: List[str]
    sampler: Callable[[], Optional[Dict[str, Any]]]
    task_prompt: Callable[[Dict[str, Any]], str]
    postconditions: Callable[[Dict[str, Any], List[Step]], Dict[str, bool]]


# ── Raw DB helpers (tools without an API module) ──────────────────────────────


def _list_event_reasons(event_type: Optional[str] = None) -> List[dict]:
    with get_conn() as conn:
        if event_type:
            rows = conn.execute(
                "SELECT event_reason_code, event_type, event_reason_name "
                "FROM fod_event_reason WHERE event_type = ?",
                (event_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT event_reason_code, event_type, event_reason_name FROM fod_event_reason"
            ).fetchall()
    return [dict(r) for r in rows]


def _list_time_off_types() -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM tm_time_off_type").fetchall()
    return [dict(r) for r in rows]


def _list_companies() -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT company_code, company_name, currency FROM fod_company WHERE status = 'Active'"
        ).fetchall()
    return [dict(r) for r in rows]


def _create_employee_with_comp(**kw) -> dict:
    """Create employee and immediately insert an active BASE compensation record."""
    result = emp.create_employee(**kw)

    pay_grade = kw.get("pay_grade")
    hire_date = kw.get("hire_date")
    person_id = (
        result.person.person_id if hasattr(result, "person") else result["person"]["person_id"]
    )

    with get_conn() as conn:
        grade_row = conn.execute(
            "SELECT min_salary, max_salary, currency FROM fod_pay_grade WHERE pay_grade_code = ?",
            (pay_grade,),
        ).fetchone()
        hire_reason = conn.execute(
            "SELECT event_reason_code FROM fod_event_reason WHERE event_type = 'Hire' LIMIT 1"
        ).fetchone()

        if grade_row:
            min_s = grade_row["min_salary"] or 0
            max_s = grade_row["max_salary"] or min_s
            salary = round((min_s + max_s) / 2, 2)
            currency = grade_row["currency"] or "USD"
        else:
            salary = 0
            currency = "USD"

        event_code = hire_reason["event_reason_code"] if hire_reason else None

        conn.execute(
            """
            INSERT INTO emp_compensation
                (person_id, start_date, pay_component_code, amount, currency,
                 pay_grade, event_reason_code)
            VALUES (?, ?, 'BASE', ?, ?, ?, ?)
            """,
            (person_id, hire_date, salary, currency, pay_grade, event_code),
        )

    return _serialize(result)


# ── Tool wrapper functions ────────────────────────────────────────────────────


def _update_job_tool(
    person_id: str,
    event_reason_code: str,
    job_code: Optional[str] = None,
    department_code: Optional[str] = None,
    location_code: Optional[str] = None,
    manager_id: Optional[str] = None,
    pay_grade: Optional[str] = None,
    fte: Optional[float] = None,
):
    kwargs: dict = {}
    if job_code is not None:
        kwargs["job_code"] = job_code
    if department_code is not None:
        kwargs["department_code"] = department_code
    if location_code is not None:
        kwargs["location_code"] = location_code
    if manager_id is not None:
        kwargs["manager_id"] = manager_id
    if pay_grade is not None:
        kwargs["pay_grade"] = pay_grade
    if fte is not None:
        kwargs["fte"] = fte
    return emp.update_job(person_id, event_reason_code, **kwargs)


def _update_application_tool(
    application_id: str,
    application_status: Optional[str] = None,
    current_stage: Optional[str] = None,
    rating: Optional[float] = None,
    rejection_reason: Optional[str] = None,
):
    return rcm.update_application(
        application_id,
        application_status=application_status,
        current_stage=current_stage,
        rating=rating,
        rejection_reason=rejection_reason,
    )


def _update_offer_tool(
    offer_id: str,
    offer_status: Optional[str] = None,
    base_salary: Optional[float] = None,
    sign_on_bonus: Optional[float] = None,
    start_date: Optional[str] = None,
):
    return rcm.update_offer(
        offer_id,
        offer_status=offer_status,
        base_salary=base_salary,
        sign_on_bonus=sign_on_bonus,
        start_date=start_date,
    )


def _update_review_tool(
    review_id: str,
    overall_rating: Optional[float] = None,
    overall_rating_label: Optional[str] = None,
    review_status: Optional[str] = None,
):
    return pm.update_review(
        review_id,
        overall_rating=overall_rating,
        overall_rating_label=overall_rating_label,
        review_status=review_status,
    )


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOL_REGISTRY: Dict[str, dict] = {
    # ── Org lookups ──────────────────────────────────────────────────────────
    "list_departments": {
        "fn": lambda: org.list_departments(status="Active"),
        "description": "List all active departments.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "list_locations": {
        "fn": lambda: org.list_locations(status="Active"),
        "description": "List all active locations.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "list_job_codes": {
        "fn": lambda: org.list_job_codes(status="Active"),
        "description": "List all active job codes.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "list_pay_grades": {
        "fn": lambda: org.list_pay_grades(),
        "description": "List all pay grades with salary bands.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "list_companies": {
        "fn": _list_companies,
        "description": "List all active companies.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "list_event_reasons": {
        "fn": _list_event_reasons,
        "description": "List event reason codes. Optionally filter by event_type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "description": "Filter by event type. Valid values: 'Hire', 'Termination', 'Compensation Change', 'Job Change'",
                }
            },
            "required": [],
        },
    },
    "list_time_off_types": {
        "fn": _list_time_off_types,
        "description": "List available time-off types (e.g. Vacation, Sick Leave, PTO).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # ── Employee read ─────────────────────────────────────────────────────────
    "list_employees": {
        "fn": lambda dept=None, location=None, status="Active", limit=20, offset=0: (
            emp.list_employees(
                dept=dept, location=location, status=status, limit=limit, offset=offset
            )
        ),
        "description": "List employees. Optionally filter by dept, location, status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dept": {"type": "string", "description": "Filter by department_code"},
                "location": {"type": "string", "description": "Filter by location_code"},
                "status": {
                    "type": "string",
                    "description": "Filter by employment_status (default: Active)",
                },
                "limit": {"type": "integer", "description": "Max results (default 20)"},
                "offset": {"type": "integer", "description": "Pagination offset"},
            },
            "required": [],
        },
    },
    "get_employee": {
        "fn": lambda person_id: emp.get_employee(person_id),
        "description": "Get full employee profile (person + job + employment) by person_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "person_id": {"type": "string", "description": "The employee's person_id UUID"},
            },
            "required": ["person_id"],
        },
    },
    "get_job": {
        "fn": lambda person_id: emp.get_job(person_id),
        "description": "Get the current (active) job record for an employee.",
        "input_schema": {
            "type": "object",
            "properties": {"person_id": {"type": "string"}},
            "required": ["person_id"],
        },
    },
    # ── Employee write ────────────────────────────────────────────────────────
    "create_employee": {
        "fn": _create_employee_with_comp,
        "description": (
            "Create a new employee. Required: first_name, last_name, hire_date (YYYY-MM-DD), "
            "job_code, location_code, company_code, dept_code, pay_grade. "
            "Optional: manager_id, middle_name, gender, date_of_birth, nationality."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "hire_date": {"type": "string", "description": "YYYY-MM-DD"},
                "job_code": {"type": "string"},
                "location_code": {"type": "string"},
                "company_code": {"type": "string"},
                "dept_code": {"type": "string"},
                "pay_grade": {"type": "string"},
                "manager_id": {"type": "string", "description": "Optional manager person_id"},
                "middle_name": {"type": "string"},
                "gender": {"type": "string"},
                "date_of_birth": {"type": "string"},
                "nationality": {"type": "string"},
            },
            "required": [
                "first_name",
                "last_name",
                "hire_date",
                "job_code",
                "location_code",
                "company_code",
                "dept_code",
                "pay_grade",
            ],
        },
    },
    "update_job": {
        "fn": _update_job_tool,
        "description": (
            "Update an employee's job assignment. Creates a new time-slice record. "
            "Required: person_id, event_reason_code. "
            "Optional fields to change: job_code, department_code, location_code, manager_id, pay_grade, fte."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "person_id": {"type": "string"},
                "event_reason_code": {"type": "string"},
                "job_code": {"type": "string"},
                "department_code": {"type": "string"},
                "location_code": {"type": "string"},
                "manager_id": {"type": "string"},
                "pay_grade": {"type": "string"},
                "fte": {"type": "number"},
            },
            "required": ["person_id", "event_reason_code"],
        },
    },
    "terminate_employee": {
        "fn": lambda person_id, termination_date, termination_reason_code, comments=None: (
            emp.terminate_employee(person_id, termination_date, termination_reason_code, comments)
        ),
        "description": (
            "Terminate an employee. Closes their employment and job records. "
            "termination_reason_code must be a code with event_type='Termination'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "person_id": {"type": "string"},
                "termination_date": {"type": "string", "description": "YYYY-MM-DD"},
                "termination_reason_code": {"type": "string"},
                "comments": {"type": "string"},
            },
            "required": ["person_id", "termination_date", "termination_reason_code"],
        },
    },
    # ── Time management ───────────────────────────────────────────────────────
    "get_time_off_balance": {
        "fn": lambda person_id, year=None: tm.get_balances(person_id, year),
        "description": "Get time-off balances for an employee.",
        "input_schema": {
            "type": "object",
            "properties": {
                "person_id": {"type": "string"},
                "year": {"type": "integer", "description": "Calendar year (default: current year)"},
            },
            "required": ["person_id"],
        },
    },
    "list_time_off_requests": {
        "fn": lambda person_id=None, status=None: tm.list_requests(
            person_id=person_id, status=status
        ),
        "description": "List time-off requests. Optionally filter by person_id and/or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "person_id": {"type": "string"},
                "status": {"type": "string", "description": "Filter by request_status"},
            },
            "required": [],
        },
    },
    "create_time_off_request": {
        "fn": lambda person_id, time_off_type_code, start_date, end_date, total_days, comments=None: (
            tm.create_request(
                person_id, time_off_type_code, start_date, end_date, total_days, comments
            )
        ),
        "description": (
            "Submit a time-off request. total_days must be > 0 and available balance sufficient."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "person_id": {"type": "string"},
                "time_off_type_code": {"type": "string"},
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                "total_days": {"type": "number"},
                "comments": {"type": "string"},
            },
            "required": ["person_id", "time_off_type_code", "start_date", "end_date", "total_days"],
        },
    },
    "approve_time_off_request": {
        "fn": lambda request_id, approver_person_id: tm.approve_request(
            request_id, approver_person_id
        ),
        "description": "Approve a Pending time-off request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "approver_person_id": {"type": "string"},
            },
            "required": ["request_id", "approver_person_id"],
        },
    },
    # ── Recruiting ────────────────────────────────────────────────────────────
    "list_requisitions": {
        "fn": lambda status=None, dept_code=None, limit=20: rcm.list_requisitions(
            status=status, dept_code=dept_code, limit=limit
        ),
        "description": "List job requisitions. Optionally filter by status and dept_code.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "dept_code": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": [],
        },
    },
    "get_requisition": {
        "fn": lambda req_id: rcm.get_requisition(req_id),
        "description": "Get a job requisition by req_id.",
        "input_schema": {
            "type": "object",
            "properties": {"req_id": {"type": "string"}},
            "required": ["req_id"],
        },
    },
    "create_requisition": {
        "fn": lambda **kw: rcm.create_requisition(**kw),
        "description": (
            "Create a new job requisition. Required: req_title, job_code, department_code, "
            "location_code, hiring_manager_person_id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "req_title": {"type": "string"},
                "job_code": {"type": "string"},
                "department_code": {"type": "string"},
                "location_code": {"type": "string"},
                "hiring_manager_person_id": {"type": "string"},
                "recruiter_person_id": {"type": "string"},
                "number_of_openings": {"type": "integer"},
                "employment_type": {"type": "string"},
                "salary_min": {"type": "number"},
                "salary_max": {"type": "number"},
                "target_hire_date": {"type": "string"},
            },
            "required": [
                "req_title",
                "job_code",
                "department_code",
                "location_code",
                "hiring_manager_person_id",
            ],
        },
    },
    "create_candidate": {
        "fn": lambda **kw: rcm.create_candidate(**kw),
        "description": "Create a new candidate profile. Required: first_name, last_name, email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "source": {"type": "string"},
                "current_company": {"type": "string"},
                "current_title": {"type": "string"},
                "years_of_experience": {"type": "integer"},
            },
            "required": ["first_name", "last_name", "email"],
        },
    },
    "create_application": {
        "fn": lambda req_id, candidate_id, application_date=None: rcm.create_application(
            req_id, candidate_id, application_date
        ),
        "description": "Submit a candidate application. Requisition must be Open.",
        "input_schema": {
            "type": "object",
            "properties": {
                "req_id": {"type": "string"},
                "candidate_id": {"type": "string"},
                "application_date": {
                    "type": "string",
                    "description": "YYYY-MM-DD (default: today)",
                },
            },
            "required": ["req_id", "candidate_id"],
        },
    },
    "update_application": {
        "fn": _update_application_tool,
        "description": (
            "Advance an application through the pipeline. "
            "Status order (forward-only): New → Under Review → Interview → Offer → Hired / Rejected."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {"type": "string"},
                "application_status": {
                    "type": "string",
                    "enum": ["New", "Under Review", "Interview", "Offer", "Hired", "Rejected"],
                },
                "current_stage": {"type": "string"},
                "rating": {"type": "number"},
                "rejection_reason": {"type": "string"},
            },
            "required": ["application_id"],
        },
    },
    "create_offer": {
        "fn": lambda **kw: rcm.create_offer(**kw),
        "description": (
            "Extend a job offer. Required: application_id, offer_date, base_salary. "
            "base_salary must be within requisition salary_min/salary_max (if set)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {"type": "string"},
                "offer_date": {"type": "string", "description": "YYYY-MM-DD"},
                "base_salary": {"type": "number"},
                "job_title": {"type": "string"},
                "start_date": {"type": "string"},
                "offer_expiry_date": {"type": "string"},
                "sign_on_bonus": {"type": "number"},
                "currency": {"type": "string"},
            },
            "required": ["application_id", "offer_date", "base_salary"],
        },
    },
    "update_offer": {
        "fn": _update_offer_tool,
        "description": "Update an offer status (e.g. offer_status='Accepted' or 'Declined').",
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_id": {"type": "string"},
                "offer_status": {
                    "type": "string",
                    "enum": ["Extended", "Accepted", "Declined", "Expired"],
                },
                "base_salary": {"type": "number"},
                "start_date": {"type": "string"},
            },
            "required": ["offer_id"],
        },
    },
    "get_offer": {
        "fn": lambda application_id: rcm.get_offer(application_id),
        "description": "Get the current offer for an application (by application_id).",
        "input_schema": {
            "type": "object",
            "properties": {"application_id": {"type": "string"}},
            "required": ["application_id"],
        },
    },
    "list_applications": {
        "fn": lambda req_id=None, candidate_id=None, status=None: rcm.list_applications(
            req_id=req_id, candidate_id=candidate_id, status=status
        ),
        "description": "List applications, optionally filtered by req_id, candidate_id, or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "req_id": {"type": "string"},
                "candidate_id": {"type": "string"},
                "status": {"type": "string"},
            },
            "required": [],
        },
    },
    # ── Performance ───────────────────────────────────────────────────────────
    "list_reviews": {
        "fn": lambda person_id=None, status=None, limit=20: pm.list_reviews(
            person_id=person_id, status=status, limit=limit
        ),
        "description": "List performance reviews. Optionally filter by person_id or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "person_id": {"type": "string"},
                "status": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": [],
        },
    },
    "get_review": {
        "fn": lambda review_id: pm.get_review(review_id),
        "description": "Get a performance review by review_id.",
        "input_schema": {
            "type": "object",
            "properties": {"review_id": {"type": "string"}},
            "required": ["review_id"],
        },
    },
    "update_review": {
        "fn": _update_review_tool,
        "description": (
            "Update a performance review. "
            "Status machine (forward-only): Draft → In Progress → Completed → Approved. "
            "overall_rating must be set before status can be 'Completed'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "review_id": {"type": "string"},
                "overall_rating": {"type": "number"},
                "overall_rating_label": {"type": "string"},
                "review_status": {
                    "type": "string",
                    "enum": ["Draft", "In Progress", "Completed", "Approved"],
                },
            },
            "required": ["review_id"],
        },
    },
}


# ── Intent helpers ────────────────────────────────────────────────────────────


def _sample_active_employee() -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT p.person_id, p.first_name || ' ' || p.last_name AS full_name,
                   j.department_code
            FROM per_person p
            JOIN emp_job j ON j.person_id = p.person_id AND j.end_date IS NULL
            WHERE j.employment_status = 'Active'
            ORDER BY RANDOM() LIMIT 1
            """
        ).fetchone()
    return dict(row) if row else None


def _find_in_steps(steps: List[Step], tool_name: str) -> Optional[dict]:
    for s in steps:
        if s.tool == tool_name and not s.is_error:
            return s.result
    return None


# ── Intent definitions ────────────────────────────────────────────────────────

INTENTS: Dict[str, IntentDef] = {}


# ADD_EMPLOYEE


def _sample_add_employee() -> dict:
    return {"hire_date": datetime.date.today().isoformat()}


def _postcond_add_employee(params: dict, steps: List[Step]) -> Dict[str, bool]:
    result = _find_in_steps(steps, "create_employee")
    if result is None:
        return {"create_employee_called": False}
    person_id = result.get("person", {}).get("person_id") if isinstance(result, dict) else None
    if not person_id:
        return {"create_employee_called": False}
    with get_conn() as conn:
        has_person = bool(
            conn.execute("SELECT 1 FROM per_person WHERE person_id = ?", (person_id,)).fetchone()
        )
        has_employment = bool(
            conn.execute(
                "SELECT 1 FROM emp_employment WHERE person_id = ? AND end_date IS NULL",
                (person_id,),
            ).fetchone()
        )
        has_active_job = bool(
            conn.execute(
                "SELECT 1 FROM emp_job WHERE person_id = ? AND end_date IS NULL "
                "AND employment_status = 'Active'",
                (person_id,),
            ).fetchone()
        )
    return {
        "person_record_created": has_person,
        "active_employment_created": has_employment,
        "active_job_created": has_active_job,
    }


INTENTS["ADD_EMPLOYEE"] = IntentDef(
    name="ADD_EMPLOYEE",
    brief=(
        "Hire a new employee. Discover valid reference values (job code, department, "
        "location, pay grade, company) via the available tools and create the employee record."
    ),
    informed_rules=(
        "Business rules:\n"
        "1. All reference values (job_code, location_code, company_code, dept_code, pay_grade) "
        "must exist in the system — use list_job_codes, list_departments, list_locations, "
        "list_pay_grades, and list_companies to discover valid codes.\n"
        "2. A Hire event reason is looked up automatically by create_employee.\n"
        "3. If you supply manager_id, that person must be an active employee.\n"
        "4. The employee is created with employment_status='Active' and fte=1.0.\n"
    ),
    tools=[
        "list_departments",
        "list_locations",
        "list_job_codes",
        "list_pay_grades",
        "list_companies",
        "list_employees",
        "create_employee",
    ],
    sampler=_sample_add_employee,
    task_prompt=lambda p: (
        f"Hire a new employee with hire date {p['hire_date']}. "
        "Choose a realistic full name (first and last) that is not already in the system. "
        "Choose appropriate values for job code, department, location, pay grade, and company."
    ),
    postconditions=_postcond_add_employee,
)


# TRANSFER_EMPLOYEE


def _postcond_transfer_employee(params: dict, steps: List[Step]) -> Dict[str, bool]:
    person_id = params.get("person_id")
    update_called = _find_in_steps(steps, "update_job") is not None
    if not person_id or not update_called:
        return {"update_job_called": False}
    with get_conn() as conn:
        job_count = conn.execute(
            "SELECT COUNT(*) FROM emp_job WHERE person_id = ?", (person_id,)
        ).fetchone()[0]
        current_dept = conn.execute(
            "SELECT department_code FROM emp_job WHERE person_id = ? AND end_date IS NULL",
            (person_id,),
        ).fetchone()
    return {
        "update_job_called": True,
        "new_job_record_created": job_count > 1,
        "active_job_exists": current_dept is not None,
    }


INTENTS["TRANSFER_EMPLOYEE"] = IntentDef(
    name="TRANSFER_EMPLOYEE",
    brief=(
        "Transfer the specified employee to a different department. "
        "Look up valid departments and a Transfer event reason code, then update the job."
    ),
    informed_rules=(
        "Business rules:\n"
        "1. Use list_event_reasons with event_type='Job Change' to get a valid event reason code.\n"
        "2. update_job closes the current emp_job record and inserts a new one (time-slicing). "
        "You must specify at least one field to change.\n"
        "3. You cannot set manager_id to the employee themselves, or to one of their reports.\n"
        "4. Use list_departments or list_locations to find valid destination codes.\n"
    ),
    tools=[
        "list_departments",
        "list_locations",
        "list_event_reasons",
        "get_employee",
        "get_job",
        "update_job",
    ],
    sampler=_sample_active_employee,
    task_prompt=lambda p: (
        f"Transfer employee {p['person_id']} ({p['full_name']}) "
        f"(currently in department {p['department_code']}) to a different department. "
        "You MUST call update_job() with the new department_code to complete this task — do not just describe how."
    ),
    postconditions=_postcond_transfer_employee,
)


# TERMINATE_EMPLOYEE


def _postcond_terminate_employee(params: dict, steps: List[Step]) -> Dict[str, bool]:
    person_id = params.get("person_id")
    called = _find_in_steps(steps, "terminate_employee") is not None
    if not person_id or not called:
        return {"terminate_employee_called": False}
    with get_conn() as conn:
        emp_row = conn.execute(
            "SELECT employment_type, termination_date FROM emp_employment "
            "WHERE person_id = ? ORDER BY employment_id DESC LIMIT 1",
            (person_id,),
        ).fetchone()
        open_job = conn.execute(
            "SELECT 1 FROM emp_job WHERE person_id = ? AND end_date IS NULL", (person_id,)
        ).fetchone()
    return {
        "terminate_employee_called": True,
        "employment_terminated": emp_row is not None and emp_row["employment_type"] == "Terminated",
        "job_record_closed": open_job is None,
    }


INTENTS["TERMINATE_EMPLOYEE"] = IntentDef(
    name="TERMINATE_EMPLOYEE",
    brief=(
        "Terminate the specified employee effective today. "
        "Look up a valid termination reason code, then call terminate_employee."
    ),
    informed_rules=(
        "Business rules:\n"
        "1. Use list_event_reasons with event_type='Termination' to find valid codes.\n"
        "2. terminate_employee sets employment_type='Terminated' and closes both "
        "emp_employment and emp_job (sets end_date).\n"
        "3. Use today's date as termination_date.\n"
    ),
    tools=["list_event_reasons", "get_employee", "terminate_employee"],
    sampler=_sample_active_employee,
    task_prompt=lambda p: (
        f"Terminate employee {p['person_id']} ({p['full_name']}) "
        f"effective {datetime.date.today().isoformat()}. "
        "You MUST call terminate_employee() to complete this task — do not just describe how."
    ),
    postconditions=_postcond_terminate_employee,
)


# SUBMIT_TIME_OFF


def _sample_submit_time_off() -> Optional[dict]:
    today = datetime.date.today()
    start_offset = random.randint(7, 30)
    # Keep duration 1–5 days so per-run balance consumption stays small
    # and 20 batched runs don't exhaust the seed balance pool.
    duration = random.randint(1, 5)
    start = (today + datetime.timedelta(days=start_offset)).isoformat()
    end = (today + datetime.timedelta(days=start_offset + duration)).isoformat()
    employee = _sample_active_employee()
    if not employee:
        return None
    return {**employee, "start_date": start, "end_date": end}


def _postcond_submit_time_off(params: dict, steps: List[Step]) -> Dict[str, bool]:
    result = _find_in_steps(steps, "create_time_off_request")
    if result is None:
        return {"request_created": False}
    request_id = result.get("request_id") if isinstance(result, dict) else None
    if not request_id:
        return {"request_created": False}
    with get_conn() as conn:
        row = conn.execute(
            "SELECT request_status FROM tm_time_off_request WHERE request_id = ?",
            (request_id,),
        ).fetchone()
    return {
        "request_created": row is not None,
        "request_status_pending": row is not None and row["request_status"] == "Pending",
    }


INTENTS["SUBMIT_TIME_OFF"] = IntentDef(
    name="SUBMIT_TIME_OFF",
    brief=(
        "Submit a time-off request for the specified employee. "
        "Check the employee's balance and choose an appropriate time-off type."
    ),
    informed_rules=(
        "Business rules:\n"
        "1. Use list_time_off_types to find valid time_off_type_codes.\n"
        "2. Use get_time_off_balance to check available days — balance must be sufficient.\n"
        "3. total_days must be > 0 and start_date <= end_date.\n"
        "4. The request starts with request_status='Pending'.\n"
    ),
    tools=[
        "list_time_off_types",
        "get_employee",
        "get_time_off_balance",
        "list_time_off_requests",
        "create_time_off_request",
    ],
    sampler=_sample_submit_time_off,
    task_prompt=lambda p: (
        f"Submit a time-off request for employee {p['person_id']} ({p['full_name']}) "
        f"from {p['start_date']} to {p['end_date']}. "
        "Check available balances first. If the first leave type has insufficient balance or an "
        "overlapping request, try a different leave type. "
        "You MUST call create_time_off_request() to complete this task."
    ),
    postconditions=_postcond_submit_time_off,
)


# APPROVE_TIME_OFF


def _sample_approve_time_off() -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT r.request_id, r.person_id, r.time_off_type_code,
                   p.first_name || ' ' || p.last_name AS full_name
            FROM tm_time_off_request r
            JOIN per_person p ON p.person_id = r.person_id
            WHERE r.request_status = 'Pending'
            ORDER BY RANDOM() LIMIT 1
            """
        ).fetchone()
    return dict(row) if row else None


def _postcond_approve_time_off(params: dict, steps: List[Step]) -> Dict[str, bool]:
    request_id = params.get("request_id")
    called = _find_in_steps(steps, "approve_time_off_request") is not None
    if not request_id or not called:
        return {"approve_called": False}
    with get_conn() as conn:
        row = conn.execute(
            "SELECT request_status FROM tm_time_off_request WHERE request_id = ?",
            (request_id,),
        ).fetchone()
    return {
        "approve_called": True,
        "request_approved": row is not None and row["request_status"] == "Approved",
    }


INTENTS["APPROVE_TIME_OFF"] = IntentDef(
    name="APPROVE_TIME_OFF",
    brief=(
        "Approve the specified pending time-off request. "
        "You need to supply a valid approver person_id from the system."
    ),
    informed_rules=(
        "Business rules:\n"
        "1. Only Pending requests can be approved.\n"
        "2. The approver_person_id must be a valid person — use list_employees to find one.\n"
        "3. On approval: pending_days move to used_days in the balance.\n"
    ),
    tools=["list_employees", "get_employee", "list_time_off_requests", "approve_time_off_request"],
    sampler=_sample_approve_time_off,
    task_prompt=lambda p: (
        f"Approve the time-off request {p['request_id']} "
        f"for employee {p['person_id']} ({p['full_name']}). "
        "Choose an appropriate approver from the active employees."
    ),
    postconditions=_postcond_approve_time_off,
)


# OPEN_REQUISITION


def _postcond_open_requisition(params: dict, steps: List[Step]) -> Dict[str, bool]:
    result = _find_in_steps(steps, "create_requisition")
    if result is None:
        return {"requisition_created": False}
    req_id = result.get("req_id") if isinstance(result, dict) else None
    if not req_id:
        return {"requisition_created": False}
    with get_conn() as conn:
        row = conn.execute(
            "SELECT req_status FROM rcm_job_requisition WHERE req_id = ?", (req_id,)
        ).fetchone()
    return {
        "requisition_created": row is not None,
        "requisition_open": row is not None and row["req_status"] == "Open",
    }


INTENTS["OPEN_REQUISITION"] = IntentDef(
    name="OPEN_REQUISITION",
    brief=(
        "Open a new job requisition. Discover valid job codes, departments, locations, "
        "and a hiring manager, then create the requisition."
    ),
    informed_rules=(
        "Business rules:\n"
        "1. job_code, department_code, and location_code must all exist in the system.\n"
        "2. hiring_manager_person_id must be a valid active employee.\n"
        "3. If both salary_min and salary_max are given, salary_min <= salary_max.\n"
        "4. The requisition is created with req_status='Open'.\n"
    ),
    tools=[
        "list_departments",
        "list_locations",
        "list_job_codes",
        "list_employees",
        "create_requisition",
    ],
    sampler=lambda: {"note": "open a requisition for any suitable role"},
    task_prompt=lambda p: (
        "Open a new job requisition for a suitable position. "
        "Choose appropriate values for job code, department, location, and hiring manager."
    ),
    postconditions=_postcond_open_requisition,
)


# HIRE_CANDIDATE


def _sample_hire_candidate() -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT req_id, req_title, department_code, salary_min, salary_max "
            "FROM rcm_job_requisition WHERE req_status = 'Open' ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def _postcond_hire_candidate(params: dict, steps: List[Step]) -> Dict[str, bool]:
    req_id = params.get("req_id")
    if not req_id:
        return {"hire_completed": False}
    with get_conn() as conn:
        hired = conn.execute(
            "SELECT COUNT(*) FROM rcm_application WHERE req_id = ? AND application_status = 'Hired'",
            (req_id,),
        ).fetchone()[0]
        accepted_offer = conn.execute(
            """
            SELECT COUNT(*) FROM rcm_offer o
            JOIN rcm_application a ON o.application_id = a.application_id
            WHERE a.req_id = ? AND o.offer_status = 'Accepted'
            """,
            (req_id,),
        ).fetchone()[0]
    return {
        "application_hired": hired > 0,
        "offer_accepted": accepted_offer > 0,
    }


INTENTS["HIRE_CANDIDATE"] = IntentDef(
    name="HIRE_CANDIDATE",
    brief=(
        "Complete a full hire cycle for the given requisition: create a candidate, "
        "apply, advance through the pipeline, extend and accept an offer."
    ),
    informed_rules=(
        "Business rules:\n"
        "1. Create a candidate with create_candidate (unique email required).\n"
        "2. Create an application — requisition must be 'Open'.\n"
        "3. Advance the application: New → Under Review → Interview → Offer.\n"
        "4. Use create_offer when in 'Interview' or 'Offer' status.\n"
        "5. Use update_offer with offer_status='Accepted' to accept.\n"
        "6. On acceptance the application becomes 'Hired'.\n"
    ),
    tools=[
        "get_requisition",
        "list_requisitions",
        "create_candidate",
        "create_application",
        "list_applications",
        "update_application",
        "create_offer",
        "update_offer",
        "get_offer",
    ],
    sampler=_sample_hire_candidate,
    task_prompt=lambda p: (
        f"Complete a full hire for requisition {p['req_id']} ({p['req_title']}). "
        "Create a candidate, submit their application, advance through the pipeline, "
        "then extend and accept an offer."
    ),
    postconditions=_postcond_hire_candidate,
)


# COMPLETE_REVIEW


def _sample_complete_review() -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT r.review_id, r.person_id, r.review_status,
                   p.first_name || ' ' || p.last_name AS full_name
            FROM pm_performance_review r
            JOIN per_person p ON p.person_id = r.person_id
            WHERE r.review_status IN ('Draft', 'In Progress')
            ORDER BY RANDOM() LIMIT 1
            """
        ).fetchone()
    return dict(row) if row else None


def _postcond_complete_review(params: dict, steps: List[Step]) -> Dict[str, bool]:
    review_id = params.get("review_id")
    called = _find_in_steps(steps, "update_review") is not None
    if not review_id or not called:
        return {"update_review_called": False}
    with get_conn() as conn:
        row = conn.execute(
            "SELECT review_status, overall_rating FROM pm_performance_review WHERE review_id = ?",
            (review_id,),
        ).fetchone()
    return {
        "update_review_called": True,
        "review_completed": row is not None and row["review_status"] == "Completed",
        "rating_set": row is not None and row["overall_rating"] is not None,
    }


INTENTS["COMPLETE_REVIEW"] = IntentDef(
    name="COMPLETE_REVIEW",
    brief=(
        "Complete the specified performance review by setting an overall rating "
        "and advancing the status to 'Completed'."
    ),
    informed_rules=(
        "Business rules:\n"
        "1. Review status machine (forward-only): Draft → In Progress → Completed → Approved.\n"
        "2. overall_rating (1.0–5.0) must be set before status can be 'Completed'.\n"
        "3. You can set overall_rating and review_status='Completed' in one update_review call.\n"
        "4. If the review is 'Draft', first advance to 'In Progress', then complete it.\n"
    ),
    tools=["list_reviews", "get_review", "update_review"],
    sampler=_sample_complete_review,
    task_prompt=lambda p: (
        f"Complete the performance review {p['review_id']} for employee "
        f"{p['person_id']} ({p['full_name']}). "
        "Call update_review() with overall_rating (a float 1.0–5.0) and "
        "review_status='Completed'. You MUST call update_review() — do not just describe how."
    ),
    postconditions=_postcond_complete_review,
)


# ── Tool dispatch ─────────────────────────────────────────────────────────────


def _call_tool(name: str, args: dict) -> Tuple[Any, bool]:
    entry = TOOL_REGISTRY.get(name)
    if entry is None:
        return {"error": f"Unknown tool: {name}"}, True
    try:
        raw = entry["fn"](**args)
        return _serialize(raw), False
    except (ValueError, LookupError) as exc:
        return {"error": str(exc)}, True
    except Exception as exc:
        return {"error": f"Unexpected error: {exc}"}, True


def _tool_definition(name: str) -> dict:
    entry = TOOL_REGISTRY[name]
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": entry["description"],
            "parameters": entry["input_schema"],
        },
    }


# ── System prompts ────────────────────────────────────────────────────────────

_BLIND_SYSTEM = (
    "You are an HR system agent. You will be given a task to complete by making "
    "API calls. You have no prior knowledge of the system's business rules — "
    "learn from the API's error responses and adjust your calls accordingly. "
    "When you have successfully completed the task, say 'TASK COMPLETE' and stop."
)

_INFORMED_PREFIX = (
    "You are an HR system agent. You will be given a task to complete by making "
    "API calls. You have full knowledge of the relevant business rules:\n\n"
)

_INFORMED_SUFFIX = (
    "\nMake the required API calls to complete the task. "
    "When you have successfully completed the task, say 'TASK COMPLETE' and stop."
)


def _build_system_prompt(mode: str, intent_def: IntentDef) -> str:
    if mode == "blind":
        return _BLIND_SYSTEM
    return _INFORMED_PREFIX + intent_def.informed_rules + _INFORMED_SUFFIX


# ── Agentic loop ──────────────────────────────────────────────────────────────


def run_agent(
    intent_def: IntentDef,
    params: Dict[str, Any],
    mode: str,
    client: OpenAI,
) -> Trajectory:
    """Execute one intent run; return a recorded Trajectory."""
    assert mode in ("blind", "informed"), f"mode must be 'blind' or 'informed', got {mode!r}"

    system = _build_system_prompt(mode, intent_def)
    task_prompt = intent_def.task_prompt(params)
    tools = [_tool_definition(t) for t in intent_def.tools]

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task_prompt},
    ]
    steps: List[Step] = []

    for _ in range(MAX_STEPS):
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=4096,
            messages=messages,
            tools=tools,
        )

        choice = response.choices[0]
        messages.append(choice.message)

        if choice.finish_reason == "stop":
            break
        if choice.finish_reason != "tool_calls":
            break

        for tc in choice.message.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            result, is_error = _call_tool(tc.function.name, args)
            steps.append(Step(tool=tc.function.name, args=args, result=result, is_error=is_error))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                }
            )

    post = intent_def.postconditions(params, steps)
    success = bool(post) and all(post.values())

    traj = Trajectory(
        intent=intent_def.name,
        mode=mode,
        params=params,
        steps=steps,
        success=success,
        postconditions=post,
    )
    traj.compute_metrics()
    return traj


# ── Synthesizer class ─────────────────────────────────────────────────────────


class AgentSynthesizer(Synthesizer):
    """
    LLM agent executes structured intents via the policy-enforcing HR APIs.
    Data coherence is enforced by the API; the agent must discover and satisfy
    all business rules to complete each intent.
    """

    name = "hr_agent"
    description = "LLM agent executes structured intents via HR APIs (blind or informed mode)"
    supports_batch = True

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--intent",
            help="Intent to run (e.g. ADD_EMPLOYEE). If omitted in batch, cycles through all intents.",
        )
        parser.add_argument(
            "--mode",
            choices=["blind", "informed"],
            default="blind",
            help="blind: no rules in prompt; informed: full rules in prompt (default: blind)",
        )

    def params_from_args(self, args: argparse.Namespace) -> dict:
        return {
            "intent": getattr(args, "intent", None),
            "mode": getattr(args, "mode", "blind"),
        }

    def sample_params(self, intent: str = None, mode: str = "blind", **kwargs) -> Optional[dict]:
        """Sample run params: pick a random eligible intent (or use the specified one)."""
        intent_name = intent.upper() if intent else random.choice(list(INTENTS.keys()))
        if intent_name not in INTENTS:
            raise ValueError(f"Unknown intent: {intent_name!r}")
        intent_def = INTENTS[intent_name]
        run_params = intent_def.sampler()
        if run_params is None:
            return None
        return {"intent": intent_name, "mode": mode, "run_params": run_params}

    def run(self, params: dict) -> SynthesisResult:
        seed = params.get("seed")
        if seed is not None:
            random.seed(seed)

        intent_name = (params.get("intent") or "").upper()
        if not intent_name:
            raise ValueError("params must include 'intent'")
        if intent_name not in INTENTS:
            raise ValueError(f"Unknown intent: {intent_name!r}")

        mode = params.get("mode", "blind")
        intent_def = INTENTS[intent_name]

        # Use pre-sampled run_params if provided (batch mode), else sample now.
        run_params = params.get("run_params")
        if run_params is None:
            run_params = intent_def.sampler()
            if run_params is None:
                raise ValueError(f"No eligible records in DB for intent {intent_name!r}")

        client = _make_client()
        traj = run_agent(intent_def, run_params, mode, client)

        return SynthesisResult(
            synthesizer=self.name,
            params={**params, "run_params": run_params},
            trajectories=[traj.to_dict()],
        )


# Generic alias used by GeneralistPopulatorSynthesizer dynamic import
HR_TOOL_REGISTRY = TOOL_REGISTRY
