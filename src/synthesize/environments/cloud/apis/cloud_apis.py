"""
Cloud Computing Platform API — wraps the EnvScaler CloudComputingPlatform class.

Each function delegates to the corresponding method on the live class instance
and syncs changes to SQLite so that GP EXPLORE can observe state.
"""

from __future__ import annotations

import json
from pathlib import Path

from synthesize.environments.cloud.db import cloud_db
from synthesize.environments.cloud.envscaler_class import CloudComputingPlatform

_ENV: CloudComputingPlatform | None = None
_SEED_CONFIG_PATH = Path(__file__).parent.parent / "seed_init_config.json"


# ── Environment lifecycle ──────────────────────────────────────────────────────

def init_env(db_path: Path | None = None) -> None:
    """Instantiate the cloud env from seed config and sync to SQLite."""
    global _ENV
    _ENV = CloudComputingPlatform()
    seed = json.loads(_SEED_CONFIG_PATH.read_text())
    _load_init_config(_ENV, seed)
    if db_path:
        cloud_db.DB_PATH = db_path
    target = cloud_db.DB_PATH
    cloud_db.init_db(db_path=target)
    cloud_db.sync_from_env(_ENV, db_path=target)


def _load_init_config(env: CloudComputingPlatform, cfg: dict) -> None:
    env.accounts = cfg.get("accounts", {})
    env.regions = cfg.get("regions", {})
    env.availability_zones = cfg.get("availability_zones", {})
    env.vpcs = cfg.get("vpcs", {})
    env.subnets = cfg.get("subnets", {})
    env.security_groups = cfg.get("security_groups", {})
    env.images = cfg.get("images", {})
    env.instances = cfg.get("instances", {})
    env.tags = cfg.get("tags", {})


def _sync() -> None:
    if _ENV is not None:
        cloud_db.sync_from_env(_ENV, db_path=cloud_db.DB_PATH)


def _call(fn_name: str, **kwargs) -> dict:
    """Call a method on _ENV, return result or error dict."""
    if _ENV is None:
        return {"error": "Environment not initialized. Call init_env() first."}
    try:
        result = getattr(_ENV, fn_name)(**kwargs)
        _sync()
        return result if isinstance(result, dict) else {"result": result}
    except Exception as exc:
        return {"error": str(exc)}


# ── READ tools ─────────────────────────────────────────────────────────────────

def get_region_by_name(region_name: str) -> dict:
    return _call("get_region_by_name", region_name=region_name)


def list_enabled_regions() -> dict:
    return _call("list_enabled_regions")


def list_availability_zones(region_name: str) -> dict:
    return _call("list_availability_zones", region_name=region_name)


def get_image_by_id(image_id: str) -> dict:
    return _call("get_image_by_id", image_id=image_id)


def list_public_images() -> dict:
    return _call("list_public_images")


def list_account_images(account_id: str) -> dict:
    return _call("list_account_images", account_id=account_id)


def get_vpc_by_id(vpc_id: str) -> dict:
    return _call("get_vpc_by_id", vpc_id=vpc_id)


def list_vpcs_by_region(region_name: str) -> dict:
    return _call("list_vpcs_by_region", region_name=region_name)


def get_subnet_by_id(subnet_id: str) -> dict:
    return _call("get_subnet_by_id", subnet_id=subnet_id)


def list_subnets_in_zone(zone_name: str) -> dict:
    return _call("list_subnets_in_zone", zone_name=zone_name)


def get_security_group_by_id(group_id: str) -> dict:
    return _call("get_security_group_by_id", group_id=group_id)


def list_security_groups_in_vpc(vpc_id: str) -> dict:
    return _call("list_security_groups_in_vpc", vpc_id=vpc_id)


def check_account_quota(account_id: str) -> dict:
    return _call("check_account_quota", account_id=account_id)


def check_account_usage(account_id: str) -> dict:
    return _call("check_account_usage", account_id=account_id)


def get_instance_by_id(instance_id: str) -> dict:
    return _call("get_instance_by_id", instance_id=instance_id)


def list_instances_by_account(account_id: str) -> dict:
    return _call("list_instances_by_account", account_id=account_id)


def list_instances_by_state(state: str) -> dict:
    return _call("list_instances_by_state", state=state)



# ── WRITE tools ────────────────────────────────────────────────────────────────

def launch_instance(
    instance_id: str,
    image_id: str,
    subnet_id: str,
    security_group_ids: list,
    instance_type: str,
    key_pair: str,
    owner_account: str,
) -> dict:
    return _call(
        "launch_instance",
        instance_id=instance_id,
        image_id=image_id,
        subnet_id=subnet_id,
        security_group_ids=security_group_ids,
        instance_type=instance_type,
        key_pair=key_pair,
        owner_account=owner_account,
    )


def terminate_instance(instance_id: str) -> dict:
    return _call("terminate_instance", instance_id=instance_id)


def start_instance(instance_id: str) -> dict:
    return _call("start_instance", instance_id=instance_id)


def stop_instance(instance_id: str) -> dict:
    return _call("stop_instance", instance_id=instance_id)


def create_security_group(group_id: str, vpc_id: str, name: str, description: str) -> dict:
    return _call("create_security_group", group_id=group_id, vpc_id=vpc_id,
                 name=name, description=description)


def authorize_security_group_ingress(
    group_id: str, ip_protocol: str, from_port: int, to_port: int, cidr_ip: str
) -> dict:
    return _call("authorize_security_group_ingress", group_id=group_id,
                 ip_protocol=ip_protocol, from_port=from_port,
                 to_port=to_port, cidr_ip=cidr_ip)


def authorize_security_group_egress(
    group_id: str, ip_protocol: str, from_port: int, to_port: int, cidr_ip: str
) -> dict:
    return _call("authorize_security_group_egress", group_id=group_id,
                 ip_protocol=ip_protocol, from_port=from_port,
                 to_port=to_port, cidr_ip=cidr_ip)


def create_vpc(vpc_id: str, cidr_block: str, region: str, owner_account: str) -> dict:
    return _call("create_vpc", vpc_id=vpc_id, cidr_block=cidr_block,
                 region=region, owner_account=owner_account)


def create_subnet(
    subnet_id: str, vpc_id: str, availability_zone: str,
    cidr_block: str, owner_account: str
) -> dict:
    return _call("create_subnet", subnet_id=subnet_id, vpc_id=vpc_id,
                 availability_zone=availability_zone, cidr_block=cidr_block,
                 owner_account=owner_account)


def register_custom_image(
    source_instance_id: str, name: str, operating_system: str,
    root_device_type: str, visibility: str, owner_account: str
) -> dict:
    return _call("register_custom_image", source_instance_id=source_instance_id,
                 name=name, operating_system=operating_system,
                 root_device_type=root_device_type, visibility=visibility,
                 owner_account=owner_account)


def modify_instance_attribute(instance_id: str, updates: dict) -> dict:
    return _call("modify_instance_attribute", instance_id=instance_id, updates=updates)


def release_public_ip(public_ip: str) -> dict:
    return _call("release_public_ip", public_ip=public_ip)


def update_account_quota(account_id: str, quota_type: str, new_limit: int) -> dict:
    return _call("update_account_quota", account_id=account_id,
                 quota_type=quota_type, new_limit=new_limit)


def tag_resource(resource_id: str, tags: dict) -> dict:
    return _call("tag_resource", resource_id=resource_id, tags=tags)
