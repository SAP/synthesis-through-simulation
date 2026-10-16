import datetime
import uuid
from typing import List, Optional

from synthesize.environments.hr.db.db import get_conn
from synthesize.environments.hr.db.models import BenefitEnrollment, BenefitPlan, EnrolledDependent


def TODAY():
    return datetime.date.today().isoformat()


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(sep=" ", timespec="seconds")


VALID_PLAN_TYPES = {"Medical", "Dental", "Vision", "Life", "401k", "FSA", "HSA"}
VALID_COVERAGE_LEVELS = {
    "Employee Only",
    "Employee + Spouse",
    "Employee + Children",
    "Family",
}
VALID_POTENTIAL_RATINGS = {"High", "Medium", "Low"}
SPOUSE_RELATIONSHIPS = {"Spouse", "Domestic Partner"}


# ── Internal helpers ──────────────────────────────────────────────────────────


def _row_to_plan(row) -> BenefitPlan:
    return BenefitPlan(
        plan_id=row["plan_id"],
        plan_name=row["plan_name"],
        plan_type=row["plan_type"],
        plan_category=row["plan_category"],
        provider=row["provider"],
        plan_year=row["plan_year"],
        employee_cost_monthly=row["employee_cost_monthly"],
        employer_cost_monthly=row["employer_cost_monthly"],
        plan_status=row["plan_status"],
    )


def _row_to_enrollment(row) -> BenefitEnrollment:
    return BenefitEnrollment(
        enrollment_id=row["enrollment_id"],
        person_id=row["person_id"],
        plan_id=row["plan_id"],
        enrollment_date=row["enrollment_date"],
        effective_start_date=row["effective_start_date"],
        effective_end_date=row["effective_end_date"],
        coverage_level=row["coverage_level"],
        enrollment_status=row["enrollment_status"],
        employee_cost_monthly=row["employee_cost_monthly"],
        employer_cost_monthly=row["employer_cost_monthly"],
    )


def _row_to_enrolled_dependent(row) -> EnrolledDependent:
    return EnrolledDependent(
        enrolled_dependent_id=row["enrolled_dependent_id"],
        enrollment_id=row["enrollment_id"],
        dependent_id=row["dependent_id"],
        coverage_start_date=row["coverage_start_date"],
        coverage_end_date=row["coverage_end_date"],
    )


def _validate_dependents(
    conn, person_id: str, coverage_level: str, dependent_ids: Optional[List[int]]
):
    if coverage_level == "Employee Only":
        return

    if not dependent_ids:
        raise ValueError(
            f"coverage_level '{coverage_level}' requires dependent_ids to be provided and non-empty."
        )

    for dep_id in dependent_ids:
        dep = conn.execute(
            "SELECT dependent_id, relationship FROM per_dependent WHERE dependent_id=? AND person_id=?",
            (dep_id, person_id),
        ).fetchone()
        if not dep:
            raise ValueError(
                f"Dependent '{dep_id}' does not exist or does not belong to person '{person_id}'."
            )

    if coverage_level == "Employee + Spouse":
        spouse_count = 0
        for dep_id in dependent_ids:
            dep = conn.execute(
                "SELECT relationship FROM per_dependent WHERE dependent_id=?", (dep_id,)
            ).fetchone()
            if dep and dep["relationship"] in SPOUSE_RELATIONSHIPS:
                spouse_count += 1
        if spouse_count != 1:
            raise ValueError(
                f"coverage_level 'Employee + Spouse' requires exactly one Spouse or Domestic Partner "
                f"in dependent_ids (found {spouse_count})."
            )


# ── Benefit Plans ─────────────────────────────────────────────────────────────


def list_benefit_plans(
    plan_type: Optional[str] = None,
    plan_year: Optional[int] = None,
    status: str = "Active",
) -> List[BenefitPlan]:
    with get_conn() as conn:
        query = "SELECT * FROM ben_benefit_plan WHERE 1=1"
        params = []
        if status:
            query += " AND plan_status=?"
            params.append(status)
        if plan_type:
            query += " AND plan_type=?"
            params.append(plan_type)
        if plan_year:
            query += " AND plan_year=?"
            params.append(plan_year)
        rows = conn.execute(query, params).fetchall()
        return [_row_to_plan(r) for r in rows]


def get_benefit_plan(plan_id: str) -> BenefitPlan:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM ben_benefit_plan WHERE plan_id=?", (plan_id,)).fetchone()
        if not row:
            raise LookupError(f"Benefit plan '{plan_id}' not found.")
        return _row_to_plan(row)


