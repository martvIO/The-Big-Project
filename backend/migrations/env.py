import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False, and NOT the alembic template's default of
    # True: alembic.ini names root/sqlalchemy/alembic only, so the default sets
    # `disabled = True` on every OTHER logger that already exists in the process
    # — "app" among them, since app.* modules hold module-scope loggers. A
    # disabled logger drops records inside isEnabledFor, before any handler, so
    # the silence is total and permanent for the life of the process. Under
    # pytest one `command.upgrade` in a db fixture used to mute every later
    # assertion about an "app" log line for the rest of the session, which is
    # why test_error_log_line_carries_only_status_and_code was green locally
    # (db tests deselected) and red on CI (they are not).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Populated when models arrive (Feature 3: tenants). None = migrations are hand-written.
target_metadata = None


def _database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().effective_database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
