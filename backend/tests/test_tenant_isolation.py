"""The permanent cross-tenant isolation suite. Blocking in CI from Feature 3 onward.

Runs as the non-owner boutique_app role — the same principal production uses.
A probe table stands in for future tenant-scoped tables and is secured with the
exact helper (`enable_tenant_rls`) real migrations will use, so what passes here
is what protects catalog/customers/bookings later.
"""

import uuid
from collections.abc import Callable

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.rls import enable_tenant_rls
from app.db.tenant import tenant_connection

pytestmark = pytest.mark.db

TENANT_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-4222-8222-222222222222")


@pytest.fixture(scope="session")
def probe_table(migrated_db: str, run_sql: Callable[[str, list[str]], None]) -> None:
    run_sql(
        migrated_db,
        [
            "DROP TABLE IF EXISTS rls_probe",
            """
            CREATE TABLE rls_probe (
              id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
              tenant_id UUID NOT NULL,
              note TEXT NOT NULL
            )
            """,
            "GRANT SELECT, INSERT, UPDATE, DELETE ON rls_probe TO app_user",
            *enable_tenant_rls("rls_probe"),
            f"""
            INSERT INTO rls_probe (tenant_id, note)
            VALUES ('{TENANT_A}', 'a-1'), ('{TENANT_A}', 'a-2'), ('{TENANT_B}', 'b-1')
            """,
        ],
    )


async def test_app_role_is_not_superuser_or_table_owner(
    app_role_url: str, probe_table: None
) -> None:
    """Guard against a vacuous pass: superusers and owners can bypass RLS."""
    engine = create_async_engine(app_role_url)
    try:
        async with engine.connect() as conn:
            is_super = await conn.execute(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            )
            assert is_super.scalar_one() is False
            owner = await conn.execute(
                text("SELECT tableowner FROM pg_tables WHERE tablename = 'rls_probe'")
            )
            current = await conn.execute(text("SELECT current_user"))
            assert owner.scalar_one() != current.scalar_one()
    finally:
        await engine.dispose()


async def test_force_rls_is_enabled_on_probe(migrated_db: str, probe_table: None) -> None:
    engine = create_async_engine(migrated_db)
    try:
        async with engine.connect() as conn:
            forced = await conn.execute(
                text("SELECT relforcerowsecurity FROM pg_class WHERE relname = 'rls_probe'")
            )
            assert forced.scalar_one() is True
    finally:
        await engine.dispose()


async def test_context_scopes_reads_to_own_tenant(app_role_url: str, probe_table: None) -> None:
    engine = create_async_engine(app_role_url)
    try:
        async with tenant_connection(engine, TENANT_A) as conn:
            notes_a = (await conn.execute(text("SELECT note FROM rls_probe"))).scalars().all()
        async with tenant_connection(engine, TENANT_B) as conn:
            notes_b = (await conn.execute(text("SELECT note FROM rls_probe"))).scalars().all()
    finally:
        await engine.dispose()
    assert notes_a and all(note.startswith("a") for note in notes_a)
    assert notes_b and all(note.startswith("b") for note in notes_b)


async def test_no_context_means_zero_rows(app_role_url: str, probe_table: None) -> None:
    """Unset context must fail closed: zero rows, not an error and never all rows."""
    engine = create_async_engine(app_role_url)
    try:
        async with engine.connect() as conn:
            count = await conn.execute(text("SELECT count(*) FROM rls_probe"))
            assert count.scalar_one() == 0
    finally:
        await engine.dispose()


async def test_write_for_other_tenant_is_rejected(app_role_url: str, probe_table: None) -> None:
    engine = create_async_engine(app_role_url)
    try:
        with pytest.raises(DBAPIError):
            async with tenant_connection(engine, TENANT_A) as conn:
                await conn.execute(
                    text("INSERT INTO rls_probe (tenant_id, note) VALUES (:tid, 'smuggled')"),
                    {"tid": str(TENANT_B)},
                )
    finally:
        await engine.dispose()


async def test_write_for_own_tenant_is_allowed(app_role_url: str, probe_table: None) -> None:
    engine = create_async_engine(app_role_url)
    try:
        async with tenant_connection(engine, TENANT_A) as conn:
            await conn.execute(
                text("INSERT INTO rls_probe (tenant_id, note) VALUES (:tid, 'a-ok')"),
                {"tid": str(TENANT_A)},
            )
        async with tenant_connection(engine, TENANT_B) as conn:
            notes_b = (await conn.execute(text("SELECT note FROM rls_probe"))).scalars().all()
    finally:
        await engine.dispose()
    assert "a-ok" not in notes_b
