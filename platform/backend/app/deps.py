import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, set_scope
from app.models import Membership, Role, User
from app.security import InvalidToken, read_access_token

_bearer = HTTPBearer(auto_error=False)

Db = Annotated[AsyncSession, Depends(get_db)]


async def current_user(db: Db, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    try:
        user_id = read_access_token(credentials.credentials)
    except InvalidToken:
        raise unauthorized from None
    await set_scope(db, user_id=user_id)
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def operator_user(db: Db, user: CurrentUser) -> User:
    if not user.is_operator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Operator access required")
    await set_scope(db, operator=True)
    return user


Operator = Annotated[User, Depends(operator_user)]


@dataclass(frozen=True)
class OrgContext:
    org_id: uuid.UUID
    user: User
    role: Role

    @property
    def can_manage(self) -> bool:
        return self.role in {Role.OWNER, Role.MANAGER}


async def org_context(
    db: Db,
    user: CurrentUser,
    x_organization_id: Annotated[uuid.UUID | None, Header()] = None,
) -> OrgContext:
    """Which customer this request acts for. Header optional when the user belongs to just one."""
    query = select(Membership).where(Membership.user_id == user.id, Membership.is_active)
    if x_organization_id is not None:
        query = query.where(Membership.organization_id == x_organization_id)
    memberships = [m for m in (await db.scalars(query)).unique() if m.organization.is_active]
    if not memberships:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this organization")
    if len(memberships) > 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose an organization with X-Organization-Id")
    membership = memberships[0]
    await set_scope(db, org_id=membership.organization_id)
    return OrgContext(membership.organization_id, user, Role(membership.role))


Org = Annotated[OrgContext, Depends(org_context)]


async def org_manager(org: Org) -> OrgContext:
    if not org.can_manage:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and managers can do this")
    return org


OrgManager = Annotated[OrgContext, Depends(org_manager)]
