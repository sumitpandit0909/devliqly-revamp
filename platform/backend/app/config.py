from functools import lru_cache
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

INSECURE_DEV_SECRET = "dev-only-secret-change-me-dev-only-secret"  # noqa: S105


def asyncpg_url(url: str) -> tuple[str, dict]:
    """Turn a provider URL (Neon, Render) into an asyncpg URL plus connect args.

    asyncpg rejects libpq-only query params such as sslmode and channel_binding, so TLS is passed separately.
    """
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    connect_args: dict = {}
    if sslmode in {"require", "verify-ca", "verify-full"}:
        connect_args["ssl"] = "require" if sslmode == "require" else True
    return (
        urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), "")),
        connect_args,
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    public_base_url: str = "http://localhost:8000"

    # The app connects as platform_app, which row-level security applies to.
    database_url: str = "postgresql://platform_app@127.0.0.1:55432/platform_dev"
    # Migrations connect as the table owner.
    migration_database_url: str = "postgresql://postgres@127.0.0.1:55432/platform_dev"

    jwt_secret: str = Field(default=INSECURE_DEV_SECRET, min_length=32)
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    setup_token_days: int = 7
    max_failed_logins: int = 5
    lockout_minutes: int = 15

    default_phone_region: str = "IN"
    cors_origins: Annotated[list[str], NoDecode] = []

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def refuse_unsafe_production(self) -> "Settings":
        if self.is_production:
            if self.jwt_secret == INSECURE_DEV_SECRET:
                raise ValueError("Set JWT_SECRET to a long random value in production")
            if not self.public_base_url.startswith("https://"):
                raise ValueError("PUBLIC_BASE_URL must use https in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
