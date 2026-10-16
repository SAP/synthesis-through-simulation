import datetime
import uuid
from typing import List, Optional

from synthesize.environments.hr.db.db import get_conn
from synthesize.environments.hr.db.models import (
    CareerPath,
    DevelopmentActivity,
    DevelopmentPlan,
    EmployeeSkill,
    Language,
    MentoringRelationship,
)

_PROFICIENCY_ORDER = ["Beginner", "Intermediate", "Advanced", "Expert"]


def _today() -> datetime.date:
    return datetime.date.today()


def _today_iso() -> str:
    return datetime.date.today().isoformat()


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(sep=" ", timespec="seconds")


def _row_to_career_path(row) -> CareerPath:
    return CareerPath(
        path_id=row["path_id"],
        path_name=row["path_name"],
        from_job_code=row["from_job_code"],
        to_job_code=row["to_job_code"],
        typical_years=row["typical_years"],
        required_competencies=row["required_competencies"],
    )


def _row_to_development_plan(row) -> DevelopmentPlan:
    return DevelopmentPlan(
        plan_id=row["plan_id"],
        person_id=row["person_id"],
        plan_name=row["plan_name"],
        target_role=row["target_role"],
        target_date=row["target_date"],
        plan_status=row["plan_status"],
        created_date=row["created_date"],
    )


def _row_to_activity(row) -> DevelopmentActivity:
    return DevelopmentActivity(
        activity_id=row["activity_id"],
        plan_id=row["plan_id"],
        activity_name=row["activity_name"],
        activity_type=row["activity_type"],
        target_completion_date=row["target_completion_date"],
        actual_completion_date=row["actual_completion_date"],
        activity_status=row["activity_status"],
    )


def _row_to_mentoring(row) -> MentoringRelationship:
    return MentoringRelationship(
        mentoring_id=row["mentoring_id"],
        mentee_person_id=row["mentee_person_id"],
        mentor_person_id=row["mentor_person_id"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        mentoring_status=row["mentoring_status"],
        focus_areas=row["focus_areas"],
    )


def _row_to_skill(row) -> EmployeeSkill:
    return EmployeeSkill(
        employee_skill_id=row["employee_skill_id"],
        person_id=row["person_id"],
        skill_id=row["skill_id"],
        proficiency_level=row["proficiency_level"],
        proficiency_rating=row["proficiency_rating"],
        years_of_experience=row["years_of_experience"],
        is_primary_skill=bool(row["is_primary_skill"]),
    )


def _row_to_language(row) -> Language:
    return Language(
        language_id=row["language_id"],
        person_id=row["person_id"],
        language_code=row["language_code"],
        language_name=row["language_name"],
        proficiency_level=row["proficiency_level"],
    )


# ── Career Paths ──────────────────────────────────────────────────────────────


def list_career_paths(
    from_job_code: Optional[str] = None, to_job_code: Optional[str] = None
) -> List[CareerPath]:
    query = "SELECT * FROM car_career_path WHERE 1=1"
    params = []
    if from_job_code is not None:
        query += " AND from_job_code = ?"
        params.append(from_job_code)
    if to_job_code is not None:
        query += " AND to_job_code = ?"
        params.append(to_job_code)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_career_path(r) for r in rows]


def get_career_path(path_id: str) -> CareerPath:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM car_career_path WHERE path_id = ?", (path_id,)).fetchone()
    if not row:
        raise LookupError(f"Career path not found: {path_id}")
    return _row_to_career_path(row)


