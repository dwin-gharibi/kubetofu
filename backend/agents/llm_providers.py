import os
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Generator
from enum import Enum


class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    MOCK = "mock"


@dataclass
class LLMConfig:
    provider: LLMProvider
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    retry_count: int = 3
    retry_delay: float = 1.0


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    tokens_used: int
    latency_ms: float
    finish_reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0


class BaseLLMProvider(ABC):
    def __init__(self, config: LLMConfig):
        self.config = config
        self.usage = LLMUsage()

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        pass

    @abstractmethod
    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        pass

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        prompt = self._messages_to_prompt(messages)
        return self.generate(prompt, **kwargs)

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            else:
                parts.append(f"User: {content}")
        return "\n\n".join(parts)

    def get_usage(self) -> LLMUsage:
        return self.usage

    def reset_usage(self):
        self.usage = LLMUsage()


class OpenAIProvider(BaseLLMProvider):
    PRICING = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    }

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.environ.get("OPENAI_API_KEY")
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            import openai

            self.client = openai.OpenAI(
                api_key=self.api_key,
                base_url=self.config.api_base,
                timeout=self.config.timeout,
            )
        except ImportError:
            self.client = None

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        if not self.client:
            raise RuntimeError(
                "OpenAI client not initialized. Install: pip install openai"
            )

        start_time = time.time()

        messages = [{"role": "user", "content": prompt}]

        if "system" in kwargs:
            messages.insert(0, {"role": "system", "content": kwargs["system"]})

        for attempt in range(self.config.retry_count):
            try:
                response = self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=kwargs.get("temperature", self.config.temperature),
                    max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                )

                latency = (time.time() - start_time) * 1000

                usage = response.usage
                self.usage.prompt_tokens += usage.prompt_tokens
                self.usage.completion_tokens += usage.completion_tokens
                self.usage.total_tokens += usage.total_tokens
                self._update_cost()

                return LLMResponse(
                    content=response.choices[0].message.content,
                    model=self.config.model,
                    provider="openai",
                    tokens_used=usage.total_tokens,
                    latency_ms=latency,
                    finish_reason=response.choices[0].finish_reason,
                    metadata={
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                    },
                )

            except Exception as e:
                if attempt < self.config.retry_count - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise RuntimeError(f"OpenAI API error: {e}")

    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        if not self.client:
            raise RuntimeError("OpenAI client not initialized")

        messages = [{"role": "user", "content": prompt}]

        stream = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _update_cost(self):
        pricing = self.PRICING.get(self.config.model, {"input": 0.01, "output": 0.03})
        self.usage.estimated_cost = (self.usage.prompt_tokens / 1000) * pricing[
            "input"
        ] + (self.usage.completion_tokens / 1000) * pricing["output"]


class AnthropicProvider(BaseLLMProvider):
    PRICING = {
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    }

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            import anthropic

            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            self.client = None

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        if not self.client:
            raise RuntimeError(
                "Anthropic client not initialized. Install: pip install anthropic"
            )

        start_time = time.time()

        system = kwargs.get(
            "system", "You are an expert Infrastructure-as-Code engineer."
        )

        for attempt in range(self.config.retry_count):
            try:
                response = self.client.messages.create(
                    model=self.config.model,
                    max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                )

                latency = (time.time() - start_time) * 1000

                self.usage.prompt_tokens += response.usage.input_tokens
                self.usage.completion_tokens += response.usage.output_tokens
                self.usage.total_tokens += (
                    response.usage.input_tokens + response.usage.output_tokens
                )
                self._update_cost()

                return LLMResponse(
                    content=response.content[0].text,
                    model=self.config.model,
                    provider="anthropic",
                    tokens_used=response.usage.input_tokens
                    + response.usage.output_tokens,
                    latency_ms=latency,
                    finish_reason=response.stop_reason,
                    metadata={
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    },
                )

            except Exception as e:
                if attempt < self.config.retry_count - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise RuntimeError(f"Anthropic API error: {e}")

    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        if not self.client:
            raise RuntimeError("Anthropic client not initialized")

        system = kwargs.get(
            "system", "You are an expert Infrastructure-as-Code engineer."
        )

        with self.client.messages.stream(
            model=self.config.model,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    def _update_cost(self):
        model_key = None
        for key in self.PRICING:
            if key in self.config.model:
                model_key = key
                break

        pricing = self.PRICING.get(model_key, {"input": 0.003, "output": 0.015})
        self.usage.estimated_cost = (self.usage.prompt_tokens / 1000) * pricing[
            "input"
        ] + (self.usage.completion_tokens / 1000) * pricing["output"]


class OllamaProvider(BaseLLMProvider):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.api_base or "http://localhost:11434"

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        import urllib.request
        import urllib.error

        start_time = time.time()

        data = json.dumps(
            {
                "model": self.config.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", self.config.temperature),
                },
            }
        ).encode()

        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                result = json.loads(response.read().decode())

            latency = (time.time() - start_time) * 1000

            return LLMResponse(
                content=result.get("response", ""),
                model=self.config.model,
                provider="ollama",
                tokens_used=result.get("eval_count", 0),
                latency_ms=latency,
                finish_reason="stop",
                metadata=result,
            )

        except urllib.error.URLError as e:
            raise RuntimeError(f"Ollama API error: {e}")

    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        response = self.generate(prompt, **kwargs)
        yield response.content


