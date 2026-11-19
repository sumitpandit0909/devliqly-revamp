"""What a rep's WhatsApp messages do. Each handler runs in the transaction that marks its job done.

A photo always means a new card, unless the rep was asked for the back of one. Buttons and awaited replies follow fixed
code paths with no AI. Only free text and voice notes go to the AI, and it can only choose from a short list of actions.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import ai
from app.cards import (
    CleanCard,
    add_activity,
    apply_changes,
    clean_reading,
    describe_contact,
    fill_blanks,
    has_card_quota,
    running_events,
    save_contact_and_lead,
    take_card_quota,
    today_in_india,
)
from app.db import only_this_customer
from app.followups import consent_at_capture, plan_follow_ups, record_opt_out
from app.models import (
    BusinessCard,
    Contact,
    ConversationMessage,
    ExpoEvent,
    FollowUp,
    Lead,
    Membership,
    Organization,
    RepConversation,
    User,
    WebhookInbox,
)
from app.queue import ClaimedJob, enqueue, job_handler
from app.storage import get_storage
from app.whatsapp import agent, client

log = logging.getLogger(__name__)

ROUTE_MESSAGE = "route_incoming_message"
APPLY_RECEIPT = "apply_delivery_receipt"
SEND_MESSAGE = "send_conversation_message"
SEND_NOTICE = "send_notice_to_stranger"
SEND_READ_RECEIPT = "send_read_receipt"
SEND_REACTION = "send_reaction"
CAPTURE_CARD = "capture_card"
SAVE_CARD = "save_card"
READ_BACK = "read_card_back"
APPLY_CORRECTION = "apply_card_correction"
READ_VOICE = "read_voice_note"
RUN_AGENT = "run_rep_request"

STRANGER_NOTICE = (
    "This WhatsApp number is for registered Devliqly users. Please ask your company admin to add your number."
)
OPT_OUT_CONFIRMATION = "You've been unsubscribed and won't get further WhatsApp messages from this number."
HELP_TEXT = agent.HELP_TEXT
UNSUPPORTED = "I can read card photos, notes and voice notes. Please send one of those."
OVER_QUOTA = "Your company has reached this month's card limit, so this card wasn't saved. Please tell your admin."
NOT_A_CARD = "That doesn't look like a business card, so I didn't save it. Please send a clear photo of the card."
CANT_READ = "I saved this photo, but couldn't read it just now. It's waiting in the CRM's review queue."
CANT_DOWNLOAD = "I couldn't download that file. Please send it again."
NOTHING_TO_ATTACH = "That card isn't available any more. Please find it in the CRM."
STATE_MINUTES = 10
# A voice note this soon after a card is assumed to be about that card
RECENT_CARD_MINUTES = 30
READ_ATTEMPTS = 4

STOP_WORDS = {"stop", "unsubscribe"}
EVENT_WORDS = {"event", "events", "change event"}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
HOURGLASS, TICK, WARNING, CROSS = "⏳", "✅", "⚠️", "❌"

# Reactions and unsupported types are saved but need no answer
KINDS_WITHOUT_REPLY = {"reaction", "unsupported", "sticker"}
# Status only moves forward, since Meta's receipts can arrive out of order
STATUS_RANK = {"queued": 0, "sent": 1, "delivered": 2, "read": 3}
# A receipt can arrive before our send has been saved, so it gets a few chances to find its message
RECEIPT_ATTEMPTS = 4


@dataclass(frozen=True)
class RepTurn:
    """The rep and message a handler is acting for."""

    org_id: uuid.UUID
    rep_user_id: uuid.UUID
    phone: str
    conversation_id: uuid.UUID
    provider_id: str

    def to_payload(self) -> dict:
        return {
            "org_id": str(self.org_id),
            "rep_user_id": str(self.rep_user_id),
            "phone": self.phone,
            "conversation_id": str(self.conversation_id),
            "provider_id": self.provider_id,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "RepTurn":
        return cls(
            uuid.UUID(payload["org_id"]),
            uuid.UUID(payload["rep_user_id"]),
            payload["phone"],
            uuid.UUID(payload["conversation_id"]),
            payload["provider_id"],
        )

    @property
    def rep_lock(self) -> str:
        return f"rep:{self.rep_user_id}"


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


async def _reply(
    db: AsyncSession,
    turn: RepTurn,
    body: str,
    *,
    quoting: str | None = None,
    buttons: list[dict] | None = None,
    card_id: uuid.UUID | None = None,
) -> None:
    details: dict = {"to_phone": turn.phone}
    if buttons:
        details["buttons"] = buttons
    if card_id:
        details["card_id"] = str(card_id)
    reply = ConversationMessage(
        organization_id=turn.org_id,
        conversation_id=turn.conversation_id,
        direction="out",
        kind="buttons" if buttons else "text",
        body=body,
        quotes_provider_id=quoting or turn.provider_id,
        details=details,
        status="queued",
    )
    db.add(reply)
    await db.flush()
    await enqueue(db, SEND_MESSAGE, {"message_id": str(reply.id)}, lock_key=f"out:{turn.phone}")


async def _react(db: AsyncSession, turn: RepTurn, emoji: str, provider_id: str | None = None) -> None:
    # Only a courtesy, so it mustn't hold up the replies queued behind it for long
    await enqueue(
        db,
        SEND_REACTION,
        {"phone": turn.phone, "provider_message_id": provider_id or turn.provider_id, "emoji": emoji},
        lock_key=f"out:{turn.phone}",
        max_attempts=2,
    )


def _set_state(conversation: RepConversation, state: str, **data) -> None:
    conversation.state = state
    conversation.state_data = data
    conversation.state_expires_at = datetime.now(UTC) + timedelta(minutes=STATE_MINUTES)


def _clear_state(conversation: RepConversation) -> None:
    conversation.state = "idle"
    conversation.state_data = {}
    conversation.state_expires_at = None


async def _rep_card(db: AsyncSession, turn: RepTurn, card_id: object) -> BusinessCard | None:
    """Only this rep's cards, whatever ID a message claims."""
    try:
        parsed = uuid.UUID(str(card_id))
    except ValueError:
        return None
    return await db.scalar(
        select(BusinessCard).where(
            BusinessCard.id == parsed,
            BusinessCard.organization_id == turn.org_id,
            BusinessCard.rep_user_id == turn.rep_user_id,
        )
    )


