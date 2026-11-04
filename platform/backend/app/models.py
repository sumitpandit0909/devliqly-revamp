import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Role(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    REP = "rep"


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _updated_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Organization(Base):
    """A customer company. Everything a customer owns hangs off one of these."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class User(Base):
    """A person. Reps may only have a phone; anyone who logs in to the CRM also has an email."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email IS NOT NULL OR phone_e164 IS NOT NULL", name="reachable"),)
    # A new colleague isn't readable until their membership exists, so inserts can't use RETURNING
    __mapper_args__ = {"eager_defaults": False}

    id: Mapped[uuid.UUID] = _pk()
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    phone_e164: Mapped[str | None] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_operator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_memberships_organization_user"),
        CheckConstraint("role IN ('owner', 'manager', 'rep')", name="known_role"),
    )

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    user: Mapped[User] = relationship(lazy="joined")
    organization: Mapped[Organization] = relationship(lazy="joined")


class ExpoEvent(Base):
    """A trade show or expo. Captured cards get tagged with one."""

    __tablename__ = "expo_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_expo_events_organization_name"),
        CheckConstraint("ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on", name="dates_in_order"),
    )

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    venue: Mapped[str | None] = mapped_column(String(200))
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class LoginSession(Base):
    """One rotating refresh token. Rotations share a family so a replayed token can end the whole chain."""

    __tablename__ = "login_sessions"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class PasswordSetupToken(Base):
    """A single-use link for a new CRM user to choose a password."""

    __tablename__ = "password_setup_tokens"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class WebhookInbox(Base):
    """Every webhook item, stored once. The unique event_key is what makes Meta's retries harmless."""

    __tablename__ = "webhook_inbox"

    id: Mapped[uuid.UUID] = _pk()
    event_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = _created_at()


class Job(Base):
    """Durable background work. Saved in the same transaction as the data that caused it."""

    __tablename__ = "job_queue"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'done', 'dead')", name="known_status"),
        Index("ix_job_queue_due", "run_after", postgresql_where=text("status = 'pending'")),
        Index("ix_job_queue_lease", "locked_until", postgresql_where=text("status = 'running'")),
        Index("ix_job_queue_lock_key", "lock_key", "seq", postgresql_where=text("status IN ('pending', 'running')")),
    )

    seq: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Jobs sharing a lock_key run strictly one at a time, in order
    lock_key: Mapped[str | None] = mapped_column(String(100))
    # Enqueuing the same dedupe_key twice does nothing
    dedupe_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="6")
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RepConversation(Base):
    """A rep's chat with the Expo Agent. The state fields drive what their next message means (later phases)."""

    __tablename__ = "rep_conversations"
    __table_args__ = (UniqueConstraint("organization_id", "rep_user_id", name="uq_rep_conversations_organization_rep"),)

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    rep_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(40), nullable=False, server_default="idle")
    state_data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    state_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint("direction IN ('in', 'out')", name="known_direction"),
        CheckConstraint("status IN ('received', 'queued', 'sent', 'delivered', 'read', 'failed')", name="known_status"),
        Index("ix_conversation_messages_conversation", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rep_conversations.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(3), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    # Meta's ID for this message; unique, so an inbound message can't be saved twice
    provider_message_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    # The inbound message this one answers, shown as a quoted reply in WhatsApp
    quotes_provider_id: Mapped[str | None] = mapped_column(String(200))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()
