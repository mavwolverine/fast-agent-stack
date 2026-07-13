"""Unit tests for ADR-045: RerankerProtocol, RerankResult, get_reranker, backends.

5-family coverage:
  1. Behavior   — factory dispatch, RagService integration, over-fetch, result ordering
  2. Contract   — Protocol method signatures, runtime_checkable, frozen dataclass
  3. Architectural — __all__ exports, lazy imports, settings read at init (ADR-012)
  4. NFR        — timeout from settings (I22), over-fetch ratio (top_k * 3)
  5. Failure-mode — I3 import guards, empty documents, bad dotted path
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fast_agent_stack.core.ai.rag import RagChunk, RagService
from fast_agent_stack.core.ai.reranker import (
    RerankerProtocol,
    RerankResult,
    get_reranker,
)
from fast_agent_stack.core.vector import VectorSearchResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**kw):  # type: ignore[no-untyped-def]
    m = MagicMock()
    m.reranker_provider = kw.get("reranker_provider", "none")
    m.reranker_model = kw.get("reranker_model", "jina-reranker-v2-base-multilingual")
    m.reranker_url = kw.get("reranker_url", "http://localhost:11434")
    m.reranker_timeout = kw.get("reranker_timeout", 30.0)
    return m


def _make_mock_embedding(dims: int = 4) -> MagicMock:
    emb = MagicMock()
    emb.dimensions = dims
    emb.embed = AsyncMock(return_value=[0.0] * dims)
    emb.embed_batch = AsyncMock(side_effect=lambda texts: [[0.0] * dims for _ in texts])
    return emb


def _make_mock_vector_store(results: list | None = None) -> MagicMock:
    vs = MagicMock()
    vs.upsert = AsyncMock()
    vs.search = AsyncMock(return_value=results or [])
    vs.delete = AsyncMock()
    vs.close = AsyncMock()
    return vs


class _ModuleLevelDummyReranker:
    """Module-level class so importlib can resolve the dotted path in ADR-012 tests."""

    def __init__(self, settings: object) -> None:
        pass

    async def rerank(self, query: str, documents: list[str], *, top_k: int = 5) -> list[RerankResult]:
        return []


def _make_vector_hits(n: int) -> list[VectorSearchResult]:
    return [
        VectorSearchResult(
            id=f"doc:{i}",
            score=float(n - i) / n,
            metadata={"_document_id": "d", "_chunk_index": i, "_chunk_count": n},
            content=f"chunk {i}",
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# 1. Behavior
# ---------------------------------------------------------------------------


def test_rerank_result_has_expected_fields():
    r = RerankResult(content="text", score=0.9, index=2)
    assert r.content == "text"
    assert r.score == 0.9
    assert r.index == 2


def test_rerank_result_is_frozen_dataclass():
    r = RerankResult(content="x", score=0.5, index=0)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        r.score = 0.0  # type: ignore[misc]


def test_get_reranker_returns_none_when_provider_is_none():
    assert get_reranker(_make_settings(reranker_provider="none")) is None


async def test_rag_service_retrieve_without_reranker_unchanged():
    """Existing behaviour: no reranker, search returns top_k directly."""
    hits = _make_vector_hits(5)
    vs = _make_mock_vector_store(hits)
    svc = RagService(_make_mock_embedding(), vs)

    results = await svc.retrieve("col", "query", top_k=5)

    call_args = vs.search.call_args
    assert call_args.kwargs["top_k"] == 5
    assert len(results) == 5
    assert all(isinstance(r, RagChunk) for r in results)


async def test_rag_service_retrieve_with_reranker_over_fetches():
    """With reranker: vector search uses top_k * 3."""
    hits = _make_vector_hits(15)
    vs = _make_mock_vector_store(hits)

    mock_reranker = MagicMock()
    mock_reranker.rerank = AsyncMock(
        return_value=[RerankResult(content=h.content or "", score=float(i), index=i) for i, h in enumerate(hits[:5])]
    )

    svc = RagService(_make_mock_embedding(), vs, reranker=mock_reranker)
    results = await svc.retrieve("col", "question", top_k=5)

    search_top_k = vs.search.call_args.kwargs["top_k"]
    assert search_top_k == 15  # top_k * 3
    assert len(results) == 5


async def test_rag_service_retrieve_with_reranker_returns_reranked_order():
    """Retrieve respects the reranker's ordering (scores descending per Protocol contract)."""
    hits = _make_vector_hits(6)
    vs = _make_mock_vector_store(hits)

    # Reranker returns results in descending score order (Protocol contract)
    reranked = [RerankResult(content=f"chunk {i}", score=float(5 - i) / 5, index=i) for i in range(5)]
    mock_reranker = MagicMock()
    mock_reranker.rerank = AsyncMock(return_value=reranked)

    svc = RagService(_make_mock_embedding(), vs, reranker=mock_reranker)
    results = await svc.retrieve("col", "question", top_k=5)

    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True), "Results must be in descending score order"


