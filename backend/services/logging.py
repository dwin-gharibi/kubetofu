import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogCategory(str, Enum):
    AGENT = "agent"
    TOOL = "tool"
    DEPLOYMENT = "deployment"
    TERRAFORM = "terraform"
    KUBERNETES = "kubernetes"
    SECURITY = "security"
    COST = "cost"
    SYSTEM = "system"
    USER = "user"


@dataclass
class LogEntry:
    message: str
    level: LogLevel = LogLevel.INFO
    category: LogCategory = LogCategory.SYSTEM
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    code: Optional[str] = None
    language: Optional[str] = None
    progress: Optional[int] = None
    total: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "message": self.message,
            "level": self.level.value,
            "category": self.category.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
            "code": self.code,
            "language": self.language,
            "progress": self.progress,
            "total": self.total,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class LogBuffer:
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._logs: List[LogEntry] = []
        self._lock = asyncio.Lock()

    async def add(self, entry: LogEntry) -> None:
        async with self._lock:
            self._logs.append(entry)
            if len(self._logs) > self.max_size:
                self._logs = self._logs[-self.max_size :]

    async def get_recent(
        self,
        count: int = 100,
        category: Optional[LogCategory] = None,
        session_id: Optional[str] = None,
        level: Optional[LogLevel] = None,
    ) -> List[LogEntry]:
        async with self._lock:
            filtered = self._logs

            if category:
                filtered = [l for l in filtered if l.category == category]

            if session_id:
                filtered = [l for l in filtered if l.session_id == session_id]

            if level:
                filtered = [l for l in filtered if l.level == level]

            return filtered[-count:]

    async def clear(self, session_id: Optional[str] = None) -> None:
        async with self._lock:
            if session_id:
                self._logs = [l for l in self._logs if l.session_id != session_id]
            else:
                self._logs = []


class LoggingService:
    def __init__(self):
        self.buffer = LogBuffer()
        self._subscribers: Dict[str, List[Callable]] = {}
        self._channel_layer = None

    @property
    def channel_layer(self):
        if self._channel_layer is None:
            self._channel_layer = get_channel_layer()
        return self._channel_layer

    async def log(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        category: LogCategory = LogCategory.SYSTEM,
        source: str = "",
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        code: Optional[str] = None,
        language: Optional[str] = None,
        progress: Optional[int] = None,
        total: Optional[int] = None,
        **metadata,
    ) -> LogEntry:
        entry = LogEntry(
            message=message,
            level=level,
            category=category,
            source=source,
            session_id=session_id,
            correlation_id=correlation_id,
            code=code,
            language=language,
            progress=progress,
            total=total,
            metadata=metadata,
        )

        await self.buffer.add(entry)
        await self._broadcast(entry)

        log_func = getattr(logger, level.value, logger.info)
        log_func(f"[{category.value}] {message}")

        return entry

    async def _broadcast(self, entry: LogEntry) -> None:
        try:
            if self.channel_layer:
                if entry.session_id:
                    await self.channel_layer.group_send(
                        f"logs_{entry.session_id}",
                        {
                            "type": "log_message",
                            "log": entry.to_dict(),
                        },
                    )

                await self.channel_layer.group_send(
                    "logs_global",
                    {
                        "type": "log_message",
                        "log": entry.to_dict(),
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to broadcast log: {e}")

    async def agent_thinking(
        self,
        agent_name: str,
        thought: str,
        session_id: str,
    ) -> LogEntry:
        return await self.log(
            message=thought,
            level=LogLevel.INFO,
            category=LogCategory.AGENT,
            source=f"agent.{agent_name}",
            session_id=session_id,
            agent=agent_name,
            type="thinking",
        )

    async def agent_action(
        self,
        agent_name: str,
        tool: str,
        input_data: Any,
        session_id: str,
    ) -> LogEntry:
        return await self.log(
            message=f"Executing {tool}",
            level=LogLevel.INFO,
            category=LogCategory.TOOL,
            source=f"agent.{agent_name}",
            session_id=session_id,
            code=json.dumps(input_data, indent=2)
            if isinstance(input_data, dict)
            else str(input_data),
            language="json",
            agent=agent_name,
            tool=tool,
            type="action",
        )

    async def agent_observation(
        self,
        agent_name: str,
        tool: str,
        output: str,
        session_id: str,
    ) -> LogEntry:
        return await self.log(
            message=f"Result from {tool}",
            level=LogLevel.INFO,
            category=LogCategory.TOOL,
            source=f"agent.{agent_name}",
            session_id=session_id,
            code=output[:2000] if len(output) > 2000 else output,
            agent=agent_name,
            tool=tool,
            type="observation",
        )

    async def terraform_output(
        self,
        output: str,
        session_id: str,
        is_error: bool = False,
    ) -> LogEntry:
        return await self.log(
            message="Terraform output",
            level=LogLevel.ERROR if is_error else LogLevel.INFO,
            category=LogCategory.TERRAFORM,
            source="terraform",
            session_id=session_id,
            code=output,
            language="hcl",
        )

    async def deployment_progress(
        self,
        message: str,
        progress: int,
        total: int,
        session_id: str,
    ) -> LogEntry:
        return await self.log(
            message=message,
            level=LogLevel.INFO,
            category=LogCategory.DEPLOYMENT,
            source="deployment",
            session_id=session_id,
            progress=progress,
            total=total,
        )

    async def security_finding(
        self,
        title: str,
        severity: str,
        description: str,
        session_id: str,
    ) -> LogEntry:
        level = LogLevel.ERROR if severity in ["critical", "high"] else LogLevel.WARNING

        return await self.log(
            message=f"[{severity.upper()}] {title}",
            level=level,
            category=LogCategory.SECURITY,
            source="security_scanner",
            session_id=session_id,
            severity=severity,
            description=description,
        )

    async def get_logs(
        self,
        session_id: Optional[str] = None,
        category: Optional[LogCategory] = None,
        count: int = 100,
    ) -> List[Dict[str, Any]]:
        entries = await self.buffer.get_recent(
            count=count,
            category=category,
            session_id=session_id,
        )
        return [e.to_dict() for e in entries]


logging_service = LoggingService()
