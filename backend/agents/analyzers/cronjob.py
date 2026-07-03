from typing import Any, Dict, List, Optional

from agents.analyzers.base import BaseAnalyzer, Issue, Severity


class CronJobAnalyzer(BaseAnalyzer):
    name = "cronjob"
    resource_kind = "CronJob"

    async def _get_resources(
        self,
        namespace: str,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        result = await self._kubectl("get", "cronjobs", namespace=namespace)
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

        if spec.get("suspend"):
            issues.append(
                self._create_issue(
                    title="CronJob is suspended",
                    severity=Severity.LOW,
                    resource_name=name,
                    namespace=namespace,
                    description="CronJob execution is suspended",
                    recommendation="Remove suspend flag to resume",
                )
            )

        active = status.get("active", [])
        if len(active) > 3:
            issues.append(
                self._create_issue(
                    title="CronJob has many active jobs",
                    severity=Severity.MEDIUM,
                    resource_name=name,
                    namespace=namespace,
                    description=f"{len(active)} jobs currently running",
                    recommendation="Check if jobs are completing successfully",
                )
            )

        return issues
