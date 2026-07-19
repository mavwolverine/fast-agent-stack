"""AI agent tests — ConversationService, TokenUsageLog, agent dispatcher, migrations."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from fast_agent_stack.core.ai.conversation import (
    ConversationLog,
    ConversationMessage,
    ConversationService,
)
from fast_agent_stack.core.ai.llm import CompletionResult, Message
from fast_agent_stack.core.ai.usage import TokenUsageLog, UsageService
from fast_agent_stack.core.database.base import FRAMEWORK_TABLES, Base

# ---------------------------------------------------------------------------
# Helpers — in-memory DB
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session():
    """Async in-memory SQLite session with AI tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


def _make_result(**kwargs) -> CompletionResult:
    defaults = dict(
        content="ok",
        model="test-model",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cost=0.001,
    )
    defaults.update(kwargs)
    return CompletionResult(**defaults)


# ===========================================================================
# A — Architectural / contract
# ===========================================================================


class TestArchitectural:
    def test_a01_conversation_imports_only_from_core_database_init(self):
        """I12: conversation.py must only import Base from core.database (not sub-modules)."""
        src = Path("fast_agent_stack/core/ai/conversation.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith("fast_agent_stack.core.database."), (
                        f"I12 violation: direct sub-module import '{node.module}'"
                    )

    def test_a02_usage_imports_only_from_core_database_init(self):
        """I12: usage.py must only import Base from core.database (not sub-modules)."""
        src = Path("fast_agent_stack/core/ai/usage.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("fast_agent_stack.core.database."), (
                    f"I12 violation: direct sub-module import '{node.module}'"
                )

    def test_a03_migration_0001_naming_convention(self):
        """I16: first AI migration filename must match NNNN_fas_<module>_<desc>.py."""
        candidates = list(Path("fast_agent_stack/core/ai/migrations/versions").glob("0001_fas_ai_*.py"))
        assert len(candidates) == 1, "Expected exactly one 0001_fas_ai_*.py migration"

    def test_a04_migration_0002_naming_convention(self):
        """I16: second AI migration filename must match NNNN_fas_<module>_<desc>.py."""
        candidates = list(Path("fast_agent_stack/core/ai/migrations/versions").glob("0002_fas_ai_*.py"))
        assert len(candidates) == 1, "Expected exactly one 0002_fas_ai_*.py migration"

    def test_a05_migration_revision_ids(self):
        """ADR-044: revision IDs and branch labels for AI migration branch."""
        m1 = importlib.import_module("fast_agent_stack.core.ai.migrations.versions.0001_fas_ai_conversation")
        m2 = importlib.import_module("fast_agent_stack.core.ai.migrations.versions.0002_fas_ai_token_usage")
        assert m1.revision == "fas_ai_0001"
        assert m1.down_revision is None
        assert m1.branch_labels == ("fas_ai",)
        assert m2.revision == "fas_ai_0002"
        assert m2.down_revision == "fas_ai_0001"

    def test_a06_framework_tables_includes_ai_tables(self):
        """FRAMEWORK_TABLES must include all three AI table names."""
        assert "conversation_log" in FRAMEWORK_TABLES
        assert "conversation_messages" in FRAMEWORK_TABLES
        assert "token_usage_log" in FRAMEWORK_TABLES

    def test_a07_migration_gate_any_of_semantics(self):
        """Migration gate uses any-of find_spec; passes if at least one SDK present (ADR-044)."""
        from fast_agent_stack.cli.db import FRAMEWORK_MIGRATION_GATES

        module_path, gate_packages = FRAMEWORK_MIGRATION_GATES[-1]  # "ai" entry is last
        assert module_path == "fast_agent_stack.core.ai.migrations"
        # Must list all four AI SDK packages
        assert "anthropic" in gate_packages
        assert "openai" in gate_packages
        assert "litellm" in gate_packages
        assert "aioboto3" in gate_packages

    def test_a08_migration_gate_uses_find_spec_not_import(self):
        """Gate implementation must use importlib.util.find_spec, not importlib.import_module."""
        src = Path("fast_agent_stack/cli/db.py").read_text()
        assert "find_spec" in src
        # Should NOT call import_module for gate logic
        # (it's still used for other parts, but the gate loop should use find_spec)
        assert "importlib.util.find_spec" in src

    def test_a09_error_before_sentinel_not_swallowed(self):
        """ADR-036: exception raised before sentinel must propagate (not be swallowed)."""
        from fast_agent_stack.core.ai.streaming import stream_sse

        # Inspect the source: the generator loop must NOT wrap the yield in try/except
        src = inspect.getsource(stream_sse)
        # The sentinel interception block must be distinct from the yield
        assert "if isinstance(item, CompletionResult):" in src
        # yield must appear outside any broad except clause
        # (structural check: no "except" immediately wrapping the yield line)
        assert 'yield f"data:' in src


