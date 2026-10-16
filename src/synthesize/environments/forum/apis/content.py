"""
Thread, post, and tag management API for the Online Discussion Forum.

Business rules enforced:
  - Each thread must have exactly one first post (created atomically with the thread)
  - Tags must be approved before use in thread creation
  - Only registered, active users can create content
  - Only authors or moderators/admins can edit/delete posts
  - Only moderators/admins can close, reopen, delete threads or change their category
  - Posting to a closed or deleted thread is not allowed
  - Thread deletion sets status='deleted'; posts are retained (soft delete)
  - Deleting a first post deletes the entire thread
  - tag usage_count is incremented when added to a thread and decremented when removed
  - last_activity on thread is updated whenever a new post is added

Auto-managed fields: last_activity (thread), usage_count (tag), is_first_post (post)
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional

from synthesize.environments.forum.db.db import get_conn

VALID_ROLES = {"member", "moderator", "admin"}
VALID_THREAD_STATUSES = {"open", "closed", "deleted"}


def _now() -> str:
    return datetime.datetime.utcnow().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.date.today().isoformat()


def _uid() -> str:
    return str(uuid.uuid4())[:8].upper()


def _is_moderator(conn, user_id: str) -> bool:
    row = conn.execute(
        "SELECT role FROM forum_user WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row is not None and row["role"] in ("moderator", "admin")


# ── User read ─────────────────────────────────────────────────────────────────


def get_user(user_id: str) -> Dict[str, Any]:
    """Return a forum user record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM forum_user WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        raise LookupError(f"User not found: {user_id!r}")
    return dict(row)


def get_user_by_username(username: str) -> Dict[str, Any]:
    """Return a user by their username.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM forum_user WHERE username = ?", (username,)
        ).fetchone()
    if row is None:
        raise LookupError(f"No user with username: {username!r}")
    return dict(row)


def list_users(role: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return active forum users, optionally filtered by role."""
    query = "SELECT * FROM forum_user WHERE is_active = 1"
    params: list = []
    if role is not None:
        if role not in VALID_ROLES:
            raise ValueError(f"role must be one of {sorted(VALID_ROLES)}, got {role!r}")
        query += " AND role = ?"
        params.append(role)
    query += " ORDER BY reputation DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ── Category read ─────────────────────────────────────────────────────────────


def get_category(category_id: str) -> Dict[str, Any]:
    """Return a category record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM category WHERE category_id = ?", (category_id,)
        ).fetchone()
    if row is None:
        raise LookupError(f"Category not found: {category_id!r}")
    return dict(row)


def list_categories() -> List[Dict[str, Any]]:
    """Return all active categories."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM category WHERE is_active = 1 ORDER BY category_id"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Tag read ──────────────────────────────────────────────────────────────────


def get_tag(tag_id: str) -> Dict[str, Any]:
    """Return a tag record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tag WHERE tag_id = ?", (tag_id,)).fetchone()
    if row is None:
        raise LookupError(f"Tag not found: {tag_id!r}")
    return dict(row)


def get_tag_by_name(name: str) -> Dict[str, Any]:
    """Return a tag by its name.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tag WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise LookupError(f"No tag with name: {name!r}")
    return dict(row)


def list_tags(approved_only: bool = True) -> List[Dict[str, Any]]:
    """Return tags, optionally only approved ones."""
    query = "SELECT * FROM tag WHERE 1=1"
    if approved_only:
        query += " AND is_approved = 1"
    query += " ORDER BY usage_count DESC, name"
    with get_conn() as conn:
        rows = conn.execute(query).fetchall()
    return [dict(r) for r in rows]


# ── Thread read ───────────────────────────────────────────────────────────────


