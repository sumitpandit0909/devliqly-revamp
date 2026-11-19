"""The CRM's contacts and leads. Managers see the whole team's; reps see only their own."""

import csv
import io
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import delete, func, or_, select

from app.cards import add_activity, apply_changes
from app.deps import Db, Org, OrgContext, OrgManager
from app.followups import plan_follow_ups
from app.maintenance import DELETE_FILES
from app.models import (
    BusinessCard,
    Company,
    Contact,
    ConversationMessage,
    ExpoEvent,
    FollowUp,
    Lead,
    LeadActivity,
    Membership,
    User,
)
from app.queue import enqueue, wake_worker
from app.schemas import (
    ActivityOut,
    CardOut,
    FollowUpOut,
    LeadDetail,
    LeadListOut,
    LeadNote,
    LeadRow,
    LeadUpdate,
)
from app.storage import get_storage

router = APIRouter(prefix="/api/org", tags=["leads"])

MAX_EXPORT_ROWS = 50_000
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _rows_query(org: OrgContext):
    query = (
        select(Lead, Company.name, Company.website, ExpoEvent.name, User.full_name)
        .join(Contact, Lead.contact_id == Contact.id)
        .outerjoin(Company, Contact.company_id == Company.id)
        .outerjoin(ExpoEvent, Lead.expo_event_id == ExpoEvent.id)
        .outerjoin(User, Lead.owner_user_id == User.id)
        .where(Lead.organization_id == org.org_id)
    )
    return query if org.can_manage else query.where(Lead.owner_user_id == org.user.id)


def _filtered(
    query,
    q: str | None,
    event_id: uuid.UUID | None,
    lead_status: str | None,
    interest: str | None,
    owner_id: uuid.UUID | None,
    needs_review: bool | None,
):
    if q and q.strip():
        term = q.strip()
        query = query.where(
            or_(
                Contact.full_name.icontains(term, autoescape=True),
                Company.name.icontains(term, autoescape=True),
                Contact.phone_e164.icontains(term, autoescape=True),
                Contact.email.icontains(term, autoescape=True),
            )
        )
    if event_id:
        query = query.where(Lead.expo_event_id == event_id)
    if lead_status:
        query = query.where(Lead.status == lead_status)
    if interest:
        query = query.where(Lead.interest == interest)
    if owner_id:
        query = query.where(Lead.owner_user_id == owner_id)
    if needs_review is not None:
        query = query.where(Lead.needs_review == needs_review)
    return query


def _to_row(lead: Lead, company: str | None, website: str | None, event: str | None, owner: str | None) -> LeadRow:
    contact = lead.contact
    return LeadRow(
        id=lead.id,
        contact_id=contact.id,
        full_name=contact.full_name,
        job_title=contact.job_title,
        company=company,
        website=website,
        phone=contact.phone_e164,
        other_phones=contact.other_phones,
        email=contact.email,
        whatsapp_opt_in=contact.whatsapp_opt_in_at is not None,
        event_id=lead.expo_event_id,
        event=event,
        owner_user_id=lead.owner_user_id,
        owner=owner,
        status=lead.status,
        interest=lead.interest,
        next_step=lead.next_step,
        follow_up_on=lead.follow_up_on,
        needs_review=lead.needs_review,
        created_at=lead.created_at,
    )


