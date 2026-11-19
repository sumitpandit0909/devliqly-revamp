import uuid
from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

from app.security import normalize_phone

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
RoleName = Literal["owner", "manager", "rep"]


def _lower(value: str | None) -> str | None:
    return value.lower() if value else value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)

    _email = field_validator("email")(_lower)


class SetPasswordRequest(BaseModel):
    token: str = Field(max_length=256)
    password: str = Field(min_length=10, max_length=256)


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int


class PersonInput(BaseModel):
    full_name: Name
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)

    _email = field_validator("email")(_lower)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value) if value else None

    @model_validator(mode="after")
    def reachable(self) -> Self:
        if not self.email and not self.phone:
            raise ValueError("Provide an email or a phone number")
        return self


class MemberCreate(PersonInput):
    role: RoleName = "rep"


class MemberUpdate(BaseModel):
    role: RoleName | None = None
    is_active: bool | None = None


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    role: str
    is_active: bool


class MemberCreated(MemberOut):
    setup_url: str | None = None


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool


class OrganizationPlanOut(OrganizationOut):
    plan: str
    monthly_card_limit: int
    seat_limit: int


class MembershipSummary(BaseModel):
    organization: OrganizationOut
    role: str


class MeOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    is_operator: bool
    memberships: list[MembershipSummary]


class OrganizationCreate(BaseModel):
    name: Name
    owner: PersonInput

    @field_validator("owner")
    @classmethod
    def owner_can_log_in(cls, value: PersonInput) -> PersonInput:
        if not value.email:
            raise ValueError("The owner needs an email to log in")
        return value


class OrganizationCreated(OrganizationOut):
    owner_setup_url: str


class ExpoEventCreate(BaseModel):
    name: Name
    venue: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    starts_on: date | None = None
    ends_on: date | None = None

    @model_validator(mode="after")
    def dates_in_order(self) -> Self:
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("The end date can't be before the start date")
        return self


class ExpoEventUpdate(BaseModel):
    name: Name | None = None
    venue: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    is_active: bool | None = None


class ExpoEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    venue: str | None
    starts_on: date | None
    ends_on: date | None
    is_active: bool


class ConversationOut(BaseModel):
    id: uuid.UUID
    rep_user_id: uuid.UUID
    rep_name: str
    rep_phone: str | None
    last_inbound_at: datetime | None


class ConversationMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    direction: str
    kind: str
    body: str | None
    status: str
    error: str | None
    created_at: datetime


class JobSummary(BaseModel):
    pending: int = 0
    running: int = 0
    done: int = 0
    dead: int = 0


class DeadJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    kind: str
    attempts: int
    last_error: str | None
    created_at: datetime
    finished_at: datetime | None


class OrganizationUpdate(BaseModel):
    plan: Name | None = None
    monthly_card_limit: int | None = Field(default=None, ge=1, le=10_000_000)
    seat_limit: int | None = Field(default=None, ge=1, le=100_000)
    is_active: bool | None = None


