import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import Db, Org, OrgContext, OrgManager
from app.followups import queue_send, record_opt_out, settings_for
from app.models import Contact, FollowUp, FollowUpSettings, Lead, OptOut
from app.queue import wake_worker
from app.schemas import (
    FollowUpEdit,
    FollowUpRow,
    FollowUpSettingsIn,
    FollowUpSettingsOut,
    OptOutIn,
    OptOutOut,
)

router = APIRouter(prefix="/api/org", tags=["follow-ups"])


async def _settings(db: Db, org_id: uuid.UUID) -> FollowUpSettings:
    return await settings_for(db, org_id)


@router.get("/follow-up-settings")
async def get_settings_for_org(db: Db, org: OrgManager) -> FollowUpSettingsOut:
    return FollowUpSettingsOut.model_validate(await _settings(db, org.org_id))


@router.put("/follow-up-settings")
async def save_settings(body: FollowUpSettingsIn, db: Db, org: OrgManager) -> FollowUpSettingsOut:
    if body.whatsapp_enabled and not body.whatsapp_template:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "WhatsApp follow-ups need an approved template name")
    if body.email_enabled and not (body.email_subject and body.email_body):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Email follow-ups need a subject and a message")
    settings = await _settings(db, org.org_id)
    for field, value in body.model_dump().items():
        setattr(settings, field, value)
    await db.flush()
    await db.refresh(settings)
    out = FollowUpSettingsOut.model_validate(settings)
    await db.commit()
    return out


def _rows(org: OrgContext):
    query = (
        select(FollowUp, Contact.full_name)
        .join(Lead, FollowUp.lead_id == Lead.id)
        .join(Contact, Lead.contact_id == Contact.id)
        .where(FollowUp.organization_id == org.org_id)
    )
    return query if org.can_manage else query.where(Lead.owner_user_id == org.user.id)


def _to_row(follow_up: FollowUp, name: str | None) -> FollowUpRow:
    return FollowUpRow(
        id=follow_up.id,
        lead_id=follow_up.lead_id,
        contact_name=name,
        channel=follow_up.channel,
        status=follow_up.status,
        recipient=follow_up.recipient,
        subject=follow_up.subject,
        body=follow_up.body,
        send_after=follow_up.send_after,
        sent_at=follow_up.sent_at,
        error=follow_up.error,
        created_at=follow_up.created_at,
    )


@router.get("/follow-ups")
async def list_follow_ups(
    db: Db,
    org: Org,
    follow_up_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[FollowUpRow]:
    query = _rows(org)
    if follow_up_status:
        query = query.where(FollowUp.status == follow_up_status)
    rows = await db.execute(query.order_by(FollowUp.created_at.desc()).limit(limit))
    return [_to_row(*row) for row in rows]


async def _locked(db: Db, org: OrgContext, follow_up_id: uuid.UUID) -> tuple[FollowUp, str | None]:
    row = (await db.execute(_rows(org).where(FollowUp.id == follow_up_id).with_for_update(of=FollowUp))).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Follow-up not found")
    return row[0], row[1]


async def _finish(db: Db, follow_up: FollowUp, name: str | None) -> FollowUpRow:
    await db.flush()
    await db.refresh(follow_up)
    out = _to_row(follow_up, name)
    await db.commit()
    wake_worker()
    return out


@router.patch("/follow-ups/{follow_up_id}")
async def edit_follow_up(follow_up_id: uuid.UUID, body: FollowUpEdit, db: Db, org: Org) -> FollowUpRow:
    follow_up, name = await _locked(db, org, follow_up_id)
    if follow_up.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only drafts can be edited")
    if follow_up.channel != "email":
        raise HTTPException(status.HTTP_409_CONFLICT, "WhatsApp follow-ups use a fixed template")
    follow_up.subject = body.subject
    follow_up.body = body.body
    return await _finish(db, follow_up, name)


@router.post("/follow-ups/{follow_up_id}/approve")
async def approve_follow_up(follow_up_id: uuid.UUID, db: Db, org: Org) -> FollowUpRow:
    follow_up, name = await _locked(db, org, follow_up_id)
    if follow_up.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only drafts can be approved")
    follow_up.approved_by_user_id = org.user.id
    await queue_send(db, follow_up)
    return await _finish(db, follow_up, name)


@router.post("/follow-ups/{follow_up_id}/cancel")
async def cancel_follow_up(follow_up_id: uuid.UUID, db: Db, org: Org) -> FollowUpRow:
    follow_up, name = await _locked(db, org, follow_up_id)
    if follow_up.status not in {"draft", "scheduled", "failed"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "This follow-up can't be cancelled")
    follow_up.status = "cancelled"
    return await _finish(db, follow_up, name)


@router.post("/follow-ups/{follow_up_id}/retry")
async def retry_follow_up(follow_up_id: uuid.UUID, db: Db, org: Org) -> FollowUpRow:
    follow_up, name = await _locked(db, org, follow_up_id)
    if follow_up.status != "failed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only failed follow-ups can be retried")
    await queue_send(db, follow_up)
    return await _finish(db, follow_up, name)


@router.get("/opt-outs")
async def list_opt_outs(db: Db, org: OrgManager) -> list[OptOutOut]:
    rows = await db.scalars(
        select(OptOut).where(OptOut.organization_id == org.org_id).order_by(OptOut.created_at.desc()).limit(500)
    )
    return [OptOutOut.model_validate(row) for row in rows]


@router.post("/opt-outs", status_code=status.HTTP_204_NO_CONTENT)
async def add_opt_out(body: OptOutIn, db: Db, org: OrgManager) -> None:
    """For someone who asks by phone or in person."""
    await record_opt_out(db, org.org_id, body.channel, body.address, "added_by_staff")
    await db.commit()
