"""Email delivery protocol and factory (ADR-018, ADR-041)."""

from __future__ import annotations

import importlib
import logging
from typing import Protocol, runtime_checkable

from fast_agent_stack.core.config import BaseSettings

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when the email backend cannot deliver a message."""


@runtime_checkable
class EmailProtocol(Protocol):
    async def send(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None: ...


def get_email_backend(settings: BaseSettings) -> EmailProtocol:
    """Return an EmailProtocol implementation based on settings.email_backend.

    Accepts the alias ``smtp`` or a dotted import path (ADR-012).
    """
    alias = settings.email_backend

    if alias == "smtp":
        from fast_agent_stack.core.email.smtp import SmtpEmailBackend

        return SmtpEmailBackend(settings)

    # Dotted-path custom backend (ADR-012)
    if "." in alias:
        module_path, cls_name = alias.rsplit(".", 1)
        try:
            mod = importlib.import_module(module_path)
        except ImportError as exc:
            raise ImportError(f"Could not import email backend '{alias}': {exc}") from exc
        cls = getattr(mod, cls_name)
        return cls()  # type: ignore[no-any-return]

    raise ValueError(f"Unknown email_backend alias '{alias}'. Use 'smtp' or a dotted import path.")
