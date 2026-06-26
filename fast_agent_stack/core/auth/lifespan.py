"""Auth lifespan hook — Redis init + backend construction (I9, I11, ADR-032)."""

from __future__ import annotations

import asyncio
from types import TracebackType

from fast_agent_stack.core.config import BaseSettings


class AuthLifespanHook:
    """Initialises the auth backend and Redis client at application startup."""

    def __init__(self, settings: BaseSettings) -> None:
        self._settings = settings
        self._redis: object | None = None

    async def __aenter__(self) -> None:
        if self._settings.auth_backend == "none":
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
                "redis_url must be set when auth_backend is not 'none' (I11)"
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

    def _install_backend(self, redis: object) -> None:
        from fast_agent_stack.core.auth.backends.factory import _set_backend
        from fast_agent_stack.core.auth.backends.jwt import JWTAuthBackend
        from fast_agent_stack.core.auth.backends.session import SessionAuthBackend
        from fast_agent_stack.core.auth.backends.combined import CombinedAuthBackend

        s = self._settings
        backend_type = s.auth_backend

        if backend_type == "jwt":
            assert s.secret_key is not None
            _set_backend(JWTAuthBackend(
                secret_key=s.secret_key,
                access_ttl=s.access_token_ttl_seconds,
                refresh_ttl=s.refresh_token_ttl_seconds,
                redis=redis,  # type: ignore[arg-type]
            ))
        elif backend_type == "session":
            _set_backend(SessionAuthBackend(
                session_ttl=s.session_ttl_seconds,
                redis=redis,  # type: ignore[arg-type]
                debug=s.debug,
            ))
        elif backend_type == "both":
            assert s.secret_key is not None
            jwt_b = JWTAuthBackend(
                secret_key=s.secret_key,
                access_ttl=s.access_token_ttl_seconds,
                refresh_ttl=s.refresh_token_ttl_seconds,
                redis=redis,  # type: ignore[arg-type]
            )
            session_b = SessionAuthBackend(
                session_ttl=s.session_ttl_seconds,
                redis=redis,  # type: ignore[arg-type]
                debug=s.debug,
            )
            _set_backend(CombinedAuthBackend(jwt=jwt_b, session=session_b))

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        from fast_agent_stack.core.auth.backends.factory import _clear_backend

        _clear_backend()
        if self._redis is not None:
            await self._redis.aclose()  # type: ignore[attr-defined]
            self._redis = None
