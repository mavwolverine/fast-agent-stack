from __future__ import annotations

from typing import Any, AsyncIterator

try:
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError("pip install fast-agent-stack[openai]") from None

from fast_agent_stack.core.ai.llm import CompletionResult, Message


class OpenAILLMBackend:
    def __init__(
        self,
        model_id: str,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        settings: Any | None = None,
    ) -> None:
        self._model_id = model_id
        _timeout = settings.llm_timeout if settings is not None else timeout
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=_timeout,
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def client(self) -> AsyncOpenAI:
        """Escape hatch (I4): direct access to the underlying AsyncOpenAI client."""
        return self._client

    def _to_messages(self, messages: list[Message]) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def complete(
        self, messages: list[Message], **kwargs: Any
    ) -> CompletionResult:
        response = await self._client.chat.completions.create(
            model=self._model_id,
            messages=self._to_messages(messages),  # type: ignore[arg-type]
            **kwargs,
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        return CompletionResult(
            content=content,
            model=self._model_id,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            cost=None,
        )

    async def stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[str | CompletionResult]:
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        response = await self._client.chat.completions.create(
            model=self._model_id,
            messages=self._to_messages(messages),  # type: ignore[arg-type]
            stream=True,
            stream_options={"include_usage": True},
            **kwargs,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens
                completion_tokens = chunk.usage.completion_tokens
                total_tokens = chunk.usage.total_tokens
        # ADR-036: sentinel is the absolute last item — no content after this
        yield CompletionResult(
            content="",
            model=self._model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=None,
        )

    async def count_tokens(self, messages: list[Message]) -> int:
        # OpenAI has no public token-count endpoint.
        # Word-count estimate: ~1.3 tokens per word.
        return int(sum(len(m.content.split()) for m in messages) * 1.3)
