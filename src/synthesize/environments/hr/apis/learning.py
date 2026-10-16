import datetime
import uuid
from typing import List, Optional

from synthesize.environments.hr.db.db import get_conn
from synthesize.environments.hr.db.models import (
    Certification,
    Course,
    LearningAssignment,
    LearningCompletion,
)


def _today() -> datetime.date:
    return datetime.date.today()


def _today_iso() -> str:
    return datetime.date.today().isoformat()


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(sep=" ", timespec="seconds")


def _row_to_course(row) -> Course:
    return Course(
        course_id=row["course_id"],
        course_code=row["course_code"],
        course_title=row["course_title"],
        course_type=row["course_type"],
        provider=row["provider"],
        duration_hours=row["duration_hours"],
        is_mandatory=bool(row["is_mandatory"]),
        course_status=row["course_status"],
    )


def _row_to_assignment(row) -> LearningAssignment:
    return LearningAssignment(
        assignment_id=row["assignment_id"],
        person_id=row["person_id"],
        course_id=row["course_id"],
        assigned_date=row["assigned_date"],
        due_date=row["due_date"],
        assignment_type=row["assignment_type"],
    )


def _row_to_completion(row) -> LearningCompletion:
    return LearningCompletion(
        completion_id=row["completion_id"],
        person_id=row["person_id"],
        course_id=row["course_id"],
        completion_date=row["completion_date"],
        expiration_date=row["expiration_date"],
        completion_status=row["completion_status"],
        score=row["score"],
        pass_fail=row["pass_fail"],
    )


def _row_to_certification(row) -> Certification:
    return Certification(
        certification_id=row["certification_id"],
        person_id=row["person_id"],
        certification_name=row["certification_name"],
        issuing_organization=row["issuing_organization"],
        issue_date=row["issue_date"],
        expiration_date=row["expiration_date"],
        status=row["status"],
    )


# ── Courses ───────────────────────────────────────────────────────────────────


def list_courses(
    course_type: Optional[str] = None, is_mandatory: Optional[bool] = None, status: str = "Active"
) -> List[Course]:
    query = "SELECT * FROM lrn_course WHERE 1=1"
    params = []
    if status is not None:
        query += " AND course_status = ?"
        params.append(status)
    if course_type is not None:
        query += " AND course_type = ?"
        params.append(course_type)
    if is_mandatory is not None:
        query += " AND is_mandatory = ?"
        params.append(1 if is_mandatory else 0)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_course(r) for r in rows]


def get_course(course_id: str) -> Course:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM lrn_course WHERE course_id = ?", (course_id,)).fetchone()
    if not row:
        raise LookupError(f"Course not found: {course_id}")
    return _row_to_course(row)


