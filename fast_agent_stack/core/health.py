"""Health check routes and Redis probe (I13)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from fast_agent_stack.core.database import check_db

router = APIRouter(tags=["health"])


async def check_redis(request: Request | None = None) -> tuple[bool, str]:
    """Ping the SDK-managed Redis pool.

    Returns (True, "ok") when Redis is not configured (no FastAPIRedisLifespanHook
    registered) or when no request is provided. This makes the health check
    transparent for projects that do not use Redis.
    """
    if request is None:
        return True, "ok"
    pool_state = getattr(request.app.state, "_redis", None)
    if pool_state is None:
        return True, "ok"
    try:
        from redis_fastapi.deps import get_async_redis
    except ImportError:
        return True, "ok"
    try:
        client = await get_async_redis(request)
        await asyncio.wait_for(client.ping(), timeout=2.0)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    db_ok, db_msg = await check_db()
    redis_ok, redis_msg = await check_redis(request)
    if not db_ok or not redis_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": db_msg, "redis": redis_msg},
        )
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "database": "ok", "redis": "ok"},
    )
