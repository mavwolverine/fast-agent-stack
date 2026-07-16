from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

__all__ = ["Message", "CompletionResult", "LLMBackend", "ToolCall", "ToolCallResult", "get_llm"]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolCallResult:
    """Returned by LLMBackend.complete() when the model wants to invoke a tool (ADR-046)."""

    tool_calls: list[ToolCall]


@dataclass(frozen=True)
class Message:
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    tool_call_id: str | None = None  # set for role="tool" responses
    tool_calls: list[ToolCall] | None = None  # set for role="assistant" tool-use turns


@dataclass(frozen=True)
class CompletionResult:
    content: str  # empty string ("") for the streaming sentinel
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float | None


@runtime_checkable
class LLMBackend(Protocol):
    @property
    def model_id(self) -> str: ...

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> CompletionResult | ToolCallResult: ...

    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | CompletionResult | ToolCallResult]: ...

    async def count_tokens(self, messages: list[Message]) -> int: ...


def get_llm(settings: Any) -> LLMBackend:
    """Factory: resolves alias or ADR-012 dotted path for LLM backend."""
    import importlib

    provider = settings.llm_provider
    if provider == "openai":
        from fast_agent_stack.core.ai.llm.openai import OpenAILLMBackend

        return OpenAILLMBackend(model_id=settings.llm_model, settings=settings)
    if provider == "anthropic":
        from fast_agent_stack.core.ai.llm.anthropic import AnthropicLLMBackend

        return AnthropicLLMBackend(model_id=settings.llm_model, settings=settings)
    if provider == "bedrock":
        from fast_agent_stack.core.ai.llm.bedrock import BedrockLLMBackend

        return BedrockLLMBackend(model_id=settings.llm_model, settings=settings)
    if provider == "litellm":
        from fast_agent_stack.core.ai.llm.litellm import LiteLLMLLMBackend

        return LiteLLMLLMBackend(model_id=settings.llm_model, settings=settings)
    # ADR-012 dotted-path custom backend
    module_path, _, class_name = provider.rpartition(".")
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls(settings=settings)  # type: ignore[no-any-return]