@router.get("/leads")
async def list_leads(
    db: Db,
    org: Org,
    q: str | None = Query(default=None, max_length=200),
    event_id: uuid.UUID | None = None,
    lead_status: str | None = Query(default=None, alias="status"),
    interest: str | None = None,
    owner_id: uuid.UUID | None = None,
    needs_review: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LeadListOut:
    query = _filtered(_rows_query(org), q, event_id, lead_status, interest, owner_id, needs_review)
    total = await db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = await db.execute(query.order_by(Lead.created_at.desc()).limit(limit).offset(offset))
    return LeadListOut(items=[_to_row(*row) for row in rows], total=total)


def _safe_cell(value: object) -> str:
    """Spreadsheets run cells starting with these as formulas, and card text is untrusted. Plain phone numbers pass."""
    text = "" if value is None else str(value)
    if text.startswith(_FORMULA_STARTS) and not (text.startswith("+") and text[1:].isdigit()):
        return "'" + text
    return text


@router.get("/leads/export.csv")
async def export_leads(
    db: Db,
    org: OrgManager,
    q: str | None = Query(default=None, max_length=200),
    event_id: uuid.UUID | None = None,
    lead_status: str | None = Query(default=None, alias="status"),
    interest: str | None = None,
    owner_id: uuid.UUID | None = None,
) -> Response:
    query = _filtered(_rows_query(org), q, event_id, lead_status, interest, owner_id, None)
    rows = await db.execute(query.order_by(Lead.created_at.desc()).limit(MAX_EXPORT_ROWS))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Name",
            "Title",
            "Company",
            "Phone",
            "Other phones",
            "Email",
            "Website",
            "Event",
            "Rep",
            "Status",
            "Interest",
            "Next step",
            "Follow up on",
            "Captured at",
        ]
    )
    for row in rows:
        item = _to_row(*row)
        writer.writerow(
            [
                _safe_cell(value)
                for value in (
                    item.full_name,
                    item.job_title,
                    item.company,
                    item.phone,
                    " ".join(item.other_phones),
                    item.email,
                    item.website,
                    item.event,
                    item.owner,
                    item.status,
                    item.interest,
                    item.next_step,
                    item.follow_up_on,
                    item.created_at.isoformat(),
                )
            ]
        )
    return Response(
        # The byte order mark tells Excel this is UTF-8, which matters for Indian-language names
        content="﻿" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


async def _visible_lead(db: Db, org: OrgContext, lead_id: uuid.UUID) -> Lead:
    query = select(Lead).where(Lead.id == lead_id, Lead.organization_id == org.org_id)
    if not org.can_manage:
        query = query.where(Lead.owner_user_id == org.user.id)
    lead = await db.scalar(query)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    return lead


async def _detail(db: Db, org: OrgContext, lead_id: uuid.UUID) -> LeadDetail:
    row = (await db.execute(_rows_query(org).where(Lead.id == lead_id))).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    activities = await db.execute(
        select(LeadActivity, User.full_name)
        .outerjoin(User, LeadActivity.actor_user_id == User.id)
        .where(LeadActivity.lead_id == lead_id)
        .order_by(LeadActivity.created_at.desc())
    )
    cards = await db.scalars(
        select(BusinessCard).where(BusinessCard.lead_id == lead_id).order_by(BusinessCard.created_at.desc())
    )
    follow_ups = await db.scalars(select(FollowUp).where(FollowUp.lead_id == lead_id).order_by(FollowUp.created_at))
    return LeadDetail(
        **_to_row(*row).model_dump(),
        activities=[
            ActivityOut(
                id=activity.id,
                kind=activity.kind,
                body=activity.body,
                details=activity.details,
                actor=actor,
                created_at=activity.created_at,
            )
            for activity, actor in activities
        ],
        cards=[CardOut.from_card(card) for card in cards],
        follow_ups=[FollowUpOut.model_validate(f) for f in follow_ups],
    )


@router.get("/leads/{lead_id}")
async def get_lead(lead_id: uuid.UUID, db: Db, org: Org) -> LeadDetail:
    return await _detail(db, org, lead_id)


@router.patch("/leads/{lead_id}")
async def update_lead(lead_id: uuid.UUID, body: LeadUpdate, db: Db, org: Org) -> LeadDetail:
    lead = await _visible_lead(db, org, lead_id)
    contact = await db.get(Contact, lead.contact_id)
    changes = body.model_dump(exclude_unset=True)
    actor = org.user.id

    if "status" in changes and changes["status"] != lead.status:
        lead.status = changes["status"]
        await add_activity(db, lead, "status", lead.status, actor_user_id=actor)
    if "interest" in changes and changes["interest"] != lead.interest:
        lead.interest = changes["interest"]
        await add_activity(db, lead, "interest", lead.interest, actor_user_id=actor)
    if "next_step" in changes:
        lead.next_step = changes["next_step"]
    if "follow_up_on" in changes and changes["follow_up_on"] != lead.follow_up_on:
        lead.follow_up_on = changes["follow_up_on"]
        follow_up_on = lead.follow_up_on.isoformat() if lead.follow_up_on else None
        await add_activity(db, lead, "follow_up_date", follow_up_on, actor_user_id=actor)
    if "needs_review" in changes:
        lead.needs_review = bool(changes["needs_review"])
    if "owner_user_id" in changes:
        if not org.can_manage:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and managers can reassign leads")
        member = await db.scalar(
            select(Membership.id).where(
                Membership.organization_id == org.org_id,
                Membership.user_id == changes["owner_user_id"],
                Membership.is_active,
            )
        )
        if member is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That person isn't on your team")
        lead.owner_user_id = changes["owner_user_id"]

    fields = {
        k: changes[k]
        for k in ("full_name", "job_title", "company", "phone", "email", "website", "address")
        if changes.get(k)
    }
    if fields:
        changed, problems = await apply_changes(db, contact, fields)
        if problems:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, " ".join(problems))
        if changed:
            await add_activity(db, lead, "correction", ", ".join(changed), actor_user_id=actor)

    if "whatsapp_opt_in" in changes:
        agreed = bool(changes["whatsapp_opt_in"])
        if agreed != (contact.whatsapp_opt_in_at is not None):
            contact.whatsapp_opt_in_at = datetime.now(UTC) if agreed else None
            await add_activity(db, lead, "whatsapp_consent", "agreed" if agreed else "withdrawn", actor_user_id=actor)

    await db.flush()
    await plan_follow_ups(db, lead, contact)
    out = await _detail(db, org, lead.id)
    await db.commit()
    wake_worker()
    return out


