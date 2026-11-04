import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import Db, Org, OrgManager
from app.models import ExpoEvent
from app.schemas import ExpoEventCreate, ExpoEventOut, ExpoEventUpdate

router = APIRouter(prefix="/api/org/events", tags=["events"])

DUPLICATE = "An event with this name already exists"


@router.get("")
async def list_events(db: Db, org: Org) -> list[ExpoEventOut]:
    events = await db.scalars(
        select(ExpoEvent)
        .where(ExpoEvent.organization_id == org.org_id)
        .order_by(ExpoEvent.starts_on.desc().nulls_last(), ExpoEvent.created_at.desc())
    )
    return [ExpoEventOut.model_validate(e) for e in events]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_event(body: ExpoEventCreate, db: Db, org: OrgManager) -> ExpoEventOut:
    event = ExpoEvent(organization_id=org.org_id, created_by_user_id=org.user.id, **body.model_dump())
    try:
        async with db.begin_nested():
            db.add(event)
            await db.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE) from None
    await db.commit()
    return ExpoEventOut.model_validate(event)


@router.get("/{event_id}")
async def get_event(event_id: uuid.UUID, db: Db, org: Org) -> ExpoEventOut:
    event = await db.scalar(select(ExpoEvent).where(ExpoEvent.id == event_id, ExpoEvent.organization_id == org.org_id))
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return ExpoEventOut.model_validate(event)


@router.patch("/{event_id}")
async def update_event(event_id: uuid.UUID, body: ExpoEventUpdate, db: Db, org: OrgManager) -> ExpoEventOut:
    event = await db.scalar(select(ExpoEvent).where(ExpoEvent.id == event_id, ExpoEvent.organization_id == org.org_id))
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    changes = body.model_dump(exclude_unset=True)
    starts_on = changes.get("starts_on", event.starts_on)
    ends_on = changes.get("ends_on", event.ends_on)
    if starts_on and ends_on and ends_on < starts_on:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The end date can't be before the start date")
    if changes.get("name", "") is None or changes.get("is_active", True) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Name and status can't be empty")
    try:
        async with db.begin_nested():
            for field, value in changes.items():
                setattr(event, field, value)
            await db.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE) from None
    await db.refresh(event)
    out = ExpoEventOut.model_validate(event)
    await db.commit()
    return out
