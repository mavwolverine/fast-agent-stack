"""Unit tests for PgVectorStore — 5 families (B/C/A/N/F).

All tests mock the SQLAlchemy AsyncEngine so no real PostgreSQL server is needed.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pgvector")

from fast_agent_stack.core.vector import CollectionNotFoundError, VectorSearchResult
from fast_agent_stack.core.vector.backends.pgvector import (
    PgVectorStore,
    _normalise_db_url,
    _validate_name,
    _vec_literal,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**kwargs: Any) -> MagicMock:
    m = MagicMock()
    m.pgvector_database_url = kwargs.get("pgvector_database_url", "postgresql+asyncpg://localhost/test")
    m.pgvector_collection_schema = kwargs.get("pgvector_collection_schema", "public")
    m.vector_timeout = kwargs.get("vector_timeout", 30.0)
    return m


def _make_conn_result(*rows: dict[str, Any]) -> MagicMock:
    """Build a mock SQLAlchemy result with fetchall() returning Row-like objects."""
    mock_rows = []
    for row in rows:
        r = MagicMock()
        for k, v in row.items():
            setattr(r, k, v)
        mock_rows.append(r)
    result = MagicMock()
    result.fetchall.return_value = mock_rows
    return result


@pytest.fixture
def engine_and_conn():
    """Returns (mock_engine, mock_conn) with begin()/connect() context managers wired up."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))

    # begin() context manager
    ctx_begin = MagicMock()
    ctx_begin.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx_begin.__aexit__ = AsyncMock(return_value=False)

    # connect() context manager
    ctx_connect = MagicMock()
    ctx_connect.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx_connect.__aexit__ = AsyncMock(return_value=False)

    mock_engine = MagicMock()
    mock_engine.begin = MagicMock(return_value=ctx_begin)
    mock_engine.connect = MagicMock(return_value=ctx_connect)
    mock_engine.dispose = AsyncMock()

    return mock_engine, mock_conn


@pytest.fixture
def store(engine_and_conn):
    mock_engine, mock_conn = engine_and_conn
    settings = _make_settings()
    with patch(
        "fast_agent_stack.core.vector.backends.pgvector.create_async_engine",
        return_value=mock_engine,
    ):
        s = PgVectorStore(settings)
    return s, mock_conn


# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


async def test_b1_create_collection_executes_extension_and_table(store):
    pg, conn = store
    await pg.create_collection("docs", 384, distance_metric="cosine")

    calls = [str(c.args[0]) for c in conn.execute.call_args_list]
    assert any("CREATE EXTENSION" in c and "vector" in c for c in calls)
    assert any("CREATE TABLE" in c and "docs" in c for c in calls)
    assert any("vector(384)" in c for c in calls)


async def test_b2_upsert_sends_insert_on_conflict(store):
    pg, conn = store
    await pg.upsert("docs", "id-1", [0.1, 0.2, 0.3], {"tag": "x"}, content="hello")

    call_sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
    assert any("INSERT INTO" in s and "docs" in s for s in call_sqls)
    assert any("ON CONFLICT" in s for s in call_sqls)


async def test_b3_upsert_embeds_vector_literal(store):
    pg, conn = store
    await pg.upsert("docs", "id-1", [1.0, 2.0, 3.0], {})

    call_sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
    assert any("[1.0,2.0,3.0]" in s for s in call_sqls)


async def test_b4_search_returns_results(engine_and_conn):
    mock_engine, mock_conn = engine_and_conn
    mock_conn.execute = AsyncMock(
        return_value=_make_conn_result(
            {"id": "abc", "score": 0.95, "content": "hello", "metadata": {"tag": "x"}},
        )
    )
    settings = _make_settings()
    with patch(
        "fast_agent_stack.core.vector.backends.pgvector.create_async_engine",
        return_value=mock_engine,
    ):
        pg = PgVectorStore(settings)

    results = await pg.search("docs", [0.1, 0.2, 0.3], top_k=5)

    assert len(results) == 1
    assert results[0].id == "abc"
    assert results[0].score == pytest.approx(0.95)
    assert results[0].content == "hello"
    assert results[0].metadata == {"tag": "x"}


async def test_b5_search_applies_filter_as_jsonb_containment(store):
    pg, conn = store
    await pg.search("docs", [0.1, 0.2], top_k=3, filter={"tag": "news"})

    call_sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
    assert any("@>" in s for s in call_sqls)
    # verify filter JSON is passed as a parameter
    call_params = [c.args[1] if len(c.args) > 1 else {} for c in conn.execute.call_args_list]
    assert any("meta" in p and json.loads(p["meta"]) == {"tag": "news"} for p in call_params)


