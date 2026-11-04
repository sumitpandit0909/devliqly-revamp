import asyncio
import os
import subprocess
import sys
from pathlib import Path

BASE = "postgresql://{user}@127.0.0.1:55432/platform_test"
OWNER_URL = os.environ.get("TEST_OWNER_DATABASE_URL", BASE.format(user="postgres"))
APP_URL = os.environ.get("TEST_APP_DATABASE_URL", BASE.format(user="platform_app"))

os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL=APP_URL,
    MIGRATION_DATABASE_URL=OWNER_URL,
    JWT_SECRET="test-secret-test-secret-test-secret-test",
    PUBLIC_BASE_URL="http://test",
    WHATSAPP_LINE_ID="100200300",
    WHATSAPP_ACCESS_TOKEN="test-token",
    WHATSAPP_APP_SECRET="test-app-secret",
    WHATSAPP_VERIFY_TOKEN="test-verify-token",
    WHATSAPP_DRY_RUN="false",
    WORKER_ENABLED="false",
)

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.accounts import add_user, issue_setup_url  # noqa: E402
from app.config import asyncpg_url  # noqa: E402
from app.db import set_scope, standalone_session  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas import PersonInput  # noqa: E402

BACKEND_DIR = Path(__file__).parent.parent
PASSWORD = "correct-horse-battery"  # noqa: S105


def owner_engine():
    url, args = asyncpg_url(OWNER_URL)
    return create_async_engine(url, connect_args=args, poolclass=NullPool)


def pytest_sessionstart(session) -> None:
    """Start from an empty database and apply the real migrations."""

    async def reset() -> None:
        engine = owner_engine()
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
        await engine.dispose()

    asyncio.run(reset())
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, check=True
    )

    async def allow_login() -> None:
        engine = owner_engine()
        async with engine.begin() as connection:
            await connection.execute(text("ALTER ROLE platform_app LOGIN"))
        await engine.dispose()

    asyncio.run(allow_login())


@pytest.fixture(autouse=True)
async def clean_tables():
    engine = owner_engine()
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE organizations, users, webhook_inbox, job_queue CASCADE"))
    await engine.dispose()


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def activate(client: httpx.AsyncClient, setup_url: str, email: str) -> str:
    """Follow a setup link, then log in. Returns an access token."""
    token = setup_url.split("#setup=")[1]
    response = await client.post("/api/auth/set-password", json={"token": token, "password": PASSWORD})
    assert response.status_code == 204, response.text
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
async def operator_token(client) -> str:
    async with standalone_session() as db:
        await set_scope(db, operator=True)
        user = await add_user(db, PersonInput(full_name="Ops", email="ops@devliqly.in"), is_operator=True)
        url = await issue_setup_url(db, user.id)
        await db.commit()
    return await activate(client, url, "ops@devliqly.in")


async def make_org(client: httpx.AsyncClient, operator_token: str, name: str, email: str) -> tuple[str, str]:
    """Create a customer through the API. Returns (organization id, owner access token)."""
    response = await client.post(
        "/api/operator/organizations",
        json={"name": name, "owner": {"full_name": f"{name} Owner", "email": email}},
        headers=bearer(operator_token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["id"], await activate(client, body["owner_setup_url"], email)


@pytest.fixture
async def two_orgs(client, operator_token) -> dict:
    a_id, a_token = await make_org(client, operator_token, "Acme", "owner@acme-demo.com")
    b_id, b_token = await make_org(client, operator_token, "Birla", "owner@birla-demo.com")
    return {"a": {"id": a_id, "token": a_token}, "b": {"id": b_id, "token": b_token}}
