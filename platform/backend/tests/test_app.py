import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.config import INSECURE_DEV_SECRET, Settings, asyncpg_url
from tests.conftest import BACKEND_DIR


def test_neon_url_is_translated_for_asyncpg():
    url, args = asyncpg_url(
        "postgresql://u:p@ep-x-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    assert url == "postgresql+asyncpg://u:p@ep-x-pooler.c-7.us-east-2.aws.neon.tech/neondb"
    assert args == {"ssl": "require"}


def test_local_url_has_no_tls():
    url, args = asyncpg_url("postgresql://u@127.0.0.1:5432/db")
    assert url == "postgresql+asyncpg://u@127.0.0.1:5432/db"
    assert args == {}


def test_production_refuses_unsafe_settings():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(environment="production", jwt_secret=INSECURE_DEV_SECRET, public_base_url="https://x.test")
    with pytest.raises(ValidationError, match="https"):
        Settings(environment="production", jwt_secret="y" * 40, public_base_url="http://x.test")


async def test_health_and_readiness(client):
    assert (await client.get("/healthz")).json() == {"status": "ok"}
    assert (await client.get("/readyz")).json() == {"status": "ready"}


async def test_security_headers_and_no_cache_on_api(client):
    response = await client.get("/api/me")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


async def test_login_page_is_served(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "Devliqly Platform" in response.text


def test_models_match_migrations():
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "check"], cwd=BACKEND_DIR, check=True, capture_output=True
    )
