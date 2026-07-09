from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

try:
    from anthropic import AsyncAnthropic
except ImportError:
    raise ImportError("pip install fast-agent-stack[anthropic]") from None

from fast_agent_stack.core.ai.llm import CompletionResult, Message


class AnthropicLLMBackend:
    def __init__(
        self,
        model_id: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_tokens: int = 4096,
        settings: Any | None = None,
    ) -> None:
        self._model_id = model_id
        self._max_tokens = max_tokens
        _timeout = settings.llm_timeout if settings is not None else timeout
        self._client = AsyncAnthropic(
            api_key=api_key,
            timeout=_timeout,
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def client(self) -> AsyncAnthropic:
        """Escape hatch (I4): direct access to the underlying AsyncAnthropic client."""
        return self._client

    def _convert_messages(self, messages: list[Message]) -> tuple[str, list[dict[str, str]]]:
        system_parts = [m.content for m in messages if m.role == "system"]
        conv = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        return " ".join(system_parts), conv

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResult:
        system_text, conv = self._convert_messages(messages)
        response = await self._client.messages.create(
            model=self._model_id,
            max_tokens=self._max_tokens,
            system=system_text,
            messages=conv,
            **kwargs,
        )
        content = response.content[0].text if response.content else ""
        usage = response.usage
        return CompletionResult(
            content=content,
            model=self._model_id,
            prompt_tokens=usage.input_tokens,
            completion_tokens=usage.output_tokens,
            total_tokens=usage.input_tokens + usage.output_tokens,
            cost=None,
        )

    async def stream(self, messages: list[Message], **kwargs: Any) -> AsyncIterator[str | CompletionResult]:
        system_text, conv = self._convert_messages(messages)
        prompt_tokens = 0
        completion_tokens = 0
        async with self._client.messages.stream(
            model=self._model_id,
            max_tokens=self._max_tokens,
            system=system_text,
            messages=conv,
            **kwargs,
        ) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
            prompt_tokens = final.usage.input_tokens
            completion_tokens = final.usage.output_tokens
        # ADR-036: sentinel is the absolute last item — no content after this
        yield CompletionResult(
            content="",
            model=self._model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=None,
        )

    async def count_tokens(self, messages: list[Message]) -> int:
        system_text, conv = self._convert_messages(messages)
        response = await self._client.messages.count_tokens(
            model=self._model_id,
            system=system_text,
            messages=conv,
        )
        return response.input_tokens  # type: ignore[no-any-return]
