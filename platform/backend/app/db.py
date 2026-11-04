import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import asyncpg_url, get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    url, connect_args = asyncpg_url(get_settings().database_url)
    # pre_ping and recycle cope with Neon suspending idle compute
    return create_async_engine(
        url,
        connect_args=connect_args,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=240,
    )


@lru_cache
def _sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """One transaction per request. Routes commit explicitly; anything uncommitted rolls back."""
    async with _sessionmaker()() as session:
        yield session


@asynccontextmanager
async def standalone_session() -> AsyncIterator[AsyncSession]:
    """A session for work outside a request, such as CLI commands."""
    async with _sessionmaker()() as session:
        yield session


async def set_scope(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    operator: bool = False,
    auth_lookup: bool = False,
) -> None:
    """Tell row-level security who this transaction acts for.

    set_config(..., true) lasts only for the current transaction, so a pooled connection can never carry
    one customer's scope into another request. Only the values passed are changed.
    """
    values: dict[str, str] = {}
    if user_id is not None:
        values["app.user_id"] = str(user_id)
    if org_id is not None:
        values["app.org_id"] = str(org_id)
    if operator:
        values["app.operator"] = "on"
    if auth_lookup:
        values["app.auth_lookup"] = "on"
    for name, value in values.items():
        await session.execute(text("SELECT set_config(:name, :value, true)"), {"name": name, "value": value})


async def clear_auth_lookup(session: AsyncSession) -> None:
    await session.execute(text("SELECT set_config('app.auth_lookup', '', true)"))
