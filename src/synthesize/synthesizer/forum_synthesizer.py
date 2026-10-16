"""
Forum synthesizers.

ForumAgentSynthesizer — LLM agent executes forum content intents via Forum APIs.

Auto-discovered by synthesis_runner.py since it subclasses DefaultAgentSynthesizer
and lives in synthesize/synthesizer/.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from synthesize.environments.forum.apis.content import (
    close_thread,
    create_post,
    create_thread,
    get_thread,
    list_categories,
    list_posts_in_thread,
    list_tags,
    list_threads_in_category,
    list_users,
    reopen_thread,
)
from synthesize.environments.forum.db.db import get_conn
from synthesize.synthesizer.agent_synthesizer import IntentDef, Step
from synthesize.synthesizer.default_agent import DefaultAgentSynthesizer
from synthesize.synthesizer.generalist_synthesizer import GeneralistSynthesizer

# ── Tool registry ─────────────────────────────────────────────────────────────

FORUM_TOOL_REGISTRY: Dict[str, dict] = {
    "list_users": {
        "fn": list_users,
        "description": "List forum users, optionally filtered by role (member, moderator, admin).",
        "input_schema": {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "enum": ["member", "moderator", "admin"],
                    "description": "Optional role filter",
                },
            },
            "required": [],
        },
    },
    "list_categories": {
        "fn": list_categories,
        "description": "List all forum categories.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "list_tags": {
        "fn": list_tags,
        "description": "List approved forum tags.",
        "input_schema": {
            "type": "object",
            "properties": {
                "approved_only": {"type": "boolean", "description": "Only approved tags (default true)"},
            },
            "required": [],
        },
    },
    "list_threads_in_category": {
        "fn": list_threads_in_category,
        "description": "List threads in a category, optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["open", "closed", "deleted"],
                    "description": "Optional status filter",
                },
            },
            "required": ["category_id"],
        },
    },
    "list_posts_in_thread": {
        "fn": list_posts_in_thread,
        "description": "List all posts in a thread.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
            },
            "required": ["thread_id"],
        },
    },
    "get_thread": {
        "fn": get_thread,
        "description": "Get a thread record by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
            },
            "required": ["thread_id"],
        },
    },
    "create_thread": {
        "fn": create_thread,
        "description": (
            "Create a new thread in a category with an opening post. "
            "author_id must be a valid user. category_id must exist. "
            "tag_ids is optional (list of approved tag IDs)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "author_id": {"type": "string", "description": "User ID of the thread author"},
                "category_id": {"type": "string"},
                "title": {"type": "string", "description": "Thread title"},
                "content": {"type": "string", "description": "Opening post content"},
                "tag_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of tag IDs to attach",
                },
            },
            "required": ["author_id", "category_id", "title", "content"],
        },
    },
    "create_post": {
        "fn": create_post,
        "description": (
            "Reply to a thread with a new post. "
            "Thread must be open. author_id must be a valid user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "author_id": {"type": "string", "description": "User ID of the post author"},
                "thread_id": {"type": "string"},
                "content": {"type": "string", "description": "Post content"},
            },
            "required": ["author_id", "thread_id", "content"],
        },
    },
    "close_thread": {
        "fn": close_thread,
        "description": (
            "Close an open thread. "
            "actor_id must be a moderator or admin."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "actor_id": {"type": "string", "description": "User ID of moderator or admin performing the action"},
            },
            "required": ["thread_id", "actor_id"],
        },
    },
    "reopen_thread": {
        "fn": reopen_thread,
        "description": (
            "Reopen a closed thread. "
            "actor_id must be a moderator or admin."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "actor_id": {"type": "string", "description": "User ID of moderator or admin"},
            },
            "required": ["thread_id", "actor_id"],
        },
    },
}

# Generic alias required by GeneralistPopulatorSynthesizer
TOOL_REGISTRY = FORUM_TOOL_REGISTRY

# ── Samplers ──────────────────────────────────────────────────────────────────


def _sample_create_thread() -> Optional[dict]:
    """Always possible from seed data — return empty dict."""
    with get_conn() as conn:
        has_user = conn.execute("SELECT 1 FROM forum_user LIMIT 1").fetchone()
        has_category = conn.execute("SELECT 1 FROM category LIMIT 1").fetchone()
    if not (has_user and has_category):
        return None
    return {}


def _sample_create_post() -> Optional[dict]:
    """Sample an open thread to reply to."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT thread_id FROM thread WHERE status = 'open' ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {"thread_id": row["thread_id"]}


