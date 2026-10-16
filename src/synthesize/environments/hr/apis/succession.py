import datetime
import uuid
from typing import List, Optional

from synthesize.environments.hr.db.db import get_conn
from synthesize.environments.hr.db.models import (
    Nominee,
    SuccessionPlan,
    TalentPool,
    TalentPoolMember,
)


def TODAY():
    return datetime.date.today().isoformat()


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(sep=" ", timespec="seconds")


VALID_READINESS = {"Ready Now", "1-2 Years", "3+ Years"}
VALID_POOL_TYPES = {"High Potential", "Leadership Pipeline", "Technical Expert"}
VALID_POTENTIAL_RATINGS = {"High", "Medium", "Low"}


# ── Internal helpers ──────────────────────────────────────────────────────────


def _row_to_plan(row) -> SuccessionPlan:
    return SuccessionPlan(
        plan_id=row["plan_id"],
        position_id=row["position_id"],
        incumbent_person_id=row["incumbent_person_id"],
        risk_of_loss=row["risk_of_loss"],
        time_to_replacement_months=row["time_to_replacement_months"],
        plan_status=row["plan_status"],
        last_review_date=row["last_review_date"],
        next_review_date=row["next_review_date"],
    )


def _row_to_nominee(row) -> Nominee:
    return Nominee(
        nominee_id=row["nominee_id"],
        plan_id=row["plan_id"],
        nominee_person_id=row["nominee_person_id"],
        readiness=row["readiness"],
        readiness_percentage=row["readiness_percentage"],
        rank=row["rank"],
        development_needs=row["development_needs"],
        status=row["status"],
    )


def _row_to_talent_pool(row) -> TalentPool:
    return TalentPool(
        talent_pool_id=row["talent_pool_id"],
        pool_name=row["pool_name"],
        pool_description=row["pool_description"],
        pool_type=row["pool_type"],
    )


def _row_to_pool_member(row) -> TalentPoolMember:
    return TalentPoolMember(
        member_id=row["member_id"],
        talent_pool_id=row["talent_pool_id"],
        person_id=row["person_id"],
        added_date=row["added_date"],
        status=row["status"],
        performance_rating=row["performance_rating"],
        potential_rating=row["potential_rating"],
    )


def _get_pay_grade_order(conn) -> dict:
    rows = conn.execute(
        "SELECT pay_grade_code, rowid FROM fod_pay_grade ORDER BY pay_grade_code"
    ).fetchall()
    return {row["pay_grade_code"]: idx for idx, row in enumerate(rows)}


def _check_readiness_grade(conn, nominee_person_id: str, position_id: str):
    nominee_job = conn.execute(
        "SELECT pay_grade FROM emp_job WHERE person_id=? AND end_date IS NULL AND employment_status='Active' LIMIT 1",
        (nominee_person_id,),
    ).fetchone()
    if not nominee_job or not nominee_job["pay_grade"]:
        return

    position = conn.execute(
        "SELECT job_code FROM fod_position WHERE position_id=?", (position_id,)
    ).fetchone()
    if not position or not position["job_code"]:
        return

    job_code = position["job_code"]
    max_grade_row = conn.execute(
        """
        SELECT ej.pay_grade
        FROM emp_job ej
        WHERE ej.job_code=? AND ej.end_date IS NULL AND ej.employment_status='Active'
          AND ej.pay_grade IS NOT NULL
        ORDER BY ej.pay_grade DESC
        LIMIT 1
        """,
        (job_code,),
    ).fetchone()
    if not max_grade_row:
        return

    grade_order = _get_pay_grade_order(conn)
    nominee_grade = nominee_job["pay_grade"]
    position_max_grade = max_grade_row["pay_grade"]

    if nominee_grade not in grade_order or position_max_grade not in grade_order:
        return

    nominee_idx = grade_order[nominee_grade]
    position_idx = grade_order[position_max_grade]

    if position_idx - nominee_idx > 1:
        raise ValueError(
            f"Nominee pay grade '{nominee_grade}' is more than 1 grade step below "
            f"the position's required grade '{position_max_grade}'; "
            f"cannot mark readiness as 'Ready Now'."
        )


# ── Succession Plans ──────────────────────────────────────────────────────────


