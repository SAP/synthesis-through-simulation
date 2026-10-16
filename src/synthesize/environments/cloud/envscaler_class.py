# EnvScaler CloudComputingPlatform class — loaded verbatim from env_61_sft
import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, TypedDict


class VirtualMachineInfo(TypedDict):
    instance_id: str
    instance_type: str
    state: str  # running/stopped/terminated
    region: str
    availability_zone: str
    image_id: str
    key_pair: str
    security_groups: List[str]  # list of group_ids
    public_ip: str
    private_ip: str
    subnet_id: str
    launch_time: str  # ISO format or timestamp
    owner_account: str

class ImageInfo(TypedDict):
    image_id: str
    name: str
    operating_system: str
    root_device_type: str
    creation_date: str
    visibility: str  # public/private
    owner_account: str

class RegionInfo(TypedDict):
    region_name: str
    status: str  # enabled/disabled
    services_available: List[str]

class AvailabilityZoneInfo(TypedDict):
    zone_name: str
    region_name: str
    status: str  # assumed from context

class VpcInfo(TypedDict):
    vpc_id: str
    cidr_block: str
    region: str
    state: str  # available/pending
    owner_account: str

class SubnetInfo(TypedDict):
    subnet_id: str
    vpc_id: str
    availability_zone: str
    cidr_block: str
    status: str  # assumed from context

class SecurityRule(TypedDict):
    ip_protocol: str  # e.g., "tcp", "udp", "icmp"
    from_port: int
    to_port: int
    cidr_ip: str  # e.g., "0.0.0.0/0"

class SecurityGroupInfo(TypedDict):
    group_id: str
    vpc_id: str
    name: str
    description: str
    ingress_rules: List[SecurityRule]
    egress_rules: List[SecurityRule]

class UserAccountInfo(TypedDict):
    account_id: str
    name: str
    role: str
    quotas: Dict[str, int]  # e.g., {"vpc_limit": 5, "instance_limit": 20}
    billing_info: dict  # flexible structure for billing data

