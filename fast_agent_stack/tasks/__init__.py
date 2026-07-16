"""Public tasks facade - re-exports broker configuration (ADR-005)."""

from fast_agent_stack.core.tasks import configure_broker

__all__ = ["configure_broker"]
