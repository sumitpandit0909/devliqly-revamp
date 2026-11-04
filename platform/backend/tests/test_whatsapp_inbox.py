import hashlib
import hmac
import json
import uuid

import httpx
import pytest
from sqlalchemy import text

from app.db import standalone_session
from app.queue import run_due_jobs
from app.whatsapp import client as meta_client
from app.whatsapp.events import read_delivery
from app.whatsapp.jobs import RECEIVED_REPLY, STRANGER_NOTICE
from tests.conftest import activate, bearer, owner_engine

LINE = "100200300"
REP_PHONE = "+919876543210"


def signed(body: dict | bytes, secret: str = "test-app-secret") -> dict:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return {"content": raw, "headers": {"X-Hub-Signature-256": signature, "Content-Type": "application/json"}}


def delivery(*messages, statuses=(), line=LINE, name="Ravi") -> dict:
    value = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": line}}
    if messages:
        value["messages"] = list(messages)
        value["contacts"] = [{"profile": {"name": name}, "wa_id": messages[0].get("from")}]
    if statuses:
        value["statuses"] = list(statuses)
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"value": value}]}]}


def text_message(body="hello", *, sender=REP_PHONE, message_id=None, **extra) -> dict:
    return {
        "from": sender.lstrip("+"),
        "id": message_id or f"wamid.{uuid.uuid4().hex}",
        "timestamp": "1793500000",
        "type": "text",
        "text": {"body": body},
        **extra,
    }


class FakeMeta:
    """Stands in for Meta's API. Set `responses` to script failures; it then answers normally."""

    def __init__(self):
        self.calls: list[dict] = []
        self.responses: list[httpx.Response] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.calls.append(body)
        if self.responses:
            return self.responses.pop(0)
        return httpx.Response(200, json={"messages": [{"id": f"wamid.out.{len(self.calls)}"}]})

    @property
    def texts(self) -> list[dict]:
        return [call for call in self.calls if call.get("type") == "text"]

    @property
    def read_receipts(self) -> list[dict]:
        return [call for call in self.calls if call.get("status") == "read"]


@pytest.fixture
def meta(monkeypatch) -> FakeMeta:
    fake = FakeMeta()
    monkeypatch.setattr(meta_client, "transport", httpx.MockTransport(fake))
    return fake


@pytest.fixture
async def rep(client, two_orgs) -> dict:
    """A rep in company A."""
    response = await client.post(
        "/api/org/members",
        json={"full_name": "Ravi", "phone": REP_PHONE, "role": "rep"},
        headers=bearer(two_orgs["a"]["token"]),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def post(client, body) -> httpx.Response:
    return await client.post("/webhooks/meta", **signed(body))


async def count(table: str, where: str = "true", **params) -> int:
    engine = owner_engine()
    async with engine.connect() as connection:
        value = (await connection.execute(text(f"SELECT count(*) FROM {table} WHERE {where}"), params)).scalar_one()  # noqa: S608
    await engine.dispose()
    return value


async def make_jobs_due() -> None:
    engine = owner_engine()
    async with engine.begin() as connection:
        await connection.execute(text("UPDATE job_queue SET run_after = now() WHERE status = 'pending'"))
    await engine.dispose()


async def rep_messages(client, token: str) -> list[dict]:
    conversations = (await client.get("/api/org/conversations", headers=bearer(token))).json()
    assert len(conversations) == 1
    url = f"/api/org/conversations/{conversations[0]['id']}/messages"
    return (await client.get(url, headers=bearer(token))).json()


# Connecting the webhook


async def test_meta_subscription_handshake(client):
    good = {"hub.mode": "subscribe", "hub.verify_token": "test-verify-token", "hub.challenge": "12345"}
    response = await client.get("/webhooks/meta", params=good)
    assert response.status_code == 200
    assert response.text == "12345"
    bad = await client.get("/webhooks/meta", params={**good, "hub.verify_token": "wrong"})
    assert bad.status_code == 403


# Only Meta gets in


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Hub-Signature-256": "sha256=deadbeef"},
        {"X-Hub-Signature-256": signed(b"something else")["headers"]["X-Hub-Signature-256"]},
    ],
)
async def test_unsigned_or_forged_webhooks_are_rejected(client, rep, headers):
    response = await client.post("/webhooks/meta", content=json.dumps(delivery(text_message())), headers=headers)
    assert response.status_code == 401
    assert await count("webhook_inbox") == 0
    assert await count("job_queue") == 0


