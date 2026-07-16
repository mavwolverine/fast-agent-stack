from __future__ import annotations

import asyncio
import json
import types
from collections.abc import AsyncIterator
from typing import Any

try:
    import litellm
except ImportError:
    raise ImportError("pip install fast-agent-stack[litellm]") from None

from fast_agent_stack.core.ai.llm import CompletionResult, Message, ToolCall, ToolCallResult


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
        return litellm  # type: ignore[no-any-return]

    def _to_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Convert Message dataclasses to OpenAI-format dicts (including tool fields)."""
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
            "timeout": self._timeout,
            **self._litellm_kwargs,
            **kwargs,
        }
        if tools:
            call_kwargs["tools"] = tools

        response = await litellm.acompletion(**call_kwargs)
        choice = response.choices[0]

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
            "timeout": self._timeout,
            **self._litellm_kwargs,
            **kwargs,
        }
        if tools:
            call_kwargs["tools"] = tools

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        tool_calls_accumulator: dict[int, dict[str, Any]] = {}

        response = await litellm.acompletion(**call_kwargs)
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
            else:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
            if getattr(chunk, "usage", None):
                prompt_tokens = chunk.usage.prompt_tokens or 0
                completion_tokens = chunk.usage.completion_tokens or 0
                total_tokens = chunk.usage.total_tokens or 0

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
            try:
                cost: float | None = litellm.completion_cost(
                    model=self._model_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
            except Exception:
                cost = None
            # ADR-036: sentinel is the absolute last item
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
