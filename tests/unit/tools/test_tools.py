"""Unit tests for ADR-046: @tool decorator, Tool, agent_loop, ToolCall, ToolCallResult.

5-family coverage:
  1. Behavior      — decorator extraction, agent_loop dispatch, tool-call round-trip
  2. Contract      — frozen dataclasses, Message amendment, LLMBackend protocol
  3. Architectural — __all__ exports, import boundaries
  4. NFR           — I23 max_iterations cap, custom override
  5. Failure-mode  — unknown tool, tool exception, iterations=1 stop
"""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest

from fast_agent_stack.core.ai.llm import (
    CompletionResult,
    Message,
    ToolCall,
    ToolCallResult,
)
from fast_agent_stack.core.ai.tools import Tool, agent_loop, tool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completion(content: str = "final answer") -> CompletionResult:
    return CompletionResult(
        content=content,
        model="test-model",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cost=None,
    )


def _make_tool_call_result(name: str = "search", args: dict | None = None) -> ToolCallResult:
    return ToolCallResult(tool_calls=[ToolCall(id="call-1", name=name, arguments=args or {"query": "test"})])


def _make_backend(responses: list) -> MagicMock:
    """Backend whose stream() yields responses in sequence.

    Each response in the list becomes one stream() call:
    - CompletionResult → yields text content tokens then the sentinel
    - ToolCallResult → yields the ToolCallResult directly
    """
    call_idx = {"i": 0}

    async def _stream_side_effect(*args, **kwargs):  # type: ignore[no-untyped-def]
        idx = call_idx["i"]
        call_idx["i"] += 1
        resp = responses[idx]
        if isinstance(resp, ToolCallResult):
            yield resp
        elif isinstance(resp, CompletionResult):
            # Yield content as tokens then sentinel
            if resp.content:
                yield resp.content
            yield CompletionResult(
                content="",
                model=resp.model,
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                total_tokens=resp.total_tokens,
                cost=resp.cost,
            )

    backend = MagicMock()
    backend.stream = MagicMock(side_effect=_stream_side_effect)
    return backend


async def _collect(ait: AsyncIterator) -> list:
    return [item async for item in ait]


# ---------------------------------------------------------------------------
# 1. Behavior
# ---------------------------------------------------------------------------


def test_tool_decorator_uses_function_name():
    @tool(description="does something")
    async def my_tool(query: str) -> str:
        return query

    assert my_tool.name == "my_tool"


def test_tool_decorator_uses_explicit_description():
    @tool(description="explicit desc")
    async def fn(x: int) -> str:
        """ignored docstring"""
        return str(x)

    assert my_tool_desc(fn) == "explicit desc"


def my_tool_desc(t: Tool) -> str:
    return t.description


def test_tool_decorator_uses_docstring_when_no_description():
    @tool()
    async def fn(x: str) -> str:
        """from the docstring"""
        return x

    assert fn.description == "from the docstring"


def test_tool_decorator_type_mapping():
    @tool(description="types")
    async def fn(a: str, b: int, c: float, d: bool) -> str:
        return ""

    props = fn.schema["function"]["parameters"]["properties"]
    assert props["a"]["type"] == "string"
    assert props["b"]["type"] == "integer"
    assert props["c"]["type"] == "number"
    assert props["d"]["type"] == "boolean"


def test_tool_decorator_required_vs_optional_params():
    @tool(description="req/opt")
    async def fn(required: str, optional: int = 5) -> str:
        return ""

    params = fn.schema["function"]["parameters"]
    assert "required" in params["required"]
    assert "optional" not in params["required"]
    assert params["properties"]["optional"]["default"] == 5


async def test_agent_loop_no_tool_calls_yields_content_and_sentinel():
    """Direct text response: yield content string then CompletionResult sentinel."""
    backend = _make_backend([_make_completion("hello world")])

    results = await _collect(agent_loop(backend, [Message(role="user", content="hi")], tools=[]))

    assert results[0] == "hello world"
    assert isinstance(results[1], CompletionResult)
    assert results[1].content == ""  # ADR-036: sentinel always has content=""


