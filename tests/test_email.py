"""Tests for Phase 6-5: Email Protocol & SmtpEmailBackend (ADR-018, ADR-041)."""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from fast_agent_stack.core.config import BaseSettings


def _settings(**kw) -> BaseSettings:
    return BaseSettings(app_name="test", **kw)


# ---------------------------------------------------------------------------
# CONTRACT — EmailProtocol interface
# ---------------------------------------------------------------------------


def test_email_protocol_exported():
    from fast_agent_stack.core.email import (
        EmailDeliveryError,
        get_email_backend,
    )

    assert callable(get_email_backend)
    assert issubclass(EmailDeliveryError, Exception)


def test_email_protocol_send_signature():
    from fast_agent_stack.core.email import EmailProtocol

    sig = inspect.signature(EmailProtocol.send)
    params = dict(sig.parameters)
    assert "to" in params
    assert "subject" in params
    assert "body_text" in params
    assert "body_html" in params
    assert params["body_html"].default is None
    # All must be keyword-only (after *)
    kw_only = {n for n, p in params.items() if p.kind == inspect.Parameter.KEYWORD_ONLY}
    assert {"to", "subject", "body_text", "body_html"} <= kw_only


def test_email_delivery_error_is_exception():
    from fast_agent_stack.core.email import EmailDeliveryError

    assert issubclass(EmailDeliveryError, Exception)


# ---------------------------------------------------------------------------
# BEHAVIOR — factory
# ---------------------------------------------------------------------------


def test_get_email_backend_smtp_returns_smtp_backend():
    pytest.importorskip("aiosmtplib")
    from fast_agent_stack.core.email import get_email_backend
    from fast_agent_stack.core.email.smtp import SmtpEmailBackend

    settings = _settings(email_backend="smtp")
    backend = get_email_backend(settings)
    assert isinstance(backend, SmtpEmailBackend)


def test_get_email_backend_dotted_path():
    """ADR-012: dotted-path custom backend."""
    from fast_agent_stack.core.email import get_email_backend

    class FakeEmailBackend:
        async def send(self, *, to, subject, body_text, body_html=None) -> None:
            pass

    import tests as _tests_pkg

    _tests_pkg.FakeEmailBackend = FakeEmailBackend  # type: ignore[attr-defined]
    try:
        settings = _settings(email_backend="tests.FakeEmailBackend")
        backend = get_email_backend(settings)
        assert isinstance(backend, FakeEmailBackend)
    finally:
        del _tests_pkg.FakeEmailBackend


def test_get_email_backend_unknown_alias_raises_value_error():
    from fast_agent_stack.core.email import get_email_backend

    settings = _settings(email_backend="sendgrid")
    with pytest.raises(ValueError):
        get_email_backend(settings)


# ---------------------------------------------------------------------------
# BEHAVIOR — SmtpEmailBackend
# ---------------------------------------------------------------------------


def test_smtp_backend_send_is_coroutine():
    pytest.importorskip("aiosmtplib")
    from fast_agent_stack.core.email.smtp import SmtpEmailBackend

    settings = _settings()
    backend = SmtpEmailBackend(settings)
    assert inspect.iscoroutinefunction(backend.send)


async def test_smtp_backend_send_invokes_aiosmtplib():
    pytest.importorskip("aiosmtplib")
    from fast_agent_stack.core.email.smtp import SmtpEmailBackend

    settings = _settings(smtp_host="smtp.example.com", smtp_port=587, smtp_use_tls=True)
    backend = SmtpEmailBackend(settings)
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await backend.send(to="user@example.com", subject="Hi", body_text="hello")
    mock_send.assert_awaited_once()
    call_kwargs = mock_send.call_args
    # Check hostname
    assert call_kwargs.kwargs.get("hostname") == "smtp.example.com" or (
        len(call_kwargs.args) > 1 and call_kwargs.args[1] == "smtp.example.com"
    )


async def test_smtp_backend_send_includes_html_when_provided():
    pytest.importorskip("aiosmtplib")

    from fast_agent_stack.core.email.smtp import SmtpEmailBackend

    settings = _settings()
    backend = SmtpEmailBackend(settings)
    sent_messages: list = []

    async def capture_send(msg, **kw):
        sent_messages.append(msg)

    with patch("aiosmtplib.send", side_effect=capture_send):
        await backend.send(
            to="u@example.com",
            subject="S",
            body_text="txt",
            body_html="<b>html</b>",
        )
    assert sent_messages
    msg = sent_messages[0]
    msg.get_content_type()
    # Should be multipart/alternative or the payload should contain both parts
    body_str = msg.as_string()
    assert "txt" in body_str
    assert "html" in body_str or "<b>" in body_str


async def test_smtp_backend_send_wraps_errors_as_email_delivery_error():
    pytest.importorskip("aiosmtplib")
    import aiosmtplib

    from fast_agent_stack.core.email import EmailDeliveryError
    from fast_agent_stack.core.email.smtp import SmtpEmailBackend

    settings = _settings()
    backend = SmtpEmailBackend(settings)
    with patch("aiosmtplib.send", side_effect=aiosmtplib.SMTPException("connection refused")):
        with pytest.raises(EmailDeliveryError):
            await backend.send(to="u@example.com", subject="S", body_text="hello")


# ---------------------------------------------------------------------------
# NFR — I2 (no smtplib)
# ---------------------------------------------------------------------------


def test_i2_smtp_backend_uses_aiosmtplib_not_smtplib():
    import fast_agent_stack.core.email.smtp as mod
    src = Path(mod.__file__).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "smtplib", "smtplib must not be imported (I2)"
        elif isinstance(node, ast.ImportFrom):
            assert node.module != "smtplib", "smtplib must not be imported (I2)"
    assert "aiosmtplib" in src, "aiosmtplib must be used"


# ---------------------------------------------------------------------------
# ARCHITECTURAL — I3
# ---------------------------------------------------------------------------


def test_i3_smtp_backend_raises_import_error_when_aiosmtplib_absent():
    cached = sys.modules.get("aiosmtplib")
    sys.modules["aiosmtplib"] = None  # type: ignore[assignment]
    smtp_key = "fast_agent_stack.core.email.smtp"
    sys.modules.pop(smtp_key, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[email-smtp\\]"):
            from fast_agent_stack.core.email.smtp import SmtpEmailBackend  # noqa: F401
    finally:
        if cached is None:
            sys.modules.pop("aiosmtplib", None)
        else:
            sys.modules["aiosmtplib"] = cached
        sys.modules.pop(smtp_key, None)
