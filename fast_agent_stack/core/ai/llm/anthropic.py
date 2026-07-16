from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

try:
    from anthropic import AsyncAnthropic
except ImportError:
    raise ImportError("pip install fast-agent-stack[anthropic]") from None

from fast_agent_stack.core.ai.llm import CompletionResult, Message, ToolCall, ToolCallResult


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

    def _convert_messages(self, messages: list[Message]) -> tuple[str, list[dict[str, Any]]]:
        """Convert Message dataclasses to Anthropic Messages API format.

        Anthropic requires:
        - role="tool" → {"role": "user", "content": [{"type": "tool_result", ...}]}
        - assistant with tool_calls → {"role": "assistant", "content": [{"type": "tool_use", ...}]}
        - regular messages → {"role": ..., "content": text}
        """
        system_parts = [m.content for m in messages if m.role == "system"]
        conv: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                continue
            if m.role == "tool" and m.tool_call_id:
                conv.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id,
                                "content": m.content,
                            }
                        ],
                    }
                )
            elif m.role == "assistant" and m.tool_calls:
                content: list[dict[str, Any]] = []
                if m.content:
                    content.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                conv.append({"role": "assistant", "content": content})
            else:
                conv.append({"role": m.role, "content": m.content})
        return " ".join(system_parts), conv

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert OpenAI-format tools to Anthropic format."""
        result = []
        for t in tools:
            func = t.get("function", t)
            result.append(
                {
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {}),
                }
            )
        return result

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> CompletionResult | ToolCallResult:
        system_text, conv = self._convert_messages(messages)
        call_kwargs: dict[str, Any] = {
            "model": self._model_id,
            "max_tokens": self._max_tokens,
            "system": system_text,
            "messages": conv,
            **kwargs,
        }
        if tools:
            call_kwargs["tools"] = self._convert_tools(tools)

        response = await self._client.messages.create(**call_kwargs)

        # Check for tool use blocks
        tool_calls = [
            ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
            for block in response.content
            if block.type == "tool_use"
        ]
        if tool_calls:
            return ToolCallResult(tool_calls=tool_calls)

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

    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | CompletionResult | ToolCallResult]:
        system_text, conv = self._convert_messages(messages)
        call_kwargs: dict[str, Any] = {
            "model": self._model_id,
            "max_tokens": self._max_tokens,
            "system": system_text,
            "messages": conv,
            **kwargs,
        }
        if tools:
            call_kwargs["tools"] = self._convert_tools(tools)

        prompt_tokens = 0
        completion_tokens = 0
        async with self._client.messages.stream(**call_kwargs) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
            prompt_tokens = final.usage.input_tokens
            completion_tokens = final.usage.output_tokens

            # Check for tool use in final message
            tool_calls = [
                ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                for block in final.content
                if block.type == "tool_use"
            ]
            if tool_calls:
                yield ToolCallResult(tool_calls=tool_calls)
                return

        # ADR-036: sentinel is the absolute last item
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