async def test_wrong_secret_is_rejected(client):
    response = await client.post("/webhooks/meta", **signed(delivery(text_message()), secret="guess"))
    assert response.status_code == 401


async def test_signed_garbage_is_accepted_and_ignored(client):
    assert (await client.post("/webhooks/meta", **signed(b"not json"))).status_code == 200
    assert (await client.post("/webhooks/meta", **signed(b"[1, 2]"))).status_code == 200
    assert await count("webhook_inbox") == 0


async def test_oversized_body_is_rejected(client):
    response = await client.post("/webhooks/meta", content=b"x" * (3 * 1024 * 1024 + 1))
    assert response.status_code == 413


async def test_other_numbers_are_ignored(client, rep):
    assert (await post(client, delivery(text_message(), line="999"))).status_code == 200
    assert await count("webhook_inbox") == 0


# The main flow


async def test_message_is_saved_answered_and_marked_read(client, two_orgs, rep, meta):
    message = text_message("Namaste")
    assert (await post(client, delivery(message))).json() == {"status": "accepted"}
    await run_due_jobs()

    history = await rep_messages(client, two_orgs["a"]["token"])
    assert [(m["direction"], m["body"], m["status"]) for m in history] == [
        ("in", "Namaste", "received"),
        ("out", RECEIVED_REPLY, "sent"),
    ]
    assert meta.texts == [
        {
            "messaging_product": "whatsapp",
            "to": REP_PHONE.lstrip("+"),
            "type": "text",
            "text": {"body": RECEIVED_REPLY, "preview_url": False},
            "context": {"message_id": message["id"]},
        }
    ]
    assert meta.read_receipts == [{"messaging_product": "whatsapp", "status": "read", "message_id": message["id"]}]


async def test_meta_retries_change_nothing(client, two_orgs, rep, meta):
    message = text_message()
    for _ in range(3):
        assert (await post(client, delivery(message))).status_code == 200
    await run_due_jobs()
    assert (await post(client, delivery(message))).status_code == 200
    await run_due_jobs()

    assert await count("webhook_inbox") == 1
    assert len(await rep_messages(client, two_orgs["a"]["token"])) == 2
    assert len(meta.texts) == 1


async def test_several_messages_in_one_delivery(client, two_orgs, rep, meta):
    await post(client, delivery(text_message("one"), text_message("two")))
    await run_due_jobs()
    history = await rep_messages(client, two_orgs["a"]["token"])
    assert [m["body"] for m in history if m["direction"] == "in"] == ["one", "two"]


async def test_messages_are_handled_in_the_order_received(client, two_orgs, rep, meta):
    for body in ("first", "second", "third"):
        await post(client, delivery(text_message(body)))
    await run_due_jobs()
    history = await rep_messages(client, two_orgs["a"]["token"])
    assert [m["body"] for m in history if m["direction"] == "in"] == ["first", "second", "third"]


def test_message_types_are_understood():
    photo = {"from": "91", "id": "a", "type": "image", "image": {"id": "M1", "mime_type": "image/jpeg", "caption": "C"}}
    button = {
        "from": "91",
        "id": "b",
        "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": "B1", "title": "Yes"}},
    }
    voice = {"from": "91", "id": "c", "type": "audio", "audio": {"id": "M2", "mime_type": "audio/ogg"}}
    reply = {"from": "91", "id": "d", "type": "text", "text": {"body": "x"}, "context": {"id": "older"}}
    messages, _ = read_delivery(delivery(photo, button, voice, reply), LINE)
    assert (messages[0].kind, messages[0].media_id, messages[0].media_mime, messages[0].text) == (
        "image",
        "M1",
        "image/jpeg",
        "C",
    )
    assert (messages[1].kind, messages[1].button_id, messages[1].text) == ("button", "B1", "Yes")
    assert (messages[2].kind, messages[2].media_id) == ("audio", "M2")
    assert messages[3].quoted_provider_id == "older"


