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

from app.db.rls import TENANT_ID_SETTING, enable_tenant_rls
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
    """Guard against a vacuous pass: superusers, BYPASSRLS roles, and owners
    can all bypass RLS."""
    engine = create_async_engine(app_role_url)
    try:
        async with engine.connect() as conn:
            flags = await conn.execute(
                text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            )
            rolsuper, rolbypassrls = flags.one()
            assert rolsuper is False
            assert rolbypassrls is False
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


async def test_update_for_other_tenant_is_a_noop(app_role_url: str, probe_table: None) -> None:
    """USING hides B's rows from A's UPDATE — 0 rows affected, B's data intact."""
    engine = create_async_engine(app_role_url)
    try:
        async with tenant_connection(engine, TENANT_A) as conn:
            result = await conn.execute(
                text("UPDATE rls_probe SET note = 'defaced' WHERE tenant_id = :tid"),
                {"tid": str(TENANT_B)},
            )
            assert result.rowcount == 0
        async with tenant_connection(engine, TENANT_B) as conn:
            notes_b = (await conn.execute(text("SELECT note FROM rls_probe"))).scalars().all()
    finally:
        await engine.dispose()
    assert "defaced" not in notes_b
    assert "b-1" in notes_b


async def test_delete_for_other_tenant_is_a_noop(app_role_url: str, probe_table: None) -> None:
    """A cannot destroy B's data: DELETE against invisible rows affects 0 rows."""
    engine = create_async_engine(app_role_url)
    try:
        async with tenant_connection(engine, TENANT_A) as conn:
            result = await conn.execute(
                text("DELETE FROM rls_probe WHERE tenant_id = :tid"),
                {"tid": str(TENANT_B)},
            )
            assert result.rowcount == 0
        async with tenant_connection(engine, TENANT_B) as conn:
            notes_b = (await conn.execute(text("SELECT note FROM rls_probe"))).scalars().all()
    finally:
        await engine.dispose()
    assert "b-1" in notes_b


async def test_reparenting_own_row_to_other_tenant_is_rejected(
    app_role_url: str, probe_table: None
) -> None:
    """WITH CHECK also governs UPDATE's new values: A cannot push a row into B."""
    engine = create_async_engine(app_role_url)
    try:
        with pytest.raises(DBAPIError):
            async with tenant_connection(engine, TENANT_A) as conn:
                await conn.execute(
                    text("UPDATE rls_probe SET tenant_id = :other WHERE note = 'a-1'"),
                    {"other": str(TENANT_B)},
                )
    finally:
        await engine.dispose()


async def test_garbage_context_fails_loudly_not_open(app_role_url: str, probe_table: None) -> None:
    """A non-UUID context that somehow bypassed the typed helper must error the
    query on the ::uuid cast (fail closed) — never fall back to showing rows."""
    engine = create_async_engine(app_role_url)
    try:
        with pytest.raises(DBAPIError):
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config(:name, 'not-a-uuid', true)"),
                    {"name": TENANT_ID_SETTING},
                )
                await conn.execute(text("SELECT count(*) FROM rls_probe"))
    finally:
        await engine.dispose()


async def test_every_tenant_id_table_has_forced_rls(migrated_db: str, probe_table: None) -> None:
    """Makes the 'secure every tenant table via enable_tenant_rls' promise
    enforceable rather than conventional: any table carrying a tenant_id column
    without FORCEd RLS fails this suite."""
    engine = create_async_engine(migrated_db)
    try:
        async with engine.connect() as conn:
            missing = (
                (
                    await conn.execute(
                        text(
                            """
                            SELECT c.relname FROM pg_class c
                            JOIN pg_attribute a ON a.attrelid = c.oid
                            WHERE a.attname = 'tenant_id'
                              AND c.relkind = 'r'
                              AND NOT a.attisdropped
                              AND NOT c.relforcerowsecurity
                            """
                        )
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()
    assert missing == []
