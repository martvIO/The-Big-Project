import asyncio
import logging
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
_ROLE_CHECK = "staff_users_role_check"
# _ADD_ROLE_CHECK is 0011's upgrade statement VERBATIM: the populated-table test
# below proves the migration's own claim, so it must run the real ALTER and not a
# paraphrase. _DROP_ROLE_CHECK deliberately drops the IF EXISTS that 0011's
# downgrade carries — a test that silently no-ops when the constraint is already
# gone would make the halves below pass vacuously.
_ADD_ROLE_CHECK = (
    f"ALTER TABLE staff_users ADD CONSTRAINT {_ROLE_CHECK} "
    "CHECK (role IN ('owner', 'shift_manager'))"
)
_DROP_ROLE_CHECK = f"ALTER TABLE staff_users DROP CONSTRAINT {_ROLE_CHECK}"
# Kept in step with test_staff_role_gating.UNKNOWN_ROLE, which owns the tripwire
# asserting it never becomes a real StaffRole.
UNKNOWN_ROLE = "no-such-role"
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
                    await conn.execute(text(_STAFF_INSERT), {"role": UNKNOWN_ROLE})
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
    GRANTs.

    The seeded row is left behind under its own random tenant_id, which is safe
    for two different reasons worth separating: every tenant-scoped reader in the
    suite cannot see it (RLS), and the two superuser probes in THIS file do see it
    but do not care — 'shift_manager' satisfies the constraint they add, so the
    populated-table test's owner half still succeeds with this row present."""

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
                        update(StaffUser).where(StaffUser.id == staff_id).values(role=UNKNOWN_ROLE)
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
    halves: an 'owner' row present -> the constraint is added; an unknown-role row
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
    assert asyncio.run(probe(UNKNOWN_ROLE)) is False


@pytest.mark.db
def test_migration_0011_round_trips(migrated_db: str) -> None:
    """downgrade() drops the CHECK; upgrade() puts it back. Runs as the migration
    owner (the app role cannot ALTER) and mutates the live schema, so it is LAST
    in this file and owns no fixtures.

    The finally is not decoration. A dropped table fails loudly for whatever runs
    next; a missing CHECK does not — it makes every constraint probe above pass
    vacuously, and the container is session-scoped and shared with
    test_staff_role_gating_integration.py.

    Ceiling, and it is no longer hypothetical: 0012 exists and IS destructive
    (it DROPs tenant_gateway_credentials and payments), so downgrade("0010") now
    unwinds it too and empties both. Nothing in the suite is harmed today —
    pytest collects this file before test_payments_*, and the upgrade back to
    head recreates both tables — but the day a payments db test has to run
    before this one, this is the test that has to grow a `0011` target instead
    of `0010`. Same ceiling test_catalog_integration's 0006 round-trip carries."""
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


# --- 0012: the two payments tables ---

_PAYMENT_TABLES = ("tenant_gateway_credentials", "payments")
_TABLE_EXISTS = "SELECT to_regclass(:name) IS NOT NULL"
_CREDENTIAL_INSERT = (
    "INSERT INTO tenant_gateway_credentials "
    "(tenant_id, provider, ciphertext, key_ref, last_validated_at, created_by) "
    "VALUES (uuid_generate_v4(), :provider, 'blob', 'fake', now(), uuid_generate_v4())"
)


def _tables_exist(url: str) -> bool:
    async def check() -> bool:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                found = []
                for name in _PAYMENT_TABLES:
                    result = await conn.execute(text(_TABLE_EXISTS), {"name": name})
                    found.append(bool(result.scalar_one()))
                assert len(set(found)) == 1, f"0012 left a half-applied schema: {found}"
                return found[0]
        finally:
            await engine.dispose()

    return asyncio.run(check())


