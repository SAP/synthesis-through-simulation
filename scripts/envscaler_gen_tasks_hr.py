"""
EnvScaler task generator for the HR environment.

Uses the same EnvScaler Step-2 prompt as envscaler_gen_tasks.py but describes the
HR (Human Resources) environment instead of the airline environment.

Usage:
    python scripts/envscaler_gen_tasks_hr.py [--n 50] [--out scripts/envscaler_hr_tasks.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

PROXY_BASE_URL = "http://localhost:4000"
MODEL = "gpt-4.1"

BASELINE_DB = REPO_ROOT / "src" / "synthesize" / "environments" / "hr" / "db" / "hr_snapshot.db"

# ── EnvScaler Step-2 prompt template ──────────────────────────────────────────

_STEP2_TEMPLATE = """\
You are a task design expert, responsible for creating realistic, clear, and challenging tasks for a specific interactive environment.

You do not need to consider how the task will be executed; another execution expert will be responsible for completing it.

# Environment Introduction:
{env_introduction}

# Environment State Definition:
{env_state_definition}

# Supported Operation Interfaces:
{env_modify_operation}

# Environment Rules / Constraints:
{env_rule}

# Current Environment Initial State / Database:
{env_init_state}

# Task Design Requirements:
- **Realism**: The task must closely align with the current environment, reflect a plausible real-world scenario, and have a well-defined objective with business relevance.
- **Feasibility**:
    i. The task must be based on and constrained by the current initial state of the environment. For example, you cannot terminate an employee that does not exist.
    ii. The task should be achievable through a combination of multiple operational interfaces supported by the environment. On one hand, the task description must include nessary information to enable successful completion (for example, if all tools only support actions by ID and can not get the ID anyway, the task should at least provide the ID). On the other hand, it should not include excessive information, so that the Agent is encouraged to use information query tools to obtain the necessary data rather than relying solely on the information provided in the task description.
    iii. Avoid tasks that require more than just the user interface. For example, timestamps might be automatically generated rather than modified through the user interface.
- **State Modification**: The goal of the task must involve modifying the current environment state/database; it cannot be limited to information queries only.
- **Challenge**: The task should be difficult enough that the agent needs to make multiple calls to information query tools and state modification tools to complete it. For example, the modification should have sufficient complexity (e.g., involving multiple objects, multiple attributes, or multi-condition combinations), and should not be achievable in a single simple step.
- **Compositionality**: The task must be composed of several distinct sub-tasks (No less than 50 words). Each sub-task must require multiple tool invocations to complete, ensuring layered complexity and interdependent steps across the task flow.
- **Clarity**: Use concise natural language to describe each sub-task. The description must be easy to understand and unambiguous. Since the ultimate goal is to modify the state, query tools are only part of the task-solving process and serve to provide information to the Agent; therefore, there is no need to include query requirements or intermediate steps in the task description.

Strictly follow the output format below:

# Analysis
[Your detailed step-by step reasoning and thought process, including environment description, current environment state, and supporting operation interfaces and so on.]

