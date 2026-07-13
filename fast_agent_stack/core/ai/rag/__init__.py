from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from fast_agent_stack.core.ai.embedding import EmbeddingProtocol
from fast_agent_stack.core.ai.extraction import get_extractor
from fast_agent_stack.core.ai.rag.chunking import fixed_chunker, paragraph_chunker
from fast_agent_stack.core.vector import VectorSearchResult, VectorStoreProtocol

if TYPE_CHECKING:
    from fast_agent_stack.core.ai.reranker import RerankerProtocol

__all__ = [
    "RagService",
    "RagChunk",
    "IngestResult",
    "ChunkingStrategy",
    "UnsupportedFileTypeError",
]

ChunkingStrategy = Literal["fixed", "paragraph"]


class UnsupportedFileTypeError(Exception):
    """Raised when ingest_file receives a MIME type with no registered extractor."""


@dataclass(frozen=True)
class RagChunk:
    content: str
    score: float
    metadata: dict[str, str | int | float | bool]
    document_id: str | None
    chunk_index: int


@dataclass(frozen=True)
class IngestResult:
    document_id: str
    chunks_stored: int
    collection: str


class RagService:
    """Composable RAG pipeline (ADR-040, amended ADR-045). DI via EmbeddingProtocol + VectorStoreProtocol."""

    def __init__(
        self,
        embedding: EmbeddingProtocol,
        vector_store: VectorStoreProtocol,
        *,
        reranker: RerankerProtocol | None = None,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        chunking_strategy: ChunkingStrategy = "fixed",
    ) -> None:
        self._embedding = embedding
        self._vector_store = vector_store
        self._reranker = reranker
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._chunking_strategy: ChunkingStrategy = chunking_strategy

    def _chunk(self, text: str) -> list[str]:
        if self._chunking_strategy == "paragraph":
            return paragraph_chunker(text)
        return fixed_chunker(text, self._chunk_size, self._chunk_overlap)

    async def ingest(
        self,
        collection: str,
        content: str,
        *,
        document_id: str | None = None,
        metadata: dict[str, str | int | float | bool] | None = None,
    ) -> IngestResult:
        if document_id is None:
            document_id = uuid.uuid4().hex
        chunks = self._chunk(content)
        if not chunks:
            return IngestResult(document_id=document_id, chunks_stored=0, collection=collection)
        base_meta: dict[str, str | int | float | bool] = dict(metadata or {})
        base_meta["_chunk_count"] = len(chunks)
        vectors = await self._embedding.embed_batch(chunks)
        for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
            chunk_meta = dict(base_meta)
            chunk_meta["_chunk_index"] = idx
            chunk_meta["_document_id"] = document_id
            await self._vector_store.upsert(
                collection=collection,
                id=f"{document_id}:{idx}",
                vector=vector,
                metadata=chunk_meta,
                content=chunk_text,
            )
        return IngestResult(
            document_id=document_id,
            chunks_stored=len(chunks),
            collection=collection,
        )

    async def ingest_file(
        self,
        collection: str,
        data: bytes,
        *,
        filename: str,
        content_type: str = "application/octet-stream",
        document_id: str | None = None,
        metadata: dict[str, str | int | float | bool] | None = None,
    ) -> IngestResult:
        if content_type == "text/plain":
            text = data.decode("utf-8", errors="replace")
        else:
            extractor = get_extractor(content_type)
            if extractor is None:
                raise UnsupportedFileTypeError(
                    f"No extractor available for content_type={content_type!r}. "
                    "Supported: application/pdf, application/vnd...docx, "
                    "application/vnd...xlsx, message/rfc822, text/plain."
                )
            text = await extractor.extract(data)
        return await self.ingest(
            collection,
            text,
            document_id=document_id,
            metadata=metadata,
        )

    async def retrieve(
        self,
        collection: str,
        query: str,
        *,
        top_k: int = 5,
        filter: dict[str, str | int | float | bool] | None = None,
    ) -> list[RagChunk]:
        fetch_k = top_k * 3 if self._reranker is not None else top_k
        vector = await self._embedding.embed(query)
        results: list[VectorSearchResult] = await self._vector_store.search(
            collection,
            vector,
            top_k=fetch_k,
            filter=filter,
        )

        def _to_chunks(hits: list[VectorSearchResult], scores: dict[int, float] | None = None) -> list[RagChunk]:
            chunks = []
            for i, hit in enumerate(hits):
                meta = dict(hit.metadata)
                doc_id = str(meta.pop("_document_id", ""))
                chunk_idx = int(meta.pop("_chunk_index", 0))
                meta.pop("_chunk_count", None)
                score = scores[i] if scores is not None else hit.score
                chunks.append(
                    RagChunk(
                        content=hit.content or "",
                        score=score,
                        metadata=meta,
                        document_id=doc_id,
                        chunk_index=chunk_idx,
                    )
                )
            return chunks

        if self._reranker is None or not results:
            return _to_chunks(results)

        documents = [hit.content or "" for hit in results]
        try:
            reranked = await self._reranker.rerank(query, documents, top_k=top_k)
        except TimeoutError:
            import logging
            logging.getLogger(__name__).warning(
                "Reranker timed out; falling back to vector similarity ordering"
            )
            return _to_chunks(results[:top_k])
        # Reorder results by reranker output; reranked items are already sorted desc by score
        reranked_chunks: list[RagChunk] = []
        for item in reranked:
            hit = results[item.index]
            meta = dict(hit.metadata)
            doc_id = str(meta.pop("_document_id", ""))
            chunk_idx = int(meta.pop("_chunk_index", 0))
            meta.pop("_chunk_count", None)
            reranked_chunks.append(
                RagChunk(
                    content=item.content,
                    score=item.score,
                    metadata=meta,
                    document_id=doc_id,
                    chunk_index=chunk_idx,
                )
            )
        return reranked_chunks

    async def delete_document(self, collection: str, document_id: str) -> int:
        # Search with a zero-vector filtered on _document_id to retrieve _chunk_count.
        # We stored _chunk_count in every chunk's metadata during ingest so we can
        # reconstruct chunk IDs deterministically without a separate index.
        dims = self._embedding.dimensions
        dummy = [0.0] * dims
        try:
            hits = await self._vector_store.search(
                collection,
                dummy,
                top_k=1,
                filter={"_document_id": document_id},
            )
            if not hits:
                return 0
            chunk_count = int(hits[0].metadata.get("_chunk_count", 0))
        except Exception:
            return 0

        deleted = 0
        for idx in range(chunk_count):
            try:
                await self._vector_store.delete(collection, f"{document_id}:{idx}")
                deleted += 1
            except Exception:
                pass
        return deleted
