"""Meta calls for connecting a customer's own WhatsApp number after they finish Embedded Signup."""

import logging
import secrets
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.whatsapp import client

log = logging.getLogger(__name__)


class SignupFailed(Exception):
    """Something the customer or we must fix. The message is safe to show them."""


@dataclass(frozen=True)
class PhoneDetails:
    phone_number_id: str
    display_phone: str | None
    verified_name: str | None
    on_business_app: bool


@dataclass(frozen=True)
class Template:
    name: str
    language: str
    category: str
    variables: int


def _url(path: str) -> str:
    return f"https://graph.facebook.com/{get_settings().graph_api_version}/{path.lstrip('/')}"


async def _call(method: str, path: str, token: str | None, **kwargs) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        async with httpx.AsyncClient(transport=client.transport, timeout=30) as http:
            response = await http.request(method, _url(path), headers=headers, **kwargs)
    except httpx.HTTPError as exc:
        raise SignupFailed("Couldn't reach Meta. Please try again.") from exc
    try:
        body = response.json()
    except ValueError:
        body = {}
    if not response.is_success:
        error = body.get("error") or {}
        log.warning("Meta refused %s %s: %s %s", method, path.split("?")[0], error.get("code"), error.get("message"))
        detail = error.get("error_user_msg") or error.get("message") or f"HTTP {response.status_code}"
        raise SignupFailed(f"Meta refused this step: {detail}"[:300])
    return body


async def exchange_code(code: str) -> str:
    """Embedded Signup returns a short-lived code; this turns it into the customer's business token."""
    settings = get_settings()
    if not settings.meta_app_id or not settings.whatsapp_app_secret:
        raise SignupFailed("Connecting a number isn't set up yet.")
    body = await _call(
        "GET",
        "oauth/access_token",
        None,
        params={"client_id": settings.meta_app_id, "client_secret": settings.whatsapp_app_secret, "code": code},
    )
    token = body.get("access_token")
    if not token:
        raise SignupFailed("Meta didn't return an access token. Please try connecting again.")
    return token


async def find_phone(waba_id: str, phone_number_id: str | None, token: str) -> PhoneDetails:
    """A WhatsApp Business app number arrives without its phone number ID, so it's looked up from the account."""
    if not phone_number_id:
        numbers = (await _call("GET", f"{waba_id}/phone_numbers", token, params={"fields": "id"})).get("data") or []
        if len(numbers) != 1:
            raise SignupFailed("That WhatsApp account has no single number to connect. Please choose one number.")
        phone_number_id = str(numbers[0]["id"])
    details = await _call(
        "GET",
        phone_number_id,
        token,
        params={"fields": "display_phone_number,verified_name,is_on_biz_app,platform_type"},
    )
    return PhoneDetails(
        phone_number_id=str(phone_number_id),
        display_phone=details.get("display_phone_number"),
        verified_name=details.get("verified_name"),
        on_business_app=bool(details.get("is_on_biz_app")),
    )


async def subscribe_to_account(waba_id: str, token: str) -> None:
    """So replies, delivery receipts and sync events for this number reach our webhook."""
    await _call("POST", f"{waba_id}/subscribed_apps", token)


async def unsubscribe_from_account(waba_id: str, token: str) -> None:
    await _call("DELETE", f"{waba_id}/subscribed_apps", token)


async def register_number(phone_number_id: str, token: str) -> None:
    """A brand-new number must be registered for the Cloud API. A WhatsApp Business app number already is."""
    # The two-step PIN protects the number from being registered elsewhere. The customer can reset it in WhatsApp
    # Manager, so it isn't stored.
    pin = f"{secrets.randbelow(1_000_000):06d}"
    await _call("POST", f"{phone_number_id}/register", token, json={"messaging_product": "whatsapp", "pin": pin})


async def start_sync(phone_number_id: str, token: str, sync_type: str) -> None:
    """Contacts, then chat history, for a WhatsApp Business app number. Each can be asked for once, within 24 hours
    of connecting."""
    await _call(
        "POST",
        f"{phone_number_id}/smb_app_data",
        token,
        json={"messaging_product": "whatsapp", "sync_type": sync_type},
    )


async def approved_templates(waba_id: str, token: str) -> list[Template]:
    body = await _call(
        "GET",
        f"{waba_id}/message_templates",
        token,
        params={"fields": "name,language,status,category,components", "limit": 200},
    )
    found = []
    for item in body.get("data") or []:
        if item.get("status") != "APPROVED":
            continue
        text = next((c.get("text") or "" for c in item.get("components") or [] if c.get("type") == "BODY"), "")
        variables = len({part.split("}}")[0] for part in text.split("{{")[1:]})
        found.append(Template(item["name"], item.get("language") or "en", item.get("category") or "", variables))
    return sorted(found, key=lambda template: (template.name, template.language))
