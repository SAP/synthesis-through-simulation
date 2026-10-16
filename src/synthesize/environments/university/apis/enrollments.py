"""
Course enrollment and waitlist API for the University environment.

Business rules enforced:
  - A student cannot enroll in a course they are already enrolled in
  - A student cannot be both enrolled and on the waitlist for the same course
  - Waitlisting is only allowed when a course is at full capacity
  - Dropping a course frees a seat and auto-promotes the top waitlisted student
  - Waitlist positions are unique per course; re-ranking assigns contiguous positions
  - Only active students can enroll
  - Only open courses accept new enrollments or waitlist entries
  - current_enrollment on course is kept in sync with active enrollment rows

Auto-managed fields: current_enrollment (on course), position (on waitlist),
                      dropped_date (on enrollment)
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional

from synthesize.environments.university.db.db import get_conn


def _today() -> str:
    return datetime.date.today().isoformat()


def _uid() -> str:
    return str(uuid.uuid4())[:8].upper()


# ── Student read ──────────────────────────────────────────────────────────────


def get_student(student_id: str) -> Dict[str, Any]:
    """Return a student record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM student WHERE student_id = ?", (student_id,)).fetchone()
    if row is None:
        raise LookupError(f"Student not found: {student_id!r}")
    return dict(row)


def get_student_by_name(name: str) -> List[Dict[str, Any]]:
    """Return students whose name matches (case-insensitive, partial match)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM student WHERE name LIKE ? ORDER BY student_id",
            (f"%{name}%",),
        ).fetchall()
    return [dict(r) for r in rows]


def list_students(enrollment_status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all students, optionally filtered by enrollment_status."""
    query = "SELECT * FROM student WHERE 1=1"
    params: list = []
    if enrollment_status is not None:
        query += " AND enrollment_status = ?"
        params.append(enrollment_status)
    query += " ORDER BY student_id"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ── Course read ───────────────────────────────────────────────────────────────


def get_course(course_id: str) -> Dict[str, Any]:
    """Return a course record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM course WHERE course_id = ?", (course_id,)).fetchone()
    if row is None:
        raise LookupError(f"Course not found: {course_id!r}")
    return dict(row)


def get_course_by_code(course_code: str) -> Dict[str, Any]:
    """Return a course by its course code.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM course WHERE course_code = ?", (course_code,)).fetchone()
    if row is None:
        raise LookupError(f"No course with code: {course_code!r}")
    return dict(row)


def list_courses(department: Optional[str] = None, is_open: Optional[bool] = None) -> List[Dict[str, Any]]:
    """Return courses, optionally filtered by department and/or open status."""
    query = "SELECT * FROM course WHERE 1=1"
    params: list = []
    if department is not None:
        query += " AND department = ?"
        params.append(department)
    if is_open is not None:
        query += " AND is_open = ?"
        params.append(1 if is_open else 0)
    query += " ORDER BY course_id"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def check_course_capacity(course_id: str) -> Dict[str, Any]:
    """Return capacity status for a course: available seats and whether it is full."""
    course = get_course(course_id)
    available = course["capacity"] - course["current_enrollment"]
    return {
        "course_id": course_id,
        "capacity": course["capacity"],
        "current_enrollment": course["current_enrollment"],
        "available_seats": available,
        "is_full": available <= 0,
        "is_open": bool(course["is_open"]),
    }


# ── Enrollment read ───────────────────────────────────────────────────────────


def get_enrollment_status(student_id: str, course_id: str) -> str:
    """Return enrollment status for a student/course pair: 'enrolled', 'dropped',
    'waitlisted', or 'not_enrolled'.
    """
    with get_conn() as conn:
        enr = conn.execute(
            "SELECT status FROM enrollment WHERE student_id = ? AND course_id = ?",
            (student_id, course_id),
        ).fetchone()
        if enr:
            return enr["status"]
        wl = conn.execute(
            "SELECT 1 FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_id, course_id),
        ).fetchone()
    return "waitlisted" if wl else "not_enrolled"


