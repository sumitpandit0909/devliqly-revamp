"""The limited assistant for free text. The AI picks one action from a short list; this code carries it out.

It can only read and annotate the rep's own leads. It has no way to send anything to a prospect or to change who a
contact is, whatever a message says.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import RepRequest
from app.cards import add_activity, describe_contact, today_in_india
from app.models import Company, Contact, Lead

HELP_TEXT = (
    "Send a photo of a business card and I'll save it.\n\n"
    "You can also ask:\n"
    "- Note for Asha: wants a demo\n"
    "- Remind me to call Asha on Friday\n"
    "- Asha is very interested\n"
    "- What's Asha's number?\n"
    "- How many cards today?\n\n"
    "Reply *event* to choose which event you're at."
)
MAX_MATCHES = 5


async def _find_leads(db: AsyncSession, org_id: uuid.UUID, rep_user_id: uuid.UUID, query: str) -> list[Lead]:
    filters = [Lead.organization_id == org_id, Lead.owner_user_id == rep_user_id]
    if query.strip():
        term = query.strip()
        filters.append(
            or_(
                Contact.full_name.icontains(term, autoescape=True),
                Company.name.icontains(term, autoescape=True),
                Contact.phone_e164.icontains(term, autoescape=True),
                Contact.email.icontains(term, autoescape=True),
            )
        )
    leads = await db.scalars(
        select(Lead)
        .join(Contact, Lead.contact_id == Contact.id)
        .outerjoin(Company, Contact.company_id == Company.id)
        .where(*filters)
        .order_by(Lead.created_at.desc())
        .limit(MAX_MATCHES)
    )
    return list(leads.unique())


def _details(contact: Contact) -> str:
    lines = [describe_contact(contact)]
    if contact.job_title:
        lines.append(contact.job_title)
    if contact.phone_e164:
        lines.append(f"\U0001f4de {contact.phone_e164}")
    if contact.email:
        lines.append(f"✉️ {contact.email}")
    return "\n".join(lines)


def valid_date(value: str) -> date | None:
    """Models sometimes produce nonsense years, and a reminder in the past is no use."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    today = today_in_india()
    return parsed if today <= parsed <= today + timedelta(days=730) else None


async def carry_out(db: AsyncSession, org_id: uuid.UUID, rep_user_id: uuid.UUID, request: RepRequest) -> str:
    if request.action == "help":
        return HELP_TEXT
    if request.action == "my_numbers":
        return await _numbers(db, org_id, rep_user_id)

    if not request.contact.strip():
        return "Which contact do you mean? Please include their name or company."
    leads = await _find_leads(db, org_id, rep_user_id, request.contact)
    if not leads:
        return f'I couldn\'t find "{request.contact.strip()[:80]}" among your contacts.'
    if request.action == "find_contact":
        return "\n\n".join(_details(lead.contact) for lead in leads)
    if len({lead.contact_id for lead in leads}) > 1:
        names = "\n".join(f"- {describe_contact(lead.contact)}" for lead in leads)
        return f"I found a few. Please be more specific:\n{names}"

    lead = leads[0]
    who = describe_contact(lead.contact)
    if request.action == "add_note":
        if not request.note.strip():
            return f"What should the note about {who} say?"
        await add_activity(db, lead, "note", request.note.strip(), actor_user_id=rep_user_id)
        return f"\U0001f4dd Note added to {who}."
    if request.action == "set_interest":
        if not request.interest:
            return f"How interested is {who}: hot, warm or cold?"
        lead.interest = request.interest
        await add_activity(db, lead, "interest", request.interest, actor_user_id=rep_user_id)
        return f"✅ {who} marked {request.interest}."
    if request.action == "set_follow_up":
        follow_up_on = valid_date(request.follow_up_date)
        if follow_up_on is None:
            return f"When should you follow up with {who}? Please give a date."
        lead.follow_up_on = follow_up_on
        lead.next_step = request.next_step.strip() or lead.next_step
        await add_activity(db, lead, "follow_up_date", follow_up_on.isoformat(), actor_user_id=rep_user_id)
        return f"✅ Follow up with {who} on {follow_up_on.isoformat()}."
    return HELP_TEXT


async def _numbers(db: AsyncSession, org_id: uuid.UUID, rep_user_id: uuid.UUID) -> str:
    base = (
        select(func.count()).select_from(Lead).where(Lead.organization_id == org_id, Lead.owner_user_id == rep_user_id)
    )
    total = await db.scalar(base)
    today = await db.scalar(base.where(func.date(func.timezone("Asia/Kolkata", Lead.created_at)) == today_in_india()))
    return f"You've saved {today} today and {total} in total."
