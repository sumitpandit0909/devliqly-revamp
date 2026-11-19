"""The CRM's API, follow-ups, opt-outs, housekeeping and the AI providers' request shapes."""

import json
import smtplib
from datetime import UTC, date, datetime

import httpx
import httpx2
import pytest
from sqlalchemy import text

from app import ai, mailer
from app.config import get_settings
from app.db import set_scope, standalone_session
from app.followups import unsubscribe_token
from app.maintenance import prune_old_records
from app.queue import ClaimedJob, run_due_jobs
from app.routers.leads import _safe_cell
from tests.conftest import activate, bearer, owner_engine
from tests.test_card_capture import (  # noqa: F401
    ScriptedAi,
    button_press,
    lead_detail,
    leads,
    meta,
    photo_message,
    reading,
    rep,
    scripted,
    send,
)
from tests.test_whatsapp_inbox import count, delivery, make_jobs_due, post, text_message


class FakeResend:
    def __init__(self):
        self.calls: list[dict] = []
        self.keys: list[str] = []
        self.responses: list[httpx.Response] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(json.loads(request.content))
        self.keys.append(request.headers["idempotency-key"])
        if self.responses:
            return self.responses.pop(0)
        return httpx.Response(200, json={"id": f"email-{len(self.calls)}"})


@pytest.fixture
def resend(monkeypatch) -> FakeResend:
    fake = FakeResend()
    monkeypatch.setattr(mailer, "transport", httpx.MockTransport(fake))
    return fake


EMAIL_SETTINGS = {
    "email_enabled": True,
    "auto_send": False,
    "email_subject": "Good to meet you, {first_name}",
    "email_body": "Hi {first_name} from {company}, {rep_name} here. {nothing}",
    "delay_minutes": 0,
    "sender_name": "Acme",
    "reply_to": "sales@acme-demo.com",
}


async def _settings(client, token, **values) -> None:
    response = await client.put("/api/org/follow-up-settings", json=values, headers=bearer(token))
    assert response.status_code == 200, response.text


# Leads


