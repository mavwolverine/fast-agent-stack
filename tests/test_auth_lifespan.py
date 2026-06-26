"""Auth lifespan + config tests — 5 families (B/C/A/N/F).

Tests I11 startup validation, I3 extras gates, AuthLifespanHook lifecycle.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fast_agent_stack.core.auth.backends.factory import _backend, _clear_backend, _set_backend
from fast_agent_stack.core.auth.lifespan import AuthLifespanHook
from fast_agent_stack.core.config import BaseSettings


def _settings(**kwargs: Any) -> BaseSettings:
    """Build a minimal BaseSettings bypassing env discovery."""
    defaults = {
        "app_name": "test",
        "auth_backend": "none",
    }
    defaults.update(kwargs)
    return BaseSettings.model_construct(**defaults)  # type: ignore[call-arg]


# ===========================================================================
# Family 1: Behavior
# ===========================================================================


async def test_b1_hook_no_op_when_auth_backend_none() -> None:
    s = _settings(auth_backend="none")
    hook = AuthLifespanHook(s)
    await hook.__aenter__()
    await hook.__aexit__(None, None, None)


async def test_b2_hook_sets_backend_on_enter(monkeypatch: pytest.MonkeyPatch) -> None:
    from fakeredis.aioredis import FakeRedis

    fake_redis = FakeRedis()

    def mock_from_url(url: str, **kw: Any) -> FakeRedis:
        return fake_redis

    s = BaseSettings.model_construct(
        app_name="test",
        auth_backend="jwt",
        secret_key="my-secret-key",
        redis_url="redis://localhost:6379",
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=2592000,
        session_ttl_seconds=86400,
        debug=False,
    )

    with (
        patch("redis.asyncio.from_url", side_effect=mock_from_url),
        patch("asyncio.wait_for", new=AsyncMock(return_value=True)),
    ):
        hook = AuthLifespanHook(s)  # type: ignore[arg-type]
        await hook.__aenter__()

    from fast_agent_stack.core.auth.backends.factory import _backend as b
    assert b is not None
    await hook.__aexit__(None, None, None)
    await fake_redis.aclose()


async def test_b3_hook_clears_backend_on_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    from fakeredis.aioredis import FakeRedis
    from fast_agent_stack.core.auth.backends.jwt import JWTAuthBackend

    fake_redis = FakeRedis()
    backend = JWTAuthBackend("k", 900, 2592000, fake_redis)
    _set_backend(backend)

    s = _settings(auth_backend="none")
    hook = AuthLifespanHook(s)
    # Manually install redis so exit can close it
    hook._redis = fake_redis
    await hook.__aexit__(None, None, None)

    from fast_agent_stack.core.auth.backends.factory import _backend as b
    assert b is None
    await fake_redis.aclose()


# ===========================================================================
# Family 2: Contract (LifespanHook Protocol)
# ===========================================================================


def test_c1_auth_lifespan_hook_implements_protocol() -> None:
    from fast_agent_stack.core.protocols import LifespanHook

    s = _settings()
    hook = AuthLifespanHook(s)
    assert isinstance(hook, LifespanHook)


# ===========================================================================
# Family 3: Architectural (I3, I9)
# ===========================================================================


def test_a1_i3_lifespan_gates_redis_import() -> None:
    import ast
    import pathlib

    src = (
        pathlib.Path(__file__).parent.parent
        / "fast_agent_stack" / "core" / "auth" / "lifespan.py"
    )
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
    pytest.fail("lifespan.py missing try/except ImportError guard (I3)")


# ===========================================================================
# Family 4: NFR — I11 startup validation
# ===========================================================================


def test_n1_i11_jwt_requires_secret_key() -> None:
    with pytest.raises(RuntimeError, match="secret_key"):
        BaseSettings(
            auth_backend="jwt",
            redis_url="redis://localhost:6379",
        )


def test_n2_i11_jwt_requires_redis_url() -> None:
    with pytest.raises(RuntimeError, match="redis_url"):
        BaseSettings(
            auth_backend="jwt",
            secret_key="my-secret",
        )


def test_n3_i11_session_requires_redis_url() -> None:
    with pytest.raises(RuntimeError, match="redis_url"):
        BaseSettings(auth_backend="session")


def test_n4_i11_both_requires_secret_key_and_redis_url() -> None:
    with pytest.raises(RuntimeError):
        BaseSettings(auth_backend="both")


def test_n5_settings_valid_none_auth_no_redis_needed() -> None:
    s = BaseSettings(auth_backend="none")
    assert s.auth_backend == "none"


def test_n6_settings_valid_jwt_with_all_required() -> None:
    s = BaseSettings(
        auth_backend="jwt",
        secret_key="valid-secret-key",
        redis_url="redis://localhost:6379",
    )
    assert s.auth_backend == "jwt"
    assert s.access_token_ttl_seconds == 900
    assert s.refresh_token_ttl_seconds == 2592000
    assert s.session_ttl_seconds == 86400


# ===========================================================================
# Family 5: Failure-mode
# ===========================================================================


async def test_f1_i11_redis_unreachable_raises_runtime_error() -> None:
    from fakeredis.aioredis import FakeRedis

    fake_redis = FakeRedis()

    def mock_from_url(url: str, **kw: Any) -> FakeRedis:
        return fake_redis

    s = BaseSettings.model_construct(
        app_name="test",
        auth_backend="jwt",
        secret_key="my-secret-key",
        redis_url="redis://bad-host:6379",
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=2592000,
        session_ttl_seconds=86400,
        debug=False,
    )

    with (
        patch("redis.asyncio.from_url", side_effect=mock_from_url),
        patch(
            "asyncio.wait_for",
            side_effect=asyncio.TimeoutError(),
        ),
        pytest.raises(RuntimeError, match="Cannot connect to Redis"),
    ):
        hook = AuthLifespanHook(s)  # type: ignore[arg-type]
        await hook.__aenter__()

    await fake_redis.aclose()
