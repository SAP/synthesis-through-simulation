import datetime
import uuid
from typing import List, Optional

from synthesize.environments.hr.db.db import get_conn
from synthesize.environments.hr.db.models import (
    Employee,
    Employment,
    JobInfo,
    Person,
    row_to_dict,
)

# ── Private helpers ────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(sep=" ", timespec="seconds")


def _person_from_row(row) -> Person:
    d = row_to_dict(row)
    return Person(
        person_id=d["person_id"],
        person_id_external=d["person_id_external"],
        first_name=d["first_name"],
        last_name=d["last_name"],
        middle_name=d.get("middle_name"),
        preferred_name=d.get("preferred_name"),
        date_of_birth=d.get("date_of_birth"),
        gender=d.get("gender"),
        nationality=d.get("nationality"),
        marital_status=d.get("marital_status"),
        person_type=d.get("person_type", "Employee"),
    )


def _employment_from_row(row) -> Employment:
    d = row_to_dict(row)
    return Employment(
        employment_id=d["employment_id"],
        person_id=d["person_id"],
        start_date=d["start_date"],
        end_date=d.get("end_date"),
        hire_date=d["hire_date"],
        termination_date=d.get("termination_date"),
        termination_reason_code=d.get("termination_reason_code"),
        employment_type=d.get("employment_type", "Active"),
        employee_class=d.get("employee_class"),
    )


def _job_from_row(row) -> JobInfo:
    d = row_to_dict(row)
    return JobInfo(
        job_info_id=d["job_info_id"],
        person_id=d["person_id"],
        start_date=d["start_date"],
        end_date=d.get("end_date"),
        event_reason_code=d.get("event_reason_code"),
        job_code=d["job_code"],
        position_id=d.get("position_id"),
        department_code=d.get("department_code"),
        location_code=d["location_code"],
        company_code=d["company_code"],
        manager_id=d.get("manager_id"),
        pay_grade=d.get("pay_grade"),
        fte=d.get("fte", 1.0),
        employment_status=d.get("employment_status", "Active"),
    )


def _next_person_id_external(conn) -> str:
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(person_id_external, 4) AS INT)) AS max_num "
        "FROM per_person WHERE person_id_external LIKE 'EMP%'"
    ).fetchone()
    max_num = row["max_num"] if row and row["max_num"] is not None else 0
    return f"EMP{max_num + 1:06d}"


def _get_direct_report_ids(conn, person_id: str) -> List[str]:
    rows = conn.execute(
        "SELECT DISTINCT person_id FROM emp_job WHERE manager_id = ? AND end_date IS NULL",
        (person_id,),
    ).fetchall()
    return [r["person_id"] for r in rows]


def _is_subordinate(conn, manager_id: str, candidate_id: str) -> bool:
    """Return True if candidate_id is anywhere in the reporting chain below manager_id."""
    visited = set()
    queue = _get_direct_report_ids(conn, manager_id)
    while queue:
        pid = queue.pop()
        if pid == candidate_id:
            return True
        if pid not in visited:
            visited.add(pid)
            queue.extend(_get_direct_report_ids(conn, pid))
    return False


# ── Public read functions ──────────────────────────────────────────────────────


def list_employees(
    dept=None,
    location=None,
    status=None,
    manager_id=None,
    limit: int = 50,
    offset: int = 0,
) -> List[Employee]:
    sql = (
        "SELECT DISTINCT p.* FROM per_person p "
        "JOIN emp_job j ON j.person_id = p.person_id AND j.end_date IS NULL "
        "WHERE 1=1"
    )
    params: list = []
    if dept:
        sql += " AND j.department_code = ?"
        params.append(dept)
    if location:
        sql += " AND j.location_code = ?"
        params.append(location)
    if status:
        sql += " AND j.employment_status = ?"
        params.append(status)
    if manager_id:
        sql += " AND j.manager_id = ?"
        params.append(manager_id)
    sql += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            person = _person_from_row(row)
            emp_row = conn.execute(
                "SELECT * FROM emp_employment WHERE person_id = ? ORDER BY employment_id DESC LIMIT 1",
                (person.person_id,),
            ).fetchone()
            job_row = conn.execute(
                "SELECT * FROM emp_job WHERE person_id = ? AND end_date IS NULL LIMIT 1",
                (person.person_id,),
            ).fetchone()
            emails = [
                row_to_dict(r)
                for r in conn.execute(
                    "SELECT * FROM per_email WHERE person_id = ?", (person.person_id,)
                ).fetchall()
            ]
            phones = [
                row_to_dict(r)
                for r in conn.execute(
                    "SELECT * FROM per_phone WHERE person_id = ?", (person.person_id,)
                ).fetchall()
            ]
            result.append(
                Employee(
                    person=person,
                    employment=_employment_from_row(emp_row) if emp_row else None,
                    job=_job_from_row(job_row) if job_row else None,
                    emails=emails,
                    phones=phones,
                )
            )
        return result