def create_career_path(
    path_name: str,
    from_job_code: str,
    to_job_code: str,
    typical_years: Optional[int] = None,
    required_competencies: Optional[str] = None,
) -> CareerPath:
    if from_job_code == to_job_code:
        raise ValueError("from_job_code and to_job_code must be different.")
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM fod_job_code WHERE job_code = ?", (from_job_code,)
        ).fetchone():
            raise ValueError(f"Job code not found: {from_job_code}")
        if not conn.execute(
            "SELECT 1 FROM fod_job_code WHERE job_code = ?", (to_job_code,)
        ).fetchone():
            raise ValueError(f"Job code not found: {to_job_code}")
        if conn.execute(
            """SELECT 1 FROM car_career_path
               WHERE from_job_code = ? AND to_job_code = ?""",
            (from_job_code, to_job_code),
        ).fetchone():
            raise ValueError(f"A career path from {from_job_code} to {to_job_code} already exists.")
        path_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO car_career_path
               (path_id, path_name, from_job_code, to_job_code,
                typical_years, required_competencies, created_on)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                path_id,
                path_name,
                from_job_code,
                to_job_code,
                typical_years,
                required_competencies,
                _now(),
            ),
        )
        row = conn.execute("SELECT * FROM car_career_path WHERE path_id = ?", (path_id,)).fetchone()
    return _row_to_career_path(row)


# ── Development Plans ─────────────────────────────────────────────────────────


def list_development_plans(person_id: str, status: Optional[str] = None) -> List[DevelopmentPlan]:
    query = "SELECT * FROM car_development_plan WHERE person_id = ?"
    params = [person_id]
    if status is not None:
        query += " AND plan_status = ?"
        params.append(status)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_development_plan(r) for r in rows]


def get_development_plan(plan_id: str) -> DevelopmentPlan:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM car_development_plan WHERE plan_id = ?", (plan_id,)
        ).fetchone()
    if not row:
        raise LookupError(f"Development plan not found: {plan_id}")
    return _row_to_development_plan(row)


def create_development_plan(
    person_id: str,
    plan_name: str,
    target_role: Optional[str] = None,
    target_date: Optional[str] = None,
    created_date: Optional[str] = None,
) -> DevelopmentPlan:
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (person_id,)
        ).fetchone():
            raise ValueError(f"Person not found: {person_id}")

        if target_date and datetime.date.fromisoformat(target_date) <= _today():
            raise ValueError("target_date must be in the future.")

        if conn.execute(
            """SELECT 1 FROM car_development_plan
               WHERE person_id = ? AND plan_name = ? AND plan_status = 'Active'""",
            (person_id, plan_name),
        ).fetchone():
            raise ValueError(f"Person {person_id} already has an Active plan named '{plan_name}'.")

        plan_id = str(uuid.uuid4())
        effective_created_date = created_date or _today_iso()
        conn.execute(
            """INSERT INTO car_development_plan
               (plan_id, person_id, plan_name, target_role, target_date,
                plan_status, created_date)
               VALUES (?, ?, ?, ?, ?, 'Active', ?)""",
            (plan_id, person_id, plan_name, target_role, target_date, effective_created_date),
        )
        row = conn.execute(
            "SELECT * FROM car_development_plan WHERE plan_id = ?", (plan_id,)
        ).fetchone()
    return _row_to_development_plan(row)


def update_development_plan(
    plan_id: str,
    plan_name: Optional[str] = None,
    target_role: Optional[str] = None,
    target_date: Optional[str] = None,
    plan_status: Optional[str] = None,
) -> DevelopmentPlan:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM car_development_plan WHERE plan_id = ?", (plan_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Development plan not found: {plan_id}")

        if plan_status is not None:
            if row["plan_status"] == "Cancelled":
                raise ValueError("Cannot reactivate a Cancelled development plan.")
            if plan_status == "Completed":
                incomplete = conn.execute(
                    """SELECT activity_name FROM car_development_activity
                       WHERE plan_id = ? AND activity_status != 'Completed'""",
                    (plan_id,),
                ).fetchall()
                if incomplete:
                    names = ", ".join(r["activity_name"] for r in incomplete)
                    raise ValueError(
                        f"Cannot complete plan: the following activities are not completed: {names}"
                    )

        updates = {}
        if plan_name is not None:
            updates["plan_name"] = plan_name
        if target_role is not None:
            updates["target_role"] = target_role
        if target_date is not None:
            updates["target_date"] = target_date
        if plan_status is not None:
            updates["plan_status"] = plan_status

        if updates:
            updates["last_modified_on"] = _today_iso()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [plan_id]
            conn.execute(f"UPDATE car_development_plan SET {set_clause} WHERE plan_id = ?", values)

        row = conn.execute(
            "SELECT * FROM car_development_plan WHERE plan_id = ?", (plan_id,)
        ).fetchone()
    return _row_to_development_plan(row)


