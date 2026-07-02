"""Redis SDK integration tests — fastapi-redis-sdk migration (ADR-037).

5 families: Behavior, Contract, Architectural, NFR, Failure-mode.
"""
from __future__ import annotations

import ast
import pathlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

ROOT = pathlib.Path(__file__).parent.parent
CORE = ROOT / "fast_agent_stack" / "core"


def _settings(**kwargs: Any):
    from fast_agent_stack.core.config import BaseSettings

    defaults = {"app_name": "test"}
    defaults.update(kwargs)
    return BaseSettings.model_construct(**defaults)  # type: ignore[call-arg]


# ===========================================================================
# Family 1: Behavior
# ===========================================================================


def test_b1_hook_wraps_app_lifespan_at_init():
    """FastAPIRedis(app).lifespan() must be called during __init__."""
    app = FastAPI()
    s = _settings(redis_url="redis://localhost:6379")

    with patch("redis_fastapi.FastAPIRedis") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        from fast_agent_stack.core.redis import FastAPIRedisLifespanHook  # noqa: F401

        # Re-import won't re-execute module code, so instantiate directly
        import importlib, fast_agent_stack.core.redis as _redis_mod
        importlib.reload(_redis_mod)
        from fast_agent_stack.core.redis import FastAPIRedisLifespanHook

        FastAPIRedisLifespanHook(s, app=app)
        mock_cls.assert_called_once_with(app)
        mock_instance.lifespan.assert_called_once_with()


async def test_b2_hook_aenter_pings_redis_i11():
    """__aenter__ must perform the I11 connectivity check via ping."""
    app = FastAPI()
    s = _settings(redis_url="redis://localhost:6379")

    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.aclose = AsyncMock()

    with patch("redis_fastapi.FastAPIRedis"):
        from fast_agent_stack.core.redis import FastAPIRedisLifespanHook
        hook = FastAPIRedisLifespanHook(s, app=app)

    with patch("redis.asyncio.from_url", return_value=mock_client):
        result = await hook.__aenter__()

    mock_client.ping.assert_called_once()
    mock_client.aclose.assert_called_once()
    assert result is hook


async def test_b3_hook_aexit_is_noop():
    """__aexit__ must be a no-op — pool teardown is SDK-managed."""
    app = FastAPI()
    s = _settings(redis_url="redis://localhost:6379")

    with patch("redis_fastapi.FastAPIRedis"):
        from fast_agent_stack.core.redis import FastAPIRedisLifespanHook
        hook = FastAPIRedisLifespanHook(s, app=app)

    # Must not raise and must not call any redis teardown
    await hook.__aexit__(None, None, None)


async def test_b4_get_auth_backend_is_per_request_factory():
    """get_auth_backend must be callable as a FastAPI dependency (async callable)."""
    import inspect
    from fast_agent_stack.core.auth.backends.factory import get_auth_backend

    assert inspect.iscoroutinefunction(get_auth_backend), (
        "get_auth_backend must be async for FastAPI DI (ADR-037)"
    )


async def test_b5_health_check_returns_ok_when_redis_not_configured():
    """check_redis(request) must return (True, 'ok') when app.state._redis is None."""
    from fast_agent_stack.core.health import check_redis

    app = FastAPI()
    mock_request = MagicMock()
    mock_request.app.state = app.state  # no _redis set

    ok, msg = await check_redis(mock_request)
    assert ok is True
    assert msg == "ok"


async def test_b6_health_check_returns_ok_when_no_request():
    from fast_agent_stack.core.health import check_redis

    ok, msg = await check_redis(None)
    assert ok is True
    assert msg == "ok"


# ===========================================================================
# Family 2: Contract
# ===========================================================================


def test_c1_fastapi_redis_lifespan_hook_implements_protocol():
    from fast_agent_stack.core.protocols import LifespanHook
    from fast_agent_stack.core.redis import FastAPIRedisLifespanHook

    app = FastAPI()
    s = _settings(redis_url="redis://localhost:6379")

    with patch("redis_fastapi.FastAPIRedis"):
        hook = FastAPIRedisLifespanHook(s, app=app)

    assert isinstance(hook, LifespanHook)


