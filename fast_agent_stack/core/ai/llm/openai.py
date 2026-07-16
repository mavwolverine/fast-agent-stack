from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

try:
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError("pip install fast-agent-stack[openai]") from None

from fast_agent_stack.core.ai.llm import CompletionResult, Message, ToolCall, ToolCallResult


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
        _base_url = settings.llm_base_url if settings is not None else base_url
        _api_key = settings.llm_api_key if settings is not None else api_key
        self._client = AsyncOpenAI(
            api_key=_api_key,
            base_url=_base_url,
            timeout=_timeout,
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def client(self) -> AsyncOpenAI:
        """Escape hatch (I4): direct access to the underlying AsyncOpenAI client."""
        return self._client

    def _to_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for m in messages:
            msg: dict[str, Any] = {"role": m.role, "content": m.content}
            if m.tool_call_id is not None:
                msg["tool_call_id"] = m.tool_call_id
            if m.tool_calls is not None:
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in m.tool_calls
                ]
            result.append(msg)
        return result

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> CompletionResult | ToolCallResult:
        call_kwargs: dict[str, Any] = {
            "model": self._model_id,
            "messages": self._to_messages(messages),
            **kwargs,
        }
        if tools:
            call_kwargs["tools"] = tools

        response = await self._client.chat.completions.create(**call_kwargs)
        choice = response.choices[0]
        usage = response.usage

        # Check for tool calls
        if choice.message.tool_calls:
            return ToolCallResult(
                tool_calls=[
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=json.loads(tc.function.arguments),
                    )
                    for tc in choice.message.tool_calls
                ]
            )

        content = choice.message.content or ""
        return CompletionResult(
            content=content,
            model=self._model_id,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            cost=None,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | CompletionResult | ToolCallResult]:
        call_kwargs: dict[str, Any] = {
            "model": self._model_id,
            "messages": self._to_messages(messages),
            "stream": True,
            "stream_options": {"include_usage": True},
            **kwargs,
        }
        if tools:
            call_kwargs["tools"] = tools

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        tool_calls_accumulator: dict[int, dict[str, Any]] = {}

        response = await self._client.chat.completions.create(**call_kwargs)
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.tool_calls:
                # Accumulate tool call deltas
                for tc_delta in chunk.choices[0].delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_accumulator:
                        tool_calls_accumulator[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tool_calls_accumulator[idx]["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_accumulator[idx]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            tool_calls_accumulator[idx]["arguments"] += tc_delta.function.arguments
            elif chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens
                completion_tokens = chunk.usage.completion_tokens
                total_tokens = chunk.usage.total_tokens

        # If tool calls were accumulated, yield ToolCallResult
        if tool_calls_accumulator:
            yield ToolCallResult(
                tool_calls=[
                    ToolCall(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=json.loads(tc["arguments"]) if tc["arguments"] else {},
                    )
                    for tc in sorted(tool_calls_accumulator.values(), key=lambda x: x["id"])
                ]
            )
        else:
            # ADR-036: sentinel is the absolute last item
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