def get_employee(person_id: str) -> Employee:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM per_person WHERE person_id = ?", (person_id,)).fetchone()
        if not row:
            raise LookupError(f"Person not found: {person_id}")
        person = _person_from_row(row)

        emp_row = conn.execute(
            "SELECT * FROM emp_employment WHERE person_id = ? ORDER BY employment_id DESC LIMIT 1",
            (person_id,),
        ).fetchone()
        job_row = conn.execute(
            "SELECT * FROM emp_job WHERE person_id = ? AND end_date IS NULL LIMIT 1",
            (person_id,),
        ).fetchone()
        emails = [
            row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM per_email WHERE person_id = ?", (person_id,)
            ).fetchall()
        ]
        phones = [
            row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM per_phone WHERE person_id = ?", (person_id,)
            ).fetchall()
        ]
        return Employee(
            person=person,
            employment=_employment_from_row(emp_row) if emp_row else None,
            job=_job_from_row(job_row) if job_row else None,
            emails=emails,
            phones=phones,
        )


def get_employment(person_id: str) -> Employment:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM emp_employment WHERE person_id = ? ORDER BY employment_id DESC LIMIT 1",
            (person_id,),
        ).fetchone()
        if not row:
            raise LookupError(f"Employment record not found for person: {person_id}")
        return _employment_from_row(row)


def get_job(person_id: str) -> JobInfo:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM emp_job WHERE person_id = ? AND end_date IS NULL LIMIT 1",
            (person_id,),
        ).fetchone()
        if not row:
            raise LookupError(f"No current job record found for person: {person_id}")
        return _job_from_row(row)


def get_job_history(person_id: str) -> List[JobInfo]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM emp_job WHERE person_id = ? ORDER BY start_date DESC",
            (person_id,),
        ).fetchall()
        return [_job_from_row(r) for r in rows]


def get_manager(person_id: str) -> Optional[Person]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT manager_id FROM emp_job WHERE person_id = ? AND end_date IS NULL LIMIT 1",
            (person_id,),
        ).fetchone()
        if not row or not row["manager_id"]:
            return None
        mgr_row = conn.execute(
            "SELECT * FROM per_person WHERE person_id = ?", (row["manager_id"],)
        ).fetchone()
        if not mgr_row:
            return None
        return _person_from_row(mgr_row)


def get_direct_reports(person_id: str) -> List[Person]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT p.* FROM per_person p "
            "JOIN emp_job j ON j.person_id = p.person_id AND j.end_date IS NULL "
            "WHERE j.manager_id = ?",
            (person_id,),
        ).fetchall()
        return [_person_from_row(r) for r in rows]


def get_org_path(person_id: str) -> List[Person]:
    chain: List[Person] = []
    visited = set()
    current_id = person_id
    with get_conn() as conn:
        while current_id and current_id not in visited:
            visited.add(current_id)
            person_row = conn.execute(
                "SELECT * FROM per_person WHERE person_id = ?", (current_id,)
            ).fetchone()
            if not person_row:
                break
            chain.append(_person_from_row(person_row))
            job_row = conn.execute(
                "SELECT manager_id FROM emp_job WHERE person_id = ? AND end_date IS NULL LIMIT 1",
                (current_id,),
            ).fetchone()
            if not job_row or not job_row["manager_id"]:
                break
            current_id = job_row["manager_id"]
    return chain


# ── Write functions ────────────────────────────────────────────────────────────


