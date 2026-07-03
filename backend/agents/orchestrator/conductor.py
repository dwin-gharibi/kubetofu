import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from agents.core.base import BaseAgent
from agents.specialized.planner import PlannerAgent
from agents.specialized.security import SecurityAgent
from agents.specialized.cost import CostAgent
from agents.specialized.deployment import DeploymentAgent
from agents.specialized.monitoring import MonitoringAgent
from agents.specialized.evaluator import EvaluatorAgent

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Task:
    id: str
    name: str
    description: str
    agent_type: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    dependencies: List[str] = field(default_factory=list)
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "priority": self.priority.value,
            "dependencies": self.dependencies,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }


@dataclass
class WorkflowResult:
    workflow_id: str
    status: str
    tasks: List[Dict[str, Any]]
    final_output: Any
    execution_time: float
    agent_interactions: int
    errors: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentPool:
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._agent_classes: Dict[str, Type[BaseAgent]] = {
            "planner": PlannerAgent,
            "security": SecurityAgent,
            "cost": CostAgent,
            "deployment": DeploymentAgent,
            "monitoring": MonitoringAgent,
            "evaluator": EvaluatorAgent,
        }

    def get_agent(self, agent_type: str) -> BaseAgent:
        if agent_type not in self._agents:
            agent_class = self._agent_classes.get(agent_type)
            if not agent_class:
                raise ValueError(f"Unknown agent type: {agent_type}")
            self._agents[agent_type] = agent_class()
        return self._agents[agent_type]

    def reset_agent(self, agent_type: str) -> None:
        if agent_type in self._agents:
            self._agents[agent_type].memory.clear()

    def list_agents(self) -> List[str]:
        return list(self._agent_classes.keys())


