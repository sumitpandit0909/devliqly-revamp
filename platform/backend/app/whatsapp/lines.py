"""Customers' own WhatsApp numbers: who sends from them, and what happens when someone writes to one.

Riya never answers on a customer's number. On a WhatsApp Business app number the customer reads and replies in the
app; our only job is to notice when someone asks to stop.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import followups
from app.models import WebhookInbox, WhatsAppLine
from app.queue import ClaimedJob, job_handler
from app.secrets_box import unseal
from app.whatsapp.client import Sender

ROUTE_LINE_MESSAGE = "route_customer_line_message"
STOP_WORDS = {"stop", "unsubscribe"}


async def sender_for(db: AsyncSession, org_id: uuid.UUID) -> Sender | None:
    """The customer's own connected number, or None to send from Devliqly's."""
    line = await db.scalar(
        select(WhatsAppLine).where(WhatsAppLine.organization_id == org_id, WhatsAppLine.status == "connected")
    )
    if line is None:
        return None
    return Sender(line.phone_number_id, unseal(line.access_token_sealed))


@job_handler(ROUTE_LINE_MESSAGE)
async def route_customer_line_message(db: AsyncSession, job: ClaimedJob) -> None:
    inbox = await db.get(WebhookInbox, uuid.UUID(job.payload["inbox_id"]))
    if inbox is None:
        return
    item = inbox.payload
    line = await db.scalar(select(WhatsAppLine).where(WhatsAppLine.phone_number_id == item.get("line_id")))
    if line is None:
        return
    if item["kind"] in {"text", "button"} and (item.get("text") or "").strip().lower() in STOP_WORDS:
        await followups.record_opt_out(db, line.organization_id, "whatsapp", item["sender_phone"], "whatsapp_reply")
