from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

try:
    import aioboto3
    from botocore.config import Config as BotocoreConfig
except ImportError:
    raise ImportError("pip install fast-agent-stack[bedrock]") from None

from fast_agent_stack.core.ai.llm import CompletionResult, Message, ToolCall, ToolCallResult


class BedrockLLMBackend:
    def __init__(
        self,
        model_id: str,
        region_name: str = "us-east-1",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        timeout: float = 30.0,
        settings: Any | None = None,
    ) -> None:
        self._model_id = model_id
        self._region = region_name
        _timeout = settings.llm_timeout if settings is not None else timeout
        self._timeout = _timeout
        self._session = aioboto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
        )
        self._boto_config = BotocoreConfig(
            connect_timeout=_timeout,
            read_timeout=_timeout,
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def session(self) -> Any:
        """Escape hatch (I4): direct access to the underlying aioboto3.Session."""
        return self._session

    def _convert_messages(self, messages: list[Message]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Convert Message dataclasses to Bedrock Converse API format.

        Bedrock requires:
        - role="tool" messages → {"role": "user", "content": [{"toolResult": {...}}]}
        - assistant messages with tool_calls → {"role": "assistant", "content": [{"toolUse": {...}}]}
        - regular messages → {"role": ..., "content": [{"text": ...}]}
        """
        system = [{"text": m.content} for m in messages if m.role == "system"]
        conv: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                continue
            if m.role == "tool" and m.tool_call_id:
                # Tool result message
                conv.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "toolResult": {
                                    "toolUseId": m.tool_call_id,
                                    "content": [{"text": m.content}],
                                }
                            }
                        ],
                    }
                )
            elif m.role == "assistant" and m.tool_calls:
                # Assistant requesting tool use
                content: list[dict[str, Any]] = []
                if m.content:
                    content.append({"text": m.content})
                for tc in m.tool_calls:
                    content.append(
                        {
                            "toolUse": {
                                "toolUseId": tc.id,
                                "name": tc.name,
                                "input": tc.arguments,
                            }
                        }
                    )
                conv.append({"role": "assistant", "content": content})
            else:
                conv.append({"role": m.role, "content": [{"text": m.content}]})
        return system, conv

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> CompletionResult | ToolCallResult:
        system, conv = self._convert_messages(messages)
        call_kwargs: dict[str, Any] = {
            "modelId": self._model_id,
            "messages": conv,
            "system": system,
            **kwargs,
        }
        if tools:
            # Convert OpenAI-format tools to Bedrock toolConfig
            call_kwargs["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": t.get("function", t)["name"],
                            "description": t.get("function", t).get("description", ""),
                            "inputSchema": {"json": t.get("function", t).get("parameters", {})},
                        }
                    }
                    for t in tools
                ]
            }

        async with self._session.client(
            "bedrock-runtime",
            region_name=self._region,
            config=self._boto_config,
        ) as client:
            response = await client.converse(**call_kwargs)

        output = response.get("output", {}).get("message", {}).get("content", [])
        usage = response.get("usage", {})

        # Check for tool use
        tool_calls = [
            ToolCall(
                id=block.get("toolUse", {}).get("toolUseId", ""),
                name=block.get("toolUse", {}).get("name", ""),
                arguments=block.get("toolUse", {}).get("input", {}),
            )
            for block in output
            if "toolUse" in block
        ]
        if tool_calls:
            return ToolCallResult(tool_calls=tool_calls)

        content = output[0]["text"] if output else ""
        return CompletionResult(
            content=content,
            model=self._model_id,
            prompt_tokens=usage.get("inputTokens", 0),
            completion_tokens=usage.get("outputTokens", 0),
            total_tokens=usage.get("totalTokens", 0),
            cost=None,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str | CompletionResult | ToolCallResult]:
        system, conv = self._convert_messages(messages)
        call_kwargs: dict[str, Any] = {
            "modelId": self._model_id,
            "messages": conv,
            "system": system,
            **kwargs,
        }
        if tools:
            call_kwargs["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": t.get("function", t)["name"],
                            "description": t.get("function", t).get("description", ""),
                            "inputSchema": {"json": t.get("function", t).get("parameters", {})},
                        }
                    }
                    for t in tools
                ]
            }

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        async with self._session.client(
            "bedrock-runtime",
            region_name=self._region,
            config=self._boto_config,
        ) as client:
            response = await client.converse_stream(**call_kwargs)
            tool_use_blocks: dict[int, dict[str, Any]] = {}
            current_block_idx = 0
            async for event in response["stream"]:
                if "contentBlockStart" in event:
                    start = event["contentBlockStart"]
                    current_block_idx = start.get("contentBlockIndex", 0)
                    if "toolUse" in start.get("start", {}):
                        tool_use_blocks[current_block_idx] = {
                            "toolUseId": start["start"]["toolUse"]["toolUseId"],
                            "name": start["start"]["toolUse"]["name"],
                            "input_json": "",
                        }
                elif "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]["delta"]
                    if "text" in delta:
                        chunk = delta["text"]
                        if chunk:
                            yield chunk
                    elif "toolUse" in delta:
                        # Accumulate tool input JSON fragments
                        idx = event["contentBlockDelta"].get("contentBlockIndex", current_block_idx)
                        if idx in tool_use_blocks:
                            tool_use_blocks[idx]["input_json"] += delta["toolUse"].get("input", "")
                elif "metadata" in event:
                    usage = event["metadata"].get("usage", {})
                    prompt_tokens = usage.get("inputTokens", 0)
                    completion_tokens = usage.get("outputTokens", 0)
                    total_tokens = usage.get("totalTokens", 0)

        # If tool calls were accumulated, yield ToolCallResult
        if tool_use_blocks:
            yield ToolCallResult(
                tool_calls=[
                    ToolCall(
                        id=block["toolUseId"],
                        name=block["name"],
                        arguments=json.loads(block["input_json"]) if block["input_json"] else {},
                    )
                    for block in tool_use_blocks.values()
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
        # Bedrock has no public token-count endpoint for the converse API.
        # Character-count estimate: ~4 chars per token.
        return sum(len(m.content) for m in messages) // 4