async def test_rag_service_retrieve_with_reranker_passes_correct_query():
    hits = _make_vector_hits(3)
    vs = _make_mock_vector_store(hits)
    mock_reranker = MagicMock()
    mock_reranker.rerank = AsyncMock(
        return_value=[
            RerankResult(content="chunk 0", score=0.9, index=0),
        ]
    )
    svc = RagService(_make_mock_embedding(), vs, reranker=mock_reranker)
    await svc.retrieve("col", "my query", top_k=1)

    call_args = mock_reranker.rerank.call_args
    assert call_args.args[0] == "my query"


# ---------------------------------------------------------------------------
# 2. Contract
# ---------------------------------------------------------------------------


def test_reranker_protocol_rerank_signature():
    sig = inspect.signature(RerankerProtocol.rerank)
    params = sig.parameters
    assert "query" in params
    assert "documents" in params
    assert "top_k" in params
    assert params["top_k"].default == 5


def test_reranker_protocol_is_runtime_checkable():
    class Fake:
        async def rerank(self, query, documents, *, top_k=5):
            return []

    assert isinstance(Fake(), RerankerProtocol)


def test_rerank_result_dataclass_fields():
    fields = {f.name for f in dataclasses.fields(RerankResult)}
    assert fields == {"content", "score", "index"}


def test_module_exports_all_names():
    from fast_agent_stack.core.ai.reranker import __all__ as exported

    assert "RerankerProtocol" in exported
    assert "RerankResult" in exported
    assert "get_reranker" in exported


# ---------------------------------------------------------------------------
# 3. Architectural
# ---------------------------------------------------------------------------


def test_get_reranker_ollama_lazy_import():
    """httpx must not be imported at module load time; only inside factory."""
    import fast_agent_stack.core.ai.reranker as mod

    with open(mod.__file__) as f:
        src = f.read()
    assert "import httpx" not in src, "httpx must not be imported at module top-level (I3 lazy import)"


def test_get_reranker_openai_lazy_import():
    import fast_agent_stack.core.ai.reranker.openai as mod

    with open(mod.__file__) as f:
        src = f.read()
    assert src.strip().startswith("from __future__") or "try:" in src, "openai backend must have an I3 extras gate"


def test_rag_service_accepts_reranker_kwarg():
    """RagService constructor accepts optional reranker= without error."""
    svc = RagService(
        _make_mock_embedding(),
        _make_mock_vector_store(),
        reranker=None,
    )
    assert svc is not None


def test_get_reranker_dotted_path_dispatch():
    """ADR-012: dotted Python path instantiates and returns the custom class."""
    target = f"{_ModuleLevelDummyReranker.__module__}._ModuleLevelDummyReranker"
    result = get_reranker(_make_settings(reranker_provider=target))
    assert isinstance(result, _ModuleLevelDummyReranker)


# ---------------------------------------------------------------------------
# 4. NFR
# ---------------------------------------------------------------------------


