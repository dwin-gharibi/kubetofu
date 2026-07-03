from typing import Any, Dict, List, Optional
from agents.analyzers.base import BaseAnalyzer, Issue, Severity


class DeploymentAnalyzer(BaseAnalyzer):
    name = "deployment"
    resource_kind = "Deployment"

    async def _get_resources(
        self,
        namespace: str,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        result = await self._kubectl("get", "deployments", namespace=namespace)
        return result.get("items", [])

    async def _analyze_resource(
        self,
        resource: Dict[str, Any],
        namespace: str,
    ) -> List[Issue]:
        issues = []
        name = resource["metadata"]["name"]
        spec = resource.get("spec", {})
        status = resource.get("status", {})

        desired = spec.get("replicas", 1)
        available = status.get("availableReplicas", 0)

        if available < desired:
            issues.append(
                self._create_issue(
                    title="Deployment not fully available",
                    severity=Severity.HIGH,
                    resource_name=name,
                    namespace=namespace,
                    description=f"Only {available}/{desired} replicas available",
                    recommendation="Check pod status and events",
                )
            )

        containers = spec.get("template", {}).get("spec", {}).get("containers", [])
        for container in containers:
            resources = container.get("resources", {})
            if not resources.get("limits"):
                issues.append(
                    self._create_issue(
                        title="Container missing resource limits",
                        severity=Severity.MEDIUM,
                        resource_name=name,
                        namespace=namespace,
                        description=f"Container '{container.get('name')}' has no resource limits",
                        recommendation="Set CPU and memory limits",
                    )
                )

        return issues