async def test_agent_loop_one_tool_call_then_final_response():
    """Tool call round-trip: call → execute → feed result → get final text."""
    call_result = _make_tool_call_result("search", {"query": "docs"})
    final = _make_completion("answer from docs")
    backend = _make_backend([call_result, final])

    @tool(description="search")
    async def search(query: str) -> str:
        return f"result for {query}"

    results = await _collect(
        agent_loop(
            backend,
            [Message(role="user", content="find something")],
            tools=[search],
        )
    )

    assert results[0] == "answer from docs"
    assert isinstance(results[1], CompletionResult)


async def test_agent_loop_passes_tool_schemas_to_backend():
    """agent_loop passes list[dict] schemas to backend.stream()."""
    backend = _make_backend([_make_completion()])

    @tool(description="a tool")
    async def my_fn(x: str) -> str:
        return x

    await _collect(agent_loop(backend, [], tools=[my_fn]))

    _, kwargs = backend.stream.call_args
    assert kwargs["tools"] is not None
    assert isinstance(kwargs["tools"], list)
    assert kwargs["tools"][0]["function"]["name"] == "my_fn"


async def test_agent_loop_appends_tool_role_messages():
    """Tool results are fed back as role='tool' messages."""
    call_result = _make_tool_call_result("search", {"query": "q"})
    final = _make_completion()
    backend = _make_backend([call_result, final])

    @tool(description="search")
    async def search(query: str) -> str:
        return "found it"

    await _collect(agent_loop(backend, [Message(role="user", content="find")], tools=[search]))

    # Second stream() call receives tool-result messages
    second_call_messages = backend.stream.call_args_list[1][0][0]
    tool_msgs = [m for m in second_call_messages if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].tool_call_id == "call-1"
    assert "found it" in tool_msgs[0].content


async def test_agent_loop_passes_none_tools_when_empty():
    """Empty tools list → tools=None passed to backend (no-op for non-tool backends)."""
    backend = _make_backend([_make_completion()])

    await _collect(agent_loop(backend, [], tools=[]))

    _, kwargs = backend.stream.call_args
    assert kwargs["tools"] is None


# ---------------------------------------------------------------------------
# 2. Contract
# ---------------------------------------------------------------------------


def test_toolcall_is_frozen_dataclass():
    tc = ToolCall(id="x", name="fn", arguments={"a": 1})
    assert dataclasses.is_dataclass(tc)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        tc.name = "other"  # type: ignore[misc]


def test_toolcallresult_is_frozen_dataclass():
    tcr = ToolCallResult(tool_calls=[])
    assert dataclasses.is_dataclass(tcr)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        tcr.tool_calls = []  # type: ignore[misc]


def test_message_tool_call_id_defaults_to_none():
    m = Message(role="user", content="hi")
    assert m.tool_call_id is None


def test_message_tool_calls_defaults_to_none():
    m = Message(role="user", content="hi")
    assert m.tool_calls is None


def test_message_tool_role_accepted():
    m = Message(role="tool", content="result", tool_call_id="call-1")
    assert m.role == "tool"
    assert m.tool_call_id == "call-1"


def test_tool_schema_has_openai_structure():
    @tool(description="test schema")
    async def fn(query: str, top_k: int = 3) -> str:
        return ""

    schema = fn.schema
    assert schema["type"] == "function"
    assert "function" in schema
    assert "name" in schema["function"]
    assert "description" in schema["function"]
    assert "parameters" in schema["function"]
    assert schema["function"]["parameters"]["type"] == "object"


def test_toolcall_dataclass_fields():
    fields = {f.name for f in dataclasses.fields(ToolCall)}
    assert fields == {"id", "name", "arguments"}


def test_toolcallresult_dataclass_fields():
    fields = {f.name for f in dataclasses.fields(ToolCallResult)}
    assert fields == {"tool_calls"}


# ---------------------------------------------------------------------------
# 3. Architectural
# ---------------------------------------------------------------------------


def test_tools_module_exports():
    from fast_agent_stack.core.ai.tools import __all__ as exported

    assert "tool" in exported
    assert "Tool" in exported
    assert "agent_loop" in exported


def test_llm_module_exports_toolcall_and_toolcallresult():
    from fast_agent_stack.core.ai.llm import __all__ as exported

    assert "ToolCall" in exported
    assert "ToolCallResult" in exported


def test_agent_loop_is_async_generator_function():
    assert inspect.isasyncgenfunction(agent_loop)


