from typing import Any, Dict, List, Optional
from agents.analyzers.base import BaseAnalyzer, Issue, Severity


class NodeAnalyzer(BaseAnalyzer):
    name = "node"
    resource_kind = "Node"

    async def _get_resources(
        self,
        namespace: str,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        result = await self._kubectl("get", "nodes")
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

        conditions = status.get("conditions", [])
        for condition in conditions:
            cond_issues = self._check_condition(name, condition)
            issues.extend(cond_issues)

        if spec.get("unschedulable"):
            issues.append(
                self._create_issue(
                    title="Node is cordoned",
                    severity=Severity.MEDIUM,
                    resource_name=name,
                    namespace="cluster",
                    description="Node marked as unschedulable",
                    recommendation="Uncordon the node when ready: kubectl uncordon "
                    + name,
                )
            )

        taint_issues = self._check_taints(name, spec.get("taints", []))
        issues.extend(taint_issues)

        capacity_issues = self._check_capacity(name, status)
        issues.extend(capacity_issues)

        return issues

    def _check_condition(
        self,
        node_name: str,
        condition: Dict[str, Any],
    ) -> List[Issue]:
        issues = []

        cond_type = condition.get("type", "")
        status = condition.get("status", "")
        reason = condition.get("reason", "")
        message = condition.get("message", "")

        if cond_type == "Ready" and status != "True":
            issues.append(
                self._create_issue(
                    title="Node not ready",
                    severity=Severity.CRITICAL,
                    resource_name=node_name,
                    namespace="cluster",
                    description=f"Node is not ready: {reason} - {message}",
                    root_cause="Node health check failed",
                    recommendation="Check kubelet logs and node resources",
                )
            )

        pressure_conditions = ["MemoryPressure", "DiskPressure", "PIDPressure"]
        if cond_type in pressure_conditions and status == "True":
            issues.append(
                self._create_issue(
                    title=f"Node under {cond_type}",
                    severity=Severity.HIGH,
                    resource_name=node_name,
                    namespace="cluster",
                    description=f"{cond_type}: {message}",
                    root_cause="Node resources running low",
                    recommendation="Free up resources or scale node pool",
                )
            )

        if cond_type == "NetworkUnavailable" and status == "True":
            issues.append(
                self._create_issue(
                    title="Node network unavailable",
                    severity=Severity.CRITICAL,
                    resource_name=node_name,
                    namespace="cluster",
                    description=message,
                    root_cause="CNI plugin issue or network configuration",
                    recommendation="Check CNI plugin status and network configuration",
                )
            )

        return issues

    def _check_taints(
        self,
        node_name: str,
        taints: List[Dict[str, Any]],
    ) -> List[Issue]:
        issues = []

        for taint in taints:
            effect = taint.get("effect", "")
            key = taint.get("key", "")

            if effect == "NoSchedule" and "node.kubernetes.io" not in key:
                issues.append(
                    self._create_issue(
                        title="Node has NoSchedule taint",
                        severity=Severity.LOW,
                        resource_name=node_name,
                        namespace="cluster",
                        description=f"Taint: {key}={taint.get('value', '')}:{effect}",
                        recommendation="Pods need matching tolerations to schedule",
                    )
                )

        return issues

    def _check_capacity(
        self,
        node_name: str,
        status: Dict[str, Any],
    ) -> List[Issue]:
        issues = []

        capacity = status.get("capacity", {})
        allocatable = status.get("allocatable", {})

        def parse_memory(value: str) -> int:
            if value.endswith("Ki"):
                return int(value[:-2]) * 1024
            elif value.endswith("Mi"):
                return int(value[:-2]) * 1024 * 1024
            elif value.endswith("Gi"):
                return int(value[:-2]) * 1024 * 1024 * 1024
            return int(value)

        try:
            cap_memory = parse_memory(capacity.get("memory", "0"))
            alloc_memory = parse_memory(allocatable.get("memory", "0"))

            if cap_memory > 0:
                overhead_pct = ((cap_memory - alloc_memory) / cap_memory) * 100

                if overhead_pct > 20:
                    issues.append(
                        self._create_issue(
                            title="High node memory overhead",
                            severity=Severity.LOW,
                            resource_name=node_name,
                            namespace="cluster",
                            description=f"{overhead_pct:.1f}% memory reserved for system",
                            recommendation="Review system reserved resources",
                        )
                    )
        except (ValueError, TypeError):
            pass

        return issues
