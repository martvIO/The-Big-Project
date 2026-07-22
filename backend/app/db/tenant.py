from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.db.rls import TENANT_ID_SETTING


@asynccontextmanager
async def tenant_session(
    session_factory: async_sessionmaker[AsyncSession], tenant_id: UUID
) -> AsyncIterator[AsyncSession]:
    """ORM session inside a transaction with the tenant context bound for its
    duration — the repository-facing analogue of tenant_connection. set_config
    is transaction-local (is_local=true), parameterized, and UUID-typed, so
    pooled connections can never leak context and no query on a tenant table
    escapes RLS."""
    async with session_factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config(:name, :value, true)"),
            {"name": TENANT_ID_SETTING, "value": str(tenant_id)},
        )
        yield session


@asynccontextmanager
async def tenant_connection(engine: AsyncEngine, tenant_id: UUID) -> AsyncIterator[AsyncConnection]:
    """A transaction with the tenant context bound for exactly its duration.

    set_config(..., is_local := true) is transaction-scoped, so pooled connections
    can never leak a tenant context across requests. The value is parameterized
    (never interpolated) and typed as UUID at the boundary, so garbage can't
    reach SQL. The Feature 4 middleware is the only production caller — the
    tenant_id always derives from the request hostname, never from client input.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config(:name, :value, true)"),
            {"name": TENANT_ID_SETTING, "value": str(tenant_id)},
        )
        yield conn
