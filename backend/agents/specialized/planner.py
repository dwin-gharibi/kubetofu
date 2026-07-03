import json
import logging
from typing import Any, Dict, List, Optional

from agents.core.base import (
    AgentConfig,
    BaseAgent,
    Tool,
    ToolResult,
)

logger = logging.getLogger(__name__)


class AnalyzeRequirementsTool(Tool):
    name = "analyze_requirements"
    description = (
        "Analyze infrastructure requirements from a natural language description"
    )

    async def execute(self, description: str, **kwargs) -> ToolResult:
        analysis = {
            "resources": [],
            "constraints": [],
            "dependencies": [],
            "estimated_complexity": "medium",
        }

        desc_lower = description.lower()

        if "kubernetes" in desc_lower or "k8s" in desc_lower:
            analysis["resources"].append(
                {
                    "type": "kubernetes_cluster",
                    "provider": "arvancloud",
                }
            )

        if (
            "database" in desc_lower
            or "postgres" in desc_lower
            or "mysql" in desc_lower
        ):
            analysis["resources"].append(
                {
                    "type": "database",
                    "engine": "postgresql" if "postgres" in desc_lower else "mysql",
                }
            )

        if "load balancer" in desc_lower or "lb" in desc_lower:
            analysis["resources"].append(
                {
                    "type": "load_balancer",
                }
            )

        if "cdn" in desc_lower:
            analysis["resources"].append(
                {
                    "type": "cdn",
                    "provider": "arvancloud",
                }
            )

        if "storage" in desc_lower or "s3" in desc_lower:
            analysis["resources"].append(
                {
                    "type": "object_storage",
                    "provider": "arvancloud",
                }
            )

        return ToolResult(
            tool_name=self.name,
            success=True,
            output=analysis,
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Natural language description of infrastructure requirements",
                },
            },
            "required": ["description"],
        }


