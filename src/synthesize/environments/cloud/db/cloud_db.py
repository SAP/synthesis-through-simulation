"""SQLite persistence layer for the Cloud Computing Platform environment."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synthesize.environments.cloud.envscaler_class import CloudComputingPlatform

CLOUD_DB_DIR = Path(__file__).parent.parent.parent.parent.parent / ".runs" / "cloud_data"
DB_PATH: Path = CLOUD_DB_DIR / "cloud.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS instances (
    instance_id     TEXT PRIMARY KEY,
    instance_type   TEXT,
    state           TEXT,
    region          TEXT,
    availability_zone TEXT,
    image_id        TEXT,
    subnet_id       TEXT,
    owner_account   TEXT,
    public_ip       TEXT,
    private_ip      TEXT
);
CREATE TABLE IF NOT EXISTS vpcs (
    vpc_id          TEXT PRIMARY KEY,
    cidr_block      TEXT,
    region          TEXT,
    state           TEXT,
    owner_account   TEXT
);
CREATE TABLE IF NOT EXISTS subnets (
    subnet_id       TEXT PRIMARY KEY,
    vpc_id          TEXT,
    availability_zone TEXT,
    cidr_block      TEXT
);
CREATE TABLE IF NOT EXISTS security_groups (
    group_id        TEXT PRIMARY KEY,
    vpc_id          TEXT,
    name            TEXT,
    description     TEXT
);
CREATE TABLE IF NOT EXISTS images (
    image_id        TEXT PRIMARY KEY,
    name            TEXT,
    operating_system TEXT,
    visibility      TEXT,
    owner_account   TEXT
);
CREATE TABLE IF NOT EXISTS accounts (
    account_id      TEXT PRIMARY KEY,
    name            TEXT,
    role            TEXT,
    billing_plan    TEXT
);
"""


def init_db(db_path: Path | None = None) -> None:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()


def sync_from_env(env: "CloudComputingPlatform", db_path: Path | None = None) -> None:
    """Upsert all in-memory state from the env instance to SQLite."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    c = conn.cursor()

    for inst in env.instances.values():
        c.execute("""
            INSERT OR REPLACE INTO instances
            (instance_id, instance_type, state, region, availability_zone,
             image_id, subnet_id, owner_account, public_ip, private_ip)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (inst.get("instance_id"), inst.get("instance_type"), inst.get("state"),
              inst.get("region"), inst.get("availability_zone"), inst.get("image_id"),
              inst.get("subnet_id"), inst.get("owner_account"),
              inst.get("public_ip"), inst.get("private_ip")))

    for vpc in env.vpcs.values():
        c.execute("""
            INSERT OR REPLACE INTO vpcs (vpc_id, cidr_block, region, state, owner_account)
            VALUES (?,?,?,?,?)
        """, (vpc.get("vpc_id"), vpc.get("cidr_block"), vpc.get("region"),
              vpc.get("state"), vpc.get("owner_account")))

    for subnet in env.subnets.values():
        c.execute("""
            INSERT OR REPLACE INTO subnets (subnet_id, vpc_id, availability_zone, cidr_block)
            VALUES (?,?,?,?)
        """, (subnet.get("subnet_id"), subnet.get("vpc_id"),
              subnet.get("availability_zone"), subnet.get("cidr_block")))

    for sg in env.security_groups.values():
        c.execute("""
            INSERT OR REPLACE INTO security_groups (group_id, vpc_id, name, description)
            VALUES (?,?,?,?)
        """, (sg.get("group_id"), sg.get("vpc_id"), sg.get("name"), sg.get("description")))

    for img in env.images.values():
        c.execute("""
            INSERT OR REPLACE INTO images (image_id, name, operating_system, visibility, owner_account)
            VALUES (?,?,?,?,?)
        """, (img.get("image_id"), img.get("name"), img.get("operating_system"),
              img.get("visibility"), img.get("owner_account")))

    for acc in env.accounts.values():
        billing_plan = ""
        bi = acc.get("billing_info", {})
        if isinstance(bi, dict):
            billing_plan = bi.get("plan", "")
        c.execute("""
            INSERT OR REPLACE INTO accounts (account_id, name, role, billing_plan)
            VALUES (?,?,?,?)
        """, (acc.get("account_id"), acc.get("name"), acc.get("role"), billing_plan))

    conn.commit()
    conn.close()


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    return sqlite3.connect(str(db_path or DB_PATH))