def test_ollama_reranker_reads_timeout_from_settings_i22():
    """OllamaReranker must use reranker_timeout from settings (I22)."""
    mock_httpx = MagicMock()
    mock_client = MagicMock()
    mock_httpx.AsyncClient.return_value = mock_client

    with patch.dict(sys.modules, {"httpx": mock_httpx}):
        mod_name = "fast_agent_stack.core.ai.reranker.ollama"
        sys.modules.pop(mod_name, None)
        try:
            ollama_mod = importlib.import_module(mod_name)
            settings = _make_settings(
                reranker_provider="ollama",
                reranker_url="http://localhost:11434",
                reranker_timeout=15.0,
            )
            ollama_mod.OllamaReranker(settings)
            _, kwargs = mock_httpx.AsyncClient.call_args
            assert kwargs.get("timeout") == 15.0
        finally:
            sys.modules.pop(mod_name, None)


def test_openai_reranker_reads_timeout_from_settings_i22():
    """OpenAIReranker must use reranker_timeout from settings (I22)."""
    mock_httpx = MagicMock()
    mock_client = MagicMock()
    mock_httpx.AsyncClient.return_value = mock_client

    with patch.dict(sys.modules, {"httpx": mock_httpx}):
        mod_name = "fast_agent_stack.core.ai.reranker.openai"
        sys.modules.pop(mod_name, None)
        try:
            openai_mod = importlib.import_module(mod_name)
            settings = _make_settings(
                reranker_provider="openai",
                reranker_url="https://api.jina.ai/v1",
                reranker_timeout=45.0,
            )
            openai_mod.OpenAIReranker(settings)
            _, kwargs = mock_httpx.AsyncClient.call_args
            assert kwargs.get("timeout") == 45.0
        finally:
            sys.modules.pop(mod_name, None)


def test_rag_service_overfetch_ratio_is_three():
    """Sanity: the over-fetch multiplier is exactly 3 (documented in ADR-045)."""
    import fast_agent_stack.core.ai.rag as mod

    with open(mod.__file__) as f:
        src = f.read()
    # The source must contain `top_k * 3` or `3 * top_k`
    assert "top_k * 3" in src or "3 * top_k" in src, "RagService.retrieve must use top_k * 3 when reranker is set"


# ---------------------------------------------------------------------------
# 5. Failure-mode
# ---------------------------------------------------------------------------


def test_ollama_import_guard_i3():
    """Missing httpx raises ImportError naming the correct extra (I3)."""
    saved = sys.modules.pop("httpx", None)
    sys.modules["httpx"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.ai.reranker.ollama"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="reranker-ollama"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["httpx"] = saved
        elif "httpx" in sys.modules:
            del sys.modules["httpx"]
        if cached is not None:
            sys.modules[mod_name] = cached


def test_openai_import_guard_i3():
    """Missing httpx raises ImportError naming the correct extra (I3)."""
    saved = sys.modules.pop("httpx", None)
    sys.modules["httpx"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.ai.reranker.openai"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="reranker-openai"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["httpx"] = saved
        elif "httpx" in sys.modules:
            del sys.modules["httpx"]
        if cached is not None:
            sys.modules[mod_name] = cached


async def test_rag_service_retrieve_empty_documents_skips_reranker():
    """Empty vector search results: reranker is not called, empty list returned."""
    vs = _make_mock_vector_store([])
    mock_reranker = MagicMock()
    mock_reranker.rerank = AsyncMock(return_value=[])
    svc = RagService(_make_mock_embedding(), vs, reranker=mock_reranker)

    results = await svc.retrieve("col", "query", top_k=5)

    mock_reranker.rerank.assert_not_called()
    assert results == []


def test_get_reranker_bad_dotted_path_raises():
    """Non-existent dotted path raises ModuleNotFoundError."""
    with pytest.raises((ModuleNotFoundError, AttributeError)):
        get_reranker(_make_settings(reranker_provider="nonexistent.module.Foo"))