def test_tools_module_does_not_import_from_internals():
    """core/ai/tools/ must only import from core.ai.llm (public __init__), not sub-modules."""
    import fast_agent_stack.core.ai.tools as mod

    with open(mod.__file__) as f:
        src = f.read()

    # Must not reach into sub-modules like core.ai.llm.something
    assert "from fast_agent_stack.core.ai.llm." not in src


# ---------------------------------------------------------------------------
# 4. NFR — I23: max_iterations cap
# ---------------------------------------------------------------------------


async def test_agent_loop_respects_max_iterations_i23():
    """agent_loop stops after max_iterations even if backend keeps returning tool calls."""
    call_result = _make_tool_call_result()

    async def _always_tool_call(*args, **kwargs):  # type: ignore[no-untyped-def]
        yield call_result

    backend = MagicMock()
    backend.stream = MagicMock(side_effect=_always_tool_call)

    @tool(description="infinite tool")
    async def search(query: str) -> str:
        return "result"

    results = await _collect(agent_loop(backend, [], tools=[search], max_iterations=3))

    assert backend.stream.call_count == 3
    # Must yield a CompletionResult sentinel to signal end of stream
    sentinels = [r for r in results if isinstance(r, CompletionResult)]
    assert len(sentinels) == 1


async def test_agent_loop_custom_max_iterations():
    """max_iterations parameter overrides the default of 10."""

    async def _always_tool_call(*args, **kwargs):  # type: ignore[no-untyped-def]
        yield _make_tool_call_result()

    backend = MagicMock()
    backend.stream = MagicMock(side_effect=_always_tool_call)

    @tool(description="t")
    async def t(query: str) -> str:
        return "r"

    await _collect(agent_loop(backend, [], tools=[t], max_iterations=2))
    assert backend.stream.call_count == 2


async def test_agent_loop_empty_tools_list_still_works():
    """No tools registered: works like a plain complete() call."""
    backend = _make_backend([_make_completion("plain answer")])
    results = await _collect(agent_loop(backend, [], tools=[]))
    assert results[0] == "plain answer"


# ---------------------------------------------------------------------------
# 5. Failure-mode
# ---------------------------------------------------------------------------


async def test_agent_loop_unknown_tool_produces_error_string():
    """Tool call for an unknown tool name does not crash; error fed back as message."""
    call_result = ToolCallResult(tool_calls=[ToolCall(id="c1", name="nonexistent_tool", arguments={})])
    final = _make_completion("recovered")
    backend = _make_backend([call_result, final])

    results = await _collect(agent_loop(backend, [], tools=[]))

    # Should complete normally with the final response
    assert isinstance(results[-1], CompletionResult)
    # The second call receives an error tool message
    second_messages = backend.stream.call_args_list[1][0][0]
    error_msg = next(m for m in second_messages if m.role == "tool")
    assert "nonexistent_tool" in error_msg.content or "Error" in error_msg.content


async def test_agent_loop_tool_exception_is_caught_and_continued():
    """Tool that raises an exception: error fed back as message, loop continues."""
    call_result = _make_tool_call_result("failing_tool", {})
    final = _make_completion("recovered after error")
    backend = _make_backend([call_result, final])

    @tool(description="will raise")
    async def failing_tool() -> str:
        raise ValueError("something broke")

    results = await _collect(agent_loop(backend, [], tools=[failing_tool]))

    assert isinstance(results[-1], CompletionResult)
    second_messages = backend.stream.call_args_list[1][0][0]
    error_msg = next(m for m in second_messages if m.role == "tool")
    assert "something broke" in error_msg.content or "Error" in error_msg.content


async def test_agent_loop_max_iterations_1_yields_empty_sentinel():
    """With max_iterations=1 and a tool call response, yields empty sentinel immediately."""

    async def _tool_call_stream(*args, **kwargs):  # type: ignore[no-untyped-def]
        yield _make_tool_call_result()

    backend = MagicMock()
    backend.stream = MagicMock(side_effect=_tool_call_stream)

    @tool(description="t")
    async def t(query: str) -> str:
        return "r"

    results = await _collect(agent_loop(backend, [], tools=[t], max_iterations=1))

    sentinels = [r for r in results if isinstance(r, CompletionResult)]
    assert len(sentinels) == 1
    assert sentinels[0].content == ""
