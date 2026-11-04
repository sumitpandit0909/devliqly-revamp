import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.accounts import add_membership, add_user, issue_setup_url
from app.deps import Db, Org, OrgManager
from app.models import Membership, Role
from app.schemas import MemberCreate, MemberCreated, MemberOut, MemberUpdate

router = APIRouter(prefix="/api/org/members", tags=["team"])


def _to_out(membership: Membership) -> MemberOut:
    return MemberOut(
        id=membership.id,
        user_id=membership.user_id,
        full_name=membership.user.full_name,
        email=membership.user.email,
        phone=membership.user.phone_e164,
        role=membership.role,
        is_active=membership.is_active,
    )


def _may_manage(actor_role: Role, target_role: str) -> bool:
    return actor_role == Role.OWNER or target_role == Role.REP


@router.get("")
async def list_members(db: Db, org: Org) -> list[MemberOut]:
    memberships = await db.scalars(
        select(Membership).where(Membership.organization_id == org.org_id).order_by(Membership.created_at)
    )
    return [_to_out(m) for m in memberships.unique()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_member(body: MemberCreate, db: Db, org: OrgManager) -> MemberCreated:
    if not _may_manage(org.role, body.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an owner can add owners and managers")
    if body.role != Role.REP and not body.email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Owners and managers need an email to log in")
    if body.role == Role.REP and not body.phone:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Reps need a WhatsApp phone number")
    user = await add_user(db, body)
    membership = await add_membership(db, org.org_id, user.id, Role(body.role))
    setup_url = await issue_setup_url(db, user.id) if user.email else None
    await db.commit()
    return MemberCreated(
        id=membership.id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone_e164,
        role=membership.role,
        is_active=membership.is_active,
        setup_url=setup_url,
    )


@router.patch("/{member_id}")
async def update_member(member_id: uuid.UUID, body: MemberUpdate, db: Db, org: OrgManager) -> MemberOut:
    membership = await db.scalar(
        select(Membership)
        .where(Membership.id == member_id, Membership.organization_id == org.org_id)
        .with_for_update(of=Membership)
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    new_role = body.role or membership.role
    if not _may_manage(org.role, membership.role) or not _may_manage(org.role, new_role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an owner can change owners and managers")

    new_active = membership.is_active if body.is_active is None else body.is_active
    losing_owner = membership.role == Role.OWNER and membership.is_active and (new_role != Role.OWNER or not new_active)
    if losing_owner:
        other_owners = await db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.organization_id == org.org_id,
                Membership.role == Role.OWNER,
                Membership.is_active,
                Membership.id != membership.id,
            )
        )
        if not other_owners:
            raise HTTPException(status.HTTP_409_CONFLICT, "An organization needs at least one active owner")

    membership.role = new_role
    membership.is_active = new_active
    await db.flush()
    out = _to_out(membership)
    await db.commit()
    return out
