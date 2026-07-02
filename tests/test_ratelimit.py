"""Tests for Phase 6-2: Rate Limiting (ADR-016)."""
from __future__ import annotations

import ast
import sys
import time
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _make_app(requests: int = 5, period: int = 60, eval_return: int = 1):
    """Build a minimal FastAPI app with RateLimitMiddleware using mocked Redis."""
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
        redis=mock_redis,
        requests=requests,
        period=period,
    )
    return app, mock_redis


# ---------------------------------------------------------------------------
# BEHAVIOR
# ---------------------------------------------------------------------------

async def test_rate_limit_allows_requests_below_threshold():
    app, _ = _make_app(requests=5, eval_return=3)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ping")
    assert resp.status_code == 200


async def test_rate_limit_returns_429_on_exceed():
    app, _ = _make_app(requests=5, eval_return=6)
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

    app.add_middleware(RateLimitMiddleware, redis=mock_redis, requests=100, period=period)

    now = int(time.time())
    expected_window = (now // period) * period

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

    app.add_middleware(RateLimitMiddleware, redis=mock_redis, requests=100, period=60)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/ping", headers={"X-Forwarded-For": "203.0.113.5"})

    assert captured_keys[0].startswith("fas:rl:203.0.113.5:")


async def test_rate_limit_response_has_ratelimit_headers():
    app, _ = _make_app(requests=10, eval_return=1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ping")
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers
    assert "X-RateLimit-Remaining" in resp.headers
    assert "X-RateLimit-Reset" in resp.headers


# ---------------------------------------------------------------------------
# ARCHITECTURAL — I3, I4
# ---------------------------------------------------------------------------

def test_i3_rate_limit_middleware_source_uses_redis_asyncio():
    import fast_agent_stack.core.ratelimit as mod
    src = Path(mod.__file__).read_text()
    tree = ast.parse(src)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
    # Should not use sync redis at module top level in place of async
    assert not any(imp == "redis" and "asyncio" not in imp for imp in imports
                   if "redis" in imp and "asyncio" not in imp
                   and not imp.startswith("redis.asyncio"))


async def test_rate_limit_lifespan_hook_exposes_redis_attr():
    pytest.importorskip("redis.asyncio")
    from fast_agent_stack.core.ratelimit import RateLimitLifespanHook
    from fast_agent_stack.core.config import BaseSettings
    settings = BaseSettings(app_name="test", redis_url="redis://localhost:6379")
    hook = RateLimitLifespanHook(settings)
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        await hook.__aenter__()
    assert hasattr(hook, "redis")
    assert hook.redis is mock_redis
    await hook.__aexit__(None, None, None)


async def test_rate_limit_lifespan_hook_closes_redis_on_exit():
    pytest.importorskip("redis.asyncio")
    from fast_agent_stack.core.ratelimit import RateLimitLifespanHook
    from fast_agent_stack.core.config import BaseSettings
    settings = BaseSettings(app_name="test", redis_url="redis://localhost:6379")
    hook = RateLimitLifespanHook(settings)
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.aclose = AsyncMock()
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        await hook.__aenter__()
        await hook.__aexit__(None, None, None)
    mock_redis.aclose.assert_called_once()


# ---------------------------------------------------------------------------
# NFR — I2 (async redis)
# ---------------------------------------------------------------------------

def test_rate_limit_middleware_source_has_no_blocking_imports():
    import fast_agent_stack.core.ratelimit as mod
    src = Path(mod.__file__).read_text()
    # Ensure it doesn't do a bare 'import redis' (sync) at module level
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "redis", "Bare sync redis import found (I2 violation)"


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
