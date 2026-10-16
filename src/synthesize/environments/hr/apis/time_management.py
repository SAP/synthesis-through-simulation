import datetime
import uuid
from typing import List, Optional

from synthesize.environments.hr.db.db import get_conn
from synthesize.environments.hr.db.models import TimeOffBalance, TimeOffRequest, Timesheet

# ── Helpers ───────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(sep=" ", timespec="seconds")


def _row_to_balance(row) -> TimeOffBalance:
    return TimeOffBalance(
        balance_id=row["balance_id"],
        person_id=row["person_id"],
        time_off_type_code=row["time_off_type_code"],
        year=row["year"],
        accrued_days=row["accrued_days"],
        used_days=row["used_days"],
        pending_days=row["pending_days"],
        available_days=row["available_days"],
    )


def _row_to_request(row) -> TimeOffRequest:
    return TimeOffRequest(
        request_id=row["request_id"],
        person_id=row["person_id"],
        time_off_type_code=row["time_off_type_code"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        total_days=row["total_days"],
        request_status=row["request_status"],
        request_date=row["request_date"],
        approval_date=row["approval_date"],
        approver_person_id=row["approver_person_id"],
        rejection_reason=row["rejection_reason"],
    )


def _row_to_timesheet(row) -> Timesheet:
    return Timesheet(
        timesheet_id=row["timesheet_id"],
        person_id=row["person_id"],
        week_start_date=row["week_start_date"],
        week_end_date=row["week_end_date"],
        total_hours=row["total_hours"],
        regular_hours=row["regular_hours"],
        overtime_hours=row["overtime_hours"],
        timesheet_status=row["timesheet_status"],
        submitted_date=row["submitted_date"],
        approved_date=row["approved_date"],
    )


# ── Balances ──────────────────────────────────────────────────────────────────


def get_balances(person_id: str, year=None) -> List[TimeOffBalance]:
    if year is None:
        year = datetime.date.today().year
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tm_time_off_balance WHERE person_id = ? AND year = ?",
            (person_id, year),
        ).fetchall()
    return [_row_to_balance(r) for r in rows]


def adjust_balance(
    person_id, time_off_type_code, year, adjustment_days, reason=None
) -> TimeOffBalance:
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (person_id,)
        ).fetchone():
            raise LookupError(f"Person '{person_id}' not found")
        if not conn.execute(
            "SELECT 1 FROM tm_time_off_type WHERE time_off_type_code = ?",
            (time_off_type_code,),
        ).fetchone():
            raise LookupError(f"Time off type '{time_off_type_code}' not found")

        existing = conn.execute(
            """
            SELECT * FROM tm_time_off_balance
            WHERE person_id = ? AND time_off_type_code = ? AND year = ?
            """,
            (person_id, time_off_type_code, year),
        ).fetchone()

        if existing is None:
            new_available = adjustment_days
            if new_available < 0:
                raise ValueError("Resulting available_days would be negative")
            new_accrued = adjustment_days if adjustment_days > 0 else 0
            conn.execute(
                """
                INSERT INTO tm_time_off_balance
                    (person_id, time_off_type_code, year, accrued_days, used_days,
                     pending_days, available_days)
                VALUES (?, ?, ?, ?, 0, 0, ?)
                """,
                (person_id, time_off_type_code, year, new_accrued, new_available),
            )
        else:
            new_available = existing["available_days"] + adjustment_days
            if new_available < 0:
                raise ValueError(
                    f"Adjustment of {adjustment_days} would result in negative "
                    f"available_days ({new_available})"
                )
            new_accrued = (
                existing["accrued_days"] + adjustment_days
                if adjustment_days > 0
                else existing["accrued_days"]
            )
            conn.execute(
                """
                UPDATE tm_time_off_balance
                SET available_days = ?, accrued_days = ?
                WHERE person_id = ? AND time_off_type_code = ? AND year = ?
                """,
                (new_available, new_accrued, person_id, time_off_type_code, year),
            )

        row = conn.execute(
            """
            SELECT * FROM tm_time_off_balance
            WHERE person_id = ? AND time_off_type_code = ? AND year = ?
            """,
            (person_id, time_off_type_code, year),
        ).fetchone()
    return _row_to_balance(row)


# ── Time-Off Requests ─────────────────────────────────────────────────────────


