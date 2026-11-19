"""Turning what the AI read into checked data, and saving it. Code, not the model, decides what's valid."""

import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import Text, cast, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import CardReading
from app.models import Company, Contact, ExpoEvent, Lead, LeadActivity, Organization, UsageMonth
from app.security import normalize_phone

MIN_CONFIDENCE = 0.6
INDIA_TIME = timezone(timedelta(hours=5, minutes=30))
_COMPANY_SUFFIXES = {"pvt", "private", "ltd", "limited", "llp", "inc", "corp", "corporation", "co", "company", "plc"}
_WEBSITE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+(/[^\s]*)?$")


def today_in_india() -> date:
    return datetime.now(INDIA_TIME).date()


def _clean_text(value: str | None, limit: int = 200) -> str | None:
    """Drops control characters, which have no place on a card, and squeezes whitespace."""
    if not value:
        return None
    printable = "".join(" " if unicodedata.category(c).startswith("C") else c for c in value)
    return " ".join(printable.split())[:limit] or None


def _clean_email(value: str) -> str | None:
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return None


def _clean_website(value: str) -> str | None:
    site = re.sub(r"^https?://", "", value.strip().lower()).rstrip("/")
    return site[:200] if _WEBSITE.match(site) else None


@dataclass
class CleanCard:
    full_name: str | None = None
    job_title: str | None = None
    company: str | None = None
    phones: list[str] = field(default_factory=list)
    email: str | None = None
    website: str | None = None
    address: str | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def has_identity(self) -> bool:
        return bool(self.full_name or self.company)

    @property
    def has_channel(self) -> bool:
        return bool(self.phones or self.email)

    @property
    def usable(self) -> bool:
        return self.has_identity and self.has_channel


def clean_reading(reading: CardReading) -> CleanCard:
    card = CleanCard(
        full_name=_clean_text(reading.full_name),
        job_title=_clean_text(reading.job_title),
        company=_clean_text(reading.company),
        address=_clean_text(reading.address, 500),
    )
    for raw in reading.phones:
        try:
            phone = normalize_phone(raw)
        except ValueError:
            card.problems.append(f"Phone number doesn't look valid: {_clean_text(raw, 40)}")
            continue
        if phone not in card.phones:
            card.phones.append(phone)
    for raw in reading.emails:
        email = _clean_email(raw)
        if email is None:
            card.problems.append(f"Email doesn't look valid: {_clean_text(raw, 80)}")
        elif card.email is None:
            card.email = email
    if reading.website:
        card.website = _clean_website(reading.website)
        if card.website is None:
            card.problems.append(f"Website doesn't look valid: {_clean_text(reading.website, 80)}")
    if reading.unsure_fields:
        card.problems.append("Hard to read: " + ", ".join(_clean_text(f, 40) or "" for f in reading.unsure_fields[:8]))
    if reading.confidence < MIN_CONFIDENCE:
        card.problems.append("The AI wasn't confident about this card")
    if not card.has_identity:
        card.problems.append("No name or company found")
    if not card.has_channel:
        card.problems.append("No phone number or email found")
    return card


def match_name(company: str) -> str:
    words = re.sub(r"[^\w\s]", " ", company.lower()).split()
    meaningful = [word for word in words if word not in _COMPANY_SUFFIXES]
    return " ".join(meaningful or words)[:200]


async def _company_for(db: AsyncSession, org_id: uuid.UUID, card: CleanCard) -> Company | None:
    if not card.company:
        return None
    key = match_name(card.company)
    await db.execute(
        insert(Company)
        .values(id=uuid.uuid4(), organization_id=org_id, name=card.company, match_name=key)
        .on_conflict_do_nothing(constraint="uq_companies_organization_match_name")
    )
    company = await db.scalar(select(Company).where(Company.organization_id == org_id, Company.match_name == key))
    company.website = company.website or card.website
    company.address = company.address or card.address
    return company


