"""Public observability facade - re-exports tracing hook (ADR-009)."""

from fast_agent_stack.core.observability import TracingLifespanHook

__all__ = ["TracingLifespanHook"]
