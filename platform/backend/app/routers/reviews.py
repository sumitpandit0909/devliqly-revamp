"""Cards a person has to look at: unreadable, or missing a name or a way to reach someone."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.ai import CardReading
from app.cards import add_activity, clean_reading, save_contact_and_lead, take_card_quota
from app.deps import Db, Org, OrgContext
from app.followups import consent_at_capture, plan_follow_ups
from app.models import BusinessCard
from app.queue import wake_worker
from app.schemas import CardOut, ReviewApproval

router = APIRouter(prefix="/api/org/reviews", tags=["reviews"])


def _visible(org: OrgContext):
    query = select(BusinessCard).where(BusinessCard.organization_id == org.org_id, BusinessCard.status == "review")
    return query if org.can_manage else query.where(BusinessCard.rep_user_id == org.user.id)


@router.get("")
async def list_reviews(db: Db, org: Org) -> list[CardOut]:
    cards = await db.scalars(_visible(org).order_by(BusinessCard.created_at).limit(200))
    return [CardOut.from_card(card) for card in cards]


async def _waiting_card(db: Db, org: OrgContext, card_id: uuid.UUID) -> BusinessCard:
    card = await db.scalar(_visible(org).where(BusinessCard.id == card_id).with_for_update())
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This card isn't waiting for review")
    return card


@router.post("/{card_id}/approve")
async def approve_card(card_id: uuid.UUID, body: ReviewApproval, db: Db, org: Org) -> CardOut:
    card = await _waiting_card(db, org, card_id)
    # Goes through the same checks as what the AI reads
    clean = clean_reading(
        CardReading(
            is_business_card=True,
            full_name=body.full_name,
            job_title=body.job_title,
            company=body.company,
            phones=[body.phone] if body.phone else [],
            emails=[body.email] if body.email else [],
            website=body.website,
            address=body.address,
            unsure_fields=[],
            confidence=1,
        )
    )
    if not clean.usable or clean.problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "; ".join(clean.problems))
    if not await take_card_quota(db, org.org_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "This month's card limit has been reached")
    saved = await save_contact_and_lead(
        db,
        org.org_id,
        clean,
        owner_user_id=card.rep_user_id or org.user.id,
        event_id=card.expo_event_id,
    )
    card.contact_id = saved.contact.id
    card.lead_id = saved.lead.id
    card.status = "saved"
    card.problems = []
    if card.caption:
        await add_activity(db, saved.lead, "note", card.caption, actor_user_id=card.rep_user_id)
    if saved.new_lead:
        await consent_at_capture(db, saved.lead, saved.contact)
    await plan_follow_ups(db, saved.lead, saved.contact)
    await db.flush()
    out = CardOut.from_card(card)
    await db.commit()
    wake_worker()
    return out


@router.post("/{card_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_card(card_id: uuid.UUID, db: Db, org: Org) -> None:
    card = await _waiting_card(db, org, card_id)
    card.status = "rejected"
    await db.commit()
