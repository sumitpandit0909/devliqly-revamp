import uuid
from datetime import date, datetime
from decimal import Decimal
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
    Numeric,
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
    plan: Mapped[str] = mapped_column(String(40), nullable=False, default="pilot", server_default="pilot")
    monthly_card_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1000, server_default="1000")
    seat_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=25, server_default="25")
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
    """A rep's chat with the Expo Agent. The state fields drive what their next message means."""

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
    # The event this rep is working at; new cards get tagged with it
    current_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("expo_events.id", ondelete="SET NULL"))
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
    # The real time of saving, because a message and its reply are often saved in one transaction, and now() would
    # give them the same time and no order
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = _updated_at()


class Company(Base):
    """A prospect's company, as opposed to an Organization, which is our customer."""

    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("organization_id", "match_name", name="uq_companies_organization_match_name"),)

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Lowercased without "Pvt Ltd" and the like, so spellings of one company land on one row
    match_name: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class Contact(Base):
    """A prospect. Reps are users, not contacts."""

    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint(
            "full_name IS NOT NULL OR company_id IS NOT NULL OR phone_e164 IS NOT NULL OR email IS NOT NULL",
            name="identifiable",
        ),
        # Parallel captures of one person can't create two contacts
        Index(
            "uq_contacts_organization_phone",
            "organization_id",
            "phone_e164",
            unique=True,
            postgresql_where=text("phone_e164 IS NOT NULL"),
        ),
        Index(
            "uq_contacts_organization_email",
            "organization_id",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index("ix_contacts_phone", "phone_e164", postgresql_where=text("phone_e164 IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    full_name: Mapped[str | None] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(200))
    phone_e164: Mapped[str | None] = mapped_column(String(20))
    other_phones: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    email: Mapped[str | None] = mapped_column(String(320))
    # Set only when the person agreed: ticked on the lead, or at capture by a customer whose reps always ask.
    # A scanned card alone is not agreement.
    whatsapp_opt_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    company: Mapped[Company | None] = relationship(lazy="joined")


class Lead(Base):
    """One contact at one event. Meeting someone again at another event is a new lead."""

    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "contact_id",
            "expo_event_id",
            name="uq_leads_organization_contact_event",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("status IN ('new', 'contacted', 'qualified', 'won', 'lost')", name="known_status"),
        CheckConstraint("interest IS NULL OR interest IN ('hot', 'warm', 'cold')", name="known_interest"),
        Index("ix_leads_organization_created", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expo_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("expo_events.id", ondelete="SET NULL"), index=True
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new", server_default="new")
    interest: Mapped[str | None] = mapped_column(String(10))
    next_step: Mapped[str | None] = mapped_column(Text)
    follow_up_on: Mapped[date | None] = mapped_column(Date)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    contact: Mapped[Contact] = relationship(lazy="joined")


class BusinessCard(Base):
    """One photographed card and how reading it went."""

    __tablename__ = "business_cards"
    __table_args__ = (
        CheckConstraint(
            "status IN ('received', 'read', 'saved', 'review', 'rejected', 'over_quota', 'failed')",
            name="known_status",
        ),
        Index("ix_business_cards_organization_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    rep_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    expo_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("expo_events.id", ondelete="SET NULL"))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id", ondelete="SET NULL"), index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), index=True)
    # Unique, so one WhatsApp photo can't become two cards
    provider_message_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received", server_default="received")
    front_key: Mapped[str | None] = mapped_column(String(300))
    back_key: Mapped[str | None] = mapped_column(String(300))
    front_mime: Mapped[str | None] = mapped_column(String(50))
    back_mime: Mapped[str | None] = mapped_column(String(50))
    caption: Mapped[str | None] = mapped_column(Text)
    # What the AI returned, and what code found wrong with it
    reading: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    problems: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class LeadActivity(Base):
    """The timeline on a lead."""

    __tablename__ = "lead_activities"
    __table_args__ = (Index("ix_lead_activities_lead", "lead_id", "created_at"),)

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = _created_at()


DEFAULT_EMAIL_SUBJECT = "Great meeting you, {first_name}"
DEFAULT_EMAIL_BODY = """Hi {first_name},

Thank you for your time today. It was good to meet you.

I'd be happy to share more about {organization} and answer any questions you have. Just reply to this email and \
I'll get back to you.

Best regards,
{rep_name}
{organization}"""


class FollowUpSettings(Base):
    """How one customer follows up. Email starts on with a standard message; WhatsApp starts off, because it needs an
    approved template and each person's agreement."""

    __tablename__ = "follow_up_settings"

    # Named like every customer table so the row-level security check finds it
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # When off, follow-ups wait as drafts for someone to approve
    auto_send: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default="60")
    sender_name: Mapped[str | None] = mapped_column(String(100))
    reply_to: Mapped[str | None] = mapped_column(String(320))
    email_subject: Mapped[str] = mapped_column(
        String(200), nullable=False, default=DEFAULT_EMAIL_SUBJECT, server_default=""
    )
    email_body: Mapped[str] = mapped_column(Text, nullable=False, default=DEFAULT_EMAIL_BODY, server_default="")
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # An approved Meta template; {{1}} is filled with the first name and {{2}} with the rep's name
    whatsapp_template: Mapped[str | None] = mapped_column(String(100))
    whatsapp_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en", server_default="en")
    # The customer confirms its reps ask every visitor for WhatsApp permission when taking their card, so each new
    # card counts as agreed. A rep can still untick one lead.
    whatsapp_consent_at_capture: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    updated_at: Mapped[datetime] = _updated_at()


class FollowUp(Base):
    """One message to a prospect, written before it's sent so failures stay visible and can be retried."""

    __tablename__ = "follow_ups"
    __table_args__ = (
        # One per lead and channel: only a channel newly learned about gets a new follow-up
        UniqueConstraint("lead_id", "channel", name="uq_follow_ups_lead_channel"),
        CheckConstraint("channel IN ('email', 'whatsapp')", name="known_channel"),
        CheckConstraint(
            "status IN ('draft', 'scheduled', 'sent', 'failed', 'cancelled', 'blocked')",
            name="known_status",
        ),
        Index("ix_follow_ups_organization_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    send_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(200), index=True)
    error: Mapped[str | None] = mapped_column(Text)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class OptOut(Base):
    """Someone who said stop. Checked again at the moment of sending."""

    __tablename__ = "opt_outs"
    __table_args__ = (
        UniqueConstraint("organization_id", "channel", "address", name="uq_opt_outs_organization_channel_address"),
        CheckConstraint("channel IN ('email', 'whatsapp')", name="known_channel"),
    )

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    address: Mapped[str] = mapped_column(String(320), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class WhatsAppLine(Base):
    """A customer's own WhatsApp number, connected through Embedded Signup. Follow-ups go out from it. On a number that
    stays on the WhatsApp Business app (Coexistence) the customer keeps chatting there, and Riya never answers."""

    __tablename__ = "whatsapp_lines"
    __table_args__ = (
        Index("ix_whatsapp_lines_waba_id", "waba_id"),
        CheckConstraint("status IN ('connected', 'disconnected')", name="known_status"),
        CheckConstraint(
            "history_status IN ('not_needed', 'waiting', 'syncing', 'done', 'not_shared', 'failed')",
            name="known_history_status",
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    # One number per customer for now
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    phone_number_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    waba_id: Mapped[str] = mapped_column(String(40), nullable=False)
    display_phone: Mapped[str | None] = mapped_column(String(40))
    verified_name: Mapped[str | None] = mapped_column(String(200))
    # Encrypted with app.secrets_box; never sent to the browser
    access_token_sealed: Mapped[str] = mapped_column(Text, nullable=False)
    on_business_app: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="connected")
    disconnect_reason: Mapped[str | None] = mapped_column(String(200))
    history_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_needed")
    history_progress: Mapped[int | None] = mapped_column(Integer)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = _updated_at()


class UsageMonth(Base):
    """Cards saved in a month, counted atomically so parallel cards can't pass the plan's limit."""

    __tablename__ = "usage_months"
    __table_args__ = (UniqueConstraint("organization_id", "month", name="uq_usage_months_organization_month"),)

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    month: Mapped[date] = mapped_column(Date, nullable=False)
    cards_saved: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class AiCall(Base):
    """One call to an AI provider, for the cost dashboard. Holds no message or card content."""

    __tablename__ = "ai_calls"
    __table_args__ = (Index("ix_ai_calls_organization_created", "organization_id", "created_at"),)

    id: Mapped[uuid.UUID] = _pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0, server_default="0")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = _created_at()
