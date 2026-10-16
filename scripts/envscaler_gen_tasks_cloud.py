"""
EnvScaler task generator for the Cloud Computing Platform environment.

Replicates EnvScaler ScenGenerator Step 2 (task description generation) using
the cloud env's tool registry and the seed init_config as the initial state.
Output is a JSON list of task strings saved to scripts/envscaler_cloud_tasks.json.

Usage:
    python scripts/envscaler_gen_tasks_cloud.py [--n 20] [--out scripts/envscaler_cloud_tasks.json]

The generated tasks are consumed by run_envscaler_comparison_cloud.py.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

PROXY_BASE_URL = "http://localhost:4000"
MODEL = "gpt-4.1"

# ── EnvScaler Step-2 prompt template (verbatim from ScenGenerator) ────────────

_STEP2_TEMPLATE = """\
You are a task design expert, responsible for creating realistic, clear, and challenging tasks for a specific interactive environment.

You do not need to consider how the task will be executed; another execution expert will be responsible for completing it.

# Environment Introduction:
{env_introduction}

# Environment State Definition:
{env_state_definition}

# Supported Operation Interfaces:
{env_modify_operation}

# Environment Rules / Constraints:
{env_rule}

# Current Environment Initial State / Database:
{env_init_state}

# Task Design Requirements:
- **Realism**: The task must closely align with the current environment, reflect a plausible real-world scenario, and have a well-defined objective with business relevance.
- **Feasibility**:
    i. The task must be based on and constrained by the current initial state of the environment. For example, you cannot terminate an instance that does not exist.
    ii. The task should be achievable through a combination of multiple operational interfaces supported by the environment. On one hand, the task description must include nessary information to enable successful completion (for example, if all tools only support actions by ID and can not get the ID anyway, the task should at least provide the ID). On the other hand, it should not include excessive information, so that the Agent is encouraged to use information query tools to obtain the necessary data rather than relying solely on the information provided in the task description.
    iii. Avoid tasks that require more than just the user interface. For example, timestamps might be automatically generated rather than modified through the user interface.
- **State Modification**: The goal of the task must involve modifying the current environment state/database; it cannot be limited to information queries only.
- **Challenge**: The task should be difficult enough that the agent needs to make multiple calls to information query tools and state modification tools to complete it. For example, the modification should have sufficient complexity (e.g., involving multiple objects, multiple attributes, or multi-condition combinations), and should not be achievable in a single simple step.
- **Compositionality**: The task must be composed of several distinct sub-tasks (No less than 50 words). Each sub-task must require multiple tool invocations to complete, ensuring layered complexity and interdependent steps across the task flow.
- **Clarity**: Use concise natural language to describe each sub-task. The description must be easy to understand and unambiguous. Since the ultimate goal is to modify the state, query tools are only part of the task-solving process and serve to provide information to the Agent; therefore, there is no need to include query requirements or intermediate steps in the task description.

Strictly follow the output format below:

# Analysis
[Your detailed step-by step reasoning and thought process, including environment description, current environment state, and supporting operation interfaces and so on.]