async def _card_from_quote(db: AsyncSession, turn: RepTurn, quoted_id: str | None) -> BusinessCard | None:
    """A rep replying to a confirmation, or to the photo itself, means that card."""
    if not quoted_id:
        return None
    photo = await db.scalar(
        select(BusinessCard).where(
            BusinessCard.provider_message_id == quoted_id,
            BusinessCard.organization_id == turn.org_id,
            BusinessCard.rep_user_id == turn.rep_user_id,
        )
    )
    if photo is not None:
        return photo
    message = await db.scalar(
        select(ConversationMessage).where(
            ConversationMessage.provider_message_id == quoted_id, ConversationMessage.organization_id == turn.org_id
        )
    )
    card_id = message.details.get("card_id") if message else None
    return await _rep_card(db, turn, card_id) if card_id else None


async def _event_for_new_card(db: AsyncSession, conversation: RepConversation) -> uuid.UUID | None:
    events = await running_events(db, conversation.organization_id)
    if conversation.current_event_id in {event.id for event in events}:
        return conversation.current_event_id
    today = today_in_india()
    candidates = events if len(events) == 1 else [e for e in events if e.starts_on and e.starts_on <= today]
    if len(candidates) == 1:
        conversation.current_event_id = candidates[0].id
        return candidates[0].id
    return None


