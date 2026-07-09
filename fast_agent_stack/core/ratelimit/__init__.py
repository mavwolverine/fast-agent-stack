"""Redis fixed-window rate limiting middleware and lifespan hook (ADR-016, ADR-033)."""

from __future__ import annotations

import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from fast_agent_stack.core.config import BaseSettings

try:
    from redis_fastapi.deps import get_async_redis as _get_async_redis
except ImportError:
    raise ImportError(
        "fastapi-redis-sdk is required for rate limiting. Install it with: pip install fast-agent-stack[rate-limit]"
    )

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

    Redis client is acquired per-request from the SDK-managed pool via
    ``request.app.state._redis`` (set by ``FastAPIRedisLifespanHook``).
    WebSocket connections are passed through without rate limiting.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        requests: int,
        period: int,
    ) -> None:
        super().__init__(app)
        self._requests = requests
        self._period = period

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # WebSocket passthrough (no rate-limit)
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        redis = await _get_async_redis(request)

        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        window_start = (int(time.time()) // self._period) * self._period
        # ADR-033: key prefix fas:rl:
        key = f"fas:rl:{ip}:{window_start}"

        count = await redis.eval(_RATE_LIMIT_LUA, 1, key, self._period)
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
    """Lifespan hook that wires RateLimitMiddleware to the app.

    Redis pool lifecycle is managed by FastAPIRedisLifespanHook (I9 step 2).
    This hook only registers the middleware; no pool ownership.
    """

    def __init__(self, settings: BaseSettings, *, app: Any = None) -> None:
        self._settings = settings
        self._app = app

    async def __aenter__(self) -> RateLimitLifespanHook:
        if self._app is not None:
            self._app.add_middleware(
                RateLimitMiddleware,
                requests=self._settings.rate_limit_requests,
                period=self._settings.rate_limit_period,
            )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass  # pool owned by FastAPIRedisLifespanHook / SDK
