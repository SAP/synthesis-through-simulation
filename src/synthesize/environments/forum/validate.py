"""
Validation script: business rules for the Forum DB.

Run directly:
    python -m synthesize.environments.forum.validate
    python -m synthesize.environments.forum.validate --db path/to/forum.db
    python -m synthesize.environments.forum.validate --json
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent / "db" / "forum.db"
DB_PATH = _DEFAULT_DB


def set_db(path: Path) -> None:
    global DB_PATH
    DB_PATH = Path(path)


def conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def rows(sql: str, params: tuple = ()) -> list:
    c = conn()
    result = c.execute(sql, params).fetchall()
    c.close()
    return [dict(r) for r in result]


def scalar(sql: str, params: tuple = ()) -> int:
    c = conn()
    result = c.execute(sql, params).fetchone()[0]
    c.close()
    return result


CHECKS = []


def check(category: str, rule: str):
    def decorator(fn):
        CHECKS.append({"category": category, "rule": rule, "fn": fn})
        return fn

    return decorator


# ── Checks ────────────────────────────────────────────────────────────────────


@check("Users", "role must be member/moderator/admin")
def check_user_role():
    return rows(
        "SELECT user_id, role FROM forum_user "
        "WHERE role NOT IN ('member', 'moderator', 'admin')"
    )


@check("Threads", "status must be open/closed/deleted")
def check_thread_status():
    return rows(
        "SELECT thread_id, status FROM thread "
        "WHERE status NOT IN ('open', 'closed', 'deleted')"
    )


@check("Threads", "All threads have exactly one first post")
def check_thread_has_one_first_post():
    return rows(
        """SELECT t.thread_id, COUNT(p.post_id) AS first_post_count
           FROM thread t
           LEFT JOIN post p ON t.thread_id = p.thread_id AND p.is_first_post = 1
           GROUP BY t.thread_id
           HAVING first_post_count != 1"""
    )


@check("Threads", "Thread author must be a known active user")
def check_thread_author_fk():
    return rows(
        """SELECT t.thread_id, t.author_id
           FROM thread t
           LEFT JOIN forum_user u ON t.author_id = u.user_id
           WHERE u.user_id IS NULL OR u.is_active = 0"""
    )


@check("Threads", "Thread must belong to an active category")
def check_thread_category_fk():
    return rows(
        """SELECT t.thread_id, t.category_id
           FROM thread t
           LEFT JOIN category c ON t.category_id = c.category_id
           WHERE c.category_id IS NULL OR c.is_active = 0"""
    )


@check("Posts", "Post author must be a known active user")
def check_post_author_fk():
    return rows(
        """SELECT p.post_id, p.author_id
           FROM post p
           LEFT JOIN forum_user u ON p.author_id = u.user_id
           WHERE u.user_id IS NULL OR u.is_active = 0"""
    )


@check("Posts", "Post content must be non-empty")
def check_post_content_non_empty():
    return rows(
        "SELECT post_id FROM post WHERE content IS NULL OR TRIM(content) = ''"
    )


@check("Posts", "All posts belong to a known thread")
def check_post_thread_fk():
    return rows(
        """SELECT p.post_id, p.thread_id
           FROM post p
           LEFT JOIN thread t ON p.thread_id = t.thread_id
           WHERE t.thread_id IS NULL"""
    )


@check("Tags", "Tags used in thread_tag must be approved")
def check_thread_tag_approved():
    return rows(
        """SELECT tt.thread_id, tt.tag_id
           FROM thread_tag tt
           JOIN tag t ON tt.tag_id = t.tag_id
           WHERE t.is_approved = 0"""
    )


@check("Tags", "thread_tag references must point to known threads and tags")
def check_thread_tag_fks():
    violations = []
    violations += rows(
        """SELECT tt.thread_id, tt.tag_id
           FROM thread_tag tt
           LEFT JOIN thread t ON tt.thread_id = t.thread_id
           WHERE t.thread_id IS NULL"""
    )
    violations += rows(
        """SELECT tt.thread_id, tt.tag_id
           FROM thread_tag tt
           LEFT JOIN tag tg ON tt.tag_id = tg.tag_id
           WHERE tg.tag_id IS NULL"""
    )
    return violations


# ── Runner ────────────────────────────────────────────────────────────────────


def run(as_json: bool = False, show_sample: int = 3) -> list:
    results = []
    for chk in CHECKS:
        violations = chk["fn"]()
        status = "PASS" if not violations else "FAIL"
        results.append(
            {
                "category": chk["category"],
                "rule": chk["rule"],
                "status": status,
                "violation_count": len(violations),
                "sample": violations[:show_sample] if show_sample else [],
            }
        )
        if not as_json:
            mark = "\033[32m✓\033[0m" if status == "PASS" else "\033[31m✗\033[0m"
            print(f"  {mark}  [{chk['category']}] {chk['rule']}")
            if violations and show_sample:
                for v in violations[:show_sample]:
                    print(f"       ↳ {v}")

    if not as_json:
        total = len(results)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = total - passed
        print("\n" + "─" * 60)
        print(f"  Checks:  {total}")
        print(f"  Passed:  \033[32m✓\033[0m {passed}")
        print(f"  Failed:    {failed}")
        if failed:
            print("\n  Failing checks:")
            for r in results:
                if r["status"] == "FAIL":
                    print(f"    \033[31m✗\033[0m  [{r['category']}] {r['rule']}  ({r['violation_count']} violations)")
        print("─" * 60)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Forum DB business rules")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.db:
        set_db(args.db)

    results = run(as_json=args.json, show_sample=3)

    if args.json:
        print(json.dumps(results, indent=2))

    sys.exit(1 if any(r["status"] == "FAIL" for r in results) else 0)


if __name__ == "__main__":
    main()
