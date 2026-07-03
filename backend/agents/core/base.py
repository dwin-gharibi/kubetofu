import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    OBSERVATION = "observation"


@dataclass
class Message:
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentThought:
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    reflection: Optional[str] = None
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AgentConfig(BaseModel):
    name: str = Field(description="Agent name")
    description: str = Field(default="", description="Agent description")
    llm_provider: str = Field(default="anthropic", description="LLM provider")
    llm_model: str = Field(default="claude-sonnet-4-20250514", description="LLM model")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    max_iterations: int = Field(default=10, ge=1, le=50)
    timeout_seconds: int = Field(default=300, ge=1)
    enable_reflection: bool = Field(default=True)
    enable_memory: bool = Field(default=True)
    tools: List[str] = Field(default_factory=list)

    class Config:
        extra = "allow"


class AgentMemory:
    def __init__(self, max_short_term: int = 50):
        self.max_short_term = max_short_term
        self.short_term: List[Message] = []
        self.thoughts: List[AgentThought] = []
        self._long_term_store = None

    def add_message(self, message: Message) -> None:
        self.short_term.append(message)
        if len(self.short_term) > self.max_short_term:
            self._summarize_and_archive()

    def add_thought(self, thought: AgentThought) -> None:
        self.thoughts.append(thought)

    def get_context(self, limit: int = 20) -> List[Message]:
        return self.short_term[-limit:]

    def get_thoughts(self, limit: int = 10) -> List[AgentThought]:
        return self.thoughts[-limit:]

    def _summarize_and_archive(self) -> None:
        self.short_term[: -self.max_short_term // 2]
        self.short_term = self.short_term[-self.max_short_term // 2 :]

    def clear(self) -> None:
        self.short_term.clear()
        self.thoughts.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "short_term": [
                {
                    "role": m.role.value,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "metadata": m.metadata,
                }
                for m in self.short_term
            ],
            "thoughts": [
                {
                    "thought": t.thought,
                    "action": t.action,
                    "observation": t.observation,
                    "confidence": t.confidence,
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in self.thoughts
            ],
        }


class Tool(ABC):
    name: str
    description: str

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        pass


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "schema": tool.get_schema(),
            }
            for tool in self._tools.values()
        ]

    def get_tools_prompt(self) -> str:
        tools_desc = []
        for tool in self._tools.values():
            schema = tool.get_schema()
            params = schema.get("properties", {})
            params_desc = ", ".join(
                f"{k}: {v.get('type', 'any')}" for k, v in params.items()
            )
            tools_desc.append(f"- {tool.name}({params_desc}): {tool.description}")
        return "\n".join(tools_desc)