def list_requests(
    person_id=None, status=None, start_date=None, end_date=None
) -> List[TimeOffRequest]:
    query = "SELECT * FROM tm_time_off_request WHERE 1=1"
    params: list = []
    if person_id is not None:
        query += " AND person_id = ?"
        params.append(person_id)
    if status is not None:
        query += " AND request_status = ?"
        params.append(status)
    if start_date is not None:
        query += " AND end_date >= ?"
        params.append(start_date)
    if end_date is not None:
        query += " AND start_date <= ?"
        params.append(end_date)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_request(r) for r in rows]


def get_request(request_id: str) -> TimeOffRequest:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tm_time_off_request WHERE request_id = ?", (request_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"Time-off request '{request_id}' not found")
    return _row_to_request(row)


def list_employee_requests(person_id: str, status=None) -> List[TimeOffRequest]:
    return list_requests(person_id=person_id, status=status)


def create_request(
    person_id,
    time_off_type_code,
    start_date,
    end_date,
    total_days,
    comments=None,
) -> TimeOffRequest:
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (person_id,)
        ).fetchone():
            raise LookupError(f"Person '{person_id}' not found")

        type_row = conn.execute(
            "SELECT * FROM tm_time_off_type WHERE time_off_type_code = ?",
            (time_off_type_code,),
        ).fetchone()
        if type_row is None:
            raise LookupError(f"Time off type '{time_off_type_code}' not found")

        if end_date < start_date:
            raise ValueError("end_date must be >= start_date")
        if total_days <= 0:
            raise ValueError("total_days must be > 0")

        year = datetime.date.fromisoformat(start_date).year
        balance_row = conn.execute(
            """
            SELECT * FROM tm_time_off_balance
            WHERE person_id = ? AND time_off_type_code = ? AND year = ?
            """,
            (person_id, time_off_type_code, year),
        ).fetchone()
        if balance_row is None or balance_row["available_days"] < total_days:
            available = balance_row["available_days"] if balance_row else 0
            raise ValueError(
                f"Insufficient balance: requested {total_days} days but only {available} available"
            )

        overlap = conn.execute(
            """
            SELECT 1 FROM tm_time_off_request
            WHERE person_id = ? AND time_off_type_code = ?
              AND request_status IN ('Pending', 'Approved')
              AND start_date <= ? AND end_date >= ?
            """,
            (person_id, time_off_type_code, end_date, start_date),
        ).fetchone()
        if overlap:
            raise ValueError(
                "An overlapping approved or pending request already exists for this period"
            )

        new_available = balance_row["available_days"] - total_days
        new_pending = balance_row["pending_days"] + total_days
        conn.execute(
            """
            UPDATE tm_time_off_balance
            SET available_days = ?, pending_days = ?
            WHERE person_id = ? AND time_off_type_code = ? AND year = ?
            """,
            (new_available, new_pending, person_id, time_off_type_code, year),
        )

        request_id = str(uuid.uuid4())
        today = datetime.date.today().isoformat()
        conn.execute(
            """
            INSERT INTO tm_time_off_request (
                request_id, person_id, time_off_type_code, start_date, end_date,
                total_days, request_status, request_date, comments, created_on
            ) VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?)
            """,
            (
                request_id,
                person_id,
                time_off_type_code,
                start_date,
                end_date,
                total_days,
                today,
                comments,
                _now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM tm_time_off_request WHERE request_id = ?", (request_id,)
        ).fetchone()
    return _row_to_request(row)


def update_request(
    request_id,
    start_date=None,
    end_date=None,
    total_days=None,
    comments=None,
) -> TimeOffRequest:
    with get_conn() as conn:
        req_row = conn.execute(
            "SELECT * FROM tm_time_off_request WHERE request_id = ?", (request_id,)
        ).fetchone()
        if req_row is None:
            raise LookupError(f"Time-off request '{request_id}' not found")
        if req_row["request_status"] != "Pending":
            raise ValueError(
                f"Can only update Pending requests (current status: {req_row['request_status']})"
            )

        new_start = start_date or req_row["start_date"]
        new_end = end_date or req_row["end_date"]
        new_total = total_days if total_days is not None else req_row["total_days"]
        new_comments = comments if comments is not None else req_row["comments"]

        if new_end < new_start:
            raise ValueError("end_date must be >= start_date")

        old_total = req_row["total_days"]
        if new_total != old_total:
            year = datetime.date.fromisoformat(new_start).year
            balance_row = conn.execute(
                """
                SELECT * FROM tm_time_off_balance
                WHERE person_id = ? AND time_off_type_code = ? AND year = ?
                """,
                (req_row["person_id"], req_row["time_off_type_code"], year),
            ).fetchone()
            delta = new_total - old_total
            current_available = balance_row["available_days"] if balance_row else 0
            if current_available - delta < 0:
                raise ValueError(
                    f"Insufficient balance for updated request: would need {delta} more days"
                )
            new_available = current_available - delta
            new_pending = (balance_row["pending_days"] if balance_row else 0) + delta
            conn.execute(
                """
                UPDATE tm_time_off_balance
                SET available_days = ?, pending_days = ?
                WHERE person_id = ? AND time_off_type_code = ? AND year = ?
                """,
                (
                    new_available,
                    new_pending,
                    req_row["person_id"],
                    req_row["time_off_type_code"],
                    year,
                ),
            )

        conn.execute(
            """
            UPDATE tm_time_off_request
            SET start_date = ?, end_date = ?, total_days = ?, comments = ?
            WHERE request_id = ?
            """,
            (new_start, new_end, new_total, new_comments, request_id),
        )
        row = conn.execute(
            "SELECT * FROM tm_time_off_request WHERE request_id = ?", (request_id,)
        ).fetchone()
    return _row_to_request(row)


def approve_request(request_id, approver_person_id) -> TimeOffRequest:
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (approver_person_id,)
        ).fetchone():
            raise LookupError(f"Approver person '{approver_person_id}' not found")

        req_row = conn.execute(
            "SELECT * FROM tm_time_off_request WHERE request_id = ?", (request_id,)
        ).fetchone()
        if req_row is None:
            raise LookupError(f"Time-off request '{request_id}' not found")
        if req_row["request_status"] != "Pending":
            raise ValueError(
                f"Can only approve Pending requests (current status: {req_row['request_status']})"
            )

        year = datetime.date.fromisoformat(req_row["start_date"]).year
        balance_row = conn.execute(
            """
            SELECT * FROM tm_time_off_balance
            WHERE person_id = ? AND time_off_type_code = ? AND year = ?
            """,
            (req_row["person_id"], req_row["time_off_type_code"], year),
        ).fetchone()
        if balance_row is not None:
            new_used = balance_row["used_days"] + req_row["total_days"]
            new_pending = balance_row["pending_days"] - req_row["total_days"]
            conn.execute(
                """
                UPDATE tm_time_off_balance
                SET used_days = ?, pending_days = ?
                WHERE person_id = ? AND time_off_type_code = ? AND year = ?
                """,
                (
                    new_used,
                    new_pending,
                    req_row["person_id"],
                    req_row["time_off_type_code"],
                    year,
                ),
            )

        today = datetime.date.today().isoformat()
        conn.execute(
            """
            UPDATE tm_time_off_request
            SET request_status = 'Approved', approval_date = ?, approver_person_id = ?,
                last_modified_on = ?
            WHERE request_id = ?
            """,
            (today, approver_person_id, _now(), request_id),
        )
        row = conn.execute(
            "SELECT * FROM tm_time_off_request WHERE request_id = ?", (request_id,)
        ).fetchone()
    return _row_to_request(row)


