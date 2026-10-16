"""
Validation script: checks structural invariants against the Cloud DB.

Run directly:
    python -m synthesize.environments.cloud.validate
    python -m synthesize.environments.cloud.validate --db path/to/cloud.db
    python -m synthesize.environments.cloud.validate --json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from synthesize.environments.cloud.db import cloud_db

DB_PATH = cloud_db.DB_PATH


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


CHECKS = []


def check(category: str, rule: str):
    def decorator(fn):
        CHECKS.append({"category": category, "rule": rule, "fn": fn})
        return fn
    return decorator


@check("Instances", "state must be running/stopped/terminated")
def check_instance_state():
    return rows(
        "SELECT instance_id, state FROM instances "
        "WHERE state NOT IN ('running','stopped','terminated')"
    )


@check("Instances", "image_id must reference known image (if set)")
def check_instance_image_fk():
    return rows(
        "SELECT instance_id, image_id FROM instances "
        "WHERE image_id NOT IN (SELECT image_id FROM images) AND image_id IS NOT NULL"
    )


@check("Instances", "subnet_id must reference known subnet (if set)")
def check_instance_subnet_fk():
    return rows(
        "SELECT instance_id, subnet_id FROM instances "
        "WHERE subnet_id NOT IN (SELECT subnet_id FROM subnets) AND subnet_id IS NOT NULL"
    )


@check("VPCs", "state must be available or pending (if set)")
def check_vpc_state():
    return rows(
        "SELECT vpc_id, state FROM vpcs "
        "WHERE state NOT IN ('available','pending') AND state IS NOT NULL"
    )


@check("Subnets", "vpc_id must reference known VPC (if set)")
def check_subnet_vpc_fk():
    return rows(
        "SELECT subnet_id, vpc_id FROM subnets "
        "WHERE vpc_id NOT IN (SELECT vpc_id FROM vpcs) AND vpc_id IS NOT NULL"
    )


@check("SecurityGroups", "vpc_id must reference known VPC (if set)")
def check_sg_vpc_fk():
    return rows(
        "SELECT group_id, vpc_id FROM security_groups "
        "WHERE vpc_id NOT IN (SELECT vpc_id FROM vpcs) AND vpc_id IS NOT NULL"
    )


def run(as_json: bool = False, show_sample: int = 3) -> list:
    results = []
    for chk in CHECKS:
        violations = chk["fn"]()
        status = "PASS" if not violations else "FAIL"
        results.append({
            "category": chk["category"],
            "rule": chk["rule"],
            "status": status,
            "violation_count": len(violations),
            "sample": violations[:show_sample] if show_sample else [],
        })
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
    parser = argparse.ArgumentParser(description="Validate Cloud DB structural invariants")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.db:
        set_db(args.db)

    results = run(as_json=args.json, show_sample=3)
    if args.json:
        print(json.dumps(results, indent=2))

    failed = sum(1 for r in results if r["status"] == "FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
