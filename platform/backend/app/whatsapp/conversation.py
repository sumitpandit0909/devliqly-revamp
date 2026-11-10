"""Background work for WhatsApp. Each handler runs in the transaction that marks its job done."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConversationMessage, Membership, Organization, RepConversation, User, WebhookInbox
from app.queue import ClaimedJob, enqueue, job_handler
from app.whatsapp import client

log = logging.getLogger(__name__)

ROUTE_MESSAGE = "route_incoming_message"
APPLY_RECEIPT = "apply_delivery_receipt"
SEND_MESSAGE = "send_conversation_message"
SEND_NOTICE = "send_notice_to_stranger"
SEND_READ_RECEIPT = "send_read_receipt"

STRANGER_NOTICE = (
    "This WhatsApp number is for registered Devliqly users. Please ask your company admin to add your number."
)
RECEIVED_REPLY = "Thanks, we've received your message."

# Reactions and unsupported types are saved but need no answer
KINDS_WITHOUT_REPLY = {"reaction", "unsupported", "sticker"}
# Status only moves forward, since Meta's receipts can arrive out of order
STATUS_RANK = {"queued": 0, "sent": 1, "delivered": 2, "read": 3}
# A receipt can arrive before our send has been saved, so it gets a few chances to find its message
RECEIPT_ATTEMPTS = 4


async def _find_rep(db: AsyncSession, phone: str) -> Membership | None:
    membership = await db.scalar(
        select(Membership)
        .join(User, Membership.user_id == User.id)
        .join(Organization, Membership.organization_id == Organization.id)
        .where(User.phone_e164 == phone, User.is_active, Membership.is_active, Organization.is_active)
        .order_by(Membership.created_at)
        .limit(1)
    )
    return membership


async def _conversation_for(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> RepConversation:
    await db.execute(
        insert(RepConversation)
        .values(organization_id=org_id, rep_user_id=user_id)
        .on_conflict_do_nothing(constraint="uq_rep_conversations_organization_rep")
    )
    return await db.scalar(
        select(RepConversation).where(RepConversation.organization_id == org_id, RepConversation.rep_user_id == user_id)
    )


@job_handler(ROUTE_MESSAGE)
async def route_incoming_message(db: AsyncSession, job: ClaimedJob) -> None:
    inbox = await db.get(WebhookInbox, uuid.UUID(job.payload["inbox_id"]))
    if inbox is None:
        return
    item = inbox.payload
    phone = item["sender_phone"]

    membership = await _find_rep(db, phone)
    if membership is None:
        # Answer at most once a day, so a stranger's messages can't be used to make us send endlessly
        today = datetime.now(UTC).date().isoformat()
        await enqueue(db, SEND_NOTICE, {"phone": phone}, lock_key=f"out:{phone}", dedupe_key=f"notice:{phone}:{today}")
        return

    org_id = membership.organization_id
    conversation = await _conversation_for(db, org_id, membership.user_id)
    details = {
        key: item[key]
        for key in ("media_id", "media_mime", "button_id", "sender_name", "sent_at", "extra")
        if item.get(key)
    }
    saved = await db.execute(
        insert(ConversationMessage)
        .values(
            organization_id=org_id,
            conversation_id=conversation.id,
            direction="in",
            kind=item["kind"],
            body=item.get("text"),
            provider_message_id=item["provider_id"],
            quotes_provider_id=item.get("quoted_provider_id"),
            details=details,
            status="received",
        )
        .on_conflict_do_nothing(index_elements=[ConversationMessage.provider_message_id])
        .returning(ConversationMessage.id)
    )
    if saved.first() is None:
        return
    conversation.last_inbound_at = datetime.now(UTC)
    await enqueue(db, SEND_READ_RECEIPT, {"provider_message_id": item["provider_id"]})

    if item["kind"] not in KINDS_WITHOUT_REPLY:
        # Later phases replace this with the card pipeline and conversation states
        reply = ConversationMessage(
            organization_id=org_id,
            conversation_id=conversation.id,
            direction="out",
            kind="text",
            body=RECEIVED_REPLY,
            quotes_provider_id=item["provider_id"],
            details={"to_phone": phone},
            status="queued",
        )
        db.add(reply)
        await db.flush()
        await enqueue(db, SEND_MESSAGE, {"message_id": str(reply.id)}, lock_key=f"out:{phone}")


@job_handler(SEND_MESSAGE)
async def send_conversation_message(db: AsyncSession, job: ClaimedJob) -> None:
    message = await db.scalar(
        select(ConversationMessage)
        .where(ConversationMessage.id == uuid.UUID(job.payload["message_id"]))
        .with_for_update()
    )
    if message is None or message.status != "queued":
        return
    try:
        message.provider_message_id = await client.send_text(
            message.details["to_phone"], message.body or "", quoting=message.quotes_provider_id
        )
        message.status = "sent"
    except client.SendRejected as exc:
        # Handled, not raised: retrying can't help, and the failure is recorded on the message
        message.status = "failed"
        message.error = str(exc)
        log.warning("Meta rejected message %s: %s", message.id, exc)


@job_handler(SEND_NOTICE)
async def send_notice_to_stranger(_: AsyncSession, job: ClaimedJob) -> None:
    try:
        await client.send_text(job.payload["phone"], STRANGER_NOTICE)
    except client.SendRejected as exc:
        log.warning("Meta rejected a notice: %s", exc)


@job_handler(SEND_READ_RECEIPT)
async def send_read_receipt(_: AsyncSession, job: ClaimedJob) -> None:
    try:
        await client.send_read_receipt(job.payload["provider_message_id"])
    except client.SendRejected as exc:
        log.info("Meta rejected a read receipt: %s", exc)


@job_handler(APPLY_RECEIPT)
async def apply_delivery_receipt(db: AsyncSession, job: ClaimedJob) -> None:
    inbox = await db.get(WebhookInbox, uuid.UUID(job.payload["inbox_id"]))
    if inbox is None:
        return
    receipt = inbox.payload
    message = await db.scalar(
        select(ConversationMessage)
        .where(ConversationMessage.provider_message_id == receipt["provider_id"])
        .with_for_update()
    )
    if message is None:
        if job.attempts < job.max_attempts:
            raise LookupError("The message for this receipt isn't saved yet")
        # Notices to strangers aren't saved as messages, so their receipts end up here
        log.info("Dropping a receipt with no matching message")
        return
    status = receipt["status"]
    if status == "failed":
        if message.status != "read":
            message.status = "failed"
            message.error = receipt.get("error")
    elif status in STATUS_RANK and STATUS_RANK[status] > STATUS_RANK.get(message.status, 4):
        message.status = status
