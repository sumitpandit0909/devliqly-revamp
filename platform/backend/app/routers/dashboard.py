import uuid

from fastapi import APIRouter
from sqlalchemy import func, select

from app.cards import current_month, today_in_india
from app.deps import Db, Org
from app.models import BusinessCard, ExpoEvent, FollowUp, Lead, Organization, UsageMonth, User
from app.schemas import CountRow, DashboardOut

router = APIRouter(prefix="/api/org/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard(db: Db, org: Org, event_id: uuid.UUID | None = None) -> DashboardOut:
    """Totals across the team for managers, and the rep's own for reps."""
    scope = [Lead.organization_id == org.org_id]
    if not org.can_manage:
        scope.append(Lead.owner_user_id == org.user.id)
    if event_id:
        scope.append(Lead.expo_event_id == event_id)

    async def lead_count(*conditions) -> int:
        return await db.scalar(select(func.count()).select_from(Lead).where(*scope, *conditions))

    today = today_in_india()
    by_status = await db.execute(select(Lead.status, func.count()).where(*scope).group_by(Lead.status))
    by_rep = await db.execute(
        select(func.coalesce(User.full_name, "Unassigned"), func.count())
        .select_from(Lead)
        .outerjoin(User, Lead.owner_user_id == User.id)
        .where(*scope)
        .group_by(User.full_name)
        .order_by(func.count().desc())
        .limit(50)
    )
    by_event = await db.execute(
        select(func.coalesce(ExpoEvent.name, "No event"), func.count())
        .select_from(Lead)
        .outerjoin(ExpoEvent, Lead.expo_event_id == ExpoEvent.id)
        .where(*scope)
        .group_by(ExpoEvent.name)
        .order_by(func.count().desc())
        .limit(50)
    )
    follow_ups = await db.execute(
        select(FollowUp.status, func.count())
        .join(Lead, FollowUp.lead_id == Lead.id)
        .where(*scope)
        .group_by(FollowUp.status)
    )
    review_scope = [BusinessCard.organization_id == org.org_id, BusinessCard.status == "review"]
    if not org.can_manage:
        review_scope.append(BusinessCard.rep_user_id == org.user.id)
    plan = await db.scalar(select(Organization.monthly_card_limit).where(Organization.id == org.org_id))
    used = await db.scalar(
        select(UsageMonth.cards_saved).where(
            UsageMonth.organization_id == org.org_id, UsageMonth.month == current_month()
        )
    )
    return DashboardOut(
        total=await lead_count(),
        today=await lead_count(func.date(func.timezone("Asia/Kolkata", Lead.created_at)) == today),
        hot=await lead_count(Lead.interest == "hot"),
        follow_ups_due=await lead_count(Lead.follow_up_on <= today, Lead.status.not_in(("won", "lost"))),
        waiting_review=await db.scalar(select(func.count()).select_from(BusinessCard).where(*review_scope))
        + await lead_count(Lead.needs_review),
        cards_this_month=used or 0,
        monthly_card_limit=plan or 0,
        by_status=[CountRow(label=label, count=count) for label, count in by_status],
        by_rep=[CountRow(label=label, count=count) for label, count in by_rep],
        by_event=[CountRow(label=label, count=count) for label, count in by_event],
        follow_ups=[CountRow(label=label, count=count) for label, count in follow_ups],
    )
