"""JWT auth backend (ADR-008, ADR-015, ADR-029, ADR-033)."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, Response

from fast_agent_stack.core.auth.backends import TokenResponse
from fast_agent_stack.core.auth.tokens import create_access_token, decode_access_token

try:
    import jwt as pyjwt
    from redis.asyncio import Redis
    from redis.exceptions import RedisError
    import redis_fastapi as _redis_fastapi_check  # noqa: F401 — I3: gate on SDK presence
except ImportError:
    raise ImportError(
        "fastapi-redis-sdk is required for JWT authentication. "
        "Install it with: pip install fast-agent-stack[auth-jwt]"
    )

_REFRESH_PREFIX = "fas:refresh:"    # ADR-033
_DENYLIST_PREFIX = "fas:jti:deny:"  # ADR-033


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
        jti = str(payload.get("jti", ""))
        if jti:
            try:
                if await self._redis.get(f"{_DENYLIST_PREFIX}{jti}"):
                    raise HTTPException(status_code=401, detail="Token revoked")
            except HTTPException:
                raise
            except RedisError as exc:
                raise HTTPException(
                    status_code=503, detail="Auth service unavailable"
                ) from exc
        return uuid.UUID(str(payload["sub"]))

    async def verify_token(self, token: str) -> uuid.UUID | None:
        try:
            payload = decode_access_token(token, self._secret_key)
        except Exception:
            return None
        jti = str(payload.get("jti", ""))
        if jti:
            try:
                if await self._redis.get(f"{_DENYLIST_PREFIX}{jti}"):
                    return None
            except RedisError as exc:
                raise HTTPException(
                    status_code=503, detail="Auth service unavailable"
                ) from exc
        try:
            return uuid.UUID(str(payload["sub"]))
        except (KeyError, ValueError):
            return None

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
        # Extract JTI from Authorization header for denylist (ADR-015)
        jti: str = ""
        remaining_ttl: int = self._access_ttl  # fallback: worst-case TTL
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ")
            try:
                # Lenient decode — we want to denylist even if token is near expiry
                payload = pyjwt.decode(
                    token,
                    self._secret_key,
                    algorithms=["HS256"],
                    options={"verify_exp": False},
                )
                jti = str(payload.get("jti", ""))
                exp = int(payload.get("exp", 0))
                remaining_ttl = max(0, exp - int(datetime.now(UTC).timestamp()))
            except Exception:
                pass  # malformed token — skip denylist write

        if refresh_tok:
            await self._redis.delete(f"{_REFRESH_PREFIX}{refresh_tok}")

        if jti and remaining_ttl > 0:
            await self._redis.set(f"{_DENYLIST_PREFIX}{jti}", "1", ex=remaining_ttl)

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