def add_activity(
    plan_id: str,
    activity_name: str,
    activity_type: str,
    target_completion_date: str,
    activity_description: Optional[str] = None,
) -> DevelopmentActivity:
    with get_conn() as conn:
        plan = conn.execute(
            "SELECT * FROM car_development_plan WHERE plan_id = ?", (plan_id,)
        ).fetchone()
        if not plan:
            raise LookupError(f"Development plan not found: {plan_id}")
        if plan["plan_status"] != "Active":
            raise ValueError(f"Development plan {plan_id} is not Active.")

        if datetime.date.fromisoformat(target_completion_date) <= _today():
            raise ValueError("target_completion_date must be in the future.")

        if plan["target_date"]:
            if datetime.date.fromisoformat(target_completion_date) > datetime.date.fromisoformat(
                plan["target_date"]
            ):
                raise ValueError(
                    "Activity target_completion_date cannot exceed the plan's target_date."
                )

        conn.execute(
            """INSERT INTO car_development_activity
               (plan_id, activity_name, activity_type, activity_description,
                target_completion_date, activity_status, created_on)
               VALUES (?, ?, ?, ?, ?, 'Not Started', ?)""",
            (
                plan_id,
                activity_name,
                activity_type,
                activity_description,
                target_completion_date,
                _now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM car_development_activity WHERE plan_id = ? ORDER BY activity_id DESC LIMIT 1",
            (plan_id,),
        ).fetchone()
    return _row_to_activity(row)


def update_activity(
    activity_id: int,
    activity_status: Optional[str] = None,
    actual_completion_date: Optional[str] = None,
    target_completion_date: Optional[str] = None,
) -> DevelopmentActivity:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM car_development_activity WHERE activity_id = ?", (activity_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Activity not found: {activity_id}")

        if activity_status is not None:
            if row["activity_status"] == "Completed" and activity_status == "In Progress":
                raise ValueError("Cannot set status back from Completed to In Progress.")

        updates = {}
        if target_completion_date is not None:
            updates["target_completion_date"] = target_completion_date
        if activity_status is not None:
            updates["activity_status"] = activity_status
            if activity_status == "Completed":
                updates["actual_completion_date"] = (
                    actual_completion_date if actual_completion_date else _today_iso()
                )
        elif actual_completion_date is not None:
            updates["actual_completion_date"] = actual_completion_date

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [activity_id]
            conn.execute(
                f"UPDATE car_development_activity SET {set_clause} WHERE activity_id = ?",
                values,
            )

        row = conn.execute(
            "SELECT * FROM car_development_activity WHERE activity_id = ?", (activity_id,)
        ).fetchone()
    return _row_to_activity(row)


# ── Mentoring ─────────────────────────────────────────────────────────────────


def list_mentoring(person_id: str, role: Optional[str] = None) -> List[MentoringRelationship]:
    if role == "mentor":
        query = "SELECT * FROM car_mentoring WHERE mentor_person_id = ?"
        params = [person_id]
    elif role == "mentee":
        query = "SELECT * FROM car_mentoring WHERE mentee_person_id = ?"
        params = [person_id]
    else:
        query = "SELECT * FROM car_mentoring WHERE mentee_person_id = ? OR mentor_person_id = ?"
        params = [person_id, person_id]
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_mentoring(r) for r in rows]


