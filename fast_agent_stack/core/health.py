"""Health check routes and Redis probe (I13)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from fast_agent_stack.core.database import check_db

router = APIRouter(tags=["health"])

_redis_url: str | None = None


def configure_redis_health(url: str | None) -> None:
    """Called by AuthLifespanHook to register the Redis URL for health checks."""
    global _redis_url
    _redis_url = url


async def check_redis() -> tuple[bool, str]:
    """Async PING check against the configured Redis URL.

    Returns (True, "ok") when redis_url is None (not configured).
    Import-guarded with I3 pattern.
    """
    if _redis_url is None:
        return True, "ok"
    try:
        import redis.asyncio as aioredis
    except ImportError:
        return True, "ok"
    client = aioredis.from_url(_redis_url, decode_responses=False)
    try:
        await asyncio.wait_for(client.ping(), timeout=2.0)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)
    finally:
        await client.aclose()


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    db_ok, db_msg = await check_db()
    redis_ok, redis_msg = await check_redis()
    if not db_ok or not redis_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": db_msg, "redis": redis_msg},
        )
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "database": "ok", "redis": "ok"},
    )
