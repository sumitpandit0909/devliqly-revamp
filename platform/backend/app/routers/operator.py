"""Devliqly staff only: set up customer companies during the pilot."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select, update

from app.accounts import add_membership, add_user, issue_setup_url
from app.deps import Db, Operator
from app.models import Job, Organization, Role
from app.queue import wake_worker
from app.schemas import DeadJobOut, JobSummary, OrganizationCreate, OrganizationCreated, OrganizationOut

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


@router.get("/jobs/summary")
async def job_summary(db: Db, _: Operator) -> JobSummary:
    rows = await db.execute(select(Job.status, func.count()).group_by(Job.status))
    return JobSummary(**{status_name: count for status_name, count in rows})


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
