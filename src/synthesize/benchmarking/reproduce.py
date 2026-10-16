"""
DB reproduction from Langfuse dataset items.

reproduce_db() replays the write steps from a DatasetItem against a fresh
baseline DB to reconstruct the final DB state. This allows any team member
with a Langfuse dataset item to reproduce a run's DB locally, without needing
the original .runs/ directory.

Only non-error write operations are replayed (read ops like list_employees
do not modify state and are skipped).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from synthesize.models import DatasetItem

# Environments for which reproduce_db is fully implemented.
_SUPPORTED_ENVS = {"it_management"}

# Tool names that are read-only (do not modify DB state).
# All other tools in the agent's tool registry are treated as writes.
_READ_ONLY_TOOLS = {
    "list_employees",
    "list_it_staff",
    "get_employee",
    "get_employee_by_email",
    "get_ticket",
    "list_tickets_by_priority",
    "list_tickets_raised_by",
    "list_tickets_assigned_to",
    # HR read tools
    "get_employee_details",
    "list_departments",
    "list_positions",
    "list_benefits",
    "get_benefit",
    "list_succession_plans",
    "get_succession_plan",
}


def reproduce_db(item: DatasetItem, env: str, out_path: Path | None = None) -> Path:
    """Replay item.input.steps against a fresh baseline DB to reproduce the final state.

    Steps:
      1. Run setup() for the given env to create a fresh DB at a temp path
      2. For each non-error, non-read-only step in item.input.steps:
         look up the API function by tool name and call it with step.args
      3. Copy the result to out_path (or a temp file) and return the path

    Args:
        item: DatasetItem containing the steps to replay
        env: environment name — must be in _SUPPORTED_ENVS
        out_path: where to save the reproduced DB (default: temp file).
                  On success: caller is responsible for deleting when done.
                  On failure: deleted if we created it (out_path was None) or if it
                  did not exist before the call. Pre-existing caller files are left
                  on disk (but may have been overwritten if the copy succeeded before
                  the error).

    Returns:
        Path to the reproduced snapshot.db

    Raises:
        NotImplementedError: if env is not in _SUPPORTED_ENVS

    Note: not safe for concurrent calls on the same env — the function temporarily
    mutates the env's module-level DB_PATH and restores it in a finally block.
    """
    if env not in _SUPPORTED_ENVS:
        raise NotImplementedError(f"reproduce_db not yet implemented for env: {env!r}")

    # Track whether we created out_path — must be determined BEFORE mkstemp creates the file
    _created_by_us = out_path is None
    if out_path is None:
        fd, tmp_file = tempfile.mkstemp(prefix="synthesis_reproduced_", suffix=".db")
        os.close(fd)
        out_path = Path(tmp_file)

    # Only clean up on failure if we created or would-create this path.
    # Use _created_by_us instead of out_path.exists() because mkstemp always creates the file
    # immediately, making .exists() return True even for our newly-created temp paths.
    _should_cleanup_on_failure = _created_by_us or not out_path.exists()

    # Save original DB_PATH so module state can be restored on error
    db_mod = _get_env_db_module(env)
    orig_db_path = db_mod.DB_PATH if db_mod is not None else None

    try:
        # Set up a fresh DB in a temp location
        with tempfile.TemporaryDirectory(prefix="synthesis_setup_") as tmp:
            tmp_db = Path(tmp) / f"{env}.db"
            _setup_env(tmp_db, env)
            shutil.copy2(tmp_db, out_path)
            # Update DB_PATH after copy succeeds: out_path now has valid data.
            # tmp_db is still alive here (TemporaryDirectory not yet exited).
            if db_mod is not None:
                db_mod.DB_PATH = out_path
        # tmp_db is now deleted (TemporaryDirectory exited above).
        # db_mod.DB_PATH points to out_path which holds the valid baseline DB.

        # Replay write steps
        tool_registry = _get_tool_registry(env, out_path)
        write_steps = [
            s for s in item.input.steps if not s.is_error and s.tool not in _READ_ONLY_TOOLS
        ]

        for step in write_steps:
            fn = tool_registry.get(step.tool)
            if fn is None:
                print(f"  Warning: unknown tool {step.tool!r} — skipping")
                continue
            try:
                fn(**step.args)
            except Exception as exc:
                print(f"  Warning: {step.tool}({step.args}) raised {exc!r} — skipping")
    except Exception:
        # Clean up out_path on failure only if we created it or it didn't exist before the call.
        # Pre-existing caller-provided files are left on disk (though they may have been
        # overwritten if shutil.copy2 succeeded before the failure).
        if _should_cleanup_on_failure and out_path.exists():
            out_path.unlink()
        raise
    finally:
        # Always restore original DB_PATH — reproduce_db must not leave module state changed
        if db_mod is not None:
            db_mod.DB_PATH = orig_db_path

    return out_path


def _get_env_db_module(env: str):
    """Return the db module for the given env, for DB_PATH save/restore."""
    if env == "it_management":
        import synthesize.environments.it_management.db.db as _db_mod

        return _db_mod
    return None


def _setup_env(db_path: Path, env: str = "it_management") -> None:
    """Initialise a fresh DB at db_path for the given env.

    Only creates schema and inserts seed data. Does not set DB_PATH — the
    caller (reproduce_db) is responsible for managing DB_PATH state.

    Note: only it_management is supported. To add a new env, extend
    _SUPPORTED_ENVS in reproduce_db and add a matching branch here.
    """
    if env != "it_management":
        raise NotImplementedError(f"_setup_env not yet implemented for env: {env!r}")
    import sqlite3

    from synthesize.environments.it_management.db.db import (
        _SCHEMA_PATH,  # type: ignore[attr-defined]
    )
    from synthesize.environments.it_management.db.reference_data import EMPLOYEES

    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(_SCHEMA_PATH.read_text())
        conn.executemany(
            "INSERT INTO employee (emp_id, name, email, category, level, salary, doj, is_active)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            EMPLOYEES,
        )


def _get_tool_registry(env: str, db_path: Path) -> dict:
    """Return a tool registry dict for the given env.

    Does not mutate DB_PATH — the caller (reproduce_db) is responsible for
    ensuring DB_PATH points to db_path before the returned functions are called.
    """
    if env == "it_management":
        from synthesize.environments.it_management.apis.employees import (
            get_employee,
            get_employee_by_email,
            list_employees,
            list_it_staff,
        )
        from synthesize.environments.it_management.apis.tickets import (
            assign_ticket,
            create_ticket,
            delete_ticket,
            get_ticket,
            list_tickets_assigned_to,
            list_tickets_by_priority,
            list_tickets_raised_by,
            resolve_ticket,
            update_ticket,
        )

        return {
            "list_employees": list_employees,
            "list_it_staff": list_it_staff,
            "get_employee": get_employee,
            "get_employee_by_email": get_employee_by_email,
            "create_ticket": create_ticket,
            "assign_ticket": assign_ticket,
            "resolve_ticket": resolve_ticket,
            "update_ticket": update_ticket,
            "delete_ticket": delete_ticket,
            "get_ticket": get_ticket,
            "list_tickets_by_priority": list_tickets_by_priority,
            "list_tickets_raised_by": list_tickets_raised_by,
            "list_tickets_assigned_to": list_tickets_assigned_to,
        }
    else:
        raise NotImplementedError(f"reproduce_db not yet implemented for env: {env!r}")