@router.post("/leads/{lead_id}/notes", status_code=status.HTTP_201_CREATED)
async def add_note(lead_id: uuid.UUID, body: LeadNote, db: Db, org: Org) -> LeadDetail:
    lead = await _visible_lead(db, org, lead_id)
    await add_activity(db, lead, "note", body.body, actor_user_id=org.user.id)
    await db.flush()
    out = await _detail(db, org, lead.id)
    await db.commit()
    return out


async def _erase_chat_about(db: Db, org_id: uuid.UUID, contact: Contact, cards: list[BusinessCard]) -> None:
    """Removes chat naming this person or their cards, and the message each of those replies answered."""
    # A rep's note doesn't name the person, but its reply does, and points back to it. This may also catch someone
    # with the same name, which only trims the rep's chat log; the CRM records are untouched.
    identifiers = [value for value in (contact.full_name, contact.phone_e164, contact.email) if value]
    identifiers += contact.other_phones or []
    mentions = [ConversationMessage.body.icontains(value, autoescape=True) for value in identifiers if len(value) >= 3]
    mentions.append(ConversationMessage.details["card_id"].astext.in_([str(card.id) for card in cards]))
    mentions.append(ConversationMessage.provider_message_id.in_([card.provider_message_id for card in cards]))
    found = await db.execute(
        select(ConversationMessage.provider_message_id, ConversationMessage.quotes_provider_id).where(
            ConversationMessage.organization_id == org_id, or_(*mentions)
        )
    )
    exchanges = {message_id for row in found for message_id in row if message_id}
    matches = [*mentions, ConversationMessage.provider_message_id.in_(exchanges)]
    await db.execute(delete(ConversationMessage).where(ConversationMessage.organization_id == org_id, or_(*matches)))


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def erase_contact(contact_id: uuid.UUID, db: Db, org: OrgManager) -> None:
    """Removes a person entirely on request: details, leads, timeline, card photos and the chat about them."""
    contact = await db.scalar(select(Contact).where(Contact.id == contact_id, Contact.organization_id == org.org_id))
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    cards = (
        await db.scalars(
            select(BusinessCard).where(
                BusinessCard.contact_id == contact.id, BusinessCard.organization_id == org.org_id
            )
        )
    ).all()
    keys = [key for card in cards for key in (card.front_key, card.back_key) if key]
    await _erase_chat_about(db, org.org_id, contact, cards)
    if cards:
        await db.execute(delete(BusinessCard).where(BusinessCard.id.in_([card.id for card in cards])))
    await db.delete(contact)
    if keys:
        await enqueue(db, DELETE_FILES, {"keys": keys})
    await db.commit()
    wake_worker()


@router.get("/cards/{card_id}/image")
async def card_image(card_id: uuid.UUID, db: Db, org: Org, side: Literal["front", "back"] = "front") -> Response:
    """Photos are served only through here, after checking access. The storage bucket stays private."""
    query = select(BusinessCard).where(BusinessCard.id == card_id, BusinessCard.organization_id == org.org_id)
    if not org.can_manage:
        query = query.where(BusinessCard.rep_user_id == org.user.id)
    card = await db.scalar(query)
    key = (card.front_key if side == "front" else card.back_key) if card else None
    mime = (card.front_mime if side == "front" else card.back_mime) if card else None
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    return Response(content=await get_storage().get(key), media_type=mime or "application/octet-stream")
