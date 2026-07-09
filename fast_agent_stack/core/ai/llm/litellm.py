from __future__ import annotations

import asyncio
import types
from collections.abc import AsyncIterator
from typing import Any

try:
    import litellm
except ImportError:
    raise ImportError("pip install fast-agent-stack[litellm]") from None

from fast_agent_stack.core.ai.llm import CompletionResult, Message


class LiteLLMLLMBackend:
    def __init__(
        self,
        model_id: str,
        timeout: float = 30.0,
        settings: Any | None = None,
        **litellm_kwargs: Any,
    ) -> None:
        self._model_id = model_id
        self._timeout = settings.llm_timeout if settings is not None else timeout
        self._litellm_kwargs = litellm_kwargs

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def litellm_module(self) -> types.ModuleType:
        """Escape hatch (I4): direct access to the litellm module."""
        return litellm  # type: ignore[return-value]

    def _to_messages(self, messages: list[Message]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResult:
        response = await litellm.acompletion(
            model=self._model_id,
            messages=self._to_messages(messages),
            timeout=self._timeout,
            **self._litellm_kwargs,
            **kwargs,
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        try:
            cost: float | None = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = None
        return CompletionResult(
            content=content,
            model=self._model_id,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            cost=cost,
        )

    async def stream(self, messages: list[Message], **kwargs: Any) -> AsyncIterator[str | CompletionResult]:
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        response = await litellm.acompletion(
            model=self._model_id,
            messages=self._to_messages(messages),
            stream=True,
            timeout=self._timeout,
            **self._litellm_kwargs,
            **kwargs,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
            if getattr(chunk, "usage", None):
                prompt_tokens = chunk.usage.prompt_tokens or 0
                completion_tokens = chunk.usage.completion_tokens or 0
                total_tokens = chunk.usage.total_tokens or 0
        try:
            cost: float | None = litellm.completion_cost(
                model=self._model_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        except Exception:
            cost = None
        # ADR-036: sentinel is the absolute last item — no content after this
        yield CompletionResult(
            content="",
            model=self._model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
        )

    async def count_tokens(self, messages: list[Message]) -> int:
        litellm_messages = self._to_messages(messages)
        # litellm.token_counter is a pure computation (no network I/O).
        # to_thread avoids blocking the event loop on large inputs.
        return await asyncio.to_thread(
            litellm.token_counter,
            model=self._model_id,
            messages=litellm_messages,
        )
