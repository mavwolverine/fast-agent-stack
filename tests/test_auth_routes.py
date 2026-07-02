"""Auth route integration tests — 5 families (B/C/A/N/F).

Tests the HTTP layer using httpx + FastAPI TestClient and fakeredis.
"""

from __future__ import annotations

from typing import Any

import pytest
from fakeredis.aioredis import FakeRedis
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

import fast_agent_stack.core.auth.models as _auth_mod  # noqa: F401
from fast_agent_stack.core.auth.backends.factory import get_auth_backend
from fast_agent_stack.core.auth.backends.jwt import JWTAuthBackend
from fast_agent_stack.core.auth.models import User
from fast_agent_stack.core.auth.password import hash_password
from fast_agent_stack.core.auth.routes import router as auth_router
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


@pytest.fixture
def app() -> FastAPI:
    fa = FastAPI()
    fa.include_router(auth_router)
    return fa


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def user_password() -> str:
    return "hunter2"


@pytest.fixture
async def active_user(user_password: str) -> User:
    async for session in get_async_session():
        user = User(
            email="alice@example.com",
            password_hash=hash_password(user_password),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    raise RuntimeError("unreachable")


# ===========================================================================
# Family 1: Behavior
# ===========================================================================


async def test_b1_login_success_returns_tokens(
    client: AsyncClient, active_user: User, user_password: str
) -> None:
    resp = await client.post("/auth/token", json={"email": "alice@example.com", "password": user_password})
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] is not None
    assert data["refresh_token"] is not None
    assert data["token_type"] == "bearer"


async def test_b2_login_wrong_password_returns_401(
    client: AsyncClient, active_user: User
) -> None:
    resp = await client.post("/auth/token", json={"email": "alice@example.com", "password": "wrong"})
    assert resp.status_code == 401


async def test_b3_login_unknown_email_returns_401(
    client: AsyncClient,
) -> None:
    resp = await client.post("/auth/token", json={"email": "nobody@x.com", "password": "x"})
    assert resp.status_code == 401


async def test_b4_refresh_valid_token_returns_new_pair(
    client: AsyncClient, active_user: User, user_password: str
) -> None:
    login = await client.post("/auth/token", json={"email": "alice@example.com", "password": user_password})
    refresh_tok = login.json()["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_tok})
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] is not None
    assert data["refresh_token"] != refresh_tok  # rotated


async def test_b5_logout_returns_204(
    client: AsyncClient, active_user: User, user_password: str
) -> None:
    login = await client.post("/auth/token", json={"email": "alice@example.com", "password": user_password})
    refresh_tok = login.json()["refresh_token"]
    resp = await client.post("/auth/logout", json={"refresh_token": refresh_tok})
    assert resp.status_code == 204


async def test_b6_logout_invalidates_refresh_token(
    client: AsyncClient, active_user: User, user_password: str
) -> None:
    login = await client.post("/auth/token", json={"email": "alice@example.com", "password": user_password})
    refresh_tok = login.json()["refresh_token"]
    await client.post("/auth/logout", json={"refresh_token": refresh_tok})
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_tok})
    assert resp.status_code == 401


async def test_b7_verification_routes_are_registered(client: AsyncClient) -> None:
    for path in ["/auth/send-verification", "/auth/verify-email",
                 "/auth/forgot-password", "/auth/reset-password"]:
        resp = await client.post(path)
        assert resp.status_code != 404, f"{path} must be a registered route"


# ===========================================================================
# Family 2: Contract
# ===========================================================================


async def test_c1_login_response_matches_token_response_schema(
    client: AsyncClient, active_user: User, user_password: str
) -> None:
    resp = await client.post("/auth/token", json={"email": "alice@example.com", "password": user_password})
    data = resp.json()
    assert "access_token" in data
    assert "token_type" in data


async def test_c2_refresh_response_matches_schema(
    client: AsyncClient, active_user: User, user_password: str
) -> None:
    login = await client.post("/auth/token", json={"email": "alice@example.com", "password": user_password})
    resp = await client.post("/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    data = resp.json()
    assert "access_token" in data


# ===========================================================================
# Family 3: Architectural
# ===========================================================================


async def test_a1_login_uses_get_async_session(
    client: AsyncClient, active_user: User, user_password: str
) -> None:
    """Route must hit the DB — proves get_async_session is wired."""
    resp = await client.post("/auth/token", json={"email": "alice@example.com", "password": user_password})
    assert resp.status_code == 200


async def test_a2_logout_with_no_body_returns_204(
    client: AsyncClient,
) -> None:
    resp = await client.post("/auth/logout", json={})
    assert resp.status_code == 204


# ===========================================================================
# Family 4: NFR
# ===========================================================================


async def test_n1_login_inactive_user_returns_401(
    client: AsyncClient, user_password: str
) -> None:
    async for session in get_async_session():
        user = User(
            email="inactive@example.com",
            password_hash=hash_password(user_password),
            is_active=False,
        )
        session.add(user)
        await session.commit()
        break
    resp = await client.post(
        "/auth/token", json={"email": "inactive@example.com", "password": user_password}
    )
    assert resp.status_code == 401


# ===========================================================================
# Family 5: Failure-mode
# ===========================================================================


async def test_f1_refresh_invalid_token_returns_401(client: AsyncClient) -> None:
    resp = await client.post("/auth/refresh", json={"refresh_token": "bogus-token"})
    assert resp.status_code == 401


async def test_f2_double_logout_is_idempotent(
    client: AsyncClient, active_user: User, user_password: str
) -> None:
    login = await client.post("/auth/token", json={"email": "alice@example.com", "password": user_password})
    refresh_tok = login.json()["refresh_token"]
    r1 = await client.post("/auth/logout", json={"refresh_token": refresh_tok})
    r2 = await client.post("/auth/logout", json={"refresh_token": refresh_tok})
    assert r1.status_code == 204
    assert r2.status_code == 204  # idempotent per S12
