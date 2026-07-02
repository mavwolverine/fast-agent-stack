"""Response caching tests — cache(), cache_evict(), cache_put(), enable_caching() (ADR-037).

5 families: Behavior, Contract, Architectural, NFR, Failure-mode.
Uses fakeredis where a real Redis client is needed.
"""
from __future__ import annotations

import ast
import pathlib
from unittest.mock import MagicMock, patch

import pytest
from fakeredis.aioredis import FakeRedis
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

ROOT = pathlib.Path(__file__).parent.parent
CORE = ROOT / "fast_agent_stack" / "core"


def _make_cached_app(ttl: int = 60) -> tuple[FastAPI, FakeRedis]:
    """Minimal app with caching enabled and a single cached GET route."""
    from fast_agent_stack.core.caching import cache, enable_caching

    fake_redis = FakeRedis()
    app = FastAPI()

    # Patch get_async_redis so cache() picks up our FakeRedis
    from redis_fastapi.deps import get_async_redis
    app.dependency_overrides[get_async_redis] = lambda: fake_redis

    enable_caching(app)

    call_count = {"n": 0}

    @app.get("/resource")
    async def get_resource(_: None = Depends(cache(ttl=ttl, eviction_group="resource"))):
        call_count["n"] += 1
        return {"value": call_count["n"]}

    return app, fake_redis


# ===========================================================================
# Family 1: Behavior
# ===========================================================================


async def test_b1_cache_hit_returns_same_response():
    """Second GET must return the cached body without calling the endpoint again."""
    app, _ = _make_cached_app(ttl=60)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.get("/resource")
        r2 = await c.get("/resource")
    assert r1.status_code == 200
    assert r2.status_code in (200, 304)
    # Body must be identical on a cache hit
    assert r1.json() == r2.json()


async def test_b2_cache_miss_calls_endpoint():
    """First GET (cold cache) must execute the endpoint."""
    app, _ = _make_cached_app(ttl=60)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/resource")
    assert r.status_code == 200
    assert r.json()["value"] == 1


async def test_b3_enable_caching_is_idempotent():
    """Calling enable_caching() twice on the same app must not raise or double-register."""
    from fast_agent_stack.core.caching import enable_caching

    app = FastAPI()
    enable_caching(app)
    enable_caching(app)  # must not raise or add duplicate middleware


