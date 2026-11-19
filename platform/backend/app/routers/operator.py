"""Devliqly staff only: set up customer companies, and watch usage, costs and failures."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select, update

from app.accounts import add_membership, add_user, issue_setup_url
from app.cards import current_month
from app.deps import Db, Operator
from app.models import AiCall, Job, Organization, Role, UsageMonth
from app.queue import wake_worker
from app.schemas import (
    DeadJobOut,
    JobSummary,
    OperatorOverview,
    OrganizationCreate,
    OrganizationCreated,
    OrganizationOut,
    OrganizationPlanOut,
    OrganizationUpdate,
    OrganizationUsage,
)

router = APIRouter(prefix="/api/operator", tags=["operator"])


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
async def create_organization(body: OrganizationCreate, db: Db, _: Operator) -> OrganizationCreated:
    organization = Organization(name=body.name)
    db.add(organization)
    await db.flush()
    owner = await add_user(db, body.owner)
    await add_membership(db, organization.id, owner.id, Role.OWNER)
    setup_url = await issue_setup_url(db, owner.id)
    await db.commit()
    return OrganizationCreated(
        id=organization.id,
        name=organization.name,
        is_active=organization.is_active,
        owner_setup_url=setup_url,
    )


@router.get("/organizations")
async def list_organizations(db: Db, _: Operator) -> list[OrganizationOut]:
    organizations = await db.scalars(select(Organization).order_by(Organization.created_at.desc()))
    return [OrganizationOut.model_validate(o) for o in organizations]


@router.patch("/organizations/{organization_id}")
async def update_organization(
    organization_id: uuid.UUID, body: OrganizationUpdate, db: Db, _: Operator
) -> OrganizationPlanOut:
    organization = await db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(organization, field, value)
    await db.flush()
    await db.refresh(organization)
    out = OrganizationPlanOut.model_validate(organization)
    await db.commit()
    return out


async def _job_counts(db: Db) -> JobSummary:
    rows = await db.execute(select(Job.status, func.count()).group_by(Job.status))
    return JobSummary(**{status_name: count for status_name, count in rows})


@router.get("/jobs/summary")
async def job_summary(db: Db, _: Operator) -> JobSummary:
    return await _job_counts(db)


@router.get("/overview")
async def overview(db: Db, _: Operator) -> OperatorOverview:
    """Usage and AI cost per customer this month. Costs are estimates from token counts and the configured prices."""
    month = current_month()
    usage = await db.execute(
        select(UsageMonth.organization_id, UsageMonth.cards_saved).where(UsageMonth.month == month)
    )
    cards = {org_id: saved for org_id, saved in usage}
    spend = {
        org_id: (calls, float(cost))
        for org_id, calls, cost in await db.execute(
            select(AiCall.organization_id, func.count(), func.coalesce(func.sum(AiCall.cost_usd), 0))
            .where(AiCall.created_at >= month)
            .group_by(AiCall.organization_id)
        )
    }
    failed = await db.scalar(
        select(func.count()).select_from(AiCall).where(AiCall.created_at >= month, AiCall.succeeded.is_(False))
    )
    organizations = await db.scalars(select(Organization).order_by(Organization.name))
    return OperatorOverview(
        organizations=[
            OrganizationUsage(
                id=organization.id,
                name=organization.name,
                is_active=organization.is_active,
                plan=organization.plan,
                monthly_card_limit=organization.monthly_card_limit,
                seat_limit=organization.seat_limit,
                cards_this_month=cards.get(organization.id, 0),
                ai_calls_this_month=spend.get(organization.id, (0, 0.0))[0],
                ai_cost_usd_this_month=spend.get(organization.id, (0, 0.0))[1],
            )
            for organization in organizations
        ],
        jobs=await _job_counts(db),
        ai_calls_failed_this_month=failed,
    )


@router.get("/jobs/dead")
async def dead_jobs(db: Db, _: Operator) -> list[DeadJobOut]:
    jobs = await db.scalars(select(Job).where(Job.status == "dead").order_by(Job.seq.desc()).limit(100))
    return [DeadJobOut.model_validate(job) for job in jobs]


@router.post("/jobs/{seq}/retry", status_code=status.HTTP_204_NO_CONTENT)
async def retry_dead_job(seq: int, db: Db, _: Operator) -> None:
    result = await db.execute(
        update(Job)
        .where(Job.seq == seq, Job.status == "dead")
        .values(status="pending", attempts=0, run_after=func.now(), finished_at=None)
    )
    if result.rowcount != 1:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No failed job with that number")
    await db.commit()
    wake_worker()