async def test_search_filter_and_pagination(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    for n in range(3):
        scripted.script(reading(full_name=f"Person {n}", phones=[f"+91982001234{n}"], emails=[f"p{n}@acme.com"]))
    await send(client, *[photo_message() for _ in range(3)])

    found = (await client.get("/api/org/leads", params={"q": "person 1"}, headers=bearer(token))).json()
    assert [row["full_name"] for row in found["items"]] == ["Person 1"]
    literal = (await client.get("/api/org/leads", params={"q": "%"}, headers=bearer(token))).json()
    assert literal["total"] == 0
    page = (await client.get("/api/org/leads", params={"limit": 2}, headers=bearer(token))).json()
    assert (len(page["items"]), page["total"]) == (2, 3)


async def test_update_status_interest_and_details_logs_a_timeline(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    response = await client.patch(
        f"/api/org/leads/{lead['id']}",
        json={"status": "qualified", "interest": "hot", "job_title": "CEO", "company": "New Co"},
        headers=bearer(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["status"], body["interest"], body["job_title"], body["company"]) == (
        "qualified",
        "hot",
        "CEO",
        "New Co",
    )
    assert {"status", "interest", "correction", "captured"} <= {a["kind"] for a in body["activities"]}


async def test_invalid_contact_details_are_refused(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    response = await client.patch(f"/api/org/leads/{lead['id']}", json={"phone": "12"}, headers=bearer(token))
    assert response.status_code == 422
    assert (await lead_detail(client, token, lead["id"]))["phone"] == lead["phone"]


async def test_notes(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    response = await client.post(f"/api/org/leads/{lead['id']}/notes", json={"body": "Called"}, headers=bearer(token))
    assert response.status_code == 201
    assert response.json()["activities"][0]["body"] == "Called"
    assert response.json()["activities"][0]["actor"] == "Acme Owner"


async def test_reassigning_needs_a_manager_and_a_team_member(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    url = f"/api/org/leads/{lead['id']}"
    other_org_me = (await client.get("/api/me", headers=bearer(two_orgs["b"]["token"]))).json()["id"]
    bad = await client.patch(url, json={"owner_user_id": other_org_me}, headers=bearer(token))
    assert bad.status_code == 422
    me = (await client.get("/api/me", headers=bearer(token))).json()["id"]
    good = await client.patch(url, json={"owner_user_id": me}, headers=bearer(token))
    assert good.json()["owner"] == "Acme Owner"


async def _rep_with_login(client, token) -> str:
    """A second rep who can log in to the CRM."""
    response = await client.post(
        "/api/org/members",
        json={"full_name": "Sana", "phone": "+919876543299", "email": "sana@acme-demo.com", "role": "rep"},
        headers=bearer(token),
    )
    return await activate(client, response.json()["setup_url"], "sana@acme-demo.com")


async def test_reps_see_only_their_own_leads_and_cant_export(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    card = (await lead_detail(client, token, lead["id"]))["cards"][0]
    sana = await _rep_with_login(client, token)

    assert await leads(client, sana) == []
    assert (await client.get(f"/api/org/leads/{lead['id']}", headers=bearer(sana))).status_code == 404
    assert (await client.get(f"/api/org/cards/{card['id']}/image", headers=bearer(sana))).status_code == 404
    assert (await client.get("/api/org/leads/export.csv", headers=bearer(sana))).status_code == 403
    assert (await client.get("/api/org/dashboard", headers=bearer(sana))).json()["total"] == 0


async def test_another_customers_lead_is_not_found(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    lead = (await leads(client, two_orgs["a"]["token"]))[0]
    other = bearer(two_orgs["b"]["token"])
    assert (await client.get(f"/api/org/leads/{lead['id']}", headers=other)).status_code == 404
    response = await client.patch(f"/api/org/leads/{lead['id']}", json={"status": "won"}, headers=other)
    assert response.status_code == 404
    assert (await client.delete(f"/api/org/contacts/{lead['contact_id']}", headers=other)).status_code == 404


# Export


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("=HYPERLINK(1)", "'=HYPERLINK(1)"),
        ("@cmd", "'@cmd"),
        ("-1+2", "'-1+2"),
        ("+SUM(A1)", "'+SUM(A1)"),
        ("+919820012345", "+919820012345"),
        ("Asha", "Asha"),
        (None, ""),
    ],
)
def test_spreadsheet_formulas_are_defused(value, expected):
    assert _safe_cell(value) == expected


async def test_export_has_the_leads_of_an_event(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    scripted.script(reading(full_name="=cmd()"))
    await send(client, photo_message())
    response = await client.get("/api/org/leads/export.csv", headers=bearer(token))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "'=cmd()" in response.text
    assert "+919820012345" in response.text


# Review queue


async def _card_in_review(client, token, meta_fixture, scripted_fixture) -> dict:
    scripted_fixture.script(reading(phones=[], emails=[]))
    await send(client, photo_message(caption="Keen"))
    queue = (await client.get("/api/org/reviews", headers=bearer(token))).json()
    assert len(queue) == 1
    return queue[0]


async def test_incomplete_card_waits_then_approval_saves_it(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    card = await _card_in_review(client, token, meta, scripted)
    assert "No phone number or email found" in card["problems"]
    assert await count("contacts") == 0

    response = await client.post(
        f"/api/org/reviews/{card['id']}/approve",
        json={"full_name": "Asha Rao", "company": "Acme", "phone": "9820012345"},
        headers=bearer(token),
    )
    assert response.status_code == 200, response.text
    assert (await client.get("/api/org/reviews", headers=bearer(token))).json() == []
    row = (await leads(client, token))[0]
    assert (row["full_name"], row["owner"], row["phone"]) == ("Asha Rao", "Ravi", "+919820012345")
    assert await count("usage_months", "cards_saved = 1") == 1


async def test_approval_runs_the_same_checks(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    card = await _card_in_review(client, token, meta, scripted)
    response = await client.post(
        f"/api/org/reviews/{card['id']}/approve",
        json={"full_name": "Asha", "phone": "12"},
        headers=bearer(token),
    )
    assert response.status_code == 422
    assert await count("contacts") == 0


async def test_rejecting_and_other_customers(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    card = await _card_in_review(client, token, meta, scripted)
    other = bearer(two_orgs["b"]["token"])
    assert (await client.post(f"/api/org/reviews/{card['id']}/reject", headers=other)).status_code == 404
    assert (await client.post(f"/api/org/reviews/{card['id']}/reject", headers=bearer(token))).status_code == 204
    assert (await client.post(f"/api/org/reviews/{card['id']}/reject", headers=bearer(token))).status_code == 404


# Dashboard


async def test_dashboard_counts(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    await client.patch(
        f"/api/org/leads/{lead['id']}",
        json={"interest": "hot", "follow_up_on": datetime.now(UTC).date().isoformat()},
        headers=bearer(token),
    )
    board = (await client.get("/api/org/dashboard", headers=bearer(token))).json()
    assert (board["total"], board["today"], board["hot"], board["follow_ups_due"]) == (1, 1, 1, 1)
    assert board["by_rep"] == [{"label": "Ravi", "count": 1}]
    assert board["by_event"] == [{"label": "No event", "count": 1}]
    assert (board["cards_this_month"], board["monthly_card_limit"]) == (1, 1000)
    assert (await client.get("/api/org/dashboard", headers=bearer(two_orgs["b"]["token"]))).json()["total"] == 0


# Follow-ups


async def test_email_follow_up_goes_by_default_with_the_standard_message(client, two_orgs, rep, meta, scripted, resend):
    # A customer who never opened the follow-up settings
    await send(client, photo_message())
    assert await count("follow_ups", "channel = 'email' AND status = 'scheduled'") == 1
    assert await count("follow_ups", "channel = 'whatsapp'") == 0
    assert resend.calls == []

    await make_jobs_due()
    await run_due_jobs()
    assert len(resend.calls) == 1
    assert resend.calls[0]["subject"] == "Great meeting you, Asha"
    assert resend.calls[0]["text"].startswith("Hi Asha,")
    settings = (await client.get("/api/org/follow-up-settings", headers=bearer(two_orgs["a"]["token"]))).json()
    assert (settings["email_enabled"], settings["whatsapp_enabled"]) == (True, False)


class FakeSmtp:
    """Stands in for smtplib.SMTP, recording what a real mail server would have received."""

    def __init__(self):
        self.logins: list[tuple[str, str]] = []
        self.messages: list = []
        self.error: Exception | None = None

    def __call__(self, host: str, port: int) -> "FakeSmtp":
        self.address = (host, port)
        return self

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def login(self, username: str, password: str) -> None:
        self.logins.append((username, password))

    def send_message(self, message) -> None:
        if self.error:
            raise self.error
        self.messages.append(message)


@pytest.fixture
def gmail(monkeypatch) -> FakeSmtp:
    fake = FakeSmtp()
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(settings, "smtp_username", "someone@gmail.com")
    monkeypatch.setattr(settings, "smtp_password", "app-password")
    monkeypatch.setattr(mailer, "smtp_factory", fake)
    return fake


async def test_email_goes_through_gmail_when_smtp_is_set(client, two_orgs, rep, meta, scripted, resend, gmail):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **{**EMAIL_SETTINGS, "auto_send": True})
    await send(client, photo_message())
    await make_jobs_due()
    await run_due_jobs()

    assert resend.calls == []
    assert gmail.address == ("smtp.gmail.com", 587)
    assert gmail.logins == [("someone@gmail.com", "app-password")]
    [message] = gmail.messages
    assert message["From"] == "Acme <hello@acme-demo.com>"
    assert (message["To"], message["Reply-To"]) == ("asha@acmetraders.com", "sales@acme-demo.com")
    assert message["Subject"] == "Good to meet you, Asha"
    assert "/u/" in message["List-Unsubscribe"]
    assert message.get_content().startswith("Hi Asha from Acme Traders Pvt Ltd")
    sent = (await client.get("/api/org/follow-ups", headers=bearer(token))).json()[0]
    assert sent["status"] == "sent"
    assert message["Message-ID"] == f"<follow-up.{sent['id']}@acme-demo.com>"


async def test_wrong_gmail_password_fails_visibly_without_retrying(client, two_orgs, rep, meta, scripted, gmail):
    gmail.error = smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
    token = two_orgs["a"]["token"]
    await _settings(client, token, **{**EMAIL_SETTINGS, "auto_send": True})
    await send(client, photo_message())
    await make_jobs_due()
    await run_due_jobs()

    failed = (await client.get("/api/org/follow-ups", headers=bearer(token))).json()[0]
    assert failed["status"] == "failed"
    assert "SMTP_PASSWORD" in failed["error"]


async def test_mail_server_errors_are_sorted(gmail):
    async def outcome(error: Exception) -> type[Exception]:
        gmail.error = error
        with pytest.raises((mailer.TemporaryEmailError, mailer.EmailRejected)) as caught:
            await mailer.send_email(
                to="a@b.com",
                subject="s",
                body="b",
                sender_name=None,
                reply_to=None,
                unsubscribe_url="http://test/u/x",
                idempotency_key="k",
            )
        return caught.type

    assert await outcome(smtplib.SMTPDataError(421, b"Try again later")) is mailer.TemporaryEmailError
    assert await outcome(smtplib.SMTPDataError(550, b"Daily sending limit exceeded")) is mailer.EmailRejected
    assert await outcome(smtplib.SMTPRecipientsRefused({})) is mailer.EmailRejected
    assert await outcome(smtplib.SMTPServerDisconnected("gone")) is mailer.TemporaryEmailError
    assert await outcome(TimeoutError()) is mailer.TemporaryEmailError


async def test_nothing_is_sent_once_email_is_switched_off(client, two_orgs, rep, meta, scripted, resend):
    await _settings(client, two_orgs["a"]["token"], **{**EMAIL_SETTINGS, "email_enabled": False})
    await send(client, photo_message())
    assert await count("follow_ups") == 0
    assert resend.calls == []


async def test_drafts_wait_for_approval_then_send_once(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **EMAIL_SETTINGS)
    await send(client, photo_message())
    drafts = (await client.get("/api/org/follow-ups", params={"status": "draft"}, headers=bearer(token))).json()
    assert len(drafts) == 1
    assert drafts[0]["subject"] == "Good to meet you, Asha"
    assert drafts[0]["body"].startswith("Hi Asha from Acme Traders Pvt Ltd, Ravi here. {nothing}")
    assert resend.calls == []

    url = f"/api/org/follow-ups/{drafts[0]['id']}"
    assert (
        await client.patch(url, json={"subject": "Hello", "body": "Edited"}, headers=bearer(token))
    ).status_code == 200
    assert (await client.post(f"{url}/approve", headers=bearer(token))).json()["status"] == "scheduled"
    await run_due_jobs()

    assert len(resend.calls) == 1
    call = resend.calls[0]
    assert (call["to"], call["subject"], call["reply_to"]) == (["asha@acmetraders.com"], "Hello", "sales@acme-demo.com")
    assert call["from"] == "Acme <hello@acme-demo.com>"
    assert "/u/" in call["headers"]["List-Unsubscribe"]
    assert "Unsubscribe" in call["text"]
    assert resend.keys == [drafts[0]["id"]]
    sent = (await client.get("/api/org/follow-ups", headers=bearer(token))).json()[0]
    assert sent["status"] == "sent"
    assert (await client.post(f"{url}/approve", headers=bearer(token))).status_code == 409


async def test_auto_send_waits_for_the_delay(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **{**EMAIL_SETTINGS, "auto_send": True, "delay_minutes": 30})
    await send(client, photo_message())
    assert resend.calls == []
    assert await count("follow_ups", "status = 'scheduled'") == 1
    await make_jobs_due()
    await run_due_jobs()
    assert len(resend.calls) == 1


AUTOMATIC = {key: value for key, value in EMAIL_SETTINGS.items() if key != "auto_send"}


async def test_follow_ups_send_without_anyone_approving_by_default(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    assert (await client.get("/api/org/follow-up-settings", headers=bearer(token))).json()["auto_send"] is True
    await _settings(client, token, **AUTOMATIC)
    await send(client, photo_message())
    assert len(resend.calls) == 1
    assert await count("follow_ups", "status = 'sent'") == 1


async def test_automatic_follow_up_waits_for_a_flagged_card_to_be_checked(
    client, two_orgs, rep, meta, scripted, resend
):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **AUTOMATIC)
    scripted.script(reading(confidence=0.2))
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    assert lead["needs_review"] is True
    assert resend.calls == []
    assert await count("follow_ups", "status = 'draft'") == 1

    body = {"email": "fixed@acmetraders.com", "needs_review": False}
    response = await client.patch(f"/api/org/leads/{lead['id']}", json=body, headers=bearer(token))
    assert response.status_code == 200
    await run_due_jobs()
    assert [call["to"] for call in resend.calls] == [["fixed@acmetraders.com"]]


async def test_correcting_an_address_changes_the_waiting_follow_up(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **{**AUTOMATIC, "delay_minutes": 30})
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    await client.patch(f"/api/org/leads/{lead['id']}", json={"email": "right@acmetraders.com"}, headers=bearer(token))
    await make_jobs_due()
    await run_due_jobs()
    assert [call["to"] for call in resend.calls] == [["right@acmetraders.com"]]


async def test_switching_email_off_stops_what_is_waiting(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **{**AUTOMATIC, "delay_minutes": 30})
    await send(client, photo_message())
    await _settings(client, token, **{**AUTOMATIC, "delay_minutes": 30, "email_enabled": False})
    await make_jobs_due()
    await run_due_jobs()
    assert resend.calls == []
    assert await count("follow_ups", "status = 'blocked'") == 1


async def test_rescan_doesnt_message_someone_twice(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **{**EMAIL_SETTINGS, "auto_send": True})
    await send(client, photo_message())
    await send(client, photo_message())
    await make_jobs_due()
    await run_due_jobs()
    assert len(resend.calls) == 1


async def test_newly_learned_email_gets_a_follow_up(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **EMAIL_SETTINGS)
    scripted.script(reading(emails=[]))
    await send(client, photo_message())
    assert await count("follow_ups") == 0
    lead = (await leads(client, token))[0]
    await client.patch(f"/api/org/leads/{lead['id']}", json={"email": "asha@acmetraders.com"}, headers=bearer(token))
    assert await count("follow_ups", "status = 'draft'") == 1


async def test_temporary_failure_retries_and_failures_are_visible(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **EMAIL_SETTINGS)
    await send(client, photo_message())
    draft = (await client.get("/api/org/follow-ups", headers=bearer(token))).json()[0]
    url = f"/api/org/follow-ups/{draft['id']}"

    resend.responses = [httpx.Response(500), httpx.Response(422, json={"message": "bad address"})]
    await client.post(f"{url}/approve", headers=bearer(token))
    await run_due_jobs()
    assert await count("follow_ups", "status = 'scheduled'") == 1
    await make_jobs_due()
    await run_due_jobs()
    failed = (await client.get("/api/org/follow-ups", params={"status": "failed"}, headers=bearer(token))).json()
    assert "bad address" in failed[0]["error"]

    assert (await client.post(f"{url}/retry", headers=bearer(token))).status_code == 200
    await run_due_jobs()
    assert (await client.get("/api/org/follow-ups", headers=bearer(token))).json()[0]["status"] == "sent"
    assert resend.keys[-1] == draft["id"]


async def test_cancelled_follow_up_isnt_sent(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **{**EMAIL_SETTINGS, "auto_send": True, "delay_minutes": 30})
    await send(client, photo_message())
    row = (await client.get("/api/org/follow-ups", headers=bearer(token))).json()[0]
    assert (await client.post(f"/api/org/follow-ups/{row['id']}/cancel", headers=bearer(token))).status_code == 200
    await make_jobs_due()
    await run_due_jobs()
    assert resend.calls == []


async def test_email_settings_are_validated(client, two_orgs):
    response = await client.put(
        "/api/org/follow-up-settings", json={"email_enabled": True}, headers=bearer(two_orgs["a"]["token"])
    )
    assert response.status_code == 422
    response = await client.put(
        "/api/org/follow-up-settings", json={"whatsapp_enabled": True}, headers=bearer(two_orgs["a"]["token"])
    )
    assert response.status_code == 422


async def test_reps_cant_change_follow_up_settings(client, two_orgs):
    sana = await _rep_with_login(client, two_orgs["a"]["token"])
    response = await client.put("/api/org/follow-up-settings", json=EMAIL_SETTINGS, headers=bearer(sana))
    assert response.status_code == 403


# Opting out


async def test_unsubscribe_link_asks_then_blocks_everything_waiting(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **{**EMAIL_SETTINGS, "auto_send": True, "delay_minutes": 30})
    await send(client, photo_message())
    link = f"/u/{unsubscribe_token(_org(two_orgs), 'asha@acmetraders.com')}"

    page = await client.get(link)
    assert page.status_code == 200
    assert "asha@acmetraders.com" in page.text
    assert await count("opt_outs") == 0

    assert (await client.post(link)).status_code == 200
    assert (await client.post(link)).status_code == 200
    assert await count("opt_outs") == 1
    assert await count("follow_ups", "status = 'blocked'") == 1
    await make_jobs_due()
    await run_due_jobs()
    assert resend.calls == []


def _org(two_orgs) -> "object":
    import uuid

    return uuid.UUID(two_orgs["a"]["id"])


async def test_forged_unsubscribe_link_is_refused(client):
    assert (await client.get("/u/not-a-token")).status_code == 404
    assert (await client.post("/u/not-a-token")).status_code == 404


async def test_opted_out_person_is_never_planned_or_sent_to(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **{**EMAIL_SETTINGS, "auto_send": True})
    response = await client.post(
        "/api/org/opt-outs", json={"channel": "email", "address": "ASHA@acmetraders.com"}, headers=bearer(token)
    )
    assert response.status_code == 204
    await send(client, photo_message())
    assert await count("follow_ups") == 0
    assert resend.calls == []


async def test_opt_out_at_the_last_moment_blocks_sending(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **{**EMAIL_SETTINGS, "auto_send": True, "delay_minutes": 30})
    await send(client, photo_message())
    engine = owner_engine()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO opt_outs (id, organization_id, channel, address, source) "
                "VALUES (gen_random_uuid(), :org, 'email', 'asha@acmetraders.com', 'test')"
            ),
            {"org": two_orgs["a"]["id"]},
        )
    await engine.dispose()
    await make_jobs_due()
    await run_due_jobs()
    assert resend.calls == []
    assert await count("follow_ups", "status = 'blocked'") == 1


WHATSAPP_SETTINGS = {
    "whatsapp_enabled": True,
    "whatsapp_template": "expo_thanks",
    "auto_send": True,
    "delay_minutes": 0,
}


async def test_scanned_card_alone_gets_no_whatsapp_message(client, two_orgs, rep, meta, scripted):
    await _settings(client, two_orgs["a"]["token"], **WHATSAPP_SETTINGS)
    await send(client, photo_message())
    assert await count("follow_ups") == 0
    assert not [call for call in meta.calls if call.get("type") == "template"]


async def test_whatsapp_goes_only_after_recorded_consent(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **WHATSAPP_SETTINGS)
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    response = await client.patch(f"/api/org/leads/{lead['id']}", json={"whatsapp_opt_in": True}, headers=bearer(token))
    assert response.json()["whatsapp_opt_in"] is True
    await make_jobs_due()
    await run_due_jobs()
    templates = [call for call in meta.calls if call.get("type") == "template"]
    assert len(templates) == 1
    assert templates[0]["to"] == "919820012345"
    assert templates[0]["template"]["name"] == "expo_thanks"
    parameters = templates[0]["template"]["components"][0]["parameters"]
    assert [p["text"] for p in parameters] == ["Asha", "Ravi"]


async def test_company_that_always_asks_doesnt_tick_each_lead(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **WHATSAPP_SETTINGS, whatsapp_consent_at_capture=True)
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    detail = (await client.get(f"/api/org/leads/{lead['id']}", headers=bearer(token))).json()
    assert detail["whatsapp_opt_in"] is True
    assert await count("lead_activities", "kind = 'whatsapp_consent'") == 1
    await make_jobs_due()
    await run_due_jobs()
    templates = [call for call in meta.calls if call.get("type") == "template"]
    assert [call["to"] for call in templates] == ["919820012345"]


async def test_asking_at_capture_never_overrides_someone_who_said_stop(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **WHATSAPP_SETTINGS, whatsapp_consent_at_capture=True)
    response = await client.post(
        "/api/org/opt-outs", json={"channel": "whatsapp", "address": "+919820012345"}, headers=bearer(token)
    )
    assert response.status_code == 204
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    detail = (await client.get(f"/api/org/leads/{lead['id']}", headers=bearer(token))).json()
    assert detail["whatsapp_opt_in"] is False
    await make_jobs_due()
    await run_due_jobs()
    assert not [call for call in meta.calls if call.get("type") == "template"]


async def test_consent_withdrawn_before_sending_blocks_it(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **{**WHATSAPP_SETTINGS, "delay_minutes": 30})
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    url = f"/api/org/leads/{lead['id']}"
    await client.patch(url, json={"whatsapp_opt_in": True}, headers=bearer(token))
    await client.patch(url, json={"whatsapp_opt_in": False}, headers=bearer(token))
    await make_jobs_due()
    await run_due_jobs()
    assert not [call for call in meta.calls if call.get("type") == "template"]
    assert await count("follow_ups", "status = 'blocked'") == 1


async def test_prospect_replying_stop_is_opted_out_everywhere(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await send(client, photo_message())
    prospect = "+919820012345"
    await post(client, delivery(text_message("STOP", sender=prospect)))
    await run_due_jobs()
    assert await count("opt_outs", "channel = 'whatsapp' AND address = :a", a=prospect) == 1
    assert (await client.get("/api/org/opt-outs", headers=bearer(token))).json()[0]["source"] == "whatsapp_reply"
    assert "unsubscribed" in [call for call in meta.calls if call.get("type") == "text"][-1]["text"]["body"]


async def test_failed_whatsapp_receipt_marks_the_follow_up(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **WHATSAPP_SETTINGS)
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    await client.patch(f"/api/org/leads/{lead['id']}", json={"whatsapp_opt_in": True}, headers=bearer(token))
    await make_jobs_due()
    await run_due_jobs()
    index = next(i for i, call in enumerate(meta.calls) if call.get("type") == "template")
    failure = {
        "id": f"wamid.out.{index + 1}",
        "status": "failed",
        "errors": [{"code": 131026, "title": "Undeliverable"}],
    }
    await post(client, delivery(statuses=[failure]))
    await run_due_jobs()
    row = (await client.get("/api/org/follow-ups", headers=bearer(token))).json()[0]
    assert (row["status"], row["error"]) == ("failed", "131026: Undeliverable")


# Erasing someone


async def test_erasing_a_contact_removes_everything_about_them(client, two_orgs, rep, meta, scripted, resend):
    token = two_orgs["a"]["token"]
    await _settings(client, token, **EMAIL_SETTINGS)
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    card = (await lead_detail(client, token, lead["id"]))["cards"][0]
    assert await count("conversation_messages", "details->>'card_id' = :c", c=card["id"]) == 1

    assert (await client.delete(f"/api/org/contacts/{lead['contact_id']}", headers=bearer(token))).status_code == 204
    await run_due_jobs()
    for table in ("contacts", "leads", "business_cards", "lead_activities", "follow_ups"):
        assert await count(table) == 0, table
    assert await count("conversation_messages", "details->>'card_id' = :c", c=card["id"]) == 0
    assert await count("conversation_messages", "kind = 'image'") == 0
    assert await count("job_queue", "kind = 'delete_stored_files' AND status = 'done'") == 1
    assert (await client.get(f"/api/org/cards/{card['id']}/image", headers=bearer(token))).status_code == 404


async def test_erasing_a_contact_removes_chat_that_mentions_them(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    card = (await lead_detail(client, token, lead["id"]))["cards"][0]
    await send(client, button_press(f"note:{card['id']}"))
    await send(client, text_message("Wants 200 units by March"))
    assert await count("conversation_messages", "body LIKE '%200 units%'") == 1
    assert await count("conversation_messages", "body LIKE :name", name=f"%Note added to {lead['full_name']}%") == 1

    assert (await client.delete(f"/api/org/contacts/{lead['contact_id']}", headers=bearer(token))).status_code == 204
    assert await count("conversation_messages", "body LIKE '%200 units%'") == 0
    assert await count("conversation_messages", "body LIKE :name", name=f"%{lead['full_name']}%") == 0


async def test_erasing_a_contact_keeps_unrelated_chat(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await send(client, text_message("Hello"))
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    assert (await client.delete(f"/api/org/contacts/{lead['contact_id']}", headers=bearer(token))).status_code == 204
    assert await count("conversation_messages", "body = 'Hello'") == 1


async def test_chat_shows_each_reply_after_the_message_it_answers(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await send(client, text_message("Hello"))
    await send(client, text_message("Hello again"))
    headers = bearer(token)
    conversation = (await client.get("/api/org/conversations", headers=headers)).json()[0]
    messages = (await client.get(f"/api/org/conversations/{conversation['id']}/messages", headers=headers)).json()
    assert [message["direction"] for message in messages] == ["in", "out", "in", "out"]


async def test_reps_cant_erase(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await send(client, photo_message())
    lead = (await leads(client, token))[0]
    sana = await _rep_with_login(client, token)
    assert (await client.delete(f"/api/org/contacts/{lead['contact_id']}", headers=bearer(sana))).status_code == 403


# Staff


async def test_overview_shows_usage_and_estimated_cost(client, two_orgs, rep, meta, scripted, operator_token):
    await send(client, photo_message())
    board = (await client.get("/api/operator/overview", headers=bearer(operator_token))).json()
    acme = next(org for org in board["organizations"] if org["name"] == "Acme")
    assert (acme["cards_this_month"], acme["ai_calls_this_month"]) == (1, 1)
    assert acme["ai_cost_usd_this_month"] == pytest.approx(0.0012)
    assert board["ai_calls_failed_this_month"] == 0
    assert (await client.get("/api/operator/overview", headers=bearer(two_orgs["a"]["token"]))).status_code == 403


async def test_staff_can_read_usage_but_not_customer_data(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    async with standalone_session() as db:
        await set_scope(db, operator=True)
        assert (await db.execute(text("SELECT count(*) FROM ai_calls"))).scalar_one() == 1
        assert (await db.execute(text("SELECT count(*) FROM contacts"))).scalar_one() == 0


# Queue permissions


async def test_a_customer_session_can_queue_only_its_own_two_job_kinds(two_orgs):
    from sqlalchemy.exc import DBAPIError

    from app.queue import enqueue

    async with standalone_session() as db:
        await set_scope(db, org_id=_org(two_orgs))
        await enqueue(db, "send_follow_up", {"follow_up_id": "x"})
        await db.rollback()
    with pytest.raises(DBAPIError, match="row-level security"):
        async with standalone_session() as db:
            await set_scope(db, org_id=_org(two_orgs))
            await enqueue(db, "route_incoming_message", {})


# Housekeeping


async def test_old_records_are_pruned_and_recent_ones_kept(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    engine = owner_engine()
    async with engine.begin() as connection:
        await connection.execute(text("UPDATE webhook_inbox SET received_at = now() - interval '40 days'"))
        await connection.execute(text("UPDATE job_queue SET finished_at = now() - interval '40 days'"))
    await engine.dispose()
    await post(client, delivery(text_message("recent")))
    await run_due_jobs()
    before_inbox = await count("webhook_inbox")
    assert before_inbox == 2

    async with standalone_session() as db:
        await set_scope(db, system=True)
        await prune_old_records(db, ClaimedJob(1, "prune_old_records", {}, 1, 6))
        await db.commit()
    assert await count("webhook_inbox") == 1
    # Only finished jobs go; the follow-up email still waiting to send stays
    assert await count("job_queue", "status IN ('done', 'dead') AND finished_at < now() - interval '30 days'") == 0
    assert await count("job_queue", "kind = 'send_follow_up' AND status = 'pending'") == 1
    assert await count("contacts") == 1


async def test_daily_job_is_queued_once_a_day():
    from app.queue import queue_daily_jobs

    await queue_daily_jobs()
    await queue_daily_jobs()
    assert await count("job_queue", "kind = 'prune_old_records'") == 1


# Login limit


async def test_too_many_login_attempts_are_slowed_down(client):
    for _ in range(20):
        await client.post("/api/auth/login", json={"email": "a@acme-demo.com", "password": "wrong"})
    response = await client.post("/api/auth/login", json={"email": "a@acme-demo.com", "password": "wrong"})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


# What's sent to the AI providers


async def _org_for_ai() -> "object":
    import uuid

    org_id = uuid.uuid4()
    engine = owner_engine()
    async with engine.begin() as connection:
        await connection.execute(text("INSERT INTO organizations (id, name) VALUES (:id, 'x')"), {"id": org_id})
    await engine.dispose()
    return org_id


async def test_gemini_request_and_response(monkeypatch):
    seen = {}

    def respond(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": reading().model_dump_json()}]}}],
                "usageMetadata": {"promptTokenCount": 500, "candidatesTokenCount": 50},
            },
        )

    monkeypatch.setattr(ai, "transport", httpx.MockTransport(respond))
    provider = ai.GeminiProvider()
    provider.api_key = "gem-key"
    monkeypatch.setattr(ai, "provider_override", provider)
    result = await ai.read_card(await _org_for_ai(), b"photo", "image/jpeg")

    assert result.full_name == "Asha Rao"
    assert seen["key"] == "gem-key"
    assert ":generateContent" in seen["url"]
    config = seen["body"]["generationConfig"]
    assert config["temperature"] == 0
    assert config["responseMimeType"] == "application/json"
    assert seen["body"]["contents"][0]["parts"][0]["inlineData"]["mimeType"] == "image/jpeg"
    assert await count("ai_calls", "input_tokens = 500 AND provider = 'gemini'") == 1


@pytest.mark.parametrize(("status_code", "error"), [(429, ai.AiError), (503, ai.AiError), (400, ai.AiRefused)])
async def test_gemini_errors_are_sorted(monkeypatch, status_code, error):
    monkeypatch.setattr(ai, "transport", httpx.MockTransport(lambda _: httpx.Response(status_code, json={})))
    monkeypatch.setattr(ai, "provider_override", ai.GeminiProvider())
    with pytest.raises(error):
        await ai.read_card(await _org_for_ai(), b"photo", "image/jpeg")


def _claude_response(content: list[dict], stop_reason: str = "end_turn") -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-haiku-5-5",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 400, "output_tokens": 40},
        },
    )


async def test_claude_request_and_response(monkeypatch):
    seen = {}

    def respond(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        seen["key"] = request.headers["authorization"]
        return _claude_response([{"type": "text", "text": reading().model_dump_json()}])

    monkeypatch.setattr(ai, "claude_transport", httpx2.MockTransport(respond))
    provider = ai.ClaudeProvider()
    provider.api_key = "claude-key"
    monkeypatch.setattr(ai, "provider_override", provider)
    result = await ai.read_card(await _org_for_ai(), b"photo", "image/jpeg")

    assert result.company == "Acme Traders Pvt Ltd"
    assert "claude-key" in seen["key"]
    assert seen["body"]["model"] == "claude-haiku-5-5"
    assert seen["body"]["output_config"]["format"]["type"] == "json_schema"
    assert "temperature" not in seen["body"]
    assert seen["body"]["messages"][0]["content"][0]["source"]["media_type"] == "image/jpeg"
    assert await count("ai_calls", "output_tokens = 40 AND provider = 'anthropic'") == 1


async def test_claude_refusal_isnt_retried(monkeypatch):
    monkeypatch.setattr(
        ai, "claude_transport", httpx2.MockTransport(lambda _: _claude_response([], stop_reason="refusal"))
    )
    provider = ai.ClaudeProvider()
    provider.api_key = "claude-key"
    monkeypatch.setattr(ai, "provider_override", provider)
    with pytest.raises(ai.AiRefused):
        await ai.read_card(await _org_for_ai(), b"photo", "image/jpeg")


async def test_claude_rate_limit_is_retried(monkeypatch):
    limited = httpx2.Response(429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow"}})
    monkeypatch.setattr(ai, "claude_transport", httpx2.MockTransport(lambda _: limited))
    provider = ai.ClaudeProvider()
    provider.api_key = "claude-key"
    monkeypatch.setattr(ai, "provider_override", provider)
    with pytest.raises(ai.AiError) as caught:
        await ai.read_card(await _org_for_ai(), b"photo", "image/jpeg")
    assert not isinstance(caught.value, ai.AiRefused)


def _openrouter(answer: str, usage: dict | None = None) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
            "usage": usage or {"prompt_tokens": 300, "completion_tokens": 30},
        },
    )


async def test_openrouter_request_and_response(monkeypatch):
    seen = {}

    def respond(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        # Wrapped in a code block, as some models do
        return _openrouter(f"```json\n{reading().model_dump_json()}\n```")

    monkeypatch.setattr(ai, "transport", httpx.MockTransport(respond))
    provider = ai.OpenRouterProvider()
    provider.api_key = "or-key"
    monkeypatch.setattr(ai, "provider_override", provider)
    result = await ai.read_card(await _org_for_ai(), b"photo", "image/jpeg")

    assert result.full_name == "Asha Rao"
    assert seen["url"] == ai.OPENROUTER_URL
    assert seen["key"] == "Bearer or-key"
    body = seen["body"]
    assert body["model"] == "deepseek/deepseek-v4.1-flash-1017"
    assert body["temperature"] == 0
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["provider"] == {"require_parameters": True}
    assert body["messages"][0]["role"] == "system"
    image = body["messages"][1]["content"][0]
    assert image["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert await count("ai_calls", "input_tokens = 300 AND provider = 'openrouter'") == 1


async def test_openrouter_voice_notes_use_the_voice_model(monkeypatch):
    seen = {}

    def respond(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        voice = ai.VoiceReading(
            transcript="Bahut interested", summary="Interested.", interest="hot", next_step="", follow_up_date=""
        )
        return _openrouter(voice.model_dump_json())

    monkeypatch.setattr(ai, "transport", httpx.MockTransport(respond))
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", "or-key")
    monkeypatch.setattr(settings, "openrouter_voice_model", "google/gemini-2.5-flash-lite")
    result = await ai.read_voice_note(await _org_for_ai(), b"audio", "audio/ogg; codecs=opus", date(2026, 11, 11))

    assert result.interest == "hot"
    assert seen["body"]["model"] == "google/gemini-2.5-flash-lite"
    assert seen["body"]["messages"][1]["content"][0]["input_audio"]["format"] == "ogg"


@pytest.mark.parametrize(
    ("status_code", "error"), [(402, ai.AiError), (429, ai.AiError), (502, ai.AiError), (400, ai.AiRefused)]
)
async def test_openrouter_errors_are_sorted(monkeypatch, status_code, error):
    monkeypatch.setattr(ai, "transport", httpx.MockTransport(lambda _: httpx.Response(status_code, json={})))
    monkeypatch.setattr(ai, "provider_override", ai.OpenRouterProvider())
    with pytest.raises(error):
        await ai.read_card(await _org_for_ai(), b"photo", "image/jpeg")


async def test_openrouter_error_inside_a_success_is_retried(monkeypatch):
    failed = httpx.Response(200, json={"error": {"code": 503, "message": "provider overloaded"}})
    monkeypatch.setattr(ai, "transport", httpx.MockTransport(lambda _: failed))
    monkeypatch.setattr(ai, "provider_override", ai.OpenRouterProvider())
    with pytest.raises(ai.AiError) as caught:
        await ai.read_card(await _org_for_ai(), b"photo", "image/jpeg")
    assert not isinstance(caught.value, ai.AiRefused)


def test_production_refuses_fake_ai_and_local_storage():
    from pydantic import ValidationError

    from app.config import Settings

    good = {"environment": "production", "jwt_secret": "y" * 40, "public_base_url": "https://x.test"}
    with pytest.raises(ValidationError, match="R2_BUCKET"):
        Settings(**good)
    with pytest.raises(ValidationError, match="fake"):
        Settings(**good, r2_bucket="b", ai_provider="fake")
    with pytest.raises(ValidationError, match="EMAIL_DRY_RUN"):
        Settings(**good, r2_bucket="b", email_dry_run=True)
    assert Settings(**good, r2_bucket="b").retention_days == 30
