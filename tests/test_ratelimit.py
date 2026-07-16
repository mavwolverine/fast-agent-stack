"""Tests for Phase 6-2 / Phase 8: Rate Limiting (ADR-016, ADR-037)."""

from __future__ import annotations

import ast
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient


def _make_app(requests: int = 5, period: int = 60, eval_return: int = 1):
    """Build a minimal FastAPI app with RateLimitMiddleware using a mocked SDK redis."""
    import fastapi

    from fast_agent_stack.core.ratelimit import RateLimitMiddleware

    app = fastapi.FastAPI()

    mock_redis = AsyncMock()
    mock_redis.eval = AsyncMock(return_value=eval_return)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    app.add_middleware(
        RateLimitMiddleware,
        requests=requests,
        period=period,
    )
    return app, mock_redis


# ---------------------------------------------------------------------------
# BEHAVIOR
# ---------------------------------------------------------------------------


async def test_rate_limit_allows_requests_below_threshold():
    app, mock_redis = _make_app(requests=5, eval_return=3)
    with patch("fast_agent_stack.core.ratelimit._get_async_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/ping")
    assert resp.status_code == 200


async def test_rate_limit_returns_429_on_exceed():
    app, mock_redis = _make_app(requests=5, eval_return=6)
    with patch("fast_agent_stack.core.ratelimit._get_async_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/ping", headers={"X-Forwarded-For": "10.0.0.1"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


async def test_rate_limit_key_includes_ip_and_window():
    """Middleware must use fas:rl:{ip}:{window_start} key format."""
    import fastapi

    from fast_agent_stack.core.ratelimit import RateLimitMiddleware

    app = fastapi.FastAPI()
    period = 60
    captured_key: list[str] = []

    mock_redis = AsyncMock()

    async def fake_eval(script, numkeys, key, *args):
        captured_key.append(key)
        return 1

    mock_redis.eval = fake_eval

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, requests=100, period=period)

    now = int(time.time())
    expected_window = (now // period) * period

    with patch("fast_agent_stack.core.ratelimit._get_async_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/ping", headers={"X-Forwarded-For": "10.0.0.1"})

    assert len(captured_key) == 1
    key = captured_key[0]
    assert key.startswith("fas:rl:10.0.0.1:")
    window_part = int(key.split(":")[-1])
    assert abs(window_part - expected_window) <= period  # within one window


async def test_rate_limit_x_forwarded_for_takes_priority():
    captured_keys: list[str] = []

    import fastapi

    from fast_agent_stack.core.ratelimit import RateLimitMiddleware

    app = fastapi.FastAPI()
    mock_redis = AsyncMock()

    async def fake_eval(script, numkeys, key, *args):
        captured_keys.append(key)
        return 1

    mock_redis.eval = fake_eval

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, requests=100, period=60)
    with patch("fast_agent_stack.core.ratelimit._get_async_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/ping", headers={"X-Forwarded-For": "203.0.113.5"})

    assert captured_keys[0].startswith("fas:rl:203.0.113.5:")


async def test_rate_limit_response_has_ratelimit_headers():
    app, mock_redis = _make_app(requests=10, eval_return=1)
    with patch("fast_agent_stack.core.ratelimit._get_async_redis", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/ping")
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers


# ---------------------------------------------------------------------------
# ARCHITECTURAL — I3 (ADR-037: redis_fastapi guard), I4
# ---------------------------------------------------------------------------


def test_i3_rate_limit_middleware_guards_on_redis_fastapi():
    """I3: ratelimit/__init__.py must guard on redis_fastapi, not bare redis (ADR-037)."""
    import fast_agent_stack.core.ratelimit as mod

    src = Path(mod.__file__).read_text()
    tree = ast.parse(src)

    guarded_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for child in ast.walk(node):
                if isinstance(child, ast.ImportFrom) and child.module:
                    guarded_modules.append(child.module)
                elif isinstance(child, ast.Import):
                    for alias in child.names:
                        guarded_modules.append(alias.name)

    assert any("redis_fastapi" in m for m in guarded_modules), (
        "ratelimit/__init__.py must have an I3 guard on redis_fastapi (ADR-037)"
    )


def test_rate_limit_middleware_has_no_redis_init_param():
    """RateLimitMiddleware must not accept a 'redis' constructor parameter (ADR-037)."""
    import inspect

    from fast_agent_stack.core.ratelimit import RateLimitMiddleware

    sig = inspect.signature(RateLimitMiddleware.__init__)
    assert "redis" not in sig.parameters, (
        "RateLimitMiddleware.__init__ must not accept 'redis' — "
        "Redis is acquired per-request from the SDK pool (ADR-037)"
    )


def test_rate_limit_lifespan_hook_has_no_redis_attribute():
    """RateLimitLifespanHook must not own a Redis pool (ADR-037, I9)."""
    from fast_agent_stack.core.config import BaseSettings
    from fast_agent_stack.core.ratelimit import RateLimitLifespanHook

    settings = BaseSettings(app_name="test", redis_url="redis://localhost:6379")
    hook = RateLimitLifespanHook(settings)
    assert not hasattr(hook, "redis"), "RateLimitLifespanHook must not own a redis attr — pool is SDK-managed"
    assert not hasattr(hook, "_redis"), "RateLimitLifespanHook must not own a _redis attr — pool is SDK-managed"


async def test_rate_limit_lifespan_hook_aexit_is_noop():
    """RateLimitLifespanHook.__aexit__ must not close any connection (no pool)."""
    from fast_agent_stack.core.config import BaseSettings
    from fast_agent_stack.core.ratelimit import RateLimitLifespanHook

    settings = BaseSettings(app_name="test")
    hook = RateLimitLifespanHook(settings)
    await hook.__aenter__()
    # No patch needed — nothing should be called on any redis client
    await hook.__aexit__(None, None, None)


# ---------------------------------------------------------------------------
# NFR — I2 (async redis), pyproject extras
# ---------------------------------------------------------------------------


def test_rate_limit_middleware_source_has_no_blocking_imports():
    import fast_agent_stack.core.ratelimit as mod

    src = Path(mod.__file__).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "redis", "Bare sync redis import found (I2 violation)"


def test_pyproject_toml_rate_limit_uses_fastapi_redis_sdk():
    """pyproject.toml rate-limit extra must depend on fastapi-redis-sdk (ADR-037)."""
    import tomllib

    toml_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(toml_path.read_text())
    optional_deps = data["project"]["optional-dependencies"]
    assert "rate-limit" in optional_deps
    rl_deps = optional_deps["rate-limit"]
    assert any("fastapi-redis-sdk" in d for d in rl_deps), (
        "rate-limit extra must list fastapi-redis-sdk>=0.7 (ADR-037)"
    )


def test_pyproject_toml_contains_tracing_extra():
    import tomllib

    toml_path = Path(__file__).resolve().parents[1] / "pyproject.toml"

    data = tomllib.loads(toml_path.read_text())
    optional_deps = data["project"]["optional-dependencies"]
    assert "tracing" in optional_deps
    tracing_deps = optional_deps["tracing"]
    assert any("opentelemetry-api" in d for d in tracing_deps)
    assert any("opentelemetry-sdk" in d for d in tracing_deps)
    assert any("opentelemetry-exporter-otlp" in d for d in tracing_deps)
