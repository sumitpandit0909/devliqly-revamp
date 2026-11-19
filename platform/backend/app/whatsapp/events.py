"""Reading Meta's webhook deliveries: is it really from Meta, and what does it contain?"""

import hashlib
import hmac
from collections.abc import Collection
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
    # Which of our numbers it arrived on: Devliqly's own, or a customer's
    line_id: str | None = None

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
    line_id: str | None = None

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


def _read_message(raw: dict, names: dict[str, str], line_id: str) -> IncomingMessage | None:
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
        line_id=line_id,
    )


def _read_receipt(raw: dict, line_id: str) -> DeliveryReceipt | None:
    provider_id, status = raw.get("id"), raw.get("status")
    if not provider_id or not status:
        return None
    errors = raw.get("errors") or []
    error = None
    if errors and isinstance(errors[0], dict):
        error = f"{errors[0].get('code', 'unknown')}: {errors[0].get('title', '')}".strip()
    return DeliveryReceipt(provider_id, status, error, line_id)


def _changes(body: dict):
    for entry in body.get("entry") or []:
        for change in (entry or {}).get("changes") or []:
            yield entry or {}, change or {}


def read_delivery(body: dict, line_ids: str | Collection[str]) -> tuple[list[IncomingMessage], list[DeliveryReceipt]]:
    """Pull messages and receipts for our numbers out of a webhook body. Anything unrecognised is skipped."""
    wanted = {line_ids} if isinstance(line_ids, str) else set(line_ids)
    messages: list[IncomingMessage] = []
    receipts: list[DeliveryReceipt] = []
    for _, change in _changes(body):
        # Chat history from a WhatsApp Business app number looks like messages, but isn't new mail
        if change.get("field", "messages") != "messages":
            continue
        value = change.get("value") or {}
        line_id = (value.get("metadata") or {}).get("phone_number_id")
        if line_id not in wanted:
            continue
        names = {
            contact.get("wa_id"): (contact.get("profile") or {}).get("name") for contact in value.get("contacts") or []
        }
        messages += [m for raw in value.get("messages") or [] if (m := _read_message(raw, names, line_id))]
        receipts += [r for raw in value.get("statuses") or [] if (r := _read_receipt(raw, line_id))]
    return messages, receipts


def line_ids_in(body: dict) -> set[str]:
    """Every number this body mentions, so only those are looked up."""
    found = set()
    for _, change in _changes(body):
        if line_id := ((change.get("value") or {}).get("metadata") or {}).get("phone_number_id"):
            found.add(str(line_id))
    return found


@dataclass(frozen=True)
class AccountUpdate:
    waba_id: str
    event: str
    reason: str | None = None


def read_account_updates(body: dict) -> list[AccountUpdate]:
    """A customer disconnecting, or reconnecting, their WhatsApp Business app number."""
    updates = []
    for entry, change in _changes(body):
        if change.get("field") != "account_update":
            continue
        value = change.get("value") or {}
        event = value.get("event")
        waba_id = (value.get("waba_info") or {}).get("waba_id") or entry.get("id")
        if not event or not waba_id:
            continue
        reason = (value.get("disconnection_info") or {}).get("reason")
        updates.append(AccountUpdate(str(waba_id), str(event), reason))
    return updates


@dataclass(frozen=True)
class HistoryProgress:
    line_id: str
    progress: int | None
    not_shared: bool = False


# The business chose not to share its chat history
HISTORY_NOT_SHARED = 2593109


def read_history_progress(body: dict) -> list[HistoryProgress]:
    """How far a WhatsApp Business app number's history sync has got. The messages themselves aren't kept."""
    found = []
    for _, change in _changes(body):
        if change.get("field") != "history":
            continue
        value = change.get("value") or {}
        line_id = (value.get("metadata") or {}).get("phone_number_id")
        if not line_id:
            continue
        for chunk in value.get("history") or []:
            codes = {error.get("code") for error in chunk.get("errors") or [] if isinstance(error, dict)}
            progress = (chunk.get("metadata") or {}).get("progress")
            found.append(
                HistoryProgress(
                    str(line_id),
                    int(progress) if isinstance(progress, int | str) and str(progress).isdigit() else None,
                    HISTORY_NOT_SHARED in codes,
                )
            )
    return found
