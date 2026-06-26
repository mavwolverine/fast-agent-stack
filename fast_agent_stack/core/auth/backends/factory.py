"""Auth backend singleton registry and FastAPI dependency (ADR-008)."""

from __future__ import annotations

from fast_agent_stack.core.auth.backends import AuthBackend

_backend: AuthBackend | None = None


def _set_backend(backend: AuthBackend) -> None:
    global _backend
    _backend = backend


def _clear_backend() -> None:
    global _backend
    _backend = None


def get_auth_backend() -> AuthBackend:
    """FastAPI dependency — returns the active auth backend singleton."""
    if _backend is None:
        raise RuntimeError(
            "Auth backend not initialised. "
            "Ensure AuthLifespanHook is registered before requests are served (I9)."
        )
    return _backend


__all__ = ["get_auth_backend", "_set_backend", "_clear_backend"]
