from typing import Any, Dict, List, Optional
from agents.analyzers.base import BaseAnalyzer, Issue, Severity


class PVCAnalyzer(BaseAnalyzer):
    name = "pvc"
    resource_kind = "PersistentVolumeClaim"

    async def _get_resources(
        self,
        namespace: str,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        result = await self._kubectl("get", "pvc", namespace=namespace)
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

        phase = status.get("phase", "")

        if phase == "Pending":
            issues.extend(self._analyze_pending(name, namespace, spec, status))
        elif phase == "Lost":
            issues.append(
                self._create_issue(
                    title="PVC in Lost state",
                    severity=Severity.CRITICAL,
                    resource_name=name,
                    namespace=namespace,
                    description="The bound PersistentVolume was deleted",
                    root_cause="Underlying storage was deleted",
                    recommendation="Recreate the PV or restore from backup",
                )
            )

        return issues

    def _analyze_pending(
        self,
        name: str,
        namespace: str,
        spec: Dict[str, Any],
        status: Dict[str, Any],
    ) -> List[Issue]:
        issues = []

        storage_class = spec.get("storageClassName", "")
        access_modes = spec.get("accessModes", [])
        resources = spec.get("resources", {}).get("requests", {})
        storage_request = resources.get("storage", "")

        issues.append(
            self._create_issue(
                title="PVC stuck in Pending state",
                severity=Severity.HIGH,
                resource_name=name,
                namespace=namespace,
                description=f"PVC requesting {storage_request} with storage class '{storage_class}'",
                root_cause="No matching PV available or storage provisioner issue",
                recommendation="Check storage class availability and provisioner logs",
                documentation_url="https://kubernetes.io/docs/concepts/storage/persistent-volumes/",
                raw_data={
                    "storage_class": storage_class,
                    "access_modes": access_modes,
                    "storage_request": storage_request,
                },
            )
        )

        if not storage_class:
            issues.append(
                self._create_issue(
                    title="PVC has no storage class",
                    severity=Severity.MEDIUM,
                    resource_name=name,
                    namespace=namespace,
                    description="PVC does not specify a storage class",
                    recommendation="Specify storageClassName or configure a default storage class",
                )
            )

        if "ReadWriteMany" in access_modes:
            issues.append(
                self._create_issue(
                    title="PVC requires ReadWriteMany access",
                    severity=Severity.LOW,
                    resource_name=name,
                    namespace=namespace,
                    description="RWX access mode requires compatible storage (NFS, CephFS, etc.)",
                    recommendation="Ensure storage class supports ReadWriteMany",
                )
            )

        return issues