def deny_request(request_id, approver_person_id, rejection_reason) -> TimeOffRequest:
    if not rejection_reason:
        raise ValueError("rejection_reason is required")

    with get_conn() as conn:
        req_row = conn.execute(
            "SELECT * FROM tm_time_off_request WHERE request_id = ?", (request_id,)
        ).fetchone()
        if req_row is None:
            raise LookupError(f"Time-off request '{request_id}' not found")
        if req_row["request_status"] != "Pending":
            raise ValueError(
                f"Can only deny Pending requests (current status: {req_row['request_status']})"
            )

        year = datetime.date.fromisoformat(req_row["start_date"]).year
        balance_row = conn.execute(
            """
            SELECT * FROM tm_time_off_balance
            WHERE person_id = ? AND time_off_type_code = ? AND year = ?
            """,
            (req_row["person_id"], req_row["time_off_type_code"], year),
        ).fetchone()
        if balance_row is not None:
            new_available = balance_row["available_days"] + req_row["total_days"]
            new_pending = balance_row["pending_days"] - req_row["total_days"]
            conn.execute(
                """
                UPDATE tm_time_off_balance
                SET available_days = ?, pending_days = ?
                WHERE person_id = ? AND time_off_type_code = ? AND year = ?
                """,
                (
                    new_available,
                    new_pending,
                    req_row["person_id"],
                    req_row["time_off_type_code"],
                    year,
                ),
            )

        conn.execute(
            """
            UPDATE tm_time_off_request
            SET request_status = 'Rejected', rejection_reason = ?, last_modified_on = ?
            WHERE request_id = ?
            """,
            (rejection_reason, _now(), request_id),
        )
        row = conn.execute(
            "SELECT * FROM tm_time_off_request WHERE request_id = ?", (request_id,)
        ).fetchone()
    return _row_to_request(row)


