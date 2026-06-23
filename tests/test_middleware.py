"""CORS middleware tests — 5 families (B/C/A/N/F)."""


import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from fast_agent_stack import FastAgentStack
from fast_agent_stack.core.middleware import CORSConfig, apply_cors

_ORIGIN = "https://example.com"
_OTHER_ORIGIN = "https://evil.com"


def _make_app(cors_origins: list[str] | None = None, **kwargs: object) -> FastAgentStack:
    stack = FastAgentStack(cors_origins=cors_origins, **kwargs)  # type: ignore[arg-type]

    @stack.fastapi_app.get("/")
    async def root() -> dict[str, str]:
        return {"ok": "yes"}

    return stack


# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


def test_b1_no_cors_config_no_acao_header() -> None:
    """Without CORS config, no Access-Control-Allow-Origin header in response."""
    client = TestClient(_make_app().fastapi_app)
    resp = client.get("/", headers={"Origin": _ORIGIN})
    assert "access-control-allow-origin" not in resp.headers


def test_b2_wildcard_allows_any_origin() -> None:
    client = TestClient(_make_app(cors_origins=["*"]).fastapi_app)
    resp = client.get("/", headers={"Origin": _ORIGIN})
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_b3_specific_origin_reflected_in_acao() -> None:
    client = TestClient(_make_app(cors_origins=[_ORIGIN]).fastapi_app)
    resp = client.get("/", headers={"Origin": _ORIGIN})
    assert resp.headers.get("access-control-allow-origin") == _ORIGIN


def test_b4_preflight_returns_cors_headers() -> None:
    client = TestClient(_make_app(cors_origins=[_ORIGIN]).fastapi_app)
    resp = client.options(
        "/",
        headers={
            "Origin": _ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


def test_b5_disallowed_origin_has_no_acao_header() -> None:
    client = TestClient(_make_app(cors_origins=[_ORIGIN]).fastapi_app)
    resp = client.get("/", headers={"Origin": _OTHER_ORIGIN})
    assert "access-control-allow-origin" not in resp.headers


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_default_no_cors_no_crash() -> None:
    stack = FastAgentStack()
    assert stack.fastapi_app is not None


def test_c2_wildcard_cors_accepted() -> None:
    stack = FastAgentStack(cors_origins=["*"])
    assert stack.fastapi_app is not None


def test_c3_multiple_origins_accepted() -> None:
    stack = FastAgentStack(cors_origins=["https://a.com", "https://b.com"])
    assert stack.fastapi_app is not None


def test_c4_cors_config_default_fields() -> None:
    cfg = CORSConfig(allow_origins=[_ORIGIN])
    assert cfg.allow_origins == [_ORIGIN]
    assert cfg.allow_credentials is False
    assert cfg.allow_methods == ["*"]
    assert cfg.allow_headers == ["*"]
    assert cfg.expose_headers == []
    assert cfg.max_age == 600


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_cors_uses_starlette_cors_middleware() -> None:
    """CORSMiddleware must come from Starlette, not a custom implementation."""
    stack = FastAgentStack(cors_origins=[_ORIGIN])
    middleware_types = [m.cls for m in stack.fastapi_app.user_middleware]
    assert CORSMiddleware in middleware_types


def test_a2_apply_cors_importable_from_core_middleware() -> None:
    assert callable(apply_cors)


def test_a3_apply_cors_adds_middleware_to_fastapi_instance() -> None:
    """apply_cors works on a raw FastAPI instance (I4 escape-hatch path)."""
    fa = FastAPI()
    apply_cors(fa, CORSConfig(allow_origins=[_ORIGIN]))
    middleware_types = [m.cls for m in fa.user_middleware]
    assert CORSMiddleware in middleware_types


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


def test_n1_cors_preflight_under_100ms() -> None:
    client = TestClient(_make_app(cors_origins=[_ORIGIN]).fastapi_app)
    start = time.monotonic()
    resp = client.options(
        "/",
        headers={
            "Origin": _ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    elapsed = time.monotonic() - start
    assert resp.status_code == 200
    assert elapsed < 0.1, f"Preflight took {elapsed:.3f}s (limit: 100ms)"


def test_n2_no_cors_means_no_middleware_overhead() -> None:
    """No CORS config → CORSMiddleware not added to middleware stack."""
    stack = FastAgentStack()
    middleware_types = [m.cls for m in stack.fastapi_app.user_middleware]
    assert CORSMiddleware not in middleware_types


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


def test_f1_empty_origins_list_adds_no_middleware() -> None:
    """Empty list is treated the same as None — no CORS middleware."""
    stack = FastAgentStack(cors_origins=[])
    middleware_types = [m.cls for m in stack.fastapi_app.user_middleware]
    assert CORSMiddleware not in middleware_types


def test_f2_none_origins_adds_no_middleware() -> None:
    stack = FastAgentStack(cors_origins=None)
    middleware_types = [m.cls for m in stack.fastapi_app.user_middleware]
    assert CORSMiddleware not in middleware_types


def test_f3_lifespan_kwarg_still_blocked_with_cors_config() -> None:
    """lifespan kwarg is rejected even when cors_origins is also provided."""
    with pytest.raises(ValueError, match="lifespan"):
        FastAgentStack(cors_origins=["*"], lifespan=lambda: None)