def get_thread(thread_id: str) -> Dict[str, Any]:
    """Return a thread record.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM thread WHERE thread_id = ?", (thread_id,)).fetchone()
    if row is None:
        raise LookupError(f"Thread not found: {thread_id!r}")
    return dict(row)


def list_threads_in_category(
    category_id: str, status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return threads in a category, ordered by last_activity descending."""
    query = "SELECT * FROM thread WHERE category_id = ?"
    params: list = [category_id]
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY last_activity DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def list_threads_by_tag(tag_id: str) -> List[Dict[str, Any]]:
    """Return all threads tagged with the given tag."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT t.* FROM thread t
               JOIN thread_tag tt ON t.thread_id = tt.thread_id
               WHERE tt.tag_id = ? ORDER BY t.last_activity DESC""",
            (tag_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_thread_tags(thread_id: str) -> List[Dict[str, Any]]:
    """Return all tags on a thread."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT tg.* FROM tag tg JOIN thread_tag tt ON tg.tag_id = tt.tag_id WHERE tt.thread_id = ?",
            (thread_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_posts_in_thread(thread_id: str) -> List[Dict[str, Any]]:
    """Return all posts in a thread, oldest first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM post WHERE thread_id = ? ORDER BY created_date, post_id",
            (thread_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_post(post_id: str) -> Dict[str, Any]:
    """Return a single post.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM post WHERE post_id = ?", (post_id,)).fetchone()
    if row is None:
        raise LookupError(f"Post not found: {post_id!r}")
    return dict(row)


# ── Thread write ──────────────────────────────────────────────────────────────


def create_thread(
    author_id: str,
    category_id: str,
    title: str,
    content: str,
    tag_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a new thread with an initial post. Tags must be approved.

    Raises LookupError if author, category, or any tag not found.
    Raises ValueError if author is inactive, category is inactive, any tag is not approved,
    or title/content is empty.
    """
    if not title or not title.strip():
        raise ValueError("title must be non-empty")
    if not content or not content.strip():
        raise ValueError("content must be non-empty")

    with get_conn() as conn:
        author = conn.execute(
            "SELECT is_active FROM forum_user WHERE user_id = ?", (author_id,)
        ).fetchone()
        if author is None:
            raise LookupError(f"User not found: {author_id!r}")
        if not author["is_active"]:
            raise ValueError(f"User {author_id!r} is not active")

        cat = conn.execute(
            "SELECT is_active FROM category WHERE category_id = ?", (category_id,)
        ).fetchone()
        if cat is None:
            raise LookupError(f"Category not found: {category_id!r}")
        if not cat["is_active"]:
            raise ValueError(f"Category {category_id!r} is not active")

        validated_tags = []
        for tag_id in (tag_ids or []):
            tag = conn.execute("SELECT is_approved FROM tag WHERE tag_id = ?", (tag_id,)).fetchone()
            if tag is None:
                raise LookupError(f"Tag not found: {tag_id!r}")
            if not tag["is_approved"]:
                raise ValueError(f"Tag {tag_id!r} is not approved")
            validated_tags.append(tag_id)

        now = _now()
        thread_id = "THR-" + _uid()
        post_id = "PST-" + _uid()

        conn.execute(
            """INSERT INTO thread (thread_id, title, category_id, author_id, created_date, last_activity, status, view_count)
               VALUES (?, ?, ?, ?, ?, ?, 'open', 0)""",
            (thread_id, title.strip(), category_id, author_id, now, now),
        )
        conn.execute(
            """INSERT INTO post (post_id, thread_id, author_id, content, created_date, is_first_post)
               VALUES (?, ?, ?, ?, ?, 1)""",
            (post_id, thread_id, author_id, content.strip(), now),
        )
        for tag_id in validated_tags:
            conn.execute(
                "INSERT INTO thread_tag (thread_id, tag_id) VALUES (?, ?)",
                (thread_id, tag_id),
            )
            conn.execute(
                "UPDATE tag SET usage_count = usage_count + 1 WHERE tag_id = ?", (tag_id,)
            )
    return get_thread(thread_id)


def create_post(author_id: str, thread_id: str, content: str) -> Dict[str, Any]:
    """Add a reply post to an open thread.

    Raises LookupError if author or thread not found.
    Raises ValueError if author is inactive or thread is not open.
    """
    if not content or not content.strip():
        raise ValueError("content must be non-empty")

    with get_conn() as conn:
        author = conn.execute(
            "SELECT is_active FROM forum_user WHERE user_id = ?", (author_id,)
        ).fetchone()
        if author is None:
            raise LookupError(f"User not found: {author_id!r}")
        if not author["is_active"]:
            raise ValueError(f"User {author_id!r} is not active")

        thread = conn.execute("SELECT status FROM thread WHERE thread_id = ?", (thread_id,)).fetchone()
        if thread is None:
            raise LookupError(f"Thread not found: {thread_id!r}")
        if thread["status"] != "open":
            raise ValueError(f"Cannot post to {thread['status']!r} thread {thread_id!r}")

        now = _now()
        post_id = "PST-" + _uid()
        conn.execute(
            """INSERT INTO post (post_id, thread_id, author_id, content, created_date, is_first_post)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (post_id, thread_id, author_id, content.strip(), now),
        )
        conn.execute(
            "UPDATE thread SET last_activity = ? WHERE thread_id = ?", (now, thread_id)
        )
    return get_post(post_id)


def edit_post(post_id: str, editor_id: str, content: str) -> Dict[str, Any]:
    """Edit a post's content. Only the author or a moderator/admin may edit.

    Raises LookupError if post or editor not found.
    Raises ValueError if editor is not authorised.
    """
    if not content or not content.strip():
        raise ValueError("content must be non-empty")

    with get_conn() as conn:
        post = conn.execute("SELECT * FROM post WHERE post_id = ?", (post_id,)).fetchone()
        if post is None:
            raise LookupError(f"Post not found: {post_id!r}")

        editor = conn.execute(
            "SELECT is_active, role FROM forum_user WHERE user_id = ?", (editor_id,)
        ).fetchone()
        if editor is None:
            raise LookupError(f"User not found: {editor_id!r}")
        if not editor["is_active"]:
            raise ValueError(f"User {editor_id!r} is not active")

        if post["author_id"] != editor_id and editor["role"] not in ("moderator", "admin"):
            raise ValueError(
                f"User {editor_id!r} is not authorised to edit post {post_id!r}"
            )

        conn.execute(
            "UPDATE post SET content = ?, edited_date = ? WHERE post_id = ?",
            (content.strip(), _now(), post_id),
        )
    return get_post(post_id)


def delete_post(post_id: str, actor_id: str) -> Dict[str, Any]:
    """Delete a post. Deleting the first post deletes the entire thread.

    Raises LookupError if post or actor not found.
    Raises ValueError if actor is not authorised.
    """
    with get_conn() as conn:
        post = conn.execute("SELECT * FROM post WHERE post_id = ?", (post_id,)).fetchone()
        if post is None:
            raise LookupError(f"Post not found: {post_id!r}")

        actor = conn.execute(
            "SELECT is_active, role FROM forum_user WHERE user_id = ?", (actor_id,)
        ).fetchone()
        if actor is None:
            raise LookupError(f"User not found: {actor_id!r}")

        if post["author_id"] != actor_id and actor["role"] not in ("moderator", "admin"):
            raise ValueError(
                f"User {actor_id!r} is not authorised to delete post {post_id!r}"
            )

        deleted = dict(post)
        if post["is_first_post"]:
            # Deleting the first post removes the whole thread
            thread_id = post["thread_id"]
            tags = conn.execute(
                "SELECT tag_id FROM thread_tag WHERE thread_id = ?", (thread_id,)
            ).fetchall()
            for t in tags:
                conn.execute(
                    "UPDATE tag SET usage_count = MAX(0, usage_count - 1) WHERE tag_id = ?",
                    (t["tag_id"],),
                )
            conn.execute("DELETE FROM thread_tag WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM post WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM thread WHERE thread_id = ?", (thread_id,))
        else:
            conn.execute("DELETE FROM post WHERE post_id = ?", (post_id,))
    return deleted


def close_thread(thread_id: str, actor_id: str) -> Dict[str, Any]:
    """Close a thread to prevent further replies. Author or moderator/admin only.

    Raises LookupError if not found.
    Raises ValueError if thread is not open or actor is not authorised.
    """
    with get_conn() as conn:
        thread = conn.execute("SELECT * FROM thread WHERE thread_id = ?", (thread_id,)).fetchone()
        if thread is None:
            raise LookupError(f"Thread not found: {thread_id!r}")
        if thread["status"] != "open":
            raise ValueError(f"Thread {thread_id!r} is already {thread['status']!r}")

        actor = conn.execute(
            "SELECT is_active, role FROM forum_user WHERE user_id = ?", (actor_id,)
        ).fetchone()
        if actor is None:
            raise LookupError(f"User not found: {actor_id!r}")
        if thread["author_id"] != actor_id and actor["role"] not in ("moderator", "admin"):
            raise ValueError(
                f"User {actor_id!r} is not authorised to close thread {thread_id!r}"
            )

        conn.execute("UPDATE thread SET status = 'closed' WHERE thread_id = ?", (thread_id,))
    return get_thread(thread_id)


def reopen_thread(thread_id: str, actor_id: str) -> Dict[str, Any]:
    """Reopen a closed thread. Moderator/admin only.

    Raises LookupError if not found.
    Raises ValueError if not closed or actor lacks permission.
    """
    with get_conn() as conn:
        thread = conn.execute("SELECT status FROM thread WHERE thread_id = ?", (thread_id,)).fetchone()
        if thread is None:
            raise LookupError(f"Thread not found: {thread_id!r}")
        if thread["status"] != "closed":
            raise ValueError(f"Thread {thread_id!r} is not closed (status: {thread['status']!r})")

        actor = conn.execute("SELECT role FROM forum_user WHERE user_id = ?", (actor_id,)).fetchone()
        if actor is None:
            raise LookupError(f"User not found: {actor_id!r}")
        if actor["role"] not in ("moderator", "admin"):
            raise ValueError("Only moderators/admins can reopen threads")

        conn.execute("UPDATE thread SET status = 'open' WHERE thread_id = ?", (thread_id,))
    return get_thread(thread_id)


def update_thread_category(thread_id: str, new_category_id: str, actor_id: str) -> Dict[str, Any]:
    """Move a thread to a different category. Moderator/admin only.

    Raises LookupError if not found.
    Raises ValueError if actor lacks permission or category is inactive.
    """
    with get_conn() as conn:
        thread = conn.execute("SELECT thread_id FROM thread WHERE thread_id = ?", (thread_id,)).fetchone()
        if thread is None:
            raise LookupError(f"Thread not found: {thread_id!r}")

        cat = conn.execute(
            "SELECT is_active FROM category WHERE category_id = ?", (new_category_id,)
        ).fetchone()
        if cat is None:
            raise LookupError(f"Category not found: {new_category_id!r}")
        if not cat["is_active"]:
            raise ValueError(f"Category {new_category_id!r} is not active")

        actor = conn.execute("SELECT role FROM forum_user WHERE user_id = ?", (actor_id,)).fetchone()
        if actor is None:
            raise LookupError(f"User not found: {actor_id!r}")
        if actor["role"] not in ("moderator", "admin"):
            raise ValueError("Only moderators/admins can move threads")

        conn.execute(
            "UPDATE thread SET category_id = ? WHERE thread_id = ?", (new_category_id, thread_id)
        )
    return get_thread(thread_id)


def add_tag_to_thread(thread_id: str, tag_id: str, actor_id: str) -> Dict[str, Any]:
    """Add an approved tag to a thread. Author or moderator/admin only.

    Raises LookupError if not found.
    Raises ValueError if tag is not approved or actor is not authorised.
    """
    with get_conn() as conn:
        thread = conn.execute("SELECT * FROM thread WHERE thread_id = ?", (thread_id,)).fetchone()
        if thread is None:
            raise LookupError(f"Thread not found: {thread_id!r}")

        tag = conn.execute("SELECT is_approved FROM tag WHERE tag_id = ?", (tag_id,)).fetchone()
        if tag is None:
            raise LookupError(f"Tag not found: {tag_id!r}")
        if not tag["is_approved"]:
            raise ValueError(f"Tag {tag_id!r} is not approved")

        actor = conn.execute(
            "SELECT role FROM forum_user WHERE user_id = ?", (actor_id,)
        ).fetchone()
        if actor is None:
            raise LookupError(f"User not found: {actor_id!r}")
        if thread["author_id"] != actor_id and actor["role"] not in ("moderator", "admin"):
            raise ValueError(f"User {actor_id!r} is not authorised to tag thread {thread_id!r}")

        existing = conn.execute(
            "SELECT 1 FROM thread_tag WHERE thread_id = ? AND tag_id = ?", (thread_id, tag_id)
        ).fetchone()
        if existing:
            raise ValueError(f"Tag {tag_id!r} is already on thread {thread_id!r}")

        conn.execute("INSERT INTO thread_tag (thread_id, tag_id) VALUES (?, ?)", (thread_id, tag_id))
        conn.execute("UPDATE tag SET usage_count = usage_count + 1 WHERE tag_id = ?", (tag_id,))
    return get_thread(thread_id)


def remove_tag_from_thread(thread_id: str, tag_id: str, actor_id: str) -> Dict[str, Any]:
    """Remove a tag from a thread. Author or moderator/admin only.

    Raises LookupError if tag not on thread.
    """
    with get_conn() as conn:
        thread = conn.execute("SELECT author_id FROM thread WHERE thread_id = ?", (thread_id,)).fetchone()
        if thread is None:
            raise LookupError(f"Thread not found: {thread_id!r}")

        actor = conn.execute("SELECT role FROM forum_user WHERE user_id = ?", (actor_id,)).fetchone()
        if actor is None:
            raise LookupError(f"User not found: {actor_id!r}")
        if thread["author_id"] != actor_id and actor["role"] not in ("moderator", "admin"):
            raise ValueError(f"User {actor_id!r} is not authorised to modify tags on thread {thread_id!r}")

        existing = conn.execute(
            "SELECT 1 FROM thread_tag WHERE thread_id = ? AND tag_id = ?", (thread_id, tag_id)
        ).fetchone()
        if not existing:
            raise LookupError(f"Tag {tag_id!r} is not on thread {thread_id!r}")

        conn.execute(
            "DELETE FROM thread_tag WHERE thread_id = ? AND tag_id = ?", (thread_id, tag_id)
        )
        conn.execute(
            "UPDATE tag SET usage_count = MAX(0, usage_count - 1) WHERE tag_id = ?", (tag_id,)
        )
    return get_thread(thread_id)


def add_tag(name: str, description: Optional[str] = None) -> Dict[str, Any]:
    """Propose a new tag (starts unapproved, requires moderator approval).

    Raises ValueError if tag name is empty or already exists.
    """
    if not name or not name.strip():
        raise ValueError("Tag name must be non-empty")

    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM tag WHERE name = ?", (name.strip(),)).fetchone():
            raise ValueError(f"Tag {name!r} already exists")
        tag_id = "TAG-" + _uid()
        conn.execute(
            "INSERT INTO tag (tag_id, name, description, usage_count, is_approved) VALUES (?, ?, ?, 0, 0)",
            (tag_id, name.strip(), description),
        )
    return get_tag(tag_id)


def approve_tag(tag_id: str, actor_id: str) -> Dict[str, Any]:
    """Approve a pending tag. Moderator/admin only.

    Raises LookupError if not found.
    Raises ValueError if already approved or actor lacks permission.
    """
    with get_conn() as conn:
        tag = conn.execute("SELECT is_approved FROM tag WHERE tag_id = ?", (tag_id,)).fetchone()
        if tag is None:
            raise LookupError(f"Tag not found: {tag_id!r}")
        if tag["is_approved"]:
            raise ValueError(f"Tag {tag_id!r} is already approved")

        actor = conn.execute("SELECT role FROM forum_user WHERE user_id = ?", (actor_id,)).fetchone()
        if actor is None:
            raise LookupError(f"User not found: {actor_id!r}")
        if actor["role"] not in ("moderator", "admin"):
            raise ValueError("Only moderators/admins can approve tags")

        conn.execute("UPDATE tag SET is_approved = 1 WHERE tag_id = ?", (tag_id,))
    return get_tag(tag_id)


def increment_thread_views(thread_id: str) -> Dict[str, Any]:
    """Increment the view counter for a thread.

    Raises LookupError if not found.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT thread_id FROM thread WHERE thread_id = ?", (thread_id,)).fetchone()
        if row is None:
            raise LookupError(f"Thread not found: {thread_id!r}")
        conn.execute(
            "UPDATE thread SET view_count = view_count + 1 WHERE thread_id = ?", (thread_id,)
        )
    return get_thread(thread_id)