def test_malformed_items_are_skipped():
    body = delivery({"id": "no-sender", "type": "text"}, statuses=[{"status": "sent"}])
    assert read_delivery(body, LINE) == ([], [])


async def test_photo_keeps_its_media_id_and_reactions_get_no_reply(client, two_orgs, rep, meta):
    photo = {"from": REP_PHONE.lstrip("+"), "id": "wamid.photo", "type": "image", "image": {"id": "M1"}}
    reaction = {"from": REP_PHONE.lstrip("+"), "id": "wamid.r", "type": "reaction", "reaction": {"emoji": "👍"}}
    await post(client, delivery(photo, reaction))
    await run_due_jobs()
    assert await count("conversation_messages", "direction = 'in'") == 2
    assert await count("conversation_messages", "details->>'media_id' = 'M1'") == 1
    assert len(meta.texts) == 1


# People who aren't reps


async def test_stranger_gets_one_notice_a_day_and_nothing_is_saved(client, two_orgs, meta):
    stranger = "+919000000001"
    for _ in range(3):
        await post(client, delivery(text_message(sender=stranger)))
    await run_due_jobs()
    assert [call["text"]["body"] for call in meta.texts] == [STRANGER_NOTICE]
    assert meta.texts[0]["to"] == stranger.lstrip("+")
    assert await count("conversation_messages") == 0


async def test_removed_rep_is_treated_as_a_stranger(client, two_orgs, rep, meta):
    await client.patch(
        f"/api/org/members/{rep['id']}", json={"is_active": False}, headers=bearer(two_orgs["a"]["token"])
    )
    await post(client, delivery(text_message()))
    await run_due_jobs()
    assert await count("conversation_messages") == 0
    assert [call["text"]["body"] for call in meta.texts] == [STRANGER_NOTICE]


# Delivery receipts


async def _sent_reply_id(client, meta) -> str:
    await post(client, delivery(text_message()))
    await run_due_jobs()
    return f"wamid.out.{meta.calls.index(meta.texts[0]) + 1}"


async def _status_of_reply(token: str, client) -> dict:
    history = await rep_messages(client, token)
    return next(m for m in history if m["direction"] == "out")


async def test_receipts_move_status_forward_only(client, two_orgs, rep, meta):
    reply_id = await _sent_reply_id(client, meta)
    token = two_orgs["a"]["token"]
    await post(client, delivery(statuses=[{"id": reply_id, "status": "read"}]))
    await run_due_jobs()
    await post(client, delivery(statuses=[{"id": reply_id, "status": "delivered"}]))
    await run_due_jobs()
    assert (await _status_of_reply(token, client))["status"] == "read"


async def test_failed_receipt_records_the_reason(client, two_orgs, rep, meta):
    reply_id = await _sent_reply_id(client, meta)
    failure = {"id": reply_id, "status": "failed", "errors": [{"code": 131026, "title": "Message undeliverable"}]}
    await post(client, delivery(statuses=[failure]))
    await run_due_jobs()
    reply = await _status_of_reply(two_orgs["a"]["token"], client)
    assert (reply["status"], reply["error"]) == ("failed", "131026: Message undeliverable")


async def test_receipt_for_unknown_message_retries_then_is_dropped(client, rep):
    await post(client, delivery(statuses=[{"id": "wamid.mystery", "status": "delivered"}]))
    for _ in range(4):
        await run_due_jobs()
        await make_jobs_due()
    assert await count("job_queue", "status = 'done'") == 1
    assert await count("job_queue", "status = 'dead'") == 0


# When sending goes wrong


