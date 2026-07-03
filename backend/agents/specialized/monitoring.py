import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.core.base import (
    AgentConfig,
    BaseAgent,
    Tool,
    ToolResult,
)

logger = logging.getLogger(__name__)


class CheckInfrastructureHealthTool(Tool):
    name = "check_infrastructure_health"
    description = "Check the health status of infrastructure components"

    async def execute(
        self,
        working_dir: str = None,
        resources: List[str] = None,
        **kwargs,
    ) -> ToolResult:
        health_status = {
            "status": "healthy",
            "components": [],
            "issues": [],
            "checked_at": datetime.utcnow().isoformat(),
        }

        if working_dir:
            try:
                result = await asyncio.create_subprocess_exec(
                    "tofu",
                    "state",
                    "list",
                    cwd=working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await result.communicate()

                if result.returncode == 0:
                    resources = stdout.decode().strip().split("\n")
                    health_status["components"].append(
                        {
                            "name": "terraform_state",
                            "status": "healthy",
                            "resource_count": len(resources),
                        }
                    )
                else:
                    health_status["components"].append(
                        {
                            "name": "terraform_state",
                            "status": "error",
                            "error": stderr.decode(),
                        }
                    )
                    health_status["status"] = "degraded"
            except Exception as e:
                health_status["issues"].append(f"Could not check Terraform state: {e}")

        try:
            result = await asyncio.create_subprocess_exec(
                "kubectl",
                "get",
                "nodes",
                "-o",
                "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                nodes_data = json.loads(stdout.decode())
                nodes = nodes_data.get("items", [])

                healthy_nodes = 0
                for node in nodes:
                    conditions = node.get("status", {}).get("conditions", [])
                    ready = any(
                        c.get("type") == "Ready" and c.get("status") == "True"
                        for c in conditions
                    )
                    if ready:
                        healthy_nodes += 1

                health_status["components"].append(
                    {
                        "name": "kubernetes",
                        "status": "healthy"
                        if healthy_nodes == len(nodes)
                        else "degraded",
                        "total_nodes": len(nodes),
                        "healthy_nodes": healthy_nodes,
                    }
                )
        except FileNotFoundError:
            pass
        except Exception as e:
            health_status["issues"].append(f"Could not check Kubernetes: {e}")

        if health_status["issues"]:
            health_status["status"] = "degraded"
        if any(c.get("status") == "error" for c in health_status["components"]):
            health_status["status"] = "unhealthy"

        return ToolResult(
            tool_name=self.name,
            success=True,
            output=health_status,
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for Terraform state",
                },
                "resources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific resources to check",
                },
            },
        }


class GetResourceMetricsTool(Tool):
    name = "get_resource_metrics"
    description = "Collect metrics for infrastructure resources"

    async def execute(
        self,
        resource_type: str = "all",
        time_range: str = "1h",
        **kwargs,
    ) -> ToolResult:
        metrics = {
            "collected_at": datetime.utcnow().isoformat(),
            "time_range": time_range,
            "resources": [],
        }

        try:
            result = await asyncio.create_subprocess_exec(
                "kubectl",
                "top",
                "nodes",
                "--no-headers",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                for line in stdout.decode().strip().split("\n"):
                    if line:
                        parts = line.split()
                        if len(parts) >= 4:
                            metrics["resources"].append(
                                {
                                    "type": "node",
                                    "name": parts[0],
                                    "cpu": parts[1],
                                    "memory": parts[3],
                                }
                            )
        except:
            pass

        try:
            result = await asyncio.create_subprocess_exec(
                "kubectl",
                "top",
                "pods",
                "--all-namespaces",
                "--no-headers",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                for line in stdout.decode().strip().split("\n")[:10]:
                    if line:
                        parts = line.split()
                        if len(parts) >= 4:
                            metrics["resources"].append(
                                {
                                    "type": "pod",
                                    "namespace": parts[0],
                                    "name": parts[1],
                                    "cpu": parts[2],
                                    "memory": parts[3],
                                }
                            )
        except:
            pass

        return ToolResult(
            tool_name=self.name,
            success=True,
            output=metrics,
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "resource_type": {
                    "type": "string",
                    "description": "Type of resources to get metrics for",
                    "default": "all",
                },
                "time_range": {
                    "type": "string",
                    "description": "Time range for metrics (1h, 24h, 7d)",
                    "default": "1h",
                },
            },
        }


class DetectAnomaliesTool(Tool):
    name = "detect_anomalies"
    description = "Detect anomalies in infrastructure metrics and behavior"

    THRESHOLDS = {
        "cpu_percent": 80,
        "memory_percent": 85,
        "disk_percent": 90,
        "error_rate_percent": 5,
    }

    async def execute(
        self,
        metrics: Dict[str, Any] = None,
        thresholds: Dict[str, float] = None,
        **kwargs,
    ) -> ToolResult:
        thresholds = thresholds or self.THRESHOLDS
        anomalies = []

        if metrics:
            for resource in metrics.get("resources", []):
                cpu = resource.get("cpu", "0%").replace("m", "").replace("%", "")
                try:
                    cpu_value = float(cpu) / 10
                    if cpu_value > thresholds.get("cpu_percent", 80):
                        anomalies.append(
                            {
                                "type": "high_cpu",
                                "resource": resource.get("name"),
                                "value": cpu_value,
                                "threshold": thresholds.get("cpu_percent"),
                                "severity": "warning" if cpu_value < 90 else "critical",
                            }
                        )
                except ValueError:
                    pass

                memory = (
                    resource.get("memory", "0Mi").replace("Mi", "").replace("Gi", "000")
                )
                try:
                    float(memory)
                except ValueError:
                    pass

        return ToolResult(
            tool_name=self.name,
            success=True,
            output={
                "anomalies": anomalies,
                "total_anomalies": len(anomalies),
                "checked_at": datetime.utcnow().isoformat(),
            },
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "metrics": {
                    "type": "object",
                    "description": "Metrics to analyze for anomalies",
                },
                "thresholds": {
                    "type": "object",
                    "description": "Custom thresholds for anomaly detection",
                },
            },
        }


