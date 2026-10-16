import datetime
import uuid
from typing import List, Optional

from synthesize.environments.hr.db.db import get_conn
from synthesize.environments.hr.db.models import Feedback, Goal, PerformanceReview

# ── State machine ─────────────────────────────────────────────────────────────

_STATUS_ORDER = {"Draft": 0, "In Progress": 1, "Completed": 2, "Approved": 3}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _row_to_review(row) -> PerformanceReview:
    return PerformanceReview(
        review_id=row["review_id"],
        person_id=row["person_id"],
        template_id=row["template_id"],
        review_period_start=row["review_period_start"],
        review_period_end=row["review_period_end"],
        review_due_date=row["review_due_date"],
        overall_rating=row["overall_rating"],
        overall_rating_label=row["overall_rating_label"],
        reviewer_person_id=row["reviewer_person_id"],
        review_status=row["review_status"],
        review_completion_date=row["review_completion_date"],
    )


def _row_to_goal(row) -> Goal:
    return Goal(
        goal_id=row["goal_id"],
        person_id=row["person_id"],
        goal_name=row["goal_name"],
        goal_description=row["goal_description"],
        goal_type=row["goal_type"],
        start_date=row["start_date"],
        due_date=row["due_date"],
        weight=row["weight"],
        status=row["status"],
        completion_percentage=row["completion_percentage"],
        final_rating=row["final_rating"],
    )


def _row_to_feedback(row) -> Feedback:
    return Feedback(
        feedback_id=row["feedback_id"],
        subject_person_id=row["subject_person_id"],
        provider_person_id=row["provider_person_id"],
        feedback_type=row["feedback_type"],
        feedback_text=row["feedback_text"],
        feedback_date=row["feedback_date"],
        is_anonymous=bool(row["is_anonymous"]),
        sentiment=row["sentiment"],
    )


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(sep=" ", timespec="seconds")


def _person_exists(conn, person_id: str) -> bool:
    return bool(
        conn.execute("SELECT 1 FROM per_person WHERE person_id = ?", (person_id,)).fetchone()
    )


# ── Performance Reviews ───────────────────────────────────────────────────────


def list_reviews(
    person_id: Optional[str] = None,
    period: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[PerformanceReview]:
    query = "SELECT * FROM pm_performance_review WHERE 1=1"
    params: list = []
    if person_id is not None:
        query += " AND person_id = ?"
        params.append(person_id)
    if period is not None:
        query += " AND (review_period_start <= ? AND review_period_end >= ?)"
        params.extend([period, period])
    if status is not None:
        query += " AND review_status = ?"
        params.append(status)
    query += " ORDER BY review_period_end DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_review(r) for r in rows]


def get_review(review_id: str) -> PerformanceReview:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM pm_performance_review WHERE review_id = ?", (review_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Performance review not found: {review_id!r}")
        return _row_to_review(row)


def list_employee_reviews(person_id: str) -> List[PerformanceReview]:
    with get_conn() as conn:
        if not _person_exists(conn, person_id):
            raise LookupError(f"Person not found: {person_id!r}")
        rows = conn.execute(
            "SELECT * FROM pm_performance_review WHERE person_id = ? ORDER BY review_period_end DESC",
            (person_id,),
        ).fetchall()
        return [_row_to_review(r) for r in rows]


