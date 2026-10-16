import datetime
from typing import List, Optional

from synthesize.environments.hr.db.db import get_conn
from synthesize.environments.hr.db.models import (
    CostCenter,
    Department,
    JobCode,
    Location,
    PayGrade,
    Person,
    Position,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _row_to_department(row) -> Department:
    return Department(
        department_code=row["department_code"],
        department_name=row["department_name"],
        division_code=row["division_code"],
        department_head_person_id=row["department_head_person_id"],
        cost_center_code=row["cost_center_code"],
        status=row["status"],
        headcount=row["headcount"] if "headcount" in row.keys() else 0,
    )


def _row_to_location(row) -> Location:
    return Location(
        location_code=row["location_code"],
        location_name=row["location_name"],
        city=row["city"],
        state=row["state"],
        country=row["country"],
        time_zone=row["time_zone"],
        status=row["status"],
    )


def _row_to_job_code(row) -> JobCode:
    return JobCode(
        job_code=row["job_code"],
        job_title=row["job_title"],
        job_level=row["job_level"],
        job_family=row["job_family"],
        flsa_status=row["flsa_status"],
        standard_hours=row["standard_hours"],
        status=row["status"],
    )


def _row_to_position(row) -> Position:
    return Position(
        position_id=row["position_id"],
        position_title=row["position_title"],
        job_code=row["job_code"],
        department_code=row["department_code"],
        location_code=row["location_code"],
        reports_to_position_id=row["reports_to_position_id"],
        critical_position=bool(row["critical_position"]),
        position_status=row["position_status"],
    )


def _row_to_cost_center(row) -> CostCenter:
    return CostCenter(
        cost_center_code=row["cost_center_code"],
        cost_center_name=row["cost_center_name"],
        company_code=row["company_code"],
        status=row["status"],
    )


def _row_to_pay_grade(row) -> PayGrade:
    return PayGrade(
        pay_grade_code=row["pay_grade_code"],
        pay_grade_name=row["pay_grade_name"],
        min_salary=row["min_salary"],
        mid_salary=row["mid_salary"],
        max_salary=row["max_salary"],
        currency=row["currency"],
    )


def _row_to_person(row) -> Person:
    return Person(
        person_id=row["person_id"],
        person_id_external=row["person_id_external"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        middle_name=row["middle_name"],
        preferred_name=row["preferred_name"],
        date_of_birth=row["date_of_birth"],
        gender=row["gender"],
        nationality=row["nationality"],
        marital_status=row["marital_status"],
        person_type=row["person_type"],
    )


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(sep=" ", timespec="seconds")


# ── Departments ───────────────────────────────────────────────────────────────


def list_departments(status: str = "Active") -> List[Department]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT d.*,
                   COUNT(j.person_id) AS headcount
            FROM fod_department d
            LEFT JOIN emp_job j
                ON j.department_code = d.department_code
                AND j.end_date IS NULL
            WHERE d.status = ?
            GROUP BY d.department_code
            """,
            (status,),
        ).fetchall()
        return [_row_to_department(r) for r in rows]


def get_department(dept_code: str) -> Department:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT d.*,
                   COUNT(j.person_id) AS headcount
            FROM fod_department d
            LEFT JOIN emp_job j
                ON j.department_code = d.department_code
                AND j.end_date IS NULL
            WHERE d.department_code = ?
            GROUP BY d.department_code
            """,
            (dept_code,),
        ).fetchone()
        if row is None:
            raise LookupError(f"Department not found: {dept_code!r}")
        return _row_to_department(row)


def list_department_employees(dept_code: str) -> List[Person]:
    get_department(dept_code)  # raises LookupError if missing
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT p.*
            FROM per_person p
            JOIN emp_job j ON j.person_id = p.person_id
            WHERE j.department_code = ?
              AND j.end_date IS NULL
            """,
            (dept_code,),
        ).fetchall()
        return [_row_to_person(r) for r in rows]


def create_department(
    department_code: str,
    department_name: str,
    division_code: Optional[str] = None,
    cost_center_code: Optional[str] = None,
    department_head_person_id: Optional[str] = None,
) -> Department:
    now = _now()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM fod_department WHERE department_code = ?",
            (department_code,),
        ).fetchone()
        if existing:
            raise ValueError(f"Department code already exists: {department_code!r}")

        if division_code is not None:
            if not conn.execute(
                "SELECT 1 FROM fod_division WHERE division_code = ?", (division_code,)
            ).fetchone():
                raise ValueError(f"Division not found: {division_code!r}")

        if cost_center_code is not None:
            if not conn.execute(
                "SELECT 1 FROM fod_cost_center WHERE cost_center_code = ?",
                (cost_center_code,),
            ).fetchone():
                raise ValueError(f"Cost center not found: {cost_center_code!r}")

        conn.execute(
            """
            INSERT INTO fod_department
                (department_code, department_name, division_code,
                 department_head_person_id, cost_center_code, status,
                 created_on, last_modified_on)
            VALUES (?, ?, ?, ?, ?, 'Active', ?, ?)
            """,
            (
                department_code,
                department_name,
                division_code,
                department_head_person_id,
                cost_center_code,
                now,
                now,
            ),
        )

    return Department(
        department_code=department_code,
        department_name=department_name,
        division_code=division_code,
        department_head_person_id=department_head_person_id,
        cost_center_code=cost_center_code,
        status="Active",
        headcount=0,
    )


def update_department(dept_code: str, **kwargs) -> Department:
    allowed = {
        "department_name",
        "division_code",
        "department_head_person_id",
        "cost_center_code",
        "status",
    }
    invalid = set(kwargs) - allowed
    if invalid:
        raise ValueError(f"Invalid fields for update_department: {invalid}")

    now = _now()
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM fod_department WHERE department_code = ?", (dept_code,)
        ).fetchone():
            raise LookupError(f"Department not found: {dept_code!r}")

        if "division_code" in kwargs and kwargs["division_code"] is not None:
            if not conn.execute(
                "SELECT 1 FROM fod_division WHERE division_code = ?",
                (kwargs["division_code"],),
            ).fetchone():
                raise ValueError(f"Division not found: {kwargs['division_code']!r}")

        if "cost_center_code" in kwargs and kwargs["cost_center_code"] is not None:
            if not conn.execute(
                "SELECT 1 FROM fod_cost_center WHERE cost_center_code = ?",
                (kwargs["cost_center_code"],),
            ).fetchone():
                raise ValueError(f"Cost center not found: {kwargs['cost_center_code']!r}")

        sets = ", ".join(f"{col} = ?" for col in kwargs)
        vals = list(kwargs.values()) + [now, dept_code]
        conn.execute(
            f"UPDATE fod_department SET {sets}, last_modified_on = ? WHERE department_code = ?",
            vals,
        )

    return get_department(dept_code)


# ── Locations ─────────────────────────────────────────────────────────────────


def list_locations(status: str = "Active") -> List[Location]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM fod_location WHERE status = ?", (status,)).fetchall()
        return [_row_to_location(r) for r in rows]


def get_location(location_code: str) -> Location:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM fod_location WHERE location_code = ?", (location_code,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Location not found: {location_code!r}")
        return _row_to_location(row)


def list_location_employees(location_code: str) -> List[Person]:
    get_location(location_code)  # raises LookupError if missing
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT p.*
            FROM per_person p
            JOIN emp_job j ON j.person_id = p.person_id
            WHERE j.location_code = ?
              AND j.end_date IS NULL
            """,
            (location_code,),
        ).fetchall()
        return [_row_to_person(r) for r in rows]


