"""Devliqly staff only: set up customer companies during the pilot."""

from fastapi import APIRouter, status
from sqlalchemy import select

from app.accounts import add_membership, add_user, issue_setup_url
from app.deps import Db, Operator
from app.models import Organization, Role
from app.schemas import OrganizationCreate, OrganizationCreated, OrganizationOut

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