def create_employee(
    first_name: str,
    last_name: str,
    hire_date: str,
    job_code: str,
    location_code: str,
    company_code: str,
    dept_code: str,
    pay_grade: str,
    manager_id: Optional[str] = None,
    middle_name: Optional[str] = None,
    gender: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    nationality: Optional[str] = None,
    employment_type: str = "Active",
) -> Employee:
    with get_conn() as conn:
        hire_reason_row = conn.execute(
            "SELECT event_reason_code FROM fod_event_reason WHERE event_type = 'Hire' LIMIT 1"
        ).fetchone()
        if not hire_reason_row:
            raise ValueError("No Hire event reason found in fod_event_reason")
        hire_event_reason = hire_reason_row["event_reason_code"]

        person_id = str(uuid.uuid4())
        person_id_external = _next_person_id_external(conn)

        conn.execute(
            """
            INSERT INTO per_person
                (person_id, person_id_external, first_name, last_name, middle_name,
                 gender, date_of_birth, nationality, person_type, created_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Employee', ?)
            """,
            (
                person_id,
                person_id_external,
                first_name,
                last_name,
                middle_name,
                gender,
                date_of_birth,
                nationality,
                _now(),
            ),
        )

        conn.execute(
            """
            INSERT INTO emp_employment
                (person_id, start_date, hire_date, employment_type, created_on)
            VALUES (?, ?, ?, ?, ?)
            """,
            (person_id, hire_date, hire_date, employment_type, _now()),
        )

        conn.execute(
            """
            INSERT INTO emp_job
                (person_id, start_date, event_reason_code, job_code, location_code,
                 company_code, department_code, manager_id, pay_grade, fte, employment_status,
                 created_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, 'Active', ?)
            """,
            (
                person_id,
                hire_date,
                hire_event_reason,
                job_code,
                location_code,
                company_code,
                dept_code,
                manager_id,
                pay_grade,
                _now(),
            ),
        )

    return get_employee(person_id)


def update_personal_info(person_id: str, **kwargs) -> Person:
    allowed = {
        "first_name",
        "last_name",
        "middle_name",
        "preferred_name",
        "gender",
        "nationality",
        "marital_status",
    }
    bad = set(kwargs) - allowed
    if bad:
        raise ValueError(
            f"Cannot update field(s): {', '.join(sorted(bad))}. "
            f"Allowed: {', '.join(sorted(allowed))}"
        )
    if not kwargs:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM per_person WHERE person_id = ?", (person_id,)
            ).fetchone()
            if not row:
                raise LookupError(f"Person not found: {person_id}")
            return _person_from_row(row)

    set_clause = ", ".join(f"{k} = ?" for k in kwargs) + ", last_modified_on = ?"
    values = list(kwargs.values()) + [_now(), person_id]
    with get_conn() as conn:
        cursor = conn.execute(f"UPDATE per_person SET {set_clause} WHERE person_id = ?", values)
        if cursor.rowcount == 0:
            raise LookupError(f"Person not found: {person_id}")
        row = conn.execute("SELECT * FROM per_person WHERE person_id = ?", (person_id,)).fetchone()
        return _person_from_row(row)


def update_job(person_id: str, event_reason_code: str, **kwargs) -> JobInfo:
    allowed = {
        "job_code",
        "location_code",
        "department_code",
        "division_code",
        "manager_id",
        "pay_grade",
        "position_id",
        "company_code",
        "business_unit_code",
        "cost_center_code",
        "fte",
    }
    bad = set(kwargs) - allowed
    if bad:
        raise ValueError(
            f"Unknown job field(s): {', '.join(sorted(bad))}. Allowed: {', '.join(sorted(allowed))}"
        )

    with get_conn() as conn:
        reason_row = conn.execute(
            "SELECT event_reason_code FROM fod_event_reason WHERE event_reason_code = ?",
            (event_reason_code,),
        ).fetchone()
        if not reason_row:
            raise ValueError(f"Event reason code not found: {event_reason_code}")

        current_row = conn.execute(
            "SELECT * FROM emp_job WHERE person_id = ? AND end_date IS NULL LIMIT 1",
            (person_id,),
        ).fetchone()
        if not current_row:
            raise ValueError(f"No current job record found for person: {person_id}")

        current = row_to_dict(current_row)

        conn.execute(
            "UPDATE emp_job SET end_date = date('now') WHERE person_id = ? AND end_date IS NULL",
            (person_id,),
        )

        new_job = {
            "job_code": kwargs.get("job_code", current["job_code"]),
            "location_code": kwargs.get("location_code", current["location_code"]),
            "department_code": kwargs.get("department_code", current.get("department_code")),
            "division_code": kwargs.get("division_code", current.get("division_code")),
            "manager_id": kwargs.get("manager_id", current.get("manager_id")),
            "pay_grade": kwargs.get("pay_grade", current.get("pay_grade")),
            "position_id": kwargs.get("position_id", current.get("position_id")),
            "company_code": kwargs.get("company_code", current["company_code"]),
            "business_unit_code": kwargs.get(
                "business_unit_code", current.get("business_unit_code")
            ),
            "cost_center_code": kwargs.get("cost_center_code", current.get("cost_center_code")),
            "fte": kwargs.get("fte", current.get("fte", 1.0)),
        }

        conn.execute(
            """
            INSERT INTO emp_job
                (person_id, start_date, event_reason_code, job_code, location_code,
                 department_code, division_code, manager_id, pay_grade, position_id,
                 company_code, business_unit_code, cost_center_code, fte, employment_status,
                 created_on)
            VALUES (?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?)
            """,
            (
                person_id,
                event_reason_code,
                new_job["job_code"],
                new_job["location_code"],
                new_job["department_code"],
                new_job["division_code"],
                new_job["manager_id"],
                new_job["pay_grade"],
                new_job["position_id"],
                new_job["company_code"],
                new_job["business_unit_code"],
                new_job["cost_center_code"],
                new_job["fte"],
                _now(),
            ),
        )

        row = conn.execute(
            "SELECT * FROM emp_job WHERE person_id = ? AND end_date IS NULL LIMIT 1",
            (person_id,),
        ).fetchone()
        return _job_from_row(row)