def _sample_close_thread() -> Optional[dict]:
    """Sample an open thread and a moderator/admin to close it."""
    with get_conn() as conn:
        thread = conn.execute(
            "SELECT thread_id FROM thread WHERE status = 'open' ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
        if thread is None:
            return None
        actor = conn.execute(
            "SELECT user_id FROM forum_user WHERE role IN ('moderator', 'admin') ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    if actor is None:
        return None
    return {"thread_id": thread["thread_id"], "actor_id": actor["user_id"]}


# ── Postconditions ────────────────────────────────────────────────────────────


def _postcond_create_thread(params: dict, steps: List[Step]) -> Dict[str, bool]:
    thread_id = None
    for step in steps:
        if step.tool == "create_thread" and not step.is_error:
            result = step.result
            if isinstance(result, dict):
                thread_id = result.get("thread_id")
            break
    if not thread_id:
        return {"thread_created": False, "first_post_created": False}

    with get_conn() as conn:
        thread = conn.execute(
            "SELECT thread_id FROM thread WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        post_count = conn.execute(
            "SELECT COUNT(*) FROM post WHERE thread_id = ?", (thread_id,)
        ).fetchone()[0]

    return {
        "thread_created": thread is not None,
        "first_post_created": post_count > 0,
    }


def _postcond_create_post(params: dict, steps: List[Step]) -> Dict[str, bool]:
    for step in steps:
        if step.tool == "create_post" and not step.is_error:
            return {"post_created": True}
    return {"post_created": False}


def _postcond_close_thread(params: dict, steps: List[Step]) -> Dict[str, bool]:
    thread_id = params.get("thread_id")
    if not thread_id:
        for step in steps:
            if step.tool == "close_thread" and not step.is_error:
                result = step.result
                if isinstance(result, dict):
                    thread_id = result.get("thread_id")
                break
    if not thread_id:
        return {"thread_status_closed": False}

    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM thread WHERE thread_id = ?", (thread_id,)
        ).fetchone()

    return {"thread_status_closed": row is not None and row["status"] == "closed"}


# ── Intent definitions ────────────────────────────────────────────────────────

FORUM_INTENTS: Dict[str, IntentDef] = {
    "CREATE_THREAD": IntentDef(
        name="CREATE_THREAD",
        brief="Create a new thread in a forum category with an opening post.",
        informed_rules="""\
Forum Thread Creation Rules:
- author_id must be a valid user
- category_id must exist
- title and content must be non-empty
- tag_ids (optional) must reference approved tags
- The API creates both the thread and first post atomically
- Vary categories, tags, and content across runs for diversity
""",
        tools=[
            "list_users",
            "list_categories",
            "list_tags",
            "create_thread",
        ],
        sampler=_sample_create_thread,
        task_prompt=lambda p: (
            "Create a new thread in a forum category. "
            "Choose a user as author, pick a relevant category, write a title and opening post, "
            "and optionally attach 1–3 tags."
        ),
        postconditions=_postcond_create_thread,
    ),
    "CREATE_POST": IntentDef(
        name="CREATE_POST",
        brief="Reply to an open thread with a new post.",
        informed_rules="""\
Forum Post Creation Rules:
- Thread must be open (status='open'); cannot post to closed threads
- author_id must be a valid user
- content must be non-empty
""",
        tools=[
            "list_categories",
            "list_threads_in_category",
            "get_thread",
            "list_users",
            "create_post",
        ],
        sampler=_sample_create_post,
        task_prompt=lambda p: (
            f"Reply to thread '{p['thread_id']}'. "
            "Choose a user as the post author and write a relevant reply."
        ),
        postconditions=_postcond_create_post,
    ),
    "CLOSE_THREAD": IntentDef(
        name="CLOSE_THREAD",
        brief="Close an open thread as a moderator or admin.",
        informed_rules="""\
Forum Thread Moderation Rules:
- Only moderators or admins can close threads (role must be 'moderator' or 'admin')
- Thread must be open (status='open')
- actor_id must have moderator or admin role
""",
        tools=[
            "list_categories",
            "list_threads_in_category",
            "list_users",
            "close_thread",
        ],
        sampler=_sample_close_thread,
        task_prompt=lambda p: (
            f"Close thread '{p['thread_id']}' as moderator/admin '{p['actor_id']}'."
        ),
        postconditions=_postcond_close_thread,
    ),
}

# ── Synthesizer classes ───────────────────────────────────────────────────────


class ForumAgentSynthesizer(DefaultAgentSynthesizer):
    def __init__(self) -> None:
        super().__init__(
            name="forum_agent",
            description="LLM agent executes forum content intents via Forum APIs",
            tool_registry=FORUM_TOOL_REGISTRY,
            intents=FORUM_INTENTS,
            env_name="Forum",
        )


class ForumGeneralistSynthesizer(GeneralistSynthesizer):
    INTENT_TO_WRITE_TOOLS = {
        "CREATE_THREAD": {"create_thread"},
        "CREATE_POST": {"create_post"},
        "CLOSE_THREAD": {"close_thread"},
    }

    def __init__(self) -> None:
        super().__init__(
            name="forum_generalist",
            description=(
                "Goal-directed agent that observes DB state, selects an appropriate intent "
                "from the bootstrap library, and executes it — no pre-assigned task."
            ),
            tool_registry=FORUM_TOOL_REGISTRY,
            bootstrap_intents=FORUM_INTENTS,
            env_name="Forum",
        )

    def _init_evolution(self) -> None:
        from pathlib import Path

        from synthesize.evolution.analyzer import TrajectoryAnalyzer
        from synthesize.evolution.engine import EvolutionEngine
        from synthesize.evolution.models import EvolvedIntent, IntentLibrary
        from synthesize.evolution.store import TrajectoryStore
        from synthesize.synthesizer.agent_synthesizer import MODEL, PROXY_BASE_URL

        runs_root = Path(".runs") / "evolution" / "forum"
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
            for name, intent_def in FORUM_INTENTS.items():
                library.add_intent(EvolvedIntent.from_intent_def(intent_def))

        self.evolution_engine = engine
        self.intent_library = library
        self.library_path = library_path