async def _on_photo(db: AsyncSession, turn: RepTurn, conversation: RepConversation, item: dict) -> None:
    if conversation.state == "awaiting_back":
        card = await _rep_card(db, turn, conversation.state_data.get("card_id"))
        _clear_state(conversation)
        if card is not None:
            await _react(db, turn, HOURGLASS)
            payload = {**turn.to_payload(), "card_id": str(card.id), "media_id": item["media_id"]}
            await enqueue(db, READ_BACK, payload, lock_key=turn.rep_lock, max_attempts=READ_ATTEMPTS)
            return
    if not await has_card_quota(db, turn.org_id):
        await _reply(db, turn, OVER_QUOTA)
        return
    card = BusinessCard(
        organization_id=turn.org_id,
        rep_user_id=turn.rep_user_id,
        expo_event_id=await _event_for_new_card(db, conversation),
        provider_message_id=turn.provider_id,
        caption=item.get("text"),
    )
    db.add(card)
    await db.flush()
    await _react(db, turn, HOURGLASS)
    # Cards are read in parallel, then saved one at a time per rep
    payload = {**turn.to_payload(), "card_id": str(card.id), "media_id": item["media_id"]}
    await enqueue(db, CAPTURE_CARD, payload, max_attempts=READ_ATTEMPTS)


async def _on_button(db: AsyncSession, turn: RepTurn, conversation: RepConversation, item: dict) -> None:
    action, _, card_id = (item.get("button_id") or "").partition(":")
    card = await _rep_card(db, turn, card_id)
    if card is None:
        await _reply(db, turn, NOTHING_TO_ATTACH)
        return
    if action == "back":
        _set_state(conversation, "awaiting_back", card_id=str(card.id))
        await _reply(db, turn, "Please send a photo of the back of the card.")
    elif action == "note":
        _set_state(conversation, "awaiting_note", card_id=str(card.id))
        await _reply(db, turn, "Send your note, as text or a voice note.")
    elif action == "fix":
        _set_state(conversation, "awaiting_correction", card_id=str(card.id))
        await _reply(db, turn, "What should change? For example: phone is 98765 43210, title is Sales Head.")
    else:
        await _reply(db, turn, UNSUPPORTED)


async def _note_on_card(db: AsyncSession, turn: RepTurn, card: BusinessCard, note: str) -> None:
    lead = await db.get(Lead, card.lead_id) if card.lead_id else None
    if lead is None:
        await _reply(db, turn, "This card isn't saved yet, so I can't add a note to it. Please use the CRM.")
        return
    await add_activity(db, lead, "note", note, actor_user_id=turn.rep_user_id)
    contact = await db.get(Contact, lead.contact_id)
    await _reply(db, turn, f"\U0001f4dd Note added to {describe_contact(contact)}.")


async def _list_events(db: AsyncSession, turn: RepTurn, conversation: RepConversation) -> None:
    events = await running_events(db, turn.org_id)
    if not events:
        await _reply(db, turn, "No events are set up. Your admin can add them in the CRM.")
        return
    lines = [f"{number}. {event.name}" for number, event in enumerate(events[:20], start=1)]
    _set_state(conversation, "awaiting_event", options=[str(event.id) for event in events[:20]])
    await _reply(db, turn, "Which event are you at? Reply with the number.\n" + "\n".join(lines))


async def _use_event(db: AsyncSession, turn: RepTurn, conversation: RepConversation, event: ExpoEvent) -> None:
    conversation.current_event_id = event.id
    _clear_state(conversation)
    # Cards from today that arrived before the rep chose. A lead already at this event stays as it is.
    today_start = datetime.combine(today_in_india(), datetime.min.time(), tzinfo=UTC) - timedelta(hours=6)
    existing = select(Lead.contact_id).where(Lead.organization_id == turn.org_id, Lead.expo_event_id == event.id)
    await db.execute(
        update(Lead)
        .where(
            Lead.organization_id == turn.org_id,
            Lead.owner_user_id == turn.rep_user_id,
            Lead.expo_event_id.is_(None),
            Lead.created_at >= today_start,
            Lead.contact_id.not_in(existing),
        )
        .values(expo_event_id=event.id)
    )
    await db.execute(
        update(BusinessCard)
        .where(
            BusinessCard.organization_id == turn.org_id,
            BusinessCard.rep_user_id == turn.rep_user_id,
            BusinessCard.expo_event_id.is_(None),
            BusinessCard.created_at >= today_start,
        )
        .values(expo_event_id=event.id)
    )
    await _reply(db, turn, f"\U0001f4cd New cards will be tagged {event.name}.")


