import datetime
import uuid
from typing import List, Optional

from synthesize.environments.hr.db.db import get_conn
from synthesize.environments.hr.db.models import (
    Application,
    Candidate,
    Interview,
    JobRequisition,
    Offer,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(sep=" ", timespec="seconds")


def _row_to_requisition(row) -> JobRequisition:
    return JobRequisition(
        req_id=row["req_id"],
        req_title=row["req_title"],
        job_code=row["job_code"],
        department_code=row["department_code"],
        location_code=row["location_code"],
        hiring_manager_person_id=row["hiring_manager_person_id"],
        recruiter_person_id=row["recruiter_person_id"],
        number_of_openings=row["number_of_openings"],
        employment_type=row["employment_type"],
        req_status=row["req_status"],
        opening_date=row["opening_date"],
        target_hire_date=row["target_hire_date"],
        salary_min=row["salary_min"],
        salary_max=row["salary_max"],
    )


def _row_to_candidate(row) -> Candidate:
    return Candidate(
        candidate_id=row["candidate_id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        email=row["email"],
        phone=row["phone"],
        source=row["source"],
        current_company=row["current_company"],
        current_title=row["current_title"],
        years_of_experience=row["years_of_experience"],
        candidate_status=row["candidate_status"],
    )


def _row_to_application(row) -> Application:
    return Application(
        application_id=row["application_id"],
        req_id=row["req_id"],
        candidate_id=row["candidate_id"],
        application_date=row["application_date"],
        application_status=row["application_status"],
        current_stage=row["current_stage"],
        rating=row["rating"],
        rejection_reason=row["rejection_reason"],
        offer_extended_date=row["offer_extended_date"],
        offer_accepted_date=row["offer_accepted_date"],
    )


def _row_to_interview(row) -> Interview:
    return Interview(
        interview_id=row["interview_id"],
        application_id=row["application_id"],
        interviewer_person_id=row["interviewer_person_id"],
        interview_type=row["interview_type"],
        interview_date=row["interview_date"],
        interview_status=row["interview_status"],
        rating=row["rating"],
        recommendation=row["recommendation"],
        feedback=row["feedback"],
    )


def _row_to_offer(row) -> Offer:
    return Offer(
        offer_id=row["offer_id"],
        application_id=row["application_id"],
        offer_date=row["offer_date"],
        offer_expiry_date=row["offer_expiry_date"],
        job_title=row["job_title"],
        start_date=row["start_date"],
        base_salary=row["base_salary"],
        currency=row["currency"],
        sign_on_bonus=row["sign_on_bonus"],
        stock_grant=row["stock_grant"],
        offer_status=row["offer_status"],
    )


_STATUS_ORDER = ["New", "Under Review", "Interview", "Offer", "Hired", "Rejected"]


def _status_rank(status: str) -> int:
    try:
        return _STATUS_ORDER.index(status)
    except ValueError:
        return -1


# ── Requisitions ──────────────────────────────────────────────────────────────


def list_requisitions(status=None, dept_code=None, limit=50, offset=0) -> List[JobRequisition]:
    query = "SELECT * FROM rcm_job_requisition WHERE 1=1"
    params: list = []
    if status is not None:
        query += " AND req_status = ?"
        params.append(status)
    if dept_code is not None:
        query += " AND department_code = ?"
        params.append(dept_code)
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_requisition(r) for r in rows]


def get_requisition(req_id: str) -> JobRequisition:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM rcm_job_requisition WHERE req_id = ?", (req_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"Requisition '{req_id}' not found")
    return _row_to_requisition(row)


def create_requisition(
    req_title,
    job_code,
    department_code,
    location_code,
    hiring_manager_person_id,
    recruiter_person_id=None,
    number_of_openings=1,
    employment_type="Full-Time",
    target_hire_date=None,
    salary_min=None,
    salary_max=None,
    job_description=None,
    requirements=None,
) -> JobRequisition:
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM fod_job_code WHERE job_code = ?", (job_code,)
        ).fetchone():
            raise ValueError(f"job_code '{job_code}' does not exist")
        if not conn.execute(
            "SELECT 1 FROM fod_department WHERE department_code = ?", (department_code,)
        ).fetchone():
            raise ValueError(f"department_code '{department_code}' does not exist")
        if not conn.execute(
            "SELECT 1 FROM fod_location WHERE location_code = ?", (location_code,)
        ).fetchone():
            raise ValueError(f"location_code '{location_code}' does not exist")
        if not conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (hiring_manager_person_id,)
        ).fetchone():
            raise ValueError(
                f"hiring_manager_person_id '{hiring_manager_person_id}' does not exist"
            )
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            raise ValueError("salary_min must be <= salary_max")

        req_id = str(uuid.uuid4())
        today = datetime.date.today().isoformat()
        conn.execute(
            """
            INSERT INTO rcm_job_requisition (
                req_id, req_title, job_code, department_code, location_code,
                hiring_manager_person_id, recruiter_person_id, number_of_openings,
                employment_type, req_status, opening_date, target_hire_date,
                salary_min, salary_max, job_description, requirements, created_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req_id,
                req_title,
                job_code,
                department_code,
                location_code,
                hiring_manager_person_id,
                recruiter_person_id,
                number_of_openings,
                employment_type,
                today,
                target_hire_date,
                salary_min,
                salary_max,
                job_description,
                requirements,
                _now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM rcm_job_requisition WHERE req_id = ?", (req_id,)
        ).fetchone()
    return _row_to_requisition(row)


def update_requisition(req_id, **kwargs) -> JobRequisition:
    allowed = {
        "req_title",
        "req_status",
        "target_hire_date",
        "salary_min",
        "salary_max",
        "job_description",
        "requirements",
        "number_of_openings",
        "recruiter_person_id",
    }
    invalid = set(kwargs) - allowed
    if invalid:
        raise ValueError(f"Cannot update fields: {invalid}")

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM rcm_job_requisition WHERE req_id = ?", (req_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Requisition '{req_id}' not found")

        current_status = row["req_status"]
        new_status = kwargs.get("req_status", current_status)
        if current_status in ("Cancelled", "Filled") and new_status != current_status:
            raise ValueError(f"Cannot reopen a requisition with status '{current_status}'")

        if not kwargs:
            return _row_to_requisition(row)

        set_clauses = ", ".join(f"{k} = ?" for k in kwargs) + ", last_modified_on = ?"
        values = list(kwargs.values()) + [_now(), req_id]
        conn.execute(f"UPDATE rcm_job_requisition SET {set_clauses} WHERE req_id = ?", values)
        row = conn.execute(
            "SELECT * FROM rcm_job_requisition WHERE req_id = ?", (req_id,)
        ).fetchone()
    return _row_to_requisition(row)


# ── Candidates ────────────────────────────────────────────────────────────────


def get_candidate(candidate_id: str) -> Candidate:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM rcm_candidate WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"Candidate '{candidate_id}' not found")
    return _row_to_candidate(row)


def create_candidate(
    first_name,
    last_name,
    email,
    phone=None,
    source=None,
    current_company=None,
    current_title=None,
    years_of_experience=None,
    location=None,
) -> Candidate:
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM rcm_candidate WHERE email = ?", (email,)).fetchone():
            raise ValueError(f"A candidate with email '{email}' already exists")

        candidate_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO rcm_candidate (
                candidate_id, first_name, last_name, email, phone, source,
                current_company, current_title, years_of_experience, location,
                candidate_status, created_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?)
            """,
            (
                candidate_id,
                first_name,
                last_name,
                email,
                phone,
                source,
                current_company,
                current_title,
                years_of_experience,
                location,
                _now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM rcm_candidate WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
    return _row_to_candidate(row)


# ── Applications ──────────────────────────────────────────────────────────────


def list_applications(req_id=None, candidate_id=None, status=None) -> List[Application]:
    query = "SELECT * FROM rcm_application WHERE 1=1"
    params: list = []
    if req_id is not None:
        query += " AND req_id = ?"
        params.append(req_id)
    if candidate_id is not None:
        query += " AND candidate_id = ?"
        params.append(candidate_id)
    if status is not None:
        query += " AND application_status = ?"
        params.append(status)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_application(r) for r in rows]


def get_application(application_id: str) -> Application:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM rcm_application WHERE application_id = ?", (application_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"Application '{application_id}' not found")
    return _row_to_application(row)


def list_req_applications(req_id: str) -> List[Application]:
    return list_applications(req_id=req_id)


def create_application(req_id, candidate_id, application_date=None) -> Application:
    with get_conn() as conn:
        req_row = conn.execute(
            "SELECT * FROM rcm_job_requisition WHERE req_id = ?", (req_id,)
        ).fetchone()
        if req_row is None:
            raise LookupError(f"Requisition '{req_id}' not found")
        if req_row["req_status"] != "Open":
            raise ValueError(
                f"Requisition '{req_id}' is not open (status: {req_row['req_status']})"
            )

        if not conn.execute(
            "SELECT 1 FROM rcm_candidate WHERE candidate_id = ?", (candidate_id,)
        ).fetchone():
            raise LookupError(f"Candidate '{candidate_id}' not found")

        existing = conn.execute(
            """
            SELECT 1 FROM rcm_application
            WHERE req_id = ? AND candidate_id = ?
              AND application_status NOT IN ('Rejected', 'Hired')
            """,
            (req_id, candidate_id),
        ).fetchone()
        if existing:
            raise ValueError(
                f"Candidate '{candidate_id}' already has an active application to requisition '{req_id}'"
            )

        application_id = str(uuid.uuid4())
        app_date = application_date or datetime.date.today().isoformat()
        conn.execute(
            """
            INSERT INTO rcm_application (
                application_id, req_id, candidate_id, application_date,
                application_status, current_stage, created_on
            ) VALUES (?, ?, ?, ?, 'New', 'Applied', ?)
            """,
            (application_id, req_id, candidate_id, app_date, _now()),
        )
        row = conn.execute(
            "SELECT * FROM rcm_application WHERE application_id = ?", (application_id,)
        ).fetchone()
    return _row_to_application(row)


def update_application(
    application_id,
    application_status=None,
    current_stage=None,
    rating=None,
    rejection_reason=None,
) -> Application:
    with get_conn() as conn:
        app_row = conn.execute(
            "SELECT * FROM rcm_application WHERE application_id = ?", (application_id,)
        ).fetchone()
        if app_row is None:
            raise LookupError(f"Application '{application_id}' not found")

        current_status = app_row["application_status"]
        new_status = application_status if application_status is not None else current_status

        if application_status is not None and application_status != current_status:
            terminal = {"Hired", "Rejected"}
            if current_status in terminal:
                raise ValueError(
                    f"Cannot transition application from terminal status '{current_status}'"
                )
            current_rank = _status_rank(current_status)
            new_rank = _status_rank(new_status)
            if new_rank < current_rank and new_status not in terminal:
                raise ValueError(
                    f"Cannot move application backwards from '{current_status}' to '{new_status}'"
                )
            if new_status == "Rejected" and not rejection_reason:
                raise ValueError("rejection_reason is required when status is 'Rejected'")

            if new_status == "Hired":
                req_row = conn.execute(
                    "SELECT * FROM rcm_job_requisition WHERE req_id = ?", (app_row["req_id"],)
                ).fetchone()
                filled_count = conn.execute(
                    """
                    SELECT COUNT(*) FROM rcm_application
                    WHERE req_id = ? AND application_status = 'Hired'
                      AND application_id != ?
                    """,
                    (app_row["req_id"], application_id),
                ).fetchone()[0]
                accepted_offers = conn.execute(
                    """
                    SELECT COUNT(*) FROM rcm_offer o
                    JOIN rcm_application a ON o.application_id = a.application_id
                    WHERE a.req_id = ? AND o.offer_status = 'Accepted'
                      AND a.application_id != ?
                    """,
                    (app_row["req_id"], application_id),
                ).fetchone()[0]
                if filled_count + accepted_offers >= req_row["number_of_openings"]:
                    raise ValueError(f"Requisition '{app_row['req_id']}' has no remaining openings")

        updates: dict = {}
        if application_status is not None:
            updates["application_status"] = new_status
        if current_stage is not None:
            updates["current_stage"] = current_stage
        if rating is not None:
            updates["rating"] = rating
        if rejection_reason is not None:
            updates["rejection_reason"] = rejection_reason

        if updates:
            set_clauses = ", ".join(f"{k} = ?" for k in updates) + ", last_modified_on = ?"
            values = list(updates.values()) + [_now(), application_id]
            conn.execute(
                f"UPDATE rcm_application SET {set_clauses} WHERE application_id = ?", values
            )

        if new_status == "Hired" and application_status is not None:
            conn.execute(
                "UPDATE rcm_candidate SET candidate_status = 'Hired' WHERE candidate_id = ?",
                (app_row["candidate_id"],),
            )
            req_row = conn.execute(
                "SELECT * FROM rcm_job_requisition WHERE req_id = ?", (app_row["req_id"],)
            ).fetchone()
            total_hired = conn.execute(
                """
                SELECT COUNT(*) FROM rcm_application
                WHERE req_id = ? AND application_status = 'Hired'
                """,
                (app_row["req_id"],),
            ).fetchone()[0]
            if total_hired >= req_row["number_of_openings"]:
                conn.execute(
                    "UPDATE rcm_job_requisition SET req_status = 'Filled' WHERE req_id = ?",
                    (app_row["req_id"],),
                )

        row = conn.execute(
            "SELECT * FROM rcm_application WHERE application_id = ?", (application_id,)
        ).fetchone()
    return _row_to_application(row)


# ── Interviews ────────────────────────────────────────────────────────────────


def list_interviews(application_id: str) -> List[Interview]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM rcm_interview WHERE application_id = ?", (application_id,)
        ).fetchall()
    return [_row_to_interview(r) for r in rows]