def create_location(
    location_code: str,
    location_name: str,
    city: str,
    country: str,
    state: Optional[str] = None,
    time_zone: Optional[str] = None,
    address_line1: Optional[str] = None,
    postal_code: Optional[str] = None,
) -> Location:
    now = _now()
    with get_conn() as conn:
        if conn.execute(
            "SELECT 1 FROM fod_location WHERE location_code = ?", (location_code,)
        ).fetchone():
            raise ValueError(f"Location code already exists: {location_code!r}")

        conn.execute(
            """
            INSERT INTO fod_location
                (location_code, location_name, city, state, country, time_zone,
                 address_line1, postal_code, status, created_on, last_modified_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)
            """,
            (
                location_code,
                location_name,
                city,
                state,
                country,
                time_zone,
                address_line1,
                postal_code,
                now,
                now,
            ),
        )

    return Location(
        location_code=location_code,
        location_name=location_name,
        city=city,
        state=state,
        country=country,
        time_zone=time_zone,
        status="Active",
    )


def update_location(location_code: str, **kwargs) -> Location:
    allowed = {
        "location_name",
        "city",
        "state",
        "country",
        "time_zone",
        "address_line1",
        "postal_code",
        "status",
    }
    invalid = set(kwargs) - allowed
    if invalid:
        raise ValueError(f"Invalid fields for update_location: {invalid}")

    now = _now()
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM fod_location WHERE location_code = ?", (location_code,)
        ).fetchone():
            raise LookupError(f"Location not found: {location_code!r}")

        sets = ", ".join(f"{col} = ?" for col in kwargs)
        vals = list(kwargs.values()) + [now, location_code]
        conn.execute(
            f"UPDATE fod_location SET {sets}, last_modified_on = ? WHERE location_code = ?",
            vals,
        )

    return get_location(location_code)


