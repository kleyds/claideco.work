from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def _smtp_config() -> dict[str, str | int | bool | None]:
    return {
        "host": os.getenv("SMTP_HOST"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER"),
        "password": os.getenv("SMTP_PASSWORD"),
        "from_email": os.getenv("SMTP_FROM", os.getenv("SMTP_USER")),
        "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true",
    }


def _frontend_base_url() -> str:
    return os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")


def send_verification_email(*, to_email: str, name: str, token: str) -> None:
    config = _smtp_config()
    verify_link = f"{_frontend_base_url()}/verify-email?token={token}"

    subject = "Verify your PesoBooks email"
    text_body = (
        f"Hi {name},\n\n"
        f"Welcome to PesoBooks. Please verify your email by clicking the link below:\n\n"
        f"{verify_link}\n\n"
        f"This link expires in 24 hours. If you did not create this account, ignore this email.\n"
    )
    html_body = (
        f"<p>Hi {name},</p>"
        f"<p>Welcome to PesoBooks. Please verify your email by clicking the link below:</p>"
        f'<p><a href="{verify_link}">Verify my email</a></p>'
        f"<p>This link expires in 24 hours. If you did not create this account, ignore this email.</p>"
    )

    if not config["host"] or not config["from_email"]:
        logger.warning(
            "SMTP not configured; skipping email send. Verification link for %s: %s",
            to_email,
            verify_link,
        )
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config["from_email"]
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(config["host"], config["port"], timeout=15) as smtp:
            smtp.ehlo()
            if config["use_tls"]:
                smtp.starttls()
                smtp.ehlo()
            if config["user"] and config["password"]:
                smtp.login(config["user"], config["password"])
            smtp.send_message(message)
    except Exception:
        logger.exception("Failed to send verification email to %s", to_email)
        raise
