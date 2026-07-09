"""Auth FastAPI dependencies — get_current_user, require_permission (ADR-028, S17)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fast_agent_stack.core.auth.backends import AuthBackend
from fast_agent_stack.core.auth.backends.factory import get_auth_backend
from fast_agent_stack.core.auth.models import Group, User
from fast_agent_stack.core.database import get_async_session


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    backend: AuthBackend = Depends(get_auth_backend),
) -> User:
    """Extract and verify the token; return the authenticated User or raise 401."""
    user_id: uuid.UUID | None = await backend.authenticate(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    result = await session.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.groups).selectinload(Group.permissions),
            selectinload(User.direct_permissions),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_permission(permission: str) -> Callable[..., object]:
    """Return a FastAPI dependency that enforces RBAC (ADR-028, S17).

    Argument is dot-separated ``"resource.action"`` (ADR-028).
    ``is_superuser`` bypasses all checks. Inactive users → 403.
    """
    resource, _, action = permission.partition(".")

    async def _check(user: User = Depends(get_current_user)) -> User:
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account inactive")
        if user.is_superuser:
            return user
        # Groups and direct_permissions loaded via selectin — no extra queries needed
        all_perms: set[tuple[str, str]] = {(p.resource, p.action) for p in user.direct_permissions}
        for group in user.groups:
            all_perms.update((p.resource, p.action) for p in group.permissions)
        if (resource, action) not in all_perms:
            raise HTTPException(status_code=403, detail="Permission denied")
        return user

    return Depends(_check)  # type: ignore[no-any-return]