class GenerateAlertTool(Tool):
    name = "generate_alert"
    description = "Generate an alert for infrastructure issues"

    async def execute(
        self,
        title: str,
        message: str,
        severity: str = "warning",
        resource: str = None,
        **kwargs,
    ) -> ToolResult:
        alert = {
            "id": f"alert-{datetime.utcnow().timestamp()}",
            "title": title,
            "message": message,
            "severity": severity,
            "resource": resource,
            "created_at": datetime.utcnow().isoformat(),
            "status": "active",
        }

        logger.warning(f"ALERT [{severity.upper()}]: {title} - {message}")

        return ToolResult(
            tool_name=self.name,
            success=True,
            output=alert,
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Alert title",
                },
                "message": {
                    "type": "string",
                    "description": "Alert message",
                },
                "severity": {
                    "type": "string",
                    "description": "Alert severity (info, warning, critical)",
                    "default": "warning",
                },
                "resource": {
                    "type": "string",
                    "description": "Affected resource",
                },
            },
            "required": ["title", "message"],
        }


class MonitoringAgent(BaseAgent):
    def __init__(self, config: Optional[AgentConfig] = None, **kwargs):
        default_config = AgentConfig(
            name="MonitoringAgent",
            description="Infrastructure monitoring and observability agent",
            temperature=0.1,
            max_iterations=10,
            tools=[
                "check_infrastructure_health",
                "get_resource_metrics",
                "detect_anomalies",
                "generate_alert",
            ],
        )
        super().__init__(config or default_config, **kwargs)

    def get_system_prompt(self) -> str:
        return """You are an expert Monitoring Agent for Kube-Tofu.

Your role is to:
1. Monitor infrastructure health continuously
2. Collect and analyze resource metrics
3. Detect anomalies and potential issues
4. Generate alerts for critical problems
5. Provide insights and recommendations

Monitoring best practices you follow:
- Monitor at multiple levels (infrastructure, application, business)
- Set appropriate thresholds for alerts
- Avoid alert fatigue with proper severity levels
- Correlate events across systems
- Maintain historical data for trend analysis
- Provide actionable insights, not just data

When monitoring:
- Focus on the four golden signals: Latency, Traffic, Errors, Saturation
- Watch for resource exhaustion trends
- Detect configuration drift
- Monitor security-related events
- Track deployment impacts

Alert severity guidelines:
- CRITICAL: Immediate action required, service impact
- WARNING: Action needed soon, potential issues
- INFO: Informational, no immediate action needed

Always provide context and recommended actions with alerts."""

    def _register_default_tools(self) -> None:
        self.tool_registry.register(CheckInfrastructureHealthTool())
        self.tool_registry.register(GetResourceMetricsTool())
        self.tool_registry.register(DetectAnomaliesTool())
        self.tool_registry.register(GenerateAlertTool())

    async def process_task(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return await self.run(task, context)

    async def check_health(self, working_dir: str = None) -> Dict[str, Any]:
        task = f"""Check the health of the infrastructure{" in " + working_dir if working_dir else ""}:

1. Check all infrastructure components
2. Collect current metrics
3. Detect any anomalies
4. Generate alerts if needed
5. Provide a health summary
"""
        return await self.run(task, {"working_dir": working_dir})

    async def analyze_metrics(self, time_range: str = "1h") -> Dict[str, Any]:
        task = f"""Analyze infrastructure metrics for the last {time_range}:

1. Collect metrics for all resources
2. Identify trends and patterns
3. Detect any anomalies
4. Provide recommendations
"""
        return await self.run(task)
