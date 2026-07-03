from typing import Any, Dict, List, Optional
from agents.analyzers.base import BaseAnalyzer, Issue, Severity


class HPAAnalyzer(BaseAnalyzer):
    name = "hpa"
    resource_kind = "HorizontalPodAutoscaler"

    async def _get_resources(
        self,
        namespace: str,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        result = await self._kubectl("get", "hpa", namespace=namespace)
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

        scaling_issues = self._check_scaling(name, namespace, spec, status)
        issues.extend(scaling_issues)

        metric_issues = self._check_metrics(name, namespace, status)
        issues.extend(metric_issues)

        condition_issues = self._check_conditions(name, namespace, status)
        issues.extend(condition_issues)

        return issues

    def _check_scaling(
        self,
        name: str,
        namespace: str,
        spec: Dict[str, Any],
        status: Dict[str, Any],
    ) -> List[Issue]:
        issues = []

        min_replicas = spec.get("minReplicas", 1)
        max_replicas = spec.get("maxReplicas", 1)
        current = status.get("currentReplicas", 0)
        desired = status.get("desiredReplicas", 0)

        if current >= max_replicas and desired > max_replicas:
            issues.append(
                self._create_issue(
                    title="HPA at maximum replicas",
                    severity=Severity.MEDIUM,
                    resource_name=name,
                    namespace=namespace,
                    description=f"Scaling limited at max ({max_replicas}), desired: {desired}",
                    recommendation="Consider increasing maxReplicas",
                )
            )

        if current == min_replicas and min_replicas > 1:
            issues.append(
                self._create_issue(
                    title="HPA at minimum replicas",
                    severity=Severity.LOW,
                    resource_name=name,
                    namespace=namespace,
                    description=f"Currently at minimum ({min_replicas}) replicas",
                    recommendation="Verify if minReplicas is appropriate",
                )
            )

        if max_replicas - min_replicas < 2:
            issues.append(
                self._create_issue(
                    title="HPA has narrow scaling range",
                    severity=Severity.LOW,
                    resource_name=name,
                    namespace=namespace,
                    description=f"Range: {min_replicas} to {max_replicas}",
                    recommendation="Consider widening the replica range for better scaling",
                )
            )

        return issues

    def _check_metrics(
        self,
        name: str,
        namespace: str,
        status: Dict[str, Any],
    ) -> List[Issue]:
        issues = []

        current_metrics = status.get("currentMetrics", [])

        if not current_metrics:
            issues.append(
                self._create_issue(
                    title="HPA has no current metrics",
                    severity=Severity.HIGH,
                    resource_name=name,
                    namespace=namespace,
                    description="No metrics available for scaling decisions",
                    root_cause="Metrics server may not be running or resource metrics unavailable",
                    recommendation="Ensure metrics-server is deployed and pods have resource requests",
                )
            )

        for metric in current_metrics:
            resource = metric.get("resource", {})
            current = resource.get("current", {})

            if "averageUtilization" in current:
                utilization = current["averageUtilization"]

                if utilization > 95:
                    issues.append(
                        self._create_issue(
                            title="HPA metric at critical utilization",
                            severity=Severity.HIGH,
                            resource_name=name,
                            namespace=namespace,
                            description=f"Utilization at {utilization}%",
                            recommendation="Scaling may not be keeping up with demand",
                        )
                    )

        return issues

    def _check_conditions(
        self,
        name: str,
        namespace: str,
        status: Dict[str, Any],
    ) -> List[Issue]:
        issues = []

        conditions = status.get("conditions", [])

        for condition in conditions:
            cond_type = condition.get("type", "")
            cond_status = condition.get("status", "")
            reason = condition.get("reason", "")
            message = condition.get("message", "")

            if cond_type == "ScalingActive" and cond_status == "False":
                issues.append(
                    self._create_issue(
                        title="HPA scaling not active",
                        severity=Severity.HIGH,
                        resource_name=name,
                        namespace=namespace,
                        description=f"Scaling inactive: {reason} - {message}",
                        recommendation="Check HPA target and metrics",
                    )
                )

            if cond_type == "AbleToScale" and cond_status == "False":
                issues.append(
                    self._create_issue(
                        title="HPA unable to scale",
                        severity=Severity.HIGH,
                        resource_name=name,
                        namespace=namespace,
                        description=f"Cannot scale: {reason} - {message}",
                        recommendation="Check target deployment exists and is scalable",
                    )
                )

        return issues
