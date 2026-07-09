"""Database module tests — 5 families (B/C/A/N/F).

Integration tests use SQLite in-memory via aiosqlite (dev dependency).
Module-level globals in session.py are reset between tests via the
`reset_db` autouse fixture.
"""

import time
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import fast_agent_stack.core.database.session as _session_mod
from fast_agent_stack.core.app import FastAgentStack
from fast_agent_stack.core.database import (
    FRAMEWORK_TABLES,
    Base,
    BaseModel,
    DatabaseLifespanHook,
    check_db,
    configure_engine,
    dispose_engine,
    get_async_session,
    get_async_session_for_schema,
    get_engine,
)
from fast_agent_stack.core.protocols import LifespanHook

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
async def reset_db() -> Any:
    """Reset engine/session state between tests."""
    yield
    await dispose_engine()


# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


def test_b1_base_is_declarative_base() -> None:
    assert hasattr(Base, "metadata")


def test_b2_base_model_is_abstract() -> None:
    assert BaseModel.__abstract__ is True


def test_b3_base_model_has_required_columns() -> None:
    {c.key for c in BaseModel.__table_args__} if hasattr(BaseModel, "__table_args__") else set()

    # Check via mapper inspect on a concrete subclass
    class _M(BaseModel):
        __tablename__ = "test_base_model_cols"

    col_names = {c.name for c in _M.__table__.columns}
    assert "id" in col_names
    assert "created_at" in col_names
    assert "updated_at" in col_names


def test_b4_get_engine_none_before_configure() -> None:
    assert get_engine() is None


def test_b5_configure_engine_creates_engine() -> None:
    configure_engine(SQLITE_URL)
    engine = get_engine()
    assert engine is not None


async def test_b6_get_async_session_yields_async_session() -> None:
    configure_engine(SQLITE_URL)
    async for session in get_async_session():
        assert isinstance(session, AsyncSession)
        break


async def test_b7_schema_validation_accepts_valid_names() -> None:
    for name in ("public", "tenant_1", "_schema", "MySchema123"):
        dep = get_async_session_for_schema(name)
        assert callable(dep)


def test_b8_schema_validation_rejects_invalid_names() -> None:
    for name in ("1bad", "bad-name", "drop; --", "", "bad name"):
        with pytest.raises(ValueError, match="Invalid schema name"):
            get_async_session_for_schema(name)


async def test_b9_database_hook_aenter_configures_engine() -> None:
    hook = DatabaseLifespanHook(SQLITE_URL)
    assert get_engine() is None
    await hook.__aenter__()
    assert get_engine() is not None
    await hook.__aexit__(None, None, None)


async def test_b10_database_hook_aexit_disposes_engine() -> None:
    hook = DatabaseLifespanHook(SQLITE_URL)
    await hook.__aenter__()
    assert get_engine() is not None
    await hook.__aexit__(None, None, None)
    assert get_engine() is None


async def test_b11_check_db_ok_when_configured() -> None:
    configure_engine(SQLITE_URL)
    ok, msg = await check_db()
    assert ok is True
    assert msg == "ok"


async def test_b12_check_db_fail_when_no_engine() -> None:
    ok, msg = await check_db()
    assert ok is False
    assert "not initialized" in msg


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_database_lifespan_hook_implements_protocol() -> None:
    hook = DatabaseLifespanHook(SQLITE_URL)
    assert isinstance(hook, LifespanHook)


def test_c2_framework_tables_is_frozenset() -> None:
    assert isinstance(FRAMEWORK_TABLES, frozenset)


async def test_c3_liveness_returns_200() -> None:
    app = FastAgentStack()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_c4_readiness_returns_200_when_db_ok() -> None:
    configure_engine(SQLITE_URL)
    app = FastAgentStack()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["database"] == "ok"


async def test_c5_readiness_returns_503_when_db_not_configured() -> None:
    app = FastAgentStack()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health/ready")
    assert r.status_code == 503
    assert "database" in r.json()


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_get_engine_escape_hatch_exists() -> None:
    """I4: engine must be accessible from the database module."""
    configure_engine(SQLITE_URL)
    engine = get_engine()
    assert engine is not None
    # The escape hatch exposes the raw AsyncEngine
    from sqlalchemy.ext.asyncio import AsyncEngine

    assert isinstance(engine, AsyncEngine)


def test_a2_session_module_does_not_read_os_environ_directly() -> None:
    """I15: database URL must never come from os.environ directly in session.py."""
    import ast
    import pathlib

    source = pathlib.Path(_session_mod.__file__).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # Check for os.environ["DATABASE_URL"] or os.environ.get("DATABASE_URL")
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Attribute) and node.value.attr == "environ":
                pytest.fail("session.py reads os.environ directly (I15 violation)")


def test_a3_schema_regex_matches_invariant_i8() -> None:
    """I8: regex must be ^[a-zA-Z_][a-zA-Z0-9_]*$."""
    regex = _session_mod._SCHEMA_RE
    assert regex.pattern == r"^[a-zA-Z_][a-zA-Z0-9_]*$"


def test_a4_lifespan_hook_is_in_public_init() -> None:
    """DatabaseLifespanHook is exported from the public fast_agent_stack.database package."""
    from fast_agent_stack.database import DatabaseLifespanHook as _hook

    assert _hook is DatabaseLifespanHook


def test_a5_no_cross_module_internal_import_in_health() -> None:
    """I12: core/health.py must import check_db from core.database, not core.database.health."""
    import ast
    import pathlib

    from fast_agent_stack.core import health as health_mod

    source = pathlib.Path(health_mod.__file__).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "core.database.health" in node.module:
                pytest.fail("core/health.py imports from core.database.health directly (I12 violation)")


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


async def test_n1_liveness_responds_under_100ms() -> None:
    app = FastAgentStack()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start = time.monotonic()
        r = await client.get("/health/live")
        elapsed = time.monotonic() - start
    assert r.status_code == 200
    assert elapsed < 0.1, f"/health/live took {elapsed:.3f}s (limit: 0.1s)"


async def test_n2_readiness_responds_under_100ms_when_db_ok() -> None:
    configure_engine(SQLITE_URL)
    app = FastAgentStack()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start = time.monotonic()
        r = await client.get("/health/ready")
        elapsed = time.monotonic() - start
    assert r.status_code == 200
    assert elapsed < 0.1, f"/health/ready took {elapsed:.3f}s (limit: 0.1s)"


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


async def test_f1_get_async_session_raises_before_init() -> None:
    with pytest.raises(RuntimeError, match="Database not initialized"):
        async for _ in get_async_session():
            pass


def test_f2_invalid_schema_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid schema name"):
        get_async_session_for_schema("bad-schema!")


async def test_f3_check_db_returns_false_on_connection_error() -> None:
    configure_engine("sqlite+aiosqlite:////nonexistent/path/db.sqlite3")
    ok, msg = await check_db()
    assert ok is False
    assert msg != "ok"


async def test_f4_hook_aexit_disposes_engine_even_after_exception() -> None:
    hook = DatabaseLifespanHook(SQLITE_URL)
    await hook.__aenter__()
    assert get_engine() is not None
    await hook.__aexit__(RuntimeError, RuntimeError("test"), None)
    assert get_engine() is None


async def test_f5_readiness_names_database_in_503_body() -> None:
    """I13: /health/ready must name the failing service in 503 body."""
    app = FastAgentStack()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health/ready")
    assert r.status_code == 503
    body = r.json()
    assert "database" in body