def list_plans(status: Optional[str] = None, critical_only: bool = False) -> List[SuccessionPlan]:
    with get_conn() as conn:
        query = """
            SELECT sp.*
            FROM suc_succession_plan sp
            JOIN fod_position fp ON sp.position_id = fp.position_id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND sp.plan_status=?"
            params.append(status)
        if critical_only:
            query += " AND fp.critical_position=1"
        rows = conn.execute(query, params).fetchall()
        return [_row_to_plan(r) for r in rows]


def get_plan(plan_id: str) -> SuccessionPlan:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM suc_succession_plan WHERE plan_id=?", (plan_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Succession plan '{plan_id}' not found.")
        return _row_to_plan(row)


def create_plan(
    position_id: str,
    incumbent_person_id: Optional[str] = None,
    risk_of_loss: Optional[str] = None,
    time_to_replacement_months: Optional[int] = None,
) -> SuccessionPlan:
    with get_conn() as conn:
        position = conn.execute(
            "SELECT position_id FROM fod_position WHERE position_id=?", (position_id,)
        ).fetchone()
        if not position:
            raise ValueError(f"Position '{position_id}' does not exist.")

        if incumbent_person_id:
            person = conn.execute(
                "SELECT person_id FROM per_person WHERE person_id=?", (incumbent_person_id,)
            ).fetchone()
            if not person:
                raise ValueError(f"Person '{incumbent_person_id}' does not exist.")

        existing = conn.execute(
            "SELECT plan_id FROM suc_succession_plan WHERE position_id=? AND plan_status='Active'",
            (position_id,),
        ).fetchone()
        if existing:
            raise ValueError(
                f"An Active succession plan already exists for position '{position_id}' "
                f"(plan_id='{existing['plan_id']}')."
            )

        plan_id = str(uuid.uuid4())
        today = TODAY()
        conn.execute(
            """
            INSERT INTO suc_succession_plan
              (plan_id, position_id, incumbent_person_id, risk_of_loss,
               time_to_replacement_months, plan_status, last_review_date, next_review_date,
               created_on)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                plan_id,
                position_id,
                incumbent_person_id,
                risk_of_loss,
                time_to_replacement_months,
                "Active",
                today,
                None,
                _now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM suc_succession_plan WHERE plan_id=?", (plan_id,)
        ).fetchone()
        return _row_to_plan(row)


def update_plan(
    plan_id: str,
    risk_of_loss: Optional[str] = None,
    time_to_replacement_months: Optional[int] = None,
    plan_status: Optional[str] = None,
    next_review_date: Optional[str] = None,
) -> SuccessionPlan:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM suc_succession_plan WHERE plan_id=?", (plan_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Succession plan '{plan_id}' not found.")

        if row["plan_status"] == "Inactive" and plan_status == "Active":
            raise ValueError("Cannot reactivate an Inactive succession plan.")

        updates = {"last_review_date": TODAY()}
        if risk_of_loss is not None:
            updates["risk_of_loss"] = risk_of_loss
        if time_to_replacement_months is not None:
            updates["time_to_replacement_months"] = time_to_replacement_months
        if plan_status is not None:
            updates["plan_status"] = plan_status
        if next_review_date is not None:
            updates["next_review_date"] = next_review_date

        set_clause = ", ".join(f"{k}=?" for k in updates) + ", last_modified_on=?"
        conn.execute(
            f"UPDATE suc_succession_plan SET {set_clause} WHERE plan_id=?",
            list(updates.values()) + [_now(), plan_id],
        )
        row = conn.execute(
            "SELECT * FROM suc_succession_plan WHERE plan_id=?", (plan_id,)
        ).fetchone()
        return _row_to_plan(row)


# ── Nominees ──────────────────────────────────────────────────────────────────


def list_nominees(plan_id: str) -> List[Nominee]:
    with get_conn() as conn:
        plan = conn.execute(
            "SELECT plan_id FROM suc_succession_plan WHERE plan_id=?", (plan_id,)
        ).fetchone()
        if not plan:
            raise LookupError(f"Succession plan '{plan_id}' not found.")
        rows = conn.execute("SELECT * FROM suc_nominee WHERE plan_id=?", (plan_id,)).fetchall()
        return [_row_to_nominee(r) for r in rows]