async def _event_by_id(db: AsyncSession, org_id: uuid.UUID, event_id: str) -> ExpoEvent | None:
    return await db.scalar(
        select(ExpoEvent).where(ExpoEvent.id == uuid.UUID(event_id), ExpoEvent.organization_id == org_id)
    )


async def _on_text(db: AsyncSession, turn: RepTurn, conversation: RepConversation, item: dict) -> None:
    message = (item.get("text") or "").strip()
    lowered = message.lower()

    if lowered in {"help", "menu", "hi", "hello"}:
        _clear_state(conversation)
        await _reply(db, turn, HELP_TEXT)
        return
    if lowered in EVENT_WORDS:
        await _list_events(db, turn, conversation)
        return

    if conversation.state == "awaiting_event":
        options = conversation.state_data.get("options") or []
        if lowered.isdigit() and 1 <= int(lowered) <= len(options):
            event = await _event_by_id(db, turn.org_id, options[int(lowered) - 1])
            if event is not None:
                await _use_event(db, turn, conversation, event)
                return
        _clear_state(conversation)

    if conversation.state == "awaiting_correction":
        card = await _rep_card(db, turn, conversation.state_data.get("card_id"))
        _clear_state(conversation)
        if card is not None:
            payload = {**turn.to_payload(), "card_id": str(card.id), "text": message}
            await enqueue(db, APPLY_CORRECTION, payload, lock_key=turn.rep_lock, max_attempts=READ_ATTEMPTS)
            return

    if conversation.state == "awaiting_note":
        card = await _rep_card(db, turn, conversation.state_data.get("card_id"))
        _clear_state(conversation)
        if card is not None:
            await _note_on_card(db, turn, card, message)
            return

    quoted = await _card_from_quote(db, turn, item.get("quoted_provider_id"))
    if quoted is not None:
        await _note_on_card(db, turn, quoted, message)
        return

    payload = {**turn.to_payload(), "text": message}
    await enqueue(db, RUN_AGENT, payload, lock_key=turn.rep_lock, max_attempts=READ_ATTEMPTS)


async def _on_voice(db: AsyncSession, turn: RepTurn, conversation: RepConversation, item: dict) -> None:
    card = None
    if conversation.state == "awaiting_note":
        card = await _rep_card(db, turn, conversation.state_data.get("card_id"))
        _clear_state(conversation)
    card = card or await _card_from_quote(db, turn, item.get("quoted_provider_id"))
    if card is None:
        since = datetime.now(UTC) - timedelta(minutes=RECENT_CARD_MINUTES)
        card = await db.scalar(
            select(BusinessCard)
            .where(
                BusinessCard.organization_id == turn.org_id,
                BusinessCard.rep_user_id == turn.rep_user_id,
                BusinessCard.status == "saved",
                BusinessCard.created_at >= since,
            )
            .order_by(BusinessCard.created_at.desc())
            .limit(1)
        )
    await _react(db, turn, HOURGLASS)
    payload = {
        **turn.to_payload(),
        "media_id": item["media_id"],
        "media_mime": item.get("media_mime") or "audio/ogg",
        "card_id": str(card.id) if card else None,
    }
    await enqueue(db, READ_VOICE, payload, lock_key=turn.rep_lock, max_attempts=READ_ATTEMPTS)


async def _on_stranger(db: AsyncSession, phone: str, item: dict) -> None:
    today = datetime.now(UTC).date().isoformat()
    if item["kind"] in {"text", "button"} and (item.get("text") or "").strip().lower() in STOP_WORDS:
        # A prospect saying stop applies at every customer holding their number
        org_ids = await db.scalars(select(Contact.organization_id).where(Contact.phone_e164 == phone).distinct())
        for org_id in org_ids.all():
            await record_opt_out(db, org_id, "whatsapp", phone, "whatsapp_reply")
        await enqueue(
            db,
            SEND_NOTICE,
            {"phone": phone, "body": OPT_OUT_CONFIRMATION},
            lock_key=f"out:{phone}",
            dedupe_key=f"opt-out:{phone}:{today}",
        )
        return
    # Answer at most once a day, so a stranger's messages can't be used to make us send endlessly
    await enqueue(db, SEND_NOTICE, {"phone": phone}, lock_key=f"out:{phone}", dedupe_key=f"notice:{phone}:{today}")


