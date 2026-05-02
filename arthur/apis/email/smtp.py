"""API utilities for sending e-mail via SMTP."""

import asyncio
import smtplib
from email.message import EmailMessage

from arthur.config import CONFIG

SMTP_TIMEOUT_SECONDS = 10


def _send_email_sync(recipient: str, subject: str, body: str) -> None:
    """Send an e-mail using the configured SMTP relay."""
    if not all(
        (
            CONFIG.email_host,
            CONFIG.email_from,
            CONFIG.email_username,
            CONFIG.email_password,
        )
    ):
        msg = "E-mail credentials are not fully configured."
        raise RuntimeError(msg)

    message = EmailMessage()
    message["From"] = CONFIG.email_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(CONFIG.email_host, CONFIG.email_port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
        if CONFIG.email_starttls:
            smtp.starttls()

        smtp.login(CONFIG.email_username, CONFIG.email_password.get_secret_value())
        smtp.send_message(message)


async def send_email(recipient: str, subject: str, body: str) -> None:
    """Send an e-mail without blocking the event loop."""
    await asyncio.to_thread(_send_email_sync, recipient, subject, body)