def list_student_enrollments(student_id: str) -> List[Dict[str, Any]]:
    """Return all enrollment records for a student."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM enrollment WHERE student_id = ? ORDER BY enrolled_date DESC",
            (student_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_course_enrollments(course_id: str) -> List[Dict[str, Any]]:
    """Return all active (enrolled) students in a course."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM enrollment WHERE course_id = ? AND status = 'enrolled' ORDER BY student_id",
            (course_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_course_waitlist(course_id: str) -> List[Dict[str, Any]]:
    """Return the waitlist for a course, ordered by position."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM waitlist WHERE course_id = ? ORDER BY position",
            (course_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_waitlist_position(student_id: str, course_id: str) -> Optional[int]:
    """Return the student's waitlist position for a course, or None if not waitlisted."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT position FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_id, course_id),
        ).fetchone()
    return row["position"] if row else None


# ── Enrollment write ──────────────────────────────────────────────────────────


def enroll_student(student_id: str, course_id: str) -> Dict[str, Any]:
    """Enroll a student in a course if a seat is available.

    Raises LookupError if student or course not found.
    Raises ValueError if:
      - student is not active
      - course is not open
      - course is at full capacity (use add_to_waitlist instead)
      - student is already enrolled or waitlisted
    """
    with get_conn() as conn:
        stu = conn.execute("SELECT enrollment_status FROM student WHERE student_id = ?", (student_id,)).fetchone()
        if stu is None:
            raise LookupError(f"Student not found: {student_id!r}")
        if stu["enrollment_status"] not in ("active",):
            raise ValueError(f"Student {student_id!r} is not active (status: {stu['enrollment_status']!r})")

        crs = conn.execute("SELECT * FROM course WHERE course_id = ?", (course_id,)).fetchone()
        if crs is None:
            raise LookupError(f"Course not found: {course_id!r}")
        if not crs["is_open"]:
            raise ValueError(f"Course {course_id!r} is not open for enrollment")
        if crs["current_enrollment"] >= crs["capacity"]:
            raise ValueError(
                f"Course {course_id!r} is full (capacity {crs['capacity']}). Use add_to_waitlist instead."
            )

        existing_enr = conn.execute(
            "SELECT status FROM enrollment WHERE student_id = ? AND course_id = ?",
            (student_id, course_id),
        ).fetchone()
        if existing_enr and existing_enr["status"] == "enrolled":
            raise ValueError(f"Student {student_id!r} is already enrolled in course {course_id!r}")

        existing_wl = conn.execute(
            "SELECT 1 FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_id, course_id),
        ).fetchone()
        if existing_wl:
            raise ValueError(f"Student {student_id!r} is on the waitlist for {course_id!r}; remove from waitlist first")

        enr_id = "ENR-" + _uid()
        today = _today()

        if existing_enr:
            # Re-enrolling after a drop — update existing row
            conn.execute(
                "UPDATE enrollment SET status = 'enrolled', enrolled_date = ?, dropped_date = NULL WHERE student_id = ? AND course_id = ?",
                (today, student_id, course_id),
            )
        else:
            conn.execute(
                """INSERT INTO enrollment (enrollment_id, student_id, course_id, status, enrolled_date, dropped_date)
                   VALUES (?, ?, ?, 'enrolled', ?, NULL)""",
                (enr_id, student_id, course_id, today),
            )
        conn.execute(
            "UPDATE course SET current_enrollment = current_enrollment + 1 WHERE course_id = ?",
            (course_id,),
        )
    return get_course(course_id)


