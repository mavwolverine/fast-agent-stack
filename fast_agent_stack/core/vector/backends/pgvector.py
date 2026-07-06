"""pgvector backend — SQLAlchemy async engine over PostgreSQL (ADR-038, I4)."""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

try:
    import pgvector  # noqa: F401 — registers vector type with SQLAlchemy
except ImportError:
    raise ImportError("pip install fast-agent-stack[vector-pgvector]") from None

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from fast_agent_stack.core.vector import CollectionNotFoundError, VectorSearchResult

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Maps protocol distance_metric → (index_ops_class, search_operator)
_DISTANCE_OPS: dict[str, tuple[str, str]] = {
    "cosine":    ("vector_cosine_ops", "<=>"),
    "euclidean": ("vector_l2_ops",     "<->"),
    "euclid":    ("vector_l2_ops",     "<->"),
    "dot":       ("vector_ip_ops",     "<#>"),
}


def _validate_name(name: str) -> None:
    if not _SAFE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid collection/schema name {name!r}: "
            "only letters, digits, and underscores are allowed, must not start with a digit."
        )


def _vec_literal(vector: list[float]) -> str:
    """Render a vector as a PostgreSQL literal string e.g. '[0.1,0.2,0.3]'."""
    return "[" + ",".join(str(float(v)) for v in vector) + "]"


def _normalise_db_url(url: str) -> str:
    """Ensure the URL uses the asyncpg driver."""
    if url.startswith("postgres://"):
        url = "postgresql" + url[len("postgres"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg" + url[len("postgresql"):]
    return url


def _is_missing_table(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "does not exist" in msg or "undefined table" in msg


class PgVectorStore:
    """PostgreSQL + pgvector backend.

    Each ``collection`` maps to a table in ``pgvector_collection_schema``.
    The escape hatch (I4) is ``self._client`` — an ``AsyncEngine``.
    """

    def __init__(self, settings: "BaseSettings") -> None:
        db_url = settings.pgvector_database_url
        if not db_url:
            raise RuntimeError(
                "pgvector_database_url must be set to use PgVectorStore. "
                "Add it to your settings (I11)."
            )
        _validate_name(settings.pgvector_collection_schema)
        self._schema: str = settings.pgvector_collection_schema
        self._timeout: float = settings.vector_timeout
        self._client: AsyncEngine = create_async_engine(
            _normalise_db_url(db_url),
            pool_pre_ping=True,
            connect_args={"timeout": settings.vector_timeout},
        )

    async def create_collection(
        self,
        name: str,
        dimensions: int,
        *,
        distance_metric: str = "cosine",
    ) -> None:
        _validate_name(name)
        if distance_metric not in _DISTANCE_OPS:
            raise ValueError(
                f"Unsupported distance_metric {distance_metric!r}. "
                f"Supported: {sorted(_DISTANCE_OPS)}"
            )
        schema, table = self._schema, name
        async with self._client.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS "{schema}"."{table}" (
                    id       TEXT    PRIMARY KEY,
                    embedding vector({dimensions}),
                    content  TEXT,
                    metadata JSONB   NOT NULL DEFAULT '{{}}'
                )
            """))

    async def upsert(
        self,
        collection: str,
        id: str,
        vector: list[float],
        metadata: dict[str, str | int | float | bool],
        *,
        content: str | None = None,
    ) -> None:
        _validate_name(collection)
        schema, table = self._schema, collection
        vec_lit = _vec_literal(vector)
        meta_json = json.dumps(metadata)
        sql = text(f"""
            INSERT INTO "{schema}"."{table}" (id, embedding, content, metadata)
            VALUES (:id, '{vec_lit}'::vector, :content, :meta::jsonb)
            ON CONFLICT (id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                content   = EXCLUDED.content,
                metadata  = EXCLUDED.metadata
        """)
        async with self._client.begin() as conn:
            try:
                await conn.execute(sql, {"id": id, "content": content, "meta": meta_json})
            except Exception as exc:
                if _is_missing_table(exc):
                    raise CollectionNotFoundError(collection) from exc
                raise

    async def search(
        self,
        collection: str,
        vector: list[float],
        *,
        top_k: int = 10,
        filter: dict[str, str | int | float | bool] | None = None,
    ) -> list[VectorSearchResult]:
        _validate_name(collection)
        schema, table = self._schema, collection
        vec_lit = _vec_literal(vector)

        params: dict[str, Any] = {"top_k": top_k}
        where_clause = ""
        if filter:
            where_clause = "WHERE metadata @> :meta::jsonb"
            params["meta"] = json.dumps(filter)

        sql = text(f"""
            SELECT id,
                   1 - (embedding <=> '{vec_lit}'::vector) AS score,
                   content,
                   metadata
            FROM   "{schema}"."{table}"
            {where_clause}
            ORDER  BY embedding <=> '{vec_lit}'::vector
            LIMIT  :top_k
        """)
        async with self._client.connect() as conn:
            try:
                result = await conn.execute(sql, params)
            except Exception as exc:
                if _is_missing_table(exc):
                    raise CollectionNotFoundError(collection) from exc
                raise

        out: list[VectorSearchResult] = []
        for row in result.fetchall():
            raw_meta: dict[str, Any] = dict(row.metadata) if row.metadata else {}
            meta: dict[str, str | int | float | bool] = {
                k: v for k, v in raw_meta.items()
                if isinstance(v, (str, int, float, bool))
            }
            out.append(VectorSearchResult(
                id=row.id,
                score=float(row.score),
                metadata=meta,
                content=row.content,
            ))
        return out

    async def delete(self, collection: str, id: str) -> None:
        _validate_name(collection)
        schema, table = self._schema, collection
        sql = text(f'DELETE FROM "{schema}"."{table}" WHERE id = :id')
        async with self._client.begin() as conn:
            try:
                await conn.execute(sql, {"id": id})
            except Exception as exc:
                if _is_missing_table(exc):
                    raise CollectionNotFoundError(collection) from exc
                raise

    async def close(self) -> None:
        await self._client.dispose()
