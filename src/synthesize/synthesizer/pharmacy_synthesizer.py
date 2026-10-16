"""
Pharmacy synthesizers.

PharmacyAgentSynthesizer — LLM agent executes pharmacy intents via Pharmacy APIs.

Auto-discovered by synthesis_runner.py since it subclasses DefaultAgentSynthesizer
and lives in synthesize/synthesizer/.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from synthesize.environments.pharmacy.apis.prescriptions import (
    cancel_prescription,
    create_prescription,
    fill_prescription,
    get_prescription,
    list_medications,
    list_patients,
    list_physicians,
    list_prescriptions_by_status,
    list_prescriptions_for_patient,
)
from synthesize.environments.pharmacy.db.db import get_conn
from synthesize.synthesizer.agent_synthesizer import IntentDef, Step
from synthesize.synthesizer.default_agent import DefaultAgentSynthesizer
from synthesize.synthesizer.generalist_synthesizer import GeneralistSynthesizer

# ── Tool registry ─────────────────────────────────────────────────────────────

PHARMACY_TOOL_REGISTRY: Dict[str, dict] = {
    "list_patients": {
        "fn": list_patients,
        "description": "List all patients.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "list_physicians": {
        "fn": list_physicians,
        "description": "List all physicians.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "list_medications": {
        "fn": list_medications,
        "description": "List medications, optionally filtered by classification (prescription, OTC, controlled).",
        "input_schema": {
            "type": "object",
            "properties": {
                "classification": {
                    "type": "string",
                    "enum": ["prescription", "OTC", "controlled"],
                    "description": "Optional classification filter",
                },
            },
            "required": [],
        },
    },
    "list_prescriptions_by_status": {
        "fn": list_prescriptions_by_status,
        "description": "List prescriptions by status (pending, filled, on_hold, cancelled, expired).",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "filled", "on_hold", "cancelled", "expired"],
                },
            },
            "required": ["status"],
        },
    },
    "list_prescriptions_for_patient": {
        "fn": list_prescriptions_for_patient,
        "description": "List all prescriptions for a specific patient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
            },
            "required": ["patient_id"],
        },
    },
    "get_prescription": {
        "fn": get_prescription,
        "description": "Get a single prescription record by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prescription_id": {"type": "string"},
            },
            "required": ["prescription_id"],
        },
    },
    "create_prescription": {
        "fn": create_prescription,
        "description": (
            "Issue a new prescription. "
            "patient, physician, and medication must all be active. "
            "dosage and instructions must be non-empty. "
            "New prescription status is always 'pending'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "physician_id": {"type": "string"},
                "medication_id": {"type": "string"},
                "dosage": {"type": "string", "description": "e.g. '10mg', '500mg twice daily'"},
                "instructions": {"type": "string", "description": "e.g. 'Take with food'"},
                "refills_remaining": {"type": "integer", "description": "Number of refills (default 0)"},
                "pharmacy_notes": {"type": "string", "description": "Optional pharmacy notes"},
            },
            "required": ["patient_id", "physician_id", "medication_id", "dosage", "instructions"],
        },
    },
    "fill_prescription": {
        "fn": fill_prescription,
        "description": (
            "Mark a prescription as filled. "
            "Status must be 'pending' or 'on_hold'. "
            "Sets date_filled to today."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prescription_id": {"type": "string"},
                "pharmacy_notes": {"type": "string", "description": "Optional pharmacy notes"},
            },
            "required": ["prescription_id"],
        },
    },
    "cancel_prescription": {
        "fn": cancel_prescription,
        "description": (
            "Cancel a prescription. "
            "Only pending or on_hold prescriptions can be cancelled."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prescription_id": {"type": "string"},
                "pharmacy_notes": {"type": "string", "description": "Optional reason for cancellation"},
            },
            "required": ["prescription_id"],
        },
    },
}

# Generic alias required by GeneralistPopulatorSynthesizer
TOOL_REGISTRY = PHARMACY_TOOL_REGISTRY

# ── Samplers ──────────────────────────────────────────────────────────────────


def _sample_create_prescription() -> Optional[dict]:
    """Always possible from seed data — return empty dict."""
    with get_conn() as conn:
        has_patient = conn.execute(
            "SELECT 1 FROM patient WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        has_physician = conn.execute(
            "SELECT 1 FROM physician WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        has_medication = conn.execute(
            "SELECT 1 FROM medication WHERE is_active = 1 LIMIT 1"
        ).fetchone()
    if not (has_patient and has_physician and has_medication):
        return None
    return {}


def _sample_fill_prescription() -> Optional[dict]:
    """Sample a pending prescription to fill."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT prescription_id FROM prescription WHERE status = 'pending' ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {"prescription_id": row["prescription_id"]}