def create_review(
    person_id: str,
    template_id: str,
    review_period_start: str,
    review_period_end: str,
    reviewer_person_id: str,
    review_due_date: Optional[str] = None,
) -> PerformanceReview:
    review_id = str(uuid.uuid4())
    now = _now()
    with get_conn() as conn:
        if not _person_exists(conn, person_id):
            raise ValueError(f"Person not found: {person_id!r}")

        if not _person_exists(conn, reviewer_person_id):
            raise ValueError(f"Reviewer person not found: {reviewer_person_id!r}")

        if not conn.execute(
            "SELECT 1 FROM pm_review_template WHERE template_id = ?", (template_id,)
        ).fetchone():
            raise ValueError(f"Review template not found: {template_id!r}")

        overlap = conn.execute(
            """
            SELECT 1 FROM pm_performance_review
            WHERE person_id = ?
              AND review_status = 'In Progress'
              AND review_period_start <= ?
              AND review_period_end >= ?
            """,
            (person_id, review_period_end, review_period_start),
        ).fetchone()
        if overlap:
            raise ValueError(
                f"An In Progress review already exists for person {person_id!r} "
                "overlapping the requested period"
            )

        conn.execute(
            """
            INSERT INTO pm_performance_review
                (review_id, person_id, template_id, review_period_start,
                 review_period_end, review_due_date, reviewer_person_id,
                 review_status, created_on, last_modified_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Draft', ?, ?)
            """,
            (
                review_id,
                person_id,
                template_id,
                review_period_start,
                review_period_end,
                review_due_date,
                reviewer_person_id,
                now,
                now,
            ),
        )

    return PerformanceReview(
        review_id=review_id,
        person_id=person_id,
        template_id=template_id,
        review_period_start=review_period_start,
        review_period_end=review_period_end,
        review_due_date=review_due_date,
        overall_rating=None,
        overall_rating_label=None,
        reviewer_person_id=reviewer_person_id,
        review_status="Draft",
        review_completion_date=None,
    )


