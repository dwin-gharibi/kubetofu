import logging
import re
from typing import Any, Dict, List, Optional

from agents.core.base import (
    AgentConfig,
    BaseAgent,
    Tool,
    ToolResult,
)

logger = logging.getLogger(__name__)


ARVANCLOUD_PRICING = {
    "flavors": {
        "g2-1-1-0": {"cpu": 1, "ram": 1, "price_hour": 5000},
        "g2-2-2-0": {"cpu": 2, "ram": 2, "price_hour": 10000},
        "g2-2-4-0": {"cpu": 2, "ram": 4, "price_hour": 15000},
        "g2-4-4-0": {"cpu": 4, "ram": 4, "price_hour": 20000},
        "g2-4-8-0": {"cpu": 4, "ram": 8, "price_hour": 30000},
        "g2-8-8-0": {"cpu": 8, "ram": 8, "price_hour": 40000},
        "g2-8-16-0": {"cpu": 8, "ram": 16, "price_hour": 60000},
        "g2-16-32-0": {"cpu": 16, "ram": 32, "price_hour": 120000},
    },
    "storage": {
        "ssd": {"price_gb_month": 2000},
        "hdd": {"price_gb_month": 1000},
    },
    "network": {
        "floating_ip": {"price_month": 50000},
        "bandwidth_gb": {"price": 500},
    },
}

AWS_PRICING = {
    "flavors": {
        "t3.micro": {"cpu": 2, "ram": 1, "price_hour": 0.0104},
        "t3.small": {"cpu": 2, "ram": 2, "price_hour": 0.0208},
        "t3.medium": {"cpu": 2, "ram": 4, "price_hour": 0.0416},
        "t3.large": {"cpu": 2, "ram": 8, "price_hour": 0.0832},
        "m5.large": {"cpu": 2, "ram": 8, "price_hour": 0.096},
        "m5.xlarge": {"cpu": 4, "ram": 16, "price_hour": 0.192},
        "m5.2xlarge": {"cpu": 8, "ram": 32, "price_hour": 0.384},
    },
    "storage": {
        "gp3": {"price_gb_month": 0.08},
        "io1": {"price_gb_month": 0.125},
    },
}


class EstimateCostTool(Tool):
    name = "estimate_cost"
    description = "Estimate costs for infrastructure configuration"

    async def execute(
        self,
        configuration: str,
        provider: str = "arvancloud",
        duration_months: int = 1,
        **kwargs,
    ) -> ToolResult:
        costs = {
            "compute": 0,
            "storage": 0,
            "network": 0,
            "other": 0,
        }
        resources = []

        pricing = ARVANCLOUD_PRICING if provider == "arvancloud" else AWS_PRICING
        hours_per_month = 730

        flavor_pattern = r'flavor_id\s*=\s*"([^"]+)"'
        for match in re.finditer(flavor_pattern, configuration):
            flavor = match.group(1)
            if flavor in pricing["flavors"]:
                price_info = pricing["flavors"][flavor]
                monthly_cost = price_info["price_hour"] * hours_per_month
                costs["compute"] += monthly_cost
                resources.append(
                    {
                        "type": "compute",
                        "flavor": flavor,
                        "monthly_cost": monthly_cost,
                        "specs": f"{price_info['cpu']} vCPU, {price_info['ram']} GB RAM",
                    }
                )

        count_pattern = r"count\s*=\s*(\d+)"
        for match in re.finditer(count_pattern, configuration):
            count = int(match.group(1))
            if count > 1:
                costs["compute"] *= count

        size_pattern = r"size\s*=\s*(\d+)"
        for match in re.finditer(size_pattern, configuration):
            size_gb = int(match.group(1))
            storage_price = pricing["storage"].get(
                "ssd", pricing["storage"].get("gp3", {})
            )
            monthly_cost = size_gb * storage_price.get("price_gb_month", 0)
            costs["storage"] += monthly_cost
            resources.append(
                {
                    "type": "storage",
                    "size_gb": size_gb,
                    "monthly_cost": monthly_cost,
                }
            )

        if "floating_ip" in configuration.lower():
            ip_cost = (
                pricing.get("network", {}).get("floating_ip", {}).get("price_month", 0)
            )
            costs["network"] += ip_cost
            resources.append(
                {
                    "type": "network",
                    "resource": "floating_ip",
                    "monthly_cost": ip_cost,
                }
            )

        monthly_total = sum(costs.values())
        total_cost = monthly_total * duration_months

        currency = "IRR" if provider == "arvancloud" else "USD"

        return ToolResult(
            tool_name=self.name,
            success=True,
            output={
                "provider": provider,
                "currency": currency,
                "duration_months": duration_months,
                "breakdown": costs,
                "monthly_total": monthly_total,
                "total_cost": total_cost,
                "resources": resources,
            },
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "configuration": {
                    "type": "string",
                    "description": "Infrastructure configuration to estimate",
                },
                "provider": {
                    "type": "string",
                    "description": "Cloud provider (arvancloud, aws)",
                    "default": "arvancloud",
                },
                "duration_months": {
                    "type": "integer",
                    "description": "Duration in months for cost estimation",
                    "default": 1,
                },
            },
            "required": ["configuration"],
        }


