"""
University synthesizers.

UniversityAgentSynthesizer — LLM agent executes university enrollment intents via University APIs.

Auto-discovered by synthesis_runner.py since it subclasses DefaultAgentSynthesizer
and lives in synthesize/synthesizer/.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from synthesize.environments.university.apis.enrollments import (
    add_to_waitlist,
    check_course_capacity,
    drop_student,
    enroll_student,
    get_course_waitlist,
    get_enrollment_status,
    list_courses,
    list_student_enrollments,
    list_students,
)
from synthesize.environments.university.db.db import get_conn
from synthesize.synthesizer.agent_synthesizer import IntentDef, Step
from synthesize.synthesizer.default_agent import DefaultAgentSynthesizer
from synthesize.synthesizer.generalist_synthesizer import GeneralistSynthesizer

# ── Tool registry ─────────────────────────────────────────────────────────────

UNIVERSITY_TOOL_REGISTRY: Dict[str, dict] = {
    "list_students": {
        "fn": list_students,
        "description": "List students, optionally filtered by enrollment_status (active, graduated, inactive, suspended).",
        "input_schema": {
            "type": "object",
            "properties": {
                "enrollment_status": {
                    "type": "string",
                    "enum": ["active", "graduated", "inactive", "suspended"],
                    "description": "Optional status filter",
                },
            },
            "required": [],
        },
    },
    "list_courses": {
        "fn": list_courses,
        "description": "List courses, optionally filtered by department or open status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "department": {"type": "string", "description": "Optional department filter"},
                "is_open": {"type": "boolean", "description": "Only open (active) courses"},
            },
            "required": [],
        },
    },
    "check_course_capacity": {
        "fn": check_course_capacity,
        "description": "Check enrollment capacity for a course: current_enrollment, capacity, available_seats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "course_id": {"type": "string"},
            },
            "required": ["course_id"],
        },
    },
    "get_enrollment_status": {
        "fn": get_enrollment_status,
        "description": "Get enrollment status string for a (student, course) pair.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "string"},
                "course_id": {"type": "string"},
            },
            "required": ["student_id", "course_id"],
        },
    },
    "list_student_enrollments": {
        "fn": list_student_enrollments,
        "description": "List all enrollments for a student.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "string"},
            },
            "required": ["student_id"],
        },
    },
    "get_course_waitlist": {
        "fn": get_course_waitlist,
        "description": "Get the waitlist for a course.",
        "input_schema": {
            "type": "object",
            "properties": {
                "course_id": {"type": "string"},
            },
            "required": ["course_id"],
        },
    },
    "enroll_student": {
        "fn": enroll_student,
        "description": (
            "Enroll an active student in an open course with available seats. "
            "Raises ValueError if student is inactive, course is full, or student is already enrolled."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "string"},
                "course_id": {"type": "string"},
            },
            "required": ["student_id", "course_id"],
        },
    },
    "drop_student": {
        "fn": drop_student,
        "description": (
            "Drop a student from a course they are currently enrolled in. "
            "Sets enrollment status to 'dropped'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "string"},
                "course_id": {"type": "string"},
            },
            "required": ["student_id", "course_id"],
        },
    },
    "add_to_waitlist": {
        "fn": add_to_waitlist,
        "description": (
            "Add an active student to the waitlist for a full course. "
            "Student must not already be enrolled or on the waitlist."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "student_id": {"type": "string"},
                "course_id": {"type": "string"},
            },
            "required": ["student_id", "course_id"],
        },
    },
}

# Generic alias required by GeneralistPopulatorSynthesizer
TOOL_REGISTRY = UNIVERSITY_TOOL_REGISTRY

# ── Samplers ──────────────────────────────────────────────────────────────────


def _sample_enroll_student() -> Optional[dict]:
    """Always possible if active students and open courses with seats exist."""
    with get_conn() as conn:
        has_student = conn.execute(
            "SELECT 1 FROM student WHERE enrollment_status = 'active' LIMIT 1"
        ).fetchone()
        has_course = conn.execute(
            """
            SELECT 1 FROM course
            WHERE is_open = 1 AND current_enrollment < capacity
            LIMIT 1
            """
        ).fetchone()
    if not (has_student and has_course):
        return None
    return {}


def _sample_drop_student() -> Optional[dict]:
    """Sample an enrolled (student_id, course_id) pair."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT student_id, course_id FROM enrollment
            WHERE status = 'enrolled'
            ORDER BY RANDOM() LIMIT 1
            """
        ).fetchone()
    if row is None:
        return None
    return {"student_id": row["student_id"], "course_id": row["course_id"]}


def _sample_add_to_waitlist() -> Optional[dict]:
    """Sample a full course and an active student not enrolled/waitlisted."""
    with get_conn() as conn:
        course = conn.execute(
            """
            SELECT course_id FROM course
            WHERE is_open = 1 AND current_enrollment >= capacity
            ORDER BY RANDOM() LIMIT 1
            """
        ).fetchone()
        if course is None:
            return None

        # Find a student not already enrolled or waitlisted
        student = conn.execute(
            """
            SELECT student_id FROM student
            WHERE enrollment_status = 'active'
              AND student_id NOT IN (
                  SELECT student_id FROM enrollment WHERE course_id = ? AND status = 'enrolled'
              )
              AND student_id NOT IN (
                  SELECT student_id FROM waitlist WHERE course_id = ?
              )
            ORDER BY RANDOM() LIMIT 1
            """,
            (course["course_id"], course["course_id"]),
        ).fetchone()
    if student is None:
        return None
    return {"student_id": student["student_id"], "course_id": course["course_id"]}


# ── Postconditions ────────────────────────────────────────────────────────────


def _postcond_enroll_student(params: dict, steps: List[Step]) -> Dict[str, bool]:
    student_id = None
    course_id = None
    for step in steps:
        if step.tool == "enroll_student" and not step.is_error:
            result = step.result
            if isinstance(result, dict):
                student_id = result.get("student_id")
                course_id = result.get("course_id")
            break
    if not (student_id and course_id):
        return {"enrollment_created": False, "status_enrolled": False}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM enrollment WHERE student_id = ? AND course_id = ?",
            (student_id, course_id),
        ).fetchone()

    return {
        "enrollment_created": row is not None,
        "status_enrolled": row is not None and row["status"] == "enrolled",
    }


def _postcond_drop_student(params: dict, steps: List[Step]) -> Dict[str, bool]:
    student_id = params.get("student_id")
    course_id = params.get("course_id")
    if not (student_id and course_id):
        for step in steps:
            if step.tool == "drop_student" and not step.is_error:
                result = step.result
                if isinstance(result, dict):
                    student_id = result.get("student_id")
                    course_id = result.get("course_id")
                break
    if not (student_id and course_id):
        return {"enrollment_status_dropped": False}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM enrollment WHERE student_id = ? AND course_id = ?",
            (student_id, course_id),
        ).fetchone()

    return {"enrollment_status_dropped": row is not None and row["status"] == "dropped"}


def _postcond_add_to_waitlist(params: dict, steps: List[Step]) -> Dict[str, bool]:
    student_id = params.get("student_id")
    course_id = params.get("course_id")
    if not (student_id and course_id):
        for step in steps:
            if step.tool == "add_to_waitlist" and not step.is_error:
                result = step.result
                if isinstance(result, dict):
                    student_id = result.get("student_id")
                    course_id = result.get("course_id")
                break
    if not (student_id and course_id):
        return {"waitlist_entry_created": False}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM waitlist WHERE student_id = ? AND course_id = ?",
            (student_id, course_id),
        ).fetchone()

    return {"waitlist_entry_created": row is not None}


# ── Intent definitions ────────────────────────────────────────────────────────

UNIVERSITY_INTENTS: Dict[str, IntentDef] = {
    "ENROLL_STUDENT": IntentDef(
        name="ENROLL_STUDENT",
        brief="Enroll an active student in an open course with available seats.",
        informed_rules="""\