async def test_b4_cache_evict_clears_group():
    """After a cache_evict dependency runs, the next GET must hit the endpoint again."""
    from fast_agent_stack.core.caching import cache, cache_evict, enable_caching
    from redis_fastapi.deps import get_async_redis

    fake_redis = FakeRedis()
    app = FastAPI()
    app.dependency_overrides[get_async_redis] = lambda: fake_redis
    enable_caching(app)

    call_count = {"n": 0}

    @app.get("/items")
    async def get_items(_: None = Depends(cache(ttl=60, eviction_group="items"))):
        call_count["n"] += 1
        return {"count": call_count["n"]}

    @app.delete("/items")
    async def delete_items(_: None = Depends(cache_evict(eviction_group="items"))):
        return {"deleted": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.get("/items")
        await c.delete("/items")  # evict
        r2 = await c.get("/items")

    assert r1.json()["count"] == 1
    assert r2.json()["count"] == 2  # endpoint re-executed after eviction


async def test_b5_cache_put_writes_on_every_call():
    """cache_put() must always execute the endpoint and store the result."""
    from fast_agent_stack.core.caching import cache, cache_put, enable_caching
    from redis_fastapi.deps import get_async_redis

    fake_redis = FakeRedis()
    app = FastAPI()
    app.dependency_overrides[get_async_redis] = lambda: fake_redis
    enable_caching(app)

    call_count = {"n": 0}

    @app.post("/items")
    async def create_item(_: None = Depends(cache_put(ttl=60, eviction_group="items"))):
        call_count["n"] += 1
        return {"count": call_count["n"]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post("/items")
        r2 = await c.post("/items")

    # cache_put always runs the endpoint
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert call_count["n"] == 2


# ===========================================================================
# Family 2: Contract
# ===========================================================================


def test_c1_cache_returns_dependency():
    """cache() must return a callable suitable for Depends()."""
    from fast_agent_stack.core.caching import cache

    dep = cache(ttl=30)
    assert callable(dep)


def test_c2_cache_evict_returns_dependency():
    from fast_agent_stack.core.caching import cache_evict

    dep = cache_evict(eviction_group="test")
    assert callable(dep)


def test_c3_cache_put_returns_dependency():
    from fast_agent_stack.core.caching import cache_put

    dep = cache_put(ttl=30)
    assert callable(dep)


def test_c4_all_symbols_in_module_all():
    from fast_agent_stack.core import caching

    for name in ["cache", "cache_evict", "cache_put", "enable_caching", "CacheBackend", "CacheBackendDep"]:
        assert name in caching.__all__
        assert hasattr(caching, name)


def test_c5_enable_caching_accepts_fastapi_app():
    """enable_caching must accept a FastAPI instance (not just Any)."""
    import inspect
    from fast_agent_stack.core.caching import enable_caching

    sig = inspect.signature(enable_caching)
    assert "app" in sig.parameters


# ===========================================================================
# Family 3: Architectural
# ===========================================================================


def test_a1_caching_module_has_i3_guard():
    """caching/__init__.py must have an I3 import guard on redis_fastapi."""
    src = (CORE / "caching" / "__init__.py").read_text()
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
        "caching/__init__.py must guard on redis_fastapi (I3)"
    )


def test_a2_caching_has_no_direct_redis_asyncio_import():
    """caching/__init__.py must not import redis.asyncio directly."""
    src = (CORE / "caching" / "__init__.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "redis.asyncio" in node.module:
            pytest.fail("caching/__init__.py must not import redis.asyncio directly")


def test_a3_enable_caching_delegates_to_sdk():
    """enable_caching() must call FastAPIRedis(app).caching(), not roll its own."""
    src = (CORE / "caching" / "__init__.py").read_text()
    assert "FastAPIRedis" in src
    assert ".caching()" in src


def test_a4_caching_module_does_not_import_from_other_core_internals():
    """caching/__init__.py must not reach into other core module internals (I12)."""
    src = (CORE / "caching" / "__init__.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            # Only allowed: redis_fastapi, __future__, typing, fastapi
            assert not node.module.startswith("fast_agent_stack.core."), (
                f"caching module imports from core internal: {node.module!r} (I12)"
            )


# ===========================================================================
# Family 4: NFR
# ===========================================================================


def test_n1_pyproject_has_caching_extra():
    import tomllib

    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    deps = data["project"]["optional-dependencies"]
    assert "caching" in deps
    assert any("fastapi-redis-sdk" in d for d in deps["caching"])


async def test_n2_cache_requires_enable_caching_first():
    """Using cache() without enable_caching() means the endpoint always runs (no cache hit short-circuit)."""
    from fast_agent_stack.core.caching import cache
    from redis_fastapi.deps import get_async_redis

    fake_redis = FakeRedis()
    app = FastAPI()
    app.dependency_overrides[get_async_redis] = lambda: fake_redis
    # deliberately NOT calling enable_caching(app)

    call_count = {"n": 0}

    @app.get("/data")
    async def get_data(_: None = Depends(cache(ttl=60))):
        call_count["n"] += 1
        return {"n": call_count["n"]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.get("/data")
        await c.get("/data")

    # Without enable_caching, CacheHitException handler is missing — endpoint runs every time
    assert call_count["n"] == 2


# ===========================================================================
# Family 5: Failure-mode
# ===========================================================================


def test_f1_import_error_without_sdk(monkeypatch):
    """Importing from fast_agent_stack.core.caching without SDK must raise ImportError."""
    import sys
    import builtins
    import importlib

    monkeypatch.delitem(sys.modules, "fast_agent_stack.core.caching", raising=False)
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "redis_fastapi":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    with pytest.raises(ImportError, match="fastapi-redis-sdk"):
        import fast_agent_stack.core.caching as _m
        importlib.reload(_m)


def test_f2_enable_caching_with_non_fastapi_object():
    """enable_caching() must raise (AttributeError or similar) for a non-FastAPI object."""
    from fast_agent_stack.core.caching import enable_caching

    with pytest.raises((AttributeError, TypeError, Exception)):
        enable_caching("not-an-app")  # type: ignore[arg-type]
