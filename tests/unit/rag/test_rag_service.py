"""Unit tests for 5-E: RagService, RagChunk, IngestResult."""
from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from fast_agent_stack.core.ai.rag import (
    ChunkingStrategy, IngestResult, RagChunk, RagService, UnsupportedFileTypeError,
)
from fast_agent_stack.core.vector import VectorSearchResult


def _make_mock_embedding(dims: int = 4) -> MagicMock:
    emb = MagicMock()
    emb.dimensions = dims
    emb.embed = AsyncMock(return_value=[0.0] * dims)
    emb.embed_batch = AsyncMock(side_effect=lambda texts: [[0.0] * dims for _ in texts])
    return emb


def _make_mock_vector_store(search_return: list | None = None) -> MagicMock:
    vs = MagicMock()
    vs.upsert = AsyncMock()
    vs.search = AsyncMock(return_value=search_return or [])
    vs.delete = AsyncMock()
    vs.close = AsyncMock()
    return vs


# ---------------------------------------------------------------------------
# CONTRACT
# ---------------------------------------------------------------------------

def test_rag_chunk_is_frozen_dataclass():
    chunk = RagChunk(content="x", score=0.5, metadata={}, document_id="d", chunk_index=0)
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        chunk.score = 0.0  # type: ignore[misc]


def test_ingest_result_is_frozen_dataclass():
    result = IngestResult(document_id="d", chunks_stored=1, collection="c")
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        result.chunks_stored = 99  # type: ignore[misc]


async def test_rag_ingest_return_type():
    svc = RagService(_make_mock_embedding(), _make_mock_vector_store())
    result = await svc.ingest("col", "hello world", document_id="d1")
    assert isinstance(result, IngestResult)


async def test_rag_retrieve_return_type():
    hit = VectorSearchResult(
        id="doc1:0", score=0.9,
        metadata={"_chunk_count": 1, "_chunk_index": 0, "_document_id": "doc1"},
        content="hello",
    )
    svc = RagService(_make_mock_embedding(), _make_mock_vector_store(search_return=[hit]))
    result = await svc.retrieve("col", "query")
    assert isinstance(result, list)
    assert all(isinstance(c, RagChunk) for c in result)


# ---------------------------------------------------------------------------
# BEHAVIOR
# ---------------------------------------------------------------------------

async def test_rag_ingest_creates_correct_chunk_count():
    # 1 short text → 1 chunk
    svc = RagService(_make_mock_embedding(), _make_mock_vector_store())
    result = await svc.ingest("col", "short text", document_id="d1")
    assert isinstance(result, IngestResult)
    assert result.document_id == "d1"
    assert result.collection == "col"
    assert result.chunks_stored == 1


async def test_rag_chunk_ids_follow_document_id_colon_chunk_index_format():
    vs = _make_mock_vector_store()
    svc = RagService(_make_mock_embedding(), vs)
    # Use text long enough for 3 chunks: 3 * 512*4 chars with no overlap issue
    text = "X" * (512 * 4 * 2 + 100)  # slightly over 2 windows → 3 chunks
    result = await svc.ingest("col", text, document_id="doc99")
    call_ids = [c.kwargs.get("id") or c.args[1] for c in vs.upsert.call_args_list]
    for i, cid in enumerate(call_ids):
        assert cid == f"doc99:{i}"


async def test_rag_retrieve_embed_and_search_called_once():
    hit = VectorSearchResult(
        id="doc1:0", score=0.9,
        metadata={"_chunk_count": 1, "_chunk_index": 0, "_document_id": "doc1"},
        content="hello",
    )
    emb = _make_mock_embedding()
    vs = _make_mock_vector_store(search_return=[hit])
    svc = RagService(emb, vs)
    chunks = await svc.retrieve("col", "query text", top_k=5)
    emb.embed.assert_called_once_with("query text")
    vs.search.assert_called_once()
    assert len(chunks) == 1
    assert chunks[0].document_id == "doc1"
    assert chunks[0].chunk_index == 0


