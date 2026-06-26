"""Session auth backend (ADR-008, ADR-032, ADR-033)."""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, Response

from fast_agent_stack.core.auth.backends import TokenResponse

try:
    from redis.asyncio import Redis
except ImportError:
    raise ImportError(
        "redis is required for session authentication. "
        "Install it with: pip install fast-agent-stack[auth-session]"
    )

_SESSION_PREFIX = "fas:session:"  # ADR-032, ADR-033
_COOKIE_NAME = "fas_session"       # ADR-032


class SessionAuthBackend:
    def __init__(
        self,
        session_ttl: int,
        redis: Redis,  # type: ignore[type-arg]
        *,
        debug: bool = False,
    ) -> None:
        self._ttl = session_ttl
        self._redis = redis
        self._debug = debug

    async def authenticate(self, request: Request) -> uuid.UUID | None:
        session_id = request.cookies.get(_COOKIE_NAME)
        if not session_id:
            return None
        raw = await self._redis.get(f"{_SESSION_PREFIX}{session_id}")
        if not raw:
            return None
        data: dict[str, str] = json.loads(raw)
        # Sliding TTL: reset on every authenticated access (ADR-032)
        await self._redis.expire(f"{_SESSION_PREFIX}{session_id}", self._ttl)
        return uuid.UUID(data["user_id"])

    async def create_token(self, user: object, response: Response) -> TokenResponse:
        from fast_agent_stack.core.auth.models import User as _User

        assert isinstance(user, _User)
        session_id = secrets.token_urlsafe(32)
        data = {
            "user_id": str(user.id),
            "created_at": datetime.now(UTC).isoformat(),
        }
        await self._redis.set(
            f"{_SESSION_PREFIX}{session_id}",
            json.dumps(data),
            ex=self._ttl,
        )
        response.set_cookie(
            _COOKIE_NAME,
            session_id,
            httponly=True,
            samesite="lax",
            secure=not self._debug,
            max_age=self._ttl,
        )
        return TokenResponse()

    async def revoke_token(
        self,
        request: Request,
        response: Response,
        refresh_tok: str | None,
    ) -> None:
        session_id = request.cookies.get(_COOKIE_NAME)
        if session_id:
            await self._redis.delete(f"{_SESSION_PREFIX}{session_id}")
        response.delete_cookie(_COOKIE_NAME)

    async def refresh_token(self, refresh_tok: str) -> TokenResponse:
        raise HTTPException(
            status_code=501,
            detail="Session auth does not support token refresh",
        )