def drop_student(student_id: str, course_id: str) -> Dict[str, Any]:
    """Drop a student from a course. Automatically promotes top waitlisted student.

    Raises LookupError if student or course not found.
    Raises ValueError if student is not enrolled.
    """
    with get_conn() as conn:
        stu = conn.execute("SELECT student_id FROM student WHERE student_id = ?", (student_id,)).fetchone()
        if stu is None:
            raise LookupError(f"Student not found: {student_id!r}")

        crs = conn.execute("SELECT course_id FROM course WHERE course_id = ?", (course_id,)).fetchone()
        if crs is None:
            raise LookupError(f"Course not found: {course_id!r}")

        enr = conn.execute(
            "SELECT status FROM enrollment WHERE student_id = ? AND course_id = ? AND status = 'enrolled'",
            (student_id, course_id),
        ).fetchone()
        if enr is None:
            raise ValueError(f"Student {student_id!r} is not enrolled in course {course_id!r}")

        today = _today()
        conn.execute(
            "UPDATE enrollment SET status = 'dropped', dropped_date = ? WHERE student_id = ? AND course_id = ?",
            (today, student_id, course_id),
        )
        conn.execute(
            "UPDATE course SET current_enrollment = current_enrollment - 1 WHERE course_id = ?",
            (course_id,),
        )

        # Auto-promote top waitlisted student
        top = conn.execute(
            "SELECT * FROM waitlist WHERE course_id = ? ORDER BY position LIMIT 1",
            (course_id,),
        ).fetchone()
        if top:
            promoted_student = top["student_id"]
            conn.execute(
                "DELETE FROM waitlist WHERE student_id = ? AND course_id = ?",
                (promoted_student, course_id),
            )
            # Re-rank remaining waitlist
            remaining = conn.execute(
                "SELECT waitlist_id FROM waitlist WHERE course_id = ? ORDER BY position",
                (course_id,),
            ).fetchall()
            for i, wl_row in enumerate(remaining, start=1):
                conn.execute(
                    "UPDATE waitlist SET position = ? WHERE waitlist_id = ?",
                    (i, wl_row["waitlist_id"]),
                )
            # Enroll the promoted student
            existing_enr = conn.execute(
                "SELECT enrollment_id FROM enrollment WHERE student_id = ? AND course_id = ?",
                (promoted_student, course_id),
            ).fetchone()
            if existing_enr:
                conn.execute(
                    "UPDATE enrollment SET status = 'enrolled', enrolled_date = ?, dropped_date = NULL WHERE student_id = ? AND course_id = ?",
                    (today, promoted_student, course_id),
                )
            else:
                conn.execute(
                    """INSERT INTO enrollment (enrollment_id, student_id, course_id, status, enrolled_date)
                       VALUES (?, ?, ?, 'enrolled', ?)""",
                    ("ENR-" + _uid(), promoted_student, course_id, today),
                )
            conn.execute(
                "UPDATE course SET current_enrollment = current_enrollment + 1 WHERE course_id = ?",
                (course_id,),
            )

    return get_course(course_id)


# ── Waitlist write ────────────────────────────────────────────────────────────