async def test_rag_retrieve_passes_filter_to_vector_search():
    vs = _make_mock_vector_store()
    svc = RagService(_make_mock_embedding(), vs)
    await svc.retrieve("col", "query", top_k=5, filter={"lang": "en"})
    call_kwargs = vs.search.call_args.kwargs
    assert call_kwargs.get("filter") == {"lang": "en"}
    assert call_kwargs.get("top_k") == 5


async def test_rag_delete_document_deletes_all_chunks():
    hit = VectorSearchResult(
        id="docA:0", score=0.0,
        metadata={"_chunk_count": 3, "_chunk_index": 0, "_document_id": "docA"},
        content="c",
    )
    vs = _make_mock_vector_store(search_return=[hit])
    svc = RagService(_make_mock_embedding(4), vs)
    count = await svc.delete_document("col", "docA")
    assert count == 3
    delete_calls = [c.args[1] for c in vs.delete.call_args_list]
    assert "docA:0" in delete_calls
    assert "docA:1" in delete_calls
    assert "docA:2" in delete_calls


async def test_rag_delete_document_returns_zero_when_not_found():
    vs = _make_mock_vector_store(search_return=[])
    svc = RagService(_make_mock_embedding(), vs)
    count = await svc.delete_document("col", "missing")
    assert count == 0
    vs.delete.assert_not_called()


async def test_rag_ingest_file_eml_dispatches_extraction():
    eml_bytes = (
        b"From: a@b.com\r\n"
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"Hello from email"
    )
    vs = _make_mock_vector_store()
    svc = RagService(_make_mock_embedding(), vs)
    result = await svc.ingest_file(
        "col", eml_bytes,
        filename="msg.eml", content_type="message/rfc822",
        document_id="d5",
    )
    assert isinstance(result, IngestResult)
    assert result.chunks_stored >= 1


async def test_rag_ingest_file_text_plain_uses_text_directly():
    vs = _make_mock_vector_store()
    emb = _make_mock_embedding()
    svc = RagService(emb, vs)
    result = await svc.ingest_file(
        "col", b"plain text content",
        filename="readme.txt", content_type="text/plain",
        document_id="d3",
    )
    assert isinstance(result, IngestResult)
    assert result.chunks_stored >= 1


async def test_rag_ingest_file_unsupported_content_type_raises():
    svc = RagService(_make_mock_embedding(), _make_mock_vector_store())
    with pytest.raises(UnsupportedFileTypeError):
        await svc.ingest_file(
            "col", b"binary",
            filename="blob.bin", content_type="application/octet-stream",
            document_id="d6",
        )


async def test_rag_ingest_stores_chunk_count_in_metadata():
    vs = _make_mock_vector_store()
    svc = RagService(_make_mock_embedding(), vs)
    await svc.ingest("col", "hello world", document_id="d1")
    upsert_call = vs.upsert.call_args
    metadata_arg = upsert_call.kwargs.get("metadata")
    if metadata_arg is None and len(upsert_call.args) > 3:
        metadata_arg = upsert_call.args[3]
    assert metadata_arg is not None
    assert "_chunk_count" in metadata_arg


# ---------------------------------------------------------------------------
# ARCHITECTURAL — I12: RAG only imports from public __init__
# ---------------------------------------------------------------------------

def test_rag_module_imports_only_from_public_inits_i12():
    import fast_agent_stack.core.ai.rag as rag_mod
    rag_dir = Path(rag_mod.__file__).parent
    forbidden_prefixes = [
        "fast_agent_stack.core.ai.embedding.backends",
        "fast_agent_stack.core.vector.backends",
        "fast_agent_stack.core.ai.extraction.backends",
    ]
    for py_file in rag_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for prefix in forbidden_prefixes:
                        assert not node.module.startswith(prefix), (
                            f"{py_file.name} imports from internal module {node.module!r} "
                            f"(I12 violation)"
                        )
