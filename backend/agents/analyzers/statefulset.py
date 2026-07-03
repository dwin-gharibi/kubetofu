from typing import Any, Dict, List, Optional
from agents.analyzers.base import BaseAnalyzer, Issue, Severity


class StatefulSetAnalyzer(BaseAnalyzer):
    name = "statefulset"
    resource_kind = "StatefulSet"

    async def _get_resources(
        self,
        namespace: str,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        result = await self._kubectl("get", "statefulsets", namespace=namespace)
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
        ready = status.get("readyReplicas", 0)

        if ready < desired:
            issues.append(
                self._create_issue(
                    title="StatefulSet not fully ready",
                    severity=Severity.HIGH,
                    resource_name=name,
                    namespace=namespace,
                    description=f"Only {ready}/{desired} replicas ready",
                    recommendation="Check pod status and PVC bindings",
                )
            )

        return issues