async def _existing_contact(db: AsyncSession, org_id: uuid.UUID, card: CleanCard) -> Contact | None:
    matches = []
    if card.phones:
        matches += [Contact.phone_e164.in_(card.phones), Contact.other_phones.has_any(cast(card.phones, ARRAY(Text)))]
    if card.email:
        matches.append(Contact.email == card.email)
    if not matches:
        return None
    return await db.scalar(
        select(Contact).where(Contact.organization_id == org_id, or_(*matches)).order_by(Contact.created_at).limit(1)
    )


def fill_blanks(contact: Contact, card: CleanCard) -> None:
    """Adds what's newly known. Never overwrites: a rep's correction shouldn't be undone by a re-scan."""
    contact.full_name = contact.full_name or card.full_name
    contact.job_title = contact.job_title or card.job_title
    contact.email = contact.email or card.email
    known = {contact.phone_e164, *contact.other_phones}
    for phone in card.phones:
        if phone in known:
            continue
        if contact.phone_e164 is None:
            contact.phone_e164 = phone
        else:
            contact.other_phones = [*contact.other_phones, phone]
        known.add(phone)


CONTACT_FIELDS = ("full_name", "job_title", "company", "phone", "email", "website", "address")


async def apply_changes(db: AsyncSession, contact: Contact, changes: dict[str, str]) -> tuple[list[str], list[str]]:
    """A person's correction, which does overwrite. Returns what changed and what couldn't be applied."""
    changed: list[str] = []
    problems: list[str] = []
    if name := _clean_text(changes.get("full_name")):
        contact.full_name = name
        changed.append("name")
    if title := _clean_text(changes.get("job_title")):
        contact.job_title = title
        changed.append("title")
    if changes.get("phone"):
        try:
            phone = normalize_phone(changes["phone"])
        except ValueError:
            problems.append(f"{_clean_text(changes['phone'], 40)} doesn't look like a valid phone number.")
        else:
            if await _taken(db, contact, Contact.phone_e164 == phone):
                problems.append(f"{phone} already belongs to another contact.")
            elif phone != contact.phone_e164:
                if contact.phone_e164:
                    contact.other_phones = [*contact.other_phones, contact.phone_e164]
                contact.other_phones = [p for p in contact.other_phones if p != phone]
                contact.phone_e164 = phone
                changed.append("phone")
    if changes.get("email"):
        email = _clean_email(changes["email"])
        if email is None:
            problems.append(f"{_clean_text(changes['email'], 80)} doesn't look like a valid email.")
        elif await _taken(db, contact, Contact.email == email):
            problems.append(f"{email} already belongs to another contact.")
        elif email != contact.email:
            contact.email = email
            changed.append("email")

    website = None
    if changes.get("website"):
        website = _clean_website(changes["website"])
        if website is None:
            problems.append(f"{_clean_text(changes['website'], 80)} doesn't look like a valid website.")
    address = _clean_text(changes.get("address"), 500)
    company = None
    if name := _clean_text(changes.get("company")):
        company = await _company_for(db, contact.organization_id, CleanCard(company=name))
        contact.company_id = company.id
        changed.append("company")
    elif (website or address) and contact.company_id:
        company = await db.get(Company, contact.company_id)
    elif website or address:
        problems.append("Add a company first, so the website or address has somewhere to go.")
    if company is not None:
        if website:
            company.website = website
            changed.append("website")
        if address:
            company.address = address
            changed.append("address")
    await db.flush()
    await db.refresh(contact, attribute_names=["company"])
    return changed, problems


async def _taken(db: AsyncSession, contact: Contact, condition) -> bool:
    other = await db.scalar(
        select(Contact.id).where(
            Contact.organization_id == contact.organization_id, Contact.id != contact.id, condition
        )
    )
    return other is not None


@dataclass(frozen=True)
class SavedCard:
    contact: Contact
    lead: Lead
    new_contact: bool
    new_lead: bool


