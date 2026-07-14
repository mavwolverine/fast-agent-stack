"""Admin lifespan hook — mounts SQLAdmin on the FastAPI app (ADR-007, ADR-049, I3, I9)."""

from __future__ import annotations

import logging
from types import TracebackType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class AdminLifespanHook:
    """Mounts sqladmin on the FastAPI app at startup.

    Must be registered AFTER DatabaseLifespanHook (position 5 in I9 ordering).
    sqladmin import is deferred to __aenter__ and guarded by I3 pattern.
    Admin panel authenticates against the user table (is_staff / is_superuser) — ADR-049.
    secret_key signs the session cookie; it is not used as a login credential.
    """

    def __init__(
        self,
        fastapi_app: FastAPI,
        *,
        secret_key: str,
        title: str = "Admin",
    ) -> None:
        self._app = fastapi_app
        self._secret_key = secret_key
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
                "Database engine not initialized. Ensure DatabaseLifespanHook is registered before AdminLifespanHook in your app's lifespan hooks."
            )

        class _PasswordAuth(AuthenticationBackend):
            async def login(self, request: Request) -> bool:
                form = await request.form()
                email = str(form.get("username", ""))
                password = str(form.get("password", ""))

                from sqlalchemy import select

                from fast_agent_stack.core.auth.models import User
                from fast_agent_stack.core.auth.password import verify_password
                from fast_agent_stack.core.database import get_async_session

                async for session in get_async_session():
                    result = await session.execute(
                        select(User).where(User.email == email)
                    )
                    user = result.scalar_one_or_none()
                    if user is None or not user.is_active:
                        return False
                    ok, _ = verify_password(password, user.password_hash or "")
                    if not ok:
                        return False
                    if not user.is_staff and not user.is_superuser:
                        return False
                    request.session.update({"admin_user_id": str(user.id)})
                    return True
                return False  # pragma: no cover

            async def authenticate(self, request: Request) -> Response | bool:
                return bool(request.session.get("admin_user_id"))

            async def logout(self, request: Request) -> bool:
                request.session.clear()
                return True

        auth_backend = _PasswordAuth(secret_key=self._secret_key)

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
