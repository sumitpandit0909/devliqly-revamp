"""Where Meta delivers WhatsApp events. Verifies, saves, queues and answers quickly; the worker does the rest."""

import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.db import set_scope
from app.deps import Db
from app.models import WebhookInbox, WhatsAppLine
from app.queue import enqueue, wake_worker
from app.whatsapp.conversation import APPLY_RECEIPT, RECEIPT_ATTEMPTS, ROUTE_MESSAGE
from app.whatsapp.events import (
    line_ids_in,
    read_account_updates,
    read_delivery,
    read_history_progress,
    signature_is_valid,
)
from app.whatsapp.lines import ROUTE_LINE_MESSAGE

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/meta", tags=["webhooks"], include_in_schema=False)

MAX_BODY_BYTES = 3 * 1024 * 1024
# A customer disconnected their WhatsApp Business app number from us, or it stopped working
DISCONNECTED_EVENTS = {"PARTNER_REMOVED", "ACCOUNT_OFFBOARDED", "ACCOUNT_DISCONNECTED"}


@router.get("", response_class=PlainTextResponse)
async def confirm_subscription(
    mode: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
) -> str:
    """Meta calls this once when the webhook is connected, to check it's really ours."""
    expected = get_settings().whatsapp_verify_token
    if mode != "subscribe" or not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verification failed")
    return challenge


async def _save_once(db: Db, event_key: str, kind: str, payload: dict) -> str | None:
    """Returns the new row's ID, or None if this event was already saved."""
    result = await db.execute(
        insert(WebhookInbox)
        .values(event_key=event_key, kind=kind, payload=payload)
        .on_conflict_do_nothing(index_elements=[WebhookInbox.event_key])
        .returning(WebhookInbox.id)
    )
    row = result.first()
    return str(row.id) if row else None


@router.post("")
async def receive_delivery(request: Request, db: Db) -> dict[str, str]:
    settings = get_settings()
    if not settings.whatsapp_app_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "WhatsApp isn't configured")
    if int(request.headers.get("content-length") or 0) > MAX_BODY_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Body too large")
    raw_body = await request.body()
    if len(raw_body) > MAX_BODY_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Body too large")
    # Checked before parsing anything, so unverified input never gets further than this
    if not signature_is_valid(raw_body, request.headers.get("x-hub-signature-256"), settings.whatsapp_app_secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid signature")

    try:
        body = json.loads(raw_body)
        mentioned = line_ids_in(body)
        updates = read_account_updates(body)
        history = read_history_progress(body)
    except (ValueError, AttributeError, TypeError):
        # It's genuinely from Meta but unreadable, and a retry would be just as unreadable
        log.warning("Ignored a signed webhook body that couldn't be read")
        return {"status": "ignored"}

    await set_scope(db, system=True)
    customer_lines = {}
    if mentioned - {settings.whatsapp_line_id}:
        rows = await db.scalars(select(WhatsAppLine).where(WhatsAppLine.phone_number_id.in_(mentioned)))
        customer_lines = {line.phone_number_id: line for line in rows}
    try:
        messages, receipts = read_delivery(body, {settings.whatsapp_line_id, *customer_lines})
    except (ValueError, AttributeError, TypeError):
        log.warning("Ignored a signed webhook body that couldn't be read")
        return {"status": "ignored"}

    for message in messages:
        if message.line_id in customer_lines:
            # Someone writing to a customer's own number. Riya stays out of it; only STOP is acted on.
            if inbox_id := await _save_once(db, message.event_key, "line_message", message.to_payload()):
                await enqueue(db, ROUTE_LINE_MESSAGE, {"inbox_id": inbox_id})
        elif inbox_id := await _save_once(db, message.event_key, "message", message.to_payload()):
            # The rep's messages are handled strictly in order
            await enqueue(db, ROUTE_MESSAGE, {"inbox_id": inbox_id}, lock_key=f"in:{message.sender_phone}")
    for receipt in receipts:
        if inbox_id := await _save_once(db, receipt.event_key, "receipt", receipt.to_payload()):
            await enqueue(db, APPLY_RECEIPT, {"inbox_id": inbox_id}, max_attempts=RECEIPT_ATTEMPTS)
    for update in updates:
        await _apply_account_update(db, update.waba_id, update.event, update.reason)
    for step in history:
        if line := customer_lines.get(step.line_id):
            _apply_history(line, step.progress, step.not_shared)
    await db.commit()
    wake_worker()
    return {"status": "accepted"}


async def _apply_account_update(db: Db, waba_id: str, event: str, reason: str | None) -> None:
    lines = await db.scalars(select(WhatsAppLine).where(WhatsAppLine.waba_id == waba_id))
    for line in lines:
        if event in DISCONNECTED_EVENTS:
            line.status = "disconnected"
            line.disconnect_reason = (reason or event).replace("_", " ").lower()[:200]
        elif event == "ACCOUNT_RECONNECTED":
            line.status = "connected"
            line.disconnect_reason = None


def _apply_history(line: WhatsAppLine, progress: int | None, not_shared: bool) -> None:
    if not_shared:
        line.history_status = "not_shared"
    elif progress is not None:
        line.history_progress = max(progress, line.history_progress or 0)
        line.history_status = "done" if line.history_progress >= 100 else "syncing"
