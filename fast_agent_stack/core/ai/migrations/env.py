"""Alembic env.py for AI framework migrations (Phase 4c).

Run via ``fastagentstack migrate`` — do not invoke directly.
The database URL is supplied by the CLI via ``context.config.attributes``.
Uses the same ``fas_alembic_version`` table as auth migrations.
"""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

import fast_agent_stack.core.ai.conversation  # noqa: F401 — registers models on Base.metadata
import fast_agent_stack.core.ai.usage  # noqa: F401
from fast_agent_stack.core.database import Base

target_metadata = Base.metadata


def _do_migrations(connection: object) -> None:
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        version_table="fas_alembic_version",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    database_url: str | None = context.config.attributes.get("database_url")
    if not database_url:
        raise RuntimeError(
            "Framework migration env.py requires database_url in alembic config "
            "attributes. Run via 'fastagentstack migrate'."
        )
    engine = create_async_engine(database_url, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_do_migrations)
    await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline migration mode is not supported for framework migrations.")
else:
    asyncio.run(run_migrations_online())
