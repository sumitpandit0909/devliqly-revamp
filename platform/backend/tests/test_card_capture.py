"""A rep's WhatsApp messages, from photo to saved lead, with scripted AI and a fake Meta."""

import json
import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import text

from app import ai
from app.ai import CardCorrection, CardReading, Completion, RepRequest, VoiceReading
from app.cards import CleanCard, clean_reading, match_name, today_in_india
from app.db import only_this_customer, set_scope, standalone_session
from app.queue import run_due_jobs
from app.whatsapp import client as meta_client
from app.whatsapp.conversation import OVER_QUOTA
from tests.conftest import bearer, owner_engine
from tests.test_whatsapp_inbox import (
    REP_PHONE,
    FakeMeta,
    count,
    delivery,
    make_jobs_due,
    post,
    rep_messages,
    text_message,
)


def reading(**overrides) -> CardReading:
    values = {
        "is_business_card": True,
        "full_name": "Asha Rao",
        "job_title": "Head of Sales",
        "company": "Acme Traders Pvt Ltd",
        "phones": ["+919820012345"],
        "emails": ["asha@acmetraders.com"],
        "website": "https://acmetraders.com/",
        "address": "Mumbai",
        "unsure_fields": [],
        "confidence": 0.95,
    }
    return CardReading(**{**values, **overrides})


class ScriptedAi:
    """Answers each kind of request from a queue, and can be told to fail."""

    name = "scripted"
    model = "scripted-1"
    can_hear = True
    input_usd_per_mtok = 1.0
    output_usd_per_mtok = 2.0

    def __init__(self):
        self.answers: dict[type, list] = {}
        self.calls: list[type] = []

    def script(self, *answers) -> None:
        for answer in answers:
            self.answers.setdefault(type(answer) if not isinstance(answer, Exception) else CardReading, []).append(
                answer
            )

    async def complete(self, instructions, text, media, form) -> Completion:
        self.calls.append(form)
        queue = self.answers.get(form) or []
        answer = queue.pop(0) if queue else None
        if isinstance(answer, Exception):
            raise answer
        if answer is None:
            answer = {
                CardReading: reading(),
                VoiceReading: VoiceReading(
                    transcript="Bahut interested hai",
                    summary="Very interested.",
                    interest="hot",
                    next_step="Call",
                    follow_up_date="",
                ),
                RepRequest: RepRequest(
                    action="help", contact="", note="", interest="", follow_up_date="", next_step=""
                ),
                CardCorrection: CardCorrection(
                    full_name="", job_title="", company="", phone="", email="", website="", address=""
                ),
            }[form]
        return Completion(answer.model_dump_json(), 1000, 100)


@pytest.fixture
def scripted(monkeypatch) -> ScriptedAi:
    fake = ScriptedAi()
    monkeypatch.setattr(ai, "provider_override", fake)
    return fake


@pytest.fixture
def meta(monkeypatch) -> FakeMeta:
    fake = FakeMeta()
    monkeypatch.setattr(meta_client, "transport", httpx.MockTransport(fake))
    return fake


@pytest.fixture
async def rep(client, two_orgs) -> dict:
    response = await client.post(
        "/api/org/members",
        json={"full_name": "Ravi", "phone": REP_PHONE, "role": "rep"},
        headers=bearer(two_orgs["a"]["token"]),
    )
    assert response.status_code == 201, response.text
    return response.json()


def photo_message(*, caption=None, message_id=None, sender=REP_PHONE) -> dict:
    image: dict = {"id": f"media-{uuid.uuid4().hex[:6]}", "mime_type": "image/jpeg"}
    if caption:
        image["caption"] = caption
    return {
        "from": sender.lstrip("+"),
        "id": message_id or f"wamid.{uuid.uuid4().hex}",
        "timestamp": "1793500000",
        "type": "image",
        "image": image,
    }


def button_press(button_id: str) -> dict:
    return {
        "from": REP_PHONE.lstrip("+"),
        "id": f"wamid.{uuid.uuid4().hex}",
        "timestamp": "1793500000",
        "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": button_id, "title": "x"}},
    }


async def send(client, *messages) -> None:
    assert (await post(client, delivery(*messages))).status_code == 200
    await run_due_jobs()