def create_benefit_plan(
    plan_name: str,
    plan_type: str,
    plan_category: str,
    provider: Optional[str] = None,
    plan_year: Optional[int] = None,
    employee_cost_monthly: Optional[float] = None,
    employer_cost_monthly: Optional[float] = None,
) -> BenefitPlan:
    with get_conn() as conn:
        if plan_type not in VALID_PLAN_TYPES:
            raise ValueError(
                f"Invalid plan_type '{plan_type}'. Must be one of: {sorted(VALID_PLAN_TYPES)}."
            )

        existing = conn.execute(
            "SELECT plan_id FROM ben_benefit_plan WHERE plan_name=? AND (plan_year=? OR (plan_year IS NULL AND ? IS NULL))",
            (plan_name, plan_year, plan_year),
        ).fetchone()
        if existing:
            raise ValueError(
                f"A benefit plan with name '{plan_name}' and year '{plan_year}' already exists."
            )

        plan_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO ben_benefit_plan
              (plan_id, plan_name, plan_type, plan_category, provider, plan_year,
               employee_cost_monthly, employer_cost_monthly, plan_status, created_on)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                plan_id,
                plan_name,
                plan_type,
                plan_category,
                provider,
                plan_year,
                employee_cost_monthly,
                employer_cost_monthly,
                "Active",
                _now(),
            ),
        )
        row = conn.execute("SELECT * FROM ben_benefit_plan WHERE plan_id=?", (plan_id,)).fetchone()
        return _row_to_plan(row)


def update_benefit_plan(plan_id: str, **kwargs) -> BenefitPlan:
    allowed = {
        "plan_name",
        "provider",
        "employee_cost_monthly",
        "employer_cost_monthly",
        "plan_status",
    }
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM ben_benefit_plan WHERE plan_id=?", (plan_id,)).fetchone()
        if not row:
            raise LookupError(f"Benefit plan '{plan_id}' not found.")

        if kwargs.get("plan_status") == "Inactive" or kwargs.get("plan_status") == "Terminated":
            active_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM ben_enrollment WHERE plan_id=? AND enrollment_status='Active'",
                (plan_id,),
            ).fetchone()["cnt"]
            if active_count > 0:
                raise ValueError(
                    f"Cannot deactivate plan '{plan_id}': it has {active_count} active enrollment(s)."
                )

        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates) + ", last_modified_on=?"
            conn.execute(
                f"UPDATE ben_benefit_plan SET {set_clause} WHERE plan_id=?",
                list(updates.values()) + [_now(), plan_id],
            )

        row = conn.execute("SELECT * FROM ben_benefit_plan WHERE plan_id=?", (plan_id,)).fetchone()
        return _row_to_plan(row)


# ── Enrollments ───────────────────────────────────────────────────────────────


def list_enrollments(person_id: str, status: Optional[str] = None) -> List[BenefitEnrollment]:
    with get_conn() as conn:
        query = "SELECT * FROM ben_enrollment WHERE person_id=?"
        params = [person_id]
        if status:
            query += " AND enrollment_status=?"
            params.append(status)
        rows = conn.execute(query, params).fetchall()
        return [_row_to_enrollment(r) for r in rows]


def get_enrollment(enrollment_id: str) -> BenefitEnrollment:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM ben_enrollment WHERE enrollment_id=?", (enrollment_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Enrollment '{enrollment_id}' not found.")
        return _row_to_enrollment(row)


