import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Issue:
    id: str
    title: str
    severity: Severity
    resource_kind: str
    resource_name: str
    namespace: str
    description: str
    root_cause: Optional[str] = None
    recommendation: Optional[str] = None
    documentation_url: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AnalysisResult:
    analyzer_name: str
    namespace: str
    issues: List[Issue]
    resources_scanned: int
    scan_duration: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None

    @property
    def has_critical(self) -> bool:
        return any(i.severity == Severity.CRITICAL for i in self.issues)

    @property
    def has_high(self) -> bool:
        return any(i.severity == Severity.HIGH for i in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analyzer": self.analyzer_name,
            "namespace": self.namespace,
            "issues": [
                {
                    "id": i.id,
                    "title": i.title,
                    "severity": i.severity.value,
                    "resource": f"{i.resource_kind}/{i.resource_name}",
                    "namespace": i.namespace,
                    "description": i.description,
                    "root_cause": i.root_cause,
                    "recommendation": i.recommendation,
                    "docs": i.documentation_url,
                }
                for i in self.issues
            ],
            "resources_scanned": self.resources_scanned,
            "scan_duration": self.scan_duration,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
        }


class BaseAnalyzer(ABC):
    name: str = "base"
    resource_kind: str = "Resource"

    def __init__(self, kubeconfig: Optional[str] = None):
        self.kubeconfig = kubeconfig
        self._kubectl_base = ["kubectl"]
        if kubeconfig:
            self._kubectl_base.extend(["--kubeconfig", kubeconfig])

    async def analyze(
        self,
        namespace: str = "default",
        filters: Optional[Dict[str, Any]] = None,
    ) -> AnalysisResult:
        start_time = datetime.utcnow()

        try:
            resources = await self._get_resources(namespace, filters)

            issues = []
            for resource in resources:
                resource_issues = await self._analyze_resource(resource, namespace)
                issues.extend(resource_issues)

            issues = await self._enrich_with_events(issues, namespace)

            duration = (datetime.utcnow() - start_time).total_seconds()

            return AnalysisResult(
                analyzer_name=self.name,
                namespace=namespace,
                issues=issues,
                resources_scanned=len(resources),
                scan_duration=duration,
            )

        except Exception as e:
            logger.exception(f"Analyzer {self.name} failed: {e}")
            duration = (datetime.utcnow() - start_time).total_seconds()

            return AnalysisResult(
                analyzer_name=self.name,
                namespace=namespace,
                issues=[],
                resources_scanned=0,
                scan_duration=duration,
                error=str(e),
            )

    @abstractmethod
    async def _get_resources(
        self,
        namespace: str,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def _analyze_resource(
        self,
        resource: Dict[str, Any],
        namespace: str,
    ) -> List[Issue]:
        pass

    async def _kubectl(
        self,
        *args,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        cmd = self._kubectl_base + list(args)

        if namespace:
            cmd.extend(["-n", namespace])

        if "-o" not in args:
            cmd.extend(["-o", "json"])

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                raise Exception(f"kubectl failed: {stderr.decode()}")

            return json.loads(stdout.decode())

        except json.JSONDecodeError:
            return {"items": []}

    async def _enrich_with_events(
        self,
        issues: List[Issue],
        namespace: str,
    ) -> List[Issue]:
        if not issues:
            return issues

        try:
            events = await self._kubectl("get", "events", namespace=namespace)

            for issue in issues:
                related_events = [
                    e
                    for e in events.get("items", [])
                    if e.get("involvedObject", {}).get("name") == issue.resource_name
                    and e.get("involvedObject", {}).get("kind") == issue.resource_kind
                ]

                if related_events:
                    recent_events = sorted(
                        related_events,
                        key=lambda x: x.get("lastTimestamp", ""),
                        reverse=True,
                    )[:3]

                    event_info = []
                    for e in recent_events:
                        event_info.append(
                            f"- {e.get('type', 'Unknown')}: {e.get('message', 'No message')}"
                        )

                    if event_info:
                        issue.description += "\n\nRelated Events:\n" + "\n".join(
                            event_info
                        )

        except Exception as e:
            logger.warning(f"Failed to enrich with events: {e}")

        return issues

    def _create_issue(
        self,
        title: str,
        severity: Severity,
        resource_name: str,
        namespace: str,
        description: str,
        **kwargs,
    ) -> Issue:
        import hashlib

        id_string = f"{self.name}:{namespace}:{resource_name}:{title}"
        issue_id = hashlib.sha256(id_string.encode()).hexdigest()[:12]

        return Issue(
            id=issue_id,
            title=title,
            severity=severity,
            resource_kind=self.resource_kind,
            resource_name=resource_name,
            namespace=namespace,
            description=description,
            **kwargs,
        )