class OrganizationUsage(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    plan: str
    monthly_card_limit: int
    seat_limit: int
    cards_this_month: int
    ai_calls_this_month: int
    ai_cost_usd_this_month: float


class OperatorOverview(BaseModel):
    organizations: list[OrganizationUsage]
    jobs: JobSummary
    ai_calls_failed_this_month: int


LeadStatus = Literal["new", "contacted", "qualified", "won", "lost"]
Interest = Literal["hot", "warm", "cold"]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class LeadRow(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    full_name: str | None
    job_title: str | None
    company: str | None
    website: str | None
    phone: str | None
    other_phones: list[str]
    email: str | None
    whatsapp_opt_in: bool
    event_id: uuid.UUID | None
    event: str | None
    owner_user_id: uuid.UUID | None
    owner: str | None
    status: str
    interest: str | None
    next_step: str | None
    follow_up_on: date | None
    needs_review: bool
    created_at: datetime


class LeadListOut(BaseModel):
    items: list[LeadRow]
    total: int


class ActivityOut(BaseModel):
    id: uuid.UUID
    kind: str
    body: str | None
    details: dict
    actor: str | None
    created_at: datetime


class CardOut(BaseModel):
    id: uuid.UUID
    status: str
    lead_id: uuid.UUID | None
    rep_user_id: uuid.UUID | None
    has_front: bool
    has_back: bool
    caption: str | None
    reading: dict
    problems: list[str]
    created_at: datetime

    @classmethod
    def from_card(cls, card) -> "CardOut":
        return cls(
            id=card.id,
            status=card.status,
            lead_id=card.lead_id,
            rep_user_id=card.rep_user_id,
            has_front=bool(card.front_key),
            has_back=bool(card.back_key),
            caption=card.caption,
            reading=card.reading,
            problems=card.problems,
            created_at=card.created_at,
        )


class FollowUpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    channel: str
    status: str
    recipient: str
    subject: str | None
    body: str | None
    send_after: datetime | None
    sent_at: datetime | None
    error: str | None
    created_at: datetime


class FollowUpRow(FollowUpOut):
    lead_id: uuid.UUID
    contact_name: str | None


class LeadDetail(LeadRow):
    activities: list[ActivityOut]
    cards: list[CardOut]
    follow_ups: list[FollowUpOut]


class LeadUpdate(BaseModel):
    status: LeadStatus | None = None
    interest: Interest | None = None
    next_step: ShortText | None = None
    follow_up_on: date | None = None
    needs_review: bool | None = None
    owner_user_id: uuid.UUID | None = None
    whatsapp_opt_in: bool | None = None
    full_name: ShortText | None = None
    job_title: ShortText | None = None
    company: ShortText | None = None
    phone: ShortText | None = None
    email: ShortText | None = None
    website: ShortText | None = None
    address: ShortText | None = None


class LeadNote(BaseModel):
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class ReviewApproval(BaseModel):
    full_name: ShortText = ""
    job_title: ShortText = ""
    company: ShortText = ""
    phone: ShortText = ""
    email: ShortText = ""
    website: ShortText = ""
    address: ShortText = ""


class CountRow(BaseModel):
    label: str
    count: int


class DashboardOut(BaseModel):
    total: int
    today: int
    hot: int
    follow_ups_due: int
    waiting_review: int
    cards_this_month: int
    monthly_card_limit: int
    by_status: list[CountRow]
    by_rep: list[CountRow]
    by_event: list[CountRow]
    follow_ups: list[CountRow]


class FollowUpSettingsIn(BaseModel):
    email_enabled: bool = False
    auto_send: bool = True
    delay_minutes: int = Field(default=60, ge=0, le=60 * 24 * 14)
    sender_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    reply_to: EmailStr | None = None
    email_subject: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    email_body: Annotated[str, StringConstraints(max_length=10_000)] = ""
    whatsapp_enabled: bool = False
    whatsapp_template: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    whatsapp_language: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=10)] = "en"
    whatsapp_consent_at_capture: bool = False


class FollowUpSettingsOut(FollowUpSettingsIn):
    model_config = ConfigDict(from_attributes=True)


class FollowUpEdit(BaseModel):
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    body: Annotated[str, StringConstraints(min_length=1, max_length=10_000)]

    @field_validator("subject")
    @classmethod
    def single_line(cls, value: str) -> str:
        return " ".join(value.split())


class OptOutIn(BaseModel):
    channel: Literal["email", "whatsapp"]
    address: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=320)]

    @model_validator(mode="after")
    def normal_form(self) -> Self:
        self.address = normalize_phone(self.address) if self.channel == "whatsapp" else self.address.lower()
        return self


class OptOutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    channel: str
    address: str
    source: str
    created_at: datetime


class WhatsAppConnect(BaseModel):
    """What Embedded Signup hands back to the browser."""

    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)]
    waba_id: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{5,30}$")]
    phone_number_id: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{5,30}$")] | None = None


class WhatsAppNumberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_phone: str | None
    verified_name: str | None
    on_business_app: bool
    status: str
    disconnect_reason: str | None
    history_status: str
    history_progress: int | None
    connected_at: datetime


class WhatsAppTemplateOut(BaseModel):
    name: str
    language: str
    category: str
    variables: int


class WhatsAppSetupOut(BaseModel):
    # False until Embedded Signup is configured, so the screen can say so instead of showing a broken button
    can_connect: bool
    app_id: str | None
    config_id: str | None
    graph_api_version: str
    number: WhatsAppNumberOut | None