def add_nominee(
    plan_id: str,
    nominee_person_id: str,
    readiness: str,
    readiness_percentage: Optional[int] = None,
    rank: Optional[int] = None,
    development_needs: Optional[str] = None,
) -> Nominee:
    with get_conn() as conn:
        plan = conn.execute(
            "SELECT * FROM suc_succession_plan WHERE plan_id=?", (plan_id,)
        ).fetchone()
        if not plan:
            raise LookupError(f"Succession plan '{plan_id}' not found.")
        if plan["plan_status"] != "Active":
            raise ValueError(f"Succession plan '{plan_id}' is not Active.")

        person = conn.execute(
            "SELECT person_id FROM per_person WHERE person_id=?", (nominee_person_id,)
        ).fetchone()
        if not person:
            raise ValueError(f"Person '{nominee_person_id}' does not exist.")

        if plan["incumbent_person_id"] and plan["incumbent_person_id"] == nominee_person_id:
            raise ValueError(f"Person '{nominee_person_id}' is already the incumbent of this plan.")

        existing_nomination = conn.execute(
            "SELECT nominee_id FROM suc_nominee WHERE plan_id=? AND nominee_person_id=? AND status='Active'",
            (plan_id, nominee_person_id),
        ).fetchone()
        if existing_nomination:
            raise ValueError(
                f"Person '{nominee_person_id}' is already an Active nominee on plan '{plan_id}'."
            )

        if readiness not in VALID_READINESS:
            raise ValueError(
                f"Invalid readiness '{readiness}'. Must be one of: {sorted(VALID_READINESS)}."
            )

        if readiness == "Ready Now":
            _check_readiness_grade(conn, nominee_person_id, plan["position_id"])

        if rank is None:
            max_rank_row = conn.execute(
                "SELECT MAX(rank) AS max_rank FROM suc_nominee WHERE plan_id=? AND status='Active'",
                (plan_id,),
            ).fetchone()
            rank = (max_rank_row["max_rank"] or 0) + 1

        today = TODAY()
        conn.execute(
            """
            INSERT INTO suc_nominee
              (plan_id, nominee_person_id, readiness, readiness_percentage,
               rank, development_needs, nomination_date, status, created_on)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                plan_id,
                nominee_person_id,
                readiness,
                readiness_percentage,
                rank,
                development_needs,
                today,
                "Active",
                _now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM suc_nominee WHERE nominee_id=last_insert_rowid()"
        ).fetchone()
        return _row_to_nominee(row)


def update_nominee(
    plan_id: str,
    nominee_id: int,
    readiness: Optional[str] = None,
    readiness_percentage: Optional[int] = None,
    rank: Optional[int] = None,
    development_needs: Optional[str] = None,
    status: Optional[str] = None,
) -> Nominee:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM suc_nominee WHERE nominee_id=?", (nominee_id,)).fetchone()
        if not row:
            raise LookupError(f"Nominee '{nominee_id}' not found.")
        if row["plan_id"] != plan_id:
            raise ValueError(f"Nominee '{nominee_id}' does not belong to plan '{plan_id}'.")

        if readiness is not None and readiness not in VALID_READINESS:
            raise ValueError(
                f"Invalid readiness '{readiness}'. Must be one of: {sorted(VALID_READINESS)}."
            )

        if readiness == "Ready Now":
            plan = conn.execute(
                "SELECT position_id FROM suc_succession_plan WHERE plan_id=?", (plan_id,)
            ).fetchone()
            _check_readiness_grade(conn, row["nominee_person_id"], plan["position_id"])

        updates = {}
        if readiness is not None:
            updates["readiness"] = readiness
        if readiness_percentage is not None:
            updates["readiness_percentage"] = readiness_percentage
        if rank is not None:
            updates["rank"] = rank
        if development_needs is not None:
            updates["development_needs"] = development_needs
        if status is not None:
            updates["status"] = status

        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates) + ", last_modified_on=?"
            conn.execute(
                f"UPDATE suc_nominee SET {set_clause} WHERE nominee_id=?",
                list(updates.values()) + [_now(), nominee_id],
            )

        row = conn.execute("SELECT * FROM suc_nominee WHERE nominee_id=?", (nominee_id,)).fetchone()
        return _row_to_nominee(row)


# ── Talent Pools ──────────────────────────────────────────────────────────────


def list_talent_pools() -> List[TalentPool]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM suc_talent_pool").fetchall()
        return [_row_to_talent_pool(r) for r in rows]


def get_talent_pool(talent_pool_id: str) -> TalentPool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM suc_talent_pool WHERE talent_pool_id=?", (talent_pool_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Talent pool '{talent_pool_id}' not found.")
        return _row_to_talent_pool(row)


def create_talent_pool(
    pool_name: str,
    pool_type: str,
    pool_description: Optional[str] = None,
) -> TalentPool:
    with get_conn() as conn:
        if pool_type not in VALID_POOL_TYPES:
            raise ValueError(
                f"Invalid pool_type '{pool_type}'. Must be one of: {sorted(VALID_POOL_TYPES)}."
            )

        existing = conn.execute(
            "SELECT talent_pool_id FROM suc_talent_pool WHERE pool_name=?", (pool_name,)
        ).fetchone()
        if existing:
            raise ValueError(f"A talent pool named '{pool_name}' already exists.")

        talent_pool_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO suc_talent_pool (talent_pool_id, pool_name, pool_description, pool_type, created_on) VALUES (?,?,?,?,?)",
            (talent_pool_id, pool_name, pool_description, pool_type, _now()),
        )
        row = conn.execute(
            "SELECT * FROM suc_talent_pool WHERE talent_pool_id=?", (talent_pool_id,)
        ).fetchone()
        return _row_to_talent_pool(row)


def update_talent_pool(
    talent_pool_id: str,
    pool_name: Optional[str] = None,
    pool_description: Optional[str] = None,
) -> TalentPool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM suc_talent_pool WHERE talent_pool_id=?", (talent_pool_id,)
        ).fetchone()
        if not row:
            raise LookupError(f"Talent pool '{talent_pool_id}' not found.")

        updates = {}
        if pool_name is not None:
            existing = conn.execute(
                "SELECT talent_pool_id FROM suc_talent_pool WHERE pool_name=? AND talent_pool_id!=?",
                (pool_name, talent_pool_id),
            ).fetchone()
            if existing:
                raise ValueError(f"A talent pool named '{pool_name}' already exists.")
            updates["pool_name"] = pool_name
        if pool_description is not None:
            updates["pool_description"] = pool_description

        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates)
            conn.execute(
                f"UPDATE suc_talent_pool SET {set_clause} WHERE talent_pool_id=?",
                list(updates.values()) + [talent_pool_id],
            )

        row = conn.execute(
            "SELECT * FROM suc_talent_pool WHERE talent_pool_id=?", (talent_pool_id,)
        ).fetchone()
        return _row_to_talent_pool(row)


# ── Talent Pool Members ───────────────────────────────────────────────────────


def list_pool_members(talent_pool_id: str) -> List[TalentPoolMember]:
    with get_conn() as conn:
        pool = conn.execute(
            "SELECT talent_pool_id FROM suc_talent_pool WHERE talent_pool_id=?", (talent_pool_id,)
        ).fetchone()
        if not pool:
            raise LookupError(f"Talent pool '{talent_pool_id}' not found.")
        rows = conn.execute(
            "SELECT * FROM suc_talent_pool_member WHERE talent_pool_id=?", (talent_pool_id,)
        ).fetchall()
        return [_row_to_pool_member(r) for r in rows]


def add_pool_member(
    talent_pool_id: str,
    person_id: str,
    performance_rating: Optional[str] = None,
    potential_rating: Optional[str] = None,
    added_by_person_id: Optional[str] = None,
) -> TalentPoolMember:
    with get_conn() as conn:
        pool = conn.execute(
            "SELECT talent_pool_id FROM suc_talent_pool WHERE talent_pool_id=?", (talent_pool_id,)
        ).fetchone()
        if not pool:
            raise LookupError(f"Talent pool '{talent_pool_id}' not found.")

        person = conn.execute(
            "SELECT person_id FROM per_person WHERE person_id=?", (person_id,)
        ).fetchone()
        if not person:
            raise ValueError(f"Person '{person_id}' does not exist.")

        existing = conn.execute(
            "SELECT member_id FROM suc_talent_pool_member WHERE talent_pool_id=? AND person_id=? AND status='Active'",
            (talent_pool_id, person_id),
        ).fetchone()
        if existing:
            raise ValueError(
                f"Person '{person_id}' is already an Active member of talent pool '{talent_pool_id}'."
            )

        if potential_rating is not None and potential_rating not in VALID_POTENTIAL_RATINGS:
            raise ValueError(
                f"Invalid potential_rating '{potential_rating}'. Must be one of: {sorted(VALID_POTENTIAL_RATINGS)}."
            )

        today = TODAY()
        conn.execute(
            """
            INSERT INTO suc_talent_pool_member
              (talent_pool_id, person_id, added_date, added_by_person_id,
               status, performance_rating, potential_rating, created_on)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                talent_pool_id,
                person_id,
                today,
                added_by_person_id,
                "Active",
                performance_rating,
                potential_rating,
                _now(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM suc_talent_pool_member WHERE member_id=last_insert_rowid()"
        ).fetchone()
        return _row_to_pool_member(row)


def update_pool_member(
    talent_pool_id: str,
    person_id: str,
    performance_rating: Optional[str] = None,
    potential_rating: Optional[str] = None,
    status: Optional[str] = None,
) -> TalentPoolMember:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM suc_talent_pool_member WHERE talent_pool_id=? AND person_id=? AND status='Active'",
            (talent_pool_id, person_id),
        ).fetchone()
        if not row:
            raise LookupError(
                f"Active member record for person '{person_id}' in pool '{talent_pool_id}' not found."
            )

        if potential_rating is not None and potential_rating not in VALID_POTENTIAL_RATINGS:
            raise ValueError(
                f"Invalid potential_rating '{potential_rating}'. Must be one of: {sorted(VALID_POTENTIAL_RATINGS)}."
            )

        updates = {}
        if performance_rating is not None:
            updates["performance_rating"] = performance_rating
        if potential_rating is not None:
            updates["potential_rating"] = potential_rating
        if status is not None:
            updates["status"] = status

        if status == "Promoted":
            nominations = conn.execute(
                "SELECT sn.plan_id FROM suc_nominee sn WHERE sn.nominee_person_id=? AND sn.status='Active'",
                (person_id,),
            ).fetchall()
            if nominations:
                plan_ids = [n["plan_id"] for n in nominations]
                print(
                    f"[INFO] Person '{person_id}' is an Active nominee on plan(s): {plan_ids}. "
                    f"Consider updating those nominations as well."
                )

        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates)
            conn.execute(
                f"UPDATE suc_talent_pool_member SET {set_clause} WHERE member_id=?",
                list(updates.values()) + [row["member_id"]],
            )

        row = conn.execute(
            "SELECT * FROM suc_talent_pool_member WHERE member_id=?", (row["member_id"],)
        ).fetchone()
        return _row_to_pool_member(row)


