import uuid
from datetime import date
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
