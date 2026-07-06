import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.conf import settings

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage

from agents.langchain.memory import AgentMemoryManager
from agents.langchain.callbacks import (
    create_callbacks,
    MetricsCallback,
    CallbackMetrics,
)
from agents.langchain.shell_tools import create_shell_tools
from agents.langchain.human_in_loop import create_human_tools
from agents.langchain.tools import create_tools_for_agent

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    success: bool
    output: Any
    thoughts: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    metrics: Optional[CallbackMetrics]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "thoughts": self.thoughts,
            "actions": self.actions,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "error": self.error,
        }


class DeepAgent:
    def __init__(
        self,
        name: str,
        description: str,
        session_id: str,
        agent_type: str = "general",
        model_provider: str = "anthropic",
        model_name: str = "claude-sonnet-4-20250514",
        temperature: float = 0.1,
        max_iterations: int = 25,
        enable_shell: bool = True,
        enable_human_in_loop: bool = True,
        enable_memory: bool = True,
        custom_tools: Optional[List[BaseTool]] = None,
    ):
        self.name = name
        self.description = description
        self.session_id = session_id
        self.agent_type = agent_type
        self.model_provider = model_provider
        self.model_name = model_name
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.enable_shell = enable_shell
        self.enable_human_in_loop = enable_human_in_loop
        self.enable_memory = enable_memory
        self.custom_tools = custom_tools or []
        self._llm = None
        self._tools: List[BaseTool] = []
        self._agent = None
        self._executor = None
        self._memory_manager = None

        self._setup_tools()
        if enable_memory:
            self._setup_memory()

    @property
    def llm(self):
        if self._llm is None:
            if self.model_provider == "anthropic":
                self._llm = ChatAnthropic(
                    model=self.model_name,
                    temperature=self.temperature,
                    max_tokens=8192,
                    anthropic_api_key=settings.LLM_SETTINGS.get("ANTHROPIC_API_KEY"),
                )
            elif self.model_provider == "openai":
                self._llm = ChatOpenAI(
                    model=self.model_name,
                    temperature=self.temperature,
                    max_tokens=8192,
                    openai_api_key=settings.LLM_SETTINGS.get("OPENAI_API_KEY"),
                )
            else:
                raise ValueError(f"Unknown model provider: {self.model_provider}")
        return self._llm

    def _setup_tools(self) -> None:
        self._tools.extend(create_tools_for_agent(self.agent_type))

        if self.enable_shell:
            self._tools.extend(create_shell_tools(allow_dangerous=False))

        if self.enable_human_in_loop:
            self._tools.extend(create_human_tools(self.session_id))

        self._tools.extend(self.custom_tools)
        logger.info(f"Agent {self.name} initialized with {len(self._tools)} tools")

    def _setup_memory(self) -> None:
        self._memory_manager = AgentMemoryManager(
            agent_id=self.name,
            session_id=self.session_id,
            llm=self.llm,
        )

    def get_system_prompt(self) -> str:
        return f"""You are {self.name}, a deep AI agent in the Kube-Tofu infrastructure platform.

## Your Role
{self.description}

## Capabilities
You have access to powerful tools for infrastructure management:
- **Terraform/OpenTofu**: Generate, validate, plan, and apply infrastructure configurations
- **Kubernetes**: Manage clusters, deployments, services, and diagnose issues
- **Shell Commands**: Execute infrastructure commands safely
- **File Operations**: Read and write configuration files
- **Search**: Find documentation, code examples, and solutions
- **Human Interaction**: Request approval for sensitive operations, ask for clarification

## Guidelines

### Tool Usage
1. Always use the appropriate tool for the task
2. Validate configurations before applying
3. Request human approval for destructive operations
4. Check costs before expensive deployments

### Safety
1. Never execute dangerous commands without approval
2. Always validate user input
3. Prefer read-only operations when exploring
4. Back up state before modifications

### Communication
1. Be clear and concise in your responses
2. Show your reasoning step by step
3. Provide code examples when helpful
4. Ask for clarification when needed

### Memory
1. Remember context from the conversation
2. Track entities (resources, users, projects)
3. Learn from past interactions
4. Apply successful patterns

## Current Context
- Session ID: {self.session_id}
- Timestamp: {datetime.utcnow().isoformat()}
- Model: {self.model_name}

## Important
- You are autonomous but can ask for human input
- Always explain your actions before executing
- If unsure, ask rather than guess
- Quality over speed
"""

    def get_prompt_template(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                ("system", self.get_system_prompt()),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                MessagesPlaceholder(
                    variable_name="agent_scratchpad_history", optional=True
                ),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

    def create_agent(self):
        prompt = self.get_prompt_template()
        self._agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self._tools,
            prompt=prompt,
        )
        return self._agent

    def get_executor(self, callbacks=None) -> AgentExecutor:
        if self._agent is None:
            self.create_agent()

        memory = None
        if self._memory_manager:
            memory = self._memory_manager.working.to_langchain_memory()

        return AgentExecutor(
            agent=self._agent,
            tools=self._tools,
            memory=memory,
            verbose=True,
            max_iterations=self.max_iterations,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
            callbacks=callbacks,
        )

    async def run(
        self,
        input_text: str,
        context: Optional[Dict[str, Any]] = None,
        enable_streaming: bool = True,
    ) -> AgentResponse:
        datetime.utcnow()

        try:
            callbacks = create_callbacks(
                session_id=self.session_id,
                agent_name=self.name,
                enable_streaming=enable_streaming,
            )

            metrics_callback = next(
                (c for c in callbacks if isinstance(c, MetricsCallback)), None
            )

            executor = self.get_executor(callbacks=callbacks)

            full_input = input_text
            if context:
                context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])
                full_input = f"{input_text}\n\nContext:\n{context_str}"

            if self._memory_manager:
                memory_context = await self._memory_manager.get_relevant_context(
                    input_text
                )
                if memory_context:
                    full_input = f"{full_input}\n\nRelevant History:\n{memory_context}"

            result = await executor.ainvoke({"input": full_input})

            thoughts = []
            actions = []

            for step in result.get("intermediate_steps", []):
                action, observation = step

                if action.log:
                    thoughts.append(
                        {
                            "content": action.log,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

                actions.append(
                    {
                        "tool": action.tool,
                        "input": str(action.tool_input)[:500],
                        "observation": str(observation)[:1000],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

            if self._memory_manager:
                await self._memory_manager.add_interaction(
                    human_input=input_text,
                    ai_output=result["output"],
                    action_taken=actions[-1]["tool"] if actions else None,
                    outcome="success",
                )

            metrics = None
            if metrics_callback:
                metrics = metrics_callback.finalize()

            return AgentResponse(
                success=True,
                output=result["output"],
                thoughts=thoughts,
                actions=actions,
                metrics=metrics,
            )

        except Exception as e:
            logger.exception(f"Agent {self.name} failed: {e}")

            return AgentResponse(
                success=False,
                output=None,
                thoughts=[],
                actions=[],
                metrics=None,
                error=str(e),
            )

    async def stream(
        self,
        input_text: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        callbacks = create_callbacks(
            session_id=self.session_id,
            agent_name=self.name,
            enable_streaming=True,
        )

        executor = self.get_executor(callbacks=callbacks)

        full_input = input_text
        if context:
            context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])
            full_input = f"{input_text}\n\nContext:\n{context_str}"

        async for event in executor.astream_events(
            {"input": full_input},
            version="v1",
        ):
            yield event

    async def reflect(
        self,
        task: str,
        actions: List[Dict],
        outcome: str,
    ) -> str:
        reflection_prompt = f"""Reflect on your performance for this task:

Task: {task}

Actions Taken:
{chr(10).join([f"- {a['tool']}: {a['observation'][:200]}" for a in actions])}

Outcome: {outcome}

Consider:
1. Was the approach efficient?
2. Could any steps be improved?
3. What would you do differently next time?
4. Were there any errors or near-misses?

Provide a brief reflection:"""

        response = await self.llm.ainvoke([HumanMessage(content=reflection_prompt)])

        return response.content


class InfrastructurePlannerAgent(DeepAgent):
    def __init__(self, session_id: str, **kwargs):
        super().__init__(
            name="InfrastructurePlanner",
            description="""Expert infrastructure architect specializing in:
- Cloud architecture design (ArvanCloud, AWS, GCP, Azure)
- Terraform/OpenTofu configuration generation
- Kubernetes manifest creation
- Cost-optimized resource planning
- High availability and disaster recovery""",
            session_id=session_id,
            agent_type="planner",
            **kwargs,
        )


class SecurityAuditorAgent(DeepAgent):
    def __init__(self, session_id: str, **kwargs):
        super().__init__(
            name="SecurityAuditor",
            description="""Security expert specializing in:
- Infrastructure vulnerability scanning
- Compliance checking (CIS, SOC2, HIPAA, PCI-DSS)
- Secret management and detection
- Network security analysis
- Security hardening recommendations""",
            session_id=session_id,
            agent_type="security",
            temperature=0.0,
            **kwargs,
        )


class CostOptimizerAgent(DeepAgent):
    def __init__(self, session_id: str, **kwargs):
        super().__init__(
            name="CostOptimizer",
            description="""Cloud cost expert specializing in:
- Real-time cost estimation using provider APIs
- Resource right-sizing recommendations
- Reserved instance planning
- Cost anomaly detection
- Multi-cloud cost comparison""",
            session_id=session_id,
            agent_type="cost",
            **kwargs,
        )


class DeploymentEngineerAgent(DeepAgent):
    def __init__(self, session_id: str, **kwargs):
        super().__init__(
            name="DeploymentEngineer",
            description="""Deployment expert specializing in:
- Terraform lifecycle management (init, plan, apply, destroy)
- Kubernetes deployments and rollouts
- Zero-downtime deployments
- Rollback procedures
- State management""",
            session_id=session_id,
            agent_type="deployment",
            enable_human_in_loop=True,
            max_iterations=30,
            **kwargs,
        )


class ClusterDiagnosticianAgent(DeepAgent):
    def __init__(self, session_id: str, **kwargs):
        super().__init__(
            name="ClusterDiagnostician",
            description="""Kubernetes diagnostic expert specializing in:
- Cluster health analysis (K8sGPT-inspired)
- Pod failure diagnosis (CrashLoopBackOff, OOMKilled)
- Service connectivity issues
- Resource constraint analysis
- Root cause determination and remediation""",
            session_id=session_id,
            agent_type="diagnostic",
            **kwargs,
        )


class ResearchAssistantAgent(DeepAgent):
    def __init__(self, session_id: str, **kwargs):
        super().__init__(
            name="ResearchAssistant",
            description="""Research expert specializing in:
- Documentation search and retrieval
- GitHub code and module discovery
- Best practices research
- Solution finding for infrastructure problems
- Knowledge synthesis""",
            session_id=session_id,
            agent_type="research",
            enable_shell=False,
            **kwargs,
        )


class ProjectAnalyzerAgent(DeepAgent):
    def __init__(self, session_id: str, **kwargs):
        super().__init__(
            name="ProjectAnalyzer",
            description="""پروژه تحلیل‌گر متخصص در:
- تحلیل ساختار پروژه‌های نرم‌افزاری
- تشخیص زبان برنامه‌نویسی و فریم‌ورک
- شناسایی وابستگی‌ها و دیتابیس‌ها
- تولید Dockerfile بهینه برای هر زبان
- ایجاد مانیفست‌های Kubernetes با بهترین روش‌ها
- پیکربندی Terraform برای زیرساخت‌های ابری
- بررسی امنیتی و پیشنهادات بهبود
- تخمین هزینه استقرار

Project Analyzer specializing in:
- Software project structure analysis
- Programming language and framework detection
- Dependency and database identification
- Optimized Dockerfile generation for any language
- Kubernetes manifests with best practices
- Terraform configuration for cloud infrastructure
- Security review and improvement suggestions
- Deployment cost estimation""",
            session_id=session_id,
            agent_type="project_analyzer",
            temperature=0.2,
            max_iterations=20,
            **kwargs,
        )

    def get_system_prompt(self) -> str:
        base_prompt = super().get_system_prompt()

        project_additions = """

## تخصص: تحلیل پروژه و تولید IaC (Project Analysis Specialization)

شما یک متخصص تحلیل پروژه هستید که می‌تواند:

### ۱. تحلیل پروژه
- شناسایی زبان برنامه‌نویسی از روی فایل‌های پروژه
- تشخیص فریم‌ورک (Django, Flask, FastAPI, React, Next.js, etc.)
- استخراج وابستگی‌ها از requirements.txt, package.json, go.mod
- شناسایی دیتابیس‌ها (PostgreSQL, MySQL, MongoDB, Redis)
- تعیین نوع سرویس (web, api, worker, static)

### ۲. تولید Dockerfile
برای هر زبان، Dockerfile بهینه با:
- Multi-stage builds برای کاهش حجم
- کاربر غیر-root برای امنیت
- Health check مناسب
- بهترین ایمیج پایه

### ۳. تولید Kubernetes Manifests
- Deployment با تنظیمات منابع مناسب
- Service با نوع صحیح
- Ingress با TLS
- HPA برای auto-scaling
- ConfigMap و Secret برای تنظیمات

### ۴. تولید Terraform
- VPC و شبکه
- منابع محاسباتی (EC2, AKS)
- دیتابیس‌های مدیریت شده
- Load balancer و CDN

### دستورالعمل پاسخ‌دهی
1. **همیشه کد کامل و قابل استفاده تولید کنید**
2. **توضیحات فارسی برای هر بخش ارائه دهید**
3. **بهترین روش‌های امنیتی را رعایت کنید**
4. **پیشنهادات بهبود ارائه دهید**
"""
        return base_prompt + project_additions


def create_deep_agent(
    agent_type: str,
    session_id: str,
    **kwargs,
) -> DeepAgent:
    agents = {
        "planner": InfrastructurePlannerAgent,
        "security": SecurityAuditorAgent,
        "cost": CostOptimizerAgent,
        "deployment": DeploymentEngineerAgent,
        "diagnostic": ClusterDiagnosticianAgent,
        "research": ResearchAssistantAgent,
        "project_analyzer": ProjectAnalyzerAgent,
    }

    agent_class = agents.get(agent_type, DeepAgent)
    return agent_class(session_id=session_id, **kwargs)