def create_interview(
    application_id,
    interviewer_person_id,
    interview_type,
    interview_date=None,
    interview_duration_mins=60,
) -> Interview:
    with get_conn() as conn:
        app_row = conn.execute(
            "SELECT * FROM rcm_application WHERE application_id = ?", (application_id,)
        ).fetchone()
        if app_row is None:
            raise LookupError(f"Application '{application_id}' not found")

        eligible_stages = {"Interview", "Offer", "Hired"}
        if app_row["application_status"] not in eligible_stages:
            raise ValueError(
                f"Application must be in Interview stage or later "
                f"(current status: {app_row['application_status']})"
            )

        if not conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (interviewer_person_id,)
        ).fetchone():
            raise LookupError(f"Person '{interviewer_person_id}' not found")

        cand_row = conn.execute(
            "SELECT * FROM rcm_candidate WHERE candidate_id = ?", (app_row["candidate_id"],)
        ).fetchone()
        if cand_row:
            person_row = conn.execute(
                "SELECT * FROM per_person WHERE person_id = ?", (interviewer_person_id,)
            ).fetchone()
            if person_row and cand_row["email"]:
                email_match = conn.execute(
                    "SELECT 1 FROM per_person_email WHERE person_id = ? AND email_address = ?",
                    (interviewer_person_id, cand_row["email"]),
                ).fetchone()
                if email_match:
                    raise ValueError("Interviewer cannot be the candidate themselves")

        if interviewer_person_id == app_row["candidate_id"]:
            raise ValueError("Interviewer cannot be the candidate themselves")

        interview_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO rcm_interview (
                interview_id, application_id, interviewer_person_id, interview_type,
                interview_date, interview_duration_mins, interview_status, created_on
            ) VALUES (?, ?, ?, ?, ?, ?, 'Scheduled', ?)
            """,
            (
                interview_id,
                application_id,
                interviewer_person_id,
                interview_type,
                interview_date,
                interview_duration_mins,
                _now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM rcm_interview WHERE interview_id = ?", (interview_id,)
        ).fetchone()
    return _row_to_interview(row)


def update_interview(
    interview_id,
    interview_status=None,
    rating=None,
    recommendation=None,
    feedback=None,
) -> Interview:
    valid_recommendations = {"Strong Hire", "Hire", "Maybe", "No Hire"}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM rcm_interview WHERE interview_id = ?", (interview_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Interview '{interview_id}' not found")

        if interview_status == "Completed" and rating is None and row["rating"] is None:
            raise ValueError("rating is required when marking an interview as Completed")

        if recommendation is not None and recommendation not in valid_recommendations:
            raise ValueError(f"recommendation must be one of: {valid_recommendations}")

        updates: dict = {}
        if interview_status is not None:
            updates["interview_status"] = interview_status
        if rating is not None:
            updates["rating"] = rating
        if recommendation is not None:
            updates["recommendation"] = recommendation
        if feedback is not None:
            updates["feedback"] = feedback

        if updates:
            set_clauses = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [interview_id]
            conn.execute(f"UPDATE rcm_interview SET {set_clauses} WHERE interview_id = ?", values)
        row = conn.execute(
            "SELECT * FROM rcm_interview WHERE interview_id = ?", (interview_id,)
        ).fetchone()
    return _row_to_interview(row)


# ── Offers ────────────────────────────────────────────────────────────────────


def get_offer(application_id: str) -> Optional[Offer]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM rcm_offer WHERE application_id = ? ORDER BY rowid DESC LIMIT 1",
            (application_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_offer(row)


def create_offer(
    application_id,
    offer_date,
    base_salary,
    job_title=None,
    start_date=None,
    offer_expiry_date=None,
    sign_on_bonus=None,
    stock_grant=None,
    currency="USD",
) -> Offer:
    with get_conn() as conn:
        app_row = conn.execute(
            "SELECT * FROM rcm_application WHERE application_id = ?", (application_id,)
        ).fetchone()
        if app_row is None:
            raise LookupError(f"Application '{application_id}' not found")

        eligible_statuses = {"Interview", "Offer"}
        if app_row["application_status"] not in eligible_statuses:
            raise ValueError(
                f"Application must be in 'Interview' or 'Offer' status "
                f"(current: {app_row['application_status']})"
            )

        active_offer = conn.execute(
            """
            SELECT 1 FROM rcm_offer
            WHERE application_id = ? AND offer_status NOT IN ('Declined', 'Expired')
            """,
            (application_id,),
        ).fetchone()
        if active_offer:
            raise ValueError(f"An active offer already exists for application '{application_id}'")

        req_row = conn.execute(
            "SELECT * FROM rcm_job_requisition WHERE req_id = ?", (app_row["req_id"],)
        ).fetchone()
        if req_row["salary_min"] is not None and base_salary < req_row["salary_min"]:
            raise ValueError(
                f"base_salary {base_salary} is below requisition salary_min {req_row['salary_min']}"
            )
        if req_row["salary_max"] is not None and base_salary > req_row["salary_max"]:
            raise ValueError(
                f"base_salary {base_salary} exceeds requisition salary_max {req_row['salary_max']}"
            )

        accepted_count = conn.execute(
            """
            SELECT COUNT(*) FROM rcm_offer o
            JOIN rcm_application a ON o.application_id = a.application_id
            WHERE a.req_id = ? AND o.offer_status = 'Accepted'
            """,
            (app_row["req_id"],),
        ).fetchone()[0]
        if accepted_count >= req_row["number_of_openings"]:
            raise ValueError(f"Requisition '{app_row['req_id']}' is already at headcount capacity")

        offer_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO rcm_offer (
                offer_id, application_id, offer_date, offer_expiry_date, job_title,
                start_date, base_salary, currency, sign_on_bonus, stock_grant, offer_status,
                created_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Extended', ?)
            """,
            (
                offer_id,
                application_id,
                offer_date,
                offer_expiry_date,
                job_title,
                start_date,
                base_salary,
                currency,
                sign_on_bonus,
                stock_grant,
                _now(),
            ),
        )
        conn.execute(
            "UPDATE rcm_application SET application_status = 'Offer', offer_extended_date = ? WHERE application_id = ?",
            (offer_date, application_id),
        )
        row = conn.execute("SELECT * FROM rcm_offer WHERE offer_id = ?", (offer_id,)).fetchone()
    return _row_to_offer(row)


