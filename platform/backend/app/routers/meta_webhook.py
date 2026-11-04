"""Where Meta delivers WhatsApp events. Verifies, saves, queues and answers quickly; the worker does the rest."""

import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.db import set_scope
from app.deps import Db
from app.models import WebhookInbox
from app.queue import enqueue, wake_worker
from app.whatsapp.events import read_delivery, signature_is_valid
from app.whatsapp.jobs import APPLY_RECEIPT, RECEIPT_ATTEMPTS, ROUTE_MESSAGE

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/meta", tags=["webhooks"], include_in_schema=False)

MAX_BODY_BYTES = 3 * 1024 * 1024


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
        messages, receipts = read_delivery(body, settings.whatsapp_line_id)
    except (ValueError, AttributeError, TypeError):
        # It's genuinely from Meta but unreadable, and a retry would be just as unreadable
        log.warning("Ignored a signed webhook body that couldn't be read")
        return {"status": "ignored"}

    await set_scope(db, system=True)
    for message in messages:
        if inbox_id := await _save_once(db, message.event_key, "message", message.to_payload()):
            # The rep's messages are handled strictly in order
            await enqueue(db, ROUTE_MESSAGE, {"inbox_id": inbox_id}, lock_key=f"in:{message.sender_phone}")
    for receipt in receipts:
        if inbox_id := await _save_once(db, receipt.event_key, "receipt", receipt.to_payload()):
            await enqueue(db, APPLY_RECEIPT, {"inbox_id": inbox_id}, max_attempts=RECEIPT_ATTEMPTS)
    await db.commit()
    wake_worker()
    return {"status": "accepted"}