University Enrollment Rules:
- Student must have enrollment_status='active'
- Course must be open (is_open=true) with available_seats > 0
- Student cannot already be enrolled in the same course
- Use check_course_capacity to verify space before enrolling
""",
        tools=[
            "list_students",
            "list_courses",
            "check_course_capacity",
            "get_enrollment_status",
            "enroll_student",
        ],
        sampler=_sample_enroll_student,
        task_prompt=lambda p: (
            "Enroll an active student in an open course that has available seats. "
            "Check course capacity first, then enroll the student."
        ),
        postconditions=_postcond_enroll_student,
    ),
    "DROP_STUDENT": IntentDef(
        name="DROP_STUDENT",
        brief="Drop a student from a course they are enrolled in.",
        informed_rules="""\
University Drop Rules:
- Student must be currently enrolled (status='enrolled') in the course
- Sets enrollment status to 'dropped'
""",
        tools=[
            "list_student_enrollments",
            "drop_student",
        ],
        sampler=_sample_drop_student,
        task_prompt=lambda p: (
            f"Drop student '{p['student_id']}' from course '{p['course_id']}'."
        ),
        postconditions=_postcond_drop_student,
    ),
    "ADD_TO_WAITLIST": IntentDef(
        name="ADD_TO_WAITLIST",
        brief="Add an active student to the waitlist for a full course.",
        informed_rules="""\
