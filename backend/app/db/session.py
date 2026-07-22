from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


async def verify_database_role(engine: AsyncEngine) -> None:
    """Fail fast if the connected role could bypass RLS. Postgres RLS — even
    FORCEd — does not apply to superusers or BYPASSRLS roles, so running the app
    with one would silently void tenant isolation with zero test failures."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        )
        rolsuper, rolbypassrls = result.one()
        if rolsuper or rolbypassrls:
            raise RuntimeError(
                "Refusing to start: the database role can bypass row-level security "
                "(superuser or BYPASSRLS). Connect as a non-privileged application role."
            )


async def ensure_safe_database_role() -> None:
    """Shared fail-fast policy for every entrypoint (web app + CLI): outside dev,
    refuse to run against an RLS-bypassing role. Dev is exempt because local runs
    use the postgres superuser. One source of truth for the 'when to skip' rule."""
    if get_settings().app_env != "dev":
        await verify_database_role(get_engine())


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().effective_database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory
