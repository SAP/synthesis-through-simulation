"""
Prescription management API for the Pharmacy environment.

Business rules enforced:
  - status must be one of: pending, filled, on_hold, cancelled, expired
  - date_filled is set only when status becomes 'filled'; cleared on 'on_hold'
  - Cannot fill a cancelled or expired prescription
  - Cannot cancel a filled prescription (must put on_hold first)
  - refills_remaining must be ≥ 0
  - All FK references (patient, physician, medication) must point to active records
  - Instructions and dosage must be non-empty

Auto-managed fields: date_filled (set/cleared by status transitions)
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional

from synthesize.environments.pharmacy.db.db import get_conn

VALID_STATUSES = {"pending", "filled", "on_hold", "cancelled", "expired"}


def _today() -> str:
    return datetime.date.today().isoformat()


def _rx_id() -> str:
    return "RX-" + str(uuid.uuid4())[:8].upper()


# ── Read ──────────────────────────────────────────────────────────────────────


def get_prescription(prescription_id: str) -> Dict[str, Any]:
    """Return a single prescription record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM prescription WHERE prescription_id = ?", (prescription_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"Prescription not found: {prescription_id!r}")
    return dict(row)


def list_prescriptions_for_patient(patient_id: str) -> List[Dict[str, Any]]:
    """Return all prescriptions for a patient, newest first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM prescription WHERE patient_id = ? ORDER BY date_issued DESC",
            (patient_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_prescriptions_by_physician(physician_id: str) -> List[Dict[str, Any]]:
    """Return all prescriptions issued by a physician."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM prescription WHERE physician_id = ? ORDER BY date_issued DESC",
            (physician_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_prescriptions_by_status(status: str) -> List[Dict[str, Any]]:
    """Return all prescriptions with the given status.

    Raises ValueError for invalid status.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}, got {status!r}")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM prescription WHERE status = ? ORDER BY date_issued DESC",
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_prescriptions_for_medication(medication_id: str) -> List[Dict[str, Any]]:
    """Return all prescriptions for a specific medication."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM prescription WHERE medication_id = ? ORDER BY date_issued DESC",
            (medication_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Write ─────────────────────────────────────────────────────────────────────


def create_prescription(
    patient_id: str,
    physician_id: str,
    medication_id: str,
    dosage: str,
    instructions: str,
    refills_remaining: int = 0,
    pharmacy_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Issue a new prescription.

    Raises LookupError if patient, physician, or medication not found.
    Raises ValueError for invalid inputs.
    """
    if not dosage or not dosage.strip():
        raise ValueError("dosage must be non-empty")
    if not instructions or not instructions.strip():
        raise ValueError("instructions must be non-empty")
    if refills_remaining < 0:
        raise ValueError(f"refills_remaining cannot be negative, got {refills_remaining}")

    with get_conn() as conn:
        pat = conn.execute("SELECT is_active FROM patient WHERE patient_id = ?", (patient_id,)).fetchone()
        if pat is None:
            raise LookupError(f"Patient not found: {patient_id!r}")
        if not pat["is_active"]:
            raise ValueError(f"Patient {patient_id!r} is not active")

        phy = conn.execute("SELECT is_active FROM physician WHERE physician_id = ?", (physician_id,)).fetchone()
        if phy is None:
            raise LookupError(f"Physician not found: {physician_id!r}")
        if not phy["is_active"]:
            raise ValueError(f"Physician {physician_id!r} is not active")

        med = conn.execute("SELECT is_active FROM medication WHERE medication_id = ?", (medication_id,)).fetchone()
        if med is None:
            raise LookupError(f"Medication not found: {medication_id!r}")
        if not med["is_active"]:
            raise ValueError(f"Medication {medication_id!r} is not active")

        rx_id = _rx_id()
        conn.execute(
            """INSERT INTO prescription
               (prescription_id, patient_id, physician_id, medication_id, dosage, instructions,
                date_issued, date_filled, status, pharmacy_notes, refills_remaining)
               VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'pending', ?, ?)""",
            (rx_id, patient_id, physician_id, medication_id, dosage.strip(), instructions.strip(),
             _today(), pharmacy_notes, refills_remaining),
        )
    return get_prescription(rx_id)


def fill_prescription(prescription_id: str, pharmacy_notes: Optional[str] = None) -> Dict[str, Any]:
    """Mark a prescription as filled and set date_filled to today.

    Raises LookupError if not found.
    Raises ValueError if status is not 'pending' or 'on_hold'.
    """
    with get_conn() as conn:
        rx = conn.execute(
            "SELECT status FROM prescription WHERE prescription_id = ?", (prescription_id,)
        ).fetchone()
        if rx is None:
            raise LookupError(f"Prescription not found: {prescription_id!r}")
        if rx["status"] not in ("pending", "on_hold"):
            raise ValueError(
                f"Cannot fill prescription {prescription_id!r}: status is {rx['status']!r} "
                f"(must be 'pending' or 'on_hold')"
            )
        updates = "status = 'filled', date_filled = ?"
        values: list = [_today()]
        if pharmacy_notes is not None:
            updates += ", pharmacy_notes = ?"
            values.append(pharmacy_notes)
        values.append(prescription_id)
        conn.execute(f"UPDATE prescription SET {updates} WHERE prescription_id = ?", values)
    return get_prescription(prescription_id)


def put_on_hold(prescription_id: str, pharmacy_notes: Optional[str] = None) -> Dict[str, Any]:
    """Put a pending or filled prescription on hold. Clears date_filled.

    Raises LookupError if not found.
    Raises ValueError if status is not 'pending' or 'filled'.
    """
    with get_conn() as conn:
        rx = conn.execute(
            "SELECT status FROM prescription WHERE prescription_id = ?", (prescription_id,)
        ).fetchone()
        if rx is None:
            raise LookupError(f"Prescription not found: {prescription_id!r}")
        if rx["status"] not in ("pending", "filled"):
            raise ValueError(
                f"Cannot put prescription {prescription_id!r} on hold: status is {rx['status']!r}"
            )
        updates = "status = 'on_hold', date_filled = NULL"
        values: list = []
        if pharmacy_notes is not None:
            updates += ", pharmacy_notes = ?"
            values.append(pharmacy_notes)
        values.append(prescription_id)
        conn.execute(f"UPDATE prescription SET {updates} WHERE prescription_id = ?", values)
    return get_prescription(prescription_id)


def cancel_prescription(prescription_id: str, pharmacy_notes: Optional[str] = None) -> Dict[str, Any]:
    """Cancel a pending or on-hold prescription.

    Raises LookupError if not found.
    Raises ValueError if status is 'filled', 'cancelled', or 'expired'.
    """
    with get_conn() as conn:
        rx = conn.execute(
            "SELECT status FROM prescription WHERE prescription_id = ?", (prescription_id,)
        ).fetchone()
        if rx is None:
            raise LookupError(f"Prescription not found: {prescription_id!r}")
        if rx["status"] not in ("pending", "on_hold"):
            raise ValueError(
                f"Cannot cancel prescription {prescription_id!r}: status is {rx['status']!r} "
                f"(must be 'pending' or 'on_hold')"
            )
        updates = "status = 'cancelled'"
        values: list = []
        if pharmacy_notes is not None:
            updates += ", pharmacy_notes = ?"
            values.append(pharmacy_notes)
        values.append(prescription_id)
        conn.execute(f"UPDATE prescription SET {updates} WHERE prescription_id = ?", values)
    return get_prescription(prescription_id)


def expire_prescription(prescription_id: str) -> Dict[str, Any]:
    """Mark a pending or on-hold prescription as expired.

    Raises LookupError if not found.
    Raises ValueError if status is not 'pending' or 'on_hold'.
    """
    with get_conn() as conn:
        rx = conn.execute(
            "SELECT status FROM prescription WHERE prescription_id = ?", (prescription_id,)
        ).fetchone()
        if rx is None:
            raise LookupError(f"Prescription not found: {prescription_id!r}")
        if rx["status"] not in ("pending", "on_hold"):
            raise ValueError(
                f"Cannot expire prescription {prescription_id!r}: status is {rx['status']!r}"
            )
        conn.execute(
            "UPDATE prescription SET status = 'expired' WHERE prescription_id = ?",
            (prescription_id,),
        )
    return get_prescription(prescription_id)


def update_prescription_instructions(
    prescription_id: str,
    instructions: str,
    dosage: Optional[str] = None,
) -> Dict[str, Any]:
    """Update dosage or instructions on a pending or on-hold prescription.

    Raises LookupError if not found.
    Raises ValueError if prescription is filled, cancelled, or expired.
    """
    if not instructions or not instructions.strip():
        raise ValueError("instructions must be non-empty")

    with get_conn() as conn:
        rx = conn.execute(
            "SELECT status FROM prescription WHERE prescription_id = ?", (prescription_id,)
        ).fetchone()
        if rx is None:
            raise LookupError(f"Prescription not found: {prescription_id!r}")
        if rx["status"] not in ("pending", "on_hold"):
            raise ValueError(
                f"Cannot modify prescription {prescription_id!r}: status is {rx['status']!r}"
            )
        updates = "instructions = ?"
        values: list = [instructions.strip()]
        if dosage is not None:
            if not dosage.strip():
                raise ValueError("dosage must be non-empty")
            updates += ", dosage = ?"
            values.append(dosage.strip())
        values.append(prescription_id)
        conn.execute(f"UPDATE prescription SET {updates} WHERE prescription_id = ?", values)
    return get_prescription(prescription_id)


def get_patient(patient_id: str) -> Dict[str, Any]:
    """Return a patient record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM patient WHERE patient_id = ?", (patient_id,)).fetchone()
    if row is None:
        raise LookupError(f"Patient not found: {patient_id!r}")
    return dict(row)


def list_patients() -> List[Dict[str, Any]]:
    """Return all active patients."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM patient WHERE is_active = 1 ORDER BY patient_id"
        ).fetchall()
    return [dict(r) for r in rows]


def get_physician(physician_id: str) -> Dict[str, Any]:
    """Return a physician record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM physician WHERE physician_id = ?", (physician_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"Physician not found: {physician_id!r}")
    return dict(row)


def list_physicians() -> List[Dict[str, Any]]:
    """Return all active physicians."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM physician WHERE is_active = 1 ORDER BY physician_id"
        ).fetchall()
    return [dict(r) for r in rows]


def get_medication(medication_id: str) -> Dict[str, Any]:
    """Return a medication record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM medication WHERE medication_id = ?", (medication_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"Medication not found: {medication_id!r}")
    return dict(row)


def list_medications(classification: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all active medications, optionally filtered by classification."""
    query = "SELECT * FROM medication WHERE is_active = 1"
    params: list = []
    if classification is not None:
        query += " AND classification = ?"
        params.append(classification)
    query += " ORDER BY medication_id"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]
