import datetime
import uuid
from typing import List, Optional

from synthesize.environments.hr.db.db import get_conn
from synthesize.environments.hr.db.models import (
    CompensationCycle,
    CompensationRecord,
    CompensationWorksheet,
    row_to_dict,
)

# ── Private helpers ────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(sep=" ", timespec="seconds")


def _comp_from_row(row) -> CompensationRecord:
    d = row_to_dict(row)
    return CompensationRecord(
        compensation_id=d["compensation_id"],
        person_id=d["person_id"],
        start_date=d["start_date"],
        end_date=d.get("end_date"),
        pay_component_code=d["pay_component_code"],
        pay_frequency=d.get("pay_frequency"),
        amount=d["amount"],
        currency=d.get("currency", "USD"),
        pay_grade=d.get("pay_grade"),
        event_reason_code=d.get("event_reason_code"),
    )


def _cycle_from_row(row) -> CompensationCycle:
    d = row_to_dict(row)
    return CompensationCycle(
        cycle_id=d["cycle_id"],
        cycle_name=d["cycle_name"],
        cycle_year=d["cycle_year"],
        cycle_type=d["cycle_type"],
        start_date=d["start_date"],
        end_date=d["end_date"],
        budget_percentage=d.get("budget_percentage"),
        cycle_status=d["cycle_status"],
    )


def _worksheet_from_row(row) -> CompensationWorksheet:
    d = row_to_dict(row)
    return CompensationWorksheet(
        worksheet_id=d["worksheet_id"],
        cycle_id=d["cycle_id"],
        person_id=d["person_id"],
        current_salary=d.get("current_salary"),
        proposed_salary=d.get("proposed_salary"),
        salary_increase_amount=d.get("salary_increase_amount"),
        salary_increase_percentage=d.get("salary_increase_percentage"),
        merit_increase=d.get("merit_increase"),
        bonus_amount=d.get("bonus_amount"),
        stock_grant_amount=d.get("stock_grant_amount"),
        compa_ratio=d.get("compa_ratio"),
        performance_rating=d.get("performance_rating"),
        worksheet_status=d.get("worksheet_status", "Draft"),
        manager_comments=d.get("manager_comments"),
    )


def _get_pay_grade_band(conn, pay_grade_code: str):
    row = conn.execute(
        "SELECT min_salary, mid_salary, max_salary FROM fod_pay_grade WHERE pay_grade_code = ?",
        (pay_grade_code,),
    ).fetchone()
    if row:
        return row_to_dict(row)
    return None


def _get_current_job(conn, person_id: str):
    return conn.execute(
        "SELECT * FROM emp_job WHERE person_id = ? AND end_date IS NULL LIMIT 1",
        (person_id,),
    ).fetchone()


# ── Compensation read functions ────────────────────────────────────────────────


def get_compensation(person_id: str) -> List[CompensationRecord]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM emp_compensation WHERE person_id = ? AND end_date IS NULL "
            "ORDER BY pay_component_code",
            (person_id,),
        ).fetchall()
        return [_comp_from_row(r) for r in rows]


def get_compensation_history(person_id: str) -> List[CompensationRecord]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM emp_compensation WHERE person_id = ? ORDER BY start_date DESC",
            (person_id,),
        ).fetchall()
        return [_comp_from_row(r) for r in rows]


# ── Compensation write functions ───────────────────────────────────────────────


