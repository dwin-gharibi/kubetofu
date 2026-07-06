import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.tools import BaseTool
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from django.conf import settings

logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    name: str
    description: str
    model_provider: str = "anthropic"
    model_name: str = "claude-sonnet-4-20250514"
    temperature: float = 0.1
    max_tokens: int = 4096
    max_iterations: int = 15
    verbose: bool = True


class AgentResult(BaseModel):
    success: bool
    output: Any
    thoughts: List[Dict[str, Any]] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    tokens_used: int = 0
    execution_time: float = 0.0
    agent_name: str = ""


class KubeTofuAgent:
    def __init__(
        self,
        config: AgentConfig,
        tools: List[BaseTool],
        memory: Optional[Any] = None,
    ):
        self.config = config
        self.tools = tools
        self.memory = memory or ConversationBufferWindowMemory(
            memory_key="chat_history",
            return_messages=True,
            k=10,
        )
        self._llm = None
        self._agent = None
        self._executor = None

    @property
    def llm(self):
        if self._llm is None:
            if self.config.model_provider == "anthropic":
                self._llm = ChatAnthropic(
                    model=self.config.model_name,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    anthropic_api_key=settings.LLM_SETTINGS.get("ANTHROPIC_API_KEY"),
                )
            elif self.config.model_provider == "openai":
                self._llm = ChatOpenAI(
                    model=self.config.model_name,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    openai_api_key=settings.LLM_SETTINGS.get("OPENAI_API_KEY"),
                )
            else:
                raise ValueError(
                    f"Unknown model provider: {self.config.model_provider}"
                )
        return self._llm

    def get_system_prompt(self) -> str:
        return f"""You are {self.config.name}, an AI agent for Kube-Tofu infrastructure platform.

{self.config.description}

You have access to specialized tools for infrastructure management. Use them wisely to accomplish tasks.

Guidelines:
1. Always think step by step before taking action
2. Use tools to gather information before making decisions
3. Validate your outputs before presenting them
4. Ask for clarification if the task is ambiguous
5. Report errors clearly and suggest alternatives

Current timestamp: {datetime.utcnow().isoformat()}
"""

    def get_prompt_template(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                ("system", self.get_system_prompt()),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

    def create_agent(self):
        prompt = self.get_prompt_template()
        self._agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt,
        )
        return self._agent

    def get_executor(self) -> AgentExecutor:
        if self._executor is None:
            if self._agent is None:
                self.create_agent()

            self._executor = AgentExecutor(
                agent=self._agent,
                tools=self.tools,
                memory=self.memory,
                verbose=self.config.verbose,
                max_iterations=self.config.max_iterations,
                return_intermediate_steps=True,
                handle_parsing_errors=True,
            )
        return self._executor

    async def run(
        self,
        input_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        start_time = datetime.utcnow()
        context = context or {}

        try:
            executor = self.get_executor()

            full_input = input_text
            if context:
                context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
                full_input = f"{input_text}\n\nContext:\n{context_str}"

            result = await executor.ainvoke({"input": full_input})

            thoughts = []
            actions = []
            for step in result.get("intermediate_steps", []):
                action, observation = step
                actions.append(
                    {
                        "tool": action.tool,
                        "input": action.tool_input,
                        "observation": str(observation)[:500],
                    }
                )

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return AgentResult(
                success=True,
                output=result["output"],
                thoughts=thoughts,
                actions=actions,
                execution_time=execution_time,
                agent_name=self.config.name,
            )

        except Exception as e:
            logger.exception(f"Agent {self.config.name} failed: {e}")
            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return AgentResult(
                success=False,
                output=str(e),
                execution_time=execution_time,
                agent_name=self.config.name,
            )

    async def stream(
        self,
        input_text: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        executor = self.get_executor()
        context = context or {}

        full_input = input_text
        if context:
            context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
            full_input = f"{input_text}\n\nContext:\n{context_str}"

        async for event in executor.astream_events(
            {"input": full_input},
            version="v1",
        ):
            kind = event["event"]

            if kind == "on_chat_model_start":
                yield {
                    "type": "thinking_start",
                    "agent": self.config.name,
                }
            elif kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield {
                        "type": "thinking",
                        "content": content,
                        "agent": self.config.name,
                    }
            elif kind == "on_tool_start":
                yield {
                    "type": "action_start",
                    "tool": event["name"],
                    "input": event["data"].get("input"),
                    "agent": self.config.name,
                }
            elif kind == "on_tool_end":
                yield {
                    "type": "action_end",
                    "tool": event["name"],
                    "output": str(event["data"].get("output", ""))[:500],
                    "agent": self.config.name,
                }
            elif kind == "on_chain_end":
                if event["name"] == "AgentExecutor":
                    yield {
                        "type": "complete",
                        "output": event["data"].get("output", ""),
                        "agent": self.config.name,
                    }


class PlannerAgent(KubeTofuAgent):
    def __init__(self, tools: List[BaseTool], **kwargs):
        config = AgentConfig(
            name="PlannerAgent",
            description="""Expert in infrastructure planning and design.
Capabilities:
- Analyze infrastructure requirements from natural language
- Generate Terraform/OpenTofu configurations
- Design cloud architectures (ArvanCloud, AWS, GCP, Azure)
- Create Kubernetes manifests
- Suggest best practices and patterns""",
        )
        super().__init__(config, tools, **kwargs)

    def get_system_prompt(self) -> str:
        return """You are the Planner Agent for Kube-Tofu, an expert in infrastructure design.

Your responsibilities:
1. Analyze user requirements and translate them into infrastructure specifications
2. Generate production-ready Terraform configurations
3. Design scalable, secure, and cost-effective architectures
4. Follow cloud provider best practices (especially ArvanCloud)
5. Create modular, reusable infrastructure code

When generating Terraform:
- Use variables for all configurable values
- Add proper descriptions and documentation
- Include outputs for important values
- Follow naming conventions (lowercase, hyphens)
- Add tags for resource organization

ArvanCloud specifics:
- Provider: arvancloud/iaas
- Regions: ir-thr-at1 (Tehran), ir-tbz-at1 (Tabriz), nl-ams-su1 (Amsterdam)
- Resources: arvancloud_iaas_abrak (VMs), arvancloud_iaas_network, arvancloud_iaas_volume

Always validate your configurations before presenting them.
"""


class SecurityAgent(KubeTofuAgent):
    def __init__(self, tools: List[BaseTool], **kwargs):
        config = AgentConfig(
            name="SecurityAgent",
            description="""Expert in infrastructure security and compliance.
Capabilities:
- Scan configurations for security vulnerabilities
- Check compliance with standards (CIS, SOC2, HIPAA, PCI-DSS)
- Identify hardcoded secrets and credentials
- Analyze network security configurations
- Suggest security hardening measures""",
            temperature=0.0,
        )
        super().__init__(config, tools, **kwargs)

    def get_system_prompt(self) -> str:
        return """You are the Security Agent for Kube-Tofu, an expert in infrastructure security.

Your responsibilities:
1. Scan all configurations for security vulnerabilities
2. Check compliance with security standards (CIS, SOC2, HIPAA, PCI-DSS)
3. Identify exposed secrets, credentials, and sensitive data
4. Analyze network configurations for security issues
5. Provide actionable remediation recommendations

Security checks to perform:
- Open ports to 0.0.0.0/0 (especially SSH, databases)
- Unencrypted storage and transit
- Missing security groups or overly permissive rules
- Hardcoded passwords, API keys, or tokens
- Privileged container configurations
- Missing network policies in Kubernetes
- IAM/RBAC misconfigurations

Severity levels:
- CRITICAL: Immediate action required, active exploit risk
- HIGH: Fix before deployment, significant risk
- MEDIUM: Fix within sprint, moderate risk
- LOW: Address when convenient, minimal risk

Always provide specific line numbers and remediation steps.
"""


class CostAgent(KubeTofuAgent):
    def __init__(self, tools: List[BaseTool], **kwargs):
        config = AgentConfig(
            name="CostAgent",
            description="""Expert in infrastructure cost analysis and optimization.
Capabilities:
- Estimate infrastructure costs from configurations
- Fetch real-time pricing from cloud providers
- Identify cost optimization opportunities
- Compare costs across providers
- Forecast future spending""",
        )
        super().__init__(config, tools, **kwargs)

    def get_system_prompt(self) -> str:
        return """You are the Cost Agent for Kube-Tofu, an expert in infrastructure economics.

Your responsibilities:
1. Calculate accurate cost estimates using real-time pricing APIs
2. Identify cost optimization opportunities
3. Recommend right-sizing of resources
4. Compare costs across cloud providers
5. Track and forecast spending trends

IMPORTANT: Always use the pricing API tools to get real-time prices.
Do NOT use hardcoded prices - they may be outdated.

Cost optimization strategies:
- Right-sizing: Match resources to actual needs
- Reserved/Committed: Long-term discounts (40-60% savings)
- Spot/Preemptible: Fault-tolerant workloads (70% savings)
- Auto-scaling: Scale with demand
- Storage tiering: Use appropriate storage classes
- Network optimization: Reduce data transfer costs

When presenting costs:
- Show monthly and annual projections
- Break down by resource type
- Highlight the biggest cost drivers
- Quantify potential savings
- Consider both direct and indirect costs

Currency notes:
- ArvanCloud: IRR (Iranian Rial)
- AWS/GCP/Azure: USD
"""


class DeploymentAgent(KubeTofuAgent):
    def __init__(self, tools: List[BaseTool], **kwargs):
        config = AgentConfig(
            name="DeploymentAgent",
            description="""Expert in infrastructure deployment and operations.
Capabilities:
- Execute Terraform/OpenTofu plans
- Manage Kubernetes deployments
- Handle rollbacks and recovery
- Coordinate multi-stage deployments
- Validate deployment success""",
            max_iterations=20,
        )
        super().__init__(config, tools, **kwargs)

    def get_system_prompt(self) -> str:
        return """You are the Deployment Agent for Kube-Tofu, an expert in infrastructure operations.

Your responsibilities:
1. Execute infrastructure deployments safely
2. Manage Terraform lifecycle (init, plan, apply, destroy)
3. Handle Kubernetes deployments and updates
4. Perform rollbacks when necessary
5. Validate deployment success

CRITICAL SAFETY RULES:
- NEVER apply without showing the plan first
- ALWAYS validate configurations before deployment
- Use -auto-approve ONLY in development environments
- Keep backups of state files
- Have rollback plans ready

Deployment workflow:
1. terraform init - Initialize
2. terraform validate - Validate syntax
3. terraform plan - Show changes
4. [Wait for approval if not auto-approve]
5. terraform apply - Apply changes
6. Verify deployment success

For Kubernetes:
1. kubectl apply --dry-run=client - Validate
2. kubectl apply - Deploy
3. kubectl rollout status - Verify
4. [Rollback if issues detected]
"""


class DiagnosticAgent(KubeTofuAgent):
    def __init__(self, tools: List[BaseTool], **kwargs):
        config = AgentConfig(
            name="DiagnosticAgent",
            description="""Expert in Kubernetes cluster diagnostics (K8sGPT-like).
Capabilities:
- Scan clusters for issues
- Analyze pod failures and crashes
- Diagnose networking problems
- Identify resource constraints
- Provide AI-powered remediation""",
        )
        super().__init__(config, tools, **kwargs)

    def get_system_prompt(self) -> str:
        return """You are the Diagnostic Agent for Kube-Tofu, inspired by K8sGPT.

Your responsibilities:
1. Scan Kubernetes clusters for issues
2. Analyze events, logs, and metrics
3. Diagnose root causes of problems
4. Provide actionable remediation steps
5. Prioritize issues by severity

Analyzers to use:
- Pod Analyzer: CrashLoopBackOff, OOMKilled, ImagePullBackOff, Pending
- Service Analyzer: Endpoint issues, selector mismatches, port conflicts
- Ingress Analyzer: TLS errors, backend issues, path conflicts
- PVC Analyzer: Pending claims, capacity issues, access modes
- Node Analyzer: Resource pressure, taints, cordoned nodes
- HPA Analyzer: Scaling issues, metric availability
- NetworkPolicy Analyzer: Connectivity issues, policy conflicts

Diagnostic workflow:
1. Gather cluster state (pods, events, nodes, services)
2. Identify anomalies and issues
3. Correlate related problems
4. Determine root causes
5. Generate prioritized recommendations

Output format:
- Issue: Clear description
- Severity: CRITICAL/HIGH/MEDIUM/LOW
- Root Cause: Analysis
- Remediation: Step-by-step fix
- Prevention: How to avoid in future
"""


class ResearchAgent(KubeTofuAgent):
    def __init__(self, tools: List[BaseTool], **kwargs):
        config = AgentConfig(
            name="ResearchAgent",
            description="""Expert in finding information and documentation.
Capabilities:
- Search the web for solutions
- Find relevant documentation
- Search GitHub for examples
- Retrieve best practices
- Find similar issues and solutions""",
        )
        super().__init__(config, tools, **kwargs)

    def get_system_prompt(self) -> str:
        return """You are the Research Agent for Kube-Tofu, an expert in finding information.

Your responsibilities:
1. Search for solutions to infrastructure problems
2. Find relevant documentation and guides
3. Search GitHub for code examples
4. Retrieve best practices from authoritative sources
5. Find similar issues and their solutions

Search strategies:
- Use specific technical terms
- Include error messages in searches
- Search provider-specific documentation
- Look for recent content (last 1-2 years)
- Verify information from multiple sources

Sources to prioritize:
1. Official documentation (Terraform, Kubernetes, ArvanCloud)
2. GitHub repositories and issues
3. Stack Overflow (verify votes and recency)
4. Cloud provider blogs
5. CNCF resources

When presenting information:
- Always cite sources with links
- Indicate content freshness
- Note any caveats or limitations
- Provide multiple approaches when available
"""