def add_to_waitlist(student_id: str, course_id: str) -> Dict[str, Any]:
    """Add a student to the waitlist for a full course.

    Raises LookupError if student or course not found.
    Raises ValueError if course is not full, student is enrolled, or already waitlisted.
    """
    with get_conn() as conn:
        stu = conn.execute("SELECT enrollment_status FROM student WHERE student_id = ?", (student_id,)).fetchone()
        if stu is None:
            raise LookupError(f"Student not found: {student_id!r}")
        if stu["enrollment_status"] not in ("active",):
            raise ValueError(f"Student {student_id!r} is not active")

        crs = conn.execute("SELECT * FROM course WHERE course_id = ?", (course_id,)).fetchone()
        if crs is None:
            raise LookupError(f"Course not found: {course_id!r}")
        if not crs["is_open"]:
            raise ValueError(f"Course {course_id!r} is not open")
        if crs["current_enrollment"] < crs["capacity"]:
            raise ValueError(
                f"Course {course_id!r} has {crs['capacity'] - crs['current_enrollment']} available seat(s). "
                f"Enroll directly instead of waitlisting."
            )

        existing_enr = conn.execute(
            "SELECT status FROM enrollment WHERE student_id = ? AND course_id = ? AND status = 'enrolled'",
            (student_id, course_id),
        ).fetchone()
        if existing_enr:
            raise ValueError(f"Student {student_id!r} is already enrolled in course {course_id!r}")

        existing_wl = conn.execute(
            "SELECT 1 FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_id, course_id),
        ).fetchone()
        if existing_wl:
            raise ValueError(f"Student {student_id!r} is already on the waitlist for {course_id!r}")

        max_pos = conn.execute(
            "SELECT COALESCE(MAX(position), 0) FROM waitlist WHERE course_id = ?", (course_id,)
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO waitlist (waitlist_id, student_id, course_id, position, added_date)
               VALUES (?, ?, ?, ?, ?)""",
            ("WL-" + _uid(), student_id, course_id, max_pos + 1, _today()),
        )
    return {"student_id": student_id, "course_id": course_id, "position": max_pos + 1}


def remove_from_waitlist(student_id: str, course_id: str) -> Dict[str, Any]:
    """Remove a student from the waitlist and re-rank remaining entries.

    Raises LookupError if not on waitlist.
    """
    with get_conn() as conn:
        wl = conn.execute(
            "SELECT position FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_id, course_id),
        ).fetchone()
        if wl is None:
            raise LookupError(f"Student {student_id!r} is not on the waitlist for {course_id!r}")

        removed_pos = wl["position"]
        conn.execute(
            "DELETE FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_id, course_id),
        )
        conn.execute(
            "UPDATE waitlist SET position = position - 1 WHERE course_id = ? AND position > ?",
            (course_id, removed_pos),
        )
    return {"student_id": student_id, "course_id": course_id, "removed_from_position": removed_pos}


def update_waitlist_priority(student_id: str, course_id: str, new_position: int) -> Dict[str, Any]:
    """Move a student to a new waitlist position, shifting others as needed.

    Raises LookupError if student not on waitlist.
    Raises ValueError if new_position is out of range.
    """
    with get_conn() as conn:
        wl = conn.execute(
            "SELECT position FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_id, course_id),
        ).fetchone()
        if wl is None:
            raise LookupError(f"Student {student_id!r} is not on the waitlist for {course_id!r}")

        total = conn.execute(
            "SELECT COUNT(*) FROM waitlist WHERE course_id = ?", (course_id,)
        ).fetchone()[0]
        if new_position < 1 or new_position > total:
            raise ValueError(f"new_position must be between 1 and {total}, got {new_position}")

        old_pos = wl["position"]
        if old_pos == new_position:
            return get_course_waitlist(course_id)[new_position - 1]

        if new_position < old_pos:
            conn.execute(
                "UPDATE waitlist SET position = position + 1 WHERE course_id = ? AND position >= ? AND position < ?",
                (course_id, new_position, old_pos),
            )
        else:
            conn.execute(
                "UPDATE waitlist SET position = position - 1 WHERE course_id = ? AND position > ? AND position <= ?",
                (course_id, old_pos, new_position),
            )
        conn.execute(
            "UPDATE waitlist SET position = ? WHERE student_id = ? AND course_id = ?",
            (new_position, student_id, course_id),
        )
    return get_course_waitlist(course_id)[new_position - 1]


def clear_waitlist(course_id: str) -> Dict[str, Any]:
    """Remove all entries from a course's waitlist.

    Raises LookupError if course not found.
    """
    with get_conn() as conn:
        crs = conn.execute("SELECT course_id FROM course WHERE course_id = ?", (course_id,)).fetchone()
        if crs is None:
            raise LookupError(f"Course not found: {course_id!r}")
        count = conn.execute(
            "SELECT COUNT(*) FROM waitlist WHERE course_id = ?", (course_id,)
        ).fetchone()[0]
        conn.execute("DELETE FROM waitlist WHERE course_id = ?", (course_id,))
    return {"course_id": course_id, "removed_entries": count}
