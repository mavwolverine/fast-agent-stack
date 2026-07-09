"""Response caching decorators backed by fastapi-redis-sdk (ADR-037, ADR-006).

Usage
-----
Call ``enable_caching(app)`` once at setup time (after ``FastAPIRedisLifespanHook``
is registered), then use ``cache()``, ``cache_evict()``, or ``cache_put()`` as
``Depends()`` on any route.

Example::

    from fast_agent_stack.core.caching import cache, cache_evict, enable_caching

    enable_caching(app)

    @app.get("/items/{id}")
    async def get_item(id: int, _=Depends(cache(ttl=60, eviction_group="items"))):
        ...

    @app.delete("/items/{id}")
    async def delete_item(id: int, _=Depends(cache_evict(eviction_group="items"))):
        ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

try:
    from redis_fastapi import (
        CacheBackend,
        CacheBackendDep,
        FastAPIRedis,
        cache,
        cache_evict,
        cache_put,
    )
except ImportError:
    raise ImportError(
        "fastapi-redis-sdk is required for response caching. Install it with: pip install fast-agent-stack[caching]"
    )


def enable_caching(app: FastAPI) -> None:
    """Register the SDK capture middleware and exception handler on *app*.

    Must be called after ``FastAPIRedisLifespanHook`` is registered (which
    calls ``FastAPIRedis(app).lifespan()``), but before the app starts serving
    requests. Calling it more than once on the same app is a no-op.
    """
    FastAPIRedis(app).caching()


__all__ = [
    "cache",
    "cache_evict",
    "cache_put",
    "enable_caching",
    "CacheBackend",
    "CacheBackendDep",
]
