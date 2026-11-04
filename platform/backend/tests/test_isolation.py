"""One customer must never reach another's data, through the API or at the database level."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import get_engine, set_scope, standalone_session
from app.models import ExpoEvent
from tests.conftest import bearer, owner_engine


async def _event(client, token: str, name: str = "Auto Expo") -> dict:
    response = await client.post("/api/org/events", json={"name": name}, headers=bearer(token))
    assert response.status_code == 201, response.text
    return response.json()


async def test_api_hides_other_customers_events(client, two_orgs):
    event = await _event(client, two_orgs["a"]["token"])
    b = bearer(two_orgs["b"]["token"])

    assert (await client.get("/api/org/events", headers=b)).json() == []
    assert (await client.get(f"/api/org/events/{event['id']}", headers=b)).status_code == 404
    assert (await client.patch(f"/api/org/events/{event['id']}", json={"name": "Hacked"}, headers=b)).status_code == 404

    own = await client.get(f"/api/org/events/{event['id']}", headers=bearer(two_orgs["a"]["token"]))
    assert own.json()["name"] == "Auto Expo"


async def test_cannot_claim_another_organization_by_header(client, two_orgs):
    headers = {**bearer(two_orgs["b"]["token"]), "X-Organization-Id": two_orgs["a"]["id"]}
    assert (await client.get("/api/org/events", headers=headers)).status_code == 403
    assert (await client.get("/api/org/members", headers=headers)).status_code == 403


async def test_member_lists_are_separate(client, two_orgs):
    members = (await client.get("/api/org/members", headers=bearer(two_orgs["b"]["token"]))).json()
    assert [m["email"] for m in members] == ["owner@birla-demo.com"]


async def test_cannot_change_another_customers_member(client, two_orgs):
    a_members = (await client.get("/api/org/members", headers=bearer(two_orgs["a"]["token"]))).json()
    response = await client.patch(
        f"/api/org/members/{a_members[0]['id']}",
        json={"is_active": False},
        headers=bearer(two_orgs["b"]["token"]),
    )
    assert response.status_code == 404


async def test_same_event_name_allowed_for_different_customers(client, two_orgs):
    await _event(client, two_orgs["a"]["token"], "Same Name")
    await _event(client, two_orgs["b"]["token"], "Same Name")


async def test_app_role_cannot_bypass_row_security():
    async with get_engine().connect() as connection:
        row = (
            await connection.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"))
        ).one()
    assert tuple(row) == (False, False)


@pytest.mark.parametrize("table", ["organizations", "users", "memberships", "expo_events"])
async def test_no_scope_sees_nothing(client, two_orgs, table):
    await _event(client, two_orgs["a"]["token"])
    async with standalone_session() as db:
        assert (await db.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one() == 0  # noqa: S608


async def test_scope_shows_only_that_customer():
    a, b = uuid.uuid4(), uuid.uuid4()
    engine = owner_engine()
    async with engine.begin() as connection:
        for org_id, name in ((a, "A"), (b, "B")):
            await connection.execute(
                text("INSERT INTO organizations (id, name) VALUES (:id, :name)"), {"id": org_id, "name": name}
            )
            # The owner role is also subject to FORCE ROW LEVEL SECURITY unless superuser, as it is here
            await connection.execute(
                text("INSERT INTO expo_events (id, organization_id, name) VALUES (:i, :o, :n)"),
                {"i": uuid.uuid4(), "o": org_id, "n": f"{name} event"},
            )
    await engine.dispose()

    async with standalone_session() as db:
        await set_scope(db, org_id=a)
        names = (await db.execute(text("SELECT name FROM expo_events"))).scalars().all()
    assert names == ["A event"]


async def test_cannot_write_into_another_customer():
    a, b = uuid.uuid4(), uuid.uuid4()
    engine = owner_engine()
    async with engine.begin() as connection:
        for org_id in (a, b):
            await connection.execute(text("INSERT INTO organizations (id, name) VALUES (:id, 'x')"), {"id": org_id})
    await engine.dispose()

    with pytest.raises(DBAPIError, match="row-level security"):
        async with standalone_session() as db:
            await set_scope(db, org_id=a)
            db.add(ExpoEvent(organization_id=b, name="Sneaky"))
            await db.flush()


async def test_scope_does_not_survive_the_transaction():
    org_id = uuid.uuid4()
    async with standalone_session() as db:
        await set_scope(db, org_id=org_id)
        await db.commit()
    for _ in range(3):  # Pooled connections get reused
        async with standalone_session() as db:
            value = (await db.execute(text("SELECT app_current_org()"))).scalar_one()
            assert value is None


async def test_every_customer_table_is_protected():
    """Fails when a future table with organization_id is added without row-level security."""
    engine = owner_engine()
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                           (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid)
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'organization_id' AND NOT a.attisdropped
                    WHERE n.nspname = 'public' AND c.relkind = 'r'
                    """
                )
            )
        ).all()
    await engine.dispose()
    assert rows
    for name, enabled, forced, policies in rows:
        assert enabled and forced and policies > 0, f"{name} is missing row-level security"
