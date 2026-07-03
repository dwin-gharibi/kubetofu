from typing import Any, Dict, List, Optional

from agents.analyzers.base import BaseAnalyzer, Issue, Severity


class ServiceAnalyzer(BaseAnalyzer):
    name = "service"
    resource_kind = "Service"

    async def _get_resources(
        self,
        namespace: str,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        result = await self._kubectl("get", "services", namespace=namespace)
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

        if name == "kubernetes":
            return []

        service_type = spec.get("type", "ClusterIP")
        selector = spec.get("selector", {})

        if selector:
            endpoints_issues = await self._check_endpoints(name, namespace, selector)
            issues.extend(endpoints_issues)

        if service_type == "LoadBalancer":
            lb_issues = self._check_loadbalancer(name, namespace, status)
            issues.extend(lb_issues)

        port_issues = self._check_ports(name, namespace, spec)
        issues.extend(port_issues)

        return issues

    async def _check_endpoints(
        self,
        service_name: str,
        namespace: str,
        selector: Dict[str, str],
    ) -> List[Issue]:
        issues = []

        try:
            endpoints = await self._kubectl(
                "get",
                "endpoints",
                service_name,
                namespace=namespace,
            )

            subsets = endpoints.get("subsets", [])

            if not subsets:
                issues.append(
                    self._create_issue(
                        title="Service has no endpoints",
                        severity=Severity.HIGH,
                        resource_name=service_name,
                        namespace=namespace,
                        description=f"No pods match the service selector: {selector}",
                        root_cause="No running pods with matching labels",
                        recommendation="Ensure pods exist with labels matching the service selector",
                        documentation_url="https://kubernetes.io/docs/concepts/services-networking/service/",
                    )
                )
            else:
                for subset in subsets:
                    not_ready = subset.get("notReadyAddresses", [])
                    if not_ready:
                        issues.append(
                            self._create_issue(
                                title="Service has unhealthy endpoints",
                                severity=Severity.MEDIUM,
                                resource_name=service_name,
                                namespace=namespace,
                                description=f"{len(not_ready)} endpoints are not ready",
                                recommendation="Check pod health and readiness probes",
                            )
                        )
        except Exception:
            pass

        return issues

    def _check_loadbalancer(
        self,
        service_name: str,
        namespace: str,
        status: Dict[str, Any],
    ) -> List[Issue]:
        issues = []

        load_balancer = status.get("loadBalancer", {})
        ingress = load_balancer.get("ingress", [])

        if not ingress:
            issues.append(
                self._create_issue(
                    title="LoadBalancer pending external IP",
                    severity=Severity.MEDIUM,
                    resource_name=service_name,
                    namespace=namespace,
                    description="LoadBalancer service has not been assigned an external IP",
                    root_cause="Cloud controller may not be configured or quota exceeded",
                    recommendation="Check cloud provider configuration and quotas",
                )
            )

        return issues

    def _check_ports(
        self,
        service_name: str,
        namespace: str,
        spec: Dict[str, Any],
    ) -> List[Issue]:
        issues = []

        ports = spec.get("ports", [])

        for port in ports:
            target_port = port.get("targetPort")
            port_num = port.get("port")

            if target_port is None:
                issues.append(
                    self._create_issue(
                        title="Service port missing targetPort",
                        severity=Severity.LOW,
                        resource_name=service_name,
                        namespace=namespace,
                        description=f"Port {port_num} has no explicit targetPort",
                        recommendation="Explicitly set targetPort for clarity",
                    )
                )

        return issues
