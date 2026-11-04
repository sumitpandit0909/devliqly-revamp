import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import text

from app.config import get_settings
from tests.conftest import PASSWORD, activate, bearer, make_org, owner_engine

EMAIL = "owner@acme-demo.com"


async def test_me_shows_user_and_organization(client, operator_token):
    org_id, token = await make_org(client, operator_token, "Acme", EMAIL)
    body = (await client.get("/api/me", headers=bearer(token))).json()
    assert body["email"] == EMAIL
    assert body["is_operator"] is False
    assert body["memberships"] == [{"organization": {"id": org_id, "name": "Acme", "is_active": True}, "role": "owner"}]


async def test_requests_without_valid_token_are_rejected(client):
    assert (await client.get("/api/me")).status_code == 401
    assert (await client.get("/api/me", headers=bearer("garbage"))).status_code == 401
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "iss": "devliqly-platform", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "x" * 40,
        algorithm="HS256",
    )
    assert (await client.get("/api/me", headers=bearer(forged))).status_code == 401
    expired = jwt.encode(
        {"sub": str(uuid.uuid4()), "iss": "devliqly-platform", "exp": datetime.now(UTC) - timedelta(minutes=1)},
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    assert (await client.get("/api/me", headers=bearer(expired))).status_code == 401


async def test_wrong_password_and_unknown_email_look_identical(client, operator_token):
    await make_org(client, operator_token, "Acme", EMAIL)
    wrong = await client.post("/api/auth/login", json={"email": EMAIL, "password": "nope-nope-nope"})
    unknown = await client.post("/api/auth/login", json={"email": "no@nobody-demo.com", "password": "nope-nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_account_locks_after_repeated_failures(client, operator_token):
    await make_org(client, operator_token, "Acme", EMAIL)
    limit = get_settings().max_failed_logins
    for _ in range(limit):
        response = await client.post("/api/auth/login", json={"email": EMAIL, "password": "wrong-wrong-wrong"})
        assert response.status_code == 401
    locked = await client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert locked.status_code == 429


async def test_setup_link_works_once_and_rejects_short_passwords(client, operator_token):
    response = await client.post(
        "/api/operator/organizations",
        json={"name": "Acme", "owner": {"full_name": "O", "email": EMAIL}},
        headers=bearer(operator_token),
    )
    token = response.json()["owner_setup_url"].split("#setup=")[1]
    short = await client.post("/api/auth/set-password", json={"token": token, "password": "short"})
    assert short.status_code == 422
    assert (await client.post("/api/auth/set-password", json={"token": token, "password": PASSWORD})).status_code == 204
    again = await client.post("/api/auth/set-password", json={"token": token, "password": PASSWORD})
    assert again.status_code == 400


async def test_tokens_are_stored_hashed(client, operator_token):
    response = await client.post(
        "/api/operator/organizations",
        json={"name": "Acme", "owner": {"full_name": "O", "email": EMAIL}},
        headers=bearer(operator_token),
    )
    token = response.json()["owner_setup_url"].split("#setup=")[1]
    await activate(client, response.json()["owner_setup_url"], EMAIL)
    refresh_cookie = client.cookies.get("platform_refresh")
    engine = owner_engine()
    async with engine.connect() as connection:
        setup_hashes = (await connection.execute(text("SELECT token_hash FROM password_setup_tokens"))).scalars().all()
        session_hashes = (await connection.execute(text("SELECT token_hash FROM login_sessions"))).scalars().all()
        password_hash = (
            await connection.execute(text("SELECT password_hash FROM users WHERE email = :e"), {"e": EMAIL})
        ).scalar_one()
    await engine.dispose()
    assert token not in setup_hashes
    assert refresh_cookie not in session_hashes
    assert password_hash.startswith("$argon2")


async def test_refresh_rotates_and_new_token_works(client, operator_token):
    await make_org(client, operator_token, "Acme", EMAIL)
    first = client.cookies.get("platform_refresh")
    response = await client.post("/api/auth/refresh")
    assert response.status_code == 200
    assert client.cookies.get("platform_refresh") != first
    assert (await client.get("/api/me", headers=bearer(response.json()["access_token"]))).status_code == 200


async def test_replayed_refresh_token_ends_the_session_chain(client, operator_token):
    await make_org(client, operator_token, "Acme", EMAIL)
    stolen = client.cookies.get("platform_refresh")
    assert (await client.post("/api/auth/refresh")).status_code == 200
    latest = client.cookies.get("platform_refresh")

    client.cookies.clear()
    client.cookies.set("platform_refresh", stolen, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401

    client.cookies.clear()
    client.cookies.set("platform_refresh", latest, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_logout_ends_the_session(client, operator_token):
    await make_org(client, operator_token, "Acme", EMAIL)
    cookie = client.cookies.get("platform_refresh")
    assert (await client.post("/api/auth/logout")).status_code == 204
    client.cookies.clear()
    client.cookies.set("platform_refresh", cookie, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_refresh_cookie_is_locked_down(client, operator_token):
    await make_org(client, operator_token, "Acme", EMAIL)
    response = await client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/auth" in cookie


async def test_operator_routes_need_an_operator(client, operator_token):
    _, owner_token = await make_org(client, operator_token, "Acme", EMAIL)
    assert (await client.get("/api/operator/organizations", headers=bearer(owner_token))).status_code == 403
    assert (await client.get("/api/operator/organizations")).status_code == 401
    listed = await client.get("/api/operator/organizations", headers=bearer(operator_token))
    assert [o["name"] for o in listed.json()] == ["Acme"]