async def save_contact_and_lead(
    db: AsyncSession,
    org_id: uuid.UUID,
    card: CleanCard,
    *,
    owner_user_id: uuid.UUID | None,
    event_id: uuid.UUID | None,
    needs_review: bool = False,
) -> SavedCard:
    """Unique keys settle races: if two captures of one person collide, one fails, retries and finds the other."""
    company = await _company_for(db, org_id, card)
    contact = await _existing_contact(db, org_id, card)
    new_contact = contact is None
    if contact is None:
        contact = Contact(
            organization_id=org_id,
            company_id=company.id if company else None,
            phone_e164=card.phones[0] if card.phones else None,
            other_phones=card.phones[1:],
            email=card.email,
            full_name=card.full_name,
            job_title=card.job_title,
        )
        db.add(contact)
        await db.flush()
    else:
        fill_blanks(contact, card)
        contact.company_id = contact.company_id or (company.id if company else None)

    created = await db.execute(
        insert(Lead)
        .values(
            id=uuid.uuid4(),
            organization_id=org_id,
            contact_id=contact.id,
            expo_event_id=event_id,
            owner_user_id=owner_user_id,
            needs_review=needs_review,
        )
        .on_conflict_do_nothing(constraint="uq_leads_organization_contact_event")
        .returning(Lead.id)
    )
    new_lead = created.first() is not None
    lead = await db.scalar(
        select(Lead).where(
            Lead.organization_id == org_id,
            Lead.contact_id == contact.id,
            Lead.expo_event_id.is_not_distinct_from(event_id),
        )
    )
    await db.flush()
    await db.refresh(contact, attribute_names=["company"])
    db.add(
        LeadActivity(
            organization_id=org_id,
            lead_id=lead.id,
            actor_user_id=owner_user_id,
            kind="captured" if new_lead else "rescanned",
        )
    )
    return SavedCard(contact, lead, new_contact, new_lead)


async def add_activity(
    db: AsyncSession,
    lead: Lead,
    kind: str,
    body: str | None = None,
    *,
    actor_user_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        LeadActivity(
            organization_id=lead.organization_id,
            lead_id=lead.id,
            actor_user_id=actor_user_id,
            kind=kind,
            body=body,
            details=details or {},
        )
    )


def current_month() -> date:
    return datetime.now(UTC).date().replace(day=1)


async def has_card_quota(db: AsyncSession, org_id: uuid.UUID) -> bool:
    """A quick check before spending money on AI. take_card_quota has the final say."""
    limit = await db.scalar(select(Organization.monthly_card_limit).where(Organization.id == org_id))
    used = await db.scalar(
        select(UsageMonth.cards_saved).where(UsageMonth.organization_id == org_id, UsageMonth.month == current_month())
    )
    return (used or 0) < (limit or 0)


async def take_card_quota(db: AsyncSession, org_id: uuid.UUID) -> bool:
    """Counts one card if the plan allows it. Atomic, so parallel cards can't pass the limit."""
    limit = await db.scalar(select(Organization.monthly_card_limit).where(Organization.id == org_id))
    if not limit:
        return False
    statement = insert(UsageMonth).values(id=uuid.uuid4(), organization_id=org_id, month=current_month(), cards_saved=1)
    statement = statement.on_conflict_do_update(
        constraint="uq_usage_months_organization_month",
        set_={"cards_saved": UsageMonth.cards_saved + 1},
        where=UsageMonth.cards_saved < limit,
    ).returning(UsageMonth.cards_saved)
    return (await db.execute(statement)).first() is not None


async def running_events(db: AsyncSession, org_id: uuid.UUID) -> list[ExpoEvent]:
    """Active events that aren't over, most recent first."""
    today = today_in_india()
    events = await db.scalars(
        select(ExpoEvent)
        .where(
            ExpoEvent.organization_id == org_id,
            ExpoEvent.is_active,
            or_(ExpoEvent.ends_on.is_(None), ExpoEvent.ends_on >= today),
        )
        .order_by(ExpoEvent.starts_on.desc().nulls_last(), ExpoEvent.created_at.desc())
    )
    return list(events)


def describe_contact(contact: Contact) -> str:
    who = contact.full_name or (contact.company.name if contact.company else None) or "this contact"
    if contact.full_name and contact.company:
        who += f", {contact.company.name}"
    return who