def create_mentoring(
    mentee_person_id: str, mentor_person_id: str, start_date: str, focus_areas: Optional[str] = None
) -> MentoringRelationship:
    if mentee_person_id == mentor_person_id:
        raise ValueError("mentor and mentee must be different people.")
    with get_conn() as conn:
        for pid, label in [(mentee_person_id, "Mentee"), (mentor_person_id, "Mentor")]:
            if not conn.execute("SELECT 1 FROM per_person WHERE person_id = ?", (pid,)).fetchone():
                raise ValueError(f"{label} person not found: {pid}")

        if conn.execute(
            """SELECT 1 FROM car_mentoring
               WHERE mentee_person_id = ? AND mentor_person_id = ?
               AND mentoring_status = 'Active'""",
            (mentee_person_id, mentor_person_id),
        ).fetchone():
            raise ValueError(
                f"An active mentoring relationship already exists between "
                f"{mentee_person_id} and {mentor_person_id}."
            )

        active_count = conn.execute(
            """SELECT COUNT(*) FROM car_mentoring
               WHERE mentee_person_id = ? AND mentoring_status = 'Active'""",
            (mentee_person_id,),
        ).fetchone()[0]
        if active_count >= 2:
            raise ValueError(
                f"Mentee {mentee_person_id} already has {active_count} active "
                "mentoring relationships (cap is 2)."
            )

        mentoring_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO car_mentoring
               (mentoring_id, mentee_person_id, mentor_person_id, start_date,
                mentoring_status, focus_areas, created_on)
               VALUES (?, ?, ?, ?, 'Active', ?, ?)""",
            (mentoring_id, mentee_person_id, mentor_person_id, start_date, focus_areas, _now()),
        )
        row = conn.execute(
            "SELECT * FROM car_mentoring WHERE mentoring_id = ?", (mentoring_id,)
        ).fetchone()
    return _row_to_mentoring(row)


def update_mentoring(
    mentoring_id: str,
    mentoring_status: Optional[str] = None,
    end_date: Optional[str] = None,
    focus_areas: Optional[str] = None,
) -> MentoringRelationship:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM car_mentoring WHERE mentoring_id = ?", (mentoring_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Mentoring relationship not found: {mentoring_id}")

        updates = {}
        if focus_areas is not None:
            updates["focus_areas"] = focus_areas
        if mentoring_status is not None:
            updates["mentoring_status"] = mentoring_status
            if mentoring_status in ("Completed", "Inactive"):
                updates["end_date"] = end_date if end_date else _today_iso()
        elif end_date is not None:
            updates["end_date"] = end_date

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [mentoring_id]
            conn.execute(f"UPDATE car_mentoring SET {set_clause} WHERE mentoring_id = ?", values)

        row = conn.execute(
            "SELECT * FROM car_mentoring WHERE mentoring_id = ?", (mentoring_id,)
        ).fetchone()
    return _row_to_mentoring(row)


# ── Skills ────────────────────────────────────────────────────────────────────


def list_skills(person_id: str) -> List[EmployeeSkill]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tp_employee_skill WHERE person_id = ?", (person_id,)
        ).fetchall()
    return [_row_to_skill(r) for r in rows]


def add_skill(
    person_id: str,
    skill_id: str,
    proficiency_level: str,
    proficiency_rating: Optional[int] = None,
    years_of_experience: Optional[float] = None,
    is_primary_skill: bool = False,
) -> EmployeeSkill:
    if proficiency_level not in _PROFICIENCY_ORDER:
        raise ValueError(f"proficiency_level must be one of: {', '.join(_PROFICIENCY_ORDER)}")
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (person_id,)
        ).fetchone():
            raise ValueError(f"Person not found: {person_id}")
        if not conn.execute("SELECT 1 FROM tp_skill WHERE skill_id = ?", (skill_id,)).fetchone():
            raise LookupError(f"Skill not found: {skill_id}")
        if conn.execute(
            "SELECT 1 FROM tp_employee_skill WHERE person_id = ? AND skill_id = ?",
            (person_id, skill_id),
        ).fetchone():
            raise ValueError(
                f"Person {person_id} already has skill {skill_id}. Use update_skill instead."
            )
        conn.execute(
            """INSERT INTO tp_employee_skill
               (person_id, skill_id, proficiency_level, proficiency_rating,
                years_of_experience, is_primary_skill, created_on)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                person_id,
                skill_id,
                proficiency_level,
                proficiency_rating,
                years_of_experience,
                1 if is_primary_skill else 0,
                _now(),
            ),
        )
        row = conn.execute(
            """SELECT * FROM tp_employee_skill
               WHERE person_id = ? AND skill_id = ?""",
            (person_id, skill_id),
        ).fetchone()
    return _row_to_skill(row)


