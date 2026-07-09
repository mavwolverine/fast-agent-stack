"""Auth backend tests — 5 families (B/C/A/N/F).

Uses fakeredis for in-process Redis emulation; no running Redis required.
"""

from __future__ import annotations

import ast
import json
import pathlib
import uuid
from typing import Any

import pytest
from fakeredis.aioredis import FakeRedis
from fastapi import Request

import fast_agent_stack.core.auth.models as _auth_mod  # noqa: F401 — registers on Base.metadata
from fast_agent_stack.core.auth.backends import AuthBackend, TokenResponse
from fast_agent_stack.core.auth.backends.jwt import _REFRESH_PREFIX, JWTAuthBackend
from fast_agent_stack.core.auth.backends.session import (
    _COOKIE_NAME,
    _SESSION_PREFIX,
    SessionAuthBackend,
)
from fast_agent_stack.core.auth.models import User
from fast_agent_stack.core.auth.tokens import create_access_token, decode_access_token
from fast_agent_stack.core.database import (
    Base,
    configure_engine,
    dispose_engine,
    get_async_session,
    get_engine,
)

SQLITE_URL = "sqlite+aiosqlite:///:memory:"
_SECRET = "test-secret-key-long-enough-for-hs256"
_TTL_ACCESS = 900
_TTL_REFRESH = 2592000
_TTL_SESSION = 86400