class GenerateTerraformTool(Tool):
    name = "generate_terraform"
    description = "Generate Terraform/OpenTofu configuration for specified resources"

    async def execute(
        self,
        resources: List[Dict[str, Any]],
        provider: str = "arvancloud",
        **kwargs,
    ) -> ToolResult:
        configs = []

        if provider == "arvancloud":
            configs.append(self._generate_arvancloud_provider())

        for resource in resources:
            resource_type = resource.get("type", "")
            config = self._generate_resource_config(resource_type, resource, provider)
            if config:
                configs.append(config)

        terraform_code = "\n\n".join(configs)

        return ToolResult(
            tool_name=self.name,
            success=True,
            output={
                "terraform_code": terraform_code,
                "provider": provider,
                "resource_count": len(resources),
            },
        )

    def _generate_arvancloud_provider(self) -> str:
        return """terraform {
  required_providers {
    arvancloud = {
      source  = "arvancloud/iaas"
      version = ">= 0.1.0"
    }
  }
}

provider "arvancloud" {
  api_key = var.arvan_api_key
  region  = var.arvan_region
}

variable "arvan_api_key" {
  type        = string
  description = "ArvanCloud API Key"
  sensitive   = true
}

variable "arvan_region" {
  type        = string
  description = "ArvanCloud region"
  default     = "ir-thr-at1"
}"""

    def _generate_resource_config(
        self,
        resource_type: str,
        resource: Dict[str, Any],
        provider: str,
    ) -> Optional[str]:
        generators = {
            "kubernetes_cluster": self._generate_k8s_config,
            "database": self._generate_database_config,
            "load_balancer": self._generate_lb_config,
            "object_storage": self._generate_storage_config,
            "virtual_machine": self._generate_vm_config,
            "network": self._generate_network_config,
            "cdn": self._generate_cdn_config,
        }

        generator = generators.get(resource_type)
        if generator:
            return generator(resource, provider)
        return None

    def _generate_k8s_config(self, resource: Dict, provider: str) -> str:
        name = resource.get("name", "main-cluster")
        return f'''# Kubernetes Cluster
resource "arvancloud_iaas_abrak" "k8s_master" {{
  name      = "{name}-master"
  region    = var.arvan_region
  flavor_id = "g2-4-4-0"
  image_id  = "ubuntu-22.04"
  
  network_interface {{
    network_id = arvancloud_iaas_network.main.id
  }}
  
  tags = ["kubernetes", "master"]
}}

resource "arvancloud_iaas_abrak" "k8s_worker" {{
  count     = 3
  name      = "{name}-worker-${{count.index + 1}}"
  region    = var.arvan_region
  flavor_id = "g2-4-4-0"
  image_id  = "ubuntu-22.04"
  
  network_interface {{
    network_id = arvancloud_iaas_network.main.id
  }}
  
  tags = ["kubernetes", "worker"]
}}'''

    def _generate_database_config(self, resource: Dict, provider: str) -> str:
        engine = resource.get("engine", "postgresql")
        return f'''# Database Instance
resource "arvancloud_iaas_abrak" "database" {{
  name      = "db-{engine}"
  region    = var.arvan_region
  flavor_id = "g2-4-8-0"
  image_id  = "ubuntu-22.04"
  
  network_interface {{
    network_id = arvancloud_iaas_network.main.id
  }}
  
  tags = ["database", "{engine}"]
}}

resource "arvancloud_iaas_volume" "db_data" {{
  name   = "db-data"
  size   = 100
  region = var.arvan_region
}}

resource "arvancloud_iaas_volume_attachment" "db_data" {{
  volume_id = arvancloud_iaas_volume.db_data.id
  server_id = arvancloud_iaas_abrak.database.id
}}'''

    def _generate_lb_config(self, resource: Dict, provider: str) -> str:
        return """# Load Balancer
resource "arvancloud_iaas_floating_ip" "lb" {
  region      = var.arvan_region
  description = "Load Balancer IP"
}"""

    def _generate_storage_config(self, resource: Dict, provider: str) -> str:
        return """# Object Storage
resource "arvancloud_iaas_volume" "storage" {
  name   = "app-storage"
  size   = 500
  region = var.arvan_region
}"""

    def _generate_vm_config(self, resource: Dict, provider: str) -> str:
        name = resource.get("name", "vm")
        flavor = resource.get("flavor", "g2-2-2-0")
        return f'''# Virtual Machine
resource "arvancloud_iaas_abrak" "{name}" {{
  name      = "{name}"
  region    = var.arvan_region
  flavor_id = "{flavor}"
  image_id  = "ubuntu-22.04"
  
  network_interface {{
    network_id = arvancloud_iaas_network.main.id
  }}
}}'''

    def _generate_network_config(self, resource: Dict, provider: str) -> str:
        return """# Network
resource "arvancloud_iaas_network" "main" {
  name   = "main-network"
  region = var.arvan_region
}

resource "arvancloud_iaas_subnet" "main" {
  name            = "main-subnet"
  network_id      = arvancloud_iaas_network.main.id
  cidr            = "10.0.0.0/24"
  enable_dhcp     = true
  gateway_ip      = "10.0.0.1"
  dns_nameservers = ["8.8.8.8", "8.8.4.4"]
}"""

    def _generate_cdn_config(self, resource: Dict, provider: str) -> str:
        domain = resource.get("domain", "example.com")
        return f'''# CDN Configuration
# Note: CDN requires ArvanCloud CDN API
# resource "arvancloud_cdn_domain" "main" {{
#   domain = "{domain}"
# }}'''

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "resources": {
                    "type": "array",
                    "description": "List of resources to generate",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "name": {"type": "string"},
                        },
                    },
                },
                "provider": {
                    "type": "string",
                    "description": "Cloud provider",
                    "default": "arvancloud",
                },
            },
            "required": ["resources"],
        }