async def test_b6_delete_sends_delete_sql(store):
    pg, conn = store
    await pg.delete("docs", "id-99")

    call_sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
    assert any("DELETE FROM" in s and "docs" in s for s in call_sqls)


async def test_b7_delete_is_idempotent_for_missing_rows(store):
    """delete() must not raise when the row doesn't exist (no error from missing rows)."""
    pg, conn = store
    conn.execute = AsyncMock(return_value=MagicMock(rowcount=0))
    await pg.delete("docs", "nonexistent")  # must not raise


async def test_b8_close_disposes_engine(engine_and_conn):
    mock_engine, _ = engine_and_conn
    settings = _make_settings()
    with patch(
        "fast_agent_stack.core.vector.backends.pgvector.create_async_engine",
        return_value=mock_engine,
    ):
        pg = PgVectorStore(settings)
    await pg.close()
    mock_engine.dispose.assert_called_once()


async def test_b9_create_collection_is_idempotent(store):
    """IF NOT EXISTS means calling create_collection twice must not raise."""
    pg, conn = store
    await pg.create_collection("docs", 384)
    await pg.create_collection("docs", 384)
    assert conn.execute.call_count >= 2  # called at least once per invocation


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_implements_vector_store_protocol():
    from fast_agent_stack.core.vector import VectorStoreProtocol

    settings = _make_settings()
    with patch("fast_agent_stack.core.vector.backends.pgvector.create_async_engine"):
        store = PgVectorStore(settings)

    assert isinstance(store, VectorStoreProtocol)


def test_c2_client_is_async_engine_i4():
    """I4: _client must be the AsyncEngine for user escape hatch."""
    from sqlalchemy.ext.asyncio import AsyncEngine

    settings = _make_settings()
    with patch("fast_agent_stack.core.vector.backends.pgvector.create_async_engine") as mock_cae:
        mock_engine = MagicMock(spec=AsyncEngine)
        mock_cae.return_value = mock_engine
        store = PgVectorStore(settings)

    assert store._client is mock_engine


