"""Encrypts secrets we keep in the database, such as a customer's WhatsApp token, so a database leak alone can't use
them."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _box() -> Fernet:
    settings = get_settings()
    if settings.token_encryption_key:
        return Fernet(settings.token_encryption_key.encode())
    if settings.is_production:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY isn't set")
    # Development and tests only: a key derived from the JWT secret, so nothing extra has to be set up locally
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode()).digest()))


def seal(value: str) -> str:
    return _box().encrypt(value.encode()).decode()


def unseal(value: str) -> str:
    try:
        return _box().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("A stored secret couldn't be decrypted. Was TOKEN_ENCRYPTION_KEY changed?") from exc
