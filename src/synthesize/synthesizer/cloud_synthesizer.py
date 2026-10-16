"""
Cloud Computing Platform synthesizer for STS.

Wraps the EnvScaler CloudComputingPlatform class as a first-class STS environment.
Provides directed agent (CloudAgentSynthesizer) and GP generalist (CloudGeneralistSynthesizer).
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, Optional

from synthesize.environments.cloud.apis import cloud_apis
from synthesize.environments.cloud.db import cloud_db
from synthesize.synthesizer.agent_synthesizer import IntentDef
from synthesize.synthesizer.default_agent import DefaultAgentSynthesizer
from synthesize.synthesizer.generalist_synthesizer import GeneralistSynthesizer

# ── Tool registry ──────────────────────────────────────────────────────────────

TOOL_REGISTRY: Dict[str, dict] = {
    # READ tools
    "list_enabled_regions": {
        "fn": cloud_apis.list_enabled_regions,
        "description": "List all enabled regions on the cloud platform.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "list_availability_zones": {
        "fn": cloud_apis.list_availability_zones,
        "description": "List availability zones in a region.",
        "input_schema": {
            "type": "object",
            "properties": {"region_name": {"type": "string", "description": "Region name (e.g. us-east-1)"}},
            "required": ["region_name"],
        },
    },
    "list_public_images": {
        "fn": cloud_apis.list_public_images,
        "description": "List all public machine images (AMIs).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    "list_account_images": {
        "fn": cloud_apis.list_account_images,
        "description": "List images owned by a specific account.",
        "input_schema": {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
    },
    "list_vpcs_by_region": {
        "fn": cloud_apis.list_vpcs_by_region,
        "description": "List all VPCs in a region.",
        "input_schema": {
            "type": "object",
            "properties": {"region_name": {"type": "string"}},
            "required": ["region_name"],
        },
    },
    "list_subnets_in_zone": {
        "fn": cloud_apis.list_subnets_in_zone,
        "description": "List subnets in an availability zone.",
        "input_schema": {
            "type": "object",
            "properties": {"zone_name": {"type": "string"}},
            "required": ["zone_name"],
        },
    },
    "list_security_groups_in_vpc": {
        "fn": cloud_apis.list_security_groups_in_vpc,
        "description": "List security groups in a VPC.",
        "input_schema": {
            "type": "object",
            "properties": {"vpc_id": {"type": "string"}},
            "required": ["vpc_id"],
        },
    },
    "check_account_quota": {
        "fn": cloud_apis.check_account_quota,
        "description": "Check quota limits for an account.",
        "input_schema": {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
    },
    "check_account_usage": {
        "fn": cloud_apis.check_account_usage,
        "description": "Check current resource usage for an account.",
        "input_schema": {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
    },
    "get_instance_by_id": {
        "fn": cloud_apis.get_instance_by_id,
        "description": "Get details of a specific VM instance.",
        "input_schema": {
            "type": "object",
            "properties": {"instance_id": {"type": "string"}},
            "required": ["instance_id"],
        },
    },
    "list_instances_by_account": {
        "fn": cloud_apis.list_instances_by_account,
        "description": "List all instances owned by an account.",
        "input_schema": {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
    },
    "list_instances_by_state": {
        "fn": cloud_apis.list_instances_by_state,
        "description": "List instances filtered by state (running/stopped/terminated).",
        "input_schema": {
            "type": "object",
            "properties": {"state": {"type": "string", "enum": ["running", "stopped", "terminated"]}},
            "required": ["state"],
        },
    },
    "get_vpc_by_id": {
        "fn": cloud_apis.get_vpc_by_id,
        "description": "Get VPC details by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"vpc_id": {"type": "string"}},
            "required": ["vpc_id"],
        },
    },
    "get_subnet_by_id": {
        "fn": cloud_apis.get_subnet_by_id,
        "description": "Get subnet details by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"subnet_id": {"type": "string"}},
            "required": ["subnet_id"],
        },
    },
    "get_security_group_by_id": {
        "fn": cloud_apis.get_security_group_by_id,
        "description": "Get security group details by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"group_id": {"type": "string"}},
            "required": ["group_id"],
        },
    },
    "get_region_by_name": {
        "fn": cloud_apis.get_region_by_name,
        "description": "Get region details by name.",
        "input_schema": {
            "type": "object",
            "properties": {"region_name": {"type": "string"}},
            "required": ["region_name"],
        },
    },
    "get_image_by_id": {
        "fn": cloud_apis.get_image_by_id,
        "description": "Get image (AMI) details by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"image_id": {"type": "string"}},
            "required": ["image_id"],
        },
    },
    # WRITE tools
    "launch_instance": {
        "fn": cloud_apis.launch_instance,
        "description": (
            "Launch a new VM instance. Requires: instance_id, image_id, subnet_id, "
            "security_group_ids (list), instance_type, key_pair, owner_account. "
            "Instance will start in 'running' state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "instance_id":       {"type": "string", "description": "Unique instance ID (e.g. i-005)"},
                "image_id":          {"type": "string"},
                "subnet_id":         {"type": "string"},
                "security_group_ids":{"type": "array", "items": {"type": "string"}},
                "instance_type":     {"type": "string", "enum": ["t2.micro","t2.small","t2.medium","t2.large","t2.xlarge"]},
                "key_pair":          {"type": "string"},
                "owner_account":     {"type": "string"},
            },
            "required": ["instance_id","image_id","subnet_id","security_group_ids","instance_type","key_pair","owner_account"],
        },
    },
    "stop_instance": {
        "fn": cloud_apis.stop_instance,
        "description": "Stop a running instance (state: running → stopped).",
        "input_schema": {
            "type": "object",
            "properties": {"instance_id": {"type": "string"}},
            "required": ["instance_id"],
        },
    },
    "start_instance": {
        "fn": cloud_apis.start_instance,
        "description": "Start a stopped instance (state: stopped → running).",
        "input_schema": {
            "type": "object",
            "properties": {"instance_id": {"type": "string"}},
            "required": ["instance_id"],
        },
    },
    "terminate_instance": {
        "fn": cloud_apis.terminate_instance,
        "description": "Permanently terminate an instance (state → terminated).",
        "input_schema": {
            "type": "object",
            "properties": {"instance_id": {"type": "string"}},
            "required": ["instance_id"],
        },
    },
    "create_vpc": {
        "fn": cloud_apis.create_vpc,
        "description": "Create a new VPC. Requires: vpc_id, cidr_block, region, owner_account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vpc_id":       {"type": "string", "description": "e.g. vpc-010"},
                "cidr_block":   {"type": "string", "description": "e.g. 10.2.0.0/16"},
                "region":       {"type": "string"},
                "owner_account":{"type": "string"},
            },
            "required": ["vpc_id","cidr_block","region","owner_account"],
        },
    },
    "create_subnet": {
        "fn": cloud_apis.create_subnet,
        "description": "Create a subnet within a VPC.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subnet_id":         {"type": "string"},
                "vpc_id":            {"type": "string"},
                "availability_zone": {"type": "string"},
                "cidr_block":        {"type": "string"},
                "owner_account":     {"type": "string"},
            },
            "required": ["subnet_id","vpc_id","availability_zone","cidr_block","owner_account"],
        },
    },
    "create_security_group": {
        "fn": cloud_apis.create_security_group,
        "description": "Create a new security group in a VPC.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_id":   {"type": "string"},
                "vpc_id":     {"type": "string"},
                "name":       {"type": "string"},
                "description":{"type": "string"},
            },
            "required": ["group_id","vpc_id","name","description"],
        },
    },
    "authorize_security_group_ingress": {
        "fn": cloud_apis.authorize_security_group_ingress,
        "description": "Add an inbound rule to a security group.",
        "input_schema": {
            "type": "object",
            "properties": {
                "group_id":    {"type": "string"},
                "ip_protocol": {"type": "string", "description": "e.g. tcp, udp, icmp"},
                "from_port":   {"type": "integer"},
                "to_port":     {"type": "integer"},
                "cidr_ip":     {"type": "string", "description": "e.g. 0.0.0.0/0"},
            },
            "required": ["group_id","ip_protocol","from_port","to_port","cidr_ip"],
        },
    },
    "register_custom_image": {
        "fn": cloud_apis.register_custom_image,
        "description": "Register a custom image (AMI) from a stopped instance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_instance_id": {"type": "string"},
                "name":               {"type": "string"},
                "operating_system":   {"type": "string"},
                "root_device_type":   {"type": "string"},
                "visibility":         {"type": "string", "enum": ["public","private"]},
                "owner_account":      {"type": "string"},
            },
            "required": ["source_instance_id","name","operating_system","root_device_type","visibility","owner_account"],
        },
    },
    "modify_instance_attribute": {
        "fn": cloud_apis.modify_instance_attribute,
        "description": "Modify an attribute of a stopped instance (e.g. instance_type).",
        "input_schema": {
            "type": "object",
            "properties": {
                "instance_id": {"type": "string"},
                "updates":     {"type": "object", "description": "Dict of attribute → new value"},
            },
            "required": ["instance_id","updates"],
        },
    },
    "update_account_quota": {
        "fn": cloud_apis.update_account_quota,
        "description": "Update resource quota for an account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id":  {"type": "string"},
                "quota_type":  {"type": "string", "description": "e.g. instance_limit, vpc_limit"},
                "new_limit":   {"type": "integer"},
            },
            "required": ["account_id","quota_type","new_limit"],
        },
    },
    "tag_resource": {
        "fn": cloud_apis.tag_resource,
        "description": "Add tags (key-value pairs) to any resource.",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource_id": {"type": "string"},
                "tags":        {"type": "object"},
            },
            "required": ["resource_id","tags"],
        },
    },
}

CLOUD_TOOL_REGISTRY = TOOL_REGISTRY  # alias for GP adapter

WRITE_TOOLS = {
    "launch_instance", "stop_instance", "start_instance", "terminate_instance",
    "create_vpc", "create_subnet", "create_security_group",
    "authorize_security_group_ingress", "register_custom_image",
    "modify_instance_attribute", "update_account_quota", "tag_resource",
}

ALL_TOOLS = list(TOOL_REGISTRY.keys())


# ── Samplers ───────────────────────────────────────────────────────────────────

def _get_instances(state: str | None = None) -> list[dict]:
    import sqlite3
    try:
        conn = sqlite3.connect(str(cloud_db.DB_PATH))
        conn.row_factory = sqlite3.Row
        if state:
            rows = conn.execute("SELECT * FROM instances WHERE state=?", (state,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM instances").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _get_vpcs() -> list[dict]:
    import sqlite3
    try:
        conn = sqlite3.connect(str(cloud_db.DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM vpcs").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _get_subnets() -> list[dict]:
    import sqlite3
    try:
        conn = sqlite3.connect(str(cloud_db.DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM subnets").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _sample_launch() -> Optional[dict]:
    return {}  # sampler returns empty; task prompt has all needed context


def _sample_stop() -> Optional[dict]:
    running = _get_instances("running")
    if not running:
        return None
    inst = random.choice(running)
    return {"instance_id": inst["instance_id"]}


def _sample_start() -> Optional[dict]:
    stopped = _get_instances("stopped")
    if not stopped:
        return None
    inst = random.choice(stopped)
    return {"instance_id": inst["instance_id"]}


def _sample_terminate() -> Optional[dict]:
    stopped = _get_instances("stopped")
    if not stopped:
        return None
    inst = random.choice(stopped)
    return {"instance_id": inst["instance_id"]}


def _sample_vpc() -> Optional[dict]:
    return {}  # always possible


# ── Intent definitions ─────────────────────────────────────────────────────────

INTENTS: Dict[str, IntentDef] = {
    "LAUNCH_INSTANCE": IntentDef(
        name="LAUNCH_INSTANCE",
        brief="Launch a new VM instance with appropriate image, subnet, and security group.",
        sampler=_sample_launch,
        task_prompt=lambda p: (
            "You are an admin for a cloud computing platform. "
            "Launch a new VM instance: first list enabled regions and availability zones, "
            "then list public images and subnets in a zone, and a security group in the VPC. "
            "Then launch the instance with instance_type='t2.micro', choosing an appropriate "
            "key_pair and owner_account (e.g. acc1). Pick a unique instance_id (e.g. i-005)."
        ),
        tools=ALL_TOOLS,
        postconditions=lambda params, steps: {
            "instance_launched": any(
                s.tool == "launch_instance" and not s.is_error for s in steps
            )
        },
        informed_rules=(
            "- Instances must be in an enabled region.\n"
            "- image_id, subnet_id and security_group_ids must exist.\n"
            "- instance_id must be unique."
        ),
    ),
    "STOP_INSTANCE": IntentDef(
        name="STOP_INSTANCE",
        brief="Stop a currently running VM instance.",
        sampler=_sample_stop,
        task_prompt=lambda p: (
            f"Stop the running instance {p.get('instance_id', 'i-001')} on the cloud platform."
        ),
        tools=ALL_TOOLS,
        postconditions=lambda params, steps: {
            "instance_stopped": any(
                s.tool == "stop_instance" and not s.is_error for s in steps
            )
        },
        informed_rules="- Only running instances can be stopped.",
    ),
    "START_INSTANCE": IntentDef(
        name="START_INSTANCE",
        brief="Start a previously stopped VM instance.",
        sampler=_sample_start,
        task_prompt=lambda p: (
            f"Start the stopped instance {p.get('instance_id', 'i-002')} on the cloud platform."
        ),
        tools=ALL_TOOLS,
        postconditions=lambda params, steps: {
            "instance_started": any(
                s.tool == "start_instance" and not s.is_error for s in steps
            )
        },
        informed_rules="- Only stopped instances can be started.",
    ),
    "TERMINATE_INSTANCE": IntentDef(
        name="TERMINATE_INSTANCE",
        brief="Terminate a VM instance (stop it first if running).",
        sampler=_sample_terminate,
        task_prompt=lambda p: (
            f"Terminate instance {p.get('instance_id', 'i-002')}. "
            "If it is running, stop it first, then terminate it."
        ),
        tools=ALL_TOOLS,
        postconditions=lambda params, steps: {
            "instance_terminated": any(
                s.tool == "terminate_instance" and not s.is_error for s in steps
            )
        },
        informed_rules="- Only stopped instances can be terminated.",
    ),
    "CREATE_VPC_SUBNET": IntentDef(
        name="CREATE_VPC_SUBNET",
        brief="Create a new VPC with a subnet and security group.",
        sampler=_sample_vpc,
        task_prompt=lambda p: (
            "Create a new VPC in region us-east-1 for account acc1 "
            "(vpc_id='vpc-010', cidr_block='10.10.0.0/16'), then create a subnet in "
            "availability zone us-east-1a (subnet_id='subnet-010', cidr_block='10.10.1.0/24'). "
            "Finally, create a security group in the new VPC (group_id='sg-010')."
        ),
        tools=ALL_TOOLS,
        postconditions=lambda params, steps: {
            "vpc_created": any(s.tool == "create_vpc" and not s.is_error for s in steps),
            "subnet_created": any(s.tool == "create_subnet" and not s.is_error for s in steps),
        },
        informed_rules="- VPC cidr_block must be unique. Region must be enabled.",
    ),
}


# ── Directed agent synthesizer ─────────────────────────────────────────────────

class CloudAgentSynthesizer(DefaultAgentSynthesizer):
    def __init__(self) -> None:
        from synthesize.environments.cloud.apis.cloud_apis import init_env
        init_env()
        super().__init__(
            name="cloud_agent",
            description="LLM agent executes cloud computing intents via Cloud Platform APIs",
            tool_registry=TOOL_REGISTRY,
            intents=INTENTS,
            env_name="Cloud Computing Platform",
        )


# ── GP generalist synthesizer ──────────────────────────────────────────────────

class CloudGeneralistSynthesizer(GeneralistSynthesizer):
    INTENT_TO_WRITE_TOOLS = {
        "LAUNCH_INSTANCE":    {"launch_instance"},
        "STOP_INSTANCE":      {"stop_instance"},
        "START_INSTANCE":     {"start_instance"},
        "TERMINATE_INSTANCE": {"terminate_instance"},
        "CREATE_VPC_SUBNET":  {"create_vpc", "create_subnet", "create_security_group"},
    }

    def __init__(self) -> None:
        from synthesize.environments.cloud.apis.cloud_apis import init_env
        init_env()
        super().__init__(
            name="cloud_generalist",
            description=(
                "Goal-directed agent that observes cloud platform state, selects an appropriate "
                "intent from the bootstrap library, and executes it — no pre-assigned task. "
                "Supports blind / informed / evolve modes."
            ),
            tool_registry=TOOL_REGISTRY,
            bootstrap_intents=INTENTS,
            env_name="Cloud Computing Platform",
        )

    def _init_evolution(self) -> None:
        self._evolution_dir = Path(".runs") / "evolution" / "cloud"
