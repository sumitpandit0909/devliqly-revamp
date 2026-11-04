import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import asyncpg_url, get_settings
from app.models import Base

target_metadata = Base.metadata


def run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    url, connect_args = asyncpg_url(get_settings().migration_database_url)
    engine = create_async_engine(url, connect_args=connect_args)
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline migrations are not supported")
asyncio.run(run_online())
