"""Public RAG facade — re-exports the user-facing RAG, embedding, and vector-store symbols."""

from fast_agent_stack.core.ai.embedding import EmbeddingProtocol, get_embedding_provider
from fast_agent_stack.core.ai.rag import (
    ChunkingStrategy,
    IngestResult,
    RagChunk,
    RagService,
    UnsupportedFileTypeError,
)
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
]