def update_compensation(
    person_id: str,
    event_reason_code: str,
    changes: List[dict],
) -> List[CompensationRecord]:
    with get_conn() as conn:
        reason_row = conn.execute(
            "SELECT event_reason_code FROM fod_event_reason WHERE event_reason_code = ?",
            (event_reason_code,),
        ).fetchone()
        if not reason_row:
            raise ValueError(f"Event reason code not found: {event_reason_code}")

        for change in changes:
            pc = change.get("pay_component_code")
            if not conn.execute(
                "SELECT 1 FROM fod_pay_component WHERE pay_component_code = ?", (pc,)
            ).fetchone():
                raise ValueError(f"Pay component code not found: {pc}")

        job_row = _get_current_job(conn, person_id)
        pay_grade_band = None
        if job_row and job_row["pay_grade"]:
            pay_grade_band = _get_pay_grade_band(conn, job_row["pay_grade"])

        for change in changes:
            pc = change["pay_component_code"]
            new_amount = float(change["amount"])

            if pc == "BASE" and pay_grade_band:
                min_sal = pay_grade_band.get("min_salary")
                max_sal = pay_grade_band.get("max_salary")
                if min_sal is not None and new_amount < min_sal:
                    raise ValueError(
                        f"BASE salary {new_amount} is below pay grade minimum {min_sal}."
                    )
                if max_sal is not None and new_amount > max_sal:
                    raise ValueError(
                        f"BASE salary {new_amount} exceeds pay grade maximum {max_sal}."
                    )

            conn.execute(
                "UPDATE emp_compensation SET end_date = date('now') "
                "WHERE person_id = ? AND pay_component_code = ? AND end_date IS NULL",
                (person_id, pc),
            )

            conn.execute(
                """
                INSERT INTO emp_compensation
                    (person_id, start_date, pay_component_code, pay_frequency,
                     amount, currency, pay_grade, event_reason_code, created_on)
                VALUES (?, date('now'), ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    person_id,
                    pc,
                    change.get("pay_frequency"),
                    new_amount,
                    change.get("currency", "USD"),
                    job_row["pay_grade"] if job_row else None,
                    event_reason_code,
                    _now(),
                ),
            )

        rows = conn.execute(
            "SELECT * FROM emp_compensation WHERE person_id = ? AND end_date IS NULL "
            "ORDER BY pay_component_code",
            (person_id,),
        ).fetchall()
        return [_comp_from_row(r) for r in rows]


# ── Compensation cycle functions ───────────────────────────────────────────────


def list_cycles() -> List[CompensationCycle]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cp_compensation_cycle ORDER BY cycle_year DESC, cycle_name"
        ).fetchall()
        return [_cycle_from_row(r) for r in rows]


def get_cycle(cycle_id: str) -> CompensationCycle:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM cp_compensation_cycle WHERE cycle_id = ?", (cycle_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Compensation cycle not found: {cycle_id}")
        return _cycle_from_row(row)


def create_cycle(
    cycle_name: str,
    cycle_year: int,
    cycle_type: str,
    start_date: str,
    end_date: str,
    budget_percentage: Optional[float] = None,
) -> CompensationCycle:
    with get_conn() as conn:
        conflict = conn.execute(
            "SELECT cycle_id FROM cp_compensation_cycle "
            "WHERE cycle_year = ? AND cycle_type = ? AND cycle_status IN ('Open', 'Planning')",
            (cycle_year, cycle_type),
        ).fetchone()
        if conflict:
            raise ValueError(
                f"A cycle of type '{cycle_type}' for year {cycle_year} is already "
                f"Open or Planning (cycle_id={conflict['cycle_id']})."
            )

        cycle_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO cp_compensation_cycle
                (cycle_id, cycle_name, cycle_year, cycle_type,
                 start_date, end_date, budget_percentage, cycle_status, created_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Planning', ?)
            """,
            (
                cycle_id,
                cycle_name,
                cycle_year,
                cycle_type,
                start_date,
                end_date,
                budget_percentage,
                _now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM cp_compensation_cycle WHERE cycle_id = ?", (cycle_id,)
        ).fetchone()
        return _cycle_from_row(row)


# ── Worksheet functions ────────────────────────────────────────────────────────


def list_worksheets(cycle_id: str) -> List[CompensationWorksheet]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM cp_worksheet WHERE cycle_id = ? ORDER BY person_id",
            (cycle_id,),
        ).fetchall()
        return [_worksheet_from_row(r) for r in rows]


