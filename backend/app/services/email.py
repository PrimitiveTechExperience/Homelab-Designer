import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> None:
    """Send a plain-text email. The "console" backend just logs it (local dev and tests)."""
    settings = get_settings()
    if settings.email_backend == "console":
        logger.info("EMAIL to=%s subject=%s\n%s", to, subject, body)
        return

    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def send_verification_email(to: str, username: str, token: str) -> None:
    link = f"{get_settings().frontend_url}/verify-email?token={token}"
    send_email(
        to,
        "Confirm your Homelab Parts Finder account",
        f"Hi {username},\n\nConfirm your account by opening this link:\n{link}\n\n"
        "The link expires in 24 hours. If you didn't sign up, ignore this email.\n",
    )