class Conductor:
    WORKFLOWS = {
        "deploy": [
            {"agent": "evaluator", "task": "validate_configuration"},
            {"agent": "security", "task": "security_scan"},
            {"agent": "cost", "task": "estimate_costs"},
            {"agent": "planner", "task": "generate_plan"},
            {"agent": "deployment", "task": "execute_deployment"},
            {"agent": "monitoring", "task": "verify_health"},
        ],
        "analyze": [
            {"agent": "planner", "task": "analyze_requirements"},
            {"agent": "security", "task": "security_assessment"},
            {"agent": "cost", "task": "cost_analysis"},
            {"agent": "evaluator", "task": "quality_evaluation"},
        ],
        "optimize": [
            {"agent": "cost", "task": "find_optimizations"},
            {"agent": "security", "task": "security_review"},
            {"agent": "evaluator", "task": "validate_changes"},
            {"agent": "planner", "task": "generate_optimized_plan"},
        ],
        "migrate": [
            {"agent": "planner", "task": "analyze_source"},
            {"agent": "planner", "task": "design_migration"},
            {"agent": "security", "task": "security_validation"},
            {"agent": "cost", "task": "cost_comparison"},
            {"agent": "deployment", "task": "execute_migration"},
            {"agent": "monitoring", "task": "validate_migration"},
        ],
    }

    def __init__(
        self,
        enable_parallel: bool = True,
        max_concurrent_agents: int = 3,
        enable_consensus: bool = True,
    ):
        self.id = str(uuid.uuid4())
        self.agent_pool = AgentPool()
        self.enable_parallel = enable_parallel
        self.max_concurrent_agents = max_concurrent_agents
        self.enable_consensus = enable_consensus
        self.tasks: Dict[str, Task] = {}
        self.execution_history: List[Dict[str, Any]] = []
        self._start_time: Optional[datetime] = None

    async def run_workflow(
        self,
        workflow_name: str,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        if workflow_name not in self.WORKFLOWS:
            raise ValueError(f"Unknown workflow: {workflow_name}")

        workflow_steps = self.WORKFLOWS[workflow_name]
        return await self._execute_workflow(
            workflow_name=workflow_name,
            steps=workflow_steps,
            input_data=input_data,
            context=context or {},
        )

    async def orchestrate(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        self._start_time = datetime.utcnow()
        context = context or {}

        logger.info(f"Conductor starting orchestration: {task_description[:100]}...")

        planner = self.agent_pool.get_agent("planner")
        decomposition_result = await planner.run(
            f"Decompose this infrastructure task into subtasks: {task_description}",
            context,
        )

        subtasks = self._extract_subtasks(decomposition_result)

        tasks = self._create_task_graph(subtasks, context)
        self.tasks = {t.id: t for t in tasks}

        results = await self._execute_tasks(tasks)
        final_output = self._aggregate_results(results)
        execution_time = (datetime.utcnow() - self._start_time).total_seconds()

        return WorkflowResult(
            workflow_id=self.id,
            status="completed"
            if all(t.status == TaskStatus.COMPLETED for t in tasks)
            else "partial",
            tasks=[t.to_dict() for t in tasks],
            final_output=final_output,
            execution_time=execution_time,
            agent_interactions=len(tasks),
            errors=[t.error for t in tasks if t.error],
        )

    async def _execute_workflow(
        self,
        workflow_name: str,
        steps: List[Dict[str, str]],
        input_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> WorkflowResult:
        self._start_time = datetime.utcnow()
        tasks = []
        current_data = input_data.copy()
        errors = []

        for i, step in enumerate(steps):
            task = Task(
                id=f"{workflow_name}-{i + 1}",
                name=step["task"],
                description=f"Step {i + 1}: {step['task']}",
                agent_type=step["agent"],
                input_data=current_data.copy(),
            )
            tasks.append(task)
            self.tasks[task.id] = task

            agent = self.agent_pool.get_agent(step["agent"])
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.utcnow()

            try:
                result = await agent.run(
                    f"Execute {step['task']} with the following data: {current_data}",
                    context,
                )

                task.output_data = result
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()

                current_data["previous_result"] = result
                current_data[step["task"]] = result

            except Exception as e:
                logger.exception(f"Task {task.id} failed: {e}")
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.utcnow()
                errors.append(str(e))

                if step.get("critical", False):
                    break

        execution_time = (datetime.utcnow() - self._start_time).total_seconds()

        return WorkflowResult(
            workflow_id=f"{self.id}-{workflow_name}",
            status="completed"
            if not errors
            else "failed"
            if len(errors) == len(tasks)
            else "partial",
            tasks=[t.to_dict() for t in tasks],
            final_output=current_data,
            execution_time=execution_time,
            agent_interactions=len(tasks),
            errors=errors,
            metadata={"workflow_name": workflow_name},
        )

    def _extract_subtasks(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        subtasks = []

        if isinstance(result, dict):
            if "result" in result:
                result_data = result["result"]
                if isinstance(result_data, dict):
                    subtasks = result_data.get("subtasks", [])
                elif isinstance(result_data, str):
                    lines = result_data.split("\n")
                    for line in lines:
                        if line.strip().startswith(("-", "*", "1", "2", "3", "4", "5")):
                            subtasks.append(
                                {
                                    "task": line.strip().lstrip("-*0123456789. "),
                                    "agent": self._infer_agent_from_task(line),
                                }
                            )

        if not subtasks:
            subtasks = [
                {"task": "analyze", "agent": "planner"},
                {"task": "evaluate", "agent": "evaluator"},
                {"task": "execute", "agent": "deployment"},
            ]

        return subtasks

    def _infer_agent_from_task(self, task: str) -> str:
        task_lower = task.lower()

        if any(w in task_lower for w in ["plan", "design", "architect", "analyze"]):
            return "planner"
        elif any(
            w in task_lower for w in ["security", "scan", "vulnerability", "compliance"]
        ):
            return "security"
        elif any(w in task_lower for w in ["cost", "price", "budget", "estimate"]):
            return "cost"
        elif any(w in task_lower for w in ["deploy", "apply", "execute", "rollback"]):
            return "deployment"
        elif any(w in task_lower for w in ["monitor", "health", "alert", "metric"]):
            return "monitoring"
        elif any(w in task_lower for w in ["validate", "evaluate", "quality", "check"]):
            return "evaluator"

        return "planner"

    def _create_task_graph(
        self,
        subtasks: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[Task]:
        tasks = []
        previous_task_id = None

        for i, subtask in enumerate(subtasks):
            task = Task(
                id=f"task-{i + 1}",
                name=subtask.get("task", f"Task {i + 1}"),
                description=subtask.get("description", subtask.get("task", "")),
                agent_type=subtask.get("agent", "planner"),
                dependencies=[previous_task_id] if previous_task_id else [],
                input_data=context.copy(),
            )
            tasks.append(task)
            previous_task_id = task.id

        return tasks

    async def _execute_tasks(self, tasks: List[Task]) -> List[Task]:
        completed_tasks = set()

        while len(completed_tasks) < len(tasks):
            executable = [
                t
                for t in tasks
                if t.id not in completed_tasks
                and all(d in completed_tasks for d in t.dependencies)
            ]

            if not executable:
                break

            if self.enable_parallel and len(executable) > 1:
                batch = executable[: self.max_concurrent_agents]
                await asyncio.gather(*[self._execute_single_task(t) for t in batch])
            else:
                await self._execute_single_task(executable[0])

            for t in tasks:
                if t.status == TaskStatus.COMPLETED:
                    completed_tasks.add(t.id)

        return tasks

    async def _execute_single_task(self, task: Task) -> None:
        agent = self.agent_pool.get_agent(task.agent_type)
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()

        try:
            result = await agent.run(
                f"Execute: {task.name}\nDescription: {task.description}",
                task.input_data,
            )
            task.output_data = result
            task.status = TaskStatus.COMPLETED
        except Exception as e:
            logger.exception(f"Task {task.id} failed: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
        finally:
            task.completed_at = datetime.utcnow()

    def _aggregate_results(self, tasks: List[Task]) -> Dict[str, Any]:
        aggregated = {
            "tasks_completed": sum(
                1 for t in tasks if t.status == TaskStatus.COMPLETED
            ),
            "tasks_failed": sum(1 for t in tasks if t.status == TaskStatus.FAILED),
            "total_tasks": len(tasks),
            "results": {},
        }

        for task in tasks:
            if task.output_data:
                aggregated["results"][task.name] = task.output_data

        return aggregated

    async def get_consensus(
        self,
        question: str,
        agents: List[str] = None,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        agents = agents or ["planner", "security", "cost"]
        context = context or {}

        responses = []

        for agent_type in agents:
            agent = self.agent_pool.get_agent(agent_type)
            result = await agent.run(
                f"Provide your expert opinion on: {question}",
                context,
            )
            responses.append(
                {
                    "agent": agent_type,
                    "response": result,
                }
            )

        return {
            "question": question,
            "responses": responses,
            "agent_count": len(responses),
            "consensus_reached": True,
            "final_decision": self._synthesize_consensus(responses),
        }

    def _synthesize_consensus(self, responses: List[Dict[str, Any]]) -> str:
        return f"Consensus from {len(responses)} agents reached."

    def get_status(self) -> Dict[str, Any]:
        return {
            "conductor_id": self.id,
            "tasks": {task_id: task.to_dict() for task_id, task in self.tasks.items()},
            "available_agents": self.agent_pool.list_agents(),
            "available_workflows": list(self.WORKFLOWS.keys()),
        }
