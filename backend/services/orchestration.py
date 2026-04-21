import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from django.conf import settings

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    
    id: str
    name: str
    agent_type: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        
        return {
            "id": self.id,
            "name": self.name,
            "agent_type": self.agent_type,
            "action": self.action,
            "parameters": self.parameters,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class Workflow:
    id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    status: WorkflowStatus = WorkflowStatus.PENDING
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_step": self.current_step,
            "error": self.error,
        }


class OrchestrationService:
    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self.step_handlers: Dict[str, Callable] = {}
        self.approval_callbacks: Dict[str, Callable] = {}
        self._event_bus = None
        
    async def get_event_bus(self):
        if self._event_bus is None:
            try:
                from services.events import EventBus
                self._event_bus = EventBus()
            except Exception:
                pass
        return self._event_bus
    
    def register_handler(
        self,
        agent_type: str,
        action: str,
        handler: Callable
    ) -> None:
        key = f"{agent_type}:{action}"
        self.step_handlers[key] = handler
        logger.info(f"Registered handler for {key}")
    
    async def create_workflow(
        self,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> Workflow:
        workflow_id = str(uuid4())
        
        workflow_steps = [
            WorkflowStep(
                id=step.get("id", str(uuid4())),
                name=step["name"],
                agent_type=step["agent_type"],
                action=step["action"],
                parameters=step.get("parameters", {}),
                depends_on=step.get("depends_on", []),
            )
            for step in steps
        ]
        
        workflow = Workflow(
            id=workflow_id,
            name=name,
            description=description,
            steps=workflow_steps,
            context=context or {},
        )
        
        self.workflows[workflow_id] = workflow
        
        event_bus = await self.get_event_bus()
        if event_bus:
            await event_bus.emit_workflow_event(
                workflow_id=workflow_id,
                step=None,
                status="created",
                data={"name": name}
            )
        
        logger.info(f"Created workflow {workflow_id}: {name}")
        return workflow
    
    async def execute_workflow(self, workflow_id: str) -> Workflow:
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.utcnow()
        
        try:
            execution_order = self._resolve_dependencies(workflow.steps)
            
            for step_batch in execution_order:
                tasks = [
                    self._execute_step(workflow, step)
                    for step in step_batch
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for step, result in zip(step_batch, results):
                    if isinstance(result, Exception):
                        step.status = StepStatus.FAILED
                        step.error = str(result)
                        workflow.error = f"Step {step.name} failed: {result}"
                        workflow.status = WorkflowStatus.FAILED
                        return workflow
                    
                    if workflow.status == WorkflowStatus.AWAITING_APPROVAL:
                        logger.info(f"Workflow {workflow_id} awaiting approval")
                        return workflow
            
            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.utcnow()
            
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.error = str(e)
            logger.error(f"Workflow {workflow_id} failed: {e}")
        
        return workflow
    
    async def _execute_step(
        self,
        workflow: Workflow,
        step: WorkflowStep
    ) -> Any:
        
        step.status = StepStatus.RUNNING
        step.started_at = datetime.utcnow()
        workflow.current_step = step.id
        
        logger.info(f"Executing step {step.name} ({step.agent_type}:{step.action})")
        
        event_bus = await self.get_event_bus()
        if event_bus:
            await event_bus.emit_workflow_event(
                workflow_id=workflow.id,
                step=step.name,
                status="running",
                data={"agent": step.agent_type}
            )
        
        try:
            handler_key = f"{step.agent_type}:{step.action}"
            handler = self.step_handlers.get(handler_key)
            
            if handler:
                params = {**step.parameters, "context": workflow.context}
                result = await handler(**params)
            else:
                logger.warning(f"No handler for {handler_key}, simulating")
                await asyncio.sleep(0.1)
                result = {"simulated": True, "step": step.name}
            
            step.result = result
            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.utcnow()
            
            workflow.context[f"step_{step.id}_result"] = result
            
            return result
            
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.completed_at = datetime.utcnow()
            raise
    
    def _resolve_dependencies(
        self,
        steps: List[WorkflowStep]
    ) -> List[List[WorkflowStep]]:
        step_map = {s.id: s for s in steps}
        in_degree = {s.id: len(s.depends_on) for s in steps}
        
        batches = []
        remaining = set(s.id for s in steps)
        
        while remaining:
            ready = [
                sid for sid in remaining
                if in_degree[sid] == 0
            ]
            
            if not ready:
                raise ValueError("Circular dependency detected")
            
            batches.append([step_map[sid] for sid in ready])
            
            for sid in ready:
                remaining.remove(sid)
                for other_id in remaining:
                    if sid in step_map[other_id].depends_on:
                        in_degree[other_id] -= 1
        
        return batches
    
    async def pause_workflow(self, workflow_id: str) -> Workflow:
        
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        if workflow.status == WorkflowStatus.RUNNING:
            workflow.status = WorkflowStatus.PAUSED
            logger.info(f"Paused workflow {workflow_id}")
        
        return workflow
    
    async def resume_workflow(self, workflow_id: str) -> Workflow:
        
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        if workflow.status in [WorkflowStatus.PAUSED, WorkflowStatus.AWAITING_APPROVAL]:
            return await self.execute_workflow(workflow_id)
        
        return workflow
    
    async def cancel_workflow(self, workflow_id: str) -> Workflow:
        
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow.status = WorkflowStatus.CANCELLED
        workflow.completed_at = datetime.utcnow()
        
        for step in workflow.steps:
            if step.status == StepStatus.PENDING:
                step.status = StepStatus.SKIPPED
        
        logger.info(f"Cancelled workflow {workflow_id}")
        return workflow
    
    async def approve_step(
        self,
        workflow_id: str,
        step_id: str,
        approved: bool,
        comment: Optional[str] = None
    ) -> Workflow:
        
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        if approved:
            logger.info(f"Approval granted for step {step_id}")
            return await self.resume_workflow(workflow_id)
        else:
            logger.info(f"Approval denied for step {step_id}: {comment}")
            workflow.status = WorkflowStatus.CANCELLED
            workflow.error = f"Approval denied: {comment}"
            return workflow
    
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        return self.workflows.get(workflow_id)
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return {"error": "Workflow not found"}
        
        return workflow.to_dict()
    
    def list_workflows(
        self,
        status: Optional[WorkflowStatus] = None
    ) -> List[Workflow]:
        workflows = list(self.workflows.values())
        if status:
            workflows = [w for w in workflows if w.status == status]
        return workflows


class WorkflowTemplates:
    @staticmethod
    def deployment_workflow(
        target: str,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        return [
            {
                "id": "plan",
                "name": "Create Infrastructure Plan",
                "agent_type": "planner",
                "action": "create_plan",
                "parameters": {"target": target, "config": config},
            },
            {
                "id": "security",
                "name": "Security Audit",
                "agent_type": "security",
                "action": "audit",
                "parameters": {},
                "depends_on": ["plan"],
            },
            {
                "id": "cost",
                "name": "Cost Analysis",
                "agent_type": "cost",
                "action": "analyze",
                "parameters": {},
                "depends_on": ["plan"],
            },
            {
                "id": "approval",
                "name": "Human Approval",
                "agent_type": "human",
                "action": "approve",
                "parameters": {"requires_approval": True},
                "depends_on": ["security", "cost"],
            },
            {
                "id": "deploy",
                "name": "Deploy Infrastructure",
                "agent_type": "deployment",
                "action": "deploy",
                "parameters": {},
                "depends_on": ["approval"],
            },
            {
                "id": "validate",
                "name": "Validate Deployment",
                "agent_type": "diagnostic",
                "action": "validate",
                "parameters": {},
                "depends_on": ["deploy"],
            },
        ]
    
    @staticmethod
    def security_scan_workflow(
        target: str
    ) -> List[Dict[str, Any]]:
        return [
            {
                "id": "vulnerability_scan",
                "name": "Vulnerability Scan",
                "agent_type": "security",
                "action": "vulnerability_scan",
                "parameters": {"target": target},
            },
            {
                "id": "compliance_check",
                "name": "Compliance Check",
                "agent_type": "security",
                "action": "compliance_check",
                "parameters": {"target": target},
            },
            {
                "id": "report",
                "name": "Generate Report",
                "agent_type": "security",
                "action": "generate_report",
                "parameters": {},
                "depends_on": ["vulnerability_scan", "compliance_check"],
            },
        ]
    
    @staticmethod
    def diagnostic_workflow(
        cluster: str
    ) -> List[Dict[str, Any]]:
        return [
            {
                "id": "collect",
                "name": "Collect Cluster Data",
                "agent_type": "diagnostic",
                "action": "collect_data",
                "parameters": {"cluster": cluster},
            },
            {
                "id": "analyze_pods",
                "name": "Analyze Pods",
                "agent_type": "diagnostic",
                "action": "analyze_pods",
                "parameters": {},
                "depends_on": ["collect"],
            },
            {
                "id": "analyze_resources",
                "name": "Analyze Resources",
                "agent_type": "diagnostic",
                "action": "analyze_resources",
                "parameters": {},
                "depends_on": ["collect"],
            },
            {
                "id": "recommendations",
                "name": "Generate Recommendations",
                "agent_type": "diagnostic",
                "action": "generate_recommendations",
                "parameters": {},
                "depends_on": ["analyze_pods", "analyze_resources"],
            },
        ]