# Task
[Only the Task description, without any other analysis or explanation.]
"""

# ── Cloud environment descriptor ───────────────────────────────────────────────

CLOUD_ENV_ITEM = {
    "env_class_name": "CloudComputingPlatform",
    "environment_introduction": (
        "A cloud computing platform that provides on-demand virtualized computing resources "
        "over the internet, including virtual machines, storage, and networking. It maintains "
        "state across regions, availability zones, and user accounts, allowing users to create, "
        "configure, and manage instances programmatically. The platform tracks running/stopped/"
        "terminated instances, VPCs, subnets, security groups, machine images, and account quotas."
    ),
    "state_space_definition": (
        "instances: {instance_id, instance_type (t2.micro/small/medium/large/xlarge), "
        "state (running/stopped/terminated), region, availability_zone, image_id, key_pair, "
        "security_groups, public_ip, private_ip, subnet_id, owner_account}\n"
        "images: {image_id, name, operating_system, root_device_type, visibility (public/private), "
        "owner_account}\n"
        "regions: {region_name, status (enabled/disabled)}\n"
        "availability_zones: {zone_name, region_name, status}\n"
        "vpcs: {vpc_id, cidr_block, region, state (available/pending), owner_account}\n"
        "subnets: {subnet_id, vpc_id, availability_zone, cidr_block, state}\n"
        "security_groups: {group_id, vpc_id, name, description, ingress_rules, egress_rules}\n"
        "accounts: {account_id, name, role, quotas {instance_limit, vpc_limit, image_limit}, "
        "billing_info {plan}}"
    ),
    "operation_list": [
        {"operation_name": "list_enabled_regions", "operation_type": "query",
         "operation_description": "List all enabled regions."},
        {"operation_name": "list_availability_zones", "operation_type": "query",
         "operation_description": "List availability zones in a given region."},
        {"operation_name": "list_public_images", "operation_type": "query",
         "operation_description": "List all public machine images."},
        {"operation_name": "list_account_images", "operation_type": "query",
         "operation_description": "List images owned by a specific account."},
        {"operation_name": "get_vpc_by_id", "operation_type": "query",
         "operation_description": "Get VPC details by ID."},
        {"operation_name": "list_vpcs_by_region", "operation_type": "query",
         "operation_description": "List all VPCs in a region."},
        {"operation_name": "get_subnet_by_id", "operation_type": "query",
         "operation_description": "Get subnet details by ID."},
        {"operation_name": "list_subnets_in_zone", "operation_type": "query",
         "operation_description": "List all subnets in an availability zone."},
        {"operation_name": "list_security_groups_in_vpc", "operation_type": "query",
         "operation_description": "List all security groups in a VPC."},
        {"operation_name": "check_account_quota", "operation_type": "query",
         "operation_description": "Get resource limits (quotas) for an account."},
        {"operation_name": "check_account_usage", "operation_type": "query",
         "operation_description": "Get current resource usage for an account."},
        {"operation_name": "get_instance_by_id", "operation_type": "query",
         "operation_description": "Get full details of an instance by ID."},
        {"operation_name": "list_instances_by_account", "operation_type": "query",
         "operation_description": "List all instances owned by an account."},
        {"operation_name": "list_instances_by_state", "operation_type": "query",
         "operation_description": "List all instances in a given state (running/stopped/terminated)."},
        {"operation_name": "launch_instance", "operation_type": "write",
         "operation_description": (
             "Launch a new VM instance. Requires: instance_id (unique), image_id, subnet_id, "
             "security_group_ids (list), instance_type, key_pair, owner_account. "
             "The instance must be in an enabled region with a valid image, subnet, and SG."
         )},
        {"operation_name": "terminate_instance", "operation_type": "write",
         "operation_description": "Terminate an instance. Only stopped instances can be terminated."},
        {"operation_name": "start_instance", "operation_type": "write",
         "operation_description": "Start a stopped instance."},
        {"operation_name": "stop_instance", "operation_type": "write",
         "operation_description": "Stop a running instance."},
        {"operation_name": "create_security_group", "operation_type": "write",
         "operation_description": "Create a new security group in a VPC."},
        {"operation_name": "authorize_security_group_ingress", "operation_type": "write",
         "operation_description": "Add an inbound rule to a security group."},
        {"operation_name": "authorize_security_group_egress", "operation_type": "write",
         "operation_description": "Add an outbound rule to a security group."},
        {"operation_name": "create_vpc", "operation_type": "write",
         "operation_description": "Create a new VPC in a region with a CIDR block."},
        {"operation_name": "create_subnet", "operation_type": "write",
         "operation_description": "Create a subnet in a VPC in a specific availability zone."},
        {"operation_name": "register_custom_image", "operation_type": "write",
         "operation_description": "Register a custom image from an existing instance."},
        {"operation_name": "modify_instance_attribute", "operation_type": "write",
         "operation_description": "Update modifiable instance attributes (e.g., security groups)."},
        {"operation_name": "tag_resource", "operation_type": "write",
         "operation_description": "Add or update metadata tags on a resource."},
    ],
    "constraints_rules": [
        "A VM instance must be launched in an enabled region with a valid image, subnet, and security group.",
        "Only stopped instances can be terminated.",
        "Only running instances can be stopped.",
        "Only stopped instances can be started.",
        "VPC CIDR blocks must be unique.",
        "Instance IDs, subnet IDs, and security group IDs must be unique.",
        "Account quotas limit the number of instances, VPCs, and images per account.",
    ],
}


def _get_cloud_db_state() -> dict:
    """Read the cloud snapshot DB state for use in the prompt."""
    db_path = REPO_ROOT / "src" / ".runs" / "cloud_data" / "cloud_snapshot.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    def q(sql):
        return [dict(r) for r in conn.execute(sql).fetchall()]

    state = {
        "instances": q("SELECT instance_id, instance_type, state, region, availability_zone, image_id, subnet_id, owner_account FROM instances"),
        "vpcs": q("SELECT vpc_id, cidr_block, region, state, owner_account FROM vpcs"),
        "subnets": q("SELECT subnet_id, vpc_id, availability_zone, cidr_block FROM subnets"),
        "security_groups": q("SELECT group_id, vpc_id, name, description FROM security_groups"),
        "images": q("SELECT image_id, name, operating_system, visibility, owner_account FROM images"),
        "accounts": q("SELECT account_id, name, role, billing_plan FROM accounts"),
    }
    conn.close()
    return state


def _build_prompt(init_state: dict) -> str:
    op_lines = []
    for i, op in enumerate(CLOUD_ENV_ITEM["operation_list"]):
        op_lines.append(
            f"{i}.\nOperation Name: {op['operation_name']}\n"
            f"Operation Type: {op['operation_type']}\n"
            f"Description: {op['operation_description']}"
        )
    op_str = "\n".join(op_lines)
    rule_str = "- " + "\n- ".join(CLOUD_ENV_ITEM["constraints_rules"])
    return _STEP2_TEMPLATE.format(
        env_introduction=CLOUD_ENV_ITEM["environment_introduction"],
        env_state_definition=CLOUD_ENV_ITEM["state_space_definition"],
        env_modify_operation=op_str,
        env_rule=rule_str,
        env_init_state=json.dumps(init_state, indent=2),
    )


def _parse_task(response: str) -> tuple[bool, str | None]:
    if "</think>" in response:
        response = response.split("</think>")[1]
    if "# Analysis" in response:
        response = response.split("# Analysis")[1]
        if "# Task" in response:
            task = response.split("# Task")[1].strip("\n* ")
            return True, task
    return False, None


def generate_tasks(n: int, out_path: Path) -> None:
    client = OpenAI(base_url=PROXY_BASE_URL, api_key="anything")
    init_state = _get_cloud_db_state()
    prompt = _build_prompt(init_state)

    tasks = []
    task_attempts = 0
    max_task_attempts = n * 3

    print(f"Generating {n} EnvScaler tasks for Cloud Computing Platform...")
    print(f"  Model: {MODEL}")

    while len(tasks) < n and task_attempts < max_task_attempts:
        task_attempts += 1
        task = None
        for retry in range(3):
            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    max_tokens=1024,
                    temperature=0.7,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.choices[0].message.content or ""
                parsed_success, task = _parse_task(raw)
                if parsed_success:
                    break
                print(f"  [attempt {task_attempts}, retry {retry + 1}] parse failed...")
            except Exception as e:
                print(f"  [attempt {task_attempts}, retry {retry + 1}] error: {e}")

        if task:
            tasks.append({
                "task_id": f"envscaler_cloud_{len(tasks):03d}",
                "task": task,
                "generated_at": datetime.utcnow().isoformat(),
            })
            print(f"  [{len(tasks):2d}/{n}] OK — {task[:80]}...")
        else:
            print(f"  [attempt {task_attempts}] failed after 3 retries, skipping...")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(tasks, f, indent=2)

    print(f"\nSaved {len(tasks)} tasks → {out_path}")
    if len(tasks) < n:
        print(f"WARNING: only {len(tasks)}/{n} tasks generated after {task_attempts} attempts")


def main():
    parser = argparse.ArgumentParser(description="Generate EnvScaler tasks for Cloud env")
    parser.add_argument("--n", type=int, default=20, help="Number of tasks to generate")
    parser.add_argument("--out", type=Path,
                        default=Path(__file__).parent / "envscaler_cloud_tasks.json")
    args = parser.parse_args()
    generate_tasks(args.n, args.out)


if __name__ == "__main__":
    main()