def update_skill(
    employee_skill_id: int,
    proficiency_level: Optional[str] = None,
    proficiency_rating: Optional[int] = None,
    years_of_experience: Optional[float] = None,
    is_primary_skill: Optional[bool] = None,
) -> EmployeeSkill:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tp_employee_skill WHERE employee_skill_id = ?",
            (employee_skill_id,),
        ).fetchone()
        if not row:
            raise LookupError(f"Employee skill not found: {employee_skill_id}")

        if proficiency_level is not None:
            if proficiency_level not in _PROFICIENCY_ORDER:
                raise ValueError(
                    f"proficiency_level must be one of: {', '.join(_PROFICIENCY_ORDER)}"
                )
            current = row["proficiency_level"]
            if current and current in _PROFICIENCY_ORDER:
                current_idx = _PROFICIENCY_ORDER.index(current)
                new_idx = _PROFICIENCY_ORDER.index(proficiency_level)
                if new_idx < current_idx:
                    raise ValueError(
                        f"Cannot lower proficiency level from {current} to {proficiency_level}."
                    )

        updates = {}
        if proficiency_level is not None:
            updates["proficiency_level"] = proficiency_level
        if proficiency_rating is not None:
            updates["proficiency_rating"] = proficiency_rating
        if years_of_experience is not None:
            updates["years_of_experience"] = years_of_experience
        if is_primary_skill is not None:
            updates["is_primary_skill"] = 1 if is_primary_skill else 0

        if updates:
            updates["last_modified_on"] = _today_iso()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [employee_skill_id]
            conn.execute(
                f"UPDATE tp_employee_skill SET {set_clause} WHERE employee_skill_id = ?",
                values,
            )

        row = conn.execute(
            "SELECT * FROM tp_employee_skill WHERE employee_skill_id = ?",
            (employee_skill_id,),
        ).fetchone()
    return _row_to_skill(row)


# ── Languages ─────────────────────────────────────────────────────────────────


def list_languages(person_id: str) -> List[Language]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tp_language WHERE person_id = ?", (person_id,)
        ).fetchall()
    return [_row_to_language(r) for r in rows]


def add_language(
    person_id: str,
    language_code: str,
    language_name: Optional[str] = None,
    proficiency_level: Optional[str] = None,
    reading_proficiency: Optional[str] = None,
    writing_proficiency: Optional[str] = None,
    speaking_proficiency: Optional[str] = None,
) -> Language:
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (person_id,)
        ).fetchone():
            raise ValueError(f"Person not found: {person_id}")
        if conn.execute(
            "SELECT 1 FROM tp_language WHERE person_id = ? AND language_code = ?",
            (person_id, language_code),
        ).fetchone():
            raise ValueError(f"Person {person_id} already has language {language_code}.")
        conn.execute(
            """INSERT INTO tp_language
               (person_id, language_code, language_name, proficiency_level,
                reading_proficiency, writing_proficiency, speaking_proficiency,
                created_on)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                person_id,
                language_code,
                language_name,
                proficiency_level,
                reading_proficiency,
                writing_proficiency,
                speaking_proficiency,
                _now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM tp_language WHERE person_id = ? AND language_code = ?",
            (person_id, language_code),
        ).fetchone()
    return _row_to_language(row)


def update_language(language_id: int, **kwargs) -> Language:
    allowed = {
        "proficiency_level",
        "reading_proficiency",
        "writing_proficiency",
        "speaking_proficiency",
    }
    invalid = set(kwargs) - allowed
    if invalid:
        raise ValueError(f"Invalid fields: {invalid}")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tp_language WHERE language_id = ?", (language_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Language record not found: {language_id}")

        if kwargs:
            set_clause = ", ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values()) + [language_id]
            conn.execute(f"UPDATE tp_language SET {set_clause} WHERE language_id = ?", values)

        row = conn.execute(
            "SELECT * FROM tp_language WHERE language_id = ?", (language_id,)
        ).fetchone()
    return _row_to_language(row)
