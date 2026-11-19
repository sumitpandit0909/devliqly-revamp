"""A customer connecting its own WhatsApp number through Embedded Signup, so follow-ups come from that number."""

import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.deps import Db, OrgManager
from app.models import WhatsAppLine
from app.schemas import WhatsAppConnect, WhatsAppNumberOut, WhatsAppSetupOut, WhatsAppTemplateOut
from app.secrets_box import seal, unseal
from app.whatsapp import onboarding

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/org/whatsapp", tags=["whatsapp number"])


async def _line(db: Db, org: OrgManager) -> WhatsAppLine | None:
    return await db.scalar(select(WhatsAppLine).where(WhatsAppLine.organization_id == org.org_id))


def _number(line: WhatsAppLine | None) -> WhatsAppNumberOut | None:
    return WhatsAppNumberOut.model_validate(line) if line else None


async def _start_syncs(line: WhatsAppLine, token: str) -> None:
    """Meta allows each sync once, within 24 hours, so a failure is shown with a way to try again."""
    try:
        await onboarding.start_sync(line.phone_number_id, token, "smb_app_state_sync")
        await onboarding.start_sync(line.phone_number_id, token, "history")
    except onboarding.SignupFailed as exc:
        log.warning("Couldn't start the WhatsApp Business app sync: %s", exc)
        line.history_status = "failed"
        return
    line.history_status = "waiting"


@router.get("")
async def setup(db: Db, org: OrgManager) -> WhatsAppSetupOut:
    settings = get_settings()
    can_connect = bool(settings.meta_app_id and settings.meta_signup_config_id and settings.whatsapp_app_secret)
    return WhatsAppSetupOut(
        can_connect=can_connect,
        app_id=settings.meta_app_id or None,
        config_id=settings.meta_signup_config_id or None,
        graph_api_version=settings.graph_api_version,
        number=_number(await _line(db, org)),
    )


@router.post("/connect")
async def connect(body: WhatsAppConnect, db: Db, org: OrgManager) -> WhatsAppNumberOut:
    existing = await _line(db, org)
    if existing is not None and existing.status == "connected":
        raise HTTPException(status.HTTP_409_CONFLICT, "A WhatsApp number is already connected. Disconnect it first.")
    try:
        token = await onboarding.exchange_code(body.code)
        phone = await onboarding.find_phone(body.waba_id, body.phone_number_id, token)
    except onboarding.SignupFailed as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    line = existing or WhatsAppLine(organization_id=org.org_id)
    line.phone_number_id = phone.phone_number_id
    line.waba_id = body.waba_id
    line.display_phone = phone.display_phone
    line.verified_name = phone.verified_name
    line.access_token_sealed = seal(token)
    line.on_business_app = phone.on_business_app
    line.status = "connected"
    line.disconnect_reason = None
    line.history_progress = None
    line.history_status = "not_needed"
    if existing is None:
        db.add(line)
    # Claimed before changing anything at Meta. Another company's row is hidden from this one, so the unique key is
    # what notices the number is taken, and registering it again would change that company's PIN.
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This number is already connected to another company") from None

    try:
        await onboarding.subscribe_to_account(body.waba_id, token)
        if not phone.on_business_app:
            await onboarding.register_number(phone.phone_number_id, token)
    except onboarding.SignupFailed as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if phone.on_business_app:
        await _start_syncs(line, token)
    await db.flush()
    await db.refresh(line)
    out = WhatsAppNumberOut.model_validate(line)
    await db.commit()
    return out


@router.post("/retry-sync")
async def retry_sync(db: Db, org: OrgManager) -> WhatsAppNumberOut:
    line = await _line(db, org)
    if line is None or line.status != "connected" or line.history_status != "failed":
        raise HTTPException(status.HTTP_409_CONFLICT, "There's no failed sync to retry")
    await _start_syncs(line, unseal(line.access_token_sealed))
    await db.flush()
    await db.refresh(line)
    out = WhatsAppNumberOut.model_validate(line)
    await db.commit()
    return out


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(db: Db, org: OrgManager) -> None:
    """Forgets the number and its token. Follow-ups go from Devliqly's number again. On a WhatsApp Business app number,
    the customer also disconnects in the app: Settings → Account → Business Platform."""
    line = await _line(db, org)
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No WhatsApp number is connected")
    if line.status == "connected":
        try:
            await onboarding.unsubscribe_from_account(line.waba_id, unseal(line.access_token_sealed))
        except onboarding.SignupFailed as exc:
            # Forgetting the token matters more than tidying up at Meta
            log.warning("Couldn't unsubscribe from a disconnected number's account: %s", exc)
    await db.delete(line)
    await db.commit()


@router.get("/templates")
async def templates(db: Db, org: OrgManager) -> list[WhatsAppTemplateOut]:
    line = await _line(db, org)
    if line is None or line.status != "connected":
        return []
    try:
        found = await onboarding.approved_templates(line.waba_id, unseal(line.access_token_sealed))
    except onboarding.SignupFailed as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return [WhatsAppTemplateOut(**vars(template)) for template in found]
