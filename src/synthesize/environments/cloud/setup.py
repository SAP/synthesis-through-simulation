"""
setup.py — initialise the Cloud Computing Platform DB from the seed config.

Run via:
    python -m synthesize.environments.cloud.setup
    synthesize --env cloud setup
"""

from __future__ import annotations

from pathlib import Path

from synthesize.environments.cloud.apis import cloud_apis
from synthesize.environments.cloud.db import cloud_db


def setup(db_path: Path | None = None) -> None:
    target = db_path or cloud_db.DB_PATH
    print("=== Cloud Computing Platform Setup ===")
    print(f"DB: {target}")

    # Remove stale DB so we get a clean slate
    if target.exists():
        target.unlink()

    cloud_apis.init_env(db_path=target)

    import sqlite3
    con = sqlite3.connect(str(target))
    n_instances = con.execute("SELECT COUNT(*) FROM instances").fetchone()[0]
    n_vpcs = con.execute("SELECT COUNT(*) FROM vpcs").fetchone()[0]
    n_subnets = con.execute("SELECT COUNT(*) FROM subnets").fetchone()[0]
    n_sgs = con.execute("SELECT COUNT(*) FROM security_groups").fetchone()[0]
    n_images = con.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    n_accounts = con.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    con.close()

    print(f"  Instances:       {n_instances}")
    print(f"  VPCs:            {n_vpcs}")
    print(f"  Subnets:         {n_subnets}")
    print(f"  Security Groups: {n_sgs}")
    print(f"  Images:          {n_images}")
    print(f"  Accounts:        {n_accounts}")
    print(f"\n=== Clean DB ready: {target} ===\n")


if __name__ == "__main__":
    setup()
