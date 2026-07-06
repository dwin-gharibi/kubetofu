import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from channels.layers import get_channel_layer
from langchain_core.callbacks import (
    AsyncCallbackHandler,
    BaseCallbackHandler,
)
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: "TokenUsage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens


@dataclass
class CallbackMetrics:
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None

    llm_calls: int = 0
    tool_calls: int = 0
    token_usage: TokenUsage = field(default_factory=TokenUsage)

    errors: List[Dict[str, Any]] = field(default_factory=list)
    tool_durations: Dict[str, float] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.utcnow() - self.start_time).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duration_seconds": self.duration_seconds,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "token_usage": {
                "prompt": self.token_usage.prompt_tokens,
                "completion": self.token_usage.completion_tokens,
                "total": self.token_usage.total_tokens,
            },
            "errors": self.errors,
            "tool_durations": self.tool_durations,
        }


class WebSocketStreamingCallback(AsyncCallbackHandler):
    def __init__(
        self,
        session_id: str,
        agent_name: str = "agent",
    ):
        self.session_id = session_id
        self.agent_name = agent_name
        self._channel_layer = None
        self._current_thought = ""

    @property
    def channel_layer(self):
        if self._channel_layer is None:
            self._channel_layer = get_channel_layer()
        return self._channel_layer

    async def _send(self, event_type: str, data: Dict[str, Any]) -> None:
        if self.channel_layer:
            try:
                await self.channel_layer.group_send(
                    f"agent_{self.session_id}",
                    {
                        "type": "agent_event",
                        "event_type": event_type,
                        "agent": self.agent_name,
                        "data": data,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to send WebSocket event: {e}")

    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs,
    ) -> None:
        await self._send(
            "llm_start",
            {
                "model": serialized.get("name", "unknown"),
            },
        )

    async def on_llm_new_token(
        self,
        token: str,
        **kwargs,
    ) -> None:
        self._current_thought += token

        await self._send(
            "token",
            {
                "token": token,
                "accumulated": self._current_thought[-500:],
            },
        )

    async def on_llm_end(
        self,
        response: LLMResult,
        **kwargs,
    ) -> None:
        self._current_thought = ""

        await self._send(
            "llm_end",
            {
                "output": response.generations[0][0].text
                if response.generations
                else "",
            },
        )

    async def on_llm_error(
        self,
        error: BaseException,
        **kwargs,
    ) -> None:
        await self._send(
            "error",
            {
                "type": "llm_error",
                "message": str(error),
            },
        )

    async def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        **kwargs,
    ) -> None:
        await self._send(
            "chain_start",
            {
                "chain": serialized.get("name", "unknown"),
            },
        )

    async def on_chain_end(
        self,
        outputs: Dict[str, Any],
        **kwargs,
    ) -> None:
        await self._send(
            "chain_end",
            {
                "has_output": bool(outputs),
            },
        )

    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs,
    ) -> None:
        await self._send(
            "tool_start",
            {
                "tool": serialized.get("name", "unknown"),
                "input": input_str[:500] if input_str else "",
            },
        )

    async def on_tool_end(
        self,
        output: str,
        **kwargs,
    ) -> None:
        await self._send(
            "tool_end",
            {
                "output": output[:1000] if output else "",
            },
        )

    async def on_tool_error(
        self,
        error: BaseException,
        **kwargs,
    ) -> None:
        await self._send(
            "error",
            {
                "type": "tool_error",
                "message": str(error),
            },
        )

    async def on_agent_action(
        self,
        action: AgentAction,
        **kwargs,
    ) -> None:
        await self._send(
            "agent_action",
            {
                "tool": action.tool,
                "input": str(action.tool_input)[:500],
                "log": action.log[:500] if action.log else "",
            },
        )

    async def on_agent_finish(
        self,
        finish: AgentFinish,
        **kwargs,
    ) -> None:
        await self._send(
            "agent_finish",
            {
                "output": str(finish.return_values.get("output", ""))[:1000],
            },
        )


