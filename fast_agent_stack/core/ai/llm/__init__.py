from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Protocol, runtime_checkable

__all__ = ["Message", "CompletionResult", "LLMBackend"]


@dataclass(frozen=True)
class Message:
    role: str  # "user" | "assistant" | "system"
    content: str


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
        self, messages: list[Message], **kwargs: Any
    ) -> CompletionResult: ...

    async def stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[str | CompletionResult]: ...

    async def count_tokens(self, messages: list[Message]) -> int: ...