def enroll(
    person_id: str,
    plan_id: str,
    coverage_level: str,
    effective_start_date: str,
    dependent_ids: Optional[List[int]] = None,
) -> BenefitEnrollment:
    with get_conn() as conn:
        person = conn.execute(
            "SELECT person_id FROM per_person WHERE person_id=?", (person_id,)
        ).fetchone()
        if not person:
            raise ValueError(f"Person '{person_id}' does not exist.")

        plan = conn.execute("SELECT * FROM ben_benefit_plan WHERE plan_id=?", (plan_id,)).fetchone()
        if not plan:
            raise LookupError(f"Benefit plan '{plan_id}' not found.")
        if plan["plan_status"] != "Active":
            raise ValueError(f"Benefit plan '{plan_id}' is not Active.")

        if coverage_level not in VALID_COVERAGE_LEVELS:
            raise ValueError(
                f"Invalid coverage_level '{coverage_level}'. Must be one of: {sorted(VALID_COVERAGE_LEVELS)}."
            )

        existing = conn.execute(
            "SELECT enrollment_id FROM ben_enrollment WHERE person_id=? AND plan_id=? AND enrollment_status='Active'",
            (person_id, plan_id),
        ).fetchone()
        if existing:
            raise ValueError(
                f"Person '{person_id}' already has an Active enrollment in plan '{plan_id}'."
            )

        _validate_dependents(conn, person_id, coverage_level, dependent_ids)

        enrollment_id = str(uuid.uuid4())
        today = TODAY()
        conn.execute(
            """
            INSERT INTO ben_enrollment
              (enrollment_id, person_id, plan_id, enrollment_date, effective_start_date,
               effective_end_date, coverage_level, enrollment_status,
               employee_cost_monthly, employer_cost_monthly, created_on)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                enrollment_id,
                person_id,
                plan_id,
                today,
                effective_start_date,
                None,
                coverage_level,
                "Active",
                plan["employee_cost_monthly"],
                plan["employer_cost_monthly"],
                _now(),
            ),
        )

        if dependent_ids:
            for dep_id in dependent_ids:
                conn.execute(
                    """
                    INSERT INTO ben_enrolled_dependent
                      (enrollment_id, dependent_id, coverage_start_date, coverage_end_date,
                       created_on)
                    VALUES (?,?,?,?,?)
                    """,
                    (enrollment_id, dep_id, effective_start_date, None, _now()),
                )

        row = conn.execute(
            "SELECT * FROM ben_enrollment WHERE enrollment_id=?", (enrollment_id,)
        ).fetchone()
        return _row_to_enrollment(row)


def update_enrollment(
    enrollment_id: str,
    coverage_level: Optional[str] = None,
    dependent_ids: Optional[List[int]] = None,
) -> BenefitEnrollment:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM ben_enrollment WHERE enrollment_id=?", (enrollment_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Enrollment '{enrollment_id}' not found.")
        if row["enrollment_status"] != "Active":
            raise ValueError(
                f"Only Active enrollments can be updated (enrollment '{enrollment_id}' "
                f"is '{row['enrollment_status']}')."
            )

        if coverage_level is not None:
            if coverage_level not in VALID_COVERAGE_LEVELS:
                raise ValueError(
                    f"Invalid coverage_level '{coverage_level}'. Must be one of: {sorted(VALID_COVERAGE_LEVELS)}."
                )
            _validate_dependents(conn, row["person_id"], coverage_level, dependent_ids)

        updates = {}
        if coverage_level is not None:
            updates["coverage_level"] = coverage_level

        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates) + ", last_modified_on=?"
            conn.execute(
                f"UPDATE ben_enrollment SET {set_clause} WHERE enrollment_id=?",
                list(updates.values()) + [_now(), enrollment_id],
            )

        if dependent_ids is not None:
            conn.execute(
                "DELETE FROM ben_enrolled_dependent WHERE enrollment_id=?", (enrollment_id,)
            )
            start_date = row["effective_start_date"]
            for dep_id in dependent_ids:
                conn.execute(
                    """
                    INSERT INTO ben_enrolled_dependent
                      (enrollment_id, dependent_id, coverage_start_date, coverage_end_date)
                    VALUES (?,?,?,?)
                    """,
                    (enrollment_id, dep_id, start_date, None),
                )

        row = conn.execute(
            "SELECT * FROM ben_enrollment WHERE enrollment_id=?", (enrollment_id,)
        ).fetchone()
        return _row_to_enrollment(row)


def terminate_enrollment(enrollment_id: str, effective_end_date: str) -> BenefitEnrollment:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM ben_enrollment WHERE enrollment_id=?", (enrollment_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Enrollment '{enrollment_id}' not found.")

        if effective_end_date < row["effective_start_date"]:
            raise ValueError(
                f"effective_end_date '{effective_end_date}' must be >= "
                f"effective_start_date '{row['effective_start_date']}'."
            )

        conn.execute(
            "UPDATE ben_enrollment SET enrollment_status='Terminated', effective_end_date=?, last_modified_on=? WHERE enrollment_id=?",
            (effective_end_date, _now(), enrollment_id),
        )
        conn.execute(
            "UPDATE ben_enrolled_dependent SET coverage_end_date=? WHERE enrollment_id=? AND coverage_end_date IS NULL",
            (effective_end_date, enrollment_id),
        )

        row = conn.execute(
            "SELECT * FROM ben_enrollment WHERE enrollment_id=?", (enrollment_id,)
        ).fetchone()
        return _row_to_enrollment(row)


# ── Enrolled Dependents ───────────────────────────────────────────────────────


def list_enrolled_dependents(enrollment_id: str) -> List[EnrolledDependent]:
    with get_conn() as conn:
        enrollment = conn.execute(
            "SELECT enrollment_id FROM ben_enrollment WHERE enrollment_id=?", (enrollment_id,)
        ).fetchone()
        if not enrollment:
            raise LookupError(f"Enrollment '{enrollment_id}' not found.")
        rows = conn.execute(
            "SELECT * FROM ben_enrolled_dependent WHERE enrollment_id=?", (enrollment_id,)
        ).fetchall()
        return [_row_to_enrolled_dependent(r) for r in rows]


def add_dependent_coverage(
    enrollment_id: str,
    dependent_id: int,
    coverage_start_date: str,
) -> EnrolledDependent:
    with get_conn() as conn:
        enrollment = conn.execute(
            "SELECT * FROM ben_enrollment WHERE enrollment_id=?", (enrollment_id,)
        ).fetchone()
        if not enrollment:
            raise LookupError(f"Enrollment '{enrollment_id}' not found.")
        if enrollment["enrollment_status"] != "Active":
            raise ValueError(
                f"Enrollment '{enrollment_id}' is not Active; cannot add dependent coverage."
            )

        dep = conn.execute(
            "SELECT dependent_id FROM per_dependent WHERE dependent_id=? AND person_id=?",
            (dependent_id, enrollment["person_id"]),
        ).fetchone()
        if not dep:
            raise ValueError(
                f"Dependent '{dependent_id}' does not exist or does not belong to "
                f"person '{enrollment['person_id']}'."
            )

        existing = conn.execute(
            "SELECT enrolled_dependent_id FROM ben_enrolled_dependent "
            "WHERE enrollment_id=? AND dependent_id=? AND coverage_end_date IS NULL",
            (enrollment_id, dependent_id),
        ).fetchone()
        if existing:
            raise ValueError(
                f"Dependent '{dependent_id}' already has active coverage on enrollment '{enrollment_id}'."
            )

        coverage_level = enrollment["coverage_level"]
        if coverage_level == "Employee Only":
            raise ValueError(
                f"Enrollment '{enrollment_id}' has coverage_level 'Employee Only'; "
                f"cannot add dependents. Update the coverage level first."
            )

        conn.execute(
            """
            INSERT INTO ben_enrolled_dependent
              (enrollment_id, dependent_id, coverage_start_date, coverage_end_date,
               created_on)
            VALUES (?,?,?,?,?)
            """,
            (enrollment_id, dependent_id, coverage_start_date, None, _now()),
        )
        row = conn.execute(
            "SELECT * FROM ben_enrolled_dependent WHERE enrolled_dependent_id=last_insert_rowid()"
        ).fetchone()
        return _row_to_enrolled_dependent(row)


def remove_dependent_coverage(
    enrolled_dependent_id: int,
    coverage_end_date: str,
) -> EnrolledDependent:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM ben_enrolled_dependent WHERE enrolled_dependent_id=?",
            (enrolled_dependent_id,),
        ).fetchone()
        if not row:
            raise LookupError(f"Enrolled dependent record '{enrolled_dependent_id}' not found.")

        conn.execute(
            "UPDATE ben_enrolled_dependent SET coverage_end_date=? WHERE enrolled_dependent_id=?",
            (coverage_end_date, enrolled_dependent_id),
        )

        enrollment = conn.execute(
            "SELECT * FROM ben_enrollment WHERE enrollment_id=?", (row["enrollment_id"],)
        ).fetchone()

        if enrollment and enrollment["coverage_level"] != "Employee Only":
            remaining = conn.execute(
                "SELECT COUNT(*) AS cnt FROM ben_enrolled_dependent "
                "WHERE enrollment_id=? AND coverage_end_date IS NULL",
                (row["enrollment_id"],),
            ).fetchone()["cnt"]
            if remaining == 0:
                raise ValueError(
                    f"All dependents have been removed from enrollment '{row['enrollment_id']}', "
                    f"but the coverage_level is still '{enrollment['coverage_level']}'. "
                    f"Please update the coverage_level to 'Employee Only'."
                )

        row = conn.execute(
            "SELECT * FROM ben_enrolled_dependent WHERE enrolled_dependent_id=?",
            (enrolled_dependent_id,),
        ).fetchone()
        return _row_to_enrolled_dependent(row)
