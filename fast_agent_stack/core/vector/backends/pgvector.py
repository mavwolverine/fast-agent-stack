from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import pgvector  # noqa: F401
except ImportError:
    raise ImportError("pip install fast-agent-stack[vector-pgvector]") from None

from fast_agent_stack.core.vector import CollectionNotFoundError, VectorSearchResult

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings


class PgVectorStore:
    """pgvector backend — uses SQLAlchemy async session (I4: self._client)."""

    def __init__(self, settings: "BaseSettings") -> None:
        self._schema = settings.pgvector_collection_schema
        self._timeout = settings.vector_timeout
        self._client: object | None = None  # injected via set_engine() at startup

    async def create_collection(
        self,
        name: str,
        dimensions: int,
        *,
        distance_metric: str = "cosine",
    ) -> None:
        raise NotImplementedError(
            "PgVectorStore.create_collection requires SQLAlchemy session injection; "
            "call set_engine() first."
        )

    async def upsert(
        self,
        collection: str,
        id: str,
        vector: list[float],
        metadata: dict[str, str | int | float | bool],
        *,
        content: str | None = None,
    ) -> None:
        raise NotImplementedError("PgVectorStore requires session injection.")

    async def search(
        self,
        collection: str,
        vector: list[float],
        *,
        top_k: int = 10,
        filter: dict[str, str | int | float | bool] | None = None,
    ) -> list[VectorSearchResult]:
        raise NotImplementedError("PgVectorStore requires session injection.")

    async def delete(self, collection: str, id: str) -> None:
        raise NotImplementedError("PgVectorStore requires session injection.")

    async def close(self) -> None:
        pass