# ── Job Codes ─────────────────────────────────────────────────────────────────


def list_job_codes(status: str = "Active") -> List[JobCode]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM fod_job_code WHERE status = ?", (status,)).fetchall()
        return [_row_to_job_code(r) for r in rows]


def get_job_code(job_code: str) -> JobCode:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM fod_job_code WHERE job_code = ?", (job_code,)).fetchone()
        if row is None:
            raise LookupError(f"Job code not found: {job_code!r}")
        return _row_to_job_code(row)


def create_job_code(
    job_code: str,
    job_title: str,
    job_level: Optional[str] = None,
    job_family: Optional[str] = None,
    flsa_status: Optional[str] = None,
    standard_hours: float = 40.0,
) -> JobCode:
    now = _now()
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM fod_job_code WHERE job_code = ?", (job_code,)).fetchone():
            raise ValueError(f"Job code already exists: {job_code!r}")

        conn.execute(
            """
            INSERT INTO fod_job_code
                (job_code, job_title, job_level, job_family, flsa_status,
                 standard_hours, status, created_on, last_modified_on)
            VALUES (?, ?, ?, ?, ?, ?, 'Active', ?, ?)
            """,
            (
                job_code,
                job_title,
                job_level,
                job_family,
                flsa_status,
                standard_hours,
                now,
                now,
            ),
        )

    return JobCode(
        job_code=job_code,
        job_title=job_title,
        job_level=job_level,
        job_family=job_family,
        flsa_status=flsa_status,
        standard_hours=standard_hours,
        status="Active",
    )


def update_job_code(job_code: str, **kwargs) -> JobCode:
    allowed = {
        "job_title",
        "job_level",
        "job_family",
        "flsa_status",
        "standard_hours",
        "status",
    }
    invalid = set(kwargs) - allowed
    if invalid:
        raise ValueError(f"Invalid fields for update_job_code: {invalid}")

    now = _now()
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM fod_job_code WHERE job_code = ?", (job_code,)
        ).fetchone():
            raise LookupError(f"Job code not found: {job_code!r}")

        sets = ", ".join(f"{col} = ?" for col in kwargs)
        vals = list(kwargs.values()) + [now, job_code]
        conn.execute(
            f"UPDATE fod_job_code SET {sets}, last_modified_on = ? WHERE job_code = ?",
            vals,
        )

    return get_job_code(job_code)


