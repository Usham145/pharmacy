from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import get_settings


def send_procurement_email(*, recipient: str, subject: str, body: str) -> bool:
    """Send email only when SMTP is configured; keeps local demos safe and deterministic."""
    settings = get_settings()
    if not recipient or not settings.smtp_host or not settings.smtp_from_email:
        return False
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
    return True