def update_review(
    review_id: str,
    overall_rating: Optional[float] = None,
    overall_rating_label: Optional[str] = None,
    review_status: Optional[str] = None,
    competency_ratings: Optional[List[dict]] = None,
) -> PerformanceReview:
    now = _now()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM pm_performance_review WHERE review_id = ?", (review_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Performance review not found: {review_id!r}")

        current_status = row["review_status"]
        current_rating = row["overall_rating"]

        if review_status is not None:
            current_order = _STATUS_ORDER.get(current_status, -1)
            new_order = _STATUS_ORDER.get(review_status, -1)
            if new_order < current_order:
                raise ValueError(
                    f"Cannot move review status backwards from "
                    f"{current_status!r} to {review_status!r}"
                )

        effective_rating = overall_rating if overall_rating is not None else current_rating
        if review_status == "Completed" and effective_rating is None:
            raise ValueError("overall_rating must be set before a review can be marked Completed")

        if competency_ratings is not None:
            for cr in competency_ratings:
                comp_id = cr.get("competency_id")
                if not conn.execute(
                    "SELECT 1 FROM fod_competency WHERE competency_id = ?", (comp_id,)
                ).fetchone():
                    raise ValueError(f"Competency not found: {comp_id!r}")

            for cr in competency_ratings:
                existing = conn.execute(
                    "SELECT review_comp_id FROM pm_review_competency WHERE review_id = ? AND competency_id = ?",
                    (review_id, cr["competency_id"]),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE pm_review_competency
                           SET rating = ?, rating_label = ?, comments = ?
                         WHERE review_id = ? AND competency_id = ?
                        """,
                        (
                            cr.get("rating"),
                            cr.get("rating_label"),
                            cr.get("comments"),
                            review_id,
                            cr["competency_id"],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO pm_review_competency
                            (review_id, competency_id, rating, rating_label, comments, created_on)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            review_id,
                            cr["competency_id"],
                            cr.get("rating"),
                            cr.get("rating_label"),
                            cr.get("comments"),
                            now,
                        ),
                    )

        sets: list = []
        vals: list = []
        if overall_rating is not None:
            sets.append("overall_rating = ?")
            vals.append(overall_rating)
        if overall_rating_label is not None:
            sets.append("overall_rating_label = ?")
            vals.append(overall_rating_label)
        if review_status is not None:
            sets.append("review_status = ?")
            vals.append(review_status)
            if review_status == "Completed":
                sets.append("review_completion_date = ?")
                vals.append(datetime.date.today().isoformat())

        if sets:
            sets.append("last_modified_on = ?")
            vals.append(now)
            vals.append(review_id)
            conn.execute(
                f"UPDATE pm_performance_review SET {', '.join(sets)} WHERE review_id = ?",
                vals,
            )

    return get_review(review_id)


# ── Goals ─────────────────────────────────────────────────────────────────────


def list_goals(person_id: str, status: Optional[str] = None) -> List[Goal]:
    with get_conn() as conn:
        if not _person_exists(conn, person_id):
            raise LookupError(f"Person not found: {person_id!r}")
        query = "SELECT * FROM pm_goal WHERE person_id = ?"
        params: list = [person_id]
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        rows = conn.execute(query, params).fetchall()
        return [_row_to_goal(r) for r in rows]


def get_goal(goal_id: str) -> Goal:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM pm_goal WHERE goal_id = ?", (goal_id,)).fetchone()
        if row is None:
            raise LookupError(f"Goal not found: {goal_id!r}")
        return _row_to_goal(row)


def _active_goal_weight_total(conn, person_id: str, exclude_goal_id: Optional[str] = None) -> float:
    query = """
        SELECT COALESCE(SUM(weight), 0)
        FROM pm_goal
        WHERE person_id = ?
          AND status NOT IN ('Completed', 'Cancelled')
          AND weight IS NOT NULL
    """
    params: list = [person_id]
    if exclude_goal_id is not None:
        query += " AND goal_id != ?"
        params.append(exclude_goal_id)
    return conn.execute(query, params).fetchone()[0]


def create_goal(
    person_id: str,
    goal_name: str,
    start_date: str,
    due_date: str,
    goal_type: Optional[str] = None,
    category: Optional[str] = None,
    weight: Optional[float] = None,
    metric: Optional[str] = None,
    target_value: Optional[float] = None,
    goal_description: Optional[str] = None,
    created_by_person_id: Optional[str] = None,
) -> Goal:
    if due_date < start_date:
        raise ValueError(f"due_date ({due_date}) must be >= start_date ({start_date})")

    goal_id = str(uuid.uuid4())
    now = _now()

    with get_conn() as conn:
        if not _person_exists(conn, person_id):
            raise ValueError(f"Person not found: {person_id!r}")

        if weight is not None:
            current_total = _active_goal_weight_total(conn, person_id)
            if current_total + weight > 100:
                raise ValueError(
                    f"Adding weight {weight} would exceed 100% total weight "
                    f"(current total: {current_total})"
                )

        conn.execute(
            """
            INSERT INTO pm_goal
                (goal_id, person_id, goal_name, goal_description, goal_type,
                 category, start_date, due_date, weight, metric, target_value,
                 status, completion_percentage, created_by_person_id,
                 created_on, last_modified_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Not Started', 0, ?, ?, ?)
            """,
            (
                goal_id,
                person_id,
                goal_name,
                goal_description,
                goal_type,
                category,
                start_date,
                due_date,
                weight,
                metric,
                target_value,
                created_by_person_id,
                now,
                now,
            ),
        )

    return Goal(
        goal_id=goal_id,
        person_id=person_id,
        goal_name=goal_name,
        goal_description=goal_description,
        goal_type=goal_type,
        start_date=start_date,
        due_date=due_date,
        weight=weight,
        status="Not Started",
        completion_percentage=0,
        final_rating=None,
    )


def update_goal(
    goal_id: str,
    status: Optional[str] = None,
    completion_percentage: Optional[int] = None,
    actual_value: Optional[float] = None,
    final_rating: Optional[float] = None,
    due_date: Optional[str] = None,
    weight: Optional[float] = None,
) -> Goal:
    now = _now()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM pm_goal WHERE goal_id = ?", (goal_id,)).fetchone()
        if row is None:
            raise LookupError(f"Goal not found: {goal_id!r}")

        current_pct = row["completion_percentage"]

        if completion_percentage is not None and completion_percentage < current_pct:
            raise ValueError(
                f"completion_percentage cannot decrease (current: {current_pct}, "
                f"requested: {completion_percentage})"
            )

        if status == "Completed":
            completion_percentage = 100

        if weight is not None:
            current_total = _active_goal_weight_total(
                conn, row["person_id"], exclude_goal_id=goal_id
            )
            if current_total + weight > 100:
                raise ValueError(
                    f"Updating weight to {weight} would exceed 100% total weight "
                    f"(other goals total: {current_total})"
                )

        sets: list = []
        vals: list = []
        for col, val in [
            ("status", status),
            ("completion_percentage", completion_percentage),
            ("actual_value", actual_value),
            ("final_rating", final_rating),
            ("due_date", due_date),
            ("weight", weight),
        ]:
            if val is not None:
                sets.append(f"{col} = ?")
                vals.append(val)

        if sets:
            sets.append("last_modified_on = ?")
            vals.append(now)
            vals.append(goal_id)
            conn.execute(f"UPDATE pm_goal SET {', '.join(sets)} WHERE goal_id = ?", vals)

    return get_goal(goal_id)


def add_goal_comment(goal_id: str, commenter_person_id: str, comment_text: str) -> dict:
    now = _now()
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM pm_goal WHERE goal_id = ?", (goal_id,)).fetchone():
            raise LookupError(f"Goal not found: {goal_id!r}")

        if not _person_exists(conn, commenter_person_id):
            raise LookupError(f"Person not found: {commenter_person_id!r}")

        cursor = conn.execute(
            """
            INSERT INTO pm_goal_comment (goal_id, commenter_person_id, comment_text, comment_date)
            VALUES (?, ?, ?, ?)
            """,
            (goal_id, commenter_person_id, comment_text, now),
        )
        comment_id = cursor.lastrowid

    return {
        "comment_id": comment_id,
        "goal_id": goal_id,
        "commenter_person_id": commenter_person_id,
        "comment_text": comment_text,
        "comment_date": now,
    }


# ── Feedback ──────────────────────────────────────────────────────────────────


def list_feedback(person_id: str, feedback_type: Optional[str] = None) -> List[Feedback]:
    with get_conn() as conn:
        if not _person_exists(conn, person_id):
            raise LookupError(f"Person not found: {person_id!r}")
        query = "SELECT * FROM pm_feedback WHERE subject_person_id = ?"
        params: list = [person_id]
        if feedback_type is not None:
            query += " AND feedback_type = ?"
            params.append(feedback_type)
        rows = conn.execute(query, params).fetchall()
        return [_row_to_feedback(r) for r in rows]


def submit_feedback(
    subject_person_id: str,
    provider_person_id: str,
    feedback_type: str,
    feedback_text: str,
    feedback_date: str,
    is_anonymous: bool = False,
    sentiment: Optional[str] = None,
) -> Feedback:
    if subject_person_id == provider_person_id:
        raise ValueError("A person cannot submit feedback about themselves")

    feedback_id = str(uuid.uuid4())
    now = _now()

    with get_conn() as conn:
        if not _person_exists(conn, subject_person_id):
            raise ValueError(f"Subject person not found: {subject_person_id!r}")

        if not _person_exists(conn, provider_person_id):
            raise ValueError(f"Provider person not found: {provider_person_id!r}")

        if feedback_type == "Manager":
            manager_row = conn.execute(
                """
                SELECT manager_id FROM emp_job
                WHERE person_id = ?
                  AND end_date IS NULL
                LIMIT 1
                """,
                (subject_person_id,),
            ).fetchone()
            if manager_row is None or manager_row["manager_id"] != provider_person_id:
                raise ValueError(
                    f"Provider {provider_person_id!r} is not the current manager "
                    f"of subject {subject_person_id!r}"
                )

        conn.execute(
            """
            INSERT INTO pm_feedback
                (feedback_id, subject_person_id, provider_person_id, feedback_type,
                 feedback_text, feedback_date, is_anonymous, sentiment, created_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                subject_person_id,
                provider_person_id,
                feedback_type,
                feedback_text,
                feedback_date,
                int(is_anonymous),
                sentiment,
                now,
            ),
        )

    return Feedback(
        feedback_id=feedback_id,
        subject_person_id=subject_person_id,
        provider_person_id=provider_person_id,
        feedback_type=feedback_type,
        feedback_text=feedback_text,
        feedback_date=feedback_date,
        is_anonymous=is_anonymous,
        sentiment=sentiment,
    )