class OptimizeCostTool(Tool):
    name = "optimize_cost"
    description = "Identify cost optimization opportunities in infrastructure"

    OPTIMIZATION_RULES = [
        {
            "id": "OPT001",
            "name": "Oversized Compute",
            "check": lambda c: re.search(r"g2-(8|16)-", c)
            or re.search(r"m5\.(2)?xlarge", c),
            "savings_percent": 30,
            "recommendation": "Consider using smaller instance sizes and scaling horizontally",
        },
        {
            "id": "OPT002",
            "name": "Reserved Instances",
            "check": lambda c: True,
            "savings_percent": 40,
            "recommendation": "Consider reserved instances for predictable workloads (40% savings)",
        },
        {
            "id": "OPT003",
            "name": "Storage Tier",
            "check": lambda c: "ssd" in c.lower() or "io1" in c.lower(),
            "savings_percent": 50,
            "recommendation": "Use HDD/gp3 for non-performance-critical storage",
        },
        {
            "id": "OPT004",
            "name": "Auto-scaling",
            "check": lambda c: "count" in c and "autoscal" not in c.lower(),
            "savings_percent": 25,
            "recommendation": "Implement auto-scaling to optimize resource usage",
        },
        {
            "id": "OPT005",
            "name": "Spot Instances",
            "check": lambda c: "spot" not in c.lower(),
            "savings_percent": 70,
            "recommendation": "Use spot/preemptible instances for fault-tolerant workloads",
        },
    ]

    async def execute(
        self,
        configuration: str,
        current_monthly_cost: float = 0,
        **kwargs,
    ) -> ToolResult:
        optimizations = []
        total_potential_savings = 0

        for rule in self.OPTIMIZATION_RULES:
            if rule["check"](configuration):
                potential_savings = current_monthly_cost * (
                    rule["savings_percent"] / 100
                )
                optimizations.append(
                    {
                        "id": rule["id"],
                        "name": rule["name"],
                        "potential_savings_percent": rule["savings_percent"],
                        "potential_savings_amount": potential_savings,
                        "recommendation": rule["recommendation"],
                    }
                )
                total_potential_savings = max(
                    total_potential_savings, potential_savings
                )

        return ToolResult(
            tool_name=self.name,
            success=True,
            output={
                "current_monthly_cost": current_monthly_cost,
                "optimizations": optimizations,
                "total_optimizations": len(optimizations),
                "max_potential_savings": total_potential_savings,
            },
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "configuration": {
                    "type": "string",
                    "description": "Infrastructure configuration to analyze",
                },
                "current_monthly_cost": {
                    "type": "number",
                    "description": "Current monthly cost for savings calculation",
                },
            },
            "required": ["configuration"],
        }


