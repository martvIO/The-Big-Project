import asyncio
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.models.constants import StaffRole
from app.models.staff_user import StaffUser

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.db
def test_migrations_apply_and_uuid_ossp_available(migrated_db: str) -> None:
    async def check() -> tuple[str, int]:
        engine = create_async_engine(migrated_db)
        try:
            async with engine.connect() as conn:
                generated = await conn.execute(text("SELECT uuid_generate_v4()::text"))
                versions = await conn.execute(text("SELECT count(*) FROM alembic_version"))
                return str(generated.scalar_one()), int(versions.scalar_one())
        finally:
            await engine.dispose()

    uuid_value, version_rows = asyncio.run(check())
    assert len(uuid_value) == 36
    assert version_rows == 1


_STAFF_INSERT = (
    "INSERT INTO staff_users (tenant_id, email, password_hash, display_name, role) "
    "VALUES (uuid_generate_v4(), 'probe@check.example', 'hash', 'Probe', :role)"
)
# 0011's statements, verbatim — the populated-table test below re-runs the real
# ALTER rather than a paraphrase of it.
_ROLE_CHECK = "staff_users_role_check"
_ADD_ROLE_CHECK = (
    f"ALTER TABLE staff_users ADD CONSTRAINT {_ROLE_CHECK} "
    "CHECK (role IN ('owner', 'shift_manager'))"
)
_DROP_ROLE_CHECK = f"ALTER TABLE staff_users DROP CONSTRAINT {_ROLE_CHECK}"
_COUNT_ROLE_CHECK = "SELECT count(*) FROM pg_constraint WHERE conname = :name"


def _role_check_exists(url: str) -> bool:
    async def check() -> int:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text(_COUNT_ROLE_CHECK), {"name": _ROLE_CHECK})
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(check()) == 1


@pytest.mark.db
def test_staff_role_check_pins_the_role_set(migrated_db: str) -> None:
    """0011's CHECK admits exactly the StaffRole members. Both probes roll back —
    nothing leaks into other tests sharing the container."""

    async def check() -> None:
        engine = create_async_engine(migrated_db)
        try:
            async with engine.connect() as conn:
                trans = await conn.begin()
                await conn.execute(text(_STAFF_INSERT), {"role": "shift_manager"})
                await trans.rollback()
            async with engine.connect() as conn:
                trans = await conn.begin()
                with pytest.raises(IntegrityError):
                    await conn.execute(text(_STAFF_INSERT), {"role": "reception"})
                await trans.rollback()
        finally:
            await engine.dispose()

    asyncio.run(check())


@pytest.mark.db
def test_the_app_role_can_promote_to_shift_manager_but_not_to_an_unknown_role(
    app_role_url: str,
) -> None:
    """The CHECK is enforced against the APP role and against UPDATE — the two
    axes the probe above leaves open (it connects as the container superuser and
    only INSERTs). The positive half is also F51's pre-flight: boutique_app really
    can write 'shift_manager' past the constraint, under forced RLS, with only its
    GRANTs. The seeded row keeps its own random tenant_id, so RLS makes it
    invisible to every other test sharing the container."""

    async def check() -> None:
        engine = create_async_engine(app_role_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                staff = await StaffUsersRepository().insert(
                    session,
                    tenant_id=tenant_id,
                    email=f"probe-{uuid.uuid4().hex[:8]}@check.example",
                    password_hash="not-a-real-hash",
                    display_name="Probe",
                )
                staff_id = staff.id

            async with tenant_session(factory, tenant_id) as session:
                await session.execute(
                    update(StaffUser)
                    .where(StaffUser.id == staff_id)
                    .values(role=StaffRole.SHIFT_MANAGER.value)
                )

            # Its own session: the refused statement aborts its transaction, and
            # an aborted transaction cannot be reused for the read-back.
            with pytest.raises(IntegrityError):
                async with tenant_session(factory, tenant_id) as session:
                    await session.execute(
                        update(StaffUser).where(StaffUser.id == staff_id).values(role="reception")
                    )

            async with tenant_session(factory, tenant_id) as session:
                stored = await session.scalar(
                    select(StaffUser.role).where(StaffUser.id == staff_id)
                )
            # The refusal changed nothing — not even partially.
            assert stored == StaffRole.SHIFT_MANAGER.value
        finally:
            await engine.dispose()

    asyncio.run(check())


@pytest.mark.db
def test_adding_the_role_check_validates_existing_rows(migrated_db: str) -> None:
    """0011's comment claims ADD CONSTRAINT validates existing rows, so the
    migration cannot fail on live data where every row carries the 'owner'
    default. Proven with the migration's exact ALTER on a POPULATED table, both
    halves: an 'owner' row present -> the constraint is added; a 'reception' row
    present -> it is REFUSED. Without the second half a NOT VALID constraint
    would pass the first and the comment would be a lie.

    Postgres runs DDL transactionally, so each half — the DROP included — rolls
    back whole and the session-scoped container ends as it started."""

    async def probe(seeded_role: str) -> bool:
        engine = create_async_engine(migrated_db)
        try:
            async with engine.connect() as conn:
                trans = await conn.begin()
                try:
                    await conn.execute(text(_DROP_ROLE_CHECK))
                    await conn.execute(text(_STAFF_INSERT), {"role": seeded_role})
                    await conn.execute(text(_ADD_ROLE_CHECK))
                    return True
                except DBAPIError as exc:
                    # DBAPIError, not IntegrityError: a failing ADD CONSTRAINT is
                    # a check_violation like a failing INSERT, but asserting the
                    # constraint name is what proves it failed for the right
                    # reason under either SQLAlchemy wrapper class.
                    assert _ROLE_CHECK in str(exc)
                    return False
                finally:
                    await trans.rollback()
        finally:
            await engine.dispose()

    assert asyncio.run(probe(StaffRole.OWNER.value)) is True
    assert asyncio.run(probe("reception")) is False


@pytest.mark.db
def test_migration_0011_round_trips(migrated_db: str) -> None:
    """downgrade() drops the CHECK; upgrade() puts it back. Runs as the migration
    owner (the app role cannot ALTER) and mutates the live schema, so it is LAST
    in this file and owns no fixtures.

    The finally is not decoration. A dropped table fails loudly for whatever runs
    next; a missing CHECK does not — it makes every constraint probe above pass
    vacuously, and the container is session-scoped and shared with
    test_staff_role_gating_integration.py.

    Ceiling: downgrade("0010") today unwinds only 0011 and touches no rows. Once a
    0012 exists this also unwinds that, and if 0012 is destructive this test starts
    destroying data for whatever runs after it — the same ceiling
    test_catalog_integration's 0006 round-trip already carries."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)
    try:
        assert _role_check_exists(migrated_db)
        command.downgrade(cfg, "0010")
        assert not _role_check_exists(migrated_db)
        command.upgrade(cfg, "head")
        assert _role_check_exists(migrated_db)
    finally:
        command.upgrade(cfg, "head")  # idempotent when already at head
