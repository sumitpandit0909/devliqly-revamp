"""Messages to prospects. Written to an outbox first; sent by a job that checks consent again at the last moment."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import mailer
from app.cards import add_activity
from app.config import get_settings
from app.models import Company, Contact, ExpoEvent, FollowUp, FollowUpSettings, Lead, OptOut, Organization, User
from app.queue import ClaimedJob, enqueue, job_handler
from app.whatsapp import client
from app.whatsapp.lines import sender_for

log = logging.getLogger(__name__)

SEND_FOLLOW_UP = "send_follow_up"
_UNSUBSCRIBE_AUDIENCE = "unsubscribe"
_TOKEN_ALGORITHM = "HS256"  # noqa: S105


def unsubscribe_token(org_id: uuid.UUID, email: str) -> str:
    return jwt.encode(
        {"aud": _UNSUBSCRIBE_AUDIENCE, "org": str(org_id), "email": email},
        get_settings().jwt_secret,
        algorithm=_TOKEN_ALGORITHM,
    )


def read_unsubscribe_token(token: str) -> tuple[uuid.UUID, str] | None:
    try:
        claims = jwt.decode(
            token, get_settings().jwt_secret, algorithms=[_TOKEN_ALGORITHM], audience=_UNSUBSCRIBE_AUDIENCE
        )
        return uuid.UUID(claims["org"]), claims["email"]
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def _fill_in(template: str, values: dict[str, str]) -> str:
    """Plain replacement rather than str.format, so a customer's template can't reach into Python objects."""
    for name, value in values.items():
        template = template.replace("{" + name + "}", value)
    return template


async def _template_values(db: AsyncSession, lead: Lead, contact: Contact) -> dict[str, str]:
    org_name = await db.scalar(select(Organization.name).where(Organization.id == lead.organization_id))
    rep_name = await db.scalar(select(User.full_name).where(User.id == lead.owner_user_id))
    event_name = await db.scalar(select(ExpoEvent.name).where(ExpoEvent.id == lead.expo_event_id))
    company_name = await db.scalar(select(Company.name).where(Company.id == contact.company_id))
    return {
        "first_name": (contact.full_name or "there").split()[0],
        "full_name": contact.full_name or "",
        "company": company_name or "",
        "rep_name": rep_name or org_name or "",
        "organization": org_name or "",
        "event": event_name or "",
    }


async def is_opted_out(db: AsyncSession, org_id: uuid.UUID, channel: str, address: str) -> bool:
    found = await db.scalar(
        select(OptOut.id).where(OptOut.organization_id == org_id, OptOut.channel == channel, OptOut.address == address)
    )
    return found is not None


async def record_opt_out(db: AsyncSession, org_id: uuid.UUID, channel: str, address: str, source: str) -> None:
    """Also stops anything already waiting to go to this person."""
    await db.execute(
        insert(OptOut)
        .values(id=uuid.uuid4(), organization_id=org_id, channel=channel, address=address, source=source)
        .on_conflict_do_nothing(constraint="uq_opt_outs_organization_channel_address")
    )
    waiting = await db.scalars(
        select(FollowUp).where(
            FollowUp.organization_id == org_id,
            FollowUp.channel == channel,
            FollowUp.recipient == address,
            FollowUp.status.in_(("draft", "scheduled", "failed")),
        )
    )
    for follow_up in waiting:
        follow_up.status = "blocked"
        follow_up.error = "This person opted out"


async def queue_send(db: AsyncSession, follow_up: FollowUp, delay_minutes: int = 0) -> None:
    follow_up.status = "scheduled"
    follow_up.error = None
    follow_up.send_after = datetime.now(UTC) + timedelta(minutes=delay_minutes)
    await enqueue(db, SEND_FOLLOW_UP, {"follow_up_id": str(follow_up.id)}, run_after=follow_up.send_after)


async def settings_for(db: AsyncSession, org_id: uuid.UUID) -> FollowUpSettings:
    """A customer who never opened the settings gets the defaults, which send a standard email."""
    settings = await db.get(FollowUpSettings, org_id)
    if settings is None:
        settings = FollowUpSettings(organization_id=org_id)
        db.add(settings)
        await db.flush()
    return settings


async def consent_at_capture(db: AsyncSession, lead: Lead, contact: Contact) -> None:
    """For a customer whose reps ask every visitor for WhatsApp permission, a newly saved card counts as agreed.
    Someone who said stop stays opted out."""
    settings = await settings_for(db, lead.organization_id)
    if not settings.whatsapp_consent_at_capture or contact.whatsapp_opt_in_at or not contact.phone_e164:
        return
    if await is_opted_out(db, lead.organization_id, "whatsapp", contact.phone_e164):
        return
    contact.whatsapp_opt_in_at = datetime.now(UTC)
    await add_activity(
        db, lead, "whatsapp_consent", "agreed when the card was taken", details={"source": "asked_at_capture"}
    )


async def plan_follow_ups(db: AsyncSession, lead: Lead, contact: Contact) -> None:
    """Called whenever a lead or its details change. The unique key means only a newly known channel gets a message."""
    settings = await settings_for(db, lead.organization_id)
    values = await _template_values(db, lead, contact)
    planned: list[dict] = []
    if settings.email_enabled and contact.email and settings.email_subject and settings.email_body:
        planned.append(
            {
                "channel": "email",
                "recipient": contact.email,
                "subject": _fill_in(settings.email_subject, values).replace("\r", " ").replace("\n", " ")[:200],
                "body": _fill_in(settings.email_body, values),
            }
        )
    if settings.whatsapp_enabled and settings.whatsapp_template and contact.phone_e164 and contact.whatsapp_opt_in_at:
        planned.append({"channel": "whatsapp", "recipient": contact.phone_e164, "subject": None, "body": None})

    for item in planned:
        if await is_opted_out(db, lead.organization_id, item["channel"], item["recipient"]):
            continue
        follow_up_id = uuid.uuid4()
        created = await db.execute(
            insert(FollowUp)
            .values(
                id=follow_up_id,
                organization_id=lead.organization_id,
                lead_id=lead.id,
                status="draft",
                **item,
            )
            .on_conflict_do_nothing(constraint="uq_follow_ups_lead_channel")
            .returning(FollowUp.id)
        )
        if created.first() is not None:
            await add_activity(db, lead, "follow_up_planned", details={"channel": item["channel"]})
            follow_up = await db.get(FollowUp, follow_up_id)
        else:
            follow_up = await db.scalar(
                select(FollowUp).where(FollowUp.lead_id == lead.id, FollowUp.channel == item["channel"])
            )
            if follow_up is None or follow_up.status not in ("draft", "scheduled"):
                continue
            # Not sent yet, so a corrected address or name should reach it. Someone approving by hand may have
            # reworded the draft, so only the address changes then.
            follow_up.recipient = item["recipient"]
            if settings.auto_send:
                follow_up.subject = item["subject"]
                follow_up.body = item["body"]
        # A lead flagged for checking may have been misread, so it waits until someone has checked it
        if settings.auto_send and follow_up.status == "draft" and not lead.needs_review:
            await queue_send(db, follow_up, settings.delay_minutes)


async def _deliver(db: AsyncSession, follow_up: FollowUp, settings: FollowUpSettings | None, lead: Lead) -> str:
    if follow_up.channel == "email":
        base = get_settings().public_base_url.rstrip("/")
        return await mailer.send_email(
            to=follow_up.recipient,
            subject=follow_up.subject or "",
            body=follow_up.body or "",
            sender_name=settings.sender_name if settings else None,
            reply_to=settings.reply_to if settings else None,
            unsubscribe_url=f"{base}/u/{unsubscribe_token(follow_up.organization_id, follow_up.recipient)}",
            idempotency_key=str(follow_up.id),
        )
    contact = await db.get(Contact, lead.contact_id)
    values = await _template_values(db, lead, contact)
    parameters = [values["first_name"], values["rep_name"]]
    # From the customer's own number when they've connected one, so the reply reaches them
    return await client.send_template(
        follow_up.recipient,
        settings.whatsapp_template,
        settings.whatsapp_language,
        parameters,
        sender=await sender_for(db, follow_up.organization_id),
    )


@job_handler(SEND_FOLLOW_UP)
async def send_follow_up(db: AsyncSession, job: ClaimedJob) -> None:
    follow_up = await db.scalar(
        select(FollowUp).where(FollowUp.id == uuid.UUID(job.payload["follow_up_id"])).with_for_update()
    )
    # Cancelled or sent since this was queued
    if follow_up is None or follow_up.status != "scheduled":
        return
    lead = await db.get(Lead, follow_up.lead_id)
    settings = await db.get(FollowUpSettings, follow_up.organization_id)

    blocked = None
    if await is_opted_out(db, follow_up.organization_id, follow_up.channel, follow_up.recipient):
        blocked = "This person opted out"
    elif follow_up.channel == "email":
        if settings is None or not settings.email_enabled:
            blocked = "Email follow-ups are switched off"
    elif follow_up.channel == "whatsapp":
        contact = await db.get(Contact, lead.contact_id)
        if contact.whatsapp_opt_in_at is None:
            blocked = "This person hasn't agreed to WhatsApp messages"
        elif settings is None or not settings.whatsapp_enabled or not settings.whatsapp_template:
            blocked = "WhatsApp follow-ups are switched off"
    if blocked:
        follow_up.status = "blocked"
        follow_up.error = blocked
        return
    # Flagged while this waited, so hold it. Clearing the flag queues it again.
    if lead.needs_review and settings is not None and settings.auto_send:
        follow_up.status = "draft"
        follow_up.send_after = None
        return

    try:
        follow_up.provider_message_id = await _deliver(db, follow_up, settings, lead)
    except (mailer.TemporaryEmailError, client.TemporarySendError) as exc:
        if job.attempts < job.max_attempts:
            raise
        follow_up.status = "failed"
        follow_up.error = str(exc)
        return
    except (mailer.EmailRejected, client.SendRejected) as exc:
        follow_up.status = "failed"
        follow_up.error = str(exc)
        log.warning("Follow-up %s was rejected: %s", follow_up.id, exc)
        return
    follow_up.status = "sent"
    follow_up.sent_at = datetime.now(UTC)
    await add_activity(db, lead, "follow_up_sent", details={"channel": follow_up.channel})