async def leads(client, token) -> list[dict]:
    response = await client.get("/api/org/leads", headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def lead_detail(client, token, lead_id) -> dict:
    return (await client.get(f"/api/org/leads/{lead_id}", headers=bearer(token))).json()


def sent_bodies(meta: FakeMeta) -> list[str]:
    bodies = []
    for call in meta.calls:
        if call.get("type") == "text":
            bodies.append(call["text"]["body"])
        elif call.get("type") == "interactive":
            bodies.append(call["interactive"]["body"]["text"])
    return bodies


def reactions(meta: FakeMeta) -> list[str]:
    return [call["reaction"]["emoji"] for call in meta.calls if call.get("type") == "reaction"]


def button_message(meta: FakeMeta) -> dict:
    return next(call for call in meta.calls if call.get("type") == "interactive")


# Checking what the AI read


def test_good_card_cleans_up():
    card = clean_reading(reading(phones=["098200 12345"], website="HTTPS://AcmeTraders.com/"))
    assert card.phones == ["+919820012345"]
    assert card.website == "acmetraders.com"
    assert card.email == "asha@acmetraders.com"
    assert card.usable and not card.problems


def test_invalid_values_are_dropped_and_flagged():
    card = clean_reading(reading(phones=["12", "+919820012345"], emails=["not-an-email"], website="not a site"))
    assert card.phones == ["+919820012345"]
    assert card.email is None
    assert len(card.problems) == 3
    assert card.usable


def test_no_way_to_reach_them_isnt_usable():
    card = clean_reading(reading(phones=[], emails=[]))
    assert not card.usable
    assert "No phone number or email found" in card.problems


def test_control_characters_are_removed():
    assert clean_reading(reading(full_name="Asha\x00\x1b[31m  Rao\n")).full_name == "Asha [31m Rao"


def test_low_confidence_and_unsure_fields_are_flagged():
    card = clean_reading(reading(confidence=0.3, unsure_fields=["phones"]))
    assert any("confident" in problem for problem in card.problems)
    assert any("Hard to read" in problem for problem in card.problems)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Acme Traders Pvt. Ltd.", "acme traders"), ("ACME TRADERS", "acme traders"), ("Limited", "limited")],
)
def test_company_spellings_match(raw, expected):
    assert match_name(raw) == expected


def test_clean_card_needs_identity():
    assert not CleanCard(phones=["+919820012345"]).usable


# Saving a card


async def test_photo_becomes_a_saved_lead_with_confirmation(client, two_orgs, rep, meta, scripted):
    photo = photo_message()
    await send(client, photo)

    rows = await leads(client, two_orgs["a"]["token"])
    assert len(rows) == 1
    row = rows[0]
    assert (row["full_name"], row["company"], row["phone"]) == ("Asha Rao", "Acme Traders Pvt Ltd", "+919820012345")
    assert (row["owner"], row["status"], row["needs_review"]) == ("Ravi", "new", False)

    confirmation = button_message(meta)
    assert confirmation["context"] == {"message_id": photo["id"]}
    assert "Asha Rao" in confirmation["interactive"]["body"]["text"]
    assert len(confirmation["interactive"]["action"]["buttons"]) == 3
    assert reactions(meta) == ["⏳", "✅"]
    assert scripted.calls == [CardReading]


