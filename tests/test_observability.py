"""Tests for Phase 6-3: Observability (ADR-009)."""
from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fast_agent_stack.core.config import BaseSettings


def _settings(**kw) -> BaseSettings:
    return BaseSettings(app_name="test-app", **kw)


# ---------------------------------------------------------------------------
# BEHAVIOR
# ---------------------------------------------------------------------------

async def test_tracing_hook_noop_when_disabled():
    """tracing_enabled=False must be a pure no-op even when OTel is absent."""
    from fast_agent_stack.core.observability import TracingLifespanHook
    settings = _settings(tracing_enabled=False)
    hook = TracingLifespanHook(settings)
    # Should not raise even if opentelemetry not installed
    await hook.__aenter__()
    await hook.__aexit__(None, None, None)
    assert hook.tracer_provider is None


async def test_tracing_hook_initialises_provider_when_enabled():
    otel = pytest.importorskip("opentelemetry")
    from fast_agent_stack.core.observability import TracingLifespanHook
    settings = _settings(tracing_enabled=True, otel_exporter_endpoint="http://collector:4317")

    mock_provider = MagicMock()
    mock_provider.shutdown = MagicMock()

    with patch("opentelemetry.sdk.trace.TracerProvider", return_value=mock_provider), \
         patch("opentelemetry.sdk.trace.export.BatchSpanProcessor"), \
         patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"), \
         patch("opentelemetry.trace.set_tracer_provider"):
        hook = TracingLifespanHook(settings)
        await hook.__aenter__()
        assert hook.tracer_provider is mock_provider


async def test_tracing_hook_shutdown_called_on_exit():
    pytest.importorskip("opentelemetry")
    from fast_agent_stack.core.observability import TracingLifespanHook
    settings = _settings(tracing_enabled=True)

    mock_provider = MagicMock()
    mock_provider.shutdown = MagicMock()
    shutdown_calls: list[str] = []

    async def fake_to_thread(fn, *args, **kw):
        shutdown_calls.append("to_thread")
        fn()

    with patch("opentelemetry.sdk.trace.TracerProvider", return_value=mock_provider), \
         patch("opentelemetry.sdk.trace.export.BatchSpanProcessor"), \
         patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"), \
         patch("opentelemetry.trace.set_tracer_provider"), \
         patch("asyncio.to_thread", side_effect=fake_to_thread):
        hook = TracingLifespanHook(settings)
        await hook.__aenter__()
        await hook.__aexit__(None, None, None)

    assert "to_thread" in shutdown_calls, "shutdown() must be offloaded via asyncio.to_thread (I2)"
    mock_provider.shutdown.assert_called_once()


async def test_tracing_hook_no_shutdown_when_provider_is_none():
    """No shutdown attempt when tracing was disabled (provider never set)."""
    from fast_agent_stack.core.observability import TracingLifespanHook
    settings = _settings(tracing_enabled=False)
    hook = TracingLifespanHook(settings)
    await hook.__aenter__()
    # This must not raise AttributeError or similar
    await hook.__aexit__(None, None, None)


# ---------------------------------------------------------------------------
# ARCHITECTURAL — I3
# ---------------------------------------------------------------------------

async def test_i3_tracing_raises_import_error_when_otel_absent_and_enabled():
    """When tracing=True but opentelemetry packages absent, ImportError with hint."""
    # Temporarily hide opentelemetry
    otel_modules = {k: v for k, v in sys.modules.items() if "opentelemetry" in k}
    for k in otel_modules:
        sys.modules[k] = None  # type: ignore[assignment]
    # Also remove cached observability module so it re-imports
    obs_key = "fast_agent_stack.core.observability"
    cached = sys.modules.pop(obs_key, None)
    try:
        from fast_agent_stack.core.observability import TracingLifespanHook
        settings = _settings(tracing_enabled=True)
        hook = TracingLifespanHook(settings)
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[tracing\\]"):
            await hook.__aenter__()
    finally:
        for k, v in otel_modules.items():
            sys.modules[k] = v
        if cached is not None:
            sys.modules[obs_key] = cached
        else:
            sys.modules.pop(obs_key, None)


async def test_i3_tracing_no_import_error_when_otel_absent_and_disabled():
    """When tracing=False, no ImportError even if OTel absent."""
    otel_modules = {k: v for k, v in sys.modules.items() if "opentelemetry" in k}
    for k in otel_modules:
        sys.modules[k] = None  # type: ignore[assignment]
    obs_key = "fast_agent_stack.core.observability"
    cached = sys.modules.pop(obs_key, None)
    try:
        from fast_agent_stack.core.observability import TracingLifespanHook
        settings = _settings(tracing_enabled=False)
        hook = TracingLifespanHook(settings)
        await hook.__aenter__()
        await hook.__aexit__(None, None, None)
    finally:
        for k, v in otel_modules.items():
            sys.modules[k] = v
        if cached is not None:
            sys.modules[obs_key] = cached
        else:
            sys.modules.pop(obs_key, None)


# ---------------------------------------------------------------------------
# CONTRACT — settings defaults
# ---------------------------------------------------------------------------

def test_tracing_settings_defaults():
    s = BaseSettings(app_name="test")
    assert s.tracing_enabled is False
    assert s.otel_exporter_endpoint == "http://localhost:4317"
