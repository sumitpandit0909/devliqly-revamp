import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from sqlalchemy import select, update

from app.config import get_settings
from app.db import clear_auth_lookup, set_scope
from app.deps import CurrentUser, Db
from app.models import LoginSession, Membership, PasswordSetupToken, User
from app.schemas import AccessToken, LoginRequest, MembershipSummary, MeOut, OrganizationOut, SetPasswordRequest
from app.security import (
    create_access_token,
    hash_opaque_token,
    hash_password,
    new_opaque_token,
    verify_password,
)

router = APIRouter(prefix="/api", tags=["auth"])

REFRESH_COOKIE = "platform_refresh"
REFRESH_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_days * 86400,
        path=REFRESH_PATH,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
    )


async def _start_session(db: Db, response: Response, user_id: uuid.UUID, family_id: uuid.UUID) -> AccessToken:
    token, token_hash = new_opaque_token()
    db.add(
        LoginSession(
            user_id=user_id,
            family_id=family_id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days),
        )
    )
    await db.flush()
    _set_refresh_cookie(response, token)
    access_token, expires_in = create_access_token(user_id)
    return AccessToken(access_token=access_token, expires_in=expires_in)


@router.post("/auth/login")
async def login(body: LoginRequest, response: Response, db: Db) -> AccessToken:
    settings = get_settings()
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    await set_scope(db, auth_lookup=True)
    user = await db.scalar(select(User).where(User.email == body.email).with_for_update())
    now = datetime.now(UTC)

    if user is not None and user.locked_until and user.locked_until > now:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Try again in a few minutes.")

    password_ok = await verify_password(user.password_hash if user else None, body.password)
    if user is None or not user.is_active or not password_ok:
        if user is not None and not password_ok:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.max_failed_logins:
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                user.failed_login_count = 0
            await db.commit()
        raise invalid

    user.failed_login_count = 0
    user.locked_until = None
    await clear_auth_lookup(db)
    await set_scope(db, user_id=user.id)
    result = await _start_session(db, response, user.id, uuid.uuid4())
    await db.commit()
    return result


@router.post("/auth/refresh")
async def refresh(
    response: Response,
    db: Db,
    platform_refresh: Annotated[str | None, Cookie()] = None,
) -> AccessToken:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Please log in again.")
    if not platform_refresh:
        raise unauthorized
    current = await db.scalar(
        select(LoginSession).where(LoginSession.token_hash == hash_opaque_token(platform_refresh)).with_for_update()
    )
    if current is None:
        raise unauthorized
    now = datetime.now(UTC)
    if current.rotated_at is not None:
        # An already-used token came back, so it may have been stolen: end every session in its chain
        await db.execute(
            update(LoginSession)
            .where(LoginSession.family_id == current.family_id, LoginSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.commit()
        raise unauthorized
    if current.revoked_at is not None or current.expires_at <= now:
        raise unauthorized

    await set_scope(db, user_id=current.user_id)
    user = await db.get(User, current.user_id)
    if user is None or not user.is_active:
        raise unauthorized
    current.rotated_at = now
    result = await _start_session(db, response, user.id, current.family_id)
    await db.commit()
    return result


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: Db,
    platform_refresh: Annotated[str | None, Cookie()] = None,
) -> None:
    if platform_refresh:
        current = await db.scalar(
            select(LoginSession).where(LoginSession.token_hash == hash_opaque_token(platform_refresh))
        )
        if current is not None:
            await db.execute(
                update(LoginSession)
                .where(LoginSession.family_id == current.family_id, LoginSession.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC))
            )
            await db.commit()
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)


@router.post("/auth/set-password", status_code=status.HTTP_204_NO_CONTENT)
async def set_password(body: SetPasswordRequest, db: Db) -> None:
    await set_scope(db, auth_lookup=True)
    setup = await db.scalar(
        select(PasswordSetupToken)
        .where(PasswordSetupToken.token_hash == hash_opaque_token(body.token))
        .with_for_update()
    )
    now = datetime.now(UTC)
    if setup is None or setup.used_at is not None or setup.expires_at <= now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This link has expired or was already used")
    user = await db.get(User, setup.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This link has expired or was already used")
    user.password_hash = await hash_password(body.password)
    user.failed_login_count = 0
    user.locked_until = None
    setup.used_at = now
    await db.execute(
        update(LoginSession)
        .where(LoginSession.user_id == user.id, LoginSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.commit()


@router.get("/me")
async def me(user: CurrentUser, db: Db) -> MeOut:
    memberships = (
        await db.scalars(select(Membership).where(Membership.user_id == user.id, Membership.is_active))
    ).unique()
    return MeOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone_e164,
        is_operator=user.is_operator,
        memberships=[
            MembershipSummary(organization=OrganizationOut.model_validate(m.organization), role=m.role)
            for m in memberships
        ],
    )
