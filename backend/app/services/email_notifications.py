from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import get_settings


def _build_message(*, recipient: str, subject: str, body: str) -> EmailMessage:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    return message


def send_email_notification(*, recipient: str, subject: str, body: str) -> bool:
    """Send email only when SMTP is configured; keeps local demos safe and deterministic."""
    settings = get_settings()
    if not recipient or not settings.smtp_host or not settings.smtp_from_email:
        return False
    message = _build_message(recipient=recipient, subject=subject, body=body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
    return True


def send_procurement_email(*, recipient: str, subject: str, body: str) -> bool:
    return send_email_notification(recipient=recipient, subject=subject, body=body)


def smtp_configuration_status() -> dict[str, object]:
    settings = get_settings()
    return {
        "configured": bool(settings.smtp_host and settings.smtp_from_email),
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "use_tls": settings.smtp_use_tls,
        "username_configured": bool(settings.smtp_username),
        "from_email": settings.smtp_from_email,
    }