@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(500, json={"error": {"code": 1, "message": "Boom"}}),
        httpx.Response(429, json={"error": {"code": 130429, "message": "Too fast"}}),
        httpx.Response(400, json={"error": {"code": 131056, "message": "Pair rate limit"}}),
    ],
)
async def test_temporary_failures_retry_and_then_send_once(client, two_orgs, rep, meta, failure):
    send_failures = [failure]

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("type") == "text" and send_failures:
            meta.calls.append(body)
            return send_failures.pop()
        return meta(request)

    meta_client.transport = httpx.MockTransport(respond)
    await post(client, delivery(text_message()))
    await run_due_jobs()
    assert (await _status_of_reply(two_orgs["a"]["token"], client))["status"] == "queued"
    assert await count("job_queue", "status = 'pending' AND last_error IS NOT NULL") == 1

    await make_jobs_due()
    await run_due_jobs()
    assert (await _status_of_reply(two_orgs["a"]["token"], client))["status"] == "sent"
    assert await count("job_queue", "status IN ('pending', 'running', 'dead')") == 0


async def test_rejected_message_fails_once_without_retrying(client, two_orgs, rep, meta):
    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        meta.calls.append(body)
        if body.get("type") == "text":
            return httpx.Response(400, json={"error": {"code": 131026, "message": "Undeliverable"}})
        return httpx.Response(200, json={"success": True})

    meta_client.transport = httpx.MockTransport(respond)
    await post(client, delivery(text_message()))
    await run_due_jobs()
    await make_jobs_due()
    await run_due_jobs()

    reply = await _status_of_reply(two_orgs["a"]["token"], client)
    assert reply["status"] == "failed"
    assert "131026" in reply["error"]
    assert len(meta.texts) == 1


async def test_network_failure_is_retried(client, two_orgs, rep, meta):
    def respond(request: httpx.Request) -> httpx.Response:
        if json.loads(request.content).get("type") == "text":
            raise httpx.ConnectError("no route")
        return meta(request)

    meta_client.transport = httpx.MockTransport(respond)
    await post(client, delivery(text_message()))
    await run_due_jobs()
    assert await count("job_queue", "status = 'pending' AND last_error LIKE '%reach Meta%'") == 1


# Customers stay separate


async def test_conversations_stay_within_their_company(client, two_orgs, rep, meta):
    await post(client, delivery(text_message("private")))
    await run_due_jobs()
    a, b = bearer(two_orgs["a"]["token"]), bearer(two_orgs["b"]["token"])

    conversation_id = (await client.get("/api/org/conversations", headers=a)).json()[0]["id"]
    assert (await client.get("/api/org/conversations", headers=b)).json() == []
    assert (await client.get(f"/api/org/conversations/{conversation_id}/messages", headers=b)).status_code == 404


async def test_reps_see_only_their_own_conversation(client, two_orgs, rep, meta):
    other = await client.post(
        "/api/org/members",
        json={"full_name": "Sana", "phone": "+919876543299", "email": "sana@acme-demo.com", "role": "rep"},
        headers=bearer(two_orgs["a"]["token"]),
    )
    sana = await activate(client, other.json()["setup_url"], "sana@acme-demo.com")
    await post(client, delivery(text_message("from ravi")))
    await post(client, delivery(text_message("from sana", sender="+919876543299")))
    await run_due_jobs()

    assert len((await client.get("/api/org/conversations", headers=bearer(two_orgs["a"]["token"]))).json()) == 2
    own = (await client.get("/api/org/conversations", headers=bearer(sana))).json()
    assert [c["rep_name"] for c in own] == ["Sana"]
    others = next(
        c
        for c in (await client.get("/api/org/conversations", headers=bearer(two_orgs["a"]["token"]))).json()
        if c["rep_name"] == "Ravi"
    )
    response = await client.get(f"/api/org/conversations/{others['id']}/messages", headers=bearer(sana))
    assert response.status_code == 404


@pytest.mark.parametrize("table", ["webhook_inbox", "job_queue", "rep_conversations", "conversation_messages"])
async def test_new_tables_show_nothing_without_a_scope(client, two_orgs, rep, meta, table):
    await post(client, delivery(text_message()))
    await run_due_jobs()
    assert await count(table) > 0
    async with standalone_session() as db:
        assert (await db.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one() == 0  # noqa: S608
