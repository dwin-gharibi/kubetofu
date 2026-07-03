from typing import Any, Dict, List, Optional
from agents.analyzers.base import BaseAnalyzer, Issue, Severity


class IngressAnalyzer(BaseAnalyzer):
    name = "ingress"
    resource_kind = "Ingress"

    async def _get_resources(
        self,
        namespace: str,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        result = await self._kubectl("get", "ingress", namespace=namespace)
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

        tls_issues = self._check_tls(name, namespace, spec)
        issues.extend(tls_issues)

        backend_issues = await self._check_backends(name, namespace, spec)
        issues.extend(backend_issues)

        class_issues = self._check_ingress_class(name, namespace, spec)
        issues.extend(class_issues)

        lb_issues = self._check_status(name, namespace, status)
        issues.extend(lb_issues)

        return issues

    def _check_tls(
        self,
        ingress_name: str,
        namespace: str,
        spec: Dict[str, Any],
    ) -> List[Issue]:
        issues = []

        tls = spec.get("tls", [])
        rules = spec.get("rules", [])

        rule_hosts = set()
        for rule in rules:
            host = rule.get("host")
            if host:
                rule_hosts.add(host)

        tls_hosts = set()
        for tls_config in tls:
            for host in tls_config.get("hosts", []):
                tls_hosts.add(host)

        hosts_without_tls = rule_hosts - tls_hosts
        if hosts_without_tls:
            issues.append(
                self._create_issue(
                    title="Ingress hosts without TLS",
                    severity=Severity.MEDIUM,
                    resource_name=ingress_name,
                    namespace=namespace,
                    description=f"Hosts not covered by TLS: {', '.join(hosts_without_tls)}",
                    recommendation="Add TLS configuration for all hosts",
                    documentation_url="https://kubernetes.io/docs/concepts/services-networking/ingress/#tls",
                )
            )

        for tls_config in tls:
            secret_name = tls_config.get("secretName")
            if not secret_name:
                issues.append(
                    self._create_issue(
                        title="TLS configuration missing secret",
                        severity=Severity.HIGH,
                        resource_name=ingress_name,
                        namespace=namespace,
                        description="TLS block has no secretName specified",
                        recommendation="Specify a TLS secret or use cert-manager",
                    )
                )

        return issues

    async def _check_backends(
        self,
        ingress_name: str,
        namespace: str,
        spec: Dict[str, Any],
    ) -> List[Issue]:
        issues = []

        rules = spec.get("rules", [])

        for rule in rules:
            http = rule.get("http", {})
            paths = http.get("paths", [])

            for path in paths:
                backend = path.get("backend", {})
                service = backend.get("service", {})
                service_name = service.get("name")

                if service_name:
                    try:
                        await self._kubectl(
                            "get",
                            "service",
                            service_name,
                            namespace=namespace,
                        )
                    except Exception:
                        issues.append(
                            self._create_issue(
                                title="Ingress references non-existent service",
                                severity=Severity.HIGH,
                                resource_name=ingress_name,
                                namespace=namespace,
                                description=f"Backend service '{service_name}' not found",
                                recommendation=f"Create service '{service_name}' or update ingress",
                            )
                        )

        return issues

    def _check_ingress_class(
        self,
        ingress_name: str,
        namespace: str,
        spec: Dict[str, Any],
    ) -> List[Issue]:
        issues = []

        ingress_class = spec.get("ingressClassName")

        if not ingress_class:
            issues.append(
                self._create_issue(
                    title="Ingress missing ingressClassName",
                    severity=Severity.LOW,
                    resource_name=ingress_name,
                    namespace=namespace,
                    description="No ingressClassName specified",
                    recommendation="Specify ingressClassName for explicit controller binding",
                )
            )

        return issues

    def _check_status(
        self,
        ingress_name: str,
        namespace: str,
        status: Dict[str, Any],
    ) -> List[Issue]:
        issues = []

        load_balancer = status.get("loadBalancer", {})
        ingress = load_balancer.get("ingress", [])

        if not ingress:
            issues.append(
                self._create_issue(
                    title="Ingress has no load balancer assigned",
                    severity=Severity.MEDIUM,
                    resource_name=ingress_name,
                    namespace=namespace,
                    description="No IP or hostname assigned to ingress",
                    recommendation="Check ingress controller is running and configured",
                )
            )

        return issues
