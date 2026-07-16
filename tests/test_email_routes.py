"""Tests for Phase 6-5: Auth email routes (ADR-018)."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# ARCHITECTURAL — I12, I18 (source scan)
# ---------------------------------------------------------------------------


def test_i12_auth_routes_imports_from_email_init_not_smtp():
    import fast_agent_stack.core.auth.routes as mod

    src = Path(mod.__file__).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "fast_agent_stack.core.email.smtp" not in node.module, (
                "auth/routes.py must not import from core.email.smtp (I12)"
            )


def test_i18_reset_password_uses_password_hash_function():
    import fast_agent_stack.core.auth.routes as mod

    src = Path(mod.__file__).read_text()
    # Confirm hash_password is imported/used (not raw hashlib)
    assert "hash_password" in src, "reset_password must call hash_password() (I18)"
    assert "hashlib" not in src, "hashlib must not be used directly (I18)"


# ---------------------------------------------------------------------------
# BEHAVIOR — fire-and-forget email routes
# ---------------------------------------------------------------------------


async def _build_test_client(session_override=None, extra_overrides=None):
    """Build a minimal FastAPI test client with auth router and mocked deps."""
    import fastapi
    from httpx import ASGITransport, AsyncClient

    from fast_agent_stack.core.auth.routes import router
    from fast_agent_stack.core.database import get_async_session

    app = fastapi.FastAPI()
    app.include_router(router)

    if session_override is not None:

        async def _session_dep():
            yield session_override

        app.dependency_overrides[get_async_session] = _session_dep

    if extra_overrides:
        app.dependency_overrides.update(extra_overrides)

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_forgot_password_always_returns_200():
    """Even for non-existent users, forgot-password must return 200 (anti-enumeration)."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # user not found
    mock_session.execute = AsyncMock(return_value=mock_result)

    async with await _build_test_client(session_override=mock_session) as client:
        resp = await client.post("/auth/forgot-password", json={"email": "no-such@example.com"})
    assert resp.status_code in (200, 202)


async def test_send_verification_swallows_email_delivery_error():
    """EmailDeliveryError must not propagate to HTTP caller."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.delete = AsyncMock()
    mock_result = MagicMock()
    mock_user = MagicMock()
    mock_user.id = "00000000-0000-0000-0000-000000000001"
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute = AsyncMock(return_value=mock_result)

    from fast_agent_stack.core.email import EmailDeliveryError

    mock_backend = AsyncMock()
    mock_backend.send = AsyncMock(side_effect=EmailDeliveryError("SMTP timeout"))

    with patch("fast_agent_stack.core.auth.routes.get_email_backend", return_value=mock_backend):
        async with await _build_test_client(session_override=mock_session) as client:
            resp = await client.post(
                "/auth/send-verification",
                json={"email": "user@example.com"},
            )
    assert resp.status_code in (200, 202)