University Waitlist Rules:
- Course must be full (current_enrollment >= capacity)
- Student must be active and not already enrolled or waitlisted for the same course
""",
        tools=[
            "list_students",
            "list_courses",
            "check_course_capacity",
            "get_enrollment_status",
            "get_course_waitlist",
            "add_to_waitlist",
        ],
        sampler=_sample_add_to_waitlist,
        task_prompt=lambda p: (
            f"Add student '{p['student_id']}' to the waitlist for full course '{p['course_id']}'."
        ),
        postconditions=_postcond_add_to_waitlist,
    ),
}

# ── Synthesizer classes ───────────────────────────────────────────────────────


class UniversityAgentSynthesizer(DefaultAgentSynthesizer):
    def __init__(self) -> None:
        super().__init__(
            name="university_agent",
            description="LLM agent executes university enrollment intents via University APIs",
            tool_registry=UNIVERSITY_TOOL_REGISTRY,
            intents=UNIVERSITY_INTENTS,
            env_name="University",
        )


class UniversityGeneralistSynthesizer(GeneralistSynthesizer):
    INTENT_TO_WRITE_TOOLS = {
        "ENROLL_STUDENT": {"enroll_student"},
        "DROP_STUDENT": {"drop_student"},
        "ADD_TO_WAITLIST": {"add_to_waitlist"},
    }

    def __init__(self) -> None:
        super().__init__(
            name="university_generalist",
            description=(
                "Goal-directed agent that observes DB state, selects an appropriate intent "
                "from the bootstrap library, and executes it — no pre-assigned task."
            ),
            tool_registry=UNIVERSITY_TOOL_REGISTRY,
            bootstrap_intents=UNIVERSITY_INTENTS,
            env_name="University",
        )

    def _init_evolution(self) -> None:
        from pathlib import Path

        from synthesize.evolution.analyzer import TrajectoryAnalyzer
        from synthesize.evolution.engine import EvolutionEngine
        from synthesize.evolution.models import EvolvedIntent, IntentLibrary
        from synthesize.evolution.store import TrajectoryStore
        from synthesize.synthesizer.agent_synthesizer import MODEL, PROXY_BASE_URL

        runs_root = Path(".runs") / "evolution" / "university"
        runs_root.mkdir(parents=True, exist_ok=True)

        store = TrajectoryStore(runs_root / "trajectories.db")
        analyzer = TrajectoryAnalyzer(
            model=MODEL,
            base_url=PROXY_BASE_URL,
            api_key="anything",
        )
        engine = EvolutionEngine(store=store, analyzer=analyzer)

        library_path = runs_root / "intent_library.json"
        if library_path.exists():
            library = IntentLibrary.load(library_path)
        else:
            library = IntentLibrary()
            for name, intent_def in UNIVERSITY_INTENTS.items():
                library.add_intent(EvolvedIntent.from_intent_def(intent_def))

        self.evolution_engine = engine
        self.intent_library = library
        self.library_path = library_path
