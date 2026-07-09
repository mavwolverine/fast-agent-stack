"""Auth lifespan hook — backend construction and startup validation (I9, I11, ADR-034)."""

from __future__ import annotations

from types import TracebackType

from fast_agent_stack.core.config import BaseSettings


class AuthLifespanHook:
    """Registers auth backend settings at startup; no Redis I/O (pool managed by SDK, ADR-037)."""

    def __init__(self, settings: BaseSettings) -> None:
        self._settings = settings

    async def __aenter__(self) -> None:
        if not self._settings.auth_backends:
            return
        # I11: validate required settings before serving requests
        if not self._settings.redis_url:
            raise RuntimeError("redis_url must be set when auth_backends is not empty (I11)")
        if "jwt" in self._settings.auth_backends and not self._settings.secret_key:
            raise RuntimeError("secret_key must be set when auth_backends includes 'jwt' (I11)")
        from fast_agent_stack.core.auth.backends.factory import _set_backend_settings

        _set_backend_settings(self._settings)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        from fast_agent_stack.core.auth.backends.factory import _clear_backend_settings

        _clear_backend_settings()