def _make_request(
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
) -> Request:
    raw_headers: list[tuple[bytes, bytes]] = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    if cookies:
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        raw_headers.append((b"cookie", cookie_str.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": raw_headers,
    }
    return Request(scope)  # type: ignore[arg-type]


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
async def active_user() -> User:
    from fast_agent_stack.core.auth.password import hash_password

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


@pytest.fixture
def jwt_backend(redis: FakeRedis) -> JWTAuthBackend:
    return JWTAuthBackend(
        secret_key=_SECRET,
        access_ttl=_TTL_ACCESS,
        refresh_ttl=_TTL_REFRESH,
        redis=redis,
    )


@pytest.fixture
def session_backend(redis: FakeRedis) -> SessionAuthBackend:
    return SessionAuthBackend(session_ttl=_TTL_SESSION, redis=redis, debug=True)


# ── helpers ─────────────────────────────────────────────────────────────────


class _MockResponse:
    def __init__(self) -> None:
        self.cookies: dict[str, Any] = {}
        self.deleted_cookies: list[str] = []

    def set_cookie(self, key: str, value: str, **kwargs: Any) -> None:
        self.cookies[key] = {"value": value, **kwargs}

    def delete_cookie(self, key: str) -> None:
        self.deleted_cookies.append(key)


# ===========================================================================
# Family 1: Behavior
# ===========================================================================


async def test_b1_jwt_create_token_returns_both_tokens(jwt_backend: JWTAuthBackend, active_user: User) -> None:
    resp = _MockResponse()
    result = await jwt_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    assert result.access_token is not None
    assert result.refresh_token is not None
    assert result.token_type == "bearer"


async def test_b2_jwt_authenticate_valid_bearer(jwt_backend: JWTAuthBackend, active_user: User) -> None:
    resp = _MockResponse()
    tokens = await jwt_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    req = _make_request({"Authorization": f"Bearer {tokens.access_token}"})
    user_id = await jwt_backend.authenticate(req)
    assert user_id == active_user.id


async def test_b3_jwt_authenticate_missing_header_returns_none(
    jwt_backend: JWTAuthBackend,
) -> None:
    req = _make_request()
    assert await jwt_backend.authenticate(req) is None


async def test_b4_jwt_refresh_issues_new_pair(jwt_backend: JWTAuthBackend, active_user: User) -> None:
    resp = _MockResponse()
    tokens = await jwt_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    new_tokens = await jwt_backend.refresh_token(tokens.refresh_token or "")
    assert new_tokens.access_token is not None
    assert new_tokens.refresh_token != tokens.refresh_token  # rotated


async def test_b5_jwt_refresh_deletes_old_key(
    jwt_backend: JWTAuthBackend, active_user: User, redis: FakeRedis
) -> None:
    resp = _MockResponse()
    tokens = await jwt_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    old_refresh = tokens.refresh_token or ""
    await jwt_backend.refresh_token(old_refresh)
    assert await redis.get(f"{_REFRESH_PREFIX}{old_refresh}") is None


async def test_b6_jwt_logout_deletes_refresh_token(
    jwt_backend: JWTAuthBackend, active_user: User, redis: FakeRedis
) -> None:
    resp = _MockResponse()
    tokens = await jwt_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    refresh_tok = tokens.refresh_token or ""
    req = _make_request()
    await jwt_backend.revoke_token(req, resp, refresh_tok)  # type: ignore[arg-type]
    assert await redis.get(f"{_REFRESH_PREFIX}{refresh_tok}") is None


async def test_b7_session_create_sets_cookie(
    session_backend: SessionAuthBackend, active_user: User, redis: FakeRedis
) -> None:
    resp = _MockResponse()
    await session_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    assert _COOKIE_NAME in resp.cookies
    session_id = resp.cookies[_COOKIE_NAME]["value"]
    raw = await redis.get(f"{_SESSION_PREFIX}{session_id}")
    assert raw is not None
    data = json.loads(raw)
    assert data["user_id"] == str(active_user.id)


async def test_b8_session_authenticate_valid_cookie(session_backend: SessionAuthBackend, active_user: User) -> None:
    resp = _MockResponse()
    await session_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    session_id = resp.cookies[_COOKIE_NAME]["value"]
    req = _make_request(cookies={_COOKIE_NAME: session_id})
    user_id = await session_backend.authenticate(req)
    assert user_id == active_user.id


async def test_b9_session_logout_deletes_key_and_cookie(
    session_backend: SessionAuthBackend, active_user: User, redis: FakeRedis
) -> None:
    resp = _MockResponse()
    await session_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    session_id = resp.cookies[_COOKIE_NAME]["value"]
    req = _make_request(cookies={_COOKIE_NAME: session_id})
    out_resp = _MockResponse()
    await session_backend.revoke_token(req, out_resp, None)  # type: ignore[arg-type]
    assert await redis.get(f"{_SESSION_PREFIX}{session_id}") is None
    assert _COOKIE_NAME in out_resp.deleted_cookies


async def test_b10_chain_tries_jwt_then_session(
    jwt_backend: JWTAuthBackend,
    session_backend: SessionAuthBackend,
    active_user: User,
) -> None:
    from fast_agent_stack.core.auth.backends.factory import _AuthBackendChain

    chain = _AuthBackendChain([jwt_backend, session_backend])
    # Session-only request — JWT returns None, chain falls through to session
    resp = _MockResponse()
    await session_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    session_id = resp.cookies[_COOKIE_NAME]["value"]
    req = _make_request(cookies={_COOKIE_NAME: session_id})
    user_id = await chain.authenticate(req)
    assert user_id == active_user.id


# ===========================================================================
# Family 2: Contract (I1 — Protocol conformance)
# ===========================================================================


def test_c1_jwt_backend_implements_auth_backend_protocol(
    jwt_backend: JWTAuthBackend,
) -> None:
    assert isinstance(jwt_backend, AuthBackend)


def test_c2_session_backend_implements_auth_backend_protocol(
    session_backend: SessionAuthBackend,
) -> None:
    assert isinstance(session_backend, AuthBackend)


def test_c3_chain_implements_auth_backend_protocol(
    jwt_backend: JWTAuthBackend,
    session_backend: SessionAuthBackend,
) -> None:
    from fast_agent_stack.core.auth.backends.factory import _AuthBackendChain

    chain = _AuthBackendChain([jwt_backend, session_backend])
    assert isinstance(chain, AuthBackend)


def test_c4_token_response_is_pydantic_model() -> None:
    t = TokenResponse(access_token="x", token_type="bearer", refresh_token="y")
    assert t.access_token == "x"
    assert t.refresh_token == "y"


# ===========================================================================
# Family 3: Architectural
# ===========================================================================


def test_a1_i3_jwt_module_has_extras_gate() -> None:
    """tokens.py must guard pyjwt behind a try/except ImportError (I3)."""
    src = pathlib.Path(__file__).parent.parent / "fast_agent_stack" / "core" / "auth" / "tokens.py"
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
    pytest.fail("tokens.py missing try/except ImportError guard (I3)")


def test_a2_i3_session_module_has_extras_gate() -> None:
    """session.py must guard redis behind a try/except ImportError (I3)."""
    src = pathlib.Path(__file__).parent.parent / "fast_agent_stack" / "core" / "auth" / "backends" / "session.py"
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
    pytest.fail("session.py missing try/except ImportError guard (I3)")


def test_a3_adr033_jwt_refresh_prefix() -> None:
    assert _REFRESH_PREFIX == "fas:refresh:"


def test_a4_adr033_session_prefix() -> None:
    assert _SESSION_PREFIX == "fas:session:"


def test_a5_adr032_cookie_name() -> None:
    assert _COOKIE_NAME == "fas_session"


def test_a6_i12_no_internal_db_imports() -> None:
    """auth/backends must not import from core.database internals (I12)."""
    backends_dir = pathlib.Path(__file__).parent.parent / "fast_agent_stack" / "core" / "auth" / "backends"
    forbidden = {"core.database.session", "core.database.base", "core.database.health"}
    for py_file in backends_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for banned in forbidden:
                    if banned in node.module:
                        pytest.fail(f"{py_file.name} imports from internal module {node.module!r} (I12)")


def test_a7_adr032_session_cookie_is_httponly(session_backend: SessionAuthBackend, active_user: User) -> None:
    import asyncio

    resp = _MockResponse()
    asyncio.get_event_loop().run_until_complete(
        session_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    )
    assert resp.cookies[_COOKIE_NAME]["httponly"] is True
    assert resp.cookies[_COOKIE_NAME]["samesite"] == "lax"


# ===========================================================================
# Family 4: NFR
# ===========================================================================


async def test_n1_access_token_ttl_reflected_in_exp(jwt_backend: JWTAuthBackend, active_user: User) -> None:
    resp = _MockResponse()
    tokens = await jwt_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    payload = decode_access_token(tokens.access_token or "", _SECRET)

    exp = int(payload["exp"])  # type: ignore[arg-type]
    iat = int(payload["iat"])  # type: ignore[arg-type]
    assert abs((exp - iat) - _TTL_ACCESS) <= 2


async def test_n2_refresh_token_ttl_set_in_redis(
    jwt_backend: JWTAuthBackend, active_user: User, redis: FakeRedis
) -> None:
    resp = _MockResponse()
    tokens = await jwt_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    ttl = await redis.ttl(f"{_REFRESH_PREFIX}{tokens.refresh_token}")
    assert abs(ttl - _TTL_REFRESH) <= 2


async def test_n3_session_ttl_reset_on_authenticate(
    session_backend: SessionAuthBackend, active_user: User, redis: FakeRedis
) -> None:
    resp = _MockResponse()
    await session_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    session_id = resp.cookies[_COOKIE_NAME]["value"]
    key = f"{_SESSION_PREFIX}{session_id}"
    # Manually reduce TTL
    await redis.expire(key, 100)
    assert (await redis.ttl(key)) <= 101
    # Authenticate resets TTL to full
    req = _make_request(cookies={_COOKIE_NAME: session_id})
    await session_backend.authenticate(req)
    new_ttl = await redis.ttl(key)
    assert abs(new_ttl - _TTL_SESSION) <= 2


# ===========================================================================
# Family 5: Failure-mode
# ===========================================================================


async def test_f1_jwt_expired_token_raises_401() -> None:
    from fast_agent_stack.core.auth.tokens import decode_access_token as _decode

    token, _ = create_access_token(uuid.uuid4(), _SECRET, -1)  # already expired
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _decode(token, _SECRET)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


async def test_f2_jwt_malformed_token_raises_401() -> None:
    from fastapi import HTTPException

    from fast_agent_stack.core.auth.tokens import decode_access_token as _decode

    with pytest.raises(HTTPException) as exc:
        _decode("not.a.jwt", _SECRET)
    assert exc.value.status_code == 401


async def test_f3_jwt_refresh_invalid_token_raises_401(
    jwt_backend: JWTAuthBackend,
) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await jwt_backend.refresh_token("nonexistent-token")
    assert exc.value.status_code == 401


async def test_f4_session_missing_cookie_returns_none(
    session_backend: SessionAuthBackend,
) -> None:
    req = _make_request()
    assert await session_backend.authenticate(req) is None


async def test_f5_session_stale_key_returns_none(
    session_backend: SessionAuthBackend, active_user: User, redis: FakeRedis
) -> None:
    resp = _MockResponse()
    await session_backend.create_token(active_user, resp)  # type: ignore[arg-type]
    session_id = resp.cookies[_COOKIE_NAME]["value"]
    await redis.delete(f"{_SESSION_PREFIX}{session_id}")
    req = _make_request(cookies={_COOKIE_NAME: session_id})
    assert await session_backend.authenticate(req) is None


async def test_f6_session_refresh_raises_501(
    session_backend: SessionAuthBackend,
) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await session_backend.refresh_token("whatever")
    assert exc.value.status_code == 501
