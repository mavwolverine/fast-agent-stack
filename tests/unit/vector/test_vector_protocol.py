"""Unit tests for 5-B: vector store protocol, types, factory dispatch, and invariants."""
from __future__ import annotations

import dataclasses
import importlib
import sys
from unittest.mock import MagicMock

import pytest

from fast_agent_stack.core.vector import (
    CollectionNotFoundError,
    VectorSearchResult,
    VectorStoreProtocol,
    get_vector_store,
)


def _make_settings(**kwargs):  # type: ignore[no-untyped-def]
    m = MagicMock()
    m.vector_db = kwargs.get("vector_db", "qdrant")
    m.qdrant_url = kwargs.get("qdrant_url", "http://localhost:6333")
    m.qdrant_api_key = kwargs.get("qdrant_api_key", None)
    m.pgvector_collection_schema = kwargs.get("pgvector_collection_schema", "public")
    m.opensearch_url = kwargs.get("opensearch_url", "http://localhost:9200")
    m.opensearch_username = kwargs.get("opensearch_username", None)
    m.opensearch_password = kwargs.get("opensearch_password", None)
    m.weaviate_url = kwargs.get("weaviate_url", "http://localhost:8080")
    m.weaviate_api_key = kwargs.get("weaviate_api_key", None)
    m.vector_timeout = kwargs.get("vector_timeout", 30.0)
    m.pgvector_database_url = kwargs.get(
        "pgvector_database_url", "postgresql+asyncpg://localhost/test"
    )
    return m


# ---------------------------------------------------------------------------
# CONTRACT
# ---------------------------------------------------------------------------

def test_vector_search_result_is_frozen_dataclass():
    result = VectorSearchResult(id="x", score=0.9, metadata={"k": "v"}, content=None)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        result.score = 0.0  # type: ignore[misc]


def test_vector_search_result_content_optional():
    result = VectorSearchResult(id="x", score=0.9, metadata={}, content=None)
    assert result.content is None


def test_vector_search_result_fields():
    fields = {f.name: f for f in dataclasses.fields(VectorSearchResult)}
    assert set(fields.keys()) == {"id", "score", "metadata", "content"}


def test_collection_not_found_error_is_exception():
    assert isinstance(CollectionNotFoundError(), Exception)


def test_vector_module_public_init_exports():
    from fast_agent_stack.core.vector import (
        CollectionNotFoundError,
        VectorSearchResult,
        VectorStoreProtocol,
        get_vector_store,
    )
    assert callable(get_vector_store)
    assert isinstance(VectorStoreProtocol, type)
    assert issubclass(CollectionNotFoundError, Exception)


# ---------------------------------------------------------------------------
# BEHAVIOR — factory dispatch
# ---------------------------------------------------------------------------

def test_get_vector_store_dotted_path_dispatch():
    """ADR-012: dotted path should import and instantiate the class."""
    pytest.importorskip("qdrant_client")
    settings = _make_settings(
        vector_db="fast_agent_stack.core.vector.backends.qdrant.QdrantStore"
    )
    from fast_agent_stack.core.vector.backends.qdrant import QdrantStore
    backend = get_vector_store(settings)
    assert isinstance(backend, QdrantStore)


# ---------------------------------------------------------------------------
# ARCHITECTURAL — I4 attribute presence
# ---------------------------------------------------------------------------

def test_qdrant_store_exposes_client_attribute_i4():
    pytest.importorskip("qdrant_client")
    settings = _make_settings(vector_db="qdrant")
    from fast_agent_stack.core.vector.backends.qdrant import QdrantStore
    store = QdrantStore(settings)
    assert hasattr(store, "_client")


def test_pgvector_store_exposes_client_attribute_i4():
    from unittest.mock import patch
    pytest.importorskip("pgvector")
    settings = _make_settings(vector_db="pgvector")
    from fast_agent_stack.core.vector.backends.pgvector import PgVectorStore
    with patch("fast_agent_stack.core.vector.backends.pgvector.create_async_engine"):
        store = PgVectorStore(settings)
    assert hasattr(store, "_client")


# ---------------------------------------------------------------------------
# FAILURE-MODE — I3 import guards
# ---------------------------------------------------------------------------

def test_qdrant_store_import_guard_i3():
    saved = sys.modules.pop("qdrant_client", None)
    for k in list(sys.modules):
        if k.startswith("qdrant_client"):
            sys.modules.pop(k, None)
    sys.modules["qdrant_client"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.vector.backends.qdrant"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[vector-qdrant\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["qdrant_client"] = saved
        elif "qdrant_client" in sys.modules:
            del sys.modules["qdrant_client"]
        if cached is not None:
            sys.modules[mod_name] = cached


def test_pgvector_store_import_guard_i3():
    saved = sys.modules.pop("pgvector", None)
    sys.modules["pgvector"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.vector.backends.pgvector"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[vector-pgvector\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["pgvector"] = saved
        elif "pgvector" in sys.modules:
            del sys.modules["pgvector"]
        if cached is not None:
            sys.modules[mod_name] = cached


def test_opensearch_store_import_guard_i3():
    saved = sys.modules.pop("opensearchpy", None)
    sys.modules["opensearchpy"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.vector.backends.opensearch"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[vector-opensearch\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["opensearchpy"] = saved
        elif "opensearchpy" in sys.modules:
            del sys.modules["opensearchpy"]
        if cached is not None:
            sys.modules[mod_name] = cached


def test_weaviate_store_import_guard_i3():
    saved = sys.modules.pop("weaviate", None)
    sys.modules["weaviate"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.vector.backends.weaviate"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[vector-weaviate\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["weaviate"] = saved
        elif "weaviate" in sys.modules:
            del sys.modules["weaviate"]
        if cached is not None:
            sys.modules[mod_name] = cached