# Task
[Only the Task description, without any other analysis or explanation.]
"""

# ── HR environment descriptor ──────────────────────────────────────────────────

HR_ENV_ITEM = {
    "environment_introduction": (
        "A Human Resources Information System (HRIS) for a mid-sized technology company. "
        "HR administrators can manage the full employee lifecycle: hiring, job changes, "
        "transfers, terminations, time-off management, performance reviews, and recruitment. "
        "The system tracks employees across departments and locations, manages compensation "
        "and pay grades, handles job requisitions and candidate pipelines, and processes "
        "time-off requests with balance enforcement."
    ),
    "state_space_definition": (
        "per_person: {person_id, first_name, last_name, hire_date, employment_status}\n"
        "emp_job: {person_id, job_code, department_code, location_code, manager_id, "
        "pay_grade, employment_status, effective_date}\n"
        "emp_employment: {person_id, company_code, employment_status, termination_date, "
        "termination_reason_code}\n"
        "fod_department: {department_code, department_name, division_code}\n"
        "fod_job_code: {job_code, job_title, level, family}\n"
        "fod_pay_grade: {pay_grade, min_salary, max_salary, currency}\n"
        "fod_location: {location_code, location_name, country_code}\n"
        "fod_event_reason: {event_reason_code, event_type, description}\n"
        "tm_time_off_type: {time_off_type_code, name, accrual_days_per_year}\n"
        "tm_time_off_balance: {person_id, time_off_type_code, balance_days}\n"
        "tm_time_off_request: {request_id, person_id, time_off_type_code, start_date, "
        "end_date, total_days, status (Pending/Approved/Rejected/Cancelled)}\n"
        "rcm_job_requisition: {req_id, req_title, job_code, department_code, "
        "location_code, status (Open/Filled/Cancelled), hiring_manager_id}\n"
        "rcm_candidate: {candidate_id, first_name, last_name, email}\n"
        "rcm_application: {application_id, req_id, candidate_id, "
        "status (New/Under Review/Interview/Offer/Hired/Rejected)}\n"
        "rcm_offer: {offer_id, application_id, base_salary, offer_date, "
        "offer_status (Pending/Accepted/Declined)}\n"
        "pm_performance_review: {review_id, person_id, review_period, "
        "status (Draft/In Progress/Completed/Approved), overall_rating}"
    ),
    "operation_list": [
        {"operation_name": "list_departments", "operation_type": "read",
         "operation_description": "List all active departments."},
        {"operation_name": "list_locations", "operation_type": "read",
         "operation_description": "List all active locations."},
        {"operation_name": "list_job_codes", "operation_type": "read",
         "operation_description": "List all active job codes."},
        {"operation_name": "list_pay_grades", "operation_type": "read",
         "operation_description": "List all pay grades with salary bands."},
        {"operation_name": "list_companies", "operation_type": "read",
         "operation_description": "List all active companies."},
        {"operation_name": "list_event_reasons", "operation_type": "read",
         "operation_description": "List event reason codes. Optionally filter by event_type."},
        {"operation_name": "list_time_off_types", "operation_type": "read",
         "operation_description": "List available time-off types (e.g. Vacation, Sick Leave, PTO)."},
        {"operation_name": "list_employees", "operation_type": "read",
         "operation_description": "List employees. Optionally filter by dept, location, status."},
        {"operation_name": "get_employee", "operation_type": "read",
         "operation_description": "Get full employee profile (person + job + employment) by person_id."},
        {"operation_name": "get_job", "operation_type": "read",
         "operation_description": "Get the current active job record for an employee."},
        {"operation_name": "create_employee", "operation_type": "write",
         "operation_description": (
             "Create a new employee. Required: first_name, last_name, hire_date (YYYY-MM-DD), "
             "job_code, location_code, company_code, dept_code, pay_grade. "
             "Optional: manager_id, gender, date_of_birth, nationality."
         )},
        {"operation_name": "update_job", "operation_type": "write",
         "operation_description": (
             "Update an employee's job assignment (transfer, promotion, manager change). "
             "Creates a new time-slice record. Required: person_id, event_reason_code. "
             "Optional: job_code, department_code, location_code, manager_id, pay_grade, fte."
         )},
        {"operation_name": "terminate_employee", "operation_type": "write",
         "operation_description": (
             "Terminate an employee. Closes employment and job records. "
             "termination_reason_code must be a code with event_type='Termination'."
         )},
        {"operation_name": "get_time_off_balance", "operation_type": "read",
         "operation_description": "Get time-off balances for an employee."},
        {"operation_name": "list_time_off_requests", "operation_type": "read",
         "operation_description": "List time-off requests. Optionally filter by person_id and/or status."},
        {"operation_name": "create_time_off_request", "operation_type": "write",
         "operation_description": (
             "Submit a time-off request. Required: person_id, time_off_type_code, "
             "start_date, end_date, total_days. total_days must be > 0 and balance must be sufficient."
         )},
        {"operation_name": "approve_time_off_request", "operation_type": "write",
         "operation_description": "Approve a Pending time-off request by request_id."},
        {"operation_name": "list_requisitions", "operation_type": "read",
         "operation_description": "List job requisitions. Optionally filter by status and dept_code."},
        {"operation_name": "get_requisition", "operation_type": "read",
         "operation_description": "Get a job requisition by req_id."},
        {"operation_name": "create_requisition", "operation_type": "write",
         "operation_description": (
             "Create a new job requisition. Required: req_title, job_code, department_code, "
             "location_code, hiring_manager_id."
         )},
        {"operation_name": "create_candidate", "operation_type": "write",
         "operation_description": "Create a new candidate profile. Required: first_name, last_name, email."},
        {"operation_name": "create_application", "operation_type": "write",
         "operation_description": "Submit a candidate application. Requisition must be Open."},
        {"operation_name": "update_application", "operation_type": "write",
         "operation_description": (
             "Advance an application through the pipeline. "
             "Status order (forward-only): New → Under Review → Interview → Offer → Hired/Rejected."
         )},
        {"operation_name": "create_offer", "operation_type": "write",
         "operation_description": (
             "Extend a job offer. Required: application_id, offer_date, base_salary. "
             "base_salary must be within the pay grade's min/max salary band."
         )},
        {"operation_name": "update_offer", "operation_type": "write",
         "operation_description": "Update an offer status (offer_status='Accepted' or 'Declined')."},
        {"operation_name": "get_offer", "operation_type": "read",
         "operation_description": "Get the current offer for an application."},
        {"operation_name": "list_applications", "operation_type": "read",
         "operation_description": "List applications, optionally filtered by req_id, candidate_id, or status."},
        {"operation_name": "list_reviews", "operation_type": "read",
         "operation_description": "List performance reviews. Optionally filter by person_id or status."},
        {"operation_name": "get_review", "operation_type": "read",
         "operation_description": "Get a performance review by review_id."},
        {"operation_name": "update_review", "operation_type": "write",
         "operation_description": (
             "Update a performance review. Status machine (forward-only): "
             "Draft → In Progress → Completed → Approved. Can also set overall_rating."
         )},
    ],
    "constraints_rules": [
        "employment_status must be 'Active' or 'Terminated'.",
        "termination_reason_code must reference an event_reason with event_type='Termination'.",
        "time-off request total_days must be > 0 and not exceed available balance.",
        "time-off request status: Pending → Approved or Rejected or Cancelled (forward-only).",
        "application status order (forward-only): New → Under Review → Interview → Offer → Hired/Rejected.",
        "offer base_salary must be within the pay grade's min_salary and max_salary range.",
        "offer_status: Pending → Accepted or Declined.",
        "requisition must be Open to accept new applications.",
        "performance review status (forward-only): Draft → In Progress → Completed → Approved.",
        "pay_grade must be a valid pay grade code from fod_pay_grade.",
        "job_code must be a valid job code from fod_job_code.",
        "department_code must be a valid code from fod_department.",
        "location_code must be a valid code from fod_location.",
        "manager_id must reference an existing Active employee.",
    ],
}


# ── DB state reader ────────────────────────────────────────────────────────────

def _read_db_state(db_path: Path) -> dict:
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    def _rows(sql: str) -> list[dict]:
        return [dict(r) for r in conn.execute(sql).fetchall()]

    state = {
        "employees": _rows(
            "SELECT p.person_id, p.first_name, p.last_name, j.employment_status, "
            "j.department_code, j.job_code, j.pay_grade "
            "FROM per_person p JOIN emp_job j ON p.person_id = j.person_id "
            "WHERE j.employment_status = 'Active' AND j.end_date IS NULL LIMIT 20"
        ),
        "departments": _rows("SELECT department_code, department_name FROM fod_department"),
        "job_codes": _rows("SELECT job_code, job_title, job_level FROM fod_job_code LIMIT 15"),
        "pay_grades": _rows("SELECT pay_grade_code, min_salary, max_salary FROM fod_pay_grade"),
        "requisitions": _rows(
            "SELECT req_id, req_title, req_status, department_code FROM rcm_job_requisition LIMIT 10"
        ),
        "time_off_requests": _rows(
            "SELECT request_id, person_id, request_status, total_days FROM tm_time_off_request "
            "WHERE request_status='Pending' LIMIT 10"
        ),
        "reviews": _rows(
            "SELECT review_id, person_id, review_status FROM pm_performance_review LIMIT 10"
        ),
    }
    conn.close()
    return state


# ── Task generation (reuse airline Step-2 pattern) ────────────────────────────

def _build_prompt(env_item: dict, init_state: dict) -> str:
    op_lines = []
    for i, op in enumerate(env_item["operation_list"]):
        op_lines.append(
            f"{i}.\nOperation Name: {op['operation_name']}\n"
            f"Operation Type: {op['operation_type']}\n"
            f"Description: {op['operation_description']}"
        )
    op_str = "\n".join(op_lines)
    rule_str = "- " + "\n- ".join(env_item["constraints_rules"])
    return _STEP2_TEMPLATE.format(
        env_introduction=env_item["environment_introduction"],
        env_state_definition=env_item["state_space_definition"],
        env_modify_operation=op_str,
        env_rule=rule_str,
        env_init_state=json.dumps(init_state, indent=2),
    )


def _parse_task(response: str) -> tuple[bool, str | None]:
    if "</think>" in response:
        response = response.split("</think>")[1]
    if "# Analysis" in response:
        response = response.split("# Analysis")[1]
        if "# Task" in response:
            task = response.split("# Task")[1].strip("\n* ")
            return True, task
    return False, None


def generate_tasks(n: int, out_path: Path) -> None:
    client = OpenAI(base_url=PROXY_BASE_URL, api_key="anything")
    init_state = _read_db_state(BASELINE_DB)
    prompt = _build_prompt(HR_ENV_ITEM, init_state)

    tasks: list[dict] = []
    task_attempts = 0
    max_task_attempts = n * 3

    print(f"Generating {n} EnvScaler tasks for HR environment...")
    print(f"  Model: {MODEL}  |  Baseline DB: {BASELINE_DB.name}")

    while len(tasks) < n and task_attempts < max_task_attempts:
        task_attempts += 1
        task = None
        for retry in range(3):
            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    max_tokens=1024,
                    temperature=0.7,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.choices[0].message.content or ""
                parsed_success, task = _parse_task(raw)
                if parsed_success:
                    break
                print(f"  [attempt {task_attempts}, retry {retry + 1}] parse failed...")
            except Exception as e:
                print(f"  [attempt {task_attempts}, retry {retry + 1}] error: {e}")

        if task:
            tasks.append({
                "task_id": f"envscaler_hr_{len(tasks):03d}",
                "task": task,
                "generated_at": datetime.utcnow().isoformat(),
            })
            print(f"  [{len(tasks):2d}/{n}] OK — {task[:80]}...")
        else:
            print(f"  [attempt {task_attempts}] failed after 3 retries, skipping...")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(tasks, f, indent=2)

    print(f"\nSaved {len(tasks)} tasks → {out_path}")
    if len(tasks) < n:
        print(f"WARNING: only generated {len(tasks)}/{n} tasks after {task_attempts} attempts.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate EnvScaler-style tasks for the HR environment.")
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).parent / "envscaler_hr_tasks.json")
    args = parser.parse_args()
    generate_tasks(args.n, args.out)
