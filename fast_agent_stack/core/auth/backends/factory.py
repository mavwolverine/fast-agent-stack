"""Auth backend per-request factory and FastAPI dependency (ADR-008, ADR-034)."""

from __future__ import annotations

import importlib
import uuid

from fastapi import Depends, Request, Response

from fast_agent_stack.core.auth.backends import AuthBackend, TokenResponse
from fast_agent_stack.core.config import BaseSettings

try:
    from redis.asyncio import Redis as _Redis
    from redis_fastapi import AsyncRedisDep
except ImportError:
    raise ImportError(
        "fastapi-redis-sdk is required for authentication. Install it with: pip install fast-agent-stack[auth-jwt]"
    )

_stored_settings: BaseSettings | None = None


def _set_backend_settings(settings: BaseSettings) -> None:
    global _stored_settings
    _stored_settings = settings


def _clear_backend_settings() -> None:
    global _stored_settings
    _stored_settings = None


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


async def get_auth_backend(
    redis: _Redis = Depends(AsyncRedisDep),  # type: ignore[assignment]
) -> AuthBackend:
    """Per-request factory — builds auth backend instances with the injected Redis client."""
    if _stored_settings is None:
        raise RuntimeError(
            "Auth backend not initialised. Ensure AuthLifespanHook is registered before requests are served (I9)."
        )
    s = _stored_settings
    from fast_agent_stack.core.auth.backends.jwt import JWTAuthBackend
    from fast_agent_stack.core.auth.backends.session import SessionAuthBackend

    backends: list[AuthBackend] = []
    for name in s.auth_backends:
        if name == "jwt":
            assert s.secret_key is not None
            backends.append(
                JWTAuthBackend(
                    secret_key=s.secret_key,
                    access_ttl=s.access_token_ttl_seconds,
                    refresh_ttl=s.refresh_token_ttl_seconds,
                    redis=redis,  # type: ignore[arg-type]
                )
            )
        elif name == "session":
            backends.append(
                SessionAuthBackend(
                    session_ttl=s.session_ttl_seconds,
                    redis=redis,  # type: ignore[arg-type]
                    debug=s.debug,
                )
            )
        else:
            # Custom dotted-path backend (ADR-034)
            module_path, cls_name = name.rsplit(".", 1)
            module = importlib.import_module(module_path)
            backends.append(getattr(module, cls_name)())

    if len(backends) == 1:
        return backends[0]
    return _AuthBackendChain(backends)  # type: ignore[return-value]


__all__ = ["get_auth_backend", "_set_backend_settings", "_clear_backend_settings"]
