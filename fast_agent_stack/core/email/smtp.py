"""SMTP email backend using aiosmtplib (ADR-018, ADR-041)."""
from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    import aiosmtplib
except ImportError as _exc:
    raise ImportError(
        "aiosmtplib is required for the SMTP email backend. "
        "Install it with: pip install fast-agent-stack[email-smtp]"
    ) from _exc

from fast_agent_stack.core.config import BaseSettings
from fast_agent_stack.core.email import EmailDeliveryError

logger = logging.getLogger(__name__)


class SmtpEmailBackend:
    """Sends email via aiosmtplib (async SMTP, I2-compliant)."""

    def __init__(self, settings: BaseSettings) -> None:
        self._settings = settings

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None:
        settings = self._settings

        if body_html:
            msg: MIMEMultipart | MIMEText = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.email_from_name} <{settings.email_from}>"
            msg["To"] = to
            msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))
        else:
            msg = MIMEText(body_text, "plain")
            msg["Subject"] = subject
            msg["From"] = f"{settings.email_from_name} <{settings.email_from}>"
            msg["To"] = to

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                use_tls=settings.smtp_use_tls,
            )
        except aiosmtplib.SMTPException as exc:
            raise EmailDeliveryError(str(exc)) from exc
