from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.http.exceptions import UnexpectedResponse
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        VectorParams,
    )
except ImportError:
    raise ImportError("pip install fast-agent-stack[vector-qdrant]") from None

from fast_agent_stack.core.vector import CollectionNotFoundError, VectorSearchResult

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings

_DISTANCE_MAP = {
    "cosine": Distance.COSINE,
    "dot": Distance.DOT,
    "euclid": Distance.EUCLID,
}


class QdrantStore:
    def __init__(self, settings: BaseSettings) -> None:
        self._client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=settings.vector_timeout,
        )

    async def create_collection(
        self,
        name: str,
        dimensions: int,
        *,
        distance_metric: str = "cosine",
    ) -> None:
        distance = _DISTANCE_MAP.get(distance_metric, Distance.COSINE)
        # Only create if it doesn't already exist
        collections = await self._client.get_collections()
        existing = {c.name for c in collections.collections}
        if name not in existing:
            await self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dimensions, distance=distance),
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
        payload: dict[str, Any] = dict(metadata)
        if content is not None:
            payload["_content"] = content
        await self._client.upsert(
            collection_name=collection,
            points=[PointStruct(id=_str_to_id(id), vector=vector, payload=payload)],
        )

    async def search(
        self,
        collection: str,
        vector: list[float],
        *,
        top_k: int = 10,
        filter: dict[str, str | int | float | bool] | None = None,
    ) -> list[VectorSearchResult]:
        try:
            qdrant_filter = _build_filter(filter) if filter else None
            results = await self._client.search(
                collection_name=collection,
                query_vector=vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
            )
        except (UnexpectedResponse, Exception) as exc:
            msg = str(exc).lower()
            if "not found" in msg or "collection" in msg:
                raise CollectionNotFoundError(collection) from exc
            raise
        out: list[VectorSearchResult] = []
        for hit in results:
            payload = dict(hit.payload or {})
            content = payload.pop("_content", None)
            meta: dict[str, str | int | float | bool] = {
                k: v for k, v in payload.items() if isinstance(v, (str, int, float, bool))
            }
            out.append(
                VectorSearchResult(
                    id=str(hit.id),
                    score=float(hit.score),
                    metadata=meta,
                    content=content if isinstance(content, str) else None,
                )
            )
        return out

    async def delete(self, collection: str, id: str) -> None:
        from qdrant_client.models import PointIdsList

        await self._client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=[_str_to_id(id)]),
        )

    async def close(self) -> None:
        await self._client.close()


def _str_to_id(id: str) -> str:
    """Convert an arbitrary string ID to a valid Qdrant point ID (UUID format)."""
    import uuid as _uuid

    try:
        # If it's already a valid UUID, use as-is
        _uuid.UUID(id)
        return id
    except ValueError:
        # Generate a deterministic UUID v5 from the string
        return str(_uuid.uuid5(_uuid.NAMESPACE_URL, id))


def _build_filter(filter: dict[str, str | int | float | bool]) -> Filter:
    conditions = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filter.items()]
    return Filter(must=conditions)
