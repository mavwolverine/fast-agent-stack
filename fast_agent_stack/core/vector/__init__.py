from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings

__all__ = [
    "VectorStoreProtocol",
    "VectorSearchResult",
    "CollectionNotFoundError",
    "get_vector_store",
]


class CollectionNotFoundError(Exception):
    """Raised when operating on a collection that does not exist."""


@dataclass(frozen=True)
class VectorSearchResult:
    id: str
    score: float
    metadata: dict[str, str | int | float | bool]
    content: str | None


@runtime_checkable
class VectorStoreProtocol(Protocol):
    async def create_collection(
        self,
        name: str,
        dimensions: int,
        *,
        distance_metric: str = "cosine",
    ) -> None: ...

    async def upsert(
        self,
        collection: str,
        id: str,
        vector: list[float],
        metadata: dict[str, str | int | float | bool],
        *,
        content: str | None = None,
    ) -> None: ...

    async def search(
        self,
        collection: str,
        vector: list[float],
        *,
        top_k: int = 10,
        filter: dict[str, str | int | float | bool] | None = None,
    ) -> list[VectorSearchResult]: ...

    async def delete(self, collection: str, id: str) -> None: ...

    async def close(self) -> None: ...


def get_vector_store(settings: "BaseSettings") -> VectorStoreProtocol:
    """Factory: resolves alias or ADR-012 dotted path."""
    backend = settings.vector_db
    if backend == "qdrant":
        from fast_agent_stack.core.vector.backends.qdrant import QdrantStore
        return QdrantStore(settings)
    if backend == "pgvector":
        from fast_agent_stack.core.vector.backends.pgvector import PgVectorStore
        return PgVectorStore(settings)
    if backend == "opensearch":
        from fast_agent_stack.core.vector.backends.opensearch import OpenSearchStore
        return OpenSearchStore(settings)
    if backend == "weaviate":
        from fast_agent_stack.core.vector.backends.weaviate import WeaviateStore
        return WeaviateStore(settings)
    module_path, _, class_name = backend.rpartition(".")
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls(settings)
