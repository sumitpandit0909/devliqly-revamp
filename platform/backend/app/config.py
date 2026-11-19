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

    # The WhatsApp Business number, from the Meta app
    whatsapp_line_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_app_secret: str = ""
    # Any random string; entered in Meta when connecting the webhook
    whatsapp_verify_token: str = ""
    graph_api_version: str = "v23.0"
    # Development only: pretend to send, without calling Meta
    whatsapp_dry_run: bool = False
    # Customers connecting their own number through Embedded Signup. The config ID comes from Facebook Login for
    # Business → Configurations.
    meta_app_id: str = ""
    meta_signup_config_id: str = ""
    # Encrypts customers' WhatsApp tokens in the database. Generate one with:
    # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: str = ""

    # gemini, anthropic, openrouter or, in development only, fake. Unset means photos wait for manual review.
    ai_provider: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_input_usd_per_mtok: float = 1.50
    gemini_output_usd_per_mtok: float = 7.50
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"
    anthropic_input_usd_per_mtok: float = 0.10
    anthropic_output_usd_per_mtok: float = 0.50
    # OpenRouter reads cards and messages with openrouter_model. That model can't hear, so voice notes go to
    # openrouter_voice_model, which must take audio. Prices are OpenRouter's listed rates for each model.
    openrouter_api_key: str = ""
    openrouter_model: str = "deepseek/deepseek-v4.1-flash-1017"
    openrouter_input_usd_per_mtok: float = 0.006
    openrouter_output_usd_per_mtok: float = 0.50
    openrouter_voice_model: str = "google/gemini-2.5-flash-lite"
    openrouter_voice_input_usd_per_mtok: float = 0.10
    openrouter_voice_output_usd_per_mtok: float = 0.40

    # Private Cloudflare R2 bucket for card photos. Without it, development stores them in storage_dir.
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    storage_dir: str = ".uploads"

    # Follow-up email. With SMTP_HOST set it goes through that mail server (for example Gmail), otherwise Resend.
    email_from: str = ""
    resend_api_key: str = ""
    smtp_host: str = ""
    # 587 uses STARTTLS, 465 uses TLS from the start
    smtp_port: int = 587
    smtp_username: str = ""
    # For Gmail, an app password, not the account password
    smtp_password: str = ""
    # Development only: pretend to send, without contacting any mail service
    email_dry_run: bool = False

    login_attempts_per_minute: int = 20
    # How long raw webhook payloads and finished jobs are kept
    retention_days: int = 30

    worker_enabled: bool = True
    worker_concurrency: int = 4
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
            if self.whatsapp_dry_run:
                raise ValueError("WHATSAPP_DRY_RUN can't be on in production")
            if self.email_dry_run:
                raise ValueError("EMAIL_DRY_RUN can't be on in production")
            if self.meta_signup_config_id and not self.token_encryption_key:
                raise ValueError("Set TOKEN_ENCRYPTION_KEY before customers can connect their WhatsApp numbers")
            if self.ai_provider == "fake":
                raise ValueError("AI_PROVIDER can't be fake in production")
            if not self.r2_bucket:
                raise ValueError("Set R2_BUCKET in production, so card photos stay in private storage")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