class MockProvider(BaseLLMProvider):
    MOCK_RESPONSES = {
        "dockerfile": """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]""",
        "kubernetes": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: app
  template:
    metadata:
      labels:
        app: app
    spec:
      containers:
      - name: app
        image: app:latest
        ports:
        - containerPort: 8000""",
        "terraform": """provider "aws" {
  region = var.region
}

variable "region" {
  default = "us-west-2"
}

resource "aws_instance" "app" {
  ami           = "ami-12345678"
  instance_type = "t2.micro"
}""",
    }

    def __init__(self, config: LLMConfig):
        super().__init__(config)

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        start_time = time.time()

        prompt_lower = prompt.lower()

        if "dockerfile" in prompt_lower or "docker" in prompt_lower:
            content = self.MOCK_RESPONSES["dockerfile"]
        elif "kubernetes" in prompt_lower or "k8s" in prompt_lower:
            content = self.MOCK_RESPONSES["kubernetes"]
        elif "terraform" in prompt_lower:
            content = self.MOCK_RESPONSES["terraform"]
        else:
            content = self.MOCK_RESPONSES["kubernetes"]

        latency = (time.time() - start_time) * 1000

        self.usage.prompt_tokens += len(prompt.split())
        self.usage.completion_tokens += len(content.split())
        self.usage.total_tokens = (
            self.usage.prompt_tokens + self.usage.completion_tokens
        )

        return LLMResponse(
            content=content,
            model="mock",
            provider="mock",
            tokens_used=self.usage.total_tokens,
            latency_ms=latency,
            finish_reason="stop",
        )

    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        response = self.generate(prompt, **kwargs)
        for word in response.content.split():
            yield word + " "


class UnifiedLLMProvider:
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.provider_name = provider
        self.model_name = model
        self.api_key = api_key
        self._provider: Optional[BaseLLMProvider] = None
        self._init_provider()

    def _init_provider(self):
        if self.provider_name:
            provider_type = LLMProvider(self.provider_name)
        else:
            provider_type = self._detect_provider()

        model = self.model_name
        if not model:
            model = self._default_model(provider_type)

        config = LLMConfig(
            provider=provider_type,
            model=model,
            api_key=self.api_key,
        )

        if provider_type == LLMProvider.OPENAI:
            self._provider = OpenAIProvider(config)
        elif provider_type == LLMProvider.ANTHROPIC:
            self._provider = AnthropicProvider(config)
        elif provider_type == LLMProvider.OLLAMA:
            self._provider = OllamaProvider(config)
        else:
            self._provider = MockProvider(config)

    def _detect_provider(self) -> LLMProvider:
        if os.environ.get("OPENAI_API_KEY"):
            return LLMProvider.OPENAI
        elif os.environ.get("ANTHROPIC_API_KEY"):
            return LLMProvider.ANTHROPIC
        elif self._check_ollama():
            return LLMProvider.OLLAMA
        else:
            return LLMProvider.MOCK

    def _check_ollama(self) -> bool:
        try:
            import urllib.request

            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=2):
                return True
        except:
            return False

    def _default_model(self, provider: LLMProvider) -> str:
        defaults = {
            LLMProvider.OPENAI: "gpt-4o",
            LLMProvider.ANTHROPIC: "claude-3-sonnet-20240229",
            LLMProvider.OLLAMA: "llama2",
            LLMProvider.MOCK: "mock",
        }
        return defaults.get(provider, "mock")

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        return self._provider.generate(prompt, **kwargs)

    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        return self._provider.generate_stream(prompt, **kwargs)

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        return self._provider.chat(messages, **kwargs)

    def get_usage(self) -> LLMUsage:
        return self._provider.get_usage()

    @property
    def provider(self) -> str:
        return self._provider.config.provider.value

    @property
    def model(self) -> str:
        return self._provider.config.model


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> UnifiedLLMProvider:
    return UnifiedLLMProvider(provider=provider, model=model)


def generate_iac(
    request: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    llm = get_llm(provider, model)

    system_prompt = """You are an expert Infrastructure-as-Code engineer.
Generate production-ready IaC configurations based on user requests.
Include security best practices, resource limits, and health checks.
Output ONLY the code without explanations."""

    response = llm.generate(request, system=system_prompt)
    return response.content