def update_manager(person_id: str, new_manager_id: str) -> JobInfo:
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (new_manager_id,)
        ).fetchone():
            raise ValueError(f"Manager person_id not found: {new_manager_id}")
        if person_id == new_manager_id:
            raise ValueError("An employee cannot be their own manager.")
        if _is_subordinate(conn, person_id, new_manager_id):
            raise ValueError(
                f"{new_manager_id} is a direct or indirect report of {person_id}. "
                "Setting them as manager would create a circular hierarchy."
            )

        transfer_row = conn.execute(
            "SELECT event_reason_code FROM fod_event_reason WHERE event_type = 'Transfer' LIMIT 1"
        ).fetchone()
        if not transfer_row:
            raise ValueError("No Transfer event reason found in fod_event_reason")
        transfer_code = transfer_row["event_reason_code"]

    return update_job(person_id, transfer_code, manager_id=new_manager_id)


def terminate_employee(
    person_id: str,
    termination_date: str,
    termination_reason_code: str,
    comments: Optional[str] = None,
) -> Employment:
    with get_conn() as conn:
        reason_row = conn.execute(
            "SELECT event_reason_code FROM fod_event_reason "
            "WHERE event_reason_code = ? AND event_type = 'Termination'",
            (termination_reason_code,),
        ).fetchone()
        if not reason_row:
            raise ValueError(
                f"Termination reason code not found or not of type 'Termination': "
                f"{termination_reason_code}"
            )

        pending_wf = conn.execute(
            """
            SELECT wi.workflow_id, wi.workflow_type FROM wf_workflow_instance wi
            WHERE wi.workflow_status = 'Pending'
              AND (
                wi.subject_person_id = ?
                OR wi.workflow_id IN (
                    SELECT workflow_id FROM wf_approval_step
                    WHERE approver_person_id = ? AND step_status = 'Pending'
                )
              )
            """,
            (person_id, person_id),
        ).fetchall()
        if pending_wf:
            ids = ", ".join(r["workflow_id"] for r in pending_wf)
            raise ValueError(f"Cannot terminate: employee has pending workflow(s): {ids}")

        emp_row = conn.execute(
            "SELECT * FROM emp_employment WHERE person_id = ? ORDER BY employment_id DESC LIMIT 1",
            (person_id,),
        ).fetchone()
        if not emp_row:
            raise LookupError(f"Employment record not found for person: {person_id}")

        conn.execute(
            """
            UPDATE emp_employment
            SET termination_date = ?,
                termination_reason_code = ?,
                employment_type = 'Terminated',
                end_date = ?,
                last_modified_on = ?
            WHERE employment_id = ?
            """,
            (
                termination_date,
                termination_reason_code,
                termination_date,
                _now(),
                emp_row["employment_id"],
            ),
        )

        conn.execute(
            "UPDATE emp_job SET end_date = ? WHERE person_id = ? AND end_date IS NULL",
            (termination_date, person_id),
        )

        updated_row = conn.execute(
            "SELECT * FROM emp_employment WHERE employment_id = ?",
            (emp_row["employment_id"],),
        ).fetchone()
        return _employment_from_row(updated_row)