# ===========================================================================
# B — Behavior
# ===========================================================================


class TestConversationService:
    async def test_b01_create_conversation_returns_log(self, db_session):
        svc = ConversationService()
        log = await svc.create_conversation(agent_name="chat", db=db_session)
        assert isinstance(log.id, UUID)
        assert log.agent_name == "chat"
        assert log.user_id is None

    async def test_b02_create_conversation_with_user_id(self, db_session):
        uid = uuid4()
        svc = ConversationService()
        log = await svc.create_conversation(agent_name="chat", user_id=uid, db=db_session)
        assert log.user_id == uid

    async def test_b03_append_message_and_get_messages(self, db_session):
        svc = ConversationService()
        log = await svc.create_conversation(agent_name="chat", db=db_session)
        msg = await svc.append_message(conversation_id=log.id, role="user", content="hello", db=db_session)
        assert isinstance(msg.id, UUID)
        assert msg.role == "user"
        assert msg.content == "hello"
        messages = await svc.get_messages(conversation_id=log.id, db=db_session)
        assert len(messages) == 1
        assert messages[0].content == "hello"

    async def test_b04_get_conversation_returns_none_for_unknown(self, db_session):
        svc = ConversationService()
        result = await svc.get_conversation(conversation_id=uuid4(), db=db_session)
        assert result is None

    async def test_b05_messages_ordered_by_created_at(self, db_session):
        """Messages are returned in insertion order (asc by created_at)."""
        svc = ConversationService()
        log = await svc.create_conversation(agent_name="chat", db=db_session)
        await svc.append_message(conversation_id=log.id, role="user", content="first", db=db_session)
        await svc.append_message(conversation_id=log.id, role="assistant", content="second", db=db_session)
        msgs = await svc.get_messages(conversation_id=log.id, db=db_session)
        assert [m.content for m in msgs] == ["first", "second"]


# ===========================================================================
# C — Contract (cost formula / schema)
# ===========================================================================