def _sample_cancel_prescription() -> Optional[dict]:
    """Sample a pending prescription to cancel."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT prescription_id FROM prescription WHERE status IN ('pending', 'on_hold') ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {"prescription_id": row["prescription_id"]}


# ── Postconditions ────────────────────────────────────────────────────────────


def _postcond_create_prescription(params: dict, steps: List[Step]) -> Dict[str, bool]:
    rx_id = None
    for step in steps:
        if step.tool == "create_prescription" and not step.is_error:
            result = step.result
            if isinstance(result, dict):
                rx_id = result.get("prescription_id")
            break
    if not rx_id:
        return {"prescription_created": False, "status_pending": False}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM prescription WHERE prescription_id = ?", (rx_id,)
        ).fetchone()

    return {
        "prescription_created": row is not None,
        "status_pending": row is not None and row["status"] == "pending",
    }


def _postcond_fill_prescription(params: dict, steps: List[Step]) -> Dict[str, bool]:
    rx_id = params.get("prescription_id")
    if not rx_id:
        for step in steps:
            if step.tool == "fill_prescription" and not step.is_error:
                result = step.result
                if isinstance(result, dict):
                    rx_id = result.get("prescription_id")
                break
    if not rx_id:
        return {"status_filled": False}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM prescription WHERE prescription_id = ?", (rx_id,)
        ).fetchone()

    return {"status_filled": row is not None and row["status"] == "filled"}


def _postcond_cancel_prescription(params: dict, steps: List[Step]) -> Dict[str, bool]:
    rx_id = params.get("prescription_id")
    if not rx_id:
        for step in steps:
            if step.tool == "cancel_prescription" and not step.is_error:
                result = step.result
                if isinstance(result, dict):
                    rx_id = result.get("prescription_id")
                break
    if not rx_id:
        return {"status_cancelled": False}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM prescription WHERE prescription_id = ?", (rx_id,)
        ).fetchone()

    return {"status_cancelled": row is not None and row["status"] == "cancelled"}


# ── Intent definitions ────────────────────────────────────────────────────────

PHARMACY_INTENTS: Dict[str, IntentDef] = {
    "CREATE_PRESCRIPTION": IntentDef(
        name="CREATE_PRESCRIPTION",
        brief="Issue a new prescription for a patient.",
        informed_rules="""\
Pharmacy Prescription Creation Rules:
- patient, physician, and medication must all be active (is_active=true)
- dosage and instructions must be non-empty
- refills_remaining must be >= 0 (default 0)
- New prescriptions always start with status='pending'
- Choose realistic dosage strings (e.g. '500mg', '10mg twice daily')
""",
        tools=[
            "list_patients",
            "list_physicians",
            "list_medications",
            "create_prescription",
        ],
        sampler=_sample_create_prescription,
        task_prompt=lambda p: (
            "Create a new prescription for a patient. "
            "Select an active patient, an active physician, and an appropriate medication. "
            "Provide realistic dosage and instructions."
        ),
        postconditions=_postcond_create_prescription,
    ),
    "FILL_PRESCRIPTION": IntentDef(
        name="FILL_PRESCRIPTION",
        brief="Fill a pending prescription.",
        informed_rules="""\
Pharmacy Fill Rules:
- Prescription must have status='pending' or 'on_hold' to be filled
- Filling sets status='filled' and date_filled=today
- Cannot fill a cancelled or expired prescription
""",
        tools=[
            "list_prescriptions_by_status",
            "get_prescription",
            "fill_prescription",
        ],
        sampler=_sample_fill_prescription,
        task_prompt=lambda p: (
            f"Fill prescription '{p['prescription_id']}'. "
            "Look up the prescription details and fill it."
        ),
        postconditions=_postcond_fill_prescription,
    ),
    "CANCEL_PRESCRIPTION": IntentDef(
        name="CANCEL_PRESCRIPTION",
        brief="Cancel a pending or on-hold prescription.",
        informed_rules="""\
Pharmacy Cancellation Rules:
- Only pending or on_hold prescriptions can be cancelled
- Filled prescriptions cannot be directly cancelled (must go on_hold first)
""",
        tools=[
            "list_prescriptions_by_status",
            "get_prescription",
            "cancel_prescription",
        ],
        sampler=_sample_cancel_prescription,
        task_prompt=lambda p: (
            f"Cancel prescription '{p['prescription_id']}'. "
            "Look up the prescription and cancel it with an appropriate note."
        ),
        postconditions=_postcond_cancel_prescription,
    ),
}

# ── Synthesizer classes ───────────────────────────────────────────────────────


class PharmacyAgentSynthesizer(DefaultAgentSynthesizer):
    def __init__(self) -> None:
        super().__init__(
            name="pharmacy_agent",
            description="LLM agent executes pharmacy prescription intents via Pharmacy APIs",
            tool_registry=PHARMACY_TOOL_REGISTRY,
            intents=PHARMACY_INTENTS,
            env_name="Pharmacy",
        )


class PharmacyGeneralistSynthesizer(GeneralistSynthesizer):
    INTENT_TO_WRITE_TOOLS = {
        "CREATE_PRESCRIPTION": {"create_prescription"},
        "FILL_PRESCRIPTION": {"fill_prescription"},
        "CANCEL_PRESCRIPTION": {"cancel_prescription"},
    }

    def __init__(self) -> None:
        super().__init__(
            name="pharmacy_generalist",
            description=(
                "Goal-directed agent that observes DB state, selects an appropriate intent "
                "from the bootstrap library, and executes it — no pre-assigned task."
            ),
            tool_registry=PHARMACY_TOOL_REGISTRY,
            bootstrap_intents=PHARMACY_INTENTS,
            env_name="Pharmacy",
        )

    def _init_evolution(self) -> None:
        from pathlib import Path

        from synthesize.evolution.analyzer import TrajectoryAnalyzer
        from synthesize.evolution.engine import EvolutionEngine
        from synthesize.evolution.models import EvolvedIntent, IntentLibrary
        from synthesize.evolution.store import TrajectoryStore
        from synthesize.synthesizer.agent_synthesizer import MODEL, PROXY_BASE_URL

        runs_root = Path(".runs") / "evolution" / "pharmacy"
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
            for name, intent_def in PHARMACY_INTENTS.items():
                library.add_intent(EvolvedIntent.from_intent_def(intent_def))

        self.evolution_engine = engine
        self.intent_library = library
        self.library_path = library_path
