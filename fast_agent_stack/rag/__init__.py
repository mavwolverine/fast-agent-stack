"""Public RAG facade — re-exports the user-facing RAG, embedding, vector-store, and reranker symbols."""

from fast_agent_stack.core.ai.embedding import EmbeddingProtocol, get_embedding_provider
from fast_agent_stack.core.ai.rag import (
    ChunkingStrategy,
    IngestResult,
    RagChunk,
    RagService,
    UnsupportedFileTypeError,
)
from fast_agent_stack.core.ai.reranker import RerankerProtocol, RerankResult, get_reranker
from fast_agent_stack.core.vector import (
    CollectionNotFoundError,
    VectorSearchResult,
    VectorStoreProtocol,
    get_vector_store,
)

__all__ = [
    # RagService
    "RagService",
    "RagChunk",
    "IngestResult",
    "ChunkingStrategy",
    "UnsupportedFileTypeError",
    # Embedding
    "EmbeddingProtocol",
    "get_embedding_provider",
    # Vector store
    "VectorStoreProtocol",
    "VectorSearchResult",
    "CollectionNotFoundError",
    "get_vector_store",
    # Reranker
    "RerankerProtocol",
    "RerankResult",
    "get_reranker",
]
