"""Error handler tests — 5 families (B/C/A/N/F)."""


import time

from fastapi.testclient import TestClient

from fast_agent_stack import FastAgentStack
from fast_agent_stack.core.middleware import install_error_handlers


def _boom_app(error_handlers: bool = True) -> FastAgentStack:
    stack = FastAgentStack(error_handlers=error_handlers)

    @stack.fastapi_app.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("unexpected failure")

    @stack.fastapi_app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    return stack


# ---------------------------------------------------------------------------
# Family 1: Behavior
# ---------------------------------------------------------------------------


def test_b1_unhandled_exception_returns_500() -> None:
    client = TestClient(_boom_app().fastapi_app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500


def test_b2_500_response_is_json_with_detail() -> None:
    client = TestClient(_boom_app().fastapi_app, raise_server_exceptions=False)
    resp = client.get("/boom")
    data = resp.json()
    assert "detail" in data


def test_b3_500_response_includes_request_id_header() -> None:
    """When both error_handlers and request_id_middleware are on, 500 carries X-Request-ID."""
    client = TestClient(_boom_app().fastapi_app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert "x-request-id" in resp.headers


def test_b4_normal_routes_unaffected() -> None:
    client = TestClient(_boom_app().fastapi_app)
    resp = client.get("/ok")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Family 2: Contract
# ---------------------------------------------------------------------------


def test_c1_error_handlers_default_is_true() -> None:
    """error_handlers=True by default — handler is registered without explicit opt-in."""
    stack = FastAgentStack()
    # FastAPI stores exception handlers in an internal dict; verify the handler is present
    handlers = dict(stack.fastapi_app.exception_handlers)
    assert Exception in handlers


def test_c2_content_type_is_application_json() -> None:
    client = TestClient(_boom_app().fastapi_app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert "application/json" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Family 3: Architectural
# ---------------------------------------------------------------------------


def test_a1_install_error_handlers_importable_from_core_middleware() -> None:
    assert callable(install_error_handlers)


def test_a2_install_error_handlers_takes_fastapi_instance() -> None:
    from fastapi import FastAPI

    fa = FastAPI()
    install_error_handlers(fa)
    assert Exception in dict(fa.exception_handlers)


# ---------------------------------------------------------------------------
# Family 4: NFR
# ---------------------------------------------------------------------------


def test_n1_error_response_under_50ms() -> None:
    client = TestClient(_boom_app().fastapi_app, raise_server_exceptions=False)
    start = time.monotonic()
    resp = client.get("/boom")
    elapsed = time.monotonic() - start
    assert resp.status_code == 500
    assert elapsed < 0.05, f"Error response took {elapsed * 1000:.1f}ms (limit: 50ms)"


# ---------------------------------------------------------------------------
# Family 5: Failure-mode
# ---------------------------------------------------------------------------


def test_f1_error_handlers_false_means_no_exception_handler() -> None:
    stack = FastAgentStack(error_handlers=False)
    handlers = dict(stack.fastapi_app.exception_handlers)
    assert Exception not in handlers


def test_f2_error_detail_does_not_leak_internal_message() -> None:
    """Internal exception message must not appear in the 500 response body."""
    client = TestClient(_boom_app().fastapi_app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert "unexpected failure" not in resp.text
    assert "RuntimeError" not in resp.text