async def test_photo_is_private_and_readable_only_through_the_api(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    lead = (await leads(client, two_orgs["a"]["token"]))[0]
    card = (await lead_detail(client, two_orgs["a"]["token"], lead["id"]))["cards"][0]

    image = await client.get(f"/api/org/cards/{card['id']}/image", headers=bearer(two_orgs["a"]["token"]))
    assert image.content == b"photo-bytes"
    assert (await client.get(f"/api/org/cards/{card['id']}/image")).status_code == 401
    other = await client.get(f"/api/org/cards/{card['id']}/image", headers=bearer(two_orgs["b"]["token"]))
    assert other.status_code == 404


async def test_meta_retries_make_one_card(client, two_orgs, rep, meta, scripted):
    photo = photo_message()
    for _ in range(3):
        assert (await post(client, delivery(photo))).status_code == 200
    await run_due_jobs()
    await send(client, photo)
    assert await count("business_cards") == 1
    assert await count("contacts") == 1
    assert len(scripted.calls) == 1


async def test_same_person_twice_is_one_contact_and_one_lead(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    await send(client, photo_message())
    assert await count("contacts") == 1
    assert await count("leads") == 1
    assert "Already saved" in sent_bodies(meta)[-1]


async def test_rescan_only_fills_blanks(client, two_orgs, rep, meta, scripted):
    scripted.script(reading(job_title=""), reading(job_title="CEO", full_name="A. Rao"))
    await send(client, photo_message())
    await send(client, photo_message())
    row = (await leads(client, two_orgs["a"]["token"]))[0]
    assert row["job_title"] == "CEO"
    assert row["full_name"] == "Asha Rao"


async def test_companies_are_shared_across_spellings(client, two_orgs, rep, meta, scripted):
    scripted.script(
        reading(company="Acme Traders Pvt Ltd", phones=["+919820012345"], emails=[]),
        reading(company="ACME TRADERS", phones=["+919820012346"], emails=[], full_name="Vik"),
    )
    await send(client, photo_message())
    await send(client, photo_message())
    assert await count("contacts") == 2
    assert await count("companies") == 1


async def test_five_cards_at_once_all_save_with_their_own_confirmation(client, two_orgs, rep, meta, scripted):
    photos = [photo_message() for _ in range(5)]
    scripted.script(
        *[
            reading(full_name=f"Person {n}", phones=[f"+91982001234{n}"], emails=[f"p{n}@acmetraders.com"])
            for n in range(5)
        ]
    )
    await send(client, *photos)
    assert len(await leads(client, two_orgs["a"]["token"])) == 5
    confirmations = [call for call in meta.calls if call.get("type") == "interactive"]
    assert {call["context"]["message_id"] for call in confirmations} == {photo["id"] for photo in photos}


async def test_not_a_card_is_rejected(client, two_orgs, rep, meta, scripted):
    scripted.script(reading(is_business_card=False))
    await send(client, photo_message())
    assert await count("contacts") == 0
    assert await count("business_cards", "status = 'rejected'") == 1
    assert "doesn't look like a business card" in sent_bodies(meta)[-1]


async def test_low_confidence_card_saves_but_is_flagged(client, two_orgs, rep, meta, scripted):
    scripted.script(reading(confidence=0.2))
    await send(client, photo_message())
    assert (await leads(client, two_orgs["a"]["token"]))[0]["needs_review"] is True
    assert "Please check" in sent_bodies(meta)[-1]


async def test_ai_answer_that_doesnt_fit_is_retried(client, two_orgs, rep, meta, monkeypatch):
    class Garbled(ScriptedAi):
        async def complete(self, instructions, text, media, form):
            self.calls.append(form)
            if len(self.calls) == 1:
                return Completion('{"oops": true}')
            return Completion(reading().model_dump_json())

    fake = Garbled()
    monkeypatch.setattr(ai, "provider_override", fake)
    await send(client, photo_message())
    assert await count("contacts") == 0
    await make_jobs_due()
    await run_due_jobs()
    assert await count("contacts") == 1


async def test_ai_keeps_failing_then_goes_to_review(client, two_orgs, rep, meta, scripted):
    scripted.script(*[ai.AiError("down") for _ in range(4)])
    await send(client, photo_message())
    for _ in range(3):
        assert await count("business_cards", "status = 'received'") == 1
        await make_jobs_due()
        await run_due_jobs()
    assert await count("business_cards", "status = 'review'") == 1
    assert await count("job_queue", "status = 'dead'") == 0
    assert "review queue" in sent_bodies(meta)[-1]


async def test_with_no_ai_set_up_photos_wait_for_review(client, two_orgs, rep, meta):
    await send(client, photo_message())
    assert await count("business_cards", "status = 'review' AND front_key IS NOT NULL") == 1


async def test_ai_cost_is_recorded_even_when_a_call_fails(client, two_orgs, rep, meta, scripted):
    scripted.script(ai.AiError("down"))
    await send(client, photo_message())
    await make_jobs_due()
    await run_due_jobs()
    assert await count("ai_calls") == 2
    assert await count("ai_calls", "succeeded AND cost_usd = 0.0012") == 1


async def test_failed_download_tells_the_rep(client, two_orgs, rep, meta, scripted):
    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(404, json={"error": {"code": 100}})
        return meta(request)

    meta_client.transport = httpx.MockTransport(respond)
    await send(client, photo_message())
    assert await count("business_cards", "status = 'failed'") == 1
    assert "download" in sent_bodies(meta)[-1]
    assert scripted.calls == []


# Plan limits


async def test_quota_blocks_new_cards_before_spending_on_ai(client, two_orgs, rep, meta, scripted, operator_token):
    response = await client.patch(
        f"/api/operator/organizations/{two_orgs['a']['id']}",
        json={"monthly_card_limit": 1},
        headers=bearer(operator_token),
    )
    assert response.status_code == 200, response.text
    await send(client, photo_message())
    await send(client, photo_message())
    assert await count("business_cards") == 1
    assert len(scripted.calls) == 1
    assert sent_bodies(meta)[-1] == OVER_QUOTA


async def test_parallel_cards_cant_pass_the_quota(client, two_orgs, rep, meta, scripted, operator_token):
    await client.patch(
        f"/api/operator/organizations/{two_orgs['a']['id']}",
        json={"monthly_card_limit": 2},
        headers=bearer(operator_token),
    )
    scripted.script(*[reading(phones=[f"+91982001234{n}"], emails=[f"p{n}@acmetraders.com"]) for n in range(4)])
    await send(client, *[photo_message() for _ in range(4)])
    assert await count("leads") == 2
    assert await count("business_cards", "status = 'over_quota'") == 2
    assert await count("usage_months", "cards_saved = 2") == 1


async def test_seat_limit(client, two_orgs, operator_token):
    await client.patch(
        f"/api/operator/organizations/{two_orgs['a']['id']}", json={"seat_limit": 1}, headers=bearer(operator_token)
    )
    response = await client.post(
        "/api/org/members",
        json={"full_name": "Ravi", "phone": REP_PHONE, "role": "rep"},
        headers=bearer(two_orgs["a"]["token"]),
    )
    assert response.status_code == 409


# Buttons, notes and corrections


async def _saved_card_button(meta: FakeMeta, action: str) -> str:
    buttons = button_message(meta)["interactive"]["action"]["buttons"]
    return next(b["reply"]["id"] for b in buttons if b["reply"]["id"].startswith(action))


async def test_note_button_then_text(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    await send(client, button_press(await _saved_card_button(meta, "note")))
    await send(client, text_message("Wants 200 units"))

    lead = (await leads(client, two_orgs["a"]["token"]))[0]
    detail = await lead_detail(client, two_orgs["a"]["token"], lead["id"])
    assert [a["body"] for a in detail["activities"] if a["kind"] == "note"] == ["Wants 200 units"]
    assert RepRequest not in scripted.calls


async def test_replying_to_a_confirmation_adds_a_note_to_that_card(client, two_orgs, rep, meta, scripted):
    scripted.script(
        reading(full_name="First", phones=["+919820012341"], emails=[]),
        reading(full_name="Second", phones=["+919820012342"], emails=[]),
    )
    await send(client, photo_message())
    await send(client, photo_message())
    confirmations = [m for m in await rep_messages(client, two_orgs["a"]["token"]) if m["kind"] == "buttons"]
    assert len(confirmations) == 2
    engine = owner_engine()
    async with engine.connect() as connection:
        first = (
            await connection.execute(
                text(
                    "SELECT provider_message_id FROM conversation_messages WHERE kind = 'buttons' "
                    "AND body LIKE '%First%'"
                )
            )
        ).scalar_one()
    await engine.dispose()

    await send(client, text_message("Met at the stall", context={"id": first}))
    rows = await leads(client, two_orgs["a"]["token"])
    first_lead = next(r for r in rows if r["full_name"] == "First")
    second_lead = next(r for r in rows if r["full_name"] == "Second")
    notes = [
        a["body"]
        for a in (await lead_detail(client, two_orgs["a"]["token"], first_lead["id"]))["activities"]
        if a["kind"] == "note"
    ]
    assert notes == ["Met at the stall"]
    other = await lead_detail(client, two_orgs["a"]["token"], second_lead["id"])
    assert not [a for a in other["activities"] if a["kind"] == "note"]


async def test_caption_becomes_a_note(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message(caption="Very keen"))
    lead = (await leads(client, two_orgs["a"]["token"]))[0]
    detail = await lead_detail(client, two_orgs["a"]["token"], lead["id"])
    assert "Very keen" in [a["body"] for a in detail["activities"]]


async def test_back_of_card_fills_gaps(client, two_orgs, rep, meta, scripted):
    scripted.script(reading(emails=[]), reading(full_name="", emails=["asha@acmetraders.com"], phones=[]))
    await send(client, photo_message())
    await send(client, button_press(await _saved_card_button(meta, "back")))
    await send(client, photo_message())

    assert await count("business_cards") == 1
    assert await count("business_cards", "back_key IS NOT NULL") == 1
    row = (await leads(client, two_orgs["a"]["token"]))[0]
    assert row["email"] == "asha@acmetraders.com"
    assert row["full_name"] == "Asha Rao"


async def test_back_supplies_what_review_was_waiting_for(client, two_orgs, rep, meta, scripted):
    scripted.script(reading(phones=[], emails=[]), reading(phones=["+919820012345"]))
    await send(client, photo_message())
    assert await count("business_cards", "status = 'review'") == 1
    engine = owner_engine()
    async with engine.connect() as connection:
        card_id = (await connection.execute(text("SELECT id FROM business_cards"))).scalar_one()
    await engine.dispose()
    await send(client, button_press(f"back:{card_id}"))
    await send(client, photo_message())
    assert await count("business_cards", "status = 'saved'") == 1
    assert await count("contacts") == 1


async def test_correction_overwrites_and_checks_values(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    await send(client, button_press(await _saved_card_button(meta, "fix")))
    scripted.script(
        CardCorrection(
            full_name="", job_title="CEO", company="", phone="98200 99999", email="bad", website="", address=""
        )
    )
    await send(client, text_message("title is CEO and phone 98200 99999"))

    row = (await leads(client, two_orgs["a"]["token"]))[0]
    assert row["job_title"] == "CEO"
    assert row["phone"] == "+919820099999"
    assert row["email"] == "asha@acmetraders.com"
    assert row["other_phones"] == ["+919820012345"]
    assert "doesn't look like a valid email" in sent_bodies(meta)[-1]


async def test_correction_cant_take_another_contacts_number(client, two_orgs, rep, meta, scripted):
    scripted.script(
        reading(full_name="First", phones=["+919820012341"], emails=[]),
        reading(full_name="Second", phones=["+919820012342"], emails=[]),
    )
    await send(client, photo_message())
    await send(client, photo_message())
    second = [call for call in meta.calls if call.get("type") == "interactive"][1]
    fix = next(
        b["reply"]["id"] for b in second["interactive"]["action"]["buttons"] if b["reply"]["id"].startswith("fix")
    )
    await send(client, button_press(fix))
    scripted.script(
        CardCorrection(full_name="", job_title="", company="", phone="+919820012341", email="", website="", address="")
    )
    await send(client, text_message("phone is 9820012341"))
    assert await count("job_queue", "status = 'dead'") == 0
    assert "already belongs" in sent_bodies(meta)[-1]


async def test_buttons_for_someone_elses_card_do_nothing(client, two_orgs, rep, meta, scripted):
    await send(client, button_press(f"note:{uuid.uuid4()}"))
    assert "isn't available" in sent_bodies(meta)[-1]


async def test_waiting_state_expires(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    await send(client, button_press(await _saved_card_button(meta, "note")))
    engine = owner_engine()
    async with engine.begin() as connection:
        await connection.execute(text("UPDATE rep_conversations SET state_expires_at = now() - interval '1 minute'"))
    await engine.dispose()
    await send(client, text_message("How many cards today?"))
    assert await count("lead_activities", "kind = 'note'") == 0
    assert RepRequest in scripted.calls


# Voice notes


def voice_message(**extra) -> dict:
    return {
        "from": REP_PHONE.lstrip("+"),
        "id": f"wamid.{uuid.uuid4().hex}",
        "timestamp": "1793500000",
        "type": "audio",
        "audio": {"id": "voice-1", "mime_type": "audio/ogg; codecs=opus"},
        **extra,
    }


async def test_voice_note_right_after_a_card_goes_on_that_card(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    follow_up = (today_in_india() + timedelta(days=3)).isoformat()
    scripted.script(
        VoiceReading(
            transcript="Bahut interested hai, call karna",
            summary="Very interested. Call them.",
            interest="hot",
            next_step="Call",
            follow_up_date=follow_up,
        )
    )
    await send(client, voice_message())
    row = (await leads(client, two_orgs["a"]["token"]))[0]
    assert (row["interest"], row["next_step"], row["follow_up_on"]) == ("hot", "Call", follow_up)
    detail = await lead_detail(client, two_orgs["a"]["token"], row["id"])
    voice = next(a for a in detail["activities"] if a["kind"] == "voice_note")
    assert voice["details"]["transcript"] == "Bahut interested hai, call karna"


async def test_voice_note_with_a_nonsense_date_keeps_the_rest(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    scripted.script(
        VoiceReading(transcript="x", summary="y", interest="warm", next_step="", follow_up_date="1999-01-01")
    )
    await send(client, voice_message())
    row = (await leads(client, two_orgs["a"]["token"]))[0]
    assert (row["interest"], row["follow_up_on"]) == ("warm", None)


async def test_voice_needs_a_provider_that_can_hear(client, two_orgs, rep, meta):
    await send(client, voice_message())
    assert "aren't set up" in sent_bodies(meta)[-1]


# The limited assistant


async def test_assistant_adds_a_note_to_the_reps_own_contact(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    scripted.script(
        RepRequest(
            action="add_note", contact="Asha", note="Sent brochure", interest="", follow_up_date="", next_step=""
        )
    )
    await send(client, text_message("note for asha: sent brochure"))
    assert await count("lead_activities", "kind = 'note' AND body = 'Sent brochure'") == 1


async def test_assistant_finds_details(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    scripted.script(
        RepRequest(action="find_contact", contact="acme", note="", interest="", follow_up_date="", next_step="")
    )
    await send(client, text_message("what's the number for acme"))
    assert "+919820012345" in sent_bodies(meta)[-1]


async def test_assistant_treats_wildcards_literally(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    scripted.script(
        RepRequest(action="find_contact", contact="%", note="", interest="", follow_up_date="", next_step="")
    )
    await send(client, text_message("find %"))
    assert "couldn't find" in sent_bodies(meta)[-1]


async def test_assistant_cant_reach_another_reps_contacts(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    other = "+919876543299"
    response = await client.post(
        "/api/org/members",
        json={"full_name": "Sana", "phone": other, "role": "rep"},
        headers=bearer(two_orgs["a"]["token"]),
    )
    assert response.status_code == 201
    scripted.script(
        RepRequest(action="find_contact", contact="Asha", note="", interest="", follow_up_date="", next_step="")
    )
    await send(client, text_message("Asha's number?", sender=other))
    assert "couldn't find" in sent_bodies(meta)[-1]


async def test_assistant_asks_when_a_name_is_ambiguous(client, two_orgs, rep, meta, scripted):
    scripted.script(
        reading(full_name="Asha Rao", phones=["+919820012341"], emails=[]),
        reading(full_name="Asha Iyer", phones=["+919820012342"], emails=[]),
    )
    await send(client, photo_message())
    await send(client, photo_message())
    scripted.script(
        RepRequest(action="set_interest", contact="Asha", note="", interest="hot", follow_up_date="", next_step="")
    )
    await send(client, text_message("asha is hot"))
    assert "be more specific" in sent_bodies(meta)[-1]
    assert await count("leads", "interest IS NOT NULL") == 0


async def test_assistant_counts(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    scripted.script(RepRequest(action="my_numbers", contact="", note="", interest="", follow_up_date="", next_step=""))
    await send(client, text_message("how many today"))
    assert "1 today and 1 in total" in sent_bodies(meta)[-1]


async def test_only_this_customer_makes_the_database_refuse_others():
    a, b = uuid.uuid4(), uuid.uuid4()
    engine = owner_engine()
    async with engine.begin() as connection:
        for org_id in (a, b):
            await connection.execute(text("INSERT INTO organizations (id, name) VALUES (:id, 'x')"), {"id": org_id})
        await connection.execute(
            text("INSERT INTO companies (id, organization_id, name, match_name) VALUES (:id, :org, 'B Co', 'b co')"),
            {"id": uuid.uuid4(), "org": b},
        )
    await engine.dispose()

    async with standalone_session() as db:
        await set_scope(db, system=True)
        assert (await db.execute(text("SELECT count(*) FROM companies"))).scalar_one() == 1
        async with only_this_customer(db, a):
            assert (await db.execute(text("SELECT count(*) FROM companies"))).scalar_one() == 0
        assert (await db.execute(text("SELECT count(*) FROM companies"))).scalar_one() == 1


# Events


async def _make_event(client, token, name, **dates) -> dict:
    response = await client.post("/api/org/events", json={"name": name, **dates}, headers=bearer(token))
    assert response.status_code == 201, response.text
    return response.json()


async def test_single_running_event_tags_cards(client, two_orgs, rep, meta, scripted):
    await _make_event(client, two_orgs["a"]["token"], "Auto Expo")
    await send(client, photo_message())
    assert (await leads(client, two_orgs["a"]["token"]))[0]["event"] == "Auto Expo"
    assert "Auto Expo" in sent_bodies(meta)[-1]


async def test_finished_events_are_ignored(client, two_orgs, rep, meta, scripted):
    yesterday = (today_in_india() - timedelta(days=1)).isoformat()
    await _make_event(client, two_orgs["a"]["token"], "Old Expo", starts_on=yesterday, ends_on=yesterday)
    await send(client, photo_message())
    assert (await leads(client, two_orgs["a"]["token"]))[0]["event"] is None


async def test_rep_chooses_between_events_and_earlier_cards_get_tagged(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    await _make_event(client, token, "Auto Expo")
    await _make_event(client, token, "Pharma Expo")
    await send(client, photo_message())
    assert (await leads(client, token))[0]["event"] is None
    assert "Which event is this for" in sent_bodies(meta)[-1]

    await send(client, text_message("event"))
    listing = sent_bodies(meta)[-1]
    number = next(line.split(".")[0] for line in listing.splitlines() if "Pharma Expo" in line)
    await send(client, text_message(number))

    assert (await leads(client, token))[0]["event"] == "Pharma Expo"
    scripted.script(reading(full_name="Next", phones=["+919820012399"], emails=[]))
    await send(client, photo_message())
    assert {row["event"] for row in await leads(client, token)} == {"Pharma Expo"}


async def test_same_person_at_two_events_is_two_leads(client, two_orgs, rep, meta, scripted):
    token = two_orgs["a"]["token"]
    event = await _make_event(client, token, "Auto Expo")
    await send(client, photo_message())
    await client.patch(f"/api/org/events/{event['id']}", json={"is_active": False}, headers=bearer(token))
    await _make_event(client, token, "Pharma Expo")
    await send(client, photo_message())
    assert await count("contacts") == 1
    assert await count("leads") == 2


# Customers stay separate


async def test_one_person_can_be_a_contact_at_two_customers(client, two_orgs, rep, meta, scripted):
    await send(client, photo_message())
    other = "+919876543288"
    await client.post(
        "/api/org/members",
        json={"full_name": "Bina", "phone": other, "role": "rep"},
        headers=bearer(two_orgs["b"]["token"]),
    )
    await send(client, photo_message(sender=other))
    assert await count("contacts") == 2
    assert len(await leads(client, two_orgs["a"]["token"])) == 1
    assert len(await leads(client, two_orgs["b"]["token"])) == 1


@pytest.mark.parametrize(
    "table",
    ["companies", "contacts", "leads", "business_cards", "lead_activities", "usage_months", "ai_calls"],
)
async def test_crm_tables_show_nothing_without_a_scope(client, two_orgs, rep, meta, scripted, table):
    await send(client, photo_message())
    assert await count(table) > 0
    async with standalone_session() as db:
        assert (await db.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one() == 0  # noqa: S608


def test_provider_requests_are_stable():
    # Both providers accept a plain object schema with every field required
    schema = ai._schema(CardReading)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert json.dumps(schema).count('"title"') == 0
