"""Sending through Meta's WhatsApp Cloud API."""

import logging
import uuid

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

# Meta's codes for sending too fast, which are worth retrying even on a 4xx response
RATE_LIMIT_CODES = {4, 80007, 130429, 131048, 131056}

# Replaced by tests with a fake Meta
transport: httpx.AsyncBaseTransport | None = None


class SendRejected(Exception):
    """Meta refused this message for good. Retrying won't help."""


class TemporarySendError(Exception):
    """Worth trying again later."""


async def _post(payload: dict) -> dict:
    settings = get_settings()
    url = f"https://graph.facebook.com/{settings.graph_api_version}/{settings.whatsapp_line_id}/messages"
    try:
        async with httpx.AsyncClient(transport=transport, timeout=20) as client:
            response = await client.post(
                url,
                json={"messaging_product": "whatsapp", **payload},
                headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            )
    except httpx.HTTPError as exc:
        raise TemporarySendError(f"Couldn't reach Meta: {type(exc).__name__}") from exc

    if response.is_success:
        return response.json()
    try:
        error = response.json().get("error") or {}
    except ValueError:
        error = {}
    summary = f"HTTP {response.status_code}, code {error.get('code', 'unknown')}: {error.get('message', '')}"[:500]
    if response.status_code >= 500 or response.status_code == 429 or error.get("code") in RATE_LIMIT_CODES:
        raise TemporarySendError(summary)
    raise SendRejected(summary)


async def send_text(to_phone: str, body: str, *, quoting: str | None = None) -> str:
    """Returns Meta's ID for the sent message."""
    if get_settings().whatsapp_dry_run:
        log.info("Dry run: would send a text message")
        return f"dryrun.{uuid.uuid4()}"
    payload: dict = {
        "to": to_phone.lstrip("+"),
        "type": "text",
        "text": {"body": body, "preview_url": False},
    }
    if quoting:
        payload["context"] = {"message_id": quoting}
    result = await _post(payload)
    try:
        return result["messages"][0]["id"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TemporarySendError("Meta's response had no message ID") from exc


async def send_read_receipt(provider_message_id: str) -> None:
    """Shows the rep blue ticks."""
    if get_settings().whatsapp_dry_run:
        return
    await _post({"status": "read", "message_id": provider_message_id})
