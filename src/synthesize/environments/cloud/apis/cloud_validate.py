"""VPR validation for the Cloud Computing Platform environment."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from synthesize.environments.cloud.db import cloud_db


def run(db_path: Path | None = None, as_json: bool = False):
    """Check structural validity of the cloud DB state."""
    path = db_path or cloud_db.DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    results = []

    def check(category: str, rule: str, sql: str) -> None:
        count = conn.execute(sql).fetchone()[0]
        results.append({
            "category": category,
            "rule": rule,
            "status": "PASS" if count == 0 else "FAIL",
            "violation_count": count,
        })

    # Instances must have valid state values
    check("Instances", "state must be running/stopped/terminated",
          "SELECT COUNT(*) FROM instances WHERE state NOT IN ('running','stopped','terminated')")

    # Instances must reference valid images
    check("Instances", "image_id must reference known image",
          "SELECT COUNT(*) FROM instances WHERE image_id NOT IN (SELECT image_id FROM images) "
          "AND image_id IS NOT NULL")

    # Instances must reference valid subnets
    check("Instances", "subnet_id must reference known subnet",
          "SELECT COUNT(*) FROM instances WHERE subnet_id NOT IN (SELECT subnet_id FROM subnets) "
          "AND subnet_id IS NOT NULL")

    # VPCs must have valid state
    check("VPCs", "vpc state must be available/pending",
          "SELECT COUNT(*) FROM vpcs WHERE state NOT IN ('available','pending') AND state IS NOT NULL")

    # Subnets must reference valid VPCs
    check("Subnets", "subnet vpc_id must reference known vpc",
          "SELECT COUNT(*) FROM subnets WHERE vpc_id NOT IN (SELECT vpc_id FROM vpcs) "
          "AND vpc_id IS NOT NULL")

    # Security groups must reference valid VPCs
    check("SecurityGroups", "group vpc_id must reference known vpc",
          "SELECT COUNT(*) FROM security_groups WHERE vpc_id NOT IN (SELECT vpc_id FROM vpcs) "
          "AND vpc_id IS NOT NULL")

    conn.close()
    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    vpr = passed / total if total > 0 else 1.0

    if as_json:
        return {"vpr": vpr, "checks": results, "passed": passed, "total": total}
    return vpr
