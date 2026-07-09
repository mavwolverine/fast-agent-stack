from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from opensearchpy import AsyncOpenSearch
    from opensearchpy.exceptions import NotFoundError
except ImportError:
    raise ImportError("pip install fast-agent-stack[vector-opensearch]") from None

from fast_agent_stack.core.vector import CollectionNotFoundError, VectorSearchResult

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings


class OpenSearchStore:
    def __init__(self, settings: BaseSettings) -> None:
        http_auth = None
        if settings.opensearch_username and settings.opensearch_password:
            http_auth = (settings.opensearch_username, settings.opensearch_password)
        self._client = AsyncOpenSearch(
            hosts=[settings.opensearch_url],
            http_auth=http_auth,
            timeout=settings.vector_timeout,
        )

    async def create_collection(
        self,
        name: str,
        dimensions: int,
        *,
        distance_metric: str = "cosine",
    ) -> None:
        space_type = "cosinesimil" if distance_metric == "cosine" else distance_metric
        body: dict[str, Any] = {
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    "vector": {
                        "type": "knn_vector",
                        "dimension": dimensions,
                        "method": {"name": "hnsw", "space_type": space_type, "engine": "nmslib"},
                    },
                    "_content": {"type": "text"},
                }
            },
        }
        await self._client.indices.create(index=name, body=body, ignore=400)

    async def upsert(
        self,
        collection: str,
        id: str,
        vector: list[float],
        metadata: dict[str, str | int | float | bool],
        *,
        content: str | None = None,
    ) -> None:
        doc: dict[str, Any] = {"vector": vector, **metadata}
        if content is not None:
            doc["_content"] = content
        await self._client.index(index=collection, id=id, body=doc, refresh=True)

    async def search(
        self,
        collection: str,
        vector: list[float],
        *,
        top_k: int = 10,
        filter: dict[str, str | int | float | bool] | None = None,
    ) -> list[VectorSearchResult]:
        try:
            knn_query: dict[str, Any] = {"vector": {"vector": vector, "k": top_k}}
            if filter:
                knn_query["vector"]["filter"] = {"bool": {"must": [{"term": {k: v}} for k, v in filter.items()]}}
            body = {"size": top_k, "query": {"knn": knn_query}}
            resp = await self._client.search(index=collection, body=body)
        except NotFoundError as exc:
            raise CollectionNotFoundError(collection) from exc
        results: list[VectorSearchResult] = []
        for hit in resp["hits"]["hits"]:
            src = dict(hit["_source"])
            content = src.pop("_content", None)
            src.pop("vector", None)
            meta: dict[str, str | int | float | bool] = {
                k: v for k, v in src.items() if isinstance(v, (str, int, float, bool))
            }
            results.append(
                VectorSearchResult(
                    id=hit["_id"],
                    score=float(hit["_score"]),
                    metadata=meta,
                    content=content if isinstance(content, str) else None,
                )
            )
        return results

    async def delete(self, collection: str, id: str) -> None:
        await self._client.delete(index=collection, id=id, ignore=404)

    async def close(self) -> None:
        await self._client.close()
