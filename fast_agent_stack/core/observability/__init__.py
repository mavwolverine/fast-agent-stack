"""OpenTelemetry tracing lifespan hook (ADR-009)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fast_agent_stack.core.config import BaseSettings

logger = logging.getLogger(__name__)


class TracingLifespanHook:
    """Async context manager that initialises (and shuts down) OTel tracing.

    Pure no-op when tracing_enabled=False — does not import opentelemetry at all
    so the package is not required in that case (I3).
    """

    def __init__(self, settings: BaseSettings) -> None:
        self._settings = settings
        self.tracer_provider: Any | None = None

    async def __aenter__(self) -> "TracingLifespanHook":
        if not self._settings.tracing_enabled:
            return self

        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError as exc:
            raise ImportError(
                f"opentelemetry packages are required for tracing: {exc}. "
                "Install them with: pip install fast-agent-stack[tracing]"
            ) from exc

        exporter = OTLPSpanExporter(endpoint=self._settings.otel_exporter_endpoint)
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        self.tracer_provider = provider
        logger.info("OpenTelemetry tracing initialised (endpoint=%s)",
                    self._settings.otel_exporter_endpoint)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.tracer_provider is None:
            return
        await asyncio.to_thread(self.tracer_provider.shutdown)
        logger.info("OpenTelemetry tracer provider shut down")
