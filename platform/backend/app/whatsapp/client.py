"""Sending through Meta's WhatsApp Cloud API."""

import logging
import struct
import uuid
import zlib
from dataclasses import dataclass

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

# Meta's codes for sending too fast, which are worth retrying even on a 4xx response
RATE_LIMIT_CODES = {4, 80007, 130429, 131048, 131056}
# Larger than WhatsApp allows for images and voice notes
MAX_MEDIA_BYTES = 20 * 1024 * 1024

# Replaced by tests with a fake Meta
transport: httpx.AsyncBaseTransport | None = None


class SendRejected(Exception):
    """Meta refused this message for good. Retrying won't help."""


class TemporarySendError(Exception):
    """Worth trying again later."""


@dataclass(frozen=True)
class Sender:
    """A customer's own number and its token. Without one, messages go from Devliqly's number."""

    phone_number_id: str
    access_token: str


async def _post(payload: dict, sender: Sender | None = None) -> dict:
    settings = get_settings()
    line_id = sender.phone_number_id if sender else settings.whatsapp_line_id
    token = sender.access_token if sender else settings.whatsapp_access_token
    url = f"https://graph.facebook.com/{settings.graph_api_version}/{line_id}/messages"
    try:
        async with httpx.AsyncClient(transport=transport, timeout=20) as client:
            response = await client.post(
                url,
                json={"messaging_product": "whatsapp", **payload},
                headers={"Authorization": f"Bearer {token}"},
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
    return _message_id(await _post(payload))


def _message_id(result: dict) -> str:
    try:
        return result["messages"][0]["id"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TemporarySendError("Meta's response had no message ID") from exc


async def send_buttons(to_phone: str, body: str, buttons: list[dict], *, quoting: str | None = None) -> str:
    """Up to three tappable replies. Each button is {"id": ..., "title": ...}."""
    if get_settings().whatsapp_dry_run:
        log.info("Dry run: would send a message with buttons")
        return f"dryrun.{uuid.uuid4()}"
    payload: dict = {
        "to": to_phone.lstrip("+"),
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body[:1024]},
            "action": {"buttons": [{"type": "reply", "reply": button} for button in buttons[:3]]},
        },
    }
    if quoting:
        payload["context"] = {"message_id": quoting}
    return _message_id(await _post(payload))


async def send_reaction(to_phone: str, provider_message_id: str, emoji: str) -> None:
    if get_settings().whatsapp_dry_run:
        return
    await _post(
        {
            "to": to_phone.lstrip("+"),
            "type": "reaction",
            "reaction": {"message_id": provider_message_id, "emoji": emoji},
        }
    )


async def send_template(
    to_phone: str, template: str, language: str, parameters: list[str], *, sender: Sender | None = None
) -> str:
    """The only way to start a conversation with someone: Meta requires a pre-approved template."""
    if get_settings().whatsapp_dry_run:
        log.info("Dry run: would send a template message")
        return f"dryrun.{uuid.uuid4()}"
    components = [{"type": "body", "parameters": [{"type": "text", "text": value} for value in parameters]}]
    return _message_id(
        await _post(
            {
                "to": to_phone.lstrip("+"),
                "type": "template",
                "template": {"name": template, "language": {"code": language}, "components": components},
            },
            sender,
        )
    )


def _sample_image() -> bytes:
    """A plain grey PNG, so the local simulator has a photo to store and show."""
    width, height = 350, 200
    row = b"\x00" + b"\xc8\xc8\xd2" * width

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = zlib.compress(row * height)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


async def download_media(media_id: str) -> tuple[bytes, str]:
    """Returns the file and its type. Meta's download link needs the same token as sending."""
    settings = get_settings()
    if settings.whatsapp_dry_run:
        return _sample_image(), "image/png"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    try:
        async with httpx.AsyncClient(transport=transport, timeout=30) as client:
            info = await client.get(
                f"https://graph.facebook.com/{settings.graph_api_version}/{media_id}", headers=headers
            )
            if info.status_code >= 500 or info.status_code == 429:
                raise TemporarySendError(f"Couldn't look up media: HTTP {info.status_code}")
            if not info.is_success:
                raise SendRejected(f"Meta wouldn't give us this media: HTTP {info.status_code}")
            details = info.json()
            if int(details.get("file_size") or 0) > MAX_MEDIA_BYTES:
                raise SendRejected("This file is too large")
            download = await client.get(details["url"], headers=headers)
    except httpx.HTTPError as exc:
        raise TemporarySendError(f"Couldn't reach Meta: {type(exc).__name__}") from exc
    if not download.is_success:
        raise TemporarySendError(f"Couldn't download media: HTTP {download.status_code}")
    if len(download.content) > MAX_MEDIA_BYTES:
        raise SendRejected("This file is too large")
    return download.content, details.get("mime_type") or "application/octet-stream"


async def send_read_receipt(provider_message_id: str) -> None:
    """Shows the rep blue ticks."""
    if get_settings().whatsapp_dry_run:
        return
    await _post({"status": "read", "message_id": provider_message_id})