def create_course(
    course_code: str,
    course_title: str,
    course_type: str,
    provider: Optional[str] = None,
    duration_hours: Optional[float] = None,
    is_mandatory: bool = False,
    course_description: Optional[str] = None,
    expiration_period_days: Optional[int] = None,
) -> Course:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM lrn_course WHERE course_code = ?", (course_code,)
        ).fetchone()
        if existing:
            raise ValueError(f"Course code already exists: {course_code}")
        course_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO lrn_course
               (course_id, course_code, course_title, course_type, provider,
                duration_hours, is_mandatory, course_description,
                expiration_period_days, course_status, created_on)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?)""",
            (
                course_id,
                course_code,
                course_title,
                course_type,
                provider,
                duration_hours,
                1 if is_mandatory else 0,
                course_description,
                expiration_period_days,
                _now(),
            ),
        )
        row = conn.execute("SELECT * FROM lrn_course WHERE course_id = ?", (course_id,)).fetchone()
    return _row_to_course(row)


def update_course(course_id: str, **kwargs) -> Course:
    allowed = {
        "course_title",
        "course_description",
        "provider",
        "duration_hours",
        "is_mandatory",
        "course_status",
        "expiration_period_days",
    }
    invalid = set(kwargs) - allowed
    if invalid:
        raise ValueError(f"Invalid fields: {invalid}")

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM lrn_course WHERE course_id = ?", (course_id,)).fetchone()
        if not row:
            raise LookupError(f"Course not found: {course_id}")

        if kwargs.get("course_status") == "Inactive":
            today = _today_iso()
            active_assignment = conn.execute(
                """SELECT 1 FROM lrn_assignment
                   WHERE course_id = ? AND due_date >= ?""",
                (course_id, today),
            ).fetchone()
            if active_assignment:
                raise ValueError(
                    "Cannot deactivate a course that has active assignments with upcoming due dates."
                )

        if "is_mandatory" in kwargs:
            kwargs["is_mandatory"] = 1 if kwargs["is_mandatory"] else 0

        set_clause = ", ".join(f"{k} = ?" for k in kwargs) + ", last_modified_on = ?"
        values = list(kwargs.values()) + [_now(), course_id]
        conn.execute(f"UPDATE lrn_course SET {set_clause} WHERE course_id = ?", values)
        row = conn.execute("SELECT * FROM lrn_course WHERE course_id = ?", (course_id,)).fetchone()
    return _row_to_course(row)


# ── Assignments ───────────────────────────────────────────────────────────────


def list_assignments(person_id: str) -> List[LearningAssignment]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM lrn_assignment WHERE person_id = ?", (person_id,)
        ).fetchall()
    return [_row_to_assignment(r) for r in rows]


def assign_course(
    person_id: str,
    course_id: str,
    due_date: Optional[str] = None,
    assignment_type: str = "Mandatory",
    assigned_by_person_id: Optional[str] = None,
) -> LearningAssignment:
    with get_conn() as conn:
        person = conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (person_id,)
        ).fetchone()
        if not person:
            raise ValueError(f"Person not found: {person_id}")

        course = conn.execute(
            "SELECT * FROM lrn_course WHERE course_id = ?", (course_id,)
        ).fetchone()
        if not course:
            raise ValueError(f"Course not found: {course_id}")
        if course["course_status"] != "Active":
            raise ValueError(f"Course is not active: {course_id}")

        active_assignment = conn.execute(
            "SELECT 1 FROM lrn_assignment WHERE person_id = ? AND course_id = ?",
            (person_id, course_id),
        ).fetchone()
        if active_assignment:
            completed = conn.execute(
                """SELECT 1 FROM lrn_completion
                   WHERE person_id = ? AND course_id = ? AND completion_status = 'Completed'""",
                (person_id, course_id),
            ).fetchone()
            if not completed:
                raise ValueError(
                    f"Person {person_id} already has an active assignment for course {course_id}."
                )

        assignment_id = str(uuid.uuid4())
        assigned_date = _today_iso()
        conn.execute(
            """INSERT INTO lrn_assignment
               (assignment_id, person_id, course_id, assigned_date, due_date,
                assignment_type, assigned_by_person_id, created_on)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                assignment_id,
                person_id,
                course_id,
                assigned_date,
                due_date,
                assignment_type,
                assigned_by_person_id,
                _now(),
            ),
        )

        completion_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO lrn_completion
               (completion_id, person_id, course_id, enrollment_date,
                completion_status, created_on)
               VALUES (?, ?, ?, ?, 'Enrolled', ?)""",
            (completion_id, person_id, course_id, assigned_date, _now()),
        )

        row = conn.execute(
            "SELECT * FROM lrn_assignment WHERE assignment_id = ?", (assignment_id,)
        ).fetchone()
    return _row_to_assignment(row)


def update_assignment(
    assignment_id: str,
    due_date: Optional[str] = None,
    assignment_type: Optional[str] = None,
    waived: bool = False,
) -> LearningAssignment:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM lrn_assignment WHERE assignment_id = ?", (assignment_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Assignment not found: {assignment_id}")

        if waived:
            conn.execute(
                """UPDATE lrn_completion SET completion_status = 'Waived'
                   WHERE person_id = ? AND course_id = ?""",
                (row["person_id"], row["course_id"]),
            )
            conn.execute("DELETE FROM lrn_assignment WHERE assignment_id = ?", (assignment_id,))
            return LearningAssignment(
                assignment_id=assignment_id,
                person_id=row["person_id"],
                course_id=row["course_id"],
                assigned_date=row["assigned_date"],
                due_date=row["due_date"],
                assignment_type=row["assignment_type"],
            )

        updates = {}
        if due_date is not None:
            if datetime.date.fromisoformat(due_date) < _today():
                raise ValueError("due_date must be >= today.")
            updates["due_date"] = due_date
        if assignment_type is not None:
            updates["assignment_type"] = assignment_type

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [assignment_id]
            conn.execute(f"UPDATE lrn_assignment SET {set_clause} WHERE assignment_id = ?", values)

        row = conn.execute(
            "SELECT * FROM lrn_assignment WHERE assignment_id = ?", (assignment_id,)
        ).fetchone()
    return _row_to_assignment(row)


# ── Completions ───────────────────────────────────────────────────────────────


def list_completions(person_id: str, status: Optional[str] = None) -> List[LearningCompletion]:
    query = "SELECT * FROM lrn_completion WHERE person_id = ?"
    params = [person_id]
    if status is not None:
        query += " AND completion_status = ?"
        params.append(status)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_completion(r) for r in rows]


def record_completion(
    person_id: str,
    course_id: str,
    completion_date: str,
    score: Optional[float] = None,
    pass_fail: Optional[str] = None,
    certificate_url: Optional[str] = None,
) -> LearningCompletion:
    with get_conn() as conn:
        person = conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (person_id,)
        ).fetchone()
        if not person:
            raise ValueError(f"Person not found: {person_id}")

        course = conn.execute(
            "SELECT * FROM lrn_course WHERE course_id = ?", (course_id,)
        ).fetchone()
        if not course:
            raise ValueError(f"Course not found: {course_id}")

        if datetime.date.fromisoformat(completion_date) > _today():
            raise ValueError("completion_date cannot be in the future.")

        expiration_date = None
        if course["expiration_period_days"]:
            expiry = datetime.date.fromisoformat(completion_date) + datetime.timedelta(
                days=course["expiration_period_days"]
            )
            expiration_date = expiry.isoformat()

        if score is not None and pass_fail is None:
            pass_fail = "Pass" if score >= 70 else "Fail"

        existing = conn.execute(
            "SELECT completion_id FROM lrn_completion WHERE person_id = ? AND course_id = ?",
            (person_id, course_id),
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE lrn_completion
                   SET completion_date = ?, expiration_date = ?,
                       completion_status = 'Completed', score = ?,
                       pass_fail = ?, certificate_url = ?,
                       last_modified_on = CURRENT_TIMESTAMP
                   WHERE person_id = ? AND course_id = ?""",
                (
                    completion_date,
                    expiration_date,
                    score,
                    pass_fail,
                    certificate_url,
                    person_id,
                    course_id,
                ),
            )
            completion_id = existing["completion_id"]
        else:
            completion_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO lrn_completion
                   (completion_id, person_id, course_id, completion_date,
                    expiration_date, completion_status, score, pass_fail,
                    certificate_url)
                   VALUES (?, ?, ?, ?, ?, 'Completed', ?, ?, ?)""",
                (
                    completion_id,
                    person_id,
                    course_id,
                    completion_date,
                    expiration_date,
                    score,
                    pass_fail,
                    certificate_url,
                ),
            )

        conn.execute(
            "DELETE FROM lrn_assignment WHERE person_id = ? AND course_id = ?",
            (person_id, course_id),
        )

        row = conn.execute(
            "SELECT * FROM lrn_completion WHERE completion_id = ?", (completion_id,)
        ).fetchone()
    return _row_to_completion(row)


# ── Certifications ────────────────────────────────────────────────────────────


def list_certifications(person_id: str, status: Optional[str] = None) -> List[Certification]:
    query = "SELECT * FROM lrn_certification WHERE person_id = ?"
    params = [person_id]
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_certification(r) for r in rows]


def add_certification(
    person_id: str,
    certification_name: str,
    issuing_organization: Optional[str] = None,
    issue_date: Optional[str] = None,
    expiration_date: Optional[str] = None,
    certification_number: Optional[str] = None,
    verification_url: Optional[str] = None,
) -> Certification:
    with get_conn() as conn:
        person = conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (person_id,)
        ).fetchone()
        if not person:
            raise ValueError(f"Person not found: {person_id}")

        if issue_date and datetime.date.fromisoformat(issue_date) > _today():
            raise ValueError("issue_date must not be in the future.")

        if expiration_date and issue_date:
            if datetime.date.fromisoformat(expiration_date) <= datetime.date.fromisoformat(
                issue_date
            ):
                raise ValueError("expiration_date must be after issue_date.")

        if expiration_date:
            status = (
                "Active" if datetime.date.fromisoformat(expiration_date) > _today() else "Expired"
            )
        else:
            status = "Active"

        certification_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO lrn_certification
               (certification_id, person_id, certification_name,
                issuing_organization, issue_date, expiration_date,
                certification_number, status, verification_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                certification_id,
                person_id,
                certification_name,
                issuing_organization,
                issue_date,
                expiration_date,
                certification_number,
                status,
                verification_url,
            ),
        )
        row = conn.execute(
            "SELECT * FROM lrn_certification WHERE certification_id = ?",
            (certification_id,),
        ).fetchone()
    return _row_to_certification(row)


def renew_certification(
    certification_id: str, new_expiration_date: str, issue_date: Optional[str] = None
) -> Certification:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM lrn_certification WHERE certification_id = ?",
            (certification_id,),
        ).fetchone()
        if not row:
            raise LookupError(f"Certification not found: {certification_id}")

        if row["expiration_date"]:
            if datetime.date.fromisoformat(new_expiration_date) <= datetime.date.fromisoformat(
                row["expiration_date"]
            ):
                raise ValueError("new_expiration_date must be after the current expiration_date.")

        updates = {"expiration_date": new_expiration_date, "status": "Active"}
        if issue_date is not None:
            updates["issue_date"] = issue_date

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [certification_id]
        conn.execute(
            f"UPDATE lrn_certification SET {set_clause} WHERE certification_id = ?", values
        )
        row = conn.execute(
            "SELECT * FROM lrn_certification WHERE certification_id = ?",
            (certification_id,),
        ).fetchone()
    return _row_to_certification(row)


def revoke_certification(certification_id: str) -> Certification:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM lrn_certification WHERE certification_id = ?",
            (certification_id,),
        ).fetchone()
        if not row:
            raise LookupError(f"Certification not found: {certification_id}")
        conn.execute(
            "UPDATE lrn_certification SET status = 'Revoked' WHERE certification_id = ?",
            (certification_id,),
        )
        row = conn.execute(
            "SELECT * FROM lrn_certification WHERE certification_id = ?",
            (certification_id,),
        ).fetchone()
    return _row_to_certification(row)