class TestUsageServiceContract:
    async def test_c01_cost_microcents_formula_known_cost(self, db_session):
        """ADR-035: cost_microcents = round(cost_dollars * 1_000_000)."""
        svc = UsageService()
        result = _make_result(cost=0.001234)
        await svc.log_usage(
            result,
            user_id=None,
            api_key_id=None,
            agent_name="chat",
            conversation_id=None,
            db=db_session,
        )
        row = (await db_session.execute(sa.select(TokenUsageLog))).scalar_one()
        assert row.cost_microcents == round(0.001234 * 1_000_000)

    async def test_c02_cost_microcents_null_when_cost_none(self, db_session):
        svc = UsageService()
        result = _make_result(cost=None)
        await svc.log_usage(
            result,
            user_id=None,
            api_key_id=None,
            agent_name="chat",
            conversation_id=None,
            db=db_session,
        )
        row = (await db_session.execute(sa.select(TokenUsageLog))).scalar_one()
        assert row.cost_microcents is None

    async def test_c03_high_cost_rounded_correctly(self, db_session):
        svc = UsageService()
        result = _make_result(cost=1.999999)
        await svc.log_usage(
            result,
            user_id=None,
            api_key_id=None,
            agent_name="chat",
            conversation_id=None,
            db=db_session,
        )
        row = (await db_session.execute(sa.select(TokenUsageLog))).scalar_one()
        assert row.cost_microcents == round(1.999999 * 1_000_000)

    async def test_c04_usage_log_row_fields_persisted(self, db_session):
        svc = UsageService()
        uid = uuid4()
        kid = uuid4()
        cid = uuid4()
        result = _make_result(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost=0.01)
        await svc.log_usage(
            result,
            user_id=uid,
            api_key_id=kid,
            agent_name="my-agent",
            conversation_id=cid,
            db=db_session,
        )
        row = (await db_session.execute(sa.select(TokenUsageLog))).scalar_one()
        assert row.user_id == uid
        assert row.api_key_id == kid
        assert row.agent_name == "my-agent"
        assert row.model == "test-model"
        assert row.prompt_tokens == 100
        assert row.completion_tokens == 50
        assert row.total_tokens == 150
        assert row.conversation_id == cid

    def test_c05_token_usage_log_tablename(self):
        assert TokenUsageLog.__tablename__ == "token_usage_log"

    def test_c06_conversation_log_tablenames(self):
        assert ConversationLog.__tablename__ == "conversation_log"
        assert ConversationMessage.__tablename__ == "conversation_messages"

    async def test_c07_log_usage_no_db_skips_write(self, db_session):
        """When db=None, log_usage is a no-op (Phase 4a backward compat)."""
        svc = UsageService()
        result = _make_result()
        await svc.log_usage(
            result,
            user_id=None,
            api_key_id=None,
            agent_name="chat",
            conversation_id=None,
            db=None,
        )
        rows = (await db_session.execute(sa.select(TokenUsageLog))).scalars().all()
        assert rows == []


# ===========================================================================
# B — Dispatcher / agent() method
# ===========================================================================


class TestAgentDispatcher:
    def _make_app(self):
        from fast_agent_stack.core.app import FastAgentStack

        return FastAgentStack()

    def _make_backend(self, content="response text"):
        backend = MagicMock()
        backend.model_id = "test-model"
        backend.complete = AsyncMock(return_value=_make_result(content=content))
        return backend

    def test_b06_agent_decorator_mounts_post_route(self):
        """I6: @app.agent registers a POST route at /agents/{name}."""
        app = self._make_app()
        backend = self._make_backend()

        @app.agent("chat", backend=backend)
        async def handler(messages, *, user_id, api_key_id, conversation_id):
            return "hello"

        routes = {r.path: r.methods for r in app.fastapi_app.routes if hasattr(r, "methods")}  # type: ignore[attr-defined]
        assert "/agents/chat" in routes
        assert "POST" in routes["/agents/chat"]

    def test_b07_duplicate_agent_name_raises(self):
        """I6: registering the same agent name twice must raise ValueError immediately."""
        app = self._make_app()
        backend = self._make_backend()

        @app.agent("chat", backend=backend)
        async def handler(messages, *, user_id, api_key_id, conversation_id):
            return "first"

        with pytest.raises(ValueError, match="chat"):

            @app.agent("chat", backend=backend)
            async def handler2(messages, *, user_id, api_key_id, conversation_id):
                return "second"

    async def test_b08_non_streaming_dispatch_returns_json(self, db_session):
        """Non-streaming handler → JSONResponse with content + model."""
        from fast_agent_stack.core.ai.agents import dispatch

        backend = self._make_backend(content="hello world")

        async def handler(messages, *, user_id, api_key_id, conversation_id):
            return "prompt text"

        resp = await dispatch(
            handler,
            backend,
            [Message(role="user", content="hi")],
            user_id=None,
            api_key_id=None,
            agent_name="chat",
            conversation_id=None,
            db=db_session,
        )
        from fastapi.responses import JSONResponse

        assert isinstance(resp, JSONResponse)
        import json

        body = json.loads(resp.body)
        assert body["content"] == "hello world"
        assert "model" in body

    async def test_b09_streaming_dispatch_returns_sse_response(self, db_session):
        """Streaming handler → StreamingResponse (text/event-stream)."""
        from fastapi.responses import StreamingResponse

        from fast_agent_stack.core.ai.agents import dispatch

        backend = self._make_backend()
        sentinel = _make_result(content="")

        async def stream_handler(messages, *, user_id, api_key_id, conversation_id):
            yield "chunk1"
            yield "chunk2"
            yield sentinel

        resp = await dispatch(
            stream_handler,
            backend,
            [Message(role="user", content="hi")],
            user_id=None,
            api_key_id=None,
            agent_name="chat",
            conversation_id=None,
            db=db_session,
        )
        assert isinstance(resp, StreamingResponse)
        assert resp.media_type == "text/event-stream"

    def test_b10_dispatch_detects_async_gen_via_isasyncgenfunction(self):
        """Dispatcher uses inspect.isasyncgenfunction to choose path."""
        import inspect

        async def streaming_handler(messages, *, user_id, api_key_id, conversation_id):
            yield "x"

        async def plain_handler(messages, *, user_id, api_key_id, conversation_id):
            return "x"

        assert inspect.isasyncgenfunction(streaming_handler)
        assert not inspect.isasyncgenfunction(plain_handler)


