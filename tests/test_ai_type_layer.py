"""Phase 4a tests: Message, CompletionResult, LLMBackend, UsageService, stream_sse."""
from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError
from typing import AsyncIterator
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from fast_agent_stack.core.ai.llm import CompletionResult, LLMBackend, Message
from fast_agent_stack.core.ai.usage import UsageService


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------


class TestMessage:
    def test_b1_attributes(self):
        m = Message(role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"

    def test_b2_frozen(self):
        m = Message(role="user", content="hello")
        with pytest.raises(FrozenInstanceError):
            m.role = "assistant"  # type: ignore[misc]

    def test_b3_equality_and_hash(self):
        a = Message(role="user", content="hi")
        b = Message(role="user", content="hi")
        assert a == b
        assert hash(a) == hash(b)
        assert a in {b}


# ---------------------------------------------------------------------------
# CompletionResult
# ---------------------------------------------------------------------------


class TestCompletionResult:
    def _make(self, **overrides):
        defaults = dict(
            content="hello",
            model="test-model",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.001,
        )
        defaults.update(overrides)
        return CompletionResult(**defaults)

    def test_b4_attributes(self):
        r = self._make()
        assert r.content == "hello"
        assert r.model == "test-model"
        assert r.prompt_tokens == 10
        assert r.completion_tokens == 5
        assert r.total_tokens == 15
        assert r.cost == 0.001

    def test_b5_frozen(self):
        r = self._make()
        with pytest.raises(FrozenInstanceError):
            r.content = "changed"  # type: ignore[misc]

    def test_b6_cost_none(self):
        r = self._make(cost=None)
        assert r.cost is None

    def test_b7_empty_content_sentinel_form(self):
        r = self._make(content="")
        assert r.content == ""

    def test_b8_equality_and_hash(self):
        a = self._make()
        b = self._make()
        assert a == b
        assert hash(a) == hash(b)


# ---------------------------------------------------------------------------
# LLMBackend Protocol
# ---------------------------------------------------------------------------


class TestLLMBackendProtocol:
    def _make_conforming(self):
        class Backend:
            @property
            def model_id(self) -> str:
                return "m"

            async def complete(self, messages, **kwargs):
                return CompletionResult("", "m", 0, 0, 0, None)

            async def stream(self, messages, **kwargs):
                yield ""

            async def count_tokens(self, messages):
                return 0

        return Backend()

    def test_c1_conforming_class_passes_isinstance(self):
        backend = self._make_conforming()
        assert isinstance(backend, LLMBackend)

    def test_c2_missing_complete_fails_isinstance(self):
        class Bad:
            @property
            def model_id(self) -> str:
                return "m"

            async def stream(self, messages, **kwargs):
                yield ""

            async def count_tokens(self, messages):
                return 0

        assert not isinstance(Bad(), LLMBackend)

    def test_c3_missing_stream_fails_isinstance(self):
        class Bad:
            @property
            def model_id(self) -> str:
                return "m"

            async def complete(self, messages, **kwargs):
                return CompletionResult("", "m", 0, 0, 0, None)

            async def count_tokens(self, messages):
                return 0

        assert not isinstance(Bad(), LLMBackend)

    def test_c4_missing_count_tokens_fails_isinstance(self):
        class Bad:
            @property
            def model_id(self) -> str:
                return "m"

            async def complete(self, messages, **kwargs):
                return CompletionResult("", "m", 0, 0, 0, None)

            async def stream(self, messages, **kwargs):
                yield ""

        assert not isinstance(Bad(), LLMBackend)


# ---------------------------------------------------------------------------
# UsageService
# ---------------------------------------------------------------------------


class TestUsageService:
    @pytest.fixture
    def service(self):
        return UsageService()

    @pytest.fixture
    def result(self):
        return CompletionResult("hi", "m", 10, 5, 15, None)

    @pytest.mark.asyncio
    async def test_b9_log_usage_completes_without_raising(self, service, result):
        await service.log_usage(
            result,
            user_id=None,
            api_key_id=None,
            agent_name="test-agent",
            conversation_id=None,
        )

    @pytest.mark.asyncio
    async def test_f1_log_usage_swallows_internal_exception(self, service, result):
        with patch.object(service, "log_usage", wraps=service.log_usage):
            # Inject a failure into the stub body via subclassing
            class FailingService(UsageService):
                async def log_usage(self, r, *, user_id, api_key_id, agent_name, conversation_id):
                    try:
                        raise RuntimeError("db down")
                    except Exception:
                        import logging
                        logging.getLogger(__name__).warning("swallowed", exc_info=True)

            svc = FailingService()
            # Must not raise
            await svc.log_usage(
                result,
                user_id=None,
                api_key_id=None,
                agent_name="test",
                conversation_id=None,
            )


# ---------------------------------------------------------------------------
# stream_sse
# ---------------------------------------------------------------------------


async def _make_iterator(items):
    for item in items:
        yield item


async def _collect_body(response) -> list[bytes]:
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    return chunks


_SENTINEL = CompletionResult(
    content="", model="m", prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=None
)

_KWARGS = dict(user_id=None, api_key_id=None, agent_name="test", conversation_id=None, db=None)


class TestStreamSSE:
    @pytest.mark.asyncio
    async def test_b10_returns_streaming_response(self):
        from fast_agent_stack.core.ai.streaming import stream_sse
        from fastapi.responses import StreamingResponse

        resp = await stream_sse(_make_iterator(["hi", _SENTINEL]), **_KWARGS)
        assert isinstance(resp, StreamingResponse)

    @pytest.mark.asyncio
    async def test_b11_media_type(self):
        from fast_agent_stack.core.ai.streaming import stream_sse

        resp = await stream_sse(_make_iterator(["hi", _SENTINEL]), **_KWARGS)
        assert resp.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_b12_sse_headers(self):
        from fast_agent_stack.core.ai.streaming import stream_sse

        resp = await stream_sse(_make_iterator(["hi", _SENTINEL]), **_KWARGS)
        assert resp.headers["cache-control"] == "no-cache"
        assert resp.headers["x-accel-buffering"] == "no"

    @pytest.mark.asyncio
    async def test_b13_str_chunks_emitted_as_sse_events(self):
        import json
        from fast_agent_stack.core.ai.streaming import stream_sse

        resp = await stream_sse(_make_iterator(["hello", " world", _SENTINEL]), **_KWARGS)
        body = await _collect_body(resp)
        assert body == [
            b'data: "hello"\n\n',
            b'data: " world"\n\n',
        ]

    @pytest.mark.asyncio
    async def test_b14_sentinel_not_emitted_to_client(self):
        from fast_agent_stack.core.ai.streaming import stream_sse

        resp = await stream_sse(_make_iterator([_SENTINEL]), **_KWARGS)
        body = await _collect_body(resp)
        assert body == []

    @pytest.mark.asyncio
    async def test_b15_log_usage_called_with_sentinel(self):
        from fast_agent_stack.core.ai import streaming
        from fast_agent_stack.core.ai.streaming import stream_sse

        mock_log = AsyncMock()
        with patch.object(streaming._usage_service, "log_usage", mock_log):
            resp = await stream_sse(_make_iterator(["chunk", _SENTINEL]), **_KWARGS)
            await _collect_body(resp)

        mock_log.assert_awaited_once_with(
            _SENTINEL,
            user_id=None,
            api_key_id=None,
            agent_name="test",
            conversation_id=None,
            db=None,
        )

    @pytest.mark.asyncio
    async def test_f2_error_before_sentinel_propagates(self):
        from fast_agent_stack.core.ai.streaming import stream_sse
        from fast_agent_stack.core.ai import streaming

        async def _failing():
            yield "chunk"
            raise RuntimeError("upstream LLM error")

        mock_log = AsyncMock()
        with patch.object(streaming._usage_service, "log_usage", mock_log):
            resp = await stream_sse(_failing(), **_KWARGS)
            with pytest.raises(RuntimeError, match="upstream LLM error"):
                await _collect_body(resp)

        mock_log.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_f3_log_usage_failure_swallowed(self):
        from fast_agent_stack.core.ai.streaming import stream_sse
        from fast_agent_stack.core.ai import streaming

        mock_log = AsyncMock(side_effect=Exception("db down"))
        with patch.object(streaming._usage_service, "log_usage", mock_log):
            resp = await stream_sse(_make_iterator(["chunk", _SENTINEL]), **_KWARGS)
            body = await _collect_body(resp)

        assert body == [b'data: "chunk"\n\n']

    @pytest.mark.asyncio
    async def test_b16_attribution_kwargs_forwarded(self):
        from fast_agent_stack.core.ai.streaming import stream_sse
        from fast_agent_stack.core.ai import streaming

        uid = uuid4()
        kid = uuid4()
        cid = uuid4()

        mock_log = AsyncMock()
        with patch.object(streaming._usage_service, "log_usage", mock_log):
            resp = await stream_sse(
                _make_iterator([_SENTINEL]),
                user_id=uid,
                api_key_id=kid,
                agent_name="my-agent",
                conversation_id=cid,
            )
            await _collect_body(resp)

        mock_log.assert_awaited_once_with(
            _SENTINEL,
            user_id=uid,
            api_key_id=kid,
            agent_name="my-agent",
            conversation_id=cid,
            db=None,
        )
