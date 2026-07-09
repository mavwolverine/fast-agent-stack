"""Phase 4b tests: LLM provider backends (Bedrock, OpenAI, Anthropic, LiteLLM).

SDK packages are mocked at module level so these tests run without installing
any optional SDK dependencies.
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Inject mock SDKs BEFORE importing any backend module.
# Setting sys.modules[name] = None marks the package as "not found" for the
# purpose of re-import (used in extras gate tests).
# We inject MagicMock instances so the module-level `import X` in each backend
# succeeds and yields a mock SDK object.
# ---------------------------------------------------------------------------

_MOCK_AIOBOTO3 = MagicMock(name="aioboto3")
_MOCK_BOTOCORE = MagicMock(name="botocore")
_MOCK_BOTOCORE_CONFIG = MagicMock(name="botocore.config")
_MOCK_OPENAI = MagicMock(name="openai")
_MOCK_ANTHROPIC = MagicMock(name="anthropic")
_MOCK_LITELLM = MagicMock(name="litellm")

for _name, _mock in [
    ("aioboto3", _MOCK_AIOBOTO3),
    ("botocore", _MOCK_BOTOCORE),
    ("botocore.config", _MOCK_BOTOCORE_CONFIG),
    ("openai", _MOCK_OPENAI),
    ("anthropic", _MOCK_ANTHROPIC),
    ("litellm", _MOCK_LITELLM),
]:
    if _name not in sys.modules:
        sys.modules[_name] = _mock  # type: ignore[assignment]

# Now import backends (they will use the mocks above)
import pytest  # noqa: E402

from fast_agent_stack.core.ai.llm import CompletionResult, LLMBackend, Message  # noqa: E402
from fast_agent_stack.core.ai.llm.anthropic import AnthropicLLMBackend  # noqa: E402
from fast_agent_stack.core.ai.llm.bedrock import BedrockLLMBackend  # noqa: E402
from fast_agent_stack.core.ai.llm.litellm import LiteLLMLLMBackend  # noqa: E402
from fast_agent_stack.core.ai.llm.openai import OpenAILLMBackend  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

_MSGS = [Message(role="user", content="Hello")]
_SYS_MSGS = [Message(role="system", content="You are helpful."), *_MSGS]


async def _collect(gen) -> list:  # type: ignore[type-arg]
    items = []
    async for item in gen:
        items.append(item)
    return items


def _make_bedrock_ctx(mock_client: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _make_bedrock_stream_events():
    async def _gen():
        yield {"contentBlockDelta": {"delta": {"text": "hello"}}}
        yield {"contentBlockDelta": {"delta": {"text": " world"}}}
        yield {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}}}

    return _gen()


def _make_openai_chunks():
    class _Chunk:
        def __init__(self, content=None, usage=None):
            self.choices = [MagicMock(delta=MagicMock(content=content))]
            self.usage = usage

    async def _gen():
        yield _Chunk(content="hello")
        yield _Chunk(content=" world")
        yield _Chunk(
            content=None,
            usage=MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    return _gen()


def _make_anthropic_ctx():
    async def _text_stream():
        yield "hello"
        yield " world"

    final = MagicMock()
    final.usage.input_tokens = 10
    final.usage.output_tokens = 5

    stream_obj = MagicMock()
    stream_obj.text_stream = _text_stream()
    stream_obj.get_final_message = AsyncMock(return_value=final)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=stream_obj)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _make_litellm_chunks():
    class _Chunk:
        def __init__(self, content=None, usage=None):
            self.choices = [MagicMock(delta=MagicMock(content=content))]
            self.usage = usage

    async def _gen():
        yield _Chunk(content="hello")
        yield _Chunk(content=" world")
        yield _Chunk(usage=MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15))

    return _gen()


# ---------------------------------------------------------------------------
# BedrockLLMBackend
# ---------------------------------------------------------------------------


class TestBedrockLLMBackend:
    def test_c1_isinstance(self):
        backend = BedrockLLMBackend(model_id="anthropic.claude-3-sonnet")
        assert isinstance(backend, LLMBackend)

    def test_b1_model_id(self):
        backend = BedrockLLMBackend(model_id="my-model")
        assert backend.model_id == "my-model"

    def test_a1_escape_hatch_session(self):
        backend = BedrockLLMBackend(model_id="m")
        # session is the aioboto3.Session instance (a mock in tests)
        assert backend.session is _MOCK_AIOBOTO3.Session.return_value

    async def test_b2_stream_sentinel_is_last(self):
        backend = BedrockLLMBackend(model_id="m")
        mock_client = MagicMock()
        mock_client.converse_stream = AsyncMock(return_value={"stream": _make_bedrock_stream_events()})
        backend._session.client.return_value = _make_bedrock_ctx(mock_client)

        items = await _collect(backend.stream(_MSGS))

        assert len(items) > 0
        last = items[-1]
        assert isinstance(last, CompletionResult)
        assert last.content == ""
        assert all(isinstance(x, str) for x in items[:-1])

    async def test_b3_stream_token_counts(self):
        backend = BedrockLLMBackend(model_id="m")
        mock_client = MagicMock()
        mock_client.converse_stream = AsyncMock(return_value={"stream": _make_bedrock_stream_events()})
        backend._session.client.return_value = _make_bedrock_ctx(mock_client)

        items = await _collect(backend.stream(_MSGS))
        sentinel: CompletionResult = items[-1]  # type: ignore[assignment]

        assert sentinel.prompt_tokens == 10
        assert sentinel.completion_tokens == 5
        assert sentinel.total_tokens == 15
        assert sentinel.cost is None

    async def test_b4_system_messages_extracted(self):
        backend = BedrockLLMBackend(model_id="m")
        mock_client = MagicMock()
        mock_client.converse = AsyncMock(
            return_value={
                "output": {"message": {"content": [{"text": "ok"}]}},
                "usage": {"inputTokens": 5, "outputTokens": 2, "totalTokens": 7},
            }
        )
        backend._session.client.return_value = _make_bedrock_ctx(mock_client)

        await backend.complete(_SYS_MSGS)

        call_kwargs = mock_client.converse.call_args.kwargs
        # system messages must be extracted to the `system` param
        assert any(part["text"] == "You are helpful." for part in call_kwargs["system"])
        # only non-system messages in `messages`
        assert all(m["role"] != "system" for m in call_kwargs["messages"])

    def test_n1_default_timeout(self):
        backend = BedrockLLMBackend(model_id="m")
        assert backend._timeout == 30.0

    def test_n2_custom_timeout(self):
        backend = BedrockLLMBackend(model_id="m", timeout=60.0)
        assert backend._timeout == 60.0

    def test_f1_extras_gate(self, monkeypatch):
        import importlib

        monkeypatch.setitem(sys.modules, "aioboto3", None)  # type: ignore[arg-type]
        monkeypatch.delitem(sys.modules, "fast_agent_stack.core.ai.llm.bedrock")

        with pytest.raises(ImportError, match=r"fast-agent-stack\[bedrock\]"):
            importlib.import_module("fast_agent_stack.core.ai.llm.bedrock")


# ---------------------------------------------------------------------------
# OpenAILLMBackend
# ---------------------------------------------------------------------------


class TestOpenAILLMBackend:
    def test_c1_isinstance(self):
        backend = OpenAILLMBackend(model_id="gpt-4o")
        assert isinstance(backend, LLMBackend)

    def test_b1_model_id(self):
        backend = OpenAILLMBackend(model_id="gpt-4o")
        assert backend.model_id == "gpt-4o"

    def test_a1_escape_hatch_client(self):
        backend = OpenAILLMBackend(model_id="gpt-4o")
        assert backend.client is _MOCK_OPENAI.AsyncOpenAI.return_value

    async def test_b2_stream_sentinel_is_last(self):
        backend = OpenAILLMBackend(model_id="gpt-4o")
        backend._client.chat.completions.create = AsyncMock(return_value=_make_openai_chunks())

        items = await _collect(backend.stream(_MSGS))

        assert len(items) > 0
        last = items[-1]
        assert isinstance(last, CompletionResult)
        assert last.content == ""
        assert all(isinstance(x, str) for x in items[:-1])

    async def test_b3_stream_token_counts(self):
        backend = OpenAILLMBackend(model_id="gpt-4o")
        backend._client.chat.completions.create = AsyncMock(return_value=_make_openai_chunks())

        items = await _collect(backend.stream(_MSGS))
        sentinel: CompletionResult = items[-1]  # type: ignore[assignment]

        assert sentinel.prompt_tokens == 10
        assert sentinel.completion_tokens == 5
        assert sentinel.total_tokens == 15

    async def test_b4_stream_options_include_usage(self):
        backend = OpenAILLMBackend(model_id="gpt-4o")
        mock_create = AsyncMock(return_value=_make_openai_chunks())
        backend._client.chat.completions.create = mock_create

        await _collect(backend.stream(_MSGS))

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("stream") is True
        assert call_kwargs.get("stream_options") == {"include_usage": True}

    def test_n1_default_timeout_passed_to_client(self):
        _MOCK_OPENAI.AsyncOpenAI.reset_mock()
        OpenAILLMBackend(model_id="m")
        _, kwargs = _MOCK_OPENAI.AsyncOpenAI.call_args
        assert kwargs.get("timeout") == 30.0

    def test_f1_extras_gate(self, monkeypatch):
        import importlib

        monkeypatch.setitem(sys.modules, "openai", None)  # type: ignore[arg-type]
        monkeypatch.delitem(sys.modules, "fast_agent_stack.core.ai.llm.openai")

        with pytest.raises(ImportError, match=r"fast-agent-stack\[openai\]"):
            importlib.import_module("fast_agent_stack.core.ai.llm.openai")


# ---------------------------------------------------------------------------
# AnthropicLLMBackend
# ---------------------------------------------------------------------------


class TestAnthropicLLMBackend:
    def test_c1_isinstance(self):
        backend = AnthropicLLMBackend(model_id="claude-3-5-sonnet")
        assert isinstance(backend, LLMBackend)

    def test_b1_model_id(self):
        backend = AnthropicLLMBackend(model_id="claude-3-5-sonnet")
        assert backend.model_id == "claude-3-5-sonnet"

    def test_a1_escape_hatch_client(self):
        backend = AnthropicLLMBackend(model_id="m")
        assert backend.client is _MOCK_ANTHROPIC.AsyncAnthropic.return_value

    async def test_b2_stream_sentinel_is_last(self):
        backend = AnthropicLLMBackend(model_id="m")
        backend._client.messages.stream.return_value = _make_anthropic_ctx()

        items = await _collect(backend.stream(_MSGS))

        assert len(items) > 0
        last = items[-1]
        assert isinstance(last, CompletionResult)
        assert last.content == ""
        assert all(isinstance(x, str) for x in items[:-1])

    async def test_b3_stream_token_counts(self):
        backend = AnthropicLLMBackend(model_id="m")
        backend._client.messages.stream.return_value = _make_anthropic_ctx()

        items = await _collect(backend.stream(_MSGS))
        sentinel: CompletionResult = items[-1]  # type: ignore[assignment]

        assert sentinel.prompt_tokens == 10
        assert sentinel.completion_tokens == 5
        assert sentinel.total_tokens == 15

    async def test_b4_system_messages_extracted(self):
        backend = AnthropicLLMBackend(model_id="m")
        backend._client.messages.stream.return_value = _make_anthropic_ctx()

        await _collect(backend.stream(_SYS_MSGS))

        call_kwargs = backend._client.messages.stream.call_args.kwargs
        assert "You are helpful." in call_kwargs["system"]
        assert all(m["role"] != "system" for m in call_kwargs["messages"])

    def test_n1_default_timeout_and_max_tokens(self):
        _MOCK_ANTHROPIC.AsyncAnthropic.reset_mock()
        AnthropicLLMBackend(model_id="m")
        _, kwargs = _MOCK_ANTHROPIC.AsyncAnthropic.call_args
        assert kwargs.get("timeout") == 30.0

    def test_n2_custom_max_tokens(self):
        backend = AnthropicLLMBackend(model_id="m", max_tokens=1024)
        assert backend._max_tokens == 1024

    def test_f1_extras_gate(self, monkeypatch):
        import importlib

        monkeypatch.setitem(sys.modules, "anthropic", None)  # type: ignore[arg-type]
        monkeypatch.delitem(sys.modules, "fast_agent_stack.core.ai.llm.anthropic")

        with pytest.raises(ImportError, match=r"fast-agent-stack\[anthropic\]"):
            importlib.import_module("fast_agent_stack.core.ai.llm.anthropic")


# ---------------------------------------------------------------------------
# LiteLLMLLMBackend
# ---------------------------------------------------------------------------


class TestLiteLLMLLMBackend:
    def test_c1_isinstance(self):
        backend = LiteLLMLLMBackend(model_id="gpt-4o")
        assert isinstance(backend, LLMBackend)

    def test_b1_model_id(self):
        backend = LiteLLMLLMBackend(model_id="bedrock/anthropic.claude-3")
        assert backend.model_id == "bedrock/anthropic.claude-3"

    def test_a1_escape_hatch_module(self):
        backend = LiteLLMLLMBackend(model_id="m")
        # Escape hatch must return whatever 'litellm' resolves to in sys.modules.
        # In production that's the real module; in tests it's our mock.
        assert backend.litellm_module is sys.modules["litellm"]

    async def test_b2_stream_sentinel_is_last(self):
        backend = LiteLLMLLMBackend(model_id="m")
        _MOCK_LITELLM.acompletion = AsyncMock(return_value=_make_litellm_chunks())
        _MOCK_LITELLM.completion_cost.return_value = None

        items = await _collect(backend.stream(_MSGS))

        assert len(items) > 0
        last = items[-1]
        assert isinstance(last, CompletionResult)
        assert last.content == ""
        assert all(isinstance(x, str) for x in items[:-1])

    async def test_b3_stream_token_counts(self):
        backend = LiteLLMLLMBackend(model_id="m")
        _MOCK_LITELLM.acompletion = AsyncMock(return_value=_make_litellm_chunks())
        _MOCK_LITELLM.completion_cost.return_value = None

        items = await _collect(backend.stream(_MSGS))
        sentinel: CompletionResult = items[-1]  # type: ignore[assignment]

        assert sentinel.prompt_tokens == 10
        assert sentinel.completion_tokens == 5
        assert sentinel.total_tokens == 15

    async def test_b4_cost_computed_when_available(self):
        backend = LiteLLMLLMBackend(model_id="m")
        _MOCK_LITELLM.acompletion = AsyncMock(return_value=_make_litellm_chunks())
        _MOCK_LITELLM.completion_cost.return_value = 0.001

        items = await _collect(backend.stream(_MSGS))
        sentinel: CompletionResult = items[-1]  # type: ignore[assignment]

        assert sentinel.cost == 0.001

    async def test_f1_cost_failure_yields_none(self):
        backend = LiteLLMLLMBackend(model_id="m")
        _MOCK_LITELLM.acompletion = AsyncMock(return_value=_make_litellm_chunks())
        _MOCK_LITELLM.completion_cost.side_effect = Exception("unknown model")

        items = await _collect(backend.stream(_MSGS))
        sentinel: CompletionResult = items[-1]  # type: ignore[assignment]

        assert sentinel.cost is None

    def test_n1_timeout_stored(self):
        backend = LiteLLMLLMBackend(model_id="m", timeout=60.0)
        assert backend._timeout == 60.0

    def test_n2_extra_kwargs_stored(self):
        backend = LiteLLMLLMBackend(model_id="m", api_key="sk-test", aws_region="us-east-1")
        assert backend._litellm_kwargs["api_key"] == "sk-test"
        assert backend._litellm_kwargs["aws_region"] == "us-east-1"

    def test_f2_extras_gate(self, monkeypatch):
        import importlib

        monkeypatch.setitem(sys.modules, "litellm", None)  # type: ignore[arg-type]
        monkeypatch.delitem(sys.modules, "fast_agent_stack.core.ai.llm.litellm")

        with pytest.raises(ImportError, match=r"fast-agent-stack\[litellm\]"):
            importlib.import_module("fast_agent_stack.core.ai.llm.litellm")
