import logging
from typing import Any, Dict, List, Optional, TypedDict, Annotated
from datetime import datetime
import operator

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict):
    task: str
    context: Dict[str, Any]
    messages: Annotated[List[Dict[str, Any]], operator.add]
    current_agent: str
    iteration: int
    analysis: Optional[Dict[str, Any]]
    security_report: Optional[Dict[str, Any]]
    cost_estimate: Optional[Dict[str, Any]]
    plan: Optional[Dict[str, Any]]
    deployment_result: Optional[Dict[str, Any]]
    diagnostic_report: Optional[Dict[str, Any]]

    should_deploy: bool
    requires_approval: bool
    approved: bool

    final_output: Optional[str]
    error: Optional[str]
    status: str


class AgentMessage(BaseModel):
    agent: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KubeTofuGraph:
    def __init__(self, agents: Dict[str, Any], checkpointer: Optional[Any] = None):
        self.agents = agents
        self.checkpointer = checkpointer or MemorySaver()
        self._graphs = {}

    def _create_deploy_graph(self) -> StateGraph:
        graph = StateGraph(WorkflowState)

        graph.add_node("analyze", self._analyze_node)
        graph.add_node("security_check", self._security_node)
        graph.add_node("cost_estimate", self._cost_node)
        graph.add_node("generate_plan", self._plan_node)
        graph.add_node("aggregate", self._aggregate_node)
        graph.add_node("await_approval", self._approval_node)
        graph.add_node("deploy", self._deploy_node)
        graph.add_node("verify", self._verify_node)
        graph.add_node("finalize", self._finalize_node)
        graph.set_entry_point("analyze")
        graph.add_edge("analyze", "security_check")
        graph.add_edge("analyze", "cost_estimate")
        graph.add_edge("security_check", "generate_plan")
        graph.add_edge("cost_estimate", "generate_plan")
        graph.add_edge("generate_plan", "aggregate")
        graph.add_conditional_edges(
            "aggregate",
            self._should_await_approval,
            {
                "await_approval": "await_approval",
                "deploy": "deploy",
            },
        )
        graph.add_conditional_edges(
            "await_approval",
            self._check_approval,
            {
                "deploy": "deploy",
                "end": "finalize",
            },
        )
        graph.add_edge("deploy", "verify")
        graph.add_edge("verify", "finalize")
        graph.add_edge("finalize", END)

        return graph.compile(checkpointer=self.checkpointer)

    def _create_analyze_graph(self) -> StateGraph:
        graph = StateGraph(WorkflowState)

        graph.add_node("analyze", self._analyze_node)
        graph.add_node("security_check", self._security_node)
        graph.add_node("cost_estimate", self._cost_node)
        graph.add_node("evaluate", self._evaluate_node)
        graph.add_node("finalize", self._finalize_node)

        graph.set_entry_point("analyze")
        graph.add_edge("analyze", "security_check")
        graph.add_edge("analyze", "cost_estimate")
        graph.add_edge("security_check", "evaluate")
        graph.add_edge("cost_estimate", "evaluate")
        graph.add_edge("evaluate", "finalize")
        graph.add_edge("finalize", END)

        return graph.compile(checkpointer=self.checkpointer)

    def _create_diagnose_graph(self) -> StateGraph:
        graph = StateGraph(WorkflowState)

        graph.add_node("scan_cluster", self._scan_cluster_node)
        graph.add_node("analyze_issues", self._analyze_issues_node)
        graph.add_node("research_solutions", self._research_node)
        graph.add_node("generate_report", self._diagnostic_report_node)
        graph.add_node("finalize", self._finalize_node)

        graph.set_entry_point("scan_cluster")
        graph.add_edge("scan_cluster", "analyze_issues")
        graph.add_edge("analyze_issues", "research_solutions")
        graph.add_edge("research_solutions", "generate_report")
        graph.add_edge("generate_report", "finalize")
        graph.add_edge("finalize", END)

        return graph.compile(checkpointer=self.checkpointer)

    def get_graph(self, workflow_type: str) -> StateGraph:
        if workflow_type not in self._graphs:
            if workflow_type == "deploy":
                self._graphs[workflow_type] = self._create_deploy_graph()
            elif workflow_type == "analyze":
                self._graphs[workflow_type] = self._create_analyze_graph()
            elif workflow_type == "diagnose":
                self._graphs[workflow_type] = self._create_diagnose_graph()
            else:
                raise ValueError(f"Unknown workflow type: {workflow_type}")

        return self._graphs[workflow_type]

    async def run(
        self,
        workflow_type: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        graph = self.get_graph(workflow_type)

        initial_state: WorkflowState = {
            "task": task,
            "context": context or {},
            "messages": [],
            "current_agent": "",
            "iteration": 0,
            "analysis": None,
            "security_report": None,
            "cost_estimate": None,
            "plan": None,
            "deployment_result": None,
            "diagnostic_report": None,
            "should_deploy": False,
            "requires_approval": True,
            "approved": False,
            "final_output": None,
            "error": None,
            "status": "started",
        }

        config = config or {"configurable": {"thread_id": "default"}}

        try:
            result = await graph.ainvoke(initial_state, config)
            return result
        except Exception as e:
            logger.exception(f"Workflow {workflow_type} failed: {e}")
            return {**initial_state, "error": str(e), "status": "failed"}

    async def stream(
        self,
        workflow_type: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        graph = self.get_graph(workflow_type)

        initial_state: WorkflowState = {
            "task": task,
            "context": context or {},
            "messages": [],
            "current_agent": "",
            "iteration": 0,
            "analysis": None,
            "security_report": None,
            "cost_estimate": None,
            "plan": None,
            "deployment_result": None,
            "diagnostic_report": None,
            "should_deploy": False,
            "requires_approval": True,
            "approved": False,
            "final_output": None,
            "error": None,
            "status": "started",
        }

        config = config or {"configurable": {"thread_id": "default"}}

        async for event in graph.astream(initial_state, config, stream_mode="updates"):
            yield event

    async def _analyze_node(self, state: WorkflowState) -> Dict[str, Any]:
        planner = self.agents.get("planner")
        if not planner:
            return {"error": "Planner agent not available"}

        result = await planner.run(
            f"Analyze this infrastructure request: {state['task']}",
            state.get("context"),
        )

        return {
            "analysis": {"output": result.output, "actions": result.actions},
            "messages": [
                {"agent": "planner", "type": "analysis", "content": result.output}
            ],
            "current_agent": "planner",
        }

    async def _security_node(self, state: WorkflowState) -> Dict[str, Any]:
        security = self.agents.get("security")
        if not security:
            return {"error": "Security agent not available"}

        analysis = state.get("analysis", {})
        result = await security.run(
            f"Security scan for: {state['task']}\nAnalysis: {analysis}",
            state.get("context"),
        )

        return {
            "security_report": {"output": result.output, "actions": result.actions},
            "messages": [
                {
                    "agent": "security",
                    "type": "security_check",
                    "content": result.output,
                }
            ],
        }

    async def _cost_node(self, state: WorkflowState) -> Dict[str, Any]:
        cost = self.agents.get("cost")
        if not cost:
            return {"error": "Cost agent not available"}

        analysis = state.get("analysis", {})
        result = await cost.run(
            f"Cost estimate for: {state['task']}\nAnalysis: {analysis}",
            state.get("context"),
        )

        return {
            "cost_estimate": {"output": result.output, "actions": result.actions},
            "messages": [
                {"agent": "cost", "type": "cost_estimate", "content": result.output}
            ],
        }

    async def _plan_node(self, state: WorkflowState) -> Dict[str, Any]:
        planner = self.agents.get("planner")
        if not planner:
            return {"error": "Planner agent not available"}

        result = await planner.run(
            f"""Generate Terraform configuration for: {state["task"]}
            
Security considerations: {state.get("security_report", {}).get("output", "N/A")}
Cost constraints: {state.get("cost_estimate", {}).get("output", "N/A")}""",
            state.get("context"),
        )

        return {
            "plan": {"output": result.output, "actions": result.actions},
            "messages": [
                {"agent": "planner", "type": "plan", "content": result.output}
            ],
            "should_deploy": True,
        }

    async def _aggregate_node(self, state: WorkflowState) -> Dict[str, Any]:
        requires_approval = True

        security = state.get("security_report", {}).get("output", "")
        if "CRITICAL" in str(security).upper():
            requires_approval = True

        state.get("cost_estimate", {}).get("output", "")

        return {
            "requires_approval": requires_approval,
            "messages": [
                {"agent": "system", "type": "aggregate", "content": "Analysis complete"}
            ],
        }

    async def _approval_node(self, state: WorkflowState) -> Dict[str, Any]:
        context = state.get("context", {})
        auto_approve = context.get("auto_approve", False)

        return {
            "approved": auto_approve,
            "messages": [
                {
                    "agent": "system",
                    "type": "approval",
                    "content": f"Auto-approve: {auto_approve}",
                }
            ],
        }

    async def _deploy_node(self, state: WorkflowState) -> Dict[str, Any]:
        deployment = self.agents.get("deployment")
        if not deployment:
            return {"error": "Deployment agent not available"}

        plan = state.get("plan", {}).get("output", "")
        result = await deployment.run(
            f"Deploy this infrastructure:\n{plan}",
            state.get("context"),
        )

        return {
            "deployment_result": {"output": result.output, "actions": result.actions},
            "messages": [
                {"agent": "deployment", "type": "deploy", "content": result.output}
            ],
        }

    async def _verify_node(self, state: WorkflowState) -> Dict[str, Any]:
        diagnostic = self.agents.get("diagnostic")
        if not diagnostic:
            return {
                "messages": [
                    {
                        "agent": "system",
                        "type": "verify",
                        "content": "Verification skipped",
                    }
                ]
            }

        result = await diagnostic.run(
            "Verify the deployment was successful. Check for any issues.",
            state.get("context"),
        )

        return {
            "messages": [
                {"agent": "diagnostic", "type": "verify", "content": result.output}
            ],
        }

    async def _evaluate_node(self, state: WorkflowState) -> Dict[str, Any]:
        return {
            "messages": [
                {
                    "agent": "system",
                    "type": "evaluate",
                    "content": "Evaluation complete",
                }
            ],
        }

    async def _scan_cluster_node(self, state: WorkflowState) -> Dict[str, Any]:
        diagnostic = self.agents.get("diagnostic")
        if not diagnostic:
            return {"error": "Diagnostic agent not available"}

        result = await diagnostic.run(
            f"Scan the Kubernetes cluster for issues: {state['task']}",
            state.get("context"),
        )

        return {
            "diagnostic_report": {"scan": result.output},
            "messages": [
                {"agent": "diagnostic", "type": "scan", "content": result.output}
            ],
        }

    async def _analyze_issues_node(self, state: WorkflowState) -> Dict[str, Any]:
        diagnostic = self.agents.get("diagnostic")
        if not diagnostic:
            return state

        scan = state.get("diagnostic_report", {}).get("scan", "")
        result = await diagnostic.run(
            f"Analyze these cluster issues and determine root causes:\n{scan}",
            state.get("context"),
        )

        current_report = state.get("diagnostic_report", {})
        current_report["analysis"] = result.output

        return {
            "diagnostic_report": current_report,
            "messages": [
                {"agent": "diagnostic", "type": "analyze", "content": result.output}
            ],
        }

    async def _research_node(self, state: WorkflowState) -> Dict[str, Any]:
        research = self.agents.get("research")
        if not research:
            return state

        analysis = state.get("diagnostic_report", {}).get("analysis", "")
        result = await research.run(
            f"Find solutions for these Kubernetes issues:\n{analysis}",
            state.get("context"),
        )

        current_report = state.get("diagnostic_report", {})
        current_report["solutions"] = result.output

        return {
            "diagnostic_report": current_report,
            "messages": [
                {"agent": "research", "type": "research", "content": result.output}
            ],
        }

    async def _diagnostic_report_node(self, state: WorkflowState) -> Dict[str, Any]:
        report = state.get("diagnostic_report", {})

        final_report = f"""
# Kubernetes Cluster Diagnostic Report

## Scan Results
{report.get("scan", "No scan data")}

## Root Cause Analysis
{report.get("analysis", "No analysis")}

## Recommended Solutions
{report.get("solutions", "No solutions")}
"""

        return {
            "diagnostic_report": {**report, "final": final_report},
            "messages": [
                {"agent": "system", "type": "report", "content": "Report generated"}
            ],
        }

    async def _finalize_node(self, state: WorkflowState) -> Dict[str, Any]:
        state.get("messages", [])

        if state.get("error"):
            status = "failed"
            final_output = f"Error: {state['error']}"
        else:
            status = "completed"

            parts = []

            if state.get("analysis"):
                parts.append(f"## Analysis\n{state['analysis'].get('output', '')}")

            if state.get("security_report"):
                parts.append(
                    f"## Security Report\n{state['security_report'].get('output', '')}"
                )

            if state.get("cost_estimate"):
                parts.append(
                    f"## Cost Estimate\n{state['cost_estimate'].get('output', '')}"
                )

            if state.get("plan"):
                parts.append(
                    f"## Infrastructure Plan\n{state['plan'].get('output', '')}"
                )

            if state.get("deployment_result"):
                parts.append(
                    f"## Deployment Result\n{state['deployment_result'].get('output', '')}"
                )

            if state.get("diagnostic_report", {}).get("final"):
                parts.append(state["diagnostic_report"]["final"])

            final_output = "\n\n".join(parts) if parts else "Workflow completed"

        return {
            "final_output": final_output,
            "status": status,
        }

    def _should_await_approval(self, state: WorkflowState) -> str:
        if state.get("requires_approval", True):
            return "await_approval"
        return "deploy"

    def _check_approval(self, state: WorkflowState) -> str:
        if state.get("approved", False):
            return "deploy"
        return "end"