class CloudComputingPlatform:
    def __init__(self):
        """
        Simulates a cloud computing platform (like AWS EC2) with full state tracking.
        """

        # Virtual Machines (Instances): {instance_id: VirtualMachineInfo}
        self.instances: Dict[str, VirtualMachineInfo] = {}

        # Images (AMIs): {image_id: ImageInfo}
        self.images: Dict[str, ImageInfo] = {}

        # Regions: {region_name: RegionInfo}
        self.regions: Dict[str, RegionInfo] = {}

        # Availability Zones: {zone_name: AvailabilityZoneInfo}
        self.availability_zones: Dict[str, AvailabilityZoneInfo] = {}

        # VPCs: {vpc_id: VpcInfo}
        self.vpcs: Dict[str, VpcInfo] = {}

        # Subnets: {subnet_id: SubnetInfo}
        self.subnets: Dict[str, SubnetInfo] = {}

        # Security Groups: {group_id: SecurityGroupInfo}
        self.security_groups: Dict[str, SecurityGroupInfo] = {}

        # User Accounts: {account_id: UserAccountInfo}
        self.accounts: Dict[str, UserAccountInfo] = {}

        # Constraints reminder:
        # - A virtual machine must be launched in an enabled region and available zone.
        # - Each instance must be associated with a valid image, subnet, and security group.
        # - IP addresses (public and private) must be unique within their respective networks.
        # - Security group ingress/egress rules must not allow unrestricted access by default.
        # - Resource creation is subject to account quotas and permissions.
        # - Instances can only be created if sufficient capacity is available in the requested zone.

    def get_region_by_name(self, region_name: str) -> dict:
        """
        Retrieve region information by region name.

        Args:
            region_name (str): The name of the region (e.g., "us-west-1").

        Returns:
            dict: {
                "success": True,
                "data": RegionInfo  # Dictionary containing region details
            }
            or
            {
                "success": False,
                "error": str  # Description of the error, e.g., "Region not found"
            }

        Constraints:
            - The region must exist in the platform.
        """
        if not region_name:
            return {"success": False, "error": "Region name cannot be empty"}

        region_info = self.regions.get(region_name)
        if not region_info:
            return {"success": False, "error": f"Region '{region_name}' not found"}

        return {"success": True, "data": region_info}

    def list_enabled_regions(self) -> dict:
        """
        Retrieve all regions that are currently enabled for resource deployment.

        Returns:
            dict: {
                "success": True,
                "data": List[RegionInfo]  # List of RegionInfo dicts where status is "enabled"
            }
            or in case of no matching regions:
            {
                "success": True,
                "data": []  # Empty list if no enabled regions
            }

        Constraints:
            - Only regions with status "enabled" are included.
            - The operation does not require account context or permissions (assumed to be publicly queryable).
        """
        enabled_regions = [
            region_info for region_info in self.regions.values()
            if region_info["status"] == "enabled"
        ]
        return { "success": True, "data": enabled_regions }

    def list_availability_zones(self, region_name: str) -> dict:
        """
        List all availability zones in a given region, with their statuses.

        Args:
            region_name (str): The name of the region to query.

        Returns:
            dict: {
                "success": True,
                "data": List[AvailabilityZoneInfo]  # List of availability zones in the region (may be empty)
            }
            or
            {
                "success": False,
                "error": str  # Description of the error, e.g., "Region not found"
            }

        Constraints:
            - The specified region must exist in the platform.
        """
        if region_name not in self.regions:
            return {"success": False, "error": "Region not found"}

        zones = [
            az_info for az_info in self.availability_zones.values()
            if az_info["region_name"] == region_name
        ]

        return {"success": True, "data": zones}

    def get_image_by_id(self, image_id: str) -> dict:
        """
        Retrieve image details (e.g., OS, visibility) by image_id.

        Args:
            image_id (str): The unique identifier of the image (e.g., 'ami-12345678').

        Returns:
            dict: {
                "success": bool,
                "data": ImageInfo  # If found
            }
            or {
                "success": False,
                "error": str  # If image not found
            }

        Constraints:
            - The image must exist in the platform's image registry.
        """
        image_info = self.images.get(image_id)
        if not image_info:
            return {"success": False, "error": "Image not found"}

        return {"success": True, "data": image_info}

    def list_public_images(self) -> dict:
        """
        List all public images available for launching instances.

        Returns:
            dict: {
                "success": True,
                "data": List[ImageInfo]  # List of public images; may be empty
            }

        Constraints:
            - Only images with visibility set to 'public' are returned.
            - No authentication or account context is required; public images are globally accessible.
        """
        public_images = [
            image_info for image_info in self.images.values()
            if image_info["visibility"] == "public"
        ]

        return { "success": True, "data": public_images }

    def list_account_images(self, account_id: str) -> dict:
        """
        List all custom images owned by the specified user account.

        Args:
            account_id (str): The ID of the user account.

        Returns:
            dict: {
                "success": True,
                "data": List[ImageInfo]  # List of images where owner_account == account_id
            }
            or
            {
                "success": False,
                "error": str  # Description of error, e.g., account not found
            }

        Constraints:
            - Only images where owner_account matches the given account_id are returned.
            - The account must exist in the system.
        """
        if account_id not in self.accounts:
            return { "success": False, "error": "Account does not exist" }

        owned_images = [
            image for image in self.images.values()
            if image["owner_account"] == account_id
        ]

        return { "success": True, "data": owned_images }

    def get_vpc_by_id(self, vpc_id: str) -> dict:
        """
        Retrieve the configuration of a VPC by its ID.

        Args:
            vpc_id (str): The ID of the VPC to retrieve.

        Returns:
            dict: {
                "success": True,
                "data": VpcInfo  # The VPC's information
            }
            or
            {
                "success": False,
                "error": str  # Description of the error, e.g. "VPC not found"
            }

        Constraints:
            - Only existing VPCs can be retrieved.
        """
        vpc = self.vpcs.get(vpc_id)
        if vpc is None:
            return {"success": False, "error": "VPC not found"}

        return {"success": True, "data": vpc}

    def list_vpcs_by_region(self, region_name: str) -> dict:
        """
        Retrieve all VPCs in the specified region.

        Args:
            region_name (str): The name of the region to list VPCs for.

        Returns:
            dict: {
                "success": True,
                "data": List[VpcInfo]  # List of VPCs in the region (may be empty)
            }
            or
            {
                "success": False,
                "error": str  # Description of error, e.g., "Region does not exist"
            }

        Constraints:
            - The region must exist in the platform.
        """
        if region_name not in self.regions:
            return {"success": False, "error": "Region does not exist"}

        result = [
            vpc_info for vpc_info in self.vpcs.values()
            if vpc_info["region"] == region_name
        ]

        return {"success": True, "data": result}

    def get_subnet_by_id(self, subnet_id: str) -> dict:
        """
        Retrieve subnet details (CIDR block, availability zone, etc.) by subnet ID.

        Args:
            subnet_id (str): The unique identifier of the subnet.

        Returns:
            dict: {
                "success": True,
                "data": SubnetInfo  # Full subnet information
            }
            or
            {
                "success": False,
                "error": str  # Description of error, e.g., "Subnet not found"
            }

        Constraints:
            - The subnet_id must exist in the system.
        """
        if not subnet_id:
            return { "success": False, "error": "Subnet ID cannot be empty" }

        subnet_info = self.subnets.get(subnet_id)
        if not subnet_info:
            return { "success": False, "error": "Subnet not found" }

        return { "success": True, "data": subnet_info }

    def list_subnets_in_zone(self, zone_name: str) -> dict:
        """
        List all subnets located in the specified availability zone.

        Args:
            zone_name (str): The name of the availability zone (e.g., 'us-west-2a').

        Returns:
            dict: {
                "success": bool,
                "data": List[SubnetInfo]  # List of subnets in the zone; may be empty
            }
            or
            {
                "success": False,
                "error": str  # Description of error (e.g., zone not found)
            }

        Constraints:
            - The availability zone must exist in the platform.
            - Subnets are associated with exactly one availability zone.
        """
        if zone_name not in self.availability_zones:
            return {
                "success": False,
                "error": f"Availability zone '{zone_name}' does not exist"
            }

        result = [
            subnet_info for subnet_info in self.subnets.values()
            if subnet_info["availability_zone"] == zone_name
        ]

        return {
            "success": True,
            "data": result
        }

    def get_security_group_by_id(self, group_id: str) -> dict:
        """
        Retrieve the security group information and its ingress/egress rules by group_id.

        Args:
            group_id (str): The unique identifier of the security group.

        Returns:
            dict: {
                "success": True,
                "data": SecurityGroupInfo  # Full security group metadata and rules
            }
            or
            {
                "success": False,
                "error": str  # Reason for failure, e.g., "Security group not found"
            }

        Constraints:
            - The security group must exist in the system.
        """
        if not group_id:
            return { "success": False, "error": "Group ID cannot be empty" }

        security_group = self.security_groups.get(group_id)
        if not security_group:
            return { "success": False, "error": "Security group not found" }

        return { "success": True, "data": security_group }

    def list_security_groups_in_vpc(self, vpc_id: str) -> dict:
        """
        Retrieve all security groups associated with the specified VPC.

        Args:
            vpc_id (str): The ID of the VPC to query for security groups.

        Returns:
            dict: {
                "success": True,
                "data": List[SecurityGroupInfo]  # List of security groups in the VPC (may be empty)
            }
            or
            {
                "success": False,
                "error": str  # Description of the error (e.g., VPC does not exist)
            }

        Constraints:
            - The VPC must exist in the system.
            - Security groups are linked to a VPC via the 'vpc_id' attribute.
        """
        if vpc_id not in self.vpcs:
            return {"success": False, "error": "VPC does not exist"}

        result = [
            sg_info for sg_info in self.security_groups.values()
            if sg_info["vpc_id"] == vpc_id
        ]

        return {"success": True, "data": result}

    def check_account_quota(self, account_id: str) -> dict:
        """
        Query the current resource limits (quotas) for a specified user account.

        Args:
            account_id (str): The unique identifier of the user account.

        Returns:
            dict: {
                "success": bool,
                "data": Dict[str, int]  # Mapping of resource types (e.g., "instance_limit") to their maximum allowed count
            }
            or
            {
                "success": False,
                "error": str  # Description of the error (e.g., account not found)
            }

        Constraints:
            - The account must exist in the system.
            - Quotas are defined per account and subject to resource creation rules.
        """
        if account_id not in self.accounts:
            return {"success": False, "error": "Account does not exist"}

        account = self.accounts[account_id]
        quotas = account["quotas"]  # This is already a dict, possibly empty

        return {"success": True, "data": quotas}

    def check_account_usage(self, account_id: str) -> dict:
        """
        Retrieve current resource usage for the specified account against their quotas.

        Args:
            account_id (str): The unique identifier of the user account.

        Returns:
            dict: {
                "success": bool,
                "data": {
                    "resource_usage": {
                        "instances": { "used": int, "limit": int },
                        "vpcs": { "used": int, "limit": int }
                    }
                }
            }
            or
            {
                "success": False,
                "error": str  # e.g., "Account not found"
            }

        Constraints:
            - Only resources owned by the account are counted.
            - Quotas are defined per account in the account's `quotas` field.
            - If a quota is not defined for a resource, the limit is considered 0.
        """
        if account_id not in self.accounts:
            return {"success": False, "error": "Account not found"}

        account = self.accounts[account_id]
        quotas = account["quotas"]

        # Count instances owned by the account
        instance_count = len([
            inst for inst in self.instances.values()
            if inst["owner_account"] == account_id
        ])

        # Count VPCs owned by the account
        vpc_count = len([
            vpc for vpc in self.vpcs.values()
            if vpc["owner_account"] == account_id
        ])

        # Build usage report
        usage_data = {
            "resource_usage": {
                "instances": {
                    "used": instance_count,
                    "limit": quotas.get("instance_limit", 0)
                },
                "vpcs": {
                    "used": vpc_count,
                    "limit": quotas.get("vpc_limit", 0)
                }
            }
        }

        return {
            "success": True,
            "data": usage_data
        }

    def get_instance_by_id(self, instance_id: str) -> dict:
        """
        Retrieve full details of a virtual machine instance by its instance_id.

        Args:
            instance_id (str): The unique identifier of the virtual machine.

        Returns:
            dict: {
                "success": True,
                "data": VirtualMachineInfo  # Full instance information
            }
            or
            {
                "success": False,
                "error": str  # Description of error, e.g., "Instance not found"
            }

        Constraints:
            - The instance_id must exist in the platform.
        """
        if not instance_id:
            return { "success": False, "error": "Instance ID cannot be empty" }

        instance = self.instances.get(instance_id)
        if instance is None:
            return { "success": False, "error": "Instance not found" }

        return { "success": True, "data": instance }

    def list_instances_by_account(self, account_id: str) -> dict:
        """
        List all virtual machine instances owned by the specified user account.

        Args:
            account_id (str): The unique identifier of the user account.

        Returns:
            dict: {
                "success": True,
                "data": List[VirtualMachineInfo]  # List of instance info (may be empty)
            }
            or
            {
                "success": False,
                "error": str  # Description of the error, e.g., account does not exist
            }

        Constraints:
            - The account must exist in the system.
        """
        if account_id not in self.accounts:
            return {"success": False, "error": "Account does not exist"}

        result = [
            instance for instance in self.instances.values()
            if instance["owner_account"] == account_id
        ]

        return {"success": True, "data": result}

    def list_instances_by_state(self, state: str) -> dict:
        """
        Filter and list all instances that are in the specified state.

        Args:
            state (str): The state to filter by. Must be one of: 'running', 'stopped', 'terminated'.

        Returns:
            dict: {
                "success": True,
                "data": List[VirtualMachineInfo]  # List of instances matching the state (may be empty)
            }
            or
            {
                "success": False,
                "error": str  # Description of error, e.g., invalid state
            }

        Constraints:
            - Only valid instance states are allowed: 'running', 'stopped', 'terminated'.
        """
        valid_states = {"running", "stopped", "terminated"}

        if state not in valid_states:
            return {
                "success": False,
                "error": "Invalid state value. Must be one of: running, stopped, terminated."
            }

        filtered_instances = [
            instance for instance in self.instances.values()
            if instance["state"] == state
        ]

        return {
            "success": True,
            "data": filtered_instances
        }

    def launch_instance(
        self,
        instance_id: str,
        image_id: str,
        subnet_id: str,
        security_group_ids: List[str],
        instance_type: str,
        key_pair: str,
        owner_account: str
    ) -> dict:
        """
        Launch a new virtual machine instance with the given configuration.

        Args:
            instance_id (str): Unique ID for the instance.
            image_id (str): ID of the image (AMI) to use.
            subnet_id (str): Subnet to launch the instance into.
            security_group_ids (List[str]): List of security group IDs to associate.
            instance_type (str): Type of instance (e.g., t2.micro).
            key_pair (str): SSH key pair name.
            owner_account (str): ID of the account launching the instance.

        Returns:
            dict: {
                "success": bool,
                "message": str,  # On success
                "error": str     # On failure
            }

        Constraints enforced:
            - Region must be enabled.
            - Image, subnet, and security groups must exist and be accessible.
            - Security groups must belong to the same VPC as the subnet.
            - Instance ID must be unique.
            - Account must have available instance quota.
            - Sufficient IP addresses in subnet CIDR (basic simulation).
            - Zone and region must be available.
        """
        # Check if instance ID already exists
        if instance_id in self.instances:
            return {"success": False, "error": "Instance ID already exists"}

        # Check if owner account exists
        if owner_account not in self.accounts:
            return {"success": False, "error": "Owner account does not exist"}

        # Check account quota for instances (assuming quota key is "instance_limit")
        account = self.accounts[owner_account]
        current_instance_count = sum(
            1 for inst in self.instances.values() if inst["owner_account"] == owner_account
        )
        if current_instance_count >= account["quotas"].get("instance_limit", 1):
            return {"success": False, "error": "Account instance quota exceeded"}

        # Check if subnet exists
        if subnet_id not in self.subnets:
            return {"success": False, "error": "Subnet does not exist"}
        subnet = self.subnets[subnet_id]
        vpc_id = subnet["vpc_id"]

        # Check if VPC exists and get region
        if vpc_id not in self.vpcs:
            return {"success": False, "error": "VPC of subnet does not exist"}
        vpc = self.vpcs[vpc_id]
        region_name = vpc["region"]

        # Check if region is enabled
        if region_name not in self.regions or self.regions[region_name]["status"] != "enabled":
            return {"success": False, "error": "Region is not enabled"}

        # Check if availability zone is valid and exists
        az_name = subnet["availability_zone"]
        if az_name not in self.availability_zones:
            return {"success": False, "error": "Availability zone does not exist"}
        az = self.availability_zones[az_name]
        if az["region_name"] != region_name:
            return {"success": False, "error": "Subnet availability zone does not match VPC region"}

        # Check if image exists
        if image_id not in self.images:
            return {"success": False, "error": "Image does not exist"}
        image = self.images[image_id]

        # Check if image is accessible (public or owned by account)
        if image["visibility"] == "private" and image["owner_account"] != owner_account:
            return {"success": False, "error": "Image is not accessible to this account"}

        # Validate security groups
        if not security_group_ids:
            return {"success": False, "error": "At least one security group is required"}
        for sg_id in security_group_ids:
            if sg_id not in self.security_groups:
                return {"success": False, "error": f"Security group {sg_id} does not exist"}
            sg = self.security_groups[sg_id]
            if sg["vpc_id"] != vpc_id:
                return {
                    "success": False,
                    "error": f"Security group {sg_id} is not in the same VPC as the subnet"
                }

        # Assign private IP (simple simulation: use a deterministic IP based on instance_id)
        # In real systems, DHCP or manual assignment occurs
        # We'll assume 10.x.x.x/16 style CIDR and assign 10.0.x.x where x is derived from instance_id
        try:
            ip_hash = int(hashlib.md5(instance_id.encode()).hexdigest()[:8], 16)
            # Simulate IP within CIDR (this is a simplification)
            private_ip = f"10.0.{(ip_hash % 250) + 1}.{(ip_hash // 250) % 250 + 1}"
        except Exception:
            private_ip = "10.0.1.100"  # fallback

        # Assign public IP (simulated for now, not tied to real pools)
        public_ip = f"203.0.{(ip_hash % 255)}.{(ip_hash // 255) % 255 + 1}"

        # Create new instance entry
        new_instance: VirtualMachineInfo = {
            "instance_id": instance_id,
            "instance_type": instance_type,
            "state": "running",
            "region": region_name,
            "availability_zone": az_name,
            "image_id": image_id,
            "key_pair": key_pair,
            "security_groups": security_group_ids,
            "public_ip": public_ip,
            "private_ip": private_ip,
            "subnet_id": subnet_id,
            "launch_time": "2023-04-05T12:34:56Z",  # Simulated launch time
            "owner_account": owner_account,
        }

        # Add to instances
        self.instances[instance_id] = new_instance

        return {"success": True, "message": "Instance launched successfully"}

    def terminate_instance(self, instance_id: str) -> dict:
        """
        Shut down and delete a running or stopped virtual machine instance.

        Args:
            instance_id (str): The unique identifier of the instance to terminate.

        Returns:
            dict: {
                "success": True,
                "message": str  # Confirmation of termination
            }
            or
            {
                "success": False,
                "error": str  # Reason for failure (e.g., instance not found)
            }

        Constraints:
            - The instance must exist.
            - Operation is idempotent: terminating an already terminated instance succeeds.
            - Only valid if the instance is in 'running' or 'stopped' state (but allowed regardless).
        """
        if instance_id not in self.instances:
            return { "success": False, "error": "Instance does not exist" }

        instance = self.instances[instance_id]

        if instance["state"] == "terminated":
            return { "success": True, "message": f"Instance '{instance_id}' was already terminated." }

        # Update state to terminated and remove from active instances
        instance["state"] = "terminated"
        del self.instances[instance_id]  # Simulate deletion from platform

        return { "success": True, "message": f"Instance '{instance_id}' terminated successfully." }

    def start_instance(self, instance_id: str) -> dict:
        """
        Start a stopped virtual machine instance.

        Args:
            instance_id (str): The unique identifier of the instance to start.

        Returns:
            dict: {
                "success": bool,
                "message": str  # On success: confirmation message
            }
            or
            {
                "success": False,
                "error": str  # Explanation of the failure
            }

        Constraints:
            - The instance must exist and be in 'stopped' state.
            - The instance's region and availability zone must be enabled.
            - The instance's owner account must exist.
            - The instance can only be started if sufficient capacity exists (simplified: assume zone status implies capacity).
        """
        instance = self.instances.get(instance_id)
        if not instance:
            return { "success": False, "error": f"Instance {instance_id} does not exist." }

        if instance["state"] != "stopped":
            return {
                "success": False,
                "error": f"Instance {instance_id} is not in 'stopped' state. Current state: {instance['state']}."
            }

        region_name = instance["region"]
        zone_name = instance["availability_zone"]
        account_id = instance["owner_account"]

        # Validate region is enabled
        region = self.regions.get(region_name)
        if not region or region["status"] != "enabled":
            return { "success": False, "error": f"Region {region_name} is not enabled." }

        # Validate availability zone is available
        zone = self.availability_zones.get(zone_name)
        if not zone or zone["region_name"] != region_name:
            return { "success": False, "error": f"Availability zone {zone_name} is not available." }

        # Validate account exists
        if account_id not in self.accounts:
            return { "success": False, "error": f"Owner account {account_id} does not exist." }

        # All checks passed: start the instance
        instance["state"] = "running"
        return { "success": True, "message": f"Instance {instance_id} started successfully." }

    def stop_instance(self, instance_id: str) -> dict:
        """
        Stop a running virtual machine instance. The instance state is preserved, and it can be started again later.

        Args:
            instance_id (str): The unique identifier of the instance to stop.

        Returns:
            dict: {
                "success": True,
                "message": str  # Success description
            }
            or
            {
                "success": False,
                "error": str  # Reason for failure (e.g., not found, not running)
            }

        Constraints:
            - The instance must exist.
            - The instance must be in 'running' state to be stopped.
            - Stopping a stopped or terminated instance is not allowed.
        """
        instance = self.instances.get(instance_id)
        if not instance:
            return { "success": False, "error": f"Instance '{instance_id}' not found." }

        if instance["state"] != "running":
            return { "success": False, "error": f"Instance '{instance_id}' is not running. Current state: '{instance['state']}'. Cannot stop." }

        # Update state to stopped
        instance["state"] = "stopped"

        return { "success": True, "message": f"Instance '{instance_id}' stopped successfully." }

    def create_security_group(
        self,
        group_id: str,
        vpc_id: str,
        name: str,
        description: str
    ) -> dict:
        """
        Create a new security group in a specified VPC.

        Args:
            group_id (str): Unique identifier for the security group.
            vpc_id (str): ID of the VPC in which to create the security group.
            name (str): Name of the security group.
            description (str): Description of the security group.

        Returns:
            dict: {
                "success": bool,
                "message": str  # On success
            }
            or
            {
                "success": False,
                "error": str  # On failure
            }

        Constraints:
            - The VPC must exist.
            - The group_id must be unique.
            - Security group is created with default deny-all rules (empty ingress/egress).
        """
        # Validate required fields
        if not group_id:
            return {"success": False, "error": "group_id is required"}
        if not vpc_id:
            return {"success": False, "error": "vpc_id is required"}
        if not name:
            return {"success": False, "error": "name is required"}
        if not description:
            return {"success": False, "error": "description is required"}

        # Check if VPC exists
        if vpc_id not in self.vpcs:
            return {"success": False, "error": f"VPC '{vpc_id}' does not exist"}

        # Check if group_id already exists
        if group_id in self.security_groups:
            return {"success": False, "error": f"Security group with ID '{group_id}' already exists"}

        # Create the security group with default deny-all (empty rules)
        security_group: SecurityGroupInfo = {
            "group_id": group_id,
            "vpc_id": vpc_id,
            "name": name,
            "description": description,
            "ingress_rules": [],
            "egress_rules": []
        }

        # Persist to state
        self.security_groups[group_id] = security_group

        return {
            "success": True,
            "message": f"Security group '{group_id}' created successfully in VPC '{vpc_id}'."
        }

    def authorize_security_group_ingress(
        self,
        group_id: str,
        ip_protocol: str,
        from_port: int,
        to_port: int,
        cidr_ip: str
    ) -> dict:
        """
        Add an ingress (inbound) rule to a security group.

        Args:
            group_id (str): The ID of the security group.
            ip_protocol (str): The protocol (e.g., "tcp", "udp", "icmp").
            from_port (int): The start of the port range (inclusive).
            to_port (int): The end of the port range (inclusive).
            cidr_ip (str): The CIDR IP range to allow (e.g., "10.0.0.0/16").

        Returns:
            dict: {
                "success": bool,
                "message": str  # On success
            } or {
                "success": False,
                "error": str  # On failure
            }

        Constraints:
            - Security group must exist.
            - Port range must be valid (1-65535, from_port <= to_port).
            - ip_protocol must be one of: 'tcp', 'udp', 'icmp'.
            - Duplicate rules (same fields) are not added.
            - CIDR format is assumed to be correct; no deep validation.
        """
        # Validate protocol
        valid_protocols = {"tcp", "udp", "icmp"}
        if ip_protocol not in valid_protocols:
            return {
                "success": False,
                "error": f"Invalid protocol: {ip_protocol}. Must be one of {valid_protocols}."
            }

        # Validate port range
        if not (1 <= from_port <= 65535) or not (1 <= to_port <= 65535):
            return {
                "success": False,
                "error": "Ports must be between 1 and 65535."
            }
        if from_port > to_port:
            return {
                "success": False,
                "error": "from_port cannot be greater than to_port."
            }

        # Check if security group exists
        if group_id not in self.security_groups:
            return {
                "success": False,
                "error": f"Security group '{group_id}' does not exist."
            }

        # Get the security group
        sg = self.security_groups[group_id]

        # Create rule to add
        new_rule = {
            "ip_protocol": ip_protocol,
            "from_port": from_port,
            "to_port": to_port,
            "cidr_ip": cidr_ip
        }

        # Check for duplicate rule
        if new_rule in sg["ingress_rules"]:
            return {
                "success": False,
                "error": "Ingress rule already exists."
            }

        # Add the rule
        sg["ingress_rules"].append(new_rule)

        return {
            "success": True,
            "message": f"Ingress rule added to security group {group_id}"
        }

    def authorize_security_group_egress(
        self,
        group_id: str,
        ip_protocol: str,
        from_port: int,
        to_port: int,
        cidr_ip: str
    ) -> dict:
        """
        Add an egress (outbound) rule to a security group.

        Args:
            group_id (str): The ID of the security group.
            ip_protocol (str): The protocol (e.g., 'tcp', 'udp', 'icmp').
            from_port (int): The start of the port range (inclusive).
            to_port (int): The end of the port range (inclusive).
            cidr_ip (str): The IPv4 CIDR range (e.g., '0.0.0.0/0').

        Returns:
            dict: {
                "success": bool,
                "message": str  # On success
            }
            or
            {
                "success": False,
                "error": str  # On failure
            }

        Constraints:
            - Security group must exist.
            - Port numbers must be between 0 and 65535.
            - from_port must be <= to_port.
            - cidr_ip must be a valid IPv4 CIDR format (basic validation).
            - ip_protocol should be a valid protocol string.
        """
        # Validate security group exists
        if group_id not in self.security_groups:
            return {"success": False, "error": f"Security group '{group_id}' does not exist"}

        # Validate ports
        if not (0 <= from_port <= 65535) or not (0 <= to_port <= 65535):
            return {"success": False, "error": "Ports must be in the range 0-65535"}
        if from_port > to_port:
            return {"success": False, "error": "from_port cannot be greater than to_port"}

        # Validate ip_protocol
        valid_protocols = {"tcp", "udp", "icmp", "icmpv6", "all"}
        if ip_protocol not in valid_protocols:
            return {"success": False, "error": f"Invalid protocol '{ip_protocol}'. Must be one of {valid_protocols}"}

        # Basic CIDR format check (e.g., "x.x.x.x/y")
        if not cidr_ip:
            return {"success": False, "error": "cidr_ip is required"}
        parts = cidr_ip.split("/")
        if len(parts) != 2:
            return {"success": False, "error": "cidr_ip must be in CIDR notation (e.g., '0.0.0.0/0')"}
        ip_parts = parts[0].split(".")
        if len(ip_parts) != 4:
            return {"success": False, "error": "Invalid IP address in CIDR"}
        try:
            ip_nums = [int(part) for part in ip_parts]
            prefix_length = int(parts[1])
            if not all(0 <= num <= 255 for num in ip_nums) or not (0 <= prefix_length <= 32):
                raise ValueError
        except ValueError:
            return {"success": False, "error": "Invalid CIDR block format"}

        # Create the rule
        new_rule = {
            "ip_protocol": ip_protocol,
            "from_port": from_port,
            "to_port": to_port,
            "cidr_ip": cidr_ip
        }

        # Add to egress rules
        self.security_groups[group_id]["egress_rules"].append(new_rule)

        return {
            "success": True,
            "message": f"Egress rule added to security group {group_id}"
        }

    def create_vpc(self, vpc_id: str, cidr_block: str, region: str, owner_account: str) -> dict:
        """
        Create a new VPC with the specified CIDR block in the given region.

        Args:
            vpc_id (str): Unique identifier for the VPC (e.g., 'vpc-12345').
            cidr_block (str): IP address range in CIDR notation (e.g., '10.0.0.0/16').
            region (str): The region where the VPC will be created.
            owner_account (str): The account ID of the user creating the VPC.

        Returns:
            dict: {
                "success": bool,
                "message": str  # On success
            }
            or
            {
                "success": False,
                "error": str  # On failure
            }

        Constraints:
            - Region must exist and be enabled.
            - VPC ID must be unique.
            - Owner account must exist.
            - Account must have capacity within its VPC quota.
        """
        # Validate input parameters
        if not vpc_id or not cidr_block or not region or not owner_account:
            return { "success": False, "error": "Missing required parameters" }

        # Check if region exists and is enabled
        region_info = self.regions.get(region)
        if not region_info:
            return { "success": False, "error": f"Region '{region}' does not exist" }
        if region_info["status"] != "enabled":
            return { "success": False, "error": f"Region '{region}' is not enabled" }

        # Check if VPC ID already exists
        if vpc_id in self.vpcs:
            return { "success": False, "error": f"VPC with ID '{vpc_id}' already exists" }

        # Check if owner account exists
        if owner_account not in self.accounts:
            return { "success": False, "error": f"Account '{owner_account}' does not exist" }

        # Check account VPC quota
        account = self.accounts[owner_account]
        current_vpc_count = len([vpc for vpc in self.vpcs.values() if vpc["owner_account"] == owner_account])
        vpc_limit = account["quotas"].get("vpc_limit", 5)  # default limit 5 if not set
        if current_vpc_count >= vpc_limit:
            return { "success": False, "error": f"Account '{owner_account}' has reached its VPC limit ({vpc_limit})" }

        # Create the VPC
        new_vpc: VpcInfo = {
            "vpc_id": vpc_id,
            "cidr_block": cidr_block,
            "region": region,
            "state": "available",
            "owner_account": owner_account
        }
        self.vpcs[vpc_id] = new_vpc

        return {
            "success": True,
            "message": f"VPC '{vpc_id}' created successfully in region '{region}'."
        }

    def create_subnet(
        self,
        subnet_id: str,
        vpc_id: str,
        availability_zone: str,
        cidr_block: str,
        owner_account: str
    ) -> dict:
        """
        Create a subnet within a VPC in a specific availability zone.

        Args:
            subnet_id (str): Unique identifier for the subnet (e.g., 'subnet-12345').
            vpc_id (str): ID of the VPC in which to create the subnet.
            availability_zone (str): The availability zone (e.g., 'us-west-2a').
            cidr_block (str): The CIDR notation for the subnet's IP range (e.g., '10.0.1.0/24').
            owner_account (str): The account ID creating the subnet.

        Returns:
            dict: {
                "success": bool,
                "message": str  # On success
            }
            or
            {
                "success": False,
                "error": str  # On failure
            }

        Constraints:
            - VPC must exist.
            - Availability zone must exist.
            - VPC's region must match the availability zone's region.
            - Subnet ID must be unique.
            - CIDR block must not overlap with existing subnets in the same VPC (simplified to exact CIDR match).
            - Owner account should exist (assumed valid for this implementation).
        """
        # Check if VPC exists
        if vpc_id not in self.vpcs:
            return { "success": False, "error": f"VPC '{vpc_id}' does not exist" }

        # Check if availability zone exists
        if availability_zone not in self.availability_zones:
            return { "success": False, "error": f"Availability zone '{availability_zone}' does not exist" }

        vpc = self.vpcs[vpc_id]
        zone = self.availability_zones[availability_zone]

        # Check region match
        if vpc["region"] != zone["region_name"]:
            return {
                "success": False,
                "error": f"VPC region '{vpc['region']}' does not match zone region '{zone['region_name']}'"
            }

        # Check subnet ID uniqueness
        if subnet_id in self.subnets:
            return { "success": False, "error": f"Subnet ID '{subnet_id}' already exists" }

        # Check CIDR block uniqueness (simplified: no duplicate CIDR in same VPC)
        for existing_subnet in self.subnets.values():
            if existing_subnet["vpc_id"] == vpc_id and existing_subnet["cidr_block"] == cidr_block:
                return {
                    "success": False,
                    "error": f"CIDR block '{cidr_block}' is already in use in VPC '{vpc_id}'"
                }

        # Create the subnet
        subnet: SubnetInfo = {
            "subnet_id": subnet_id,
            "vpc_id": vpc_id,
            "availability_zone": availability_zone,
            "cidr_block": cidr_block,
            "status": "available"  # Assume created subnet is immediately available
        }

        self.subnets[subnet_id] = subnet

        return {
            "success": True,
            "message": f"Subnet '{subnet_id}' created successfully in VPC '{vpc_id}'."
        }

    def register_custom_image(
        self,
        source_instance_id: str,
        name: str,
        operating_system: str,
        root_device_type: str,
        visibility: str,
        owner_account: str
    ) -> dict:
        """
        Register a new custom image (AMI-like) from an existing instance.

        Args:
            source_instance_id (str): Instance ID as the source for the image.
            name (str): Name for the new image (should be unique for the account).
            operating_system (str): OS description (e.g., "Ubuntu 20.04").
            root_device_type (str): E.g., "ebs", "instance-store".
            visibility (str): "public" or "private".
            owner_account (str): Account ID registering the new image.

        Returns:
            dict:
                On success:
                    {
                        "success": True,
                        "message": "Custom image registered successfully.",
                        "image_id": <str>
                    }
                On failure:
                    {
                        "success": False,
                        "error": <str>
                    }

        Constraints:
            - Source instance must exist and not be terminated.
            - Image name must be unique per account.
            - Owner account must exist and not exceed image quota.
            - Image visibility (public/private) must be valid.
            - Only instance source is supported (snapshots not supported in this environment).
        """
        # Check owner account exists
        if owner_account not in self.accounts:
            return { "success": False, "error": "Owner account does not exist." }

        # Check image quota (assume "image_limit" is used)
        quota = self.accounts[owner_account]['quotas'].get('image_limit', 100)
        image_count = len([img for img in self.images.values() if img['owner_account'] == owner_account])
        if image_count >= quota:
            return { "success": False, "error": "Image quota exceeded for account." }

        # Check source_instance_id exists and is not terminated
        source_instance = self.instances.get(source_instance_id)
        if not source_instance:
            return { "success": False, "error": "Source instance does not exist." }
        if source_instance['state'] == 'terminated':
            return { "success": False, "error": "Cannot create image from terminated instance." }

        # Validate visibility
        if visibility not in ["public", "private"]:
            return { "success": False, "error": "Invalid image visibility value." }

        # Validate image name uniqueness for owner
        for img in self.images.values():
            if img['owner_account'] == owner_account and img['name'] == name:
                return { "success": False, "error": "Image name must be unique within account." }

        # Generate a unique image_id
        image_id = f"img-{uuid.uuid4().hex[:8]}"

        creation_date = datetime.utcnow().isoformat() + "Z"

        new_image = {
            "image_id": image_id,
            "name": name,
            "operating_system": operating_system,
            "root_device_type": root_device_type,
            "creation_date": creation_date,
            "visibility": visibility,
            "owner_account": owner_account
        }
        self.images[image_id] = new_image

        return {
            "success": True,
            "message": "Custom image registered successfully.",
            "image_id": image_id
        }

    def modify_instance_attribute(self, instance_id: str, updates: dict) -> dict:
        """
        Update one or more modifiable attributes of a virtual machine instance (e.g., security groups, key_pair).
        Does not allow modification of state, instance_id, launch_time, or other immutable/core fields.

        Args:
            instance_id (str): The ID of the instance to modify.
            updates (dict): A dictionary of attribute-value pairs to update. Supported keys:
                - security_groups: List[str] (list of group_ids)
                - key_pair: str
                - (other metadata fields, but not state, private_ip, launch_time, etc.)

        Returns:
            dict: {
                "success": bool,
                "message": str,  # if success
                "error": str     # if not success
            }

        Constraints:
            - Instance must exist and not be terminated.
            - Security groups must exist and be in the same VPC as the instance.
            - Cannot modify protected attributes (e.g., state, instance_id, launch_time).
        """
        # Check if instance exists
        if instance_id not in self.instances:
            return {"success": False, "error": "Instance does not exist"}

        instance = self.instances[instance_id]

        # Check if instance is terminated
        if instance["state"] == "terminated":
            return {"success": False, "error": "Cannot modify a terminated instance"}

        # Disallowed attributes to modify via this method
        protected_attrs = {"instance_id", "state", "launch_time", "instance_type", "region",
                           "availability_zone", "private_ip", "public_ip", "subnet_id", "image_id"}

        for key in updates:
            if key in protected_attrs:
                return {"success": False, "error": f"Cannot modify protected attribute: {key}"}

        # Handle security_groups update
        if "security_groups" in updates:
            new_sg_ids = updates["security_groups"]
            if not isinstance(new_sg_ids, list):
                return {"success": False, "error": "security_groups must be a list of group IDs"}

            # Get instance's VPC via subnet
            if instance["subnet_id"] not in self.subnets:
                return {"success": False, "error": "Instance's subnet does not exist in system"}

            subnet = self.subnets[instance["subnet_id"]]
            vpc_id = subnet["vpc_id"]

            # Validate each security group
            for sg_id in new_sg_ids:
                if sg_id not in self.security_groups:
                    return {"success": False, "error": f"Security group {sg_id} does not exist"}
                sg = self.security_groups[sg_id]
                if sg["vpc_id"] != vpc_id:
                    return {
                        "success": False,
                        "error": f"Security group {sg_id} belongs to a different VPC than the instance"
                    }

            # If all valid, update
            instance["security_groups"] = new_sg_ids

        # Handle key_pair update
        if "key_pair" in updates:
            key_pair_value = updates["key_pair"]
            if not isinstance(key_pair_value, str):
                return {"success": False, "error": "key_pair must be a string"}
            instance["key_pair"] = key_pair_value

        # Add support for other metadata fields in the future (e.g., tags via tag_resource)

        # Apply all valid updates (only security_groups and key_pair handled here)
        # Note: This could be extended to support tags, description, etc., depending on need.

        return {"success": True, "message": "Instance attribute(s) updated successfully."}

    def release_public_ip(self, public_ip: str) -> dict:
        """
        Release a public IP address assigned to an instance. If the IP is not currently assigned,
        this operation is idempotent and treated as a success.

        Args:
            public_ip (str): The public IP address (e.g., "203.0.113.45") to release.

        Returns:
            dict: {
                "success": True,
                "message": "Public IP released successfully."
            }
            or
            {
                "success": False,
                "error": str  # Only if invalid input
            }

        Constraints:
            - The IP address format should be valid (basic check).
            - If the IP is assigned to an instance, it will be disassociated.
            - Releasing an unassigned IP is allowed (no error).
        """
        # Inline IP format validation: IPv4 dotted-quad, numbers 0-255
        if not public_ip or not isinstance(public_ip, str):
            return {"success": False, "error": "Invalid IP address format"}
        parts = public_ip.strip().split(".")
        if len(parts) != 4:
            return {"success": False, "error": "Invalid IP address format"}
        try:
            nums = [int(part) for part in parts]
        except ValueError:
            return {"success": False, "error": "Invalid IP address format"}
        if not all(0 <= n <= 255 for n in nums):
            return {"success": False, "error": "Invalid IP address format"}

        # Search and release logic
        for instance in self.instances.values():
            if instance["public_ip"] == public_ip:
                instance["public_ip"] = ""
                break  # Only one instance should ever have this IP

        # Always return success (idempotent operation)
        return {"success": True, "message": "Public IP released successfully."}

    def update_account_quota(self, account_id: str, quota_type: str, new_limit: int) -> dict:
        """
        Request an increase in account resource limits (simulated admin/support-assisted update).

        Args:
            account_id (str): The ID of the user account requesting quota change.
            quota_type (str): The type of quota to update (e.g., "instance_limit", "vpc_limit").
            new_limit (int): The new limit value for the specified quota type.

        Returns:
            dict: {
                "success": bool,
                "message": str  # On success: confirmation of update
            }
            or
            {
                "success": False,
                "error": str  # Reason for failure
            }

        Constraints:
            - The account must exist.
            - The new limit must be non-negative.
            - This operation simulates an approved quota increase (no approval workflow enforced).
        """
        if account_id not in self.accounts:
            return { "success": False, "error": f"Account {account_id} does not exist." }

        if new_limit < 0:
            return { "success": False, "error": "New limit must be non-negative." }

        if not isinstance(quota_type, str) or not quota_type.strip():
            return { "success": False, "error": "Quota type must be a non-empty string." }

        # Update or set the quota
        self.accounts[account_id]["quotas"][quota_type] = new_limit

        message = f"Quota for {quota_type} updated to {new_limit} for account {account_id}."
        return { "success": True, "message": message }

    def tag_resource(self, resource_id: str, tags: Dict[str, str]) -> dict:
        """
        Add or update metadata tags (key-value pairs) on a specified resource.

        Args:
            resource_id (str): The unique identifier of the resource (e.g., instance_id, vpc_id).
            tags (Dict[str, str]): A dictionary of key-value tags to apply to the resource.

        Returns:
            dict: {
                "success": True,
                "message": str  # Confirmation of tagging
            }
            or
            {
                "success": False,
                "error": str  # e.g., "Resource not found"
            }

        Constraints:
            - The resource must exist in the platform (instance, image, VPC, subnet, security group, or account).
            - Tags are metadata only and do not affect resource configuration or permissions.
        """
        # Initialize tags storage if not present
        if not hasattr(self, 'tags'):
            self.tags = {}

        # List of all possible taggable resources by their ID
        taggable_resources = (
            list(self.instances.keys()) +
            list(self.images.keys()) +
            list(self.vpcs.keys()) +
            list(self.subnets.keys()) +
            list(self.security_groups.keys()) +
            list(self.accounts.keys())
        )

        if resource_id not in taggable_resources:
            return {"success": False, "error": "Resource not found"}

        # Initialize tag dictionary for this resource if not present
        if resource_id not in self.tags:
            self.tags[resource_id] = {}

        # Update with new tags (allows overwriting existing keys)
        self.tags[resource_id].update(tags)

        return {"success": True, "message": f"Tags added to resource '{resource_id}'"}
