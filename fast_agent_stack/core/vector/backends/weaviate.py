from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    import weaviate
    import weaviate.classes as wvc
except ImportError:
    raise ImportError("pip install fast-agent-stack[vector-weaviate]") from None

from fast_agent_stack.core.vector import CollectionNotFoundError, VectorSearchResult

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings


class WeaviateStore:
    def __init__(self, settings: "BaseSettings") -> None:
        auth = (
            weaviate.auth.AuthApiKey(api_key=settings.weaviate_api_key)
            if settings.weaviate_api_key
            else None
        )
        self._client = weaviate.use_async_with_custom(
            http_host=settings.weaviate_url.replace("http://", "").split(":")[0],
            http_port=int(settings.weaviate_url.split(":")[-1]) if ":" in settings.weaviate_url else 8080,
            http_secure=settings.weaviate_url.startswith("https"),
            grpc_host=settings.weaviate_url.replace("http://", "").split(":")[0],
            grpc_port=50051,
            grpc_secure=False,
            auth_credentials=auth,
        )
        self._timeout = settings.vector_timeout

    async def create_collection(
        self,
        name: str,
        dimensions: int,
        *,
        distance_metric: str = "cosine",
    ) -> None:
        async with self._client as client:
            metric_map = {
                "cosine": wvc.config.VectorDistances.COSINE,
                "dot": wvc.config.VectorDistances.DOT,
                "euclid": wvc.config.VectorDistances.L2_SQUARED,
            }
            await client.collections.create(
                name=name,
                vectorizer_config=wvc.config.Configure.Vectorizer.none(),
                vector_index_config=wvc.config.Configure.VectorIndex.hnsw(
                    distance_metric=metric_map.get(distance_metric, wvc.config.VectorDistances.COSINE),
                ),
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
        props: dict[str, Any] = dict(metadata)
        if content is not None:
            props["_content"] = content
        async with self._client as client:
            col = client.collections.get(collection)
            await col.data.insert(properties=props, vector=vector, uuid=_to_uuid(id))

    async def search(
        self,
        collection: str,
        vector: list[float],
        *,
        top_k: int = 10,
        filter: dict[str, str | int | float | bool] | None = None,
    ) -> list[VectorSearchResult]:
        try:
            async with self._client as client:
                col = client.collections.get(collection)
                resp = await col.query.near_vector(
                    near_vector=vector,
                    limit=top_k,
                    return_metadata=wvc.query.MetadataQuery(score=True, distance=True),
                )
        except Exception as exc:
            if "not found" in str(exc).lower():
                raise CollectionNotFoundError(collection) from exc
            raise
        results: list[VectorSearchResult] = []
        for obj in resp.objects:
            props = dict(obj.properties)
            content = props.pop("_content", None)
            meta: dict[str, str | int | float | bool] = {
                k: v for k, v in props.items()
                if isinstance(v, (str, int, float, bool))
            }
            results.append(VectorSearchResult(
                id=str(obj.uuid),
                score=float(obj.metadata.score or 0.0),
                metadata=meta,
                content=content if isinstance(content, str) else None,
            ))
        return results

    async def delete(self, collection: str, id: str) -> None:
        async with self._client as client:
            col = client.collections.get(collection)
            await col.data.delete_by_id(_to_uuid(id))

    async def close(self) -> None:
        pass


def _to_uuid(id: str) -> str:
    import hashlib
    import uuid as _uuid
    try:
        _uuid.UUID(id)
        return id
    except ValueError:
        # deterministic UUID from string
        h = hashlib.md5(id.encode()).hexdigest()
        return str(_uuid.UUID(h))
