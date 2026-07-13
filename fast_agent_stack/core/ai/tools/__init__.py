from __future__ import annotations

import inspect
import typing
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from fast_agent_stack.core.ai.llm import (
    CompletionResult,
    LLMBackend,
    Message,
    ToolCall,
    ToolCallResult,
)

__all__ = ["tool", "Tool", "agent_loop", "ToolCall", "ToolCallResult"]

_PYTHON_TO_JSON_TYPE: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
}


@dataclass
class Tool:
    """An async callable decorated with its OpenAI-compatible JSON schema (ADR-046)."""

    fn: Callable[..., Any]
    name: str
    description: str
    schema: dict[str, Any]

    async def __call__(self, **kwargs: Any) -> str:
        return await self.fn(**kwargs)


def tool(
    description: str | None = None,
) -> Callable[[Callable[..., Any]], Tool]:
    """Decorator that registers an async function as an LLM-callable tool (ADR-046).

    Usage::

        @tool(description="Search the document store")
        async def search(query: str, top_k: int = 5) -> str:
            ...
    """

    def decorator(fn: Callable[..., Any]) -> Tool:
        desc = description or (fn.__doc__ or "").strip()
        sig = inspect.signature(fn)
        # get_type_hints() evaluates string annotations from `from __future__ import annotations`
        try:
            hints = typing.get_type_hints(fn)
        except Exception:
            hints = {}
        properties: dict[str, Any] = {}
        required: list[str] = []
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            annotation = hints.get(param_name, inspect.Parameter.empty)
            json_type = _PYTHON_TO_JSON_TYPE.get(annotation, "string")
            prop: dict[str, Any] = {"type": json_type}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)
            else:
                prop["default"] = param.default
            properties[param_name] = prop
        schema = {
            "type": "function",
            "function": {
                "name": fn.__name__,
                "description": desc,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
        return Tool(fn=fn, name=fn.__name__, description=desc, schema=schema)

    return decorator


async def agent_loop(
    backend: LLMBackend,
    messages: list[Message],
    *,
    tools: list[Tool],
    max_iterations: int = 10,
) -> AsyncIterator[str | CompletionResult]:
    """LLM-tool dispatch loop (ADR-046, I23: capped at max_iterations).

    Yields text chunks and a CompletionResult sentinel on the final response.
    Yields an empty CompletionResult sentinel when max_iterations is reached.
    """
    tool_map = {t.name: t for t in tools}
    tool_schemas: list[dict[str, Any]] = [t.schema for t in tools]
    current_messages = list(messages)

    for _ in range(max_iterations):
        result = await backend.complete(
            current_messages,
            tools=tool_schemas if tool_schemas else None,
        )

        if isinstance(result, ToolCallResult):
            current_messages.append(Message(role="assistant", content="", tool_calls=result.tool_calls))
            for call in result.tool_calls:
                fn = tool_map.get(call.name)
                if fn is None:
                    tool_output = f"Error: unknown tool {call.name!r}"
                else:
                    try:
                        tool_output = await fn(**call.arguments)
                    except Exception as exc:
                        tool_output = f"Error: {exc}"
                current_messages.append(Message(role="tool", content=str(tool_output), tool_call_id=call.id))
        else:
            # Final text response — yield content chunk then sentinel
            yield result.content
            yield result
            return

    # Reached iteration cap (I23) — emit empty sentinel to close the stream
    yield CompletionResult(
        content="",
        model="",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost=None,
    )