def cancel_request(request_id, person_id) -> TimeOffRequest:
    with get_conn() as conn:
        req_row = conn.execute(
            "SELECT * FROM tm_time_off_request WHERE request_id = ?", (request_id,)
        ).fetchone()
        if req_row is None:
            raise LookupError(f"Time-off request '{request_id}' not found")
        if req_row["person_id"] != person_id:
            raise ValueError("Only the requesting person can cancel this request")
        if req_row["request_status"] == "Rejected":
            raise ValueError("Cannot cancel a Rejected request")
        if req_row["request_status"] not in ("Pending", "Approved"):
            raise ValueError(f"Cannot cancel a request with status '{req_row['request_status']}'")

        year = datetime.date.fromisoformat(req_row["start_date"]).year
        balance_row = conn.execute(
            """
            SELECT * FROM tm_time_off_balance
            WHERE person_id = ? AND time_off_type_code = ? AND year = ?
            """,
            (req_row["person_id"], req_row["time_off_type_code"], year),
        ).fetchone()

        if balance_row is not None:
            if req_row["request_status"] == "Pending":
                new_available = balance_row["available_days"] + req_row["total_days"]
                new_pending = balance_row["pending_days"] - req_row["total_days"]
                conn.execute(
                    """
                    UPDATE tm_time_off_balance
                    SET available_days = ?, pending_days = ?
                    WHERE person_id = ? AND time_off_type_code = ? AND year = ?
                    """,
                    (
                        new_available,
                        new_pending,
                        req_row["person_id"],
                        req_row["time_off_type_code"],
                        year,
                    ),
                )
            elif req_row["request_status"] == "Approved":
                new_available = balance_row["available_days"] + req_row["total_days"]
                new_used = balance_row["used_days"] - req_row["total_days"]
                conn.execute(
                    """
                    UPDATE tm_time_off_balance
                    SET available_days = ?, used_days = ?
                    WHERE person_id = ? AND time_off_type_code = ? AND year = ?
                    """,
                    (
                        new_available,
                        new_used,
                        req_row["person_id"],
                        req_row["time_off_type_code"],
                        year,
                    ),
                )

        conn.execute(
            "UPDATE tm_time_off_request SET request_status = 'Cancelled', last_modified_on = ? WHERE request_id = ?",
            (_now(), request_id),
        )
        row = conn.execute(
            "SELECT * FROM tm_time_off_request WHERE request_id = ?", (request_id,)
        ).fetchone()
    return _row_to_request(row)


# ── Timesheets ────────────────────────────────────────────────────────────────


def get_timesheet(person_id: str, week_start_date: str) -> Optional[Timesheet]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tm_timesheet WHERE person_id = ? AND week_start_date = ?",
            (person_id, week_start_date),
        ).fetchone()
    if row is None:
        return None
    return _row_to_timesheet(row)


def list_timesheets(person_id: str) -> List[Timesheet]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tm_timesheet WHERE person_id = ? ORDER BY week_start_date DESC",
            (person_id,),
        ).fetchall()
    return [_row_to_timesheet(r) for r in rows]


