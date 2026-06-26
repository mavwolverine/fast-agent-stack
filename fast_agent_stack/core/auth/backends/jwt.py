"""JWT auth backend (ADR-008, ADR-015, ADR-029, ADR-033)."""

from __future__ import annotations

import secrets
import uuid

from fastapi import HTTPException, Request, Response

from fast_agent_stack.core.auth.backends import TokenResponse
from fast_agent_stack.core.auth.tokens import create_access_token, decode_access_token

try:
    from redis.asyncio import Redis
except ImportError:
    raise ImportError(
        "redis is required for JWT authentication. "
        "Install it with: pip install fast-agent-stack[auth-jwt]"
    )

_REFRESH_PREFIX = "fas:refresh:"  # ADR-033


class JWTAuthBackend:
    def __init__(
        self,
        secret_key: str,
        access_ttl: int,
        refresh_ttl: int,
        redis: Redis,  # type: ignore[type-arg]
    ) -> None:
        self._secret_key = secret_key
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl
        self._redis = redis

    async def authenticate(self, request: Request) -> uuid.UUID | None:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        token = auth.removeprefix("Bearer ")
        payload = decode_access_token(token, self._secret_key)
        return uuid.UUID(str(payload["sub"]))

    async def create_token(self, user: object, response: Response) -> TokenResponse:
        from fast_agent_stack.core.auth.models import User as _User

        assert isinstance(user, _User)
        token, _jti = create_access_token(user.id, self._secret_key, self._access_ttl)
        refresh_tok = secrets.token_urlsafe(32)
        await self._redis.set(
            f"{_REFRESH_PREFIX}{refresh_tok}",
            str(user.id),
            ex=self._refresh_ttl,
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            refresh_token=refresh_tok,
        )

    async def revoke_token(
        self,
        request: Request,
        response: Response,
        refresh_tok: str | None,
    ) -> None:
        # Phase 3b: delete refresh token only. JTI denylist added in Phase 3c.
        if refresh_tok:
            await self._redis.delete(f"{_REFRESH_PREFIX}{refresh_tok}")

    async def refresh_token(self, refresh_tok: str) -> TokenResponse:
        raw = await self._redis.get(f"{_REFRESH_PREFIX}{refresh_tok}")
        if not raw:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
        user_id = uuid.UUID(raw.decode() if isinstance(raw, bytes) else raw)
        # Rotate: delete old, issue new
        await self._redis.delete(f"{_REFRESH_PREFIX}{refresh_tok}")
        new_refresh = secrets.token_urlsafe(32)
        await self._redis.set(
            f"{_REFRESH_PREFIX}{new_refresh}",
            str(user_id),
            ex=self._refresh_ttl,
        )
        new_access, _ = create_access_token(user_id, self._secret_key, self._access_ttl)
        return TokenResponse(
            access_token=new_access,
            token_type="bearer",
            refresh_token=new_refresh,
        )