class MetricsCallback(BaseCallbackHandler):
    def __init__(self):
        self.metrics = CallbackMetrics()
        self._tool_start_times: Dict[str, float] = {}

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs,
    ) -> None:
        self.metrics.llm_calls += 1

    def on_llm_end(
        self,
        response: LLMResult,
        **kwargs,
    ) -> None:
        if response.llm_output:
            usage = response.llm_output.get("token_usage", {})
            if usage:
                self.metrics.token_usage.prompt_tokens += usage.get("prompt_tokens", 0)
                self.metrics.token_usage.completion_tokens += usage.get(
                    "completion_tokens", 0
                )
                self.metrics.token_usage.total_tokens += usage.get("total_tokens", 0)

    def on_llm_error(
        self,
        error: BaseException,
        **kwargs,
    ) -> None:
        self.metrics.errors.append(
            {
                "type": "llm_error",
                "message": str(error),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs,
    ) -> None:
        self.metrics.tool_calls += 1
        tool_name = serialized.get("name", "unknown")
        self._tool_start_times[tool_name] = time.time()

    def on_tool_end(
        self,
        output: str,
        **kwargs,
    ) -> None:
        for tool_name, start_time in list(self._tool_start_times.items()):
            duration = time.time() - start_time

            if tool_name in self.metrics.tool_durations:
                self.metrics.tool_durations[tool_name] += duration
            else:
                self.metrics.tool_durations[tool_name] = duration

            del self._tool_start_times[tool_name]
            break

    def on_tool_error(
        self,
        error: BaseException,
        **kwargs,
    ) -> None:
        self.metrics.errors.append(
            {
                "type": "tool_error",
                "message": str(error),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def finalize(self) -> CallbackMetrics:
        self.metrics.end_time = datetime.utcnow()
        return self.metrics


class LoggingCallback(BaseCallbackHandler):
    def __init__(self, log_level: int = logging.INFO):
        self.log_level = log_level
        self.logger = logging.getLogger("kubetofu.agent")

    def _log(self, message: str) -> None:
        self.logger.log(self.log_level, message)

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs,
    ) -> None:
        model = serialized.get("name", "unknown")
        self._log(f"LLM Start: {model}")

    def on_llm_end(
        self,
        response: LLMResult,
        **kwargs,
    ) -> None:
        output = response.generations[0][0].text[:100] if response.generations else ""
        self._log(f"LLM End: {output}...")

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs,
    ) -> None:
        tool = serialized.get("name", "unknown")
        self._log(f"Tool Start: {tool} - {input_str[:100]}...")

    def on_tool_end(
        self,
        output: str,
        **kwargs,
    ) -> None:
        self._log(f"Tool End: {output[:100]}...")

    def on_agent_action(
        self,
        action: AgentAction,
        **kwargs,
    ) -> None:
        self._log(f"Agent Action: {action.tool}")

    def on_agent_finish(
        self,
        finish: AgentFinish,
        **kwargs,
    ) -> None:
        output = finish.return_values.get("output", "")[:100]
        self._log(f"Agent Finish: {output}...")


class CostTrackingCallback(BaseCallbackHandler):
    PRICING = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    }

    def __init__(self):
        self.total_cost = 0.0
        self.model_costs: Dict[str, float] = {}

    def on_llm_end(
        self,
        response: LLMResult,
        **kwargs,
    ) -> None:
        if not response.llm_output:
            return

        usage = response.llm_output.get("token_usage", {})
        model = response.llm_output.get("model_name", "")

        if not usage or not model:
            return

        pricing = None
        for model_prefix, prices in self.PRICING.items():
            if model_prefix in model.lower():
                pricing = prices
                break

        if not pricing:
            return

        input_cost = (usage.get("prompt_tokens", 0) / 1000) * pricing["input"]
        output_cost = (usage.get("completion_tokens", 0) / 1000) * pricing["output"]
        total = input_cost + output_cost

        self.total_cost += total

        if model not in self.model_costs:
            self.model_costs[model] = 0.0
        self.model_costs[model] += total

    def get_cost_summary(self) -> Dict[str, Any]:
        return {
            "total_cost_usd": round(self.total_cost, 4),
            "by_model": {k: round(v, 4) for k, v in self.model_costs.items()},
        }


def create_callbacks(
    session_id: str,
    agent_name: str = "agent",
    enable_streaming: bool = True,
    enable_metrics: bool = True,
    enable_logging: bool = True,
    enable_cost_tracking: bool = True,
) -> List[BaseCallbackHandler]:
    callbacks = []

    if enable_streaming:
        callbacks.append(WebSocketStreamingCallback(session_id, agent_name))

    if enable_metrics:
        callbacks.append(MetricsCallback())

    if enable_logging:
        callbacks.append(LoggingCallback())

    if enable_cost_tracking:
        callbacks.append(CostTrackingCallback())

    return callbacks