class CompareProvidersTool(Tool):
    name = "compare_providers"
    description = "Compare infrastructure costs across different cloud providers"

    async def execute(
        self,
        requirements: Dict[str, Any],
        providers: List[str] = None,
        **kwargs,
    ) -> ToolResult:
        providers = providers or ["arvancloud", "aws"]
        comparisons = []

        cpu = requirements.get("cpu", 2)
        ram = requirements.get("ram", 4)
        storage = requirements.get("storage_gb", 100)

        hours_per_month = 730

        for provider in providers:
            pricing = ARVANCLOUD_PRICING if provider == "arvancloud" else AWS_PRICING

            best_flavor = None
            best_price = float("inf")

            for flavor, info in pricing["flavors"].items():
                if info["cpu"] >= cpu and info["ram"] >= ram:
                    if info["price_hour"] < best_price:
                        best_price = info["price_hour"]
                        best_flavor = flavor

            if best_flavor:
                compute_cost = best_price * hours_per_month
                storage_cost = (
                    storage * list(pricing["storage"].values())[0]["price_gb_month"]
                )
                total = compute_cost + storage_cost

                comparisons.append(
                    {
                        "provider": provider,
                        "currency": "IRR" if provider == "arvancloud" else "USD",
                        "recommended_flavor": best_flavor,
                        "compute_monthly": compute_cost,
                        "storage_monthly": storage_cost,
                        "total_monthly": total,
                    }
                )

        def normalize_cost(c):
            if c["currency"] == "IRR":
                return c["total_monthly"] / 50000
            return c["total_monthly"]

        comparisons.sort(key=normalize_cost)
        cheapest = comparisons[0]["provider"] if comparisons else None

        return ToolResult(
            tool_name=self.name,
            success=True,
            output={
                "requirements": requirements,
                "comparisons": comparisons,
                "cheapest_provider": cheapest,
            },
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "requirements": {
                    "type": "object",
                    "description": "Resource requirements (cpu, ram, storage_gb)",
                    "properties": {
                        "cpu": {"type": "integer"},
                        "ram": {"type": "integer"},
                        "storage_gb": {"type": "integer"},
                    },
                },
                "providers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Providers to compare",
                },
            },
            "required": ["requirements"],
        }


class CostAgent(BaseAgent):
    def __init__(self, config: Optional[AgentConfig] = None, **kwargs):
        default_config = AgentConfig(
            name="CostAgent",
            description="Infrastructure cost estimation and optimization agent",
            temperature=0.1,
            max_iterations=8,
            tools=["estimate_cost", "optimize_cost", "compare_providers"],
        )
        super().__init__(config or default_config, **kwargs)

    def get_system_prompt(self) -> str:
        return """You are an expert Cost Optimization Agent for Kube-Tofu.

Your role is to:
1. Estimate infrastructure costs accurately
2. Identify cost optimization opportunities
3. Recommend right-sizing of resources
4. Compare costs across cloud providers
5. Analyze spending patterns and trends

Cost optimization strategies you recommend:
- Right-sizing: Match resources to actual needs
- Reserved/Committed: Long-term commitments for discounts
- Spot/Preemptible: Interruptible instances for batch workloads
- Auto-scaling: Scale based on demand
- Storage tiering: Use appropriate storage classes
- Network optimization: Reduce data transfer costs

When analyzing costs:
- Always provide monthly and annual projections
- Compare with alternative configurations
- Highlight the biggest cost drivers
- Quantify potential savings
- Consider both direct and indirect costs

Be specific with numbers and always show your calculations.
Use ArvanCloud as the primary provider but compare with alternatives when relevant.

Currency notes:
- ArvanCloud: Prices in IRR (Iranian Rial)
- AWS/GCP/Azure: Prices in USD"""

    def _register_default_tools(self) -> None:
        self.tool_registry.register(EstimateCostTool())
        self.tool_registry.register(OptimizeCostTool())
        self.tool_registry.register(CompareProvidersTool())

    async def process_task(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return await self.run(task, context)

    async def estimate(
        self,
        configuration: str,
        provider: str = "arvancloud",
    ) -> Dict[str, Any]:
        task = f"""Estimate the costs for this infrastructure configuration:

Provider: {provider}

{configuration}

Please:
1. Calculate compute costs
2. Calculate storage costs
3. Calculate network costs
4. Provide monthly and annual totals
5. Suggest optimizations
"""
        return await self.run(task)

    async def optimize(self, configuration: str, current_cost: float) -> Dict[str, Any]:
        task = f"""Analyze this infrastructure for cost optimization opportunities:

Current monthly cost: {current_cost}

{configuration}

Please identify all possible ways to reduce costs while maintaining functionality.
"""
        return await self.run(task)