@pytest.mark.db
def test_the_provider_check_admits_fake_and_rejects_a_real_provider(migrated_db: str) -> None:
    """D8's security control, both halves. The negative half names 'lemonsqueezy'
    explicitly so nobody later assumes F18's value is already allowed and ships
    an adapter whose first INSERT is an IntegrityError — the CHECK widens in
    F18's own migration, alongside the adapter, which is the whole point.

    Both probes roll back; nothing leaks into the shared container."""

    async def check() -> None:
        engine = create_async_engine(migrated_db)
        try:
            async with engine.connect() as conn:
                trans = await conn.begin()
                await conn.execute(text(_CREDENTIAL_INSERT), {"provider": "fake"})
                await trans.rollback()
            for refused in ("lemonsqueezy", "grow"):
                async with engine.connect() as conn:
                    trans = await conn.begin()
                    with pytest.raises(IntegrityError):
                        await conn.execute(text(_CREDENTIAL_INSERT), {"provider": refused})
                    await trans.rollback()
        finally:
            await engine.dispose()

    asyncio.run(check())


@pytest.mark.db
def test_the_app_role_cannot_delete_from_either_payments_table(app_role_url: str) -> None:
    """D7's revoked DELETE is REAL, not a comment: a hard DELETE of a payment row
    destroys financial evidence and of a credential row destroys the rotation
    trail. 0002's ALTER DEFAULT PRIVILEGES auto-granted full CRUD, so without
    0012's REVOKE-before-GRANT this passes silently.

    Shaped like the app-role UPDATE probe above: connect as the non-owner role
    (the container superuser bypasses grants) and assert the refusal reason, not
    merely that something raised. Each DELETE aborts its own transaction, so
    each gets its own session."""

    async def check() -> None:
        engine = create_async_engine(app_role_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant_id = uuid.uuid4()
        try:
            for table in _PAYMENT_TABLES:
                with pytest.raises(DBAPIError) as exc:
                    async with tenant_session(factory, tenant_id) as session:
                        await session.execute(text(f"DELETE FROM {table}"))
                assert "permission denied" in str(exc.value).lower(), table
            # …and the grants it DOES need are intact, so the revoke was
            # surgical rather than a blanket lockout.
            async with tenant_session(factory, tenant_id) as session:
                for table in _PAYMENT_TABLES:
                    await session.execute(text(f"SELECT count(*) FROM {table}"))
        finally:
            await engine.dispose()

    asyncio.run(check())


@pytest.mark.db
def test_migration_0012_round_trips(migrated_db: str) -> None:
    """downgrade() drops both tables; upgrade() puts them back. Runs as the
    migration owner (the app role cannot DROP) and mutates the live schema, so
    it is LAST in this file and owns no fixtures.

    The finally is not decoration and it is stricter here than for 0011: leaving
    the schema at 0011 would make every payments db test in the suite fail with
    UndefinedTable rather than with anything diagnostic, and the container is
    session-scoped and shared."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)
    try:
        assert _tables_exist(migrated_db)
        command.downgrade(cfg, "0011")
        assert not _tables_exist(migrated_db)
        command.upgrade(cfg, "head")
        assert _tables_exist(migrated_db)
    finally:
        command.upgrade(cfg, "head")  # idempotent when already at head


def test_running_env_py_does_not_disable_the_app_logger() -> None:
    """Unmarked and offline (`sql=True` runs env.py and touches no database), so
    this guard runs in the fast suite that the db-marked tests are deselected
    from — the suite where the damage used to be invisible.

    `fileConfig`'s default is disable_existing_loggers=True, and alembic.ini
    names only root/sqlalchemy/alembic, so the default sets `disabled = True` on
    "app". A disabled logger drops records inside isEnabledFor, before any
    handler, so no amount of caplog or handler-attaching in a test can see past
    it: one `command.upgrade` in a db fixture muted every "app" log assertion for
    the rest of the session, which is how
    test_error_log_line_carries_only_status_and_code was green locally and red
    on CI. env.py passes disable_existing_loggers=False; this fails if it stops.
    """
    app_logger = logging.getLogger("app")
    root = logging.getLogger()
    # fileConfig REPLACES root's handlers and level. Restore them, or this test
    # leaks the alembic console handler into every test that follows it.
    previous_handlers, previous_level = root.handlers[:], root.level
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", "postgresql+asyncpg://u:p@localhost/unused")
    try:
        command.upgrade(cfg, "head", sql=True)
        assert app_logger.disabled is False
    finally:
        root.handlers[:] = previous_handlers
        root.setLevel(previous_level)
        app_logger.disabled = False
