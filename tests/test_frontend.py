"""Tests for FastAgentStack.frontend() static SPA serving (ADR-024)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fast_agent_stack import FastAgentStack


def _stack_with_frontend(directory: str, path: str = "/") -> TestClient:
    stack = FastAgentStack()
    stack.frontend(directory, path=path)
    return TestClient(stack.fastapi_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# 1. Behavior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/", ""])
def test_b1_serves_index_html_at_root(tmp_path, path):
    (tmp_path / "index.html").write_text("<h1>Hello</h1>")
    client = _stack_with_frontend(str(tmp_path))
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<h1>Hello</h1>" in resp.text


def test_b2_serves_static_asset(tmp_path):
    (tmp_path / "index.html").write_text("<h1>App</h1>")
    (tmp_path / "app.js").write_text("console.log('hi')")
    client = _stack_with_frontend(str(tmp_path))
    resp = client.get("/app.js")
    assert resp.status_code == 200
    assert "console.log" in resp.text


def test_b3_api_route_takes_priority_over_static(tmp_path):
    (tmp_path / "index.html").write_text("<h1>App</h1>")
    stack = FastAgentStack()

    @stack.fastapi_app.get("/api/ping")
    async def ping():
        return {"pong": True}

    stack.frontend(str(tmp_path))
    client = TestClient(stack.fastapi_app)
    resp = client.get("/api/ping")
    assert resp.status_code == 200
    assert resp.json() == {"pong": True}


def test_b4_custom_mount_path(tmp_path):
    (tmp_path / "index.html").write_text("<h1>UI</h1>")
    client = _stack_with_frontend(str(tmp_path), path="/ui")
    resp = client.get("/ui/")
    assert resp.status_code == 200
    assert "<h1>UI</h1>" in resp.text


def test_b5_health_route_still_works_after_frontend(tmp_path):
    (tmp_path / "index.html").write_text("")
    client = _stack_with_frontend(str(tmp_path))
    resp = client.get("/health/live")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 2. Contract
# ---------------------------------------------------------------------------


def test_c1_method_exists_on_fast_agent_stack():
    stack = FastAgentStack()
    assert callable(getattr(stack, "frontend", None))


def test_c2_returns_none(tmp_path):
    (tmp_path / "index.html").write_text("")
    stack = FastAgentStack()
    result = stack.frontend(str(tmp_path))
    assert result is None


def test_c3_path_kwarg_defaults_to_root(tmp_path):
    import inspect
    sig = inspect.signature(FastAgentStack.frontend)
    assert sig.parameters["path"].default == "/"


def test_c4_path_is_keyword_only(tmp_path):
    import inspect
    sig = inspect.signature(FastAgentStack.frontend)
    assert sig.parameters["path"].kind == inspect.Parameter.KEYWORD_ONLY


# ---------------------------------------------------------------------------
# 3. Architectural
# ---------------------------------------------------------------------------


def test_a1_no_extras_required(tmp_path):
    # StaticFiles is in starlette, always installed with fastapi — no import guard needed
    (tmp_path / "index.html").write_text("")
    stack = FastAgentStack()
    stack.frontend(str(tmp_path))  # must not raise ImportError


def test_a2_frontend_is_on_public_class():
    # frontend() is accessed via FastAgentStack (public), not via core internals
    import fast_agent_stack as public_module
    stack = public_module.FastAgentStack()
    assert hasattr(stack, "frontend")


# ---------------------------------------------------------------------------
# 4. NFR
# ---------------------------------------------------------------------------


def test_n1_empty_directory_with_gitkeep_does_not_raise(tmp_path):
    # Scaffold generates empty frontend/ with .gitkeep; StaticFiles must accept it
    (tmp_path / ".gitkeep").write_text("")
    stack = FastAgentStack()
    stack.frontend(str(tmp_path))


def test_n2_multiple_static_files_served_correctly(tmp_path):
    (tmp_path / "index.html").write_text("<h1>App</h1>")
    (tmp_path / "style.css").write_text("body { color: red; }")
    (tmp_path / "logo.svg").write_text("<svg/>")
    client = _stack_with_frontend(str(tmp_path))
    assert client.get("/style.css").status_code == 200
    assert client.get("/logo.svg").status_code == 200


# ---------------------------------------------------------------------------
# 5. Failure-mode
# ---------------------------------------------------------------------------


def test_f1_raises_on_nonexistent_directory():
    stack = FastAgentStack()
    with pytest.raises(Exception):
        stack.frontend("/nonexistent/path/xyz_does_not_exist")