def update_offer(
    offer_id,
    offer_status=None,
    base_salary=None,
    sign_on_bonus=None,
    start_date=None,
    **kwargs,
) -> Offer:
    with get_conn() as conn:
        offer_row = conn.execute(
            "SELECT * FROM rcm_offer WHERE offer_id = ?", (offer_id,)
        ).fetchone()
        if offer_row is None:
            raise LookupError(f"Offer '{offer_id}' not found")

        current_status = offer_row["offer_status"]
        if current_status in ("Accepted", "Expired"):
            raise ValueError(f"Cannot modify an offer with status '{current_status}'")

        if offer_status == "Declined":
            decline_reason = kwargs.get("decline_reason")
            if not decline_reason:
                raise ValueError("decline_reason is required when declining an offer")

        updates: dict = {}
        if offer_status is not None:
            updates["offer_status"] = offer_status
        if base_salary is not None:
            updates["base_salary"] = base_salary
        if sign_on_bonus is not None:
            updates["sign_on_bonus"] = sign_on_bonus
        if start_date is not None:
            updates["start_date"] = start_date

        today = datetime.date.today().isoformat()

        if offer_status == "Accepted":
            updates["accepted_date"] = today
        elif offer_status == "Declined":
            updates["declined_date"] = today
            updates["decline_reason"] = kwargs.get("decline_reason")

        if updates:
            set_clauses = ", ".join(f"{k} = ?" for k in updates) + ", last_modified_on = ?"
            values = list(updates.values()) + [_now(), offer_id]
            conn.execute(f"UPDATE rcm_offer SET {set_clauses} WHERE offer_id = ?", values)

        if offer_status == "Accepted":
            app_row = conn.execute(
                "SELECT * FROM rcm_application WHERE application_id = ?",
                (offer_row["application_id"],),
            ).fetchone()
            conn.execute(
                "UPDATE rcm_application SET application_status = 'Hired', offer_accepted_date = ? WHERE application_id = ?",
                (today, offer_row["application_id"]),
            )
            conn.execute(
                "UPDATE rcm_candidate SET candidate_status = 'Hired' WHERE candidate_id = ?",
                (app_row["candidate_id"],),
            )
            req_row = conn.execute(
                "SELECT * FROM rcm_job_requisition WHERE req_id = ?", (app_row["req_id"],)
            ).fetchone()
            accepted_count = conn.execute(
                """
                SELECT COUNT(*) FROM rcm_offer o
                JOIN rcm_application a ON o.application_id = a.application_id
                WHERE a.req_id = ? AND o.offer_status = 'Accepted'
                """,
                (app_row["req_id"],),
            ).fetchone()[0]
            if accepted_count >= req_row["number_of_openings"]:
                conn.execute(
                    "UPDATE rcm_job_requisition SET req_status = 'Filled' WHERE req_id = ?",
                    (app_row["req_id"],),
                )

        row = conn.execute("SELECT * FROM rcm_offer WHERE offer_id = ?", (offer_id,)).fetchone()
    return _row_to_offer(row)
