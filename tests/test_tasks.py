"""Tests for Phase 6-1: Background Tasks (ADR-005, ADR-020)."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
import typer

from fast_agent_stack.core.config import BaseSettings


def _settings(**kw) -> BaseSettings:
    return BaseSettings(app_name="test", redis_url="redis://localhost:6379", **kw)


# ---------------------------------------------------------------------------
# ARCHITECTURAL — I3 guards
# ---------------------------------------------------------------------------

def test_configure_broker_raises_import_error_when_dramatiq_absent():
    original = sys.modules.get("dramatiq")
    sys.modules["dramatiq"] = None  # type: ignore[assignment]
    try:
        # Force re-import after patching
        if "fast_agent_stack.core.tasks" in sys.modules:
            del sys.modules["fast_agent_stack.core.tasks"]
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[tasks\\]"):
            from fast_agent_stack.core.tasks import configure_broker  # noqa: F401
    finally:
        if original is None:
            sys.modules.pop("dramatiq", None)
        else:
            sys.modules["dramatiq"] = original
        sys.modules.pop("fast_agent_stack.core.tasks", None)


def test_scheduler_raises_import_error_when_periodiq_absent():
    original = sys.modules.get("periodiq")
    sys.modules["periodiq"] = None  # type: ignore[assignment]
    try:
        if "fast_agent_stack.cli.scheduler_cmd" in sys.modules:
            del sys.modules["fast_agent_stack.cli.scheduler_cmd"]
        from fast_agent_stack.cli.scheduler_cmd import scheduler
        with pytest.raises((ImportError, SystemExit, typer.Exit)):
            scheduler(["myapp.tasks"])
    finally:
        if original is None:
            sys.modules.pop("periodiq", None)
        else:
            sys.modules["periodiq"] = original
        sys.modules.pop("fast_agent_stack.cli.scheduler_cmd", None)


# ---------------------------------------------------------------------------
# ARCHITECTURAL — CLI commands registered
# ---------------------------------------------------------------------------

def test_worker_command_registered_on_cli_app():
    from fast_agent_stack.cli.main import app
    command_names = [cmd.name for cmd in app.registered_commands]
    assert "worker" in command_names


def test_scheduler_command_registered_on_cli_app():
    from fast_agent_stack.cli.main import app
    command_names = [cmd.name for cmd in app.registered_commands]
    assert "scheduler" in command_names


# ---------------------------------------------------------------------------
# CONTRACT — settings field
# ---------------------------------------------------------------------------

def test_tasks_broker_url_defaults_to_none():
    s = BaseSettings(app_name="test")
    assert s.tasks_broker_url is None


def test_tasks_broker_url_can_be_set():
    s = _settings(tasks_broker_url="redis://tasks:6379")
    assert s.tasks_broker_url == "redis://tasks:6379"


# ---------------------------------------------------------------------------
# BEHAVIOR — configure_broker (requires dramatiq)
# ---------------------------------------------------------------------------

def test_configure_broker_returns_broker_instance():
    dramatiq = pytest.importorskip("dramatiq")
    from fast_agent_stack.core.tasks import configure_broker
    settings = _settings()
    with patch("dramatiq.set_broker"), \
         patch("dramatiq.brokers.redis.RedisBroker") as mock_broker_cls:
        mock_broker = MagicMock(spec=dramatiq.Broker)
        mock_broker_cls.return_value = mock_broker
        result = configure_broker(settings)
        assert result is mock_broker


def test_configure_broker_uses_tasks_broker_url_over_redis_url():
    pytest.importorskip("dramatiq")
    from fast_agent_stack.core.tasks import configure_broker
    settings = _settings(tasks_broker_url="redis://tasks:6379")
    captured = {}
    with patch("dramatiq.brokers.redis.RedisBroker") as mock_cls, \
         patch("dramatiq.set_broker"):
        mock_cls.side_effect = lambda url, **kw: captured.update({"url": url}) or MagicMock()
        configure_broker(settings)
    assert captured.get("url") == "redis://tasks:6379"


def test_configure_broker_falls_back_to_redis_url():
    pytest.importorskip("dramatiq")
    from fast_agent_stack.core.tasks import configure_broker
    settings = _settings(redis_url="redis://primary:6379")
    captured = {}
    with patch("dramatiq.brokers.redis.RedisBroker") as mock_cls, \
         patch("dramatiq.set_broker"):
        mock_cls.side_effect = lambda url, **kw: captured.update({"url": url}) or MagicMock()
        configure_broker(settings)
    assert captured.get("url") == "redis://primary:6379"