def _is_photo(item: dict) -> bool:
    if not item.get("media_id"):
        return False
    return item["kind"] == "image" or (
        item["kind"] == "document" and (item.get("media_mime") or "").split(";")[0] in IMAGE_TYPES
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
        await _on_stranger(db, phone, item)
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
    if conversation.state_expires_at and conversation.state_expires_at < datetime.now(UTC):
        _clear_state(conversation)
    await enqueue(db, SEND_READ_RECEIPT, {"provider_message_id": item["provider_id"]})

    turn = RepTurn(org_id, membership.user_id, phone, conversation.id, item["provider_id"])
    kind = item["kind"]
    if _is_photo(item):
        await _on_photo(db, turn, conversation, item)
    elif kind == "button":
        await _on_button(db, turn, conversation, item)
    elif kind == "audio" and item.get("media_id"):
        await _on_voice(db, turn, conversation, item)
    elif kind == "text":
        await _on_text(db, turn, conversation, item)
    elif kind not in KINDS_WITHOUT_REPLY:
        await _reply(db, turn, UNSUPPORTED)


async def _send_to_review(db: AsyncSession, turn: RepTurn, card: BusinessCard, problem: str) -> None:
    card.status = "review"
    card.problems = [*card.problems, problem]
    await _react(db, turn, WARNING)
    await _reply(db, turn, CANT_READ, card_id=card.id)


async def _download_photo(db: AsyncSession, turn: RepTurn, job: ClaimedJob) -> tuple[bytes, str] | None:
    """The photo, or None if there's no point trying again; the rep has then been told."""
    try:
        data, mime = await client.download_media(job.payload["media_id"])
    except client.TemporarySendError:
        if job.attempts < job.max_attempts:
            raise
        data, mime = None, ""
    except client.SendRejected:
        data, mime = None, ""
    mime = mime.split(";")[0].strip().lower()
    if data is None or mime not in IMAGE_TYPES:
        await _react(db, turn, CROSS)
        await _reply(db, turn, CANT_DOWNLOAD)
        return None
    return data, mime


@job_handler(CAPTURE_CARD)
async def capture_card(db: AsyncSession, job: ClaimedJob) -> None:
    turn = RepTurn.from_payload(job.payload)
    card = await db.get(BusinessCard, uuid.UUID(job.payload["card_id"]))
    if card is None or card.status != "received":
        return
    photo = await _download_photo(db, turn, job)
    if photo is None:
        card.status = "failed"
        return
    data, mime = photo
    card.front_mime = mime
    card.front_key = f"{card.organization_id}/cards/{card.id}/front"
    await get_storage().put(card.front_key, data, mime)
    try:
        reading = await ai.read_card(card.organization_id, data, mime)
    except ai.AiRefused as exc:
        await _send_to_review(db, turn, card, f"Not read automatically: {exc}")
        return
    except ai.AiError as exc:
        if job.attempts < job.max_attempts:
            raise
        await _send_to_review(db, turn, card, f"Not read automatically: {exc}")
        return
    card.reading = reading.model_dump()
    card.status = "read"
    await enqueue(db, SAVE_CARD, job.payload, lock_key=turn.rep_lock)


def _confirmation(saved, clean: CleanCard, event_name: str | None, needs_event: bool) -> str:
    contact = saved.contact
    title = contact.job_title
    company = contact.company.name if contact.company else None
    name = contact.full_name or company or "New contact"
    headline = f"{TICK} Saved: {name}" if saved.new_lead else f"{TICK} Already saved, updated: {name}"
    lines = [headline]
    if contact.full_name and (title or company):
        lines.append(" at ".join(part for part in (title, company) if part))
    if contact.phone_e164:
        lines.append(f"\U0001f4de {contact.phone_e164}")
    if contact.email:
        lines.append(f"✉️ {contact.email}")
    if event_name:
        lines.append(f"\U0001f4cd {event_name}")
    if clean.problems:
        lines.append(f"{WARNING} Please check: " + "; ".join(clean.problems)[:300])
    if needs_event:
        lines.append("Which event is this for? Reply *event* to choose.")
    return "\n".join(lines)


def _card_buttons(card_id: uuid.UUID) -> list[dict]:
    return [
        {"id": f"back:{card_id}", "title": "Add back side"},
        {"id": f"note:{card_id}", "title": "Add note"},
        {"id": f"fix:{card_id}", "title": "Wrong details"},
    ]


@job_handler(SAVE_CARD)
async def save_card(db: AsyncSession, job: ClaimedJob) -> None:
    """One transaction: company, contact, lead, card, quota and follow-ups all save, or none do."""
    turn = RepTurn.from_payload(job.payload)
    card = await db.get(BusinessCard, uuid.UUID(job.payload["card_id"]))
    if card is None or card.status != "read":
        return
    reading = ai.CardReading.model_validate(card.reading)
    if not reading.is_business_card:
        card.status = "rejected"
        await _react(db, turn, CROSS)
        await _reply(db, turn, NOT_A_CARD)
        return
    clean = clean_reading(reading)
    card.problems = clean.problems
    if not clean.usable:
        card.status = "review"
        await _react(db, turn, WARNING)
        await _reply(
            db,
            turn,
            f"{WARNING} I couldn't save this: " + "; ".join(clean.problems)[:300] + ". It's waiting for "
            "review in the CRM.",
            card_id=card.id,
        )
        return
    if not await take_card_quota(db, card.organization_id):
        card.status = "over_quota"
        await _react(db, turn, WARNING)
        await _reply(db, turn, OVER_QUOTA)
        return

    saved = await save_contact_and_lead(
        db,
        card.organization_id,
        clean,
        owner_user_id=card.rep_user_id,
        event_id=card.expo_event_id,
        needs_review=bool(clean.problems),
    )
    card.contact_id = saved.contact.id
    card.lead_id = saved.lead.id
    card.status = "saved"
    if card.caption:
        await add_activity(db, saved.lead, "note", card.caption, actor_user_id=card.rep_user_id)
    if saved.new_lead:
        await consent_at_capture(db, saved.lead, saved.contact)
    await plan_follow_ups(db, saved.lead, saved.contact)

    event_name = None
    needs_event = False
    if card.expo_event_id:
        event_name = await db.scalar(select(ExpoEvent.name).where(ExpoEvent.id == card.expo_event_id))
    else:
        needs_event = bool(await running_events(db, card.organization_id))
    await _react(db, turn, TICK)
    await _reply(
        db,
        turn,
        _confirmation(saved, clean, event_name, needs_event),
        buttons=_card_buttons(card.id),
        card_id=card.id,
    )


def _merge_readings(front: ai.CardReading, back: ai.CardReading) -> ai.CardReading:
    """The front wins; the back only fills gaps and adds numbers and emails."""
    return ai.CardReading(
        is_business_card=front.is_business_card or back.is_business_card,
        full_name=front.full_name or back.full_name,
        job_title=front.job_title or back.job_title,
        company=front.company or back.company,
        phones=[*front.phones, *(p for p in back.phones if p not in front.phones)],
        emails=[*front.emails, *(e for e in back.emails if e not in front.emails)],
        website=front.website or back.website,
        address=front.address or back.address,
        unsure_fields=[*front.unsure_fields, *back.unsure_fields],
        confidence=max(front.confidence, back.confidence),
    )


@job_handler(READ_BACK)
async def read_card_back(db: AsyncSession, job: ClaimedJob) -> None:
    turn = RepTurn.from_payload(job.payload)
    card = await db.get(BusinessCard, uuid.UUID(job.payload["card_id"]))
    if card is None:
        return
    photo = await _download_photo(db, turn, job)
    if photo is None:
        return
    data, mime = photo
    card.back_mime = mime
    card.back_key = f"{card.organization_id}/cards/{card.id}/back"
    await get_storage().put(card.back_key, data, mime)
    try:
        back = await ai.read_card(card.organization_id, data, mime)
    except ai.AiRefused:
        await _react(db, turn, WARNING)
        await _reply(db, turn, "I saved the back of the card, but couldn't read it.", card_id=card.id)
        return
    except ai.AiError:
        if job.attempts < job.max_attempts:
            raise
        await _react(db, turn, WARNING)
        await _reply(db, turn, "I saved the back of the card, but couldn't read it.", card_id=card.id)
        return

    merged = _merge_readings(ai.CardReading.model_validate(card.reading), back) if card.reading else back
    card.reading = merged.model_dump()
    clean = clean_reading(merged)
    await _react(db, turn, TICK)
    if card.contact_id:
        contact = await db.get(Contact, card.contact_id)
        fill_blanks(contact, clean)
        await db.flush()
        lead = await db.get(Lead, card.lead_id)
        await add_activity(db, lead, "back_added", actor_user_id=turn.rep_user_id)
        await plan_follow_ups(db, lead, contact)
        await _reply(db, turn, f"{TICK} Added the back of the card for {describe_contact(contact)}.", card_id=card.id)
    elif card.status == "review" and clean.usable:
        # The back supplied what was missing, so the card can now be saved normally
        card.status = "read"
        await enqueue(db, SAVE_CARD, job.payload, lock_key=turn.rep_lock)
    else:
        await _reply(db, turn, "Added the back of the card. It's still waiting for review in the CRM.", card_id=card.id)


@job_handler(APPLY_CORRECTION)
async def apply_card_correction(db: AsyncSession, job: ClaimedJob) -> None:
    turn = RepTurn.from_payload(job.payload)
    card = await db.get(BusinessCard, uuid.UUID(job.payload["card_id"]))
    if card is None:
        return
    if not card.contact_id:
        await _reply(db, turn, "This card isn't saved yet, so please correct it in the CRM's review queue.")
        return
    contact = await db.get(Contact, card.contact_id)
    current = {
        "full_name": contact.full_name or "",
        "job_title": contact.job_title or "",
        "company": contact.company.name if contact.company else "",
        "phone": contact.phone_e164 or "",
        "email": contact.email or "",
    }
    try:
        correction = await ai.understand_correction(card.organization_id, job.payload["text"], current)
    except ai.AiRefused:
        await _reply(db, turn, "I couldn't work that out. Please correct this card in the CRM.")
        return
    except ai.AiError:
        if job.attempts < job.max_attempts:
            raise
        await _reply(db, turn, "I couldn't work that out just now. Please try again in a minute.")
        return

    lead = await db.get(Lead, card.lead_id) if card.lead_id else None
    changes = {key: value for key, value in correction.model_dump().items() if value}
    changed, problems = await apply_changes(db, contact, changes)
    if changed and lead is not None:
        lead.needs_review = False
        await add_activity(
            db, lead, "correction", ", ".join(changed), actor_user_id=turn.rep_user_id, details={"fields": changed}
        )
        await plan_follow_ups(db, lead, contact)
    lines = []
    if changed:
        lines.append(f"{TICK} Updated {', '.join(changed)} for {describe_contact(contact)}.")
    lines += problems
    await _reply(db, turn, "\n".join(lines) or "I didn't find anything to change. Please try rewording it.")


@job_handler(READ_VOICE)
async def read_voice_note(db: AsyncSession, job: ClaimedJob) -> None:
    turn = RepTurn.from_payload(job.payload)
    try:
        audio, mime = await client.download_media(job.payload["media_id"])
    except client.SendRejected:
        await _reply(db, turn, CANT_DOWNLOAD)
        return
    except client.TemporarySendError:
        if job.attempts < job.max_attempts:
            raise
        await _reply(db, turn, CANT_DOWNLOAD)
        return
    try:
        # The audio isn't stored, only what was said
        voice = await ai.read_voice_note(turn.org_id, audio, job.payload["media_mime"] or mime, today_in_india())
    except ai.AiNotConfigured:
        await _reply(db, turn, "Voice notes aren't set up yet. Please type it instead.")
        return
    except ai.AiRefused:
        await _reply(db, turn, "I couldn't understand that voice note. Please type it instead.")
        return
    except ai.AiError:
        if job.attempts < job.max_attempts:
            raise
        await _reply(db, turn, "I couldn't process that voice note just now. Please try again in a minute.")
        return

    card = await _rep_card(db, turn, job.payload["card_id"]) if job.payload.get("card_id") else None
    lead = await db.get(Lead, card.lead_id) if card and card.lead_id else None
    if lead is None:
        reply = await _agent_reply(db, turn, voice.transcript)
        await _react(db, turn, TICK)
        await _reply(db, turn, reply)
        return
    await add_activity(
        db,
        lead,
        "voice_note",
        voice.summary or voice.transcript,
        actor_user_id=turn.rep_user_id,
        details={"transcript": voice.transcript},
    )
    lead.interest = voice.interest or lead.interest
    lead.next_step = voice.next_step or lead.next_step
    follow_up_on = agent.valid_date(voice.follow_up_date)
    lead.follow_up_on = follow_up_on or lead.follow_up_on
    contact = await db.get(Contact, lead.contact_id)
    lines = [f"{TICK} Added to {describe_contact(contact)}: {voice.summary or voice.transcript}"[:900]]
    if voice.interest:
        lines.append(f"Interest: {voice.interest}")
    if voice.next_step:
        lines.append(f"Next step: {voice.next_step}"[:200])
    if follow_up_on:
        lines.append(f"Follow up: {follow_up_on.isoformat()}")
    await _react(db, turn, TICK)
    await _reply(db, turn, "\n".join(lines))


async def _agent_reply(db: AsyncSession, turn: RepTurn, message: str) -> str:
    request = await ai.understand_request(turn.org_id, message, today_in_india())
    # What a person typed steers the actions below, so the database itself holds them to this customer
    async with only_this_customer(db, turn.org_id):
        return await agent.carry_out(db, turn.org_id, turn.rep_user_id, request)


@job_handler(RUN_AGENT)
async def run_rep_request(db: AsyncSession, job: ClaimedJob) -> None:
    turn = RepTurn.from_payload(job.payload)
    try:
        reply = await _agent_reply(db, turn, job.payload["text"])
    except ai.AiRefused:
        reply = HELP_TEXT
    except ai.AiError:
        if job.attempts < job.max_attempts:
            raise
        reply = "I couldn't process that just now. Please try again in a minute."
    await _reply(db, turn, reply)


@job_handler(SEND_MESSAGE)
async def send_conversation_message(db: AsyncSession, job: ClaimedJob) -> None:
    message = await db.scalar(
        select(ConversationMessage)
        .where(ConversationMessage.id == uuid.UUID(job.payload["message_id"]))
        .with_for_update()
    )
    if message is None or message.status != "queued":
        return
    phone, buttons = message.details["to_phone"], message.details.get("buttons")
    try:
        if buttons:
            message.provider_message_id = await client.send_buttons(
                phone, message.body or "", buttons, quoting=message.quotes_provider_id
            )
        else:
            message.provider_message_id = await client.send_text(
                phone, message.body or "", quoting=message.quotes_provider_id
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
        await client.send_text(job.payload["phone"], job.payload.get("body") or STRANGER_NOTICE)
    except client.SendRejected as exc:
        log.warning("Meta rejected a notice: %s", exc)


@job_handler(SEND_READ_RECEIPT)
async def send_read_receipt(_: AsyncSession, job: ClaimedJob) -> None:
    try:
        await client.send_read_receipt(job.payload["provider_message_id"])
    except client.SendRejected as exc:
        log.info("Meta rejected a read receipt: %s", exc)


@job_handler(SEND_REACTION)
async def send_reaction(_: AsyncSession, job: ClaimedJob) -> None:
    try:
        await client.send_reaction(job.payload["phone"], job.payload["provider_message_id"], job.payload["emoji"])
    except client.SendRejected as exc:
        log.info("Meta rejected a reaction: %s", exc)
    except client.TemporarySendError:
        if job.attempts < job.max_attempts:
            raise


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
        follow_up = await db.scalar(
            select(FollowUp).where(FollowUp.provider_message_id == receipt["provider_id"]).with_for_update()
        )
        if follow_up is not None:
            if receipt["status"] == "failed":
                follow_up.status = "failed"
                follow_up.error = receipt.get("error")
            return
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
