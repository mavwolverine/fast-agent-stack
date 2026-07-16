"""OpenTelemetry tracing lifespan hook (ADR-009)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fast_agent_stack.core.config import BaseSettings

logger = logging.getLogger(__name__)


class TracingLifespanHook:
    """Async context manager that initialises (and shuts down) OTel tracing.

    Pure no-op when tracing_enabled=False - does not import opentelemetry at all
    so the package is not required in that case (I3).
    """

    def __init__(self, settings: BaseSettings, *, app: Any = None) -> None:
        self._settings = settings
        self._app = app
        self.tracer_provider: Any | None = None

        # Instrument the app at registration time (before the ASGI middleware stack is frozen)
        if app is not None and settings.tracing_enabled:
            try:
                from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

                FastAPIInstrumentor.instrument_app(app)
            except ImportError:
                pass  # Will raise properly in __aenter__

    async def __aenter__(self) -> TracingLifespanHook:
        if not self._settings.tracing_enabled:
            return self

        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError as exc:
            raise ImportError(
                f"opentelemetry packages are required for tracing: {exc}. "
                "Install them with: pip install fast-agent-stack[tracing]"
            ) from exc

        service_name = self._settings.app_name if hasattr(self._settings, "app_name") else "fast-agent-stack"
        try:
            resource = Resource.create({"service.name": service_name})
            exporter = OTLPSpanExporter(
                endpoint=self._settings.otel_exporter_endpoint,
                insecure=not self._settings.otel_exporter_endpoint.startswith("https"),
            )
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            self.tracer_provider = provider

            logger.info(
                "OpenTelemetry tracing initialised (service=%s, endpoint=%s)",
                service_name,
                self._settings.otel_exporter_endpoint,
            )
        except Exception:
            logger.warning("Failed to initialise OpenTelemetry tracing - continuing without tracing", exc_info=True)

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.tracer_provider is None:
            return
        if self._app is not None:
            try:
                from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

                FastAPIInstrumentor.uninstrument_app(self._app)
            except Exception:
                pass
        await asyncio.to_thread(self.tracer_provider.shutdown)
        logger.info("OpenTelemetry tracer provider shut down")
