from typing import Any, Dict, List, Optional
from agents.analyzers.base import BaseAnalyzer, Issue, Severity


class NetworkPolicyAnalyzer(BaseAnalyzer):
    name = "network_policy"
    resource_kind = "NetworkPolicy"

    async def _get_resources(
        self,
        namespace: str,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        result = await self._kubectl("get", "networkpolicies", namespace=namespace)
        return result.get("items", [])

    async def _analyze_resource(
        self,
        resource: Dict[str, Any],
        namespace: str,
    ) -> List[Issue]:
        issues = []
        name = resource["metadata"]["name"]
        spec = resource.get("spec", {})

        ingress = spec.get("ingress", [])
        spec.get("egress", [])

        for rule in ingress:
            if not rule:
                issues.append(
                    self._create_issue(
                        title="NetworkPolicy allows all ingress",
                        severity=Severity.MEDIUM,
                        resource_name=name,
                        namespace=namespace,
                        description="Empty ingress rule allows all traffic",
                        recommendation="Consider restricting ingress sources",
                    )
                )

        return issues
