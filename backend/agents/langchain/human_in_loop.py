import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from channels.layers import get_channel_layer
from django.core.cache import cache
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ApprovalType(str, Enum):
    DEPLOYMENT = "deployment"
    DESTRUCTION = "destruction"
    SECURITY_OVERRIDE = "security_override"
    COST_THRESHOLD = "cost_threshold"
    DANGEROUS_COMMAND = "dangerous_command"
    SENSITIVE_DATA = "sensitive_data"


@dataclass
class ApprovalRequest:
    id: str
    type: ApprovalType
    title: str
    description: str
    details: Dict[str, Any]
    requester: str
    session_id: str
    created_at: datetime
    expires_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "details": self.details,
            "requester": self.requester,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "status": self.status.value,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class HumanFeedback:
    id: str
    session_id: str
    agent_output_id: str
    rating: int
    feedback_text: Optional[str]
    corrections: Optional[Dict[str, Any]]
    timestamp: datetime


class ApprovalManager:
    CACHE_PREFIX = "approval"
    DEFAULT_TIMEOUT = 300

    def __init__(self):
        self._channel_layer = None
        self._callbacks: Dict[str, Callable] = {}

    @property
    def channel_layer(self):
        if self._channel_layer is None:
            self._channel_layer = get_channel_layer()
        return self._channel_layer

    def _get_cache_key(self, request_id: str) -> str:
        return f"{self.CACHE_PREFIX}:{request_id}"

    async def request_approval(
        self,
        type: ApprovalType,
        title: str,
        description: str,
        details: Dict[str, Any],
        requester: str,
        session_id: str,
        timeout_seconds: int = None,
    ) -> ApprovalRequest:
        timeout = timeout_seconds or self.DEFAULT_TIMEOUT

        request = ApprovalRequest(
            id=str(uuid.uuid4()),
            type=type,
            title=title,
            description=description,
            details=details,
            requester=requester,
            session_id=session_id,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=timeout),
        )

        cache.set(
            self._get_cache_key(request.id),
            request.to_dict(),
            timeout=timeout + 60,
        )

        await self._notify_approval_request(request)
        logger.info(f"Created approval request: {request.id} ({type.value})")

        return request

    async def _notify_approval_request(self, request: ApprovalRequest) -> None:
        if self.channel_layer:
            await self.channel_layer.group_send(
                f"session_{request.session_id}",
                {
                    "type": "approval_request",
                    "request": request.to_dict(),
                },
            )

    async def wait_for_approval(
        self,
        request_id: str,
        poll_interval: float = 1.0,
    ) -> ApprovalRequest:
        while True:
            request_data = cache.get(self._get_cache_key(request_id))

            if not request_data:
                raise ValueError(f"Approval request {request_id} not found")

            status = ApprovalStatus(request_data["status"])

            if status != ApprovalStatus.PENDING:
                return self._dict_to_request(request_data)

            expires_at = datetime.fromisoformat(request_data["expires_at"])
            if datetime.utcnow() > expires_at:
                return await self.timeout_request(request_id)

            await asyncio.sleep(poll_interval)

    async def approve(
        self,
        request_id: str,
        approver: str,
    ) -> ApprovalRequest:
        request_data = cache.get(self._get_cache_key(request_id))

        if not request_data:
            raise ValueError(f"Request {request_id} not found")

        request_data["status"] = ApprovalStatus.APPROVED.value
        request_data["approved_by"] = approver
        request_data["approved_at"] = datetime.utcnow().isoformat()

        cache.set(self._get_cache_key(request_id), request_data)

        request = self._dict_to_request(request_data)
        await self._notify_approval_update(request)

        logger.info(f"Request {request_id} approved by {approver}")

        return request

    async def reject(
        self,
        request_id: str,
        rejector: str,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        request_data = cache.get(self._get_cache_key(request_id))

        if not request_data:
            raise ValueError(f"Request {request_id} not found")

        request_data["status"] = ApprovalStatus.REJECTED.value
        request_data["approved_by"] = rejector
        request_data["approved_at"] = datetime.utcnow().isoformat()
        request_data["rejection_reason"] = reason

        cache.set(self._get_cache_key(request_id), request_data)

        request = self._dict_to_request(request_data)
        await self._notify_approval_update(request)

        logger.info(f"Request {request_id} rejected by {rejector}: {reason}")

        return request

    async def timeout_request(self, request_id: str) -> ApprovalRequest:
        request_data = cache.get(self._get_cache_key(request_id))

        if not request_data:
            raise ValueError(f"Request {request_id} not found")

        request_data["status"] = ApprovalStatus.TIMEOUT.value

        cache.set(self._get_cache_key(request_id), request_data)

        request = self._dict_to_request(request_data)
        await self._notify_approval_update(request)

        logger.info(f"Request {request_id} timed out")

        return request

    async def _notify_approval_update(self, request: ApprovalRequest) -> None:
        if self.channel_layer:
            await self.channel_layer.group_send(
                f"session_{request.session_id}",
                {
                    "type": "approval_update",
                    "request": request.to_dict(),
                },
            )

    def _dict_to_request(self, data: Dict) -> ApprovalRequest:
        return ApprovalRequest(
            id=data["id"],
            type=ApprovalType(data["type"]),
            title=data["title"],
            description=data["description"],
            details=data["details"],
            requester=data["requester"],
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            status=ApprovalStatus(data["status"]),
            approved_by=data.get("approved_by"),
            approved_at=datetime.fromisoformat(data["approved_at"])
            if data.get("approved_at")
            else None,
            rejection_reason=data.get("rejection_reason"),
        )


class FeedbackCollector:
    CACHE_PREFIX = "feedback"

    async def collect_feedback(
        self,
        session_id: str,
        agent_output_id: str,
        rating: int,
        feedback_text: Optional[str] = None,
        corrections: Optional[Dict[str, Any]] = None,
    ) -> HumanFeedback:
        feedback = HumanFeedback(
            id=str(uuid.uuid4()),
            session_id=session_id,
            agent_output_id=agent_output_id,
            rating=max(1, min(5, rating)),
            feedback_text=feedback_text,
            corrections=corrections,
            timestamp=datetime.utcnow(),
        )

        cache_key = f"{self.CACHE_PREFIX}:{feedback.id}"
        cache.set(
            cache_key,
            {
                "id": feedback.id,
                "session_id": feedback.session_id,
                "agent_output_id": feedback.agent_output_id,
                "rating": feedback.rating,
                "feedback_text": feedback.feedback_text,
                "corrections": feedback.corrections,
                "timestamp": feedback.timestamp.isoformat(),
            },
            timeout=86400 * 30,
        )

        logger.info(f"Collected feedback: {feedback.id} (rating: {rating})")

        return feedback

    async def get_feedback_stats(self, session_id: str) -> Dict[str, Any]:
        return {
            "total_feedbacks": 0,
            "average_rating": 0,
            "positive_count": 0,
            "negative_count": 0,
        }


class HumanApprovalInput(BaseModel):
    action: str = Field(description="The action requiring approval")
    reason: str = Field(description="Why approval is needed")
    details: Optional[str] = Field(default=None, description="Technical details")


class HumanApprovalTool(BaseTool):
    name: str = "request_human_approval"
    description: str = """Request human approval before executing a sensitive action.
Use this for:
- Destructive operations (delete, destroy)
- Cost-significant deployments
- Security-sensitive changes
- Accessing production environments"""
    args_schema: type[BaseModel] = HumanApprovalInput

    session_id: str = ""
    approval_manager: ApprovalManager = None

    def __init__(self, session_id: str, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id
        self.approval_manager = ApprovalManager()

    def _run(
        self,
        action: str,
        reason: str,
        details: Optional[str] = None,
    ) -> str:
        import asyncio

        async def _async_run():
            request = await self.approval_manager.request_approval(
                type=ApprovalType.DANGEROUS_COMMAND,
                title=f"Approval Required: {action}",
                description=reason,
                details={"action": action, "technical_details": details},
                requester="agent",
                session_id=self.session_id,
            )

            result = await self.approval_manager.wait_for_approval(request.id)

            if result.status == ApprovalStatus.APPROVED:
                return f"✅ APPROVED by {result.approved_by}. You may proceed with: {action}"
            elif result.status == ApprovalStatus.REJECTED:
                return f"❌ REJECTED: {result.rejection_reason or 'No reason provided'}"
            else:
                return "⏰ TIMEOUT: Approval not received in time"

        return asyncio.get_event_loop().run_until_complete(_async_run())


class HumanInputInput(BaseModel):
    question: str = Field(description="Question to ask the human")
    options: Optional[List[str]] = Field(
        default=None, description="Optional list of choices"
    )


class HumanInputTool(BaseTool):
    name: str = "ask_human"
    description: str = """Ask the human a question when you need:
- Clarification on requirements
- Choice between options
- Missing information
- Confirmation of understanding"""
    args_schema: type[BaseModel] = HumanInputInput

    session_id: str = ""

    def __init__(self, session_id: str, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id

    def _run(
        self,
        question: str,
        options: Optional[List[str]] = None,
    ) -> str:
        if options:
            options_str = "\n".join(
                [f"{i + 1}. {opt}" for i, opt in enumerate(options)]
            )
            return f"❓ HUMAN INPUT NEEDED\n\nQuestion: {question}\n\nOptions:\n{options_str}\n\nPlease wait for human response..."

        return f"❓ HUMAN INPUT NEEDED\n\nQuestion: {question}\n\nPlease wait for human response..."


class HumanFeedbackInput(BaseModel):
    content: str = Field(description="Content to get feedback on")
    question: str = Field(default="Is this correct?", description="Feedback question")


class HumanFeedbackTool(BaseTool):
    name: str = "request_feedback"
    description: str = "Request feedback from human on your output before finalizing."
    args_schema: type[BaseModel] = HumanFeedbackInput

    def _run(
        self,
        content: str,
        question: str = "Is this correct?",
    ) -> str:
        return f"""📋 FEEDBACK REQUEST

{content}

---
{question}

Please provide your feedback (approve/reject/modify)."""


approval_manager = ApprovalManager()
feedback_collector = FeedbackCollector()


def create_human_tools(session_id: str) -> List[BaseTool]:
    return [
        HumanApprovalTool(session_id=session_id),
        HumanInputTool(session_id=session_id),
        HumanFeedbackTool(),
    ]
