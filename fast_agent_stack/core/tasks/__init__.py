"""Background task broker configuration (ADR-005, ADR-020)."""

from __future__ import annotations

import logging

from fast_agent_stack.core.config import BaseSettings

try:
    import dramatiq
    from dramatiq.brokers.redis import RedisBroker
except ImportError:
    raise ImportError(
        "dramatiq is required to use background tasks. Install it with: pip install fast-agent-stack[tasks]"
    ) from None

logger = logging.getLogger(__name__)


def configure_broker(settings: BaseSettings) -> dramatiq.Broker:
    """Wire Dramatiq to Redis. Falls back to settings.redis_url when tasks_broker_url is not set."""
    url = settings.tasks_broker_url or settings.redis_url
    broker = RedisBroker(url=url)
    dramatiq.set_broker(broker)
    logger.info("Dramatiq broker configured: %s", url)
    return broker
