"""Auth hardening tests — JTI denylist, API keys, Redis health, Admin (5 families).

Uses fakeredis for Redis; no live Redis or admin server required.
"""

from __future__ import annotations

import ast
import hashlib
import pathlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import fast_agent_stack.core.auth.models as _auth_mod  # noqa: F401
from fast_agent_stack.core.auth.api_keys import (
    authenticate_api_key,
    generate_api_key,
    hash_api_key,
)
from fast_agent_stack.core.auth.api_keys import (
    router as api_keys_router,
)
from fast_agent_stack.core.auth.backends.factory import get_auth_backend
from fast_agent_stack.core.auth.backends.jwt import (
    _DENYLIST_PREFIX,
    _REFRESH_PREFIX,
    JWTAuthBackend,
)
from fast_agent_stack.core.auth.models import ApiKey, User
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
from fast_agent_stack.core.health import check_redis

SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SECRET = "test-secret-key-long-enough-for-hs256"
_TTL_ACCESS = 900
_TTL_REFRESH = 2592000


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


@pytest.fixture
def app() -> FastAPI:
    fa = FastAPI()
    fa.include_router(auth_router)
    fa.include_router(api_keys_router)
    return fa


@pytest.fixture(autouse=True)
async def setup_backend(app: FastAPI, redis: FakeRedis) -> Any:
    """Wire a JWTAuthBackend with fakeredis via dependency override (ADR-037 migration)."""
    backend = JWTAuthBackend(
        secret_key=_SECRET,
        access_ttl=_TTL_ACCESS,
        refresh_ttl=_TTL_REFRESH,
        redis=redis,
    )

    async def _override() -> JWTAuthBackend:
        return backend

    app.dependency_overrides[get_auth_backend] = _override
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def active_user() -> User:
    async for session in get_async_session():
        user = User(
            email="alice@example.com",
            password_hash=hash_password("secret"),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    raise RuntimeError("unreachable")


def _bearer_for(user_id: uuid.UUID, ttl: int = _TTL_ACCESS) -> tuple[str, str]:
    """Return (header_value, jti)."""
    token, jti = create_access_token(user_id, _SECRET, ttl)
    return f"Bearer {token}", jti


async def _login(client: AsyncClient) -> tuple[str, str]:
    resp = await client.post("/auth/token", json={"email": "alice@example.com", "password": "secret"})
    data = resp.json()
    return data["access_token"], data["refresh_token"]


# ===========================================================================
# Family 1: Behavior
# ===========================================================================


async def test_b1_jti_written_to_denylist_on_logout(client: AsyncClient, active_user: User, redis: FakeRedis) -> None:
    access_tok, refresh_tok = await _login(client)
    resp = await client.post(
        "/auth/logout",
        json={"refresh_token": refresh_tok},
        headers={"Authorization": f"Bearer {access_tok}"},
    )
    assert resp.status_code == 204
    # refresh key must be gone
    assert await redis.get(f"{_REFRESH_PREFIX}{refresh_tok}") is None
    # at least one denylist key must exist
    keys = await redis.keys(f"{_DENYLIST_PREFIX}*")
    assert len(keys) == 1


async def test_b2_revoked_jti_rejected_on_subsequent_request(
    client: AsyncClient, active_user: User, redis: FakeRedis
) -> None:
    access_tok, refresh_tok = await _login(client)
    # Log out — writes JTI to denylist
    await client.post(
        "/auth/logout",
        json={"refresh_token": refresh_tok},
        headers={"Authorization": f"Bearer {access_tok}"},
    )
    # Re-use the same access token
    resp = await client.get(
        "/api-keys",
        headers={"Authorization": f"Bearer {access_tok}"},
    )
    assert resp.status_code == 401


async def test_b3_api_key_creation_returns_full_key_once(client: AsyncClient, active_user: User) -> None:
    bearer, _ = _bearer_for(active_user.id)
    resp = await client.post(
        "/api-keys",
        json={"name": "test-key"},
        headers={"Authorization": bearer},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "key" in data
    assert data["key"].startswith("fas_")
    assert "key_hash" not in data


async def test_b4_get_api_keys_has_no_key_field(client: AsyncClient, active_user: User) -> None:
    bearer, _ = _bearer_for(active_user.id)
    await client.post("/api-keys", json={"name": "k"}, headers={"Authorization": bearer})
    resp = await client.get("/api-keys", headers={"Authorization": bearer})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert "key" not in items[0]
    assert "key_hash" not in items[0]


async def test_b5_authenticate_api_key_updates_last_used_at(client: AsyncClient, active_user: User) -> None:
    bearer, _ = _bearer_for(active_user.id)
    create_resp = await client.post("/api-keys", json={"name": "test"}, headers={"Authorization": bearer})
    assert create_resp.status_code == 201
    full_key = create_resp.json()["key"]

    # authenticate_api_key uses the same shared `:memory:` connection pool
    async for session in get_async_session():
        result = await authenticate_api_key(full_key, session)
        assert result is not None
        assert result.last_used_at is not None
        break


async def test_b6_revoke_sets_revoked_at_not_delete(client: AsyncClient, active_user: User) -> None:
    bearer, _ = _bearer_for(active_user.id)
    create_resp = await client.post("/api-keys", json={"name": "rev-key"}, headers={"Authorization": bearer})
    key_id = create_resp.json()["id"]
    rev_resp = await client.post(f"/api-keys/{key_id}/revoke", headers={"Authorization": bearer})
    assert rev_resp.status_code == 204

    # Row still exists with revoked_at set
    async for session in get_async_session():
        from sqlalchemy import select as _select

        result = await session.execute(_select(ApiKey).where(ApiKey.id == uuid.UUID(key_id)))
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.revoked_at is not None
        break


async def test_b7_health_ready_includes_redis_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_check(request: Any = None) -> tuple[bool, str]:
        return True, "ok"

    from fast_agent_stack.core import health as _health_mod

    monkeypatch.setattr(_health_mod, "check_redis", _fake_check)

    app = FastAPI()
    from fast_agent_stack.core.health import router as health_router

    app.include_router(health_router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["redis"] == "ok"


# ===========================================================================
# Family 2: Contract
# ===========================================================================


def test_c1_api_key_created_response_has_no_key_hash_field() -> None:
    from fast_agent_stack.core.auth.api_keys import ApiKeyCreatedResponse

    fields = ApiKeyCreatedResponse.model_fields
    assert "key_hash" not in fields
    assert "key" in fields


def test_c2_api_key_list_item_has_no_key_or_key_hash_field() -> None:
    from fast_agent_stack.core.auth.api_keys import ApiKeyListItem

    fields = ApiKeyListItem.model_fields
    assert "key" not in fields
    assert "key_hash" not in fields


def test_c3_jti_denylist_prefix_matches_adr033() -> None:
    assert _DENYLIST_PREFIX == "fas:jti:deny:"


def test_c4_api_key_format_matches_adr031() -> None:
    full_key, key_hash, key_prefix = generate_api_key()
    assert full_key.startswith("fas_")
    assert len(full_key) == 47  # 4 + 43 chars
    assert key_prefix == full_key[:8]
    assert len(key_hash) == 64  # SHA-256 hex


def test_c5_hash_api_key_is_sha256() -> None:
    raw = "fas_test"
    expected = hashlib.sha256(raw.encode()).hexdigest()
    assert hash_api_key(raw) == expected


# ===========================================================================
# Family 3: Architectural
# ===========================================================================


def test_a1_i3_admin_lifespan_has_import_guard() -> None:
    src = pathlib.Path(__file__).parent.parent / "fast_agent_stack" / "core" / "admin" / "lifespan.py"
    tree = ast.parse(src.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if (
                    handler.type is not None
                    and isinstance(handler.type, ast.Name)
                    and handler.type.id == "ImportError"
                ):
                    return
    pytest.fail("admin/lifespan.py missing try/except ImportError guard (I3)")


def test_a2_i3_admin_views_has_import_guard() -> None:
    src = pathlib.Path(__file__).parent.parent / "fast_agent_stack" / "core" / "admin" / "views.py"
    tree = ast.parse(src.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if (
                    handler.type is not None
                    and isinstance(handler.type, ast.Name)
                    and handler.type.id == "ImportError"
                ):
                    return
    pytest.fail("admin/views.py missing try/except ImportError guard (I3)")


def test_a3_i12_admin_no_internal_db_imports() -> None:
    admin_dir = pathlib.Path(__file__).parent.parent / "fast_agent_stack" / "core" / "admin"
    forbidden = {"core.database.session", "core.database.base"}
    for py_file in admin_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for banned in forbidden:
                    if banned in node.module:
                        pytest.fail(f"{py_file.name} imports from internal {node.module!r} (I12)")


def test_a4_admin_lifespan_hook_implements_protocol() -> None:
    from fast_agent_stack.core.admin.lifespan import AdminLifespanHook
    from fast_agent_stack.core.protocols import LifespanHook

    app = FastAPI()
    hook = AdminLifespanHook(app, secret_key="secret")
    assert isinstance(hook, LifespanHook)


def test_a5_i19_api_key_admin_excludes_key_hash() -> None:
    from fast_agent_stack.core.admin.views import ApiKeyAdmin

    excluded = getattr(ApiKeyAdmin, "form_excluded_columns", [])
    assert "key_hash" in excluded


# ===========================================================================
# Family 4: NFR
# ===========================================================================


async def test_n1_health_ready_reports_redis_down(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_check(request: Any = None) -> tuple[bool, str]:
        return False, "connection refused"

    from fast_agent_stack.core import health as _health_mod

    monkeypatch.setattr(_health_mod, "check_redis", _fake_check)

    app = FastAPI()
    from fast_agent_stack.core.health import router as health_router

    app.include_router(health_router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/health/ready")
    assert resp.status_code == 503
    assert "redis" in resp.json()


async def test_n2_check_redis_returns_ok_when_not_configured() -> None:
    ok, msg = await check_redis()  # no request → not configured → ok
    assert ok is True
    assert msg == "ok"


async def test_n3_api_key_lookup_uses_key_hash_index(client: AsyncClient, active_user: User) -> None:
    """Lookup queries by key_hash — proves indexed lookup path is exercised."""
    bearer, _ = _bearer_for(active_user.id)
    create_resp = await client.post("/api-keys", json={"name": "n3"}, headers={"Authorization": bearer})
    full_key = create_resp.json()["key"]
    expected_hash = hash_api_key(full_key)
    async for session in get_async_session():
        result = await authenticate_api_key(full_key, session)
        assert result is not None
        assert result.key_hash == expected_hash
        break


# ===========================================================================
# Family 5: Failure-mode
# ===========================================================================


async def test_f1_i17_redis_unreachable_during_denylist_check_returns_503(
    client: AsyncClient, active_user: User, redis: FakeRedis
) -> None:
    bearer, jti = _bearer_for(active_user.id)

    # Manually put something unrelated in Redis to ensure connection works,
    # then simulate a RedisError on .get()
    from redis.exceptions import ConnectionError as RedisConnError

    original_get = redis.get

    async def failing_get(key: str) -> None:
        if _DENYLIST_PREFIX in str(key):
            raise RedisConnError("simulated failure")
        return await original_get(key)

    redis.get = failing_get  # type: ignore[method-assign]

    resp = await client.get("/api-keys", headers={"Authorization": bearer})
    assert resp.status_code == 503


async def test_f2_expired_api_key_returns_none(client: AsyncClient, active_user: User) -> None:
    bearer, _ = _bearer_for(active_user.id)
    past_str = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    create_resp = await client.post(
        "/api-keys",
        json={"name": "expired", "expires_at": past_str},
        headers={"Authorization": bearer},
    )
    assert create_resp.status_code == 201
    full_key = create_resp.json()["key"]
    async for session in get_async_session():
        result = await authenticate_api_key(full_key, session)
        assert result is None
        break


async def test_f3_revoked_api_key_returns_none(client: AsyncClient, active_user: User) -> None:
    bearer, _ = _bearer_for(active_user.id)
    create_resp = await client.post("/api-keys", json={"name": "revoked"}, headers={"Authorization": bearer})
    key_id = create_resp.json()["id"]
    full_key = create_resp.json()["key"]
    # Revoke via route
    await client.post(f"/api-keys/{key_id}/revoke", headers={"Authorization": bearer})
    async for session in get_async_session():
        result = await authenticate_api_key(full_key, session)
        assert result is None
        break


async def test_f4_logout_no_auth_header_still_deletes_refresh(
    client: AsyncClient, active_user: User, redis: FakeRedis
) -> None:
    access_tok, refresh_tok = await _login(client)
    # Logout WITHOUT Authorization header — only refresh token deleted
    resp = await client.post("/auth/logout", json={"refresh_token": refresh_tok})
    assert resp.status_code == 204
    assert await redis.get(f"{_REFRESH_PREFIX}{refresh_tok}") is None
    # No denylist key should have been written
    keys = await redis.keys(f"{_DENYLIST_PREFIX}*")
    assert len(keys) == 0


async def test_f5_unknown_api_key_returns_none() -> None:
    async for session in get_async_session():
        result = await authenticate_api_key("fas_doesnotexist", session)
        assert result is None
        break


async def test_f6_delete_api_key_removes_row(client: AsyncClient, active_user: User) -> None:
    bearer, _ = _bearer_for(active_user.id)
    create_resp = await client.post("/api-keys", json={"name": "del-key"}, headers={"Authorization": bearer})
    key_id = create_resp.json()["id"]
    del_resp = await client.delete(f"/api-keys/{key_id}", headers={"Authorization": bearer})
    assert del_resp.status_code == 204

    async for session in get_async_session():
        from sqlalchemy import select as _select

        result = await session.execute(_select(ApiKey).where(ApiKey.id == uuid.UUID(key_id)))
        assert result.scalar_one_or_none() is None
        break