# ── Positions ─────────────────────────────────────────────────────────────────


def list_positions(status: Optional[str] = None, dept_code: Optional[str] = None) -> List[Position]:
    query = "SELECT * FROM fod_position WHERE 1=1"
    params: list = []
    if status is not None:
        query += " AND position_status = ?"
        params.append(status)
    if dept_code is not None:
        query += " AND department_code = ?"
        params.append(dept_code)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_position(r) for r in rows]


def get_position(position_id: str) -> Position:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM fod_position WHERE position_id = ?", (position_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Position not found: {position_id!r}")
        return _row_to_position(row)


def create_position(
    position_id: str,
    position_title: str,
    job_code: str,
    department_code: str,
    location_code: str,
    reports_to_position_id: Optional[str] = None,
    critical_position: bool = False,
) -> Position:
    now = _now()
    with get_conn() as conn:
        if conn.execute(
            "SELECT 1 FROM fod_position WHERE position_id = ?", (position_id,)
        ).fetchone():
            raise ValueError(f"Position ID already exists: {position_id!r}")

        if not conn.execute(
            "SELECT 1 FROM fod_job_code WHERE job_code = ?", (job_code,)
        ).fetchone():
            raise ValueError(f"Job code not found: {job_code!r}")

        if not conn.execute(
            "SELECT 1 FROM fod_department WHERE department_code = ?", (department_code,)
        ).fetchone():
            raise ValueError(f"Department not found: {department_code!r}")

        if not conn.execute(
            "SELECT 1 FROM fod_location WHERE location_code = ?", (location_code,)
        ).fetchone():
            raise ValueError(f"Location not found: {location_code!r}")

        if reports_to_position_id is not None:
            if reports_to_position_id == position_id:
                raise ValueError("A position cannot report to itself")
            if not conn.execute(
                "SELECT 1 FROM fod_position WHERE position_id = ?",
                (reports_to_position_id,),
            ).fetchone():
                raise ValueError(f"reports_to_position_id not found: {reports_to_position_id!r}")

        conn.execute(
            """
            INSERT INTO fod_position
                (position_id, position_title, job_code, department_code, location_code,
                 reports_to_position_id, critical_position, position_status,
                 created_on, last_modified_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)
            """,
            (
                position_id,
                position_title,
                job_code,
                department_code,
                location_code,
                reports_to_position_id,
                int(critical_position),
                now,
                now,
            ),
        )

    return Position(
        position_id=position_id,
        position_title=position_title,
        job_code=job_code,
        department_code=department_code,
        location_code=location_code,
        reports_to_position_id=reports_to_position_id,
        critical_position=critical_position,
        position_status="Active",
    )


def update_position(position_id: str, **kwargs) -> Position:
    allowed = {
        "position_title",
        "department_code",
        "location_code",
        "reports_to_position_id",
        "critical_position",
        "position_status",
    }
    invalid = set(kwargs) - allowed
    if invalid:
        raise ValueError(f"Invalid fields for update_position: {invalid}")

    now = _now()
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM fod_position WHERE position_id = ?", (position_id,)
        ).fetchone():
            raise LookupError(f"Position not found: {position_id!r}")

        if "department_code" in kwargs and kwargs["department_code"] is not None:
            if not conn.execute(
                "SELECT 1 FROM fod_department WHERE department_code = ?",
                (kwargs["department_code"],),
            ).fetchone():
                raise ValueError(f"Department not found: {kwargs['department_code']!r}")

        if "location_code" in kwargs and kwargs["location_code"] is not None:
            if not conn.execute(
                "SELECT 1 FROM fod_location WHERE location_code = ?",
                (kwargs["location_code"],),
            ).fetchone():
                raise ValueError(f"Location not found: {kwargs['location_code']!r}")

        if "reports_to_position_id" in kwargs and kwargs["reports_to_position_id"] is not None:
            if kwargs["reports_to_position_id"] == position_id:
                raise ValueError("A position cannot report to itself")
            if not conn.execute(
                "SELECT 1 FROM fod_position WHERE position_id = ?",
                (kwargs["reports_to_position_id"],),
            ).fetchone():
                raise ValueError(
                    f"reports_to_position_id not found: {kwargs['reports_to_position_id']!r}"
                )

        if "critical_position" in kwargs:
            kwargs["critical_position"] = int(kwargs["critical_position"])

        sets = ", ".join(f"{col} = ?" for col in kwargs)
        vals = list(kwargs.values()) + [now, position_id]
        conn.execute(
            f"UPDATE fod_position SET {sets}, last_modified_on = ? WHERE position_id = ?",
            vals,
        )

    return get_position(position_id)