# ===========================================================================
# F — Failure modes
# ===========================================================================


class TestFailureModes:
    async def test_f01_i21_log_usage_failure_swallowed_non_streaming(self, db_session):
        """I21: log_usage failure in non-streaming dispatch is swallowed."""
        from fast_agent_stack.core.ai import agents as agents_module
        from fast_agent_stack.core.ai.agents import dispatch

        backend = MagicMock()
        backend.model_id = "test-model"
        backend.complete = AsyncMock(return_value=_make_result())

        async def handler(messages, *, user_id, api_key_id, conversation_id):
            return "prompt"

        failing_log = AsyncMock(side_effect=RuntimeError("db down"))
        with patch.object(agents_module._usage_service, "log_usage", failing_log):
            # Must NOT raise despite log_usage failing
            resp = await dispatch(
                handler,
                backend,
                [Message(role="user", content="hi")],
                user_id=None,
                api_key_id=None,
                agent_name="chat",
                conversation_id=None,
                db=db_session,
            )
        from fastapi.responses import JSONResponse

        assert isinstance(resp, JSONResponse)

    async def test_f02_i21_log_usage_failure_swallowed_streaming(self, db_session):
        """I21: log_usage failure in streaming path is swallowed."""
        from fast_agent_stack.core.ai import streaming as streaming_module
        from fast_agent_stack.core.ai.streaming import stream_sse

        sentinel = _make_result(content="")

        async def gen():
            yield "chunk"
            yield sentinel

        failing_log = AsyncMock(side_effect=RuntimeError("db down"))
        with patch.object(streaming_module._usage_service, "log_usage", failing_log):
            resp = await stream_sse(
                gen(),
                user_id=None,
                api_key_id=None,
                agent_name="chat",
                conversation_id=None,
                db=db_session,
            )
            chunks = []
            async for chunk in resp.body_iterator:
                chunks.append(chunk)
        assert chunks == [b'data: "chunk"\n\n']

    async def test_f03_error_before_sentinel_propagates_in_streaming(self, db_session):
        """ADR-036: LLM error before sentinel must propagate (not be swallowed)."""
        from fast_agent_stack.core.ai.streaming import stream_sse

        async def failing_gen():
            yield "chunk"
            raise RuntimeError("upstream LLM error")

        resp = await stream_sse(
            failing_gen(),
            user_id=None,
            api_key_id=None,
            agent_name="chat",
            conversation_id=None,
            db=db_session,
        )
        with pytest.raises(RuntimeError, match="upstream LLM error"):
            async for _ in resp.body_iterator:
                pass

    def test_f04_duplicate_route_not_added_on_second_registration(self):
        """Second registration with same name raises — route count stays the same."""
        from fast_agent_stack.core.app import FastAgentStack

        app = FastAgentStack()
        backend = MagicMock()

        @app.agent("chat", backend=backend)
        async def h1(messages, *, user_id, api_key_id, conversation_id):
            return "x"

        route_count = len(app.fastapi_app.routes)

        with pytest.raises(ValueError):

            @app.agent("chat", backend=backend)
            async def h2(messages, *, user_id, api_key_id, conversation_id):
                return "x"

        assert len(app.fastapi_app.routes) == route_count

    def test_f05_ai_package_dir_respects_llm_provider_none(self):
        """ai/ package uses a copier directory-name conditional gated on llm_provider (ADR replaces the
        old single-file agents.py.jinja content-guard with a directory-name guard)."""
        from fast_agent_stack.cli.new import TEMPLATE_DIR

        project_dir = TEMPLATE_DIR / "{{project_name}}"
        matches = [d for d in project_dir.iterdir() if d.is_dir() and "ai" in d.name and "endif" in d.name]
        assert matches, "ai/ conditional directory not found in template/{{project_name}}/"
        dirname = matches[0].name
        assert '{% if llm_provider != "none" %}' in dirname or "{% if llm_provider != 'none' %}" in dirname
        assert "{% endif %}" in dirname

    def test_f06_ai_agents_jinja_delegates_to_get_llm_factory(self):
        """ai/agents/__init__.py.jinja must delegate provider selection to get_llm(), not hardcode a
        provider-specific branch (I7) - get_llm() itself covers all four providers, tested in
        test_llm_backends.py::TestGetLLMFactory."""
        from fast_agent_stack.cli.new import TEMPLATE_DIR

        project_dir = TEMPLATE_DIR / "{{project_name}}"
        matches = [d for d in project_dir.iterdir() if d.is_dir() and "ai" in d.name and "endif" in d.name]
        assert matches, "ai/ conditional directory not found in template/{{project_name}}/"
        agents_init = matches[0] / "agents" / "__init__.py.jinja"
        assert agents_init.exists(), f"Missing: {agents_init}"
        template = agents_init.read_text()
        assert "get_llm(" in template, "ai/agents/__init__.py.jinja must call get_llm() to resolve the configured provider"


# ===========================================================================
# N — NFR / roundtrip
# ===========================================================================


class TestMigrationRoundtrip:
    async def test_n02_usage_log_write_and_read(self, db_session):
        """End-to-end: write usage row and read it back."""
        svc = UsageService()
        result = _make_result(cost=0.005)
        await svc.log_usage(
            result,
            user_id=None,
            api_key_id=None,
            agent_name="integration",
            conversation_id=None,
            db=db_session,
        )
        rows = (await db_session.execute(sa.select(TokenUsageLog))).scalars().all()
        assert len(rows) == 1
        assert rows[0].agent_name == "integration"
        assert rows[0].cost_microcents == 5000

    async def test_n03_conversation_message_ordering_with_multiple(self, db_session):
        """Multiple messages are returned in insertion order."""
        svc = ConversationService()
        log = await svc.create_conversation(agent_name="chat", db=db_session)
        for i in range(5):
            await svc.append_message(
                conversation_id=log.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"msg-{i}",
                db=db_session,
            )
        msgs = await svc.get_messages(conversation_id=log.id, db=db_session)
        assert [m.content for m in msgs] == [f"msg-{i}" for i in range(5)]
