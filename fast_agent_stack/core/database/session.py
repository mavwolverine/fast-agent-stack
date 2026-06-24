import re
from collections.abc import AsyncGenerator, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_SCHEMA_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_engine(database_url: str, *, echo: bool = False) -> None:
    global _engine, _session_factory
    _engine = create_async_engine(database_url, echo=echo)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_engine() -> AsyncEngine | None:
    return _engine


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError(
            "Database not initialized. Register DatabaseLifespanHook before use."
        )
    async with _session_factory() as session:
        yield session


def get_async_session_for_schema(
    schema: str,
) -> Callable[[], AsyncGenerator[AsyncSession, None]]:
    """Return a FastAPI dependency scoped to *schema*.

    Validates schema against ^[a-zA-Z_][a-zA-Z0-9_]*$ (I8) before issuing
    SET search_path — never interpolates unvalidated input into SQL.
    """
    if not _SCHEMA_RE.match(schema):
        raise ValueError(
            f"Invalid schema name: {schema!r}. Must match ^[a-zA-Z_][a-zA-Z0-9_]*$"
        )

    async def _dep() -> AsyncGenerator[AsyncSession, None]:
        if _session_factory is None:
            raise RuntimeError(
                "Database not initialized. Register DatabaseLifespanHook before use."
            )
        async with _session_factory() as session:
            await session.execute(text(f"SET search_path TO {schema}, public"))
            yield session

    return _dep
