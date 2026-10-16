"""
Employee read-only API for IT Service Management environment.
"""

from __future__ import annotations

from typing import Any, Dict, List

from synthesize.environments.it_management.db.db import get_conn


def list_employees() -> List[Dict[str, Any]]:
    """Return all active employees (emp_id, name, email, category, level)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT emp_id, name, email, category, level FROM employee WHERE is_active = 1 ORDER BY emp_id"
        ).fetchall()
    return [dict(r) for r in rows]


def list_it_staff() -> List[Dict[str, Any]]:
    """Return all active IT-category employees (eligible ticket assignees)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT emp_id, name, email, level FROM employee WHERE category = 'IT' AND is_active = 1 ORDER BY emp_id"
        ).fetchall()
    return [dict(r) for r in rows]


def get_employee(emp_id: str) -> Dict[str, Any]:
    """Return full record for a single employee.

    Raises LookupError if emp_id not found.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT emp_id, name, email, category, level, salary, doj, is_active FROM employee WHERE emp_id = ?",
            (emp_id,),
        ).fetchone()
    if row is None:
        raise LookupError(f"Employee not found: {emp_id!r}")
    return dict(row)


def get_employee_by_email(email: str) -> Dict[str, Any]:
    """Return the employee record (emp_id, name) for the given email address.

    Raises LookupError if email not found.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT emp_id, name FROM employee WHERE email = ?", (email.lower(),)
        ).fetchone()
    if row is None:
        raise LookupError(f"No employee found with email: {email!r}")
    return dict(row)
