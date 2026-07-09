"""Admin lifespan hook — mounts SQLAdmin on the FastAPI app (ADR-007, I3, I9)."""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


class AdminLifespanHook:
    """Mounts sqladmin on the FastAPI app at startup.

    Must be registered AFTER DatabaseLifespanHook (position 5 in I9 ordering).
    sqladmin import is deferred to __aenter__ and guarded by I3 pattern.
    """

    def __init__(
        self,
        fastapi_app: FastAPI,
        *,
        admin_secret_key: str,
        title: str = "Admin",
    ) -> None:
        self._app = fastapi_app
        self._admin_secret_key = admin_secret_key
        self._title = title
        self._admin: object | None = None

    async def __aenter__(self) -> None:
        try:
            from sqladmin import Admin
            from sqladmin.authentication import AuthenticationBackend
            from starlette.requests import Request
            from starlette.responses import Response
        except ImportError:
            raise ImportError(
                "sqladmin is required for the admin panel. Install it with: pip install fast-agent-stack[admin]"
            )

        from fast_agent_stack.core.database import get_engine

        engine = get_engine()
        if engine is None:
            raise RuntimeError(
                "Database engine not initialized. DatabaseLifespanHook must run before AdminLifespanHook (I9)."
            )

        secret = self._admin_secret_key

        class _PasswordAuth(AuthenticationBackend):
            async def login(self, request: Request) -> bool:
                form = await request.form()
                password = form.get("password", "")
                if password == secret:
                    request.session.update({"admin_authenticated": True})
                    return True
                return False

            async def authenticate(self, request: Request) -> Response | bool:
                return bool(request.session.get("admin_authenticated"))

            async def logout(self, request: Request) -> bool:
                request.session.clear()
                return True

        auth_backend = _PasswordAuth(secret_key=self._admin_secret_key)

        from fast_agent_stack.core.admin.views import get_admin_views

        admin = Admin(
            self._app,
            engine,
            authentication_backend=auth_backend,
            title=self._title,
        )
        for view in get_admin_views():
            admin.add_view(view)
        self._admin = admin

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._admin = None
