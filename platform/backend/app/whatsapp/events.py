"""Reading Meta's webhook deliveries: is it really from Meta, and what does it contain?"""

import hashlib
import hmac
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


def signature_is_valid(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    if not header or not app_secret:
        return False
    expected = "sha256=" + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


@dataclass(frozen=True)
class IncomingMessage:
    provider_id: str
    sender_phone: str
    kind: str
    sent_at: str | None = None
    sender_name: str | None = None
    text: str | None = None
    media_id: str | None = None
    media_mime: str | None = None
    button_id: str | None = None
    quoted_provider_id: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def event_key(self) -> str:
        return f"message:{self.provider_id}"

    def to_payload(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DeliveryReceipt:
    provider_id: str
    status: str
    error: str | None = None

    @property
    def event_key(self) -> str:
        return f"receipt:{self.provider_id}:{self.status}"

    def to_payload(self) -> dict:
        return asdict(self)


MEDIA_KINDS = {"image", "document", "audio", "video", "sticker"}


def _timestamp(value: object) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), UTC).isoformat()  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _read_message(raw: dict, names: dict[str, str]) -> IncomingMessage | None:
    provider_id, sender, kind = raw.get("id"), raw.get("from"), raw.get("type")
    if not provider_id or not sender or not kind:
        return None
    text = media_id = media_mime = button_id = None
    extra: dict = {}
    if kind == "text":
        text = (raw.get("text") or {}).get("body")
    elif kind in MEDIA_KINDS:
        media = raw.get(kind) or {}
        media_id, media_mime, text = media.get("id"), media.get("mime_type"), media.get("caption")
    elif kind == "interactive":
        interactive = raw.get("interactive") or {}
        choice = interactive.get("button_reply") or interactive.get("list_reply") or {}
        kind, button_id, text = "button", choice.get("id"), choice.get("title")
    elif kind == "button":
        button = raw.get("button") or {}
        button_id, text = button.get("payload"), button.get("text")
    elif kind in {"location", "contacts", "reaction"}:
        extra = {kind: raw.get(kind)}
    return IncomingMessage(
        provider_id=provider_id,
        sender_phone=f"+{str(sender).lstrip('+')}",
        kind=kind,
        sent_at=_timestamp(raw.get("timestamp")),
        sender_name=names.get(sender),
        text=text,
        media_id=media_id,
        media_mime=media_mime,
        button_id=button_id,
        quoted_provider_id=(raw.get("context") or {}).get("id"),
        extra=extra,
    )


def _read_receipt(raw: dict) -> DeliveryReceipt | None:
    provider_id, status = raw.get("id"), raw.get("status")
    if not provider_id or not status:
        return None
    errors = raw.get("errors") or []
    error = None
    if errors and isinstance(errors[0], dict):
        error = f"{errors[0].get('code', 'unknown')}: {errors[0].get('title', '')}".strip()
    return DeliveryReceipt(provider_id, status, error)


def read_delivery(body: dict, line_id: str) -> tuple[list[IncomingMessage], list[DeliveryReceipt]]:
    """Pull messages and receipts for our number out of a webhook body. Anything unrecognised is skipped."""
    messages: list[IncomingMessage] = []
    receipts: list[DeliveryReceipt] = []
    for entry in body.get("entry") or []:
        for change in (entry or {}).get("changes") or []:
            value = (change or {}).get("value") or {}
            if (value.get("metadata") or {}).get("phone_number_id") != line_id:
                continue
            names = {
                contact.get("wa_id"): (contact.get("profile") or {}).get("name")
                for contact in value.get("contacts") or []
            }
            messages += [m for raw in value.get("messages") or [] if (m := _read_message(raw, names))]
            receipts += [r for raw in value.get("statuses") or [] if (r := _read_receipt(raw))]
    return messages, receipts
