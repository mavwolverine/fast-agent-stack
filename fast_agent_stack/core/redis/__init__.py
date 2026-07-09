"""Redis lifespan hook wrapping fastapi-redis-sdk (ADR-037, I9 step 2)."""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Any

from fast_agent_stack.core.config import BaseSettings


class FastAPIRedisLifespanHook:
    """Lifespan hook that integrates fastapi-redis-sdk into the FastAgentStack hook chain.

    Call order per I9 (amended):
      1. DatabaseLifespanHook
      2. FastAPIRedisLifespanHook  ← this class (conditional: auth or rate-limit enabled)
      3. AuthLifespanHook
      4. RateLimitLifespanHook
      ...

    ``FastAPIRedis(app).lifespan()`` wraps the app's existing lifespan context so the
    SDK-managed pool is available before any hook's ``__aenter__`` is called.
    ``__aenter__`` performs the I11 connectivity check against the live pool.
    Pool teardown is handled by the SDK's wrapped lifespan after all hooks exit.
    """

    def __init__(self, settings: BaseSettings, *, app: Any) -> None:
        try:
            from redis_fastapi import FastAPIRedis
        except ImportError:
            raise ImportError(
                "fastapi-redis-sdk is required for Redis integration. "
                "Install it with: pip install fast-agent-stack[auth-jwt]"
            )
        if not settings.redis_url:
            raise RuntimeError("redis_url must be set when Redis integration is enabled (I11)")
        self._settings = settings
        self._app = app
        # Wrap the app's lifespan at setup time (before startup).
        # The SDK creates the pool BEFORE our hook chain runs, so all hooks can use Redis.
        FastAPIRedis(app).lifespan()

    async def __aenter__(self) -> FastAPIRedisLifespanHook:
        # I11: connectivity check — the SDK pool is already initialised at this point
        try:
            import redis.asyncio as aioredis
        except ImportError:
            return self
        client = aioredis.from_url(self._settings.redis_url, decode_responses=False)  # type: ignore[arg-type]
        try:
            await asyncio.wait_for(client.ping(), timeout=5.0)  # type: ignore[arg-type]
        except (TimeoutError, Exception) as exc:
            await client.aclose()
            raise RuntimeError(
                f"Cannot connect to Redis at {self._settings.redis_url} — required for auth/rate-limit (I11)"
            ) from exc
        await client.aclose()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass  # SDK handles pool teardown via the wrapped lifespan
