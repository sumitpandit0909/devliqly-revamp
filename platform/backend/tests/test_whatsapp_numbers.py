"""Customers connecting their own WhatsApp number through Embedded Signup, and what changes once they have."""

import json

import httpx
import pytest

from app.config import get_settings
from app.queue import run_due_jobs
from app.whatsapp import client as meta_client
from tests.conftest import bearer
from tests.test_card_capture import ScriptedAi, leads, photo_message, rep, scripted, send  # noqa: F401
from tests.test_whatsapp_inbox import count, delivery, make_jobs_due, post, text_message

CUSTOMER_LINE = "777000111"
CUSTOMER_WABA = "888000222"
CUSTOMER_TOKEN = "customer-business-token"  # noqa: S105
PROSPECT = "+919820012345"


class FakeGraph:
    """Meta's Graph API for both the signup steps and sending. Records each call."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict, str]] = []
        self.on_business_app = True
        self.fail_code_exchange = False
        self.templates = [
            {
                "name": "expo_follow_up",
                "language": "en",
                "status": "APPROVED",
                "category": "MARKETING",
                "components": [{"type": "BODY", "text": "Hi {{1}}, this is {{2}}."}],
            },
            {"name": "draft_one", "language": "en", "status": "PENDING", "category": "UTILITY", "components": []},
        ]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.split("/", 2)[-1]
        body = json.loads(request.content) if request.content else {}
        self.calls.append((request.method, path, body, request.headers.get("authorization", "")))
        if path == "oauth/access_token":
            if self.fail_code_exchange:
                return httpx.Response(400, json={"error": {"code": 100, "message": "This code has expired"}})
            return httpx.Response(200, json={"access_token": CUSTOMER_TOKEN})
        if path == f"{CUSTOMER_WABA}/phone_numbers":
            return httpx.Response(200, json={"data": [{"id": CUSTOMER_LINE}]})
        if path == CUSTOMER_LINE:
            return httpx.Response(
                200,
                json={
                    "display_phone_number": "+91 98111 22233",
                    "verified_name": "Acme Traders",
                    "is_on_biz_app": self.on_business_app,
                    "platform_type": "CLOUD_API",
                },
            )
        if path == f"{CUSTOMER_WABA}/message_templates":
            return httpx.Response(200, json={"data": self.templates})
        if path.endswith("/messages"):
            return httpx.Response(200, json={"messages": [{"id": f"wamid.out.{len(self.calls)}"}]})
        if "download" in path:
            return httpx.Response(200, content=b"photo-bytes")
        if request.method == "GET":
            return httpx.Response(200, json={"url": "https://media.test/download", "mime_type": "image/jpeg"})
        return httpx.Response(200, json={"success": True, "request_id": "r1"})

    def paths(self, method: str | None = None) -> list[str]:
        return [path for verb, path, _, _ in self.calls if method in (None, verb)]

    def templates_sent(self) -> list[tuple[str, dict, str]]:
        return [(path, body, auth) for verb, path, body, auth in self.calls if body.get("type") == "template"]


@pytest.fixture
def graph(monkeypatch) -> FakeGraph:
    fake = FakeGraph()
    monkeypatch.setattr(meta_client, "transport", httpx.MockTransport(fake))
    settings = get_settings()
    monkeypatch.setattr(settings, "meta_app_id", "1664043868687217")
    monkeypatch.setattr(settings, "meta_signup_config_id", "cfg-123")
    return fake


async def connect(client, token: str, **extra) -> httpx.Response:
    body = {"code": "signup-code-0123456789", "waba_id": CUSTOMER_WABA, **extra}
    return await client.post("/api/org/whatsapp/connect", json=body, headers=bearer(token))


def customer_line_delivery(*messages, statuses=()) -> dict:
    return delivery(*messages, statuses=statuses, line=CUSTOMER_LINE)


def account_update(event: str, reason: str | None = None) -> dict:
    value: dict = {"event": event, "waba_info": {"waba_id": CUSTOMER_WABA, "owner_business_id": "5"}}
    if reason:
        value["disconnection_info"] = {"reason": reason, "initiated_by": "USER"}
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "1", "changes": [{"field": "account_update", "value": value}]}],
    }


def history(progress: int | None = None, *, not_shared: bool = False) -> dict:
    chunk: dict = {"metadata": {"phase": 0, "chunk_order": 1, "progress": progress}, "threads": []}
    if not_shared:
        chunk = {"errors": [{"code": 2593109, "title": "History sync is turned off"}]}
    value = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": CUSTOMER_LINE}, "history": [chunk]}
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": CUSTOMER_WABA, "changes": [{"field": "history", "value": value}]}],
    }


async def number(client, token: str) -> dict | None:
    return (await client.get("/api/org/whatsapp", headers=bearer(token))).json()["number"]


# Connecting


async def test_connect_button_only_appears_once_signup_is_configured(client, two_orgs):
    setup = (await client.get("/api/org/whatsapp", headers=bearer(two_orgs["a"]["token"]))).json()
    assert setup["can_connect"] is False
    assert setup["number"] is None


async def test_business_app_number_connects_without_registering_and_starts_the_sync(client, two_orgs, graph):
    token = two_orgs["a"]["token"]
    response = await connect(client, token)
    assert response.status_code == 200, response.text
    out = response.json()
    assert (out["display_phone"], out["on_business_app"], out["history_status"]) == ("+91 98111 22233", True, "waiting")
    assert f"{CUSTOMER_WABA}/subscribed_apps" in graph.paths("POST")
    assert not [path for path in graph.paths() if path.endswith("/register")]
    syncs = [body["sync_type"] for verb, path, body, _ in graph.calls if path.endswith("/smb_app_data")]
    assert syncs == ["smb_app_state_sync", "history"]
    # The token is stored encrypted, never as written
    assert await count("whatsapp_lines", "access_token_sealed NOT LIKE :t", t=f"%{CUSTOMER_TOKEN}%") == 1
    assert "access_token" not in json.dumps((await client.get("/api/org/whatsapp", headers=bearer(token))).json())


async def test_new_number_is_registered_and_needs_no_sync(client, two_orgs, graph):
    graph.on_business_app = False
    response = await connect(client, two_orgs["a"]["token"], phone_number_id=CUSTOMER_LINE)
    assert response.json()["history_status"] == "not_needed"
    [register] = [body for verb, path, body, _ in graph.calls if path.endswith("/register")]
    assert len(register["pin"]) == 6
    assert not [path for path in graph.paths() if path.endswith("/smb_app_data")]


async def test_one_number_cant_belong_to_two_companies(client, two_orgs, graph):
    assert (await connect(client, two_orgs["a"]["token"])).status_code == 200
    response = await connect(client, two_orgs["b"]["token"])
    assert response.status_code == 409
    assert await count("whatsapp_lines") == 1


async def test_failed_signup_stores_nothing(client, two_orgs, graph):
    graph.fail_code_exchange = True
    response = await connect(client, two_orgs["a"]["token"])
    assert response.status_code == 422
    assert "expired" in response.json()["detail"]
    assert await count("whatsapp_lines") == 0


async def test_only_approved_templates_are_offered(client, two_orgs, graph):
    token = two_orgs["a"]["token"]
    await connect(client, token)
    templates = (await client.get("/api/org/whatsapp/templates", headers=bearer(token))).json()
    assert templates == [{"name": "expo_follow_up", "language": "en", "category": "MARKETING", "variables": 2}]


async def test_disconnecting_forgets_the_token(client, two_orgs, graph):
    token = two_orgs["a"]["token"]
    await connect(client, token)
    assert (await client.delete("/api/org/whatsapp", headers=bearer(token))).status_code == 204
    assert f"{CUSTOMER_WABA}/subscribed_apps" in graph.paths("DELETE")
    assert await count("whatsapp_lines") == 0


async def test_another_company_cant_see_the_number(client, two_orgs, graph):
    await connect(client, two_orgs["a"]["token"])
    assert await number(client, two_orgs["b"]["token"]) is None


# Meta's events about the number


async def test_history_sync_progress_shows_up(client, two_orgs, graph):
    token = two_orgs["a"]["token"]
    await connect(client, token)
    await post(client, history(40))
    assert (await number(client, token))["history_status"] == "syncing"
    assert (await number(client, token))["history_progress"] == 40
    await post(client, history(100))
    assert (await number(client, token))["history_status"] == "done"


async def test_declined_history_is_shown_as_such(client, two_orgs, graph):
    token = two_orgs["a"]["token"]
    await connect(client, token)
    await post(client, history(not_shared=True))
    assert (await number(client, token))["history_status"] == "not_shared"


async def test_disconnecting_in_the_business_app_is_noticed(client, two_orgs, graph):
    token = two_orgs["a"]["token"]
    await connect(client, token)
    await post(client, account_update("PARTNER_REMOVED", "PRIMARY_INACTIVITY"))
    found = await number(client, token)
    assert (found["status"], found["disconnect_reason"]) == ("disconnected", "primary inactivity")
    await post(client, account_update("ACCOUNT_RECONNECTED"))
    assert (await number(client, token))["status"] == "connected"


async def test_history_messages_are_never_treated_as_new_messages(client, two_orgs, graph, rep):
    body = history(10)
    body["entry"][0]["changes"][0]["value"]["messages"] = [text_message("old chat")]
    await post(client, body)
    await run_due_jobs()
    assert await count("webhook_inbox", "kind IN ('message', 'line_message')") == 0


# Messages on a customer's number


async def test_riya_stays_silent_on_a_customers_number(client, two_orgs, graph, rep):
    await connect(client, two_orgs["a"]["token"])
    sent_before = len(graph.paths("POST"))
    # Even a registered rep writing to the customer's own number gets no answer from Riya
    await post(client, customer_line_delivery(text_message("hello"), text_message("help", sender=PROSPECT)))
    await run_due_jobs()
    assert [path for path in graph.paths("POST")[sent_before:] if path.endswith("/messages")] == []
    assert await count("rep_conversations") == 0


async def test_stop_on_a_customers_number_opts_out_of_that_company_only(client, two_orgs, graph):
    await connect(client, two_orgs["a"]["token"])
    await post(client, customer_line_delivery(text_message("STOP", sender=PROSPECT)))
    await run_due_jobs()
    assert (
        await count(
            "opt_outs",
            "channel = 'whatsapp' AND address = :a AND organization_id = :o",
            a=PROSPECT,
            o=two_orgs["a"]["id"],
        )
        == 1
    )
    assert await count("opt_outs") == 1


# Follow-ups from the customer's number


async def _whatsapp_follow_up(client, token) -> None:
    settings = {
        "whatsapp_enabled": True,
        "whatsapp_template": "expo_follow_up",
        "whatsapp_consent_at_capture": True,
        "auto_send": True,
        "delay_minutes": 0,
        "email_enabled": False,
    }
    response = await client.put("/api/org/follow-up-settings", json=settings, headers=bearer(token))
    assert response.status_code == 200, response.text
    await send(client, photo_message())
    await make_jobs_due()
    await run_due_jobs()


async def test_follow_up_goes_from_the_customers_own_number(client, two_orgs, graph, rep, scripted):
    token = two_orgs["a"]["token"]
    await connect(client, token)
    await _whatsapp_follow_up(client, token)
    [(path, body, auth)] = graph.templates_sent()
    assert path.startswith(f"{CUSTOMER_LINE}/")
    assert auth == f"Bearer {CUSTOMER_TOKEN}"
    assert body["to"] == PROSPECT.lstrip("+")


async def test_without_a_number_follow_ups_go_from_devliqly(client, two_orgs, graph, rep, scripted):
    await _whatsapp_follow_up(client, two_orgs["a"]["token"])
    [(path, _, auth)] = graph.templates_sent()
    assert path.startswith(f"{get_settings().whatsapp_line_id}/")
    assert auth == "Bearer test-token"


async def test_disconnected_number_isnt_used(client, two_orgs, graph, rep, scripted):
    token = two_orgs["a"]["token"]
    await connect(client, token)
    await post(client, account_update("PARTNER_REMOVED"))
    await _whatsapp_follow_up(client, token)
    [(path, _, _)] = graph.templates_sent()
    assert path.startswith(f"{get_settings().whatsapp_line_id}/")


async def test_failed_delivery_on_the_customers_number_marks_the_follow_up(client, two_orgs, graph, rep, scripted):
    token = two_orgs["a"]["token"]
    await connect(client, token)
    await _whatsapp_follow_up(client, token)
    sent = (await client.get("/api/org/follow-ups", headers=bearer(token))).json()[0]
    assert sent["status"] == "sent"
    [(path, _, _)] = graph.templates_sent()
    message_id = next(f"wamid.out.{i + 1}" for i, call in enumerate(graph.calls) if call[2].get("type") == "template")
    failed = {"id": message_id, "status": "failed", "errors": [{"code": 131049, "title": "Not delivered"}]}
    await post(client, customer_line_delivery(statuses=[failed]))
    await run_due_jobs()
    assert (await client.get("/api/org/follow-ups", headers=bearer(token))).json()[0]["status"] == "failed"