# ── Employee Nominations ──────────────────────────────────────────────────────


def list_employee_nominations(person_id: str) -> List[dict]:
    with get_conn() as conn:
        person = conn.execute(
            "SELECT person_id FROM per_person WHERE person_id=?", (person_id,)
        ).fetchone()
        if not person:
            raise LookupError(f"Person '{person_id}' not found.")

        rows = conn.execute(
            """
            SELECT
                sn.nominee_id, sn.plan_id, sn.nominee_person_id, sn.readiness,
                sn.readiness_percentage, sn.rank, sn.development_needs, sn.status,
                sp.position_id, sp.incumbent_person_id, sp.risk_of_loss,
                sp.time_to_replacement_months, sp.plan_status,
                sp.last_review_date, sp.next_review_date,
                fp.position_title
            FROM suc_nominee sn
            JOIN suc_succession_plan sp ON sn.plan_id = sp.plan_id
            JOIN fod_position fp ON sp.position_id = fp.position_id
            WHERE sn.nominee_person_id=?
            """,
            (person_id,),
        ).fetchall()

        results = []
        for r in rows:
            plan = SuccessionPlan(
                plan_id=r["plan_id"],
                position_id=r["position_id"],
                incumbent_person_id=r["incumbent_person_id"],
                risk_of_loss=r["risk_of_loss"],
                time_to_replacement_months=r["time_to_replacement_months"],
                plan_status=r["plan_status"],
                last_review_date=r["last_review_date"],
                next_review_date=r["next_review_date"],
            )
            nominee = Nominee(
                nominee_id=r["nominee_id"],
                plan_id=r["plan_id"],
                nominee_person_id=r["nominee_person_id"],
                readiness=r["readiness"],
                readiness_percentage=r["readiness_percentage"],
                rank=r["rank"],
                development_needs=r["development_needs"],
                status=r["status"],
            )
            results.append(
                {
                    "plan": plan,
                    "nominee": nominee,
                    "position_title": r["position_title"],
                }
            )
        return results
