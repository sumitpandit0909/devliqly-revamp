import pytest

from tests.conftest import activate, bearer


async def _add(client, token: str, **body):
    return await client.post("/api/org/members", json=body, headers=bearer(token))


async def test_rep_needs_only_a_phone_and_it_is_normalized(client, two_orgs):
    response = await _add(client, two_orgs["a"]["token"], full_name="Ravi", phone="098765 43210", role="rep")
    assert response.status_code == 201, response.text
    assert response.json()["phone"] == "+919876543210"
    assert response.json()["setup_url"] is None


@pytest.mark.parametrize("phone", ["12345", "not a phone"])
async def test_invalid_phone_is_rejected(client, two_orgs, phone):
    response = await _add(client, two_orgs["a"]["token"], full_name="Ravi", phone=phone, role="rep")
    assert response.status_code == 422


async def test_role_contact_requirements(client, two_orgs):
    token = two_orgs["a"]["token"]
    assert (await _add(client, token, full_name="R", email="r@acme-demo.com", role="rep")).status_code == 422
    assert (await _add(client, token, full_name="M", phone="+919876543211", role="manager")).status_code == 422
    assert (await _add(client, token, full_name="X", role="rep")).status_code == 422


async def test_duplicate_phone_or_email_conflicts_without_breaking_the_request(client, two_orgs):
    await _add(client, two_orgs["a"]["token"], full_name="Ravi", phone="+919876543210", role="rep")
    again = await _add(client, two_orgs["b"]["token"], full_name="Other", phone="+919876543210", role="rep")
    assert again.status_code == 409


async def test_rep_cannot_manage_but_can_read_events(client, two_orgs):
    owner = two_orgs["a"]["token"]
    created = await _add(client, owner, full_name="Ravi", phone="+919876543212", email="ravi@acme-demo.com", role="rep")
    rep_token = await activate(client, created.json()["setup_url"], "ravi@acme-demo.com")

    assert (await client.get("/api/org/events", headers=bearer(rep_token))).status_code == 200
    assert (await client.post("/api/org/events", json={"name": "X"}, headers=bearer(rep_token))).status_code == 403
    assert (await _add(client, rep_token, full_name="N", phone="+919876543213", role="rep")).status_code == 403


async def test_manager_can_add_reps_but_not_managers_or_change_owners(client, two_orgs):
    owner = two_orgs["a"]["token"]
    created = await _add(client, owner, full_name="Maya", email="maya@acme-demo.com", role="manager")
    manager = await activate(client, created.json()["setup_url"], "maya@acme-demo.com")

    assert (await _add(client, manager, full_name="R", phone="+919876543214", role="rep")).status_code == 201
    assert (await _add(client, manager, full_name="M2", email="m2@acme-demo.com", role="manager")).status_code == 403

    members = (await client.get("/api/org/members", headers=bearer(owner))).json()
    owner_row = next(m for m in members if m["role"] == "owner")
    rep_row = next(m for m in members if m["role"] == "rep")
    promote = await client.patch(f"/api/org/members/{rep_row['id']}", json={"role": "owner"}, headers=bearer(manager))
    assert promote.status_code == 403
    demote = await client.patch(f"/api/org/members/{owner_row['id']}", json={"role": "rep"}, headers=bearer(manager))
    assert demote.status_code == 403


async def test_last_owner_cannot_be_removed(client, two_orgs):
    token = two_orgs["a"]["token"]
    members = (await client.get("/api/org/members", headers=bearer(token))).json()
    owner_id = members[0]["id"]
    assert (
        await client.patch(f"/api/org/members/{owner_id}", json={"is_active": False}, headers=bearer(token))
    ).status_code == 409
    assert (
        await client.patch(f"/api/org/members/{owner_id}", json={"role": "rep"}, headers=bearer(token))
    ).status_code == 409


async def test_deactivated_member_loses_access_immediately(client, two_orgs):
    owner = two_orgs["a"]["token"]
    created = await _add(client, owner, full_name="Maya", email="maya@acme-demo.com", role="manager")
    manager = await activate(client, created.json()["setup_url"], "maya@acme-demo.com")
    assert (await client.get("/api/org/events", headers=bearer(manager))).status_code == 200

    response = await client.patch(
        f"/api/org/members/{created.json()['id']}", json={"is_active": False}, headers=bearer(owner)
    )
    assert response.status_code == 200
    assert (await client.get("/api/org/events", headers=bearer(manager))).status_code == 403


async def test_event_lifecycle_and_validation(client, two_orgs):
    headers = bearer(two_orgs["a"]["token"])
    bad = await client.post(
        "/api/org/events", json={"name": "E", "starts_on": "2026-12-05", "ends_on": "2026-12-01"}, headers=headers
    )
    assert bad.status_code == 422
    created = await client.post(
        "/api/org/events",
        json={"name": "Auto Expo", "venue": "Pragati Maidan", "starts_on": "2026-12-01", "ends_on": "2026-12-05"},
        headers=headers,
    )
    assert created.status_code == 201
    event_id = created.json()["id"]
    assert (await client.post("/api/org/events", json={"name": "Auto Expo"}, headers=headers)).status_code == 409
    updated = await client.patch(f"/api/org/events/{event_id}", json={"venue": "Bharat Mandapam"}, headers=headers)
    assert updated.json()["venue"] == "Bharat Mandapam"
    out_of_order = await client.patch(f"/api/org/events/{event_id}", json={"ends_on": "2026-11-01"}, headers=headers)
    assert out_of_order.status_code == 422
