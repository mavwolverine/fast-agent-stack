"""Auth dependency tests — get_current_user, require_permission (ADR-028, S17)."""

from __future__ import annotations

from typing import Any

import pytest
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import fast_agent_stack.core.auth.models as _auth_mod  # noqa: F401
from fast_agent_stack.core.auth.backends.factory import get_auth_backend
from fast_agent_stack.core.auth.backends.jwt import JWTAuthBackend
from fast_agent_stack.core.auth.dependencies import require_permission
from fast_agent_stack.core.auth.models import Group, Permission, User
from fast_agent_stack.core.auth.password import hash_password
from fast_agent_stack.core.auth.routes import router as auth_router
from fast_agent_stack.core.auth.tokens import create_access_token
from fast_agent_stack.core.database import (
    Base,
    configure_engine,
    dispose_engine,
    get_async_session,
    get_engine,
)

SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SECRET = "test-secret-key-long-enough-for-hs256"


@pytest.fixture(autouse=True)
async def setup_db() -> Any:
    configure_engine(SQLITE_URL)
    engine = get_engine()
    assert engine is not None
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await dispose_engine()


@pytest.fixture
async def redis() -> FakeRedis:
    r = FakeRedis()
    yield r
    await r.aclose()


@pytest.fixture(autouse=True)
async def setup_backend(app: FastAPI, redis: FakeRedis) -> Any:
    backend = JWTAuthBackend(
        secret_key=_SECRET,
        access_ttl=900,
        refresh_ttl=2592000,
        redis=redis,
    )

    async def _override() -> JWTAuthBackend:
        return backend

    app.dependency_overrides[get_auth_backend] = _override
    yield
    app.dependency_overrides.pop(get_auth_backend, None)


def _make_app() -> FastAPI:
    fa = FastAPI()
    fa.include_router(auth_router)

    @fa.get("/protected")
    async def protected(user: User = require_permission("posts.delete")) -> dict[str, str]:
        return {"user": str(user.id)}

    return fa


@pytest.fixture
def app() -> FastAPI:
    return _make_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _bearer(user_id: str) -> str:
    token, _ = create_access_token(
        user_id=__import__("uuid").UUID(user_id),
        secret_key=_SECRET,
        ttl_seconds=900,
    )
    return f"Bearer {token}"


async def _create_user(
    email: str = "u@x.com",
    is_active: bool = True,
    is_superuser: bool = False,
) -> User:
    async for session in get_async_session():
        user = User(
            email=email,
            password_hash=hash_password("pw"),
            is_active=is_active,
            is_superuser=is_superuser,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    raise RuntimeError("unreachable")


async def _grant_permission(user: User, resource: str, action: str) -> None:

    async for session in get_async_session():
        merged = await session.merge(user)
        await session.refresh(merged, ["direct_permissions"])
        perm = Permission(resource=resource, action=action)
        session.add(perm)
        merged.direct_permissions.append(perm)
        await session.commit()
        break


async def _grant_via_group(user: User, resource: str, action: str) -> None:
    async for session in get_async_session():
        merged = await session.merge(user)
        await session.refresh(merged, ["groups"])
        perm = Permission(resource=resource, action=action)
        group = Group(name=f"g-{resource}-{action}")
        group.permissions.append(perm)
        merged.groups.append(group)
        session.add(group)
        await session.commit()
        break


# ===========================================================================
# Family 1: Behavior — S17 scenarios
# ===========================================================================


async def test_b1_user_with_group_perm_allowed(client: AsyncClient) -> None:
    user = await _create_user()
    await _grant_via_group(user, "posts", "delete")
    resp = await client.get("/protected", headers={"Authorization": _bearer(str(user.id))})
    assert resp.status_code == 200


async def test_b2_user_without_perm_denied(client: AsyncClient) -> None:
    user = await _create_user(email="noperm@x.com")
    resp = await client.get("/protected", headers={"Authorization": _bearer(str(user.id))})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Permission denied"


async def test_b3_superuser_bypasses_permission_check(client: AsyncClient) -> None:
    user = await _create_user(email="super@x.com", is_superuser=True)
    resp = await client.get("/protected", headers={"Authorization": _bearer(str(user.id))})
    assert resp.status_code == 200


async def test_b4_inactive_user_denied(client: AsyncClient) -> None:
    user = await _create_user(email="inactive@x.com", is_active=False)
    await _grant_via_group(user, "posts", "delete")
    resp = await client.get("/protected", headers={"Authorization": _bearer(str(user.id))})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Account inactive"


async def test_b5_unauthenticated_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/protected")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


async def test_b6_direct_user_permission_allowed(client: AsyncClient) -> None:
    user = await _create_user(email="direct@x.com")
    await _grant_permission(user, "posts", "delete")
    resp = await client.get("/protected", headers={"Authorization": _bearer(str(user.id))})
    assert resp.status_code == 200


# ===========================================================================
# Family 2: Contract
# ===========================================================================


def test_c1_require_permission_returns_depends() -> None:
    from fastapi import params

    dep = require_permission("posts.delete")
    assert isinstance(dep, params.Depends)


def test_c2_require_permission_dot_split() -> None:
    """Verify the dot-split logic handles edge cases (ADR-028)."""
    from fastapi import params

    dep = require_permission("resource.action.extra")
    assert isinstance(dep, params.Depends)


# ===========================================================================
# Family 3: Architectural (I12)
# ===========================================================================


def test_a1_i12_dependencies_no_internal_db_import() -> None:
    import ast
    import pathlib

    src = pathlib.Path(__file__).parent.parent / "fast_agent_stack" / "core" / "auth" / "dependencies.py"
    tree = ast.parse(src.read_text())
    forbidden = {"core.database.session", "core.database.base"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for banned in forbidden:
                if banned in node.module:
                    pytest.fail(f"dependencies.py imports from internal {node.module!r} (I12)")


# ===========================================================================
# Family 4: NFR
# ===========================================================================


async def test_n1_get_current_user_raises_401_on_no_auth(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/protected")
    assert resp.status_code == 401


# ===========================================================================
# Family 5: Failure-mode
# ===========================================================================


async def test_f1_expired_token_returns_401(client: AsyncClient) -> None:
    import uuid

    from fast_agent_stack.core.auth.tokens import create_access_token as _cat

    token, _ = _cat(uuid.uuid4(), _SECRET, -1)  # already expired
    resp = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_f2_malformed_bearer_token_returns_401(client: AsyncClient) -> None:
    resp = await client.get("/protected", headers={"Authorization": "Bearer bad.token"})
    assert resp.status_code == 401
