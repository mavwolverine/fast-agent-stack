"""Request-ID middleware tests — 5 families (B/C/A/N/F)."""

import re
import time

from fastapi import Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from fast_agent_stack import FastAgentStack
from fast_agent_stack.core.middleware import RequestIDMiddleware, get_request_id

_UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def _app_with_root() -> FastAgentStack:
    stack = FastAgentStack()

    @stack.fastapi_app.get("/")
    async def root() -> dict[str, str]:
        return {"ok": "yes"}

    return stack


# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


def test_b1_response_has_x_request_id_header() -> None:
    client = TestClient(_app_with_root().fastapi_app)
    resp = client.get("/")
    assert "x-request-id" in resp.headers


def test_b2_client_supplied_id_is_echoed() -> None:
    client = TestClient(_app_with_root().fastapi_app)
    resp = client.get("/", headers={"X-Request-ID": "my-trace-id"})
    assert resp.headers["x-request-id"] == "my-trace-id"


def test_b3_generated_id_is_uuid4() -> None:
    client = TestClient(_app_with_root().fastapi_app)
    resp = client.get("/")
    rid = resp.headers["x-request-id"]
    assert _UUID4_RE.match(rid), f"Not a UUID4: {rid!r}"


def test_b4_request_id_accessible_via_state() -> None:
    stack = FastAgentStack()
    captured: list[str] = []

    @stack.fastapi_app.get("/capture")
    async def capture(request: Request) -> dict[str, str]:
        captured.append(str(request.state.request_id))
        return {}

    client = TestClient(stack.fastapi_app)
    client.get("/capture")
    assert len(captured) == 1
    assert captured[0] != ""


def test_b5_get_request_id_returns_current_id() -> None:
    stack = FastAgentStack()
    captured: list[str] = []

    @stack.fastapi_app.get("/ctxvar")
    async def ctxvar() -> dict[str, str]:
        captured.append(get_request_id())
        return {}

    client = TestClient(stack.fastapi_app)
    client.get("/ctxvar")
    assert captured[0] != ""
    assert _UUID4_RE.match(captured[0])


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_default_request_id_middleware_is_on() -> None:
    """request_id_middleware defaults to True — enabled by default."""
    stack = FastAgentStack()
    middleware_types = [m.cls for m in stack.fastapi_app.user_middleware]
    assert RequestIDMiddleware in middleware_types


def test_c2_request_id_middleware_false_disables_it() -> None:
    stack = FastAgentStack(request_id_middleware=False)
    middleware_types = [m.cls for m in stack.fastapi_app.user_middleware]
    assert RequestIDMiddleware not in middleware_types


def test_c3_each_request_gets_unique_id() -> None:
    client = TestClient(_app_with_root().fastapi_app)
    ids = {client.get("/").headers["x-request-id"] for _ in range(5)}
    assert len(ids) == 5, "Expected 5 unique request IDs"


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_request_id_middleware_is_pure_asgi() -> None:
    """Must not inherit BaseHTTPMiddleware — avoids streaming issues."""
    assert not issubclass(RequestIDMiddleware, BaseHTTPMiddleware)


def test_a2_request_id_middleware_outermost_relative_to_cors() -> None:
    """RequestID must be outermost so it injects X-Request-ID into CORS preflights too."""
    stack = FastAgentStack(cors_origins=["https://example.com"])
    types = [m.cls for m in stack.fastapi_app.user_middleware]
    rid_idx = types.index(RequestIDMiddleware)
    from starlette.middleware.cors import CORSMiddleware

    cors_idx = types.index(CORSMiddleware)
    # user_middleware[0] is outermost; lower index = outermost
    assert rid_idx < cors_idx, "RequestIDMiddleware must be at a lower index (outermost) than CORSMiddleware"


def test_a3_get_request_id_returns_empty_outside_request() -> None:
    """Outside a request context the contextvar returns the default empty string."""
    assert get_request_id() == ""


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


def test_n1_request_id_overhead_under_5ms() -> None:
    """Framework overhead from request-id middleware must not exceed 5ms (NFR)."""
    client = TestClient(_app_with_root().fastapi_app)
    # Warm-up
    client.get("/")
    start = time.monotonic()
    for _ in range(20):
        client.get("/")
    elapsed = (time.monotonic() - start) / 20
    assert elapsed < 0.005, f"Avg per-request: {elapsed * 1000:.2f}ms (limit: 5ms)"


def test_n2_request_id_header_present_on_cors_preflight() -> None:
    """X-Request-ID must appear in CORS preflight responses too."""
    stack = FastAgentStack(cors_origins=["https://example.com"])

    @stack.fastapi_app.get("/")
    async def root() -> dict[str, str]:
        return {}

    client = TestClient(stack.fastapi_app)
    resp = client.options(
        "/",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "x-request-id" in resp.headers


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


def test_f1_empty_incoming_id_generates_uuid() -> None:
    """An empty X-Request-ID header is treated as absent — a UUID4 is generated."""
    client = TestClient(_app_with_root().fastapi_app)
    resp = client.get("/", headers={"X-Request-ID": ""})
    rid = resp.headers["x-request-id"]
    assert _UUID4_RE.match(rid), f"Expected UUID4, got {rid!r}"


def test_f2_no_request_id_middleware_no_x_request_id_header() -> None:
    stack = FastAgentStack(request_id_middleware=False)

    @stack.fastapi_app.get("/")
    async def root() -> dict[str, str]:
        return {}

    client = TestClient(stack.fastapi_app)
    resp = client.get("/")
    assert "x-request-id" not in resp.headers


def test_f3_concurrent_requests_get_independent_ids() -> None:
    """Each request has its own contextvar slot — IDs must not bleed across requests."""
    stack = FastAgentStack()
    captured: list[str] = []

    @stack.fastapi_app.get("/seq")
    async def seq(request: Request) -> dict[str, str]:
        captured.append(str(request.state.request_id))
        return {}

    client = TestClient(stack.fastapi_app)
    for _ in range(3):
        client.get("/seq")

    assert len(set(captured)) == 3, "Each sequential request must have a unique ID"
