"""Creating people and their first-login links, shared by the API and the CLI."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Membership, PasswordSetupToken, Role, User
from app.schemas import PersonInput
from app.security import new_opaque_token


async def add_user(db: AsyncSession, person: PersonInput, *, is_operator: bool = False) -> User:
    user = User(
        full_name=person.full_name,
        email=person.email,
        phone_e164=person.phone,
        is_operator=is_operator,
    )
    # A savepoint keeps the transaction, and its security scope, alive if the insert conflicts
    try:
        async with db.begin_nested():
            db.add(user)
            await db.flush()
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "This email or phone number is already in use") from None
    return user


async def add_membership(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, role: Role) -> Membership:
    membership = Membership(organization_id=org_id, user_id=user_id, role=role.value)
    db.add(membership)
    await db.flush()
    return membership


async def issue_setup_url(db: AsyncSession, user_id: uuid.UUID) -> str:
    settings = get_settings()
    token, token_hash = new_opaque_token()
    db.add(
        PasswordSetupToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=settings.setup_token_days),
        )
    )
    await db.flush()
    # In the fragment, so the token never reaches server or proxy logs
    return f"{settings.public_base_url.rstrip('/')}/#setup={token}"