def get_worksheet(cycle_id: str, person_id: str) -> CompensationWorksheet:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM cp_worksheet WHERE cycle_id = ? AND person_id = ?",
            (cycle_id, person_id),
        ).fetchone()
        if not row:
            raise LookupError(f"Worksheet not found for cycle={cycle_id}, person={person_id}")
        return _worksheet_from_row(row)


def update_worksheet(
    cycle_id: str,
    person_id: str,
    proposed_salary: Optional[float] = None,
    merit_increase: Optional[float] = None,
    bonus_amount: Optional[float] = None,
    stock_grant_amount: Optional[float] = None,
    manager_comments: Optional[str] = None,
    submit: bool = False,
) -> CompensationWorksheet:
    with get_conn() as conn:
        cycle_row = conn.execute(
            "SELECT cycle_status FROM cp_compensation_cycle WHERE cycle_id = ?",
            (cycle_id,),
        ).fetchone()
        if not cycle_row:
            raise LookupError(f"Compensation cycle not found: {cycle_id}")
        if cycle_row["cycle_status"] in ("Completed", "Closed"):
            raise ValueError(
                f"Cycle {cycle_id} is {cycle_row['cycle_status']} and cannot be modified."
            )

        ws_row = conn.execute(
            "SELECT * FROM cp_worksheet WHERE cycle_id = ? AND person_id = ?",
            (cycle_id, person_id),
        ).fetchone()
        if not ws_row:
            raise LookupError(f"Worksheet not found for cycle={cycle_id}, person={person_id}")

        ws = row_to_dict(ws_row)
        current_salary = ws.get("current_salary")

        salary_increase_amount = None
        salary_increase_pct = None
        compa_ratio = ws.get("compa_ratio")

        if proposed_salary is not None:
            if current_salary is not None:
                salary_increase_amount = proposed_salary - current_salary
                if current_salary and current_salary != 0:
                    salary_increase_pct = (salary_increase_amount / current_salary) * 100

            job_row = _get_current_job(conn, person_id)
            if job_row and job_row["pay_grade"]:
                band = _get_pay_grade_band(conn, job_row["pay_grade"])
                if band:
                    max_sal = band.get("max_salary")
                    mid_sal = band.get("mid_salary")
                    if max_sal is not None and proposed_salary > max_sal * 1.2:
                        raise ValueError(
                            f"Proposed salary {proposed_salary} exceeds pay grade maximum "
                            f"{max_sal} by more than 20%."
                        )
                    if mid_sal is not None and mid_sal != 0:
                        compa_ratio = proposed_salary / mid_sal

        updates: dict = {}
        if proposed_salary is not None:
            updates["proposed_salary"] = proposed_salary
        if salary_increase_amount is not None:
            updates["salary_increase_amount"] = salary_increase_amount
        if salary_increase_pct is not None:
            updates["salary_increase_percentage"] = round(salary_increase_pct, 4)
        if compa_ratio is not None:
            updates["compa_ratio"] = round(compa_ratio, 4)
        if merit_increase is not None:
            updates["merit_increase"] = merit_increase
        if bonus_amount is not None:
            updates["bonus_amount"] = bonus_amount
        if stock_grant_amount is not None:
            updates["stock_grant_amount"] = stock_grant_amount
        if manager_comments is not None:
            updates["manager_comments"] = manager_comments
        if submit:
            updates["worksheet_status"] = "Submitted"

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates) + ", last_modified_on = ?"
            values = list(updates.values()) + [_now(), cycle_id, person_id]
            conn.execute(
                f"UPDATE cp_worksheet SET {set_clause} WHERE cycle_id = ? AND person_id = ?",
                values,
            )

        updated_row = conn.execute(
            "SELECT * FROM cp_worksheet WHERE cycle_id = ? AND person_id = ?",
            (cycle_id, person_id),
        ).fetchone()
        return _worksheet_from_row(updated_row)
