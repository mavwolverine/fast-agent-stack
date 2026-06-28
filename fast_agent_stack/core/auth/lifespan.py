"""Auth lifespan hook — Redis init + backend construction (I9, I11, ADR-032, ADR-034)."""

from __future__ import annotations

import asyncio
import uuid
from types import TracebackType
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, Response

from fast_agent_stack.core.auth.backends import AuthBackend, TokenResponse
from fast_agent_stack.core.config import BaseSettings

if TYPE_CHECKING:
    pass


class _AuthBackendChain:
    """Private chain — tries backends in order for auth; primary-only for token ops (ADR-034)."""

    def __init__(self, backends: list[AuthBackend]) -> None:
        self._backends = backends
        self._primary = backends[0]

    async def authenticate(self, request: Request) -> uuid.UUID | None:
        for backend in self._backends:
            user_id = await backend.authenticate(request)
            if user_id is not None:
                return user_id
        return None

    async def verify_token(self, token: str) -> uuid.UUID | None:
        for backend in self._backends:
            user_id = await backend.verify_token(token)
            if user_id is not None:
                return user_id
        return None

    async def create_token(self, user: object, response: Response) -> TokenResponse:
        return await self._primary.create_token(user, response)

    async def refresh_token(self, refresh_tok: str) -> TokenResponse:
        return await self._primary.refresh_token(refresh_tok)

    async def revoke_token(
        self,
        request: Request,
        response: Response,
        refresh_tok: str | None,
    ) -> None:
        # I20: revoke on ALL backends so no method remains valid after logout
        for backend in self._backends:
            await backend.revoke_token(request, response, refresh_tok)


class AuthLifespanHook:
    """Initialises the auth backend and Redis client at application startup."""

    def __init__(self, settings: BaseSettings) -> None:
        self._settings = settings
        self._redis: object | None = None

    async def __aenter__(self) -> None:
        if not self._settings.auth_backends:
            return

        # I3: gate on redis
        try:
            import redis.asyncio as aioredis
        except ImportError:
            raise ImportError(
                "redis is required for authentication. "
                "Install it with: pip install fast-agent-stack[auth-jwt]"
            )

        # I11: redis_url validated at settings construction; double-guard here for clarity
        if not self._settings.redis_url:
            raise RuntimeError(
                "redis_url must be set when auth_backends is not empty (I11)"
            )

        redis_client = aioredis.from_url(
            self._settings.redis_url, decode_responses=False
        )

        # I11: connectivity check within 5s timeout
        try:
            await asyncio.wait_for(redis_client.ping(), timeout=5.0)
        except (asyncio.TimeoutError, Exception) as exc:
            await redis_client.aclose()
            raise RuntimeError(
                f"Cannot connect to Redis at {self._settings.redis_url} "
                "— required for auth token storage (I11)"
            ) from exc

        self._redis = redis_client
        self._install_backend(redis_client)
        from fast_agent_stack.core.health import configure_redis_health
        configure_redis_health(self._settings.redis_url)

    def _install_backend(self, redis: object) -> None:
        from fast_agent_stack.core.auth.backends.factory import _set_backend
        from fast_agent_stack.core.auth.backends.jwt import JWTAuthBackend
        from fast_agent_stack.core.auth.backends.session import SessionAuthBackend

        s = self._settings
        backends: list[AuthBackend] = []

        for name in s.auth_backends:
            if name == "jwt":
                assert s.secret_key is not None
                backends.append(JWTAuthBackend(
                    secret_key=s.secret_key,
                    access_ttl=s.access_token_ttl_seconds,
                    refresh_ttl=s.refresh_token_ttl_seconds,
                    redis=redis,  # type: ignore[arg-type]
                ))
            elif name == "session":
                backends.append(SessionAuthBackend(
                    session_ttl=s.session_ttl_seconds,
                    redis=redis,  # type: ignore[arg-type]
                    debug=s.debug,
                ))
            else:
                # Custom dotted-path backend (ADR-034)
                import importlib
                module_path, cls_name = name.rsplit(".", 1)
                module = importlib.import_module(module_path)
                backends.append(getattr(module, cls_name)())

        if len(backends) == 1:
            _set_backend(backends[0])
        else:
            _set_backend(_AuthBackendChain(backends))  # type: ignore[arg-type]

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        from fast_agent_stack.core.auth.backends.factory import _clear_backend

        _clear_backend()
        from fast_agent_stack.core.health import configure_redis_health
        configure_redis_health(None)
        if self._redis is not None:
            await self._redis.aclose()  # type: ignore[attr-defined]
            self._redis = None
