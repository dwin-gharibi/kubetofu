import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str
    metadata: Dict[str, Any]


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        pass

    @abstractmethod
    async def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs,
    ) -> Dict[str, Any]:
        pass


class AnthropicProvider(BaseLLMProvider):
    def __init__(
        self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"
    ):
        self.api_key = api_key or settings.LLM_SETTINGS.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or "You are a helpful AI assistant.",
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    async def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs,
    ) -> Dict[str, Any]:
        messages = [{"role": "user", "content": prompt}]

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or "You are a helpful AI assistant.",
                messages=messages,
                tools=tools,
            )

            result = {
                "content": "",
                "tool_calls": [],
            }

            for block in response.content:
                if hasattr(block, "text"):
                    result["content"] += block.text
                elif hasattr(block, "type") and block.type == "tool_use":
                    result["tool_calls"].append(
                        {
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )

            return result
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise


class OpenAIProvider(BaseLLMProvider):
    def __init__(
        self, api_key: Optional[str] = None, model: str = "gpt-4-turbo-preview"
    ):
        self.api_key = api_key or settings.LLM_SETTINGS.get("OPENAI_API_KEY", "")
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import openai

            self._client = openai.AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        messages = [
            {
                "role": "system",
                "content": system_prompt or "You are a helpful AI assistant.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs,
    ) -> Dict[str, Any]:
        messages = [
            {
                "role": "system",
                "content": system_prompt or "You are a helpful AI assistant.",
            },
            {"role": "user", "content": prompt},
        ]

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            }
            for tool in tools
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=openai_tools if openai_tools else None,
            )

            message = response.choices[0].message
            result = {
                "content": message.content or "",
                "tool_calls": [],
            }

            if message.tool_calls:
                import json

                for tc in message.tool_calls:
                    result["tool_calls"].append(
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "input": json.loads(tc.function.arguments),
                        }
                    )

            return result
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


class OllamaProvider(BaseLLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url
        self.model = model

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        import aiohttp

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt or "You are a helpful AI assistant.",
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                ) as response:
                    result = await response.json()
                    return result.get("response", "")
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise

    async def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs,
    ) -> Dict[str, Any]:
        tools_desc = "\n".join(
            f"- {t['name']}: {t.get('description', '')}" for t in tools
        )

        enhanced_prompt = f"""{prompt}

Available tools:
{tools_desc}

If you need to use a tool, respond with:
TOOL: <tool_name>
INPUT: <json input>
"""

        response = await self.generate(
            prompt=enhanced_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return {"content": response, "tool_calls": []}


class LLMProvider:
    PROVIDERS = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
    }

    def __init__(
        self,
        provider: str = "anthropic",
        model: Optional[str] = None,
        **kwargs,
    ):
        self.provider_name = provider.lower()

        if self.provider_name not in self.PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}")

        default_models = {
            "anthropic": "claude-sonnet-4-20250514",
            "openai": "gpt-4-turbo-preview",
            "ollama": "llama3",
        }

        self.model = model or default_models.get(self.provider_name)
        self._provider = self.PROVIDERS[self.provider_name](model=self.model, **kwargs)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        return await self._provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs,
    ) -> Dict[str, Any]:
        return await self._provider.generate_with_tools(
            prompt=prompt,
            tools=tools,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    @classmethod
    def from_settings(cls) -> "LLMProvider":
        llm_settings = getattr(settings, "LLM_SETTINGS", {})
        return cls(
            provider=llm_settings.get("PROVIDER", "anthropic"),
            model=llm_settings.get("MODEL"),
        )