def test_c2_rate_limit_middleware_no_redis_constructor_param():
    """RateLimitMiddleware must not accept 'redis' in __init__ (ADR-037)."""
    import inspect
    from fast_agent_stack.core.ratelimit import RateLimitMiddleware

    sig = inspect.signature(RateLimitMiddleware.__init__)
    assert "redis" not in sig.parameters


def test_c3_auth_lifespan_hook_no_redis_pool_ownership():
    """AuthLifespanHook must not have _redis or redis attributes."""
    from fast_agent_stack.core.auth.lifespan import AuthLifespanHook

    s = _settings(auth_backends=[], redis_url=None)
    hook = AuthLifespanHook(s)
    assert not hasattr(hook, "_redis")
    assert not hasattr(hook, "redis")


def test_c4_factory_exposes_get_auth_backend_in_all():
    from fast_agent_stack.core.auth.backends import factory

    assert "get_auth_backend" in (factory.__all__ or [])


# ===========================================================================
# Family 3: Architectural
# ===========================================================================


def test_a1_auth_lifespan_has_no_redis_imports():
    """lifespan.py must not import from redis.* (pool entirely SDK-managed)."""
    src = (CORE / "auth" / "lifespan.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "redis" not in node.module, (
                f"auth/lifespan.py imports from '{node.module}' — must not own Redis (ADR-037)"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert "redis" not in alias.name


def test_a2_ratelimit_has_no_redis_asyncio_direct_import():
    """ratelimit/__init__.py must not import redis.asyncio at module level (ADR-037)."""
    src = (CORE / "ratelimit" / "__init__.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        # Only bare (non-guarded) imports at module level are disallowed
    # Simpler: check no top-level (unguarded) redis.asyncio import
    for node in tree.body:  # top-level statements only
        if isinstance(node, ast.ImportFrom) and node.module and "redis" in node.module:
            pytest.fail(
                f"ratelimit/__init__.py has unguarded top-level redis import: {node.module}"
            )


def test_a3_auth_backend_chain_lives_in_factory():
    """_AuthBackendChain must be in factory.py, not lifespan.py."""
    lifespan_src = (CORE / "auth" / "lifespan.py").read_text()
    factory_src = (CORE / "auth" / "backends" / "factory.py").read_text()

    lifespan_tree = ast.parse(lifespan_src)
    factory_tree = ast.parse(factory_src)

    lifespan_classes = {n.name for n in ast.walk(lifespan_tree) if isinstance(n, ast.ClassDef)}
    factory_classes = {n.name for n in ast.walk(factory_tree) if isinstance(n, ast.ClassDef)}

    assert "_AuthBackendChain" not in lifespan_classes
    assert "_AuthBackendChain" in factory_classes


def test_a4_health_has_no_from_url_call():
    """health.py must not call redis.asyncio.from_url — uses SDK pool via request."""
    src = (CORE / "health.py").read_text()
    assert "from_url" not in src, (
        "health.py must not call from_url; use get_async_redis(request) from SDK (ADR-037)"
    )


def test_a5_factory_guards_on_redis_fastapi():
    """factory.py I3 guard must import redis_fastapi (not just redis.asyncio)."""
    src = (CORE / "auth" / "backends" / "factory.py").read_text()
    tree = ast.parse(src)

    guarded: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for child in ast.walk(node):
                if isinstance(child, ast.ImportFrom) and child.module:
                    guarded.append(child.module)
                elif isinstance(child, ast.Import):
                    for alias in child.names:
                        guarded.append(alias.name)

    assert any("redis_fastapi" in m for m in guarded), (
        "factory.py I3 guard must gate on redis_fastapi (ADR-037)"
    )


# ===========================================================================
# Family 4: NFR
# ===========================================================================


def test_n1_pyproject_auth_jwt_uses_fastapi_redis_sdk():
    import tomllib

    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    deps = data["project"]["optional-dependencies"]
    assert any("fastapi-redis-sdk" in d for d in deps.get("auth-jwt", []))


def test_n2_pyproject_auth_session_uses_fastapi_redis_sdk():
    import tomllib

    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    deps = data["project"]["optional-dependencies"]
    assert any("fastapi-redis-sdk" in d for d in deps.get("auth-session", []))


def test_n3_pyproject_rate_limit_uses_fastapi_redis_sdk():
    import tomllib

    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    deps = data["project"]["optional-dependencies"]
    assert any("fastapi-redis-sdk" in d for d in deps.get("rate-limit", []))


def test_n4_template_app_py_has_no_caching_call():
    """Template must NOT call .caching() — it is user opt-in (ADR-037)."""
    template_src = (
        ROOT / "fast_agent_stack" / "template" / "{{project_name}}" / "app.py.jinja"
    ).read_text()
    assert ".caching()" not in template_src, (
        "Template must not call .caching() — users opt in themselves (ADR-037)"
    )


def test_n5_template_redis_hook_in_conditional_block():
    """FastAPIRedisLifespanHook must only be registered when auth or rate-limit is enabled."""
    template_src = (
        ROOT / "fast_agent_stack" / "template" / "{{project_name}}" / "app.py.jinja"
    ).read_text()

    assert "FastAPIRedisLifespanHook" in template_src
    # Hook must be inside an if block, not unconditional
    lines = template_src.splitlines()
    for i, line in enumerate(lines):
        if "FastAPIRedisLifespanHook" in line and "add_lifespan_hook" in line:
            # The line (or a recent prior line) must be inside an {% if %} block
            context = "\n".join(lines[max(0, i - 5):i + 1])
            assert "{%- if include_auth or include_rate_limit %}" in context or \
                   "{% if include_auth or include_rate_limit %}" in context, (
                "FastAPIRedisLifespanHook registration must be inside conditional block"
            )


# ===========================================================================
# Family 5: Failure-mode
# ===========================================================================


def test_f1_hook_init_raises_import_error_without_sdk(monkeypatch):
    """FastAPIRedisLifespanHook.__init__ must raise ImportError when SDK absent."""
    import sys
    monkeypatch.delitem(sys.modules, "redis_fastapi", raising=False)
    monkeypatch.delitem(sys.modules, "fast_agent_stack.core.redis", raising=False)

    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "redis_fastapi":
            raise ImportError("sdk not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    import importlib
    import fast_agent_stack.core.redis as _m
    importlib.reload(_m)

    app = FastAPI()
    s = _settings(redis_url="redis://localhost:6379")
    with pytest.raises(ImportError, match="fastapi-redis-sdk"):
        _m.FastAPIRedisLifespanHook(s, app=app)


def test_f2_hook_init_raises_if_no_redis_url():
    """FastAPIRedisLifespanHook.__init__ must raise RuntimeError when redis_url is None."""
    from fast_agent_stack.core.redis import FastAPIRedisLifespanHook

    app = FastAPI()
    s = _settings(redis_url=None)

    with patch("redis_fastapi.FastAPIRedis"):
        with pytest.raises(RuntimeError, match="redis_url"):
            FastAPIRedisLifespanHook(s, app=app)


async def test_f3_hook_aenter_raises_on_unreachable_redis():
    """__aenter__ must raise RuntimeError when ping times out (I11)."""
    from fast_agent_stack.core.redis import FastAPIRedisLifespanHook

    app = FastAPI()
    s = _settings(redis_url="redis://localhost:6379")

    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(side_effect=Exception("connection refused"))
    mock_client.aclose = AsyncMock()

    with patch("redis_fastapi.FastAPIRedis"):
        hook = FastAPIRedisLifespanHook(s, app=app)

    with patch("redis.asyncio.from_url", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Cannot connect to Redis"):
            await hook.__aenter__()

    mock_client.aclose.assert_called_once()


async def test_f4_get_auth_backend_raises_before_lifespan():
    """get_auth_backend must raise RuntimeError if called before AuthLifespanHook enters."""
    from fast_agent_stack.core.auth.backends import factory as _factory

    # Ensure clean state
    _factory._stored_settings = None

    mock_redis = AsyncMock()
    with pytest.raises(RuntimeError, match="not initialised"):
        await _factory.get_auth_backend(redis=mock_redis)


async def test_f5_check_redis_returns_false_on_ping_error():
    """check_redis must return (False, error_msg) when ping fails (I13)."""
    from fast_agent_stack.core.health import check_redis

    app = FastAPI()
    mock_pool_state = MagicMock()
    app.state._redis = mock_pool_state  # type: ignore[attr-defined]

    mock_request = MagicMock()
    mock_request.app = app

    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(side_effect=Exception("redis down"))

    with patch("redis_fastapi.deps.get_async_redis", return_value=mock_client):
        ok, msg = await check_redis(mock_request)

    assert ok is False
    assert "redis down" in msg
