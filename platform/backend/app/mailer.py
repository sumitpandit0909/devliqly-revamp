"""Sending follow-up email, through an SMTP server such as Gmail when one is set up, otherwise through Resend."""

import asyncio
import logging
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from email.utils import formataddr, formatdate

import httpx

from app.config import Settings, get_settings

log = logging.getLogger(__name__)

# Replaced by tests with a fake Resend
transport: httpx.AsyncBaseTransport | None = None
# Replaced by tests with a fake mail server
smtp_factory = None


class EmailRejected(Exception):
    """Retrying won't help."""


class TemporaryEmailError(Exception):
    """Worth trying again later."""


def _text(body: str, unsubscribe_url: str) -> str:
    return f"{body}\n\n--\nDon't want these emails? Unsubscribe: {unsubscribe_url}"


def _unsubscribe_headers(unsubscribe_url: str) -> dict[str, str]:
    return {"List-Unsubscribe": f"<{unsubscribe_url}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


async def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    sender_name: str | None,
    reply_to: str | None,
    unsubscribe_url: str,
    idempotency_key: str,
) -> str:
    """Returns the provider's message ID. The key stops a retry after a crash sending the same email twice."""
    settings = get_settings()
    if settings.email_dry_run:
        log.info("Dry run: would send an email")
        return f"dryrun.{uuid.uuid4()}"
    if not settings.email_from:
        raise EmailRejected("Email isn't set up yet: EMAIL_FROM is needed")
    if settings.smtp_host:
        message = _smtp_message(settings, to, subject, body, sender_name, reply_to, unsubscribe_url, idempotency_key)
        return await asyncio.to_thread(_send_smtp, settings, message)
    if not settings.resend_api_key:
        raise EmailRejected("Email isn't set up yet: set SMTP_HOST or RESEND_API_KEY")
    return await _send_resend(settings, to, subject, body, sender_name, reply_to, unsubscribe_url, idempotency_key)


def _smtp_message(
    settings: Settings,
    to: str,
    subject: str,
    body: str,
    sender_name: str | None,
    reply_to: str | None,
    unsubscribe_url: str,
    idempotency_key: str,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((sender_name, settings.email_from)) if sender_name else settings.email_from
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    # Fixed per follow-up, so if a retry ever does send twice, mail apps treat it as the same message
    domain = settings.email_from.rsplit("@", 1)[-1]
    message["Message-ID"] = f"<follow-up.{idempotency_key}@{domain}>"
    if reply_to:
        message["Reply-To"] = reply_to
    for name, value in _unsubscribe_headers(unsubscribe_url).items():
        message[name] = value
    message.set_content(_text(body, unsubscribe_url))
    return message


def _connect(settings: Settings) -> smtplib.SMTP:
    if smtp_factory is not None:
        return smtp_factory(settings.smtp_host, settings.smtp_port)
    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        return smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=context)
    server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
    server.starttls(context=context)
    return server


def _send_smtp(settings: Settings, message: EmailMessage) -> str:
    try:
        with _connect(settings) as server:
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailRejected("The mail server refused the login. Check SMTP_USERNAME and SMTP_PASSWORD") from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise EmailRejected("The mail server refused this address") from exc
    except smtplib.SMTPResponseException as exc:
        detail = exc.smtp_error.decode(errors="replace")[:300] if isinstance(exc.smtp_error, bytes) else ""
        if 400 <= exc.smtp_code < 500:
            raise TemporaryEmailError(f"The mail server said try later ({exc.smtp_code})") from exc
        raise EmailRejected(f"The mail server refused the email ({exc.smtp_code}): {detail}") from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise TemporaryEmailError(f"Couldn't reach the mail server: {type(exc).__name__}") from exc
    return message["Message-ID"]


async def _send_resend(
    settings: Settings,
    to: str,
    subject: str,
    body: str,
    sender_name: str | None,
    reply_to: str | None,
    unsubscribe_url: str,
    idempotency_key: str,
) -> str:
    payload = {
        "from": f"{sender_name} <{settings.email_from}>" if sender_name else settings.email_from,
        "to": [to],
        "subject": subject,
        "text": _text(body, unsubscribe_url),
        "headers": _unsubscribe_headers(unsubscribe_url),
    }
    if reply_to:
        payload["reply_to"] = reply_to
    try:
        async with httpx.AsyncClient(transport=transport, timeout=20) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers={"Authorization": f"Bearer {settings.resend_api_key}", "Idempotency-Key": idempotency_key},
            )
    except httpx.HTTPError as exc:
        raise TemporaryEmailError(f"Couldn't reach Resend: {type(exc).__name__}") from exc
    if response.status_code == 429 or response.status_code >= 500:
        raise TemporaryEmailError(f"Resend returned HTTP {response.status_code}")
    if not response.is_success:
        raise EmailRejected(f"Resend returned HTTP {response.status_code}: {response.text[:300]}")
    return response.json()["id"]