# ── Cost Centers ──────────────────────────────────────────────────────────────


def list_cost_centers() -> List[CostCenter]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM fod_cost_center").fetchall()
        return [_row_to_cost_center(r) for r in rows]


def get_cost_center(cost_center_code: str) -> CostCenter:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM fod_cost_center WHERE cost_center_code = ?",
            (cost_center_code,),
        ).fetchone()
        if row is None:
            raise LookupError(f"Cost center not found: {cost_center_code!r}")
        return _row_to_cost_center(row)


def create_cost_center(
    cost_center_code: str,
    cost_center_name: str,
    company_code: Optional[str] = None,
) -> CostCenter:
    now = _now()
    with get_conn() as conn:
        if conn.execute(
            "SELECT 1 FROM fod_cost_center WHERE cost_center_code = ?",
            (cost_center_code,),
        ).fetchone():
            raise ValueError(f"Cost center code already exists: {cost_center_code!r}")

        if company_code is not None:
            if not conn.execute(
                "SELECT 1 FROM fod_company WHERE company_code = ?", (company_code,)
            ).fetchone():
                raise ValueError(f"Company not found: {company_code!r}")

        conn.execute(
            """
            INSERT INTO fod_cost_center
                (cost_center_code, cost_center_name, company_code, status,
                 created_on, last_modified_on)
            VALUES (?, ?, ?, 'Active', ?, ?)
            """,
            (cost_center_code, cost_center_name, company_code, now, now),
        )

    return CostCenter(
        cost_center_code=cost_center_code,
        cost_center_name=cost_center_name,
        company_code=company_code,
        status="Active",
    )


def update_cost_center(cost_center_code: str, **kwargs) -> CostCenter:
    allowed = {"cost_center_name", "company_code", "status"}
    invalid = set(kwargs) - allowed
    if invalid:
        raise ValueError(f"Invalid fields for update_cost_center: {invalid}")

    now = _now()
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM fod_cost_center WHERE cost_center_code = ?",
            (cost_center_code,),
        ).fetchone():
            raise LookupError(f"Cost center not found: {cost_center_code!r}")

        if "company_code" in kwargs and kwargs["company_code"] is not None:
            if not conn.execute(
                "SELECT 1 FROM fod_company WHERE company_code = ?",
                (kwargs["company_code"],),
            ).fetchone():
                raise ValueError(f"Company not found: {kwargs['company_code']!r}")

        sets = ", ".join(f"{col} = ?" for col in kwargs)
        vals = list(kwargs.values()) + [now, cost_center_code]
        conn.execute(
            f"UPDATE fod_cost_center SET {sets}, last_modified_on = ? WHERE cost_center_code = ?",
            vals,
        )

    return get_cost_center(cost_center_code)


# ── Pay Grades ────────────────────────────────────────────────────────────────


def list_pay_grades() -> List[PayGrade]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM fod_pay_grade").fetchall()
        return [_row_to_pay_grade(r) for r in rows]


def get_pay_grade(pay_grade_code: str) -> PayGrade:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM fod_pay_grade WHERE pay_grade_code = ?", (pay_grade_code,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Pay grade not found: {pay_grade_code!r}")
        return _row_to_pay_grade(row)
