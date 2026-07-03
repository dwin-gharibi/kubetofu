from typing import Any, Dict, List, Optional

from agents.analyzers.base import BaseAnalyzer, Issue, Severity


class PodAnalyzer(BaseAnalyzer):
    name = "pod"
    resource_kind = "Pod"

    async def _get_resources(
        self,
        namespace: str,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        result = await self._kubectl("get", "pods", namespace=namespace)
        pods = result.get("items", [])

        if filters:
            if filters.get("labels"):
                pass
            if filters.get("names"):
                pods = [p for p in pods if p["metadata"]["name"] in filters["names"]]

        return pods

    async def _analyze_resource(
        self,
        resource: Dict[str, Any],
        namespace: str,
    ) -> List[Issue]:
        issues = []

        name = resource["metadata"]["name"]
        status = resource.get("status", {})
        spec = resource.get("spec", {})

        phase = status.get("phase", "")

        if phase == "Pending":
            issue = self._check_pending(name, namespace, status, spec)
            if issue:
                issues.append(issue)

        elif phase == "Failed":
            issue = self._check_failed(name, namespace, status)
            if issue:
                issues.append(issue)

        for cs in status.get("containerStatuses", []):
            container_issues = self._check_container_status(name, namespace, cs)
            issues.extend(container_issues)

        for cs in status.get("initContainerStatuses", []):
            container_issues = self._check_container_status(
                name, namespace, cs, is_init=True
            )
            issues.extend(container_issues)

        for condition in status.get("conditions", []):
            condition_issues = self._check_condition(name, namespace, condition)
            issues.extend(condition_issues)

        return issues

    def _check_pending(
        self,
        name: str,
        namespace: str,
        status: Dict,
        spec: Dict,
    ) -> Optional[Issue]:
        conditions = status.get("conditions", [])

        for condition in conditions:
            if (
                condition.get("type") == "PodScheduled"
                and condition.get("status") == "False"
            ):
                reason = condition.get("reason", "Unknown")
                message = condition.get("message", "")

                if "Insufficient" in message:
                    return self._create_issue(
                        title="Pod pending due to insufficient resources",
                        severity=Severity.HIGH,
                        resource_name=name,
                        namespace=namespace,
                        description=f"Pod cannot be scheduled: {message}",
                        root_cause="Cluster lacks sufficient resources (CPU, memory, or GPU)",
                        recommendation="Scale up the cluster or reduce resource requests",
                        documentation_url="https://kubernetes.io/docs/concepts/scheduling-eviction/",
                    )

                elif "node(s) had taint" in message:
                    return self._create_issue(
                        title="Pod pending due to node taints",
                        severity=Severity.MEDIUM,
                        resource_name=name,
                        namespace=namespace,
                        description=f"Pod cannot be scheduled: {message}",
                        root_cause="No nodes match pod tolerations",
                        recommendation="Add appropriate tolerations or remove node taints",
                        documentation_url="https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/",
                    )

                else:
                    return self._create_issue(
                        title="Pod stuck in Pending state",
                        severity=Severity.MEDIUM,
                        resource_name=name,
                        namespace=namespace,
                        description=f"Scheduling failed: {reason} - {message}",
                        root_cause="Unable to schedule pod to any node",
                        recommendation="Check node availability and pod requirements",
                    )

        return None

    def _check_failed(
        self,
        name: str,
        namespace: str,
        status: Dict,
    ) -> Optional[Issue]:
        reason = status.get("reason", "Unknown")
        message = status.get("message", "")

        if reason == "Evicted":
            return self._create_issue(
                title="Pod was evicted",
                severity=Severity.HIGH,
                resource_name=name,
                namespace=namespace,
                description=f"Pod was evicted: {message}",
                root_cause="Node resource pressure or pod disruption",
                recommendation="Check node resource usage and configure appropriate QoS",
                documentation_url="https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/",
            )

        return self._create_issue(
            title="Pod in Failed state",
            severity=Severity.HIGH,
            resource_name=name,
            namespace=namespace,
            description=f"Pod failed: {reason} - {message}",
        )

    def _check_container_status(
        self,
        pod_name: str,
        namespace: str,
        cs: Dict,
        is_init: bool = False,
    ) -> List[Issue]:
        issues = []
        container_name = cs.get("name", "unknown")
        prefix = "Init container" if is_init else "Container"

        restart_count = cs.get("restartCount", 0)
        if restart_count > 5:
            state = cs.get("state", {})
            waiting = state.get("waiting", {})
            reason = waiting.get("reason", "")

            if reason == "CrashLoopBackOff":
                last_state = cs.get("lastState", {}).get("terminated", {})
                exit_code = last_state.get("exitCode", "unknown")
                term_reason = last_state.get("reason", "unknown")

                issues.append(
                    self._create_issue(
                        title=f"{prefix} in CrashLoopBackOff",
                        severity=Severity.CRITICAL,
                        resource_name=pod_name,
                        namespace=namespace,
                        description=f"{prefix} '{container_name}' has crashed {restart_count} times. "
                        f"Last exit code: {exit_code}, reason: {term_reason}",
                        root_cause="Container repeatedly crashing after startup",
                        recommendation="Check container logs with: kubectl logs {pod} -c {container} --previous",
                        documentation_url="https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/",
                    )
                )

        waiting = cs.get("state", {}).get("waiting", {})
        reason = waiting.get("reason", "")

        if reason == "ImagePullBackOff" or reason == "ErrImagePull":
            message = waiting.get("message", "")

            issues.append(
                self._create_issue(
                    title=f"{prefix} cannot pull image",
                    severity=Severity.HIGH,
                    resource_name=pod_name,
                    namespace=namespace,
                    description=f"Image pull failed for '{container_name}': {message}",
                    root_cause="Image not found, authentication issue, or network problem",
                    recommendation="Verify image name, check registry credentials, and network connectivity",
                    documentation_url="https://kubernetes.io/docs/concepts/containers/images/",
                )
            )

        terminated = cs.get("lastState", {}).get("terminated", {})
        if terminated.get("reason") == "OOMKilled":
            issues.append(
                self._create_issue(
                    title=f"{prefix} killed due to OOM",
                    severity=Severity.HIGH,
                    resource_name=pod_name,
                    namespace=namespace,
                    description=f"Container '{container_name}' was killed due to out of memory",
                    root_cause="Container exceeded its memory limit",
                    recommendation="Increase memory limits or optimize application memory usage",
                    documentation_url="https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/",
                )
            )

        return issues

    def _check_condition(
        self,
        pod_name: str,
        namespace: str,
        condition: Dict,
    ) -> List[Issue]:
        issues = []

        cond_type = condition.get("type", "")
        status = condition.get("status", "")
        reason = condition.get("reason", "")
        message = condition.get("message", "")

        if cond_type == "Ready" and status == "False":
            if reason == "ContainersNotReady":
                issues.append(
                    self._create_issue(
                        title="Pod not ready - containers not ready",
                        severity=Severity.MEDIUM,
                        resource_name=pod_name,
                        namespace=namespace,
                        description=f"Containers are not ready: {message}",
                        recommendation="Check container health and readiness probes",
                    )
                )

        return issues