async def test_c3_search_returns_vector_search_result_instances(engine_and_conn):
    mock_engine, mock_conn = engine_and_conn
    mock_conn.execute = AsyncMock(
        return_value=_make_conn_result(
            {"id": "x", "score": 0.8, "content": None, "metadata": {}},
        )
    )
    settings = _make_settings()
    with patch(
        "fast_agent_stack.core.vector.backends.pgvector.create_async_engine",
        return_value=mock_engine,
    ):
        pg = PgVectorStore(settings)

    results = await pg.search("docs", [0.1, 0.2])
    assert all(isinstance(r, VectorSearchResult) for r in results)


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_i3_import_guard():
    import importlib
    import sys

    mod_name = "fast_agent_stack.core.vector.backends.pgvector"
    saved_mod = sys.modules.get(mod_name)
    saved_pgvector = sys.modules.get("pgvector")

    sys.modules["pgvector"] = None  # type: ignore[assignment]
    sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[vector-pgvector\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        # Restore pgvector sentinel
        if saved_pgvector is not None:
            sys.modules["pgvector"] = saved_pgvector
        else:
            sys.modules.pop("pgvector", None)
        # Restore the module object so later patch() calls target the same module
        # that PgVectorStore was imported from.  Without this, patch() reimports
        # the module, creating a second copy whose create_async_engine is patched
        # while PgVectorStore still calls the original binding — causing real
        # connections to be attempted.
        if saved_mod is not None:
            sys.modules[mod_name] = saved_mod


def test_a2_name_validation_blocks_sql_injection():
    with pytest.raises(ValueError, match="Invalid"):
        _validate_name("foo; DROP TABLE bar")
    with pytest.raises(ValueError, match="Invalid"):
        _validate_name("1starts_with_digit")
    with pytest.raises(ValueError, match="Invalid"):
        _validate_name("foo-bar")
    with pytest.raises(ValueError, match="Invalid"):
        _validate_name("")


def test_a3_name_validation_allows_valid_names():
    _validate_name("my_collection")
    _validate_name("Collection123")
    _validate_name("_private")
    _validate_name("a")


async def test_a4_upsert_validates_collection_name():
    settings = _make_settings()
    with patch("fast_agent_stack.core.vector.backends.pgvector.create_async_engine"):
        pg = PgVectorStore(settings)

    with pytest.raises(ValueError, match="Invalid"):
        await pg.upsert("bad-name!", "id", [1.0], {})


async def test_a5_search_validates_collection_name():
    settings = _make_settings()
    with patch("fast_agent_stack.core.vector.backends.pgvector.create_async_engine"):
        pg = PgVectorStore(settings)

    with pytest.raises(ValueError, match="Invalid"):
        await pg.search("bad name", [1.0])


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


def test_n1_url_normalisation_adds_asyncpg_driver():
    assert _normalise_db_url("postgresql://host/db") == "postgresql+asyncpg://host/db"
    assert _normalise_db_url("postgres://host/db") == "postgresql+asyncpg://host/db"
    assert _normalise_db_url("postgresql+asyncpg://host/db") == "postgresql+asyncpg://host/db"


def test_n2_vec_literal_formats_correctly():
    assert _vec_literal([1.0, 2.0, 3.0]) == "[1.0,2.0,3.0]"
    assert _vec_literal([]) == "[]"
    assert _vec_literal([0.1]) == "[0.1]"


async def test_n3_search_uses_cosine_distance_operator(store):
    pg, conn = store
    await pg.search("docs", [0.1, 0.2])
    call_sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
    assert any("<=>" in s for s in call_sqls)


async def test_n4_search_score_is_one_minus_distance(store):
    """Score column must use 1 - (embedding <=> ...) so 1.0 = identical."""
    pg, conn = store
    await pg.search("docs", [0.0])
    call_sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
    assert any("1 -" in s and "<=>" in s for s in call_sqls)


def test_n5_create_engine_called_with_asyncpg_url():
    settings = _make_settings(pgvector_database_url="postgresql://localhost/test")
    with patch("fast_agent_stack.core.vector.backends.pgvector.create_async_engine") as mock_cae:
        mock_cae.return_value = MagicMock()
        PgVectorStore(settings)

    called_url = mock_cae.call_args.args[0]
    assert called_url.startswith("postgresql+asyncpg://")


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


def test_f1_missing_database_url_raises_runtime_error():
    settings = _make_settings(pgvector_database_url=None)
    with pytest.raises(RuntimeError, match="pgvector_database_url"):
        with patch("fast_agent_stack.core.vector.backends.pgvector.create_async_engine"):
            PgVectorStore(settings)


def test_f2_invalid_schema_name_raises_at_init():
    settings = _make_settings(pgvector_collection_schema="bad schema!")
    with pytest.raises(ValueError, match="Invalid"):
        with patch("fast_agent_stack.core.vector.backends.pgvector.create_async_engine"):
            PgVectorStore(settings)


async def test_f3_upsert_raises_collection_not_found_on_missing_table(engine_and_conn):
    mock_engine, mock_conn = engine_and_conn
    mock_conn.execute = AsyncMock(side_effect=Exception('relation "public"."docs" does not exist'))
    settings = _make_settings()
    with patch(
        "fast_agent_stack.core.vector.backends.pgvector.create_async_engine",
        return_value=mock_engine,
    ):
        pg = PgVectorStore(settings)

    with pytest.raises(CollectionNotFoundError):
        await pg.upsert("docs", "id", [1.0], {})


async def test_f4_search_raises_collection_not_found_on_missing_table(engine_and_conn):
    mock_engine, mock_conn = engine_and_conn
    mock_conn.execute = AsyncMock(side_effect=Exception("relation does not exist"))
    settings = _make_settings()
    with patch(
        "fast_agent_stack.core.vector.backends.pgvector.create_async_engine",
        return_value=mock_engine,
    ):
        pg = PgVectorStore(settings)

    with pytest.raises(CollectionNotFoundError):
        await pg.search("docs", [1.0])


async def test_f5_delete_raises_collection_not_found_on_missing_table(engine_and_conn):
    mock_engine, mock_conn = engine_and_conn
    mock_conn.execute = AsyncMock(side_effect=Exception("table does not exist"))
    settings = _make_settings()
    with patch(
        "fast_agent_stack.core.vector.backends.pgvector.create_async_engine",
        return_value=mock_engine,
    ):
        pg = PgVectorStore(settings)

    with pytest.raises(CollectionNotFoundError):
        await pg.delete("docs", "id")


async def test_f6_other_db_errors_propagate_unchanged(engine_and_conn):
    mock_engine, mock_conn = engine_and_conn
    mock_conn.execute = AsyncMock(side_effect=Exception("permission denied for table docs"))
    settings = _make_settings()
    with patch(
        "fast_agent_stack.core.vector.backends.pgvector.create_async_engine",
        return_value=mock_engine,
    ):
        pg = PgVectorStore(settings)

    with pytest.raises(Exception, match="permission denied"):
        await pg.upsert("docs", "id", [1.0], {})


async def test_f7_unsupported_distance_metric_raises_value_error(store):
    pg, _ = store
    with pytest.raises(ValueError, match="Unsupported distance_metric"):
        await pg.create_collection("docs", 384, distance_metric="hamming")
