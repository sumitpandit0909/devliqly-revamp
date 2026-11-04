import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import phonenumbers
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi.concurrency import run_in_threadpool

from app.config import get_settings

_hasher = PasswordHasher()
# Verified when no such account exists, so response time doesn't reveal which emails are registered
_decoy_hash = _hasher.hash(secrets.token_urlsafe(16))

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "devliqly-platform"


class InvalidToken(Exception):
    pass


async def hash_password(password: str) -> str:
    return await run_in_threadpool(_hasher.hash, password)


async def verify_password(stored_hash: str | None, password: str) -> bool:
    def check() -> bool:
        try:
            _hasher.verify(stored_hash or _decoy_hash, password)
        except (VerificationError, InvalidHashError):
            return False
        return stored_hash is not None

    return await run_in_threadpool(check)


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    settings = get_settings()
    lifetime = timedelta(minutes=settings.access_token_minutes)
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": str(user_id), "iss": JWT_ISSUER, "iat": now, "exp": now + lifetime},
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )
    return token, int(lifetime.total_seconds())


def read_access_token(token: str) -> uuid.UUID:
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["sub", "exp", "iss"]},
        )
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidToken from exc


def new_opaque_token() -> tuple[str, str]:
    """A random token and the hash to store. Only the hash reaches the database."""
    token = secrets.token_urlsafe(48)
    return token, hash_opaque_token(token)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_phone(raw: str) -> str:
    """E.164 form, e.g. 9876543210 -> +919876543210. Raises ValueError if it isn't a valid number."""
    try:
        parsed = phonenumbers.parse(raw, get_settings().default_phone_region)
    except phonenumbers.NumberParseException as exc:
        raise ValueError("Enter a valid phone number") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("Enter a valid phone number")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
