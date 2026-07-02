"""Redis fixed-window rate limiting middleware and lifespan hook (ADR-016, ADR-033)."""
from __future__ import annotations

import importlib
import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from fast_agent_stack.core.config import BaseSettings

logger = logging.getLogger(__name__)

# ADR-016: atomic INCR + EXPIRE-on-first — only one round-trip via eval
_RATE_LIMIT_LUA = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiter keyed by client IP (ADR-016, ADR-033).

    The ``redis`` parameter must be an already-connected async redis client
    (e.g. ``redis.asyncio.Redis``); the middleware does not create connections.
    WebSocket connections are passed through without rate limiting.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        redis: Any,
        requests: int,
        period: int,
    ) -> None:
        super().__init__(app)
        self._redis = redis
        self._requests = requests
        self._period = period

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # WebSocket passthrough (no rate-limit)
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        ip = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )
        window_start = (int(time.time()) // self._period) * self._period
        # ADR-033: key prefix fas:rl:
        key = f"fas:rl:{ip}:{window_start}"

        count = await self._redis.eval(_RATE_LIMIT_LUA, 1, key, self._period)
        remaining = max(0, self._requests - count)
        reset_at = window_start + self._period

        if count > self._requests:
            return JSONResponse(
                {"detail": "Too Many Requests"},
                status_code=429,
                headers={
                    "Retry-After": str(self._period),
                    "X-RateLimit-Limit": str(self._requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)
        return response


class RateLimitLifespanHook:
    """Lifespan hook that creates and owns a redis.asyncio connection pool (I4)."""

    def __init__(self, settings: BaseSettings) -> None:
        self._settings = settings
        self.redis: Any = None

    async def __aenter__(self) -> "RateLimitLifespanHook":
        try:
            redis_asyncio = importlib.import_module("redis.asyncio")
        except ImportError as exc:
            raise ImportError(
                f"redis is required for rate limiting: {exc}. "
                "Install it with: pip install fast-agent-stack[rate-limit]"
            ) from exc

        self.redis = redis_asyncio.from_url(self._settings.redis_url)
        await self.redis.ping()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.redis is not None:
            await self.redis.aclose()