def create_timesheet(person_id, week_start_date) -> Timesheet:
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM per_person WHERE person_id = ?", (person_id,)
        ).fetchone():
            raise LookupError(f"Person '{person_id}' not found")

        parsed = datetime.date.fromisoformat(week_start_date)
        if parsed.weekday() != 0:
            raise ValueError(f"week_start_date must be a Monday (got {parsed.strftime('%A')})")

        existing = conn.execute(
            "SELECT 1 FROM tm_timesheet WHERE person_id = ? AND week_start_date = ?",
            (person_id, week_start_date),
        ).fetchone()
        if existing:
            raise ValueError(
                f"Timesheet already exists for person '{person_id}' and week '{week_start_date}'"
            )

        week_end_date = (parsed + datetime.timedelta(days=6)).isoformat()
        timesheet_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO tm_timesheet (
                timesheet_id, person_id, week_start_date, week_end_date,
                total_hours, regular_hours, overtime_hours, timesheet_status,
                created_on
            ) VALUES (?, ?, ?, ?, 0, 0, 0, 'Draft', ?)
            """,
            (timesheet_id, person_id, week_start_date, week_end_date, _now()),
        )
        row = conn.execute(
            "SELECT * FROM tm_timesheet WHERE timesheet_id = ?", (timesheet_id,)
        ).fetchone()
    return _row_to_timesheet(row)


def update_timesheet(timesheet_id, entries: list, submit=False) -> Timesheet:
    with get_conn() as conn:
        ts_row = conn.execute(
            "SELECT * FROM tm_timesheet WHERE timesheet_id = ?", (timesheet_id,)
        ).fetchone()
        if ts_row is None:
            raise LookupError(f"Timesheet '{timesheet_id}' not found")
        if ts_row["timesheet_status"] not in ("Draft", "Rejected"):
            raise ValueError(
                f"Can only update Draft or Rejected timesheets "
                f"(current status: {ts_row['timesheet_status']})"
            )

        week_start = datetime.date.fromisoformat(ts_row["week_start_date"])
        week_end = datetime.date.fromisoformat(ts_row["week_end_date"])

        for entry in entries:
            work_date = datetime.date.fromisoformat(entry["work_date"])
            if not (week_start <= work_date <= week_end):
                raise ValueError(
                    f"work_date {entry['work_date']} is outside the timesheet week "
                    f"({ts_row['week_start_date']} to {ts_row['week_end_date']})"
                )
            if entry["hours"] > 24:
                raise ValueError(
                    f"Cannot enter more than 24 hours for a single day (got {entry['hours']} on {entry['work_date']})"
                )

        conn.execute("DELETE FROM tm_timesheet_entry WHERE timesheet_id = ?", (timesheet_id,))

        daily_hours: dict = {}
        for entry in entries:
            day = entry["work_date"]
            daily_hours[day] = daily_hours.get(day, 0) + entry["hours"]
            conn.execute(
                """
                INSERT INTO tm_timesheet_entry
                    (timesheet_id, work_date, hours, project_code, task_code,
                     cost_center_code, comments)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timesheet_id,
                    day,
                    entry["hours"],
                    entry.get("project_code"),
                    entry.get("task_code"),
                    entry.get("cost_center_code"),
                    entry.get("comments"),
                ),
            )

        total_hours = sum(e["hours"] for e in entries)
        regular_hours = sum(min(day_total, 8.0) for day_total in daily_hours.values())
        overtime_hours = sum(max(day_total - 8.0, 0.0) for day_total in daily_hours.values())

        if submit:
            today = datetime.date.today().isoformat()
            conn.execute(
                """
                UPDATE tm_timesheet
                SET total_hours = ?, regular_hours = ?, overtime_hours = ?,
                    timesheet_status = 'Submitted', submitted_date = ?,
                    last_modified_on = ?
                WHERE timesheet_id = ?
                """,
                (total_hours, regular_hours, overtime_hours, today, _now(), timesheet_id),
            )
        else:
            conn.execute(
                """
                UPDATE tm_timesheet
                SET total_hours = ?, regular_hours = ?, overtime_hours = ?,
                    last_modified_on = ?
                WHERE timesheet_id = ?
                """,
                (total_hours, regular_hours, overtime_hours, _now(), timesheet_id),
            )

        row = conn.execute(
            "SELECT * FROM tm_timesheet WHERE timesheet_id = ?", (timesheet_id,)
        ).fetchone()
    return _row_to_timesheet(row)
