import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from django.conf import settings
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    AGENT_STARTED = "agent.started"
    AGENT_THINKING = "agent.thinking"
    AGENT_ACTION = "agent.action"
    AGENT_OBSERVATION = "agent.observation"
    AGENT_COMPLETED = "agent.completed"
    AGENT_ERROR = "agent.error"
    DEPLOYMENT_QUEUED = "deployment.queued"
    DEPLOYMENT_STARTED = "deployment.started"
    DEPLOYMENT_PROGRESS = "deployment.progress"
    DEPLOYMENT_COMPLETED = "deployment.completed"
    DEPLOYMENT_FAILED = "deployment.failed"
    DEPLOYMENT_ROLLBACK = "deployment.rollback"
    RESOURCE_CREATED = "resource.created"
    RESOURCE_UPDATED = "resource.updated"
    RESOURCE_DELETED = "resource.deleted"
    RESOURCE_ERROR = "resource.error"
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_NODE_ENTER = "workflow.node.enter"
    WORKFLOW_NODE_EXIT = "workflow.node.exit"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_ERROR = "workflow.error"
    SECURITY_ALERT = "alert.security"
    COST_ALERT = "alert.cost"
    HEALTH_ALERT = "alert.health"
    USER_MESSAGE = "user.message"
    USER_APPROVAL = "user.approval"


@dataclass
class Event:
    type: EventType
    payload: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=EventType(data["type"]),
            payload=data.get("payload", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.utcnow(),
            source=data.get("source", ""),
            correlation_id=data.get("correlation_id"),
            metadata=data.get("metadata", {}),
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "Event":
        return cls.from_dict(json.loads(json_str))


class EventHandler:
    async def handle(self, event: Event) -> None:
        raise NotImplementedError


class EventBus:
    def __init__(self, backend: str = "redis"):
        self.backend = backend
        self._handlers: Dict[EventType, List[Callable]] = {}
        self._redis: Optional[redis.Redis] = None
        self._pubsub = None
        self._running = False
    
    async def connect(self) -> None:
        
        if self.backend == "redis":
            redis_url = settings.REDIS_URL if hasattr(settings, 'REDIS_URL') else "redis://localhost:6379"
            self._redis = redis.from_url(redis_url)
            self._pubsub = self._redis.pubsub()
        elif self.backend == "memory":
            pass
    
    async def disconnect(self) -> None:
        
        self._running = False
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
    
    async def publish(self, event: Event) -> None:
        channel = f"kubetofu:{event.type.value}"
        message = event.to_json()
        
        logger.debug(f"Publishing event: {event.type.value}")
        
        if self.backend == "redis" and self._redis:
            await self._redis.publish(channel, message)
        elif self.backend == "memory":
            await self._dispatch(event)
    
    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], Any],
    ) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        self._handlers[event_type].append(handler)
        
        logger.debug(f"Subscribed handler to {event_type.value}")
    
    async def start_listening(self) -> None:
        
        if self.backend != "redis" or not self._pubsub:
            return
        
        patterns = ["kubetofu:*"]
        await self._pubsub.psubscribe(*patterns)
        
        self._running = True
        
        async for message in self._pubsub.listen():
            if not self._running:
                break
            
            if message["type"] == "pmessage":
                try:
                    event = Event.from_json(message["data"])
                    await self._dispatch(event)
                except Exception as e:
                    logger.error(f"Error processing event: {e}")
    
    async def _dispatch(self, event: Event) -> None:
        
        handlers = self._handlers.get(event.type, [])
        
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Handler error for {event.type}: {e}")
        
    async def emit_agent_thinking(
        self,
        agent_name: str,
        thought: str,
        correlation_id: Optional[str] = None,
    ) -> None:
        
        await self.publish(Event(
            type=EventType.AGENT_THINKING,
            payload={
                "agent": agent_name,
                "thought": thought,
            },
            source=f"agent.{agent_name}",
            correlation_id=correlation_id,
        ))
    
    async def emit_agent_action(
        self,
        agent_name: str,
        action: str,
        tool: str,
        input_data: Any,
        correlation_id: Optional[str] = None,
    ) -> None:
        
        await self.publish(Event(
            type=EventType.AGENT_ACTION,
            payload={
                "agent": agent_name,
                "action": action,
                "tool": tool,
                "input": input_data,
            },
            source=f"agent.{agent_name}",
            correlation_id=correlation_id,
        ))
    
    async def emit_deployment_progress(
        self,
        deployment_id: str,
        progress: int,
        message: str,
        current_step: str,
    ) -> None:
        
        await self.publish(Event(
            type=EventType.DEPLOYMENT_PROGRESS,
            payload={
                "deployment_id": deployment_id,
                "progress": progress,
                "message": message,
                "current_step": current_step,
            },
            source="deployment_service",
            correlation_id=deployment_id,
        ))
    
    async def emit_workflow_node(
        self,
        workflow_id: str,
        node_name: str,
        entering: bool = True,
        data: Optional[Dict] = None,
    ) -> None:
        
        event_type = EventType.WORKFLOW_NODE_ENTER if entering else EventType.WORKFLOW_NODE_EXIT
        
        await self.publish(Event(
            type=event_type,
            payload={
                "workflow_id": workflow_id,
                "node": node_name,
                "data": data or {},
            },
            source="workflow_service",
            correlation_id=workflow_id,
        ))


event_bus = EventBus()