class DecomposeTaskTool(Tool):
    name = "decompose_task"
    description = (
        "Break down a complex infrastructure task into smaller, manageable subtasks"
    )

    async def execute(self, task: str, **kwargs) -> ToolResult:
        subtasks = []
        task_lower = task.lower()

        if "deploy" in task_lower:
            subtasks.extend(
                [
                    {
                        "id": "1",
                        "task": "Validate infrastructure requirements",
                        "agent": "evaluator",
                    },
                    {
                        "id": "2",
                        "task": "Check security compliance",
                        "agent": "security",
                    },
                    {"id": "3", "task": "Estimate costs", "agent": "cost"},
                    {
                        "id": "4",
                        "task": "Generate infrastructure plan",
                        "agent": "planner",
                    },
                    {"id": "5", "task": "Execute deployment", "agent": "deployment"},
                    {"id": "6", "task": "Setup monitoring", "agent": "monitoring"},
                ]
            )
        elif "migrate" in task_lower:
            subtasks.extend(
                [
                    {
                        "id": "1",
                        "task": "Analyze current infrastructure",
                        "agent": "planner",
                    },
                    {"id": "2", "task": "Design migration plan", "agent": "planner"},
                    {"id": "3", "task": "Security assessment", "agent": "security"},
                    {"id": "4", "task": "Cost comparison", "agent": "cost"},
                    {"id": "5", "task": "Execute migration", "agent": "deployment"},
                    {"id": "6", "task": "Validate migration", "agent": "evaluator"},
                ]
            )
        else:
            subtasks.extend(
                [
                    {"id": "1", "task": f"Analyze: {task}", "agent": "planner"},
                    {"id": "2", "task": "Execute plan", "agent": "deployment"},
                ]
            )

        return ToolResult(
            tool_name=self.name,
            success=True,
            output={
                "original_task": task,
                "subtasks": subtasks,
                "total_subtasks": len(subtasks),
            },
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The complex task to decompose",
                },
            },
            "required": ["task"],
        }


class PlannerAgent(BaseAgent):
    def __init__(self, config: Optional[AgentConfig] = None, **kwargs):
        default_config = AgentConfig(
            name="PlannerAgent",
            description="Infrastructure planning and architecture design agent",
            temperature=0.2,
            max_iterations=15,
            tools=["analyze_requirements", "generate_terraform", "decompose_task"],
        )
        super().__init__(config or default_config, **kwargs)

    def get_system_prompt(self) -> str:
        return """You are an expert Infrastructure Planner Agent for Kube-Tofu.

Your role is to:
1. Analyze infrastructure requirements from natural language descriptions
2. Design optimal, scalable, and secure architectures
3. Generate Terraform/OpenTofu configurations
4. Decompose complex infrastructure tasks into manageable subtasks
5. Apply best practices for cloud infrastructure

You have deep expertise in:
- Cloud platforms (ArvanCloud, AWS, GCP, Azure)
- Infrastructure as Code (Terraform, OpenTofu, Pulumi)
- Kubernetes and container orchestration
- Networking and security best practices
- Cost optimization strategies

When planning infrastructure:
- Always consider high availability and fault tolerance
- Design for scalability from the start
- Include proper networking and security groups
- Consider cost implications
- Follow the principle of least privilege
- Use infrastructure modules for reusability

You are working with ArvanCloud as the primary cloud provider.
ArvanCloud provides IaaS services including:
- Abrak (Virtual Machines)
- Networks and Subnets
- Floating IPs
- Volumes (Block Storage)
- Load Balancers
- Object Storage
- CDN

Always generate infrastructure that follows ArvanCloud best practices."""

    def _register_default_tools(self) -> None:
        self.tool_registry.register(AnalyzeRequirementsTool())
        self.tool_registry.register(GenerateTerraformTool())
        self.tool_registry.register(DecomposeTaskTool())

    async def process_task(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return await self.run(task, context)

    async def analyze_requirements(self, description: str) -> Dict[str, Any]:
        task = f"Analyze the following infrastructure requirements and provide a detailed plan:\n\n{description}"
        return await self.run(task)

    async def generate_plan(
        self,
        requirements: Dict[str, Any],
        provider: str = "arvancloud",
    ) -> Dict[str, Any]:
        task = f"""Generate a complete infrastructure plan for the following requirements:

Requirements: {json.dumps(requirements, indent=2)}
Provider: {provider}

Please:
1. Analyze the requirements
2. Generate appropriate Terraform configurations
3. Provide deployment recommendations
"""
        return await self.run(task)