class BaseAgent(ABC):
    def __init__(
        self,
        config: AgentConfig,
        llm_provider: Optional[Any] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.config = config
        self.id = str(uuid.uuid4())
        self.state = AgentState.IDLE
        self.memory = AgentMemory()
        self.tool_registry = tool_registry or ToolRegistry()
        self._llm = llm_provider
        self._iteration = 0
        self._start_time: Optional[datetime] = None

        self._register_default_tools()

    @property
    def name(self) -> str:
        return self.config.name

    @abstractmethod
    def get_system_prompt(self) -> str:
        pass

    @abstractmethod
    async def process_task(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        pass

    def _register_default_tools(self) -> None:
        pass

    async def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.state = AgentState.THINKING
        self._start_time = datetime.utcnow()
        self._iteration = 0
        context = context or {}

        self.memory.add_message(
            Message(
                role=MessageRole.USER,
                content=task,
                metadata={"context": context},
            )
        )

        try:
            result = await self._run_loop(task, context)
            self.state = AgentState.COMPLETED
            return {
                "success": True,
                "result": result,
                "thoughts": self.memory.to_dict()["thoughts"],
                "iterations": self._iteration,
                "execution_time": (
                    datetime.utcnow() - self._start_time
                ).total_seconds(),
            }
        except Exception as e:
            logger.exception(f"Agent {self.name} failed: {e}")
            self.state = AgentState.FAILED
            return {
                "success": False,
                "error": str(e),
                "thoughts": self.memory.to_dict()["thoughts"],
                "iterations": self._iteration,
                "execution_time": (
                    datetime.utcnow() - self._start_time
                ).total_seconds(),
            }

    async def _run_loop(
        self,
        task: str,
        context: Dict[str, Any],
    ) -> Any:
        while self._iteration < self.config.max_iterations:
            self._iteration += 1

            elapsed = (datetime.utcnow() - self._start_time).total_seconds()
            if elapsed > self.config.timeout_seconds:
                raise TimeoutError(
                    f"Agent exceeded timeout of {self.config.timeout_seconds}s"
                )

            self.state = AgentState.THINKING
            thought = await self._think(task, context)
            self.memory.add_thought(thought)

            if thought.action == "finish":
                return thought.action_input.get("answer", thought.observation)

            if thought.action and thought.action_input:
                self.state = AgentState.ACTING
                tool_result = await self._act(thought.action, thought.action_input)

                self.state = AgentState.OBSERVING
                thought.observation = self._format_observation(tool_result)

                self.memory.add_message(
                    Message(
                        role=MessageRole.OBSERVATION,
                        content=thought.observation,
                        tool_name=thought.action,
                    )
                )

            if self.config.enable_reflection and self._iteration % 3 == 0:
                self.state = AgentState.REFLECTING
                reflection = await self._reflect(task, context)
                thought.reflection = reflection

        raise RuntimeError(
            f"Agent exceeded max iterations ({self.config.max_iterations})"
        )

    async def _think(
        self,
        task: str,
        context: Dict[str, Any],
    ) -> AgentThought:
        prompt = self._build_think_prompt(task, context)
        response = await self._call_llm(prompt)

        return self._parse_thought_response(response)

    async def _act(
        self,
        action: str,
        action_input: Dict[str, Any],
    ) -> ToolResult:
        tool = self.tool_registry.get(action)
        if not tool:
            return ToolResult(
                tool_name=action,
                success=False,
                output=None,
                error=f"Unknown tool: {action}",
            )

        try:
            import time

            start = time.time()
            result = await tool.execute(**action_input)
            result.execution_time = time.time() - start
            return result
        except Exception as e:
            logger.exception(f"Tool {action} failed: {e}")
            return ToolResult(
                tool_name=action,
                success=False,
                output=None,
                error=str(e),
            )

    async def _reflect(
        self,
        task: str,
        context: Dict[str, Any],
    ) -> str:
        prompt = self._build_reflect_prompt(task, context)
        return await self._call_llm(prompt)

    def _build_think_prompt(self, task: str, context: Dict[str, Any]) -> str:
        system = self.get_system_prompt()
        tools_prompt = self.tool_registry.get_tools_prompt()

        history = self._format_history()

        return f"""{system}

## Available Tools
{tools_prompt}

## Current Context
{self._format_context(context)}

## Conversation History
{history}

## Current Task
{task}

## Instructions
Think step by step about what action to take next.
Format your response as:

THOUGHT: [Your reasoning about what to do next]
ACTION: [The tool name to use, or "finish" if you have the final answer]
ACTION_INPUT: [JSON object with the tool parameters, or {{"answer": "your final answer"}} if finishing]

Remember to always include all three parts in your response.
"""

    def _build_reflect_prompt(self, task: str, context: Dict[str, Any]) -> str:
        thoughts = self.memory.get_thoughts()
        thoughts_summary = "\n".join(
            f"- Thought {i + 1}: {t.thought[:100]}..." for i, t in enumerate(thoughts)
        )

        return f"""Reflect on your progress so far on this task:

Task: {task}

Your thoughts so far:
{thoughts_summary}

Questions to consider:
1. Are you making progress toward the goal?
2. Have you encountered any errors or issues?
3. Should you adjust your approach?
4. What's the most important next step?

Provide a brief reflection (2-3 sentences):
"""

    def _format_history(self) -> str:
        messages = self.memory.get_context()
        formatted = []
        for msg in messages:
            role = msg.role.value.upper()
            formatted.append(f"[{role}]: {msg.content}")
        return "\n".join(formatted) if formatted else "(No history yet)"

    def _format_context(self, context: Dict[str, Any]) -> str:
        if not context:
            return "(No additional context)"
        import json

        return json.dumps(context, indent=2, default=str)

    def _format_observation(self, result: ToolResult) -> str:
        if result.success:
            return f"Tool '{result.tool_name}' succeeded:\n{result.output}"
        else:
            return f"Tool '{result.tool_name}' failed:\n{result.error}"

    def _parse_thought_response(self, response: str) -> AgentThought:
        import json
        import re

        thought = ""
        action = None
        action_input = None

        thought_match = re.search(r"THOUGHT:\s*(.+?)(?=ACTION:|$)", response, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        action_match = re.search(r"ACTION:\s*(\w+)", response)
        if action_match:
            action = action_match.group(1).strip()

        input_match = re.search(r"ACTION_INPUT:\s*(\{.+?\})", response, re.DOTALL)
        if input_match:
            try:
                action_input = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                json_match = re.search(r"\{[^{}]+\}", response)
                if json_match:
                    try:
                        action_input = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        action_input = {"raw": input_match.group(1)}

        return AgentThought(
            thought=thought or response,
            action=action,
            action_input=action_input,
            confidence=0.8 if action else 0.5,
        )

    async def _call_llm(self, prompt: str) -> str:
        if self._llm is None:
            from agents.core.llm import LLMProvider

            self._llm = LLMProvider(
                provider=self.config.llm_provider,
                model=self.config.llm_model,
            )

        return await self._llm.generate(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

    def get_state(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state.value,
            "iteration": self._iteration,
            "memory": self.memory.to_dict(),
        }
