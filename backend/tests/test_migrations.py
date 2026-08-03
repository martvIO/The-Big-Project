import asyncio
import datetime
import logging
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.models.constants import QueueTicketStatus, StaffRole, VisitType
from app.models.queue_ticket import QueueTicket
from app.models.staff_user import StaffUser

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


def _parent_of(marker: str) -> str:
    """The revision one step below the migration whose message contains `marker`.

    A round-trip test needs a downgrade TARGET, and both obvious spellings rot:
    a hardcoded revision id rots when the branch is renumbered at rebase, and
    `"-1"` rots the moment ANOTHER feature lands a migration on top, because it
    then means "one step back from somebody else's head". The deposit block
    below records that second failure happening for real — F53 landed on top and
    the payments round-trip silently stopped one revision short, reporting a
    failure against payments from a feature that never touched it.

    Identifying the revision by WHAT IT IS costs nothing and survives both.

    `down_revision` is typed str | list | tuple because alembic supports merge
    revisions with several parents. This project has exactly one head
    (test_exactly_one_migration_head) and no merges, so anything but a plain str
    means the history grew a shape no test in this file expects.
    """
    revisions = ScriptDirectory.from_config(_alembic_config()).walk_revisions()
    script = next((s for s in revisions if marker in (s.doc or "").lower()), None)
    assert script is not None, f"no migration is identifiable by {marker!r} any more"
    parent = script.down_revision
    assert isinstance(parent, str), f"expected a single-parent revision, got {parent!r}"
    return parent


def test_exactly_one_migration_head() -> None:
    """Two migrations claiming one revision id is the failure mode that parallel
    feature branches actually hit, and it is invisible to every other guard.

    The filenames differ, so git merges both files cleanly and reports no
    conflict. Nothing in review looks wrong. The first symptom is
    `alembic upgrade head` refusing to run against a branched history, which
    surfaces as every `db`-marked test erroring at fixture setup with a message
    about multiple heads — on CI, in a job that was green on the branch an hour
    earlier, with a diff that touched no migration.

    So this assertion is deliberately NOT `db`-marked: it needs no database and
    no Docker, which means it runs in `make test` on a laptop and fails BEFORE
    the push that would have caused it. It reads the revision graph off the
    filesystem, exactly as alembic does.

    Not pinned to a literal head value — that would rot on every migration and
    teach whoever hits it to update the literal without reading why.
    """
    heads = ScriptDirectory.from_config(_alembic_config()).get_heads()
    assert len(heads) == 1, (
        f"alembic has {len(heads)} heads: {sorted(heads)}. Two migrations declare the same "
        "`down_revision`, which almost always means two feature branches each claimed the "
        "next number. Renumber the later one: set its `revision` to follow the other and "
        "point its `down_revision` at it, and rename the file to match."
    )


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
# F57's migration statement, VERBATIM, for the same reason _ADD_ROLE_CHECK is
# 0011's. It is also — byte for byte — what F57's DOWNGRADE must refuse to run
# past a floor-role row, which is why _ADD_ROLE_CHECK is reused below as the
# narrowing statement rather than spelled a second time.
_ADD_WIDE_ROLE_CHECK = (
    f"ALTER TABLE staff_users ADD CONSTRAINT {_ROLE_CHECK} "
    "CHECK (role IN ('owner', 'shift_manager', 'reception', 'sales_assistant', 'seamstress'))"
)
_DROP_ROLE_CHECK = f"ALTER TABLE staff_users DROP CONSTRAINT {_ROLE_CHECK}"
# Kept in step with test_staff_role_gating.UNKNOWN_ROLE, which owns the tripwire
# asserting it never becomes a real StaffRole. F57 is the day 0011's three
# anticipated roles actually joined the enum, and the sentinel held — it was
# chosen precisely so that day would not silently invert every test using it.
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
    """The CHECK admits exactly the StaffRole members and nothing else.

    ITERATED from the live enum rather than listing today's five: the day a sixth
    role is added, either the migration widened the CHECK with it and this test
    covers it for free, or it did not and this test is the red. Listing values
    would have to be edited by the same hand that forgot the migration.

    EVERY probe rolls back, and after F57 that is load-bearing rather than tidy.
    `migrated_db` is `scope="session"`, so one container is shared by every
    db-marked module — and a committed 'reception' row makes
    test_adding_the_role_check_validates_existing_rows re-add 0011's TWO-value
    CHECK over a row that violates it, flipping an assertion in a test that never
    mentions F57."""

    async def check() -> None:
        engine = create_async_engine(migrated_db)
        try:
            for role in StaffRole:
                async with engine.connect() as conn:
                    trans = await conn.begin()
                    await conn.execute(text(_STAFF_INSERT), {"role": role.value})
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
    populated-table test's owner half still succeeds with this row present.

    ⚠ **After F57 that leftover may hold ONLY 'owner' or 'shift_manager'**, which
    is why the floor-role half below is rolled back rather than committed. A
    committed 'reception' row reddens THREE tests — both round-trips, whose first
    statement is F57's narrowing downgrade, and
    test_adding_the_role_check_validates_existing_rows, which has nothing to do
    with round-trips and would simply find 0011's two-value ADD refused."""

    class _Rollback(Exception):
        """Aborts the tenant_session so the floor-role write is never committed.
        Exiting tenant_session IS the commit (db/tenant.py:25), so there is no
        gentler way to run a write under the app role and keep nothing."""

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

            # F57's widened CHECK on the same two axes the shift_manager half
            # covers — the APP role, and UPDATE rather than INSERT. Rolled back,
            # per the docstring: the write must happen and be admitted, and it
            # must not survive this test.
            with pytest.raises(_Rollback):
                async with tenant_session(factory, tenant_id) as session:
                    await session.execute(
                        update(StaffUser)
                        .where(StaffUser.id == staff_id)
                        .values(role=StaffRole.SEAMSTRESS.value)
                    )
                    promoted = await session.scalar(
                        select(StaffUser.role).where(StaffUser.id == staff_id)
                    )
                    assert promoted == StaffRole.SEAMSTRESS.value
                    raise _Rollback

            async with tenant_session(factory, tenant_id) as session:
                after = await session.scalar(select(StaffUser.role).where(StaffUser.id == staff_id))
            # The rollback is real, and the leftover row is back to a value the
            # narrowing downgrade can live with.
            assert after == StaffRole.SHIFT_MANAGER.value
        finally:
            await engine.dispose()

    asyncio.run(check())


def _constraint_accepts(url: str, add_sql: str, seeded_roles: list[str]) -> bool:
    """DROP the role CHECK, seed rows, and try to re-add `add_sql` over them.

    One helper for three claims — 0011's ADD-validates-existing-rows, F57's
    widened sibling, and F57's downgrade refusing to narrow — because all three
    are the same experiment with a different statement and a different seed, and
    three copies of it would be three places to drift.

    Postgres runs DDL transactionally, so each call — the DROP included — rolls
    back whole and the session-scoped container ends as it started. That is what
    keeps a seeded floor role from reaching any other module (spec D1's trap).
    """

    async def probe() -> bool:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                trans = await conn.begin()
                try:
                    await conn.execute(text(_DROP_ROLE_CHECK))
                    for role in seeded_roles:
                        await conn.execute(text(_STAFF_INSERT), {"role": role})
                    await conn.execute(text(add_sql))
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

    return asyncio.run(probe())


@pytest.mark.db
def test_adding_the_role_check_validates_existing_rows(migrated_db: str) -> None:
    """0011's comment claims ADD CONSTRAINT validates existing rows, so the
    migration cannot fail on live data where every row carries the 'owner'
    default. Proven with the migration's exact ALTER on a POPULATED table, both
    halves: an 'owner' row present -> the constraint is added; an unknown-role row
    present -> it is REFUSED. Without the second half a NOT VALID constraint
    would pass the first and the comment would be a lie."""
    assert _constraint_accepts(migrated_db, _ADD_ROLE_CHECK, [StaffRole.OWNER.value]) is True
    assert _constraint_accepts(migrated_db, _ADD_ROLE_CHECK, [UNKNOWN_ROLE]) is False


@pytest.mark.db
def test_adding_the_widened_role_check_validates_existing_rows(migrated_db: str) -> None:
    """F57's widening, on a POPULATED table, with the migration's exact ALTER —
    0011's shape reused because the claim is the same claim.

    A widening can only ever ADMIT rows that were already legal, so this cannot
    fail on live data. The test exists anyway for the two things the argument
    does not cover: a claim is worth what proves it, and a typo in one of the
    three new literals fails here rather than in production.

    The positive half seeds BOTH generations — two pre-F57 roles and a floor one
    — so it proves the widened constraint still admits the old set rather than
    only the values it added. That is the mutation a careless rewrite of the
    literal list would make, and seeding 'reception' alone would miss it."""
    assert (
        _constraint_accepts(
            migrated_db,
            _ADD_WIDE_ROLE_CHECK,
            [StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value, StaffRole.RECEPTION.value],
        )
        is True
    )
    assert _constraint_accepts(migrated_db, _ADD_WIDE_ROLE_CHECK, [UNKNOWN_ROLE]) is False


@pytest.mark.db
def test_the_downgrade_refuses_to_narrow_past_a_floor_role_row(migrated_db: str) -> None:
    """F57's downgrade re-adds the TWO-value CHECK deliberately WITHOUT
    `IF EXISTS` and deliberately ABLE TO FAIL, and this is that failure asserted
    rather than described.

    A row holding 'seamstress' must BLOCK the narrowing. The alternative — a
    lenient downgrade — leaves the database describing a state its own schema
    forbids: a row sitting past a constraint its value violates, which nothing
    afterwards would ever notice.

    The statement under test is `_ADD_ROLE_CHECK`, which is 0011's upgrade and
    F57's downgrade byte for byte. That is not a shortcut — it is the reason the
    downgrade is spelled the way it is."""
    assert _constraint_accepts(migrated_db, _ADD_ROLE_CHECK, [StaffRole.SEAMSTRESS.value]) is False


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


def _provider_admitted(url: str, provider: str) -> bool:
    """Probes the CHECK by attempting one INSERT and rolling it back. Nothing
    leaks into the session-scoped container either way."""

    async def check() -> bool:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                trans = await conn.begin()
                try:
                    await conn.execute(text(_CREDENTIAL_INSERT), {"provider": provider})
                except IntegrityError:
                    return False
                finally:
                    await trans.rollback()
                return True
        finally:
            await engine.dispose()

    return asyncio.run(check())


@pytest.mark.db
def test_the_provider_check_admits_exactly_fake_and_lemonsqueezy(migrated_db: str) -> None:
    """D8's security control, both halves, at 0013's width.

    Until F18 this test asserted 'lemonsqueezy' was REFUSED, so that nobody
    could assume the value was already allowed and ship an adapter whose first
    INSERT is an IntegrityError. 0013 widens the CHECK alongside the adapter,
    which is exactly the discipline that assertion was protecting — so the value
    moves from the negative half to the positive one and the negative half keeps
    naming a provider with no adapter behind it.

    The CHECK is what makes "no real merchant credential can be stored behind an
    adapter that has not shipped" a property of the SCHEMA. It must widen by one
    value per adapter, never pre-emptively."""
    assert _provider_admitted(migrated_db, "fake")
    assert _provider_admitted(migrated_db, "lemonsqueezy")
    for refused in ("grow", "stripe", "LEMONSQUEEZY", ""):
        assert not _provider_admitted(migrated_db, refused), refused


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


# --- 0013: the widened provider CHECK ---


@pytest.mark.db
def test_migration_0013_round_trips(migrated_db: str) -> None:
    """downgrade() narrows the CHECK back to 'fake' alone; upgrade() re-widens
    it. Runs as the migration owner (the app role cannot ALTER) and mutates the
    live schema, so it is LAST in this file and owns no fixtures.

    The finally is not decoration and this one is the quiet failure mode 0011's
    docstring warns about: leaving the schema at 0012 does not DROP anything, so
    nothing fails loudly — every payments db test that stores a lemonsqueezy
    credential set would just start raising IntegrityError somewhere unrelated,
    in a session-scoped container shared with the rest of the suite.

    The probes here bracket the transition in BOTH directions rather than only
    asserting the end state: a downgrade that silently no-ops would otherwise
    leave this green while shipping a migration that cannot be rolled back."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)
    try:
        assert _provider_admitted(migrated_db, "lemonsqueezy")
        command.downgrade(cfg, "0012")
        assert not _provider_admitted(migrated_db, "lemonsqueezy")
        # …and the narrowed CHECK still admits what 0012 declared, so the
        # downgrade restored the constraint rather than merely dropping it.
        assert _provider_admitted(migrated_db, "fake")
        command.upgrade(cfg, "head")
        assert _provider_admitted(migrated_db, "lemonsqueezy")
    finally:
        command.upgrade(cfg, "head")  # idempotent when already at head


# --- 0014: the booking check-in column ---

_CHECK_IN_COLUMN = (
    "SELECT data_type, is_nullable FROM information_schema.columns "
    "WHERE table_name = 'bookings' AND column_name = 'checked_in_at'"
)
_STATUS_CONSTRAINT_DEF = (
    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
    "WHERE conrelid = 'bookings'::regclass AND conname = 'bookings_status_check'"
)
_INDEX_DEF = "SELECT indexdef FROM pg_indexes WHERE tablename = 'bookings' AND indexname = :name"
# Spelled as POSTGRES deparses them, not as 0008/0009 wrote them: both
# pg_get_constraintdef and pg_indexes.indexdef normalise (IN (...) becomes
# = ANY (ARRAY[...]), predicates get parenthesised and re-ordered, and the
# schema is qualified). Captured from a real 16.x server rather than
# transcribed from the migration source, because a literal that merely looks
# right would pin nothing.
_STATUS_CHECK_DEF = (
    "CHECK ((status = ANY (ARRAY['confirmed'::text, 'cancelled'::text, "
    "'no_show'::text, 'completed'::text, 'pending_payment'::text])))"
)
# 'pending_payment' was appended by F19, and this literal changing IS the
# deliberate review F34 asked for — see the test below. Re-captured from a real
# 16.x server after the widening, never hand-edited: the value F19 would have
# GUESSED (appending to the pre-existing string) happens to be right here only
# because the new value sorts last in the ARRAY as written, and that is luck
# rather than a rule.
_CANCELLED_BY_CHECK_DEF = (
    "CHECK ((cancelled_by = ANY (ARRAY['customer'::text, 'owner'::text, 'expired'::text])))"
)
_PENDING_PAYMENT_INDEX_DEF = (
    "CREATE INDEX idx_bookings_pending_payment ON public.bookings "
    "USING btree (tenant_id, created_at) "
    "WHERE ((deleted_at IS NULL) AND (status = 'pending_payment'::text))"
)
_SLOT_SEAT_INDEX_DEF = (
    "CREATE UNIQUE INDEX idx_bookings_slot_seat_unique ON public.bookings "
    "USING btree (tenant_id, starts_at, seat_index) "
    "WHERE ((deleted_at IS NULL) AND (status <> 'cancelled'::text))"
)
_CUSTOMER_STARTS_INDEX_DEF = (
    "CREATE UNIQUE INDEX idx_bookings_tenant_customer_starts_unique ON public.bookings "
    "USING btree (tenant_id, customer_id, starts_at) "
    "WHERE ((deleted_at IS NULL) AND (status <> 'cancelled'::text))"
)


def _check_in_column(url: str) -> tuple[str, str] | None:
    async def read() -> tuple[str, str] | None:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                row = (await conn.execute(text(_CHECK_IN_COLUMN))).first()
                return None if row is None else (str(row[0]), str(row[1]))
        finally:
            await engine.dispose()

    return asyncio.run(read())


def _pinned_definitions(url: str) -> tuple[str, str, str]:
    async def read() -> tuple[str, str, str]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                status = await conn.execute(text(_STATUS_CONSTRAINT_DEF))
                slot = await conn.execute(
                    text(_INDEX_DEF), {"name": "idx_bookings_slot_seat_unique"}
                )
                customer = await conn.execute(
                    text(_INDEX_DEF), {"name": "idx_bookings_tenant_customer_starts_unique"}
                )
                return (
                    str(status.scalar_one()),
                    str(slot.scalar_one()),
                    str(customer.scalar_one()),
                )
        finally:
            await engine.dispose()

    return asyncio.run(read())


@pytest.mark.db
def test_the_booking_check_in_migration_leaves_the_status_check_and_both_unique_indexes_alone(
    migrated_db: str,
) -> None:
    """The highest-value test in F34, and what it guards is a FUTURE edit.

    Spec D1 argues at length that check-in is a COLUMN and not a fifth
    BookingStatus, and the whole argument rests on the status CHECK and the two
    partial unique indexes being untouched. This makes that promise mechanical
    instead of rhetorical: when E4 widens the CHECK for 'pending_payment' it
    collides with a pinned literal and a deliberate review, instead of colliding
    with nothing.

    **That collision has now happened, and the guard did its job.** F19 widened
    the status CHECK with 'pending_payment' and this assertion went red on the
    first local db run, which is the outcome F34 designed for. The literal was
    re-captured from a live server and updated deliberately.

    What matters is what did NOT change: BOTH index assertions below stayed
    green through that widening, un-edited. That is F19's D1 claim — a held seat
    is an occupied seat, needing no index change and no occupancy-query change —
    proved by this test rather than asserted by its spec. If a future feature
    finds itself editing _SLOT_SEAT_INDEX_DEF or _CUSTOMER_STARTS_INDEX_DEF, it
    is changing what frees a seat, and that is a much larger decision than a
    migration.

    Keyed to `head` — i.e. AFTER this feature's migration, whatever number it
    ended up with — and never to a hardcoded revision id (D2). The migration id
    is resolved from `alembic heads` at build time, so a literal here would rot
    the first time another feature lands a migration first."""
    status_check, slot_seat, customer_starts = _pinned_definitions(migrated_db)
    assert status_check == _STATUS_CHECK_DEF
    assert slot_seat == _SLOT_SEAT_INDEX_DEF
    assert customer_starts == _CUSTOMER_STARTS_INDEX_DEF


@pytest.mark.db
def test_migration_0014_round_trips(migrated_db: str) -> None:
    """upgrade() adds one nullable TIMESTAMPTZ; downgrade() drops it. Runs as the
    migration owner (the app role cannot ALTER) and mutates the live
    session-scoped schema, so it is LAST among the schema-mutating tests in this
    file and owns no fixtures.

    Probes BOTH directions rather than only the end state, which is 0013's own
    rule: a downgrade that silently no-ops would otherwise stay green while
    shipping a migration that cannot be rolled back.

    The finally is not decoration. Leaving the schema at 0013 drops the column
    the ORM still maps, so every later booking db test in the shared container
    would fail with UndefinedColumn somewhere unrelated to itself."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)
    try:
        assert _check_in_column(migrated_db) == ("timestamp with time zone", "YES")
        command.downgrade(cfg, "0013")
        assert _check_in_column(migrated_db) is None
        command.upgrade(cfg, "head")
        assert _check_in_column(migrated_db) == ("timestamp with time zone", "YES")
    finally:
        command.upgrade(cfg, "head")  # idempotent when already at head


# --- F57: the widened role CHECK and the break column ---

_BREAK_COLUMN = (
    "SELECT data_type, is_nullable FROM information_schema.columns "
    "WHERE table_name = 'staff_users' AND column_name = 'break_started_at'"
)
_ROLE_CONSTRAINT_DEF = (
    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
    f"WHERE conrelid = 'staff_users'::regclass AND conname = '{_ROLE_CHECK}'"
)
# Spelled as POSTGRES deparses it, not as the migration wrote it:
# pg_get_constraintdef normalises `IN (...)` into `= ANY (ARRAY[...])` and casts
# every literal. CAPTURED from a real 16.x server rather than transcribed from
# _ADD_WIDE_ROLE_CHECK above, because a literal that merely looks right would pin
# nothing — and pinning nothing is the whole failure mode this test exists to
# prevent for whoever widens this constraint next.
_WIDE_ROLE_CHECK_DEF = (
    "CHECK ((role = ANY (ARRAY['owner'::text, 'shift_manager'::text, "
    "'reception'::text, 'sales_assistant'::text, 'seamstress'::text])))"
)


def _role_constraint_def(url: str) -> str:
    async def read() -> str:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                return str((await conn.execute(text(_ROLE_CONSTRAINT_DEF))).scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(read())


def _break_column(url: str) -> tuple[str, str] | None:
    async def read() -> tuple[str, str] | None:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                row = (await conn.execute(text(_BREAK_COLUMN))).first()
                return None if row is None else (str(row[0]), str(row[1]))
        finally:
            await engine.dispose()

    return asyncio.run(read())


@pytest.mark.db
def test_the_floor_roles_migration_pins_the_widened_constraint_definition(
    migrated_db: str,
) -> None:
    """The highest-value test in F57, and what it guards is a FUTURE edit.

    Every argument in this feature rests on the role set being exactly these
    five: D4 spells the floor router's gate `require_role(*StaffRole)`, D5's
    walker pins the three floor roles out of everything else, and
    test_me_echoes_an_out_of_enum_role_verbatim records in writing that what
    makes `/manage/auth/me`'s un-allowlisted echo safe is THE DATABASE. This
    makes that mechanical: when F36 or a later feature widens the role set it
    collides with a pinned literal and a deliberate review, instead of colliding
    with nothing.

    Keyed to `head` — i.e. AFTER this feature's migration, whatever number it
    ended up with — and never to a hardcoded revision id (D3). The migration id
    is resolved from `alembic heads` at build time, so a literal here would rot
    the first time another feature lands a migration first."""
    assert _role_constraint_def(migrated_db) == _WIDE_ROLE_CHECK_DEF


@pytest.mark.db
def test_the_floor_roles_migration_adds_a_nullable_break_timestamp(migrated_db: str) -> None:
    """One nullable TIMESTAMPTZ and nothing else — no default, no NOT NULL, no
    backfill. NULL is the only "not on a break" sentinel (spec D2), so a default
    or a NOT NULL would have to invent a second one."""
    assert _break_column(migrated_db) == ("timestamp with time zone", "YES")


@pytest.mark.db
def test_migration_floor_roles_round_trips(migrated_db: str) -> None:
    """upgrade() widens the CHECK and adds the column; downgrade() removes BOTH.
    Runs as the migration owner (the app role cannot ALTER) and mutates the live
    session-scoped schema, so it is LAST among the schema-mutating tests in this
    file and owns no fixtures.

    Probes BOTH directions and BOTH halves rather than only the end state, which
    is 0013's own rule: a downgrade that silently no-ops on one of the two would
    stay green while shipping a migration that cannot be rolled back.

    `downgrade(cfg, "0014")` and not a revision id of F57's own — the target is
    the revision this one REVISES, which is what `alembic heads` answered at
    build time. The finally is not decoration: leaving the schema narrow drops a
    column the ORM still maps AND a constraint three tests above probe, in a
    shared session-scoped container."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)
    try:
        assert _break_column(migrated_db) == ("timestamp with time zone", "YES")
        assert _role_constraint_def(migrated_db) == _WIDE_ROLE_CHECK_DEF
        command.downgrade(cfg, "0014")
        assert _break_column(migrated_db) is None
        # …and the narrowed CHECK is REBUILT, not merely dropped: the downgrade
        # re-adds 0011's two-value expression, and asserting its presence is what
        # separates "rolled back" from "gave up halfway".
        assert _role_check_exists(migrated_db)
        assert _role_constraint_def(migrated_db) != _WIDE_ROLE_CHECK_DEF
        command.upgrade(cfg, "head")
        assert _break_column(migrated_db) == ("timestamp with time zone", "YES")
        assert _role_constraint_def(migrated_db) == _WIDE_ROLE_CHECK_DEF
    finally:
        command.upgrade(cfg, "head")  # idempotent when already at head


# --- F33: the walk-in queue ticket table ---

_QUEUE_COLUMNS = (
    "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
    "WHERE table_name = 'queue_tickets'"
)
_CUSTOMERS_OPT_IN = (
    "SELECT count(*) FROM information_schema.columns "
    "WHERE table_name = 'customers' AND column_name = 'marketing_opt_in_at'"
)
# Ruling 3's assertion, and it is the one that must never pass by accident: the
# dedup index was a targeted day-long denial of service on one named person AND
# a free, silent presence oracle, and NOTHING in the shipped product can free
# its key (status transitions are F58's, the sweep is F20's). Re-adding any
# uniqueness reddens here rather than quietly restoring both defects.
_QUEUE_UNIQUE_INDEXES = (
    "SELECT count(*) FROM pg_index WHERE indrelid = 'queue_tickets'::regclass "
    "AND indisunique AND NOT indisprimary"
)
_QUEUE_CONSTRAINT_DEF = (
    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
    "WHERE conrelid = 'queue_tickets'::regclass AND conname = :name"
)
_QUEUE_INDEX_DEF = (
    "SELECT indexdef FROM pg_indexes WHERE tablename = 'queue_tickets' AND indexname = :name"
)
_QUEUE_INDEX_NAME = "idx_queue_tickets_tenant_day_active"
_VISIT_TYPE_CHECK = "queue_tickets_visit_type_check"
_STATUS_CHECK = "queue_tickets_status_check"
_SKIP_COUNT_CHECK = "queue_tickets_skip_count_check"
# Spelled as POSTGRES deparses them, not as the migration wrote them: both
# pg_get_constraintdef and pg_indexes.indexdef normalise (IN (...) becomes
# = ANY (ARRAY[...]), every element gains a ::text cast, predicates get
# parenthesised and the schema is qualified). CAPTURED from a real 16.x server
# rather than transcribed from the migration source, because a literal that
# merely looks right would pin nothing — which is the whole failure mode this
# test exists to prevent for whoever adds a fifth status next (F58).
_VISIT_TYPE_CHECK_DEF = "CHECK ((visit_type = ANY (ARRAY['bride'::text, 'evening'::text])))"
_STATUS_CHECK_DEF_QUEUE = (
    "CHECK ((status = ANY (ARRAY['waiting'::text, 'in_service'::text, "
    "'done'::text, 'removed'::text])))"
)
_SKIP_COUNT_CHECK_DEF = "CHECK ((skip_count >= 0))"
_QUEUE_INDEX_DEF_PINNED = (
    "CREATE INDEX idx_queue_tickets_tenant_day_active ON public.queue_tickets "
    "USING btree (tenant_id, queue_day) WHERE (deleted_at IS NULL)"
)

_QUEUE_INSERT = (
    "INSERT INTO queue_tickets "
    "(tenant_id, queue_day, name, phone, visit_type, status, skip_count) "
    "VALUES (uuid_generate_v4(), DATE '2026-08-03', 'Probe', '+972501234567', "
    ":visit_type, :status, :skip_count)"
)
_DROP_STATUS_CHECK = f"ALTER TABLE queue_tickets DROP CONSTRAINT {_STATUS_CHECK}"
# The migration's own CHECK expression VERBATIM: the populated-table test proves
# the migration could actually be applied to live data, so it must run the real
# ALTER and not a paraphrase.
_ADD_STATUS_CHECK = (
    f"ALTER TABLE queue_tickets ADD CONSTRAINT {_STATUS_CHECK} "
    "CHECK (status IN ('waiting','in_service','done','removed'))"
)
UNKNOWN_QUEUE_STATUS = "no-such-status"


def _queue_columns(url: str) -> dict[str, tuple[str, str]]:
    async def read() -> dict[str, tuple[str, str]]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                rows = (await conn.execute(text(_QUEUE_COLUMNS))).all()
                return {str(r[0]): (str(r[1]), str(r[2])) for r in rows}
        finally:
            await engine.dispose()

    return asyncio.run(read())


def _queue_pinned_definitions(url: str) -> tuple[str, str, str, str]:
    async def read() -> tuple[str, str, str, str]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                out = []
                for name in (_VISIT_TYPE_CHECK, _STATUS_CHECK, _SKIP_COUNT_CHECK):
                    result = await conn.execute(text(_QUEUE_CONSTRAINT_DEF), {"name": name})
                    out.append(str(result.scalar_one()))
                index = await conn.execute(text(_QUEUE_INDEX_DEF), {"name": _QUEUE_INDEX_NAME})
                out.append(str(index.scalar_one()))
                return (out[0], out[1], out[2], out[3])
        finally:
            await engine.dispose()

    return asyncio.run(read())


def _queue_insert_admitted(url: str, **values: object) -> bool:
    """One INSERT against the three CHECKs, rolled back either way — the
    superuser axis, which reaches the constraint but not the GRANTs or RLS."""
    params: dict = {"visit_type": "bride", "status": "waiting", "skip_count": 0}
    params.update(values)

    async def probe() -> bool:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                trans = await conn.begin()
                try:
                    await conn.execute(text(_QUEUE_INSERT), params)
                except IntegrityError:
                    return False
                finally:
                    await trans.rollback()
                return True
        finally:
            await engine.dispose()

    return asyncio.run(probe())


def _queue_status_check_accepts(url: str, seeded_statuses: list[str]) -> bool:
    """DROP the status CHECK, seed rows, and try to re-add the migration's exact
    expression over them — `_constraint_accepts` above, for the other table.

    Postgres runs DDL transactionally, so each call (the DROP included) rolls
    back whole and the session-scoped container ends as it started."""

    async def probe() -> bool:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                trans = await conn.begin()
                try:
                    await conn.execute(text(_DROP_STATUS_CHECK))
                    for status in seeded_statuses:
                        await conn.execute(
                            text(_QUEUE_INSERT),
                            {"visit_type": "bride", "status": status, "skip_count": 0},
                        )
                    await conn.execute(text(_ADD_STATUS_CHECK))
                    return True
                except DBAPIError as exc:
                    assert _STATUS_CHECK in str(exc)
                    return False
                finally:
                    await trans.rollback()
        finally:
            await engine.dispose()

    return asyncio.run(probe())


@pytest.mark.db
def test_the_queue_tickets_migration_creates_the_scoping_and_consent_columns(
    migrated_db: str,
) -> None:
    """`queue_day` is a stored DATE and not an expression over `created_at` (D4):
    an expression makes the day the DATABASE's clock, and the whole Jerusalem
    boundary suite is only writable because the value comes from the injectable
    Clock instead.

    `marketing_opt_in_at` is nullable — NULL is the only "no consent on record"
    sentinel, so a default or a NOT NULL would have to invent a second one."""
    columns = _queue_columns(migrated_db)
    assert columns["queue_day"] == ("date", "NO")
    assert columns["marketing_opt_in_at"] == ("timestamp with time zone", "YES")
    assert columns["skip_count"] == ("integer", "NO")
    assert columns["called_at"] == ("timestamp with time zone", "YES")
    assert columns["requeued_at"] == ("timestamp with time zone", "YES")


@pytest.mark.db
def test_customers_gained_no_marketing_consent_column(migrated_db: str) -> None:
    """Ruling 2: the consent timestamp lands on `queue_tickets` and F33 never
    touches `customers` at all. A later reader who "helpfully" re-adds the ADD
    COLUMN half reddens here instead of quietly reopening the write path — the
    one whose overwrite-the-name behaviour was the forgery vector."""

    async def read() -> int:
        engine = create_async_engine(migrated_db)
        try:
            async with engine.connect() as conn:
                return int((await conn.execute(text(_CUSTOMERS_OPT_IN))).scalar_one())
        finally:
            await engine.dispose()

    assert asyncio.run(read()) == 0


@pytest.mark.db
def test_the_queue_tickets_migration_pins_its_checks_and_its_one_index(migrated_db: str) -> None:
    """The highest-value test in F33, and what it guards is a FUTURE edit.

    Keyed to `head` — i.e. AFTER this feature's migration, whatever number it
    ended up with — and never to a hardcoded revision id, so a literal here would
    not rot the first time another feature lands a migration first.

    The index row is the one that fails loudly if someone re-adds UNIQUE."""
    visit_type, status, skip_count, index = _queue_pinned_definitions(migrated_db)
    assert visit_type == _VISIT_TYPE_CHECK_DEF
    assert status == _STATUS_CHECK_DEF_QUEUE
    assert skip_count == _SKIP_COUNT_CHECK_DEF
    assert index == _QUEUE_INDEX_DEF_PINNED


@pytest.mark.db
def test_queue_tickets_carries_no_unique_index_but_the_primary_key(migrated_db: str) -> None:
    """Ruling 3, as a property of the SCHEMA rather than of a paragraph.

    A later reader who wants uniqueness back must first answer both of the
    findings that killed it: who frees the key when nothing in the shipped
    product can write a status, and what does the refusal disclose about a woman
    whose number a stranger typed in."""

    async def read() -> int:
        engine = create_async_engine(migrated_db)
        try:
            async with engine.connect() as conn:
                return int((await conn.execute(text(_QUEUE_UNIQUE_INDEXES))).scalar_one())
        finally:
            await engine.dispose()

    assert asyncio.run(read()) == 0


@pytest.mark.db
def test_the_queue_checks_admit_exactly_their_enums_and_nothing_else(migrated_db: str) -> None:
    """Iterated from the live enums rather than listing today's values: the day a
    fifth status is added, either the migration widened the CHECK with it and
    this covers it for free, or it did not and this is the red."""
    for visit_type in VisitType:
        assert _queue_insert_admitted(migrated_db, visit_type=visit_type.value), visit_type
    for status in QueueTicketStatus:
        assert _queue_insert_admitted(migrated_db, status=status.value), status
    assert _queue_insert_admitted(migrated_db, skip_count=0)
    assert _queue_insert_admitted(migrated_db, skip_count=7)

    assert not _queue_insert_admitted(migrated_db, visit_type="groom")
    assert not _queue_insert_admitted(migrated_db, status=UNKNOWN_QUEUE_STATUS)
    assert not _queue_insert_admitted(migrated_db, skip_count=-1)


@pytest.mark.db
def test_the_app_role_can_move_a_ticket_to_in_service_but_not_to_an_unknown_status(
    app_role_url: str,
) -> None:
    """The CHECK against the APP role and against UPDATE — the two axes the probe
    above leaves open (it connects as the container superuser and only INSERTs).
    The positive half is also F58's pre-flight: boutique_app really can write a
    status transition past the constraint, under forced RLS, with only its
    GRANTs.

    The leftover row is left under its own random tenant_id holding a LEGAL
    status, which matters twice: every tenant-scoped reader in the suite cannot
    see it (RLS), and the populated-table test below re-adds the status CHECK
    over the whole table and must still succeed with it present."""

    async def check() -> None:
        engine = create_async_engine(app_role_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                ticket = QueueTicket(
                    tenant_id=tenant_id,
                    queue_day=datetime.date(2026, 8, 3),
                    name="Probe",
                    phone="+972501234567",
                    visit_type=VisitType.BRIDE.value,
                )
                session.add(ticket)
                await session.flush()
                ticket_id = ticket.id

            async with tenant_session(factory, tenant_id) as session:
                await session.execute(
                    update(QueueTicket)
                    .where(QueueTicket.id == ticket_id)
                    .values(status=QueueTicketStatus.IN_SERVICE.value)
                )

            # Its own session: the refused statement aborts its transaction, and
            # an aborted transaction cannot be reused for the read-back.
            with pytest.raises(IntegrityError):
                async with tenant_session(factory, tenant_id) as session:
                    await session.execute(
                        update(QueueTicket)
                        .where(QueueTicket.id == ticket_id)
                        .values(status=UNKNOWN_QUEUE_STATUS)
                    )

            async with tenant_session(factory, tenant_id) as session:
                stored = await session.scalar(
                    select(QueueTicket.status).where(QueueTicket.id == ticket_id)
                )
            # The refusal changed nothing — not even partially.
            assert stored == QueueTicketStatus.IN_SERVICE.value
        finally:
            await engine.dispose()

    asyncio.run(check())


@pytest.mark.db
def test_adding_the_queue_status_check_validates_existing_rows(migrated_db: str) -> None:
    """The migration's CHECK arrives with the table, so it cannot fail on live
    data today — but F58 widens this set, and the ALTER it will need is this one.
    Both halves: legal rows present -> the constraint is added; an unknown-status
    row present -> it is REFUSED. Without the second half a NOT VALID constraint
    would pass the first and prove nothing."""
    assert (
        _queue_status_check_accepts(
            migrated_db, [QueueTicketStatus.WAITING.value, QueueTicketStatus.DONE.value]
        )
        is True
    )
    assert _queue_status_check_accepts(migrated_db, [UNKNOWN_QUEUE_STATUS]) is False


@pytest.mark.db
def test_migration_queue_tickets_round_trips(migrated_db: str) -> None:
    """upgrade() creates the table; downgrade() drops it. Runs as the migration
    owner (the app role cannot CREATE TABLE) and mutates the live session-scoped
    schema, so it is LAST among the schema-mutating tests in this file and owns
    no fixtures.

    Probes BOTH directions rather than only the end state, which is 0013's own
    rule: a downgrade that silently no-ops would stay green while shipping a
    migration that cannot be rolled back.

    The target is the revision this one REVISES, which is what `alembic heads`
    answered at build time — never a revision id of F33's own. The finally is not
    decoration: leaving the schema down drops a table the ORM still maps, so
    every later queue db test in the shared container would fail with
    UndefinedTable somewhere unrelated to itself."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)

    def exists() -> bool:
        async def read() -> bool:
            engine = create_async_engine(migrated_db)
            try:
                async with engine.connect() as conn:
                    result = await conn.execute(text(_TABLE_EXISTS), {"name": "queue_tickets"})
                    return bool(result.scalar_one())
            finally:
                await engine.dispose()

        return asyncio.run(read())

    try:
        assert exists()
        command.downgrade(cfg, "0017")
        assert not exists()
        command.upgrade(cfg, "head")
        assert exists()
        assert _queue_columns(migrated_db)["queue_day"] == ("date", "NO")
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


def _column_type(url: str, table: str, column: str) -> tuple[str, str] | None:
    async def read() -> tuple[str, str] | None:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            "SELECT data_type, is_nullable FROM information_schema.columns "
                            "WHERE table_name = :t AND column_name = :c"
                        ),
                        {"t": table, "c": column},
                    )
                ).first()
                return (str(row[0]), str(row[1])) if row else None
        finally:
            await engine.dispose()

    return asyncio.run(read())


def _one(url: str, sql: str, params: dict[str, str] | None = None) -> str | None:
    async def read() -> str | None:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                row = (await conn.execute(text(sql), params or {})).first()
                return str(row[0]) if row else None
        finally:
            await engine.dispose()

    return asyncio.run(read())


@pytest.mark.db
def test_the_deposit_migration_pins_its_two_widened_checks_and_its_new_index(
    migrated_db: str,
) -> None:
    """The F34 discipline applied to F19's own three statements, and for the same
    reason: the next feature that widens one of these should collide with a
    literal and a review rather than with nothing.

    All three are captured from a live 16.x server, never hand-written — Postgres
    deparses `IN (...)` to `= ANY (ARRAY[...])`, parenthesises index predicates
    and schema-qualifies the table, so a transcription of what the migration
    SAYS would pin nothing and redden CI on a green build.

    The index assertion carries the load for D6 claim 2: if the WHERE clause
    stops being partial on 'pending_payment', the orphan sweep silently becomes
    a sequential scan of the whole bookings table on every worker tick.
    """
    assert _one(migrated_db, _STATUS_CONSTRAINT_DEF) == _STATUS_CHECK_DEF
    assert (
        _one(
            migrated_db,
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'bookings'::regclass AND conname = 'bookings_cancelled_by_check'",
        )
        == _CANCELLED_BY_CHECK_DEF
    )
    assert (
        _one(migrated_db, _INDEX_DEF, {"name": "idx_bookings_pending_payment"})
        == _PENDING_PAYMENT_INDEX_DEF
    )


_BOOKING_PROBE_INSERT = (
    "INSERT INTO bookings (tenant_id, customer_id, appointment_type_id, starts_at, seat_index, "
    "terms_version_accepted, terms_accepted_at, appointment_type_name, status, cancelled_by) "
    "VALUES (uuid_generate_v4(), uuid_generate_v4(), uuid_generate_v4(), now(), 1, 1, now(), "
    "'probe', :status, :cancelled_by)"
)


@pytest.mark.db
def test_the_widened_checks_admit_the_new_values_and_still_reject_an_unknown_one(
    migrated_db: str,
) -> None:
    """A CHECK that admits everything is not a widened CHECK, it is a dropped one
    — and the drop-then-add in F19's migration is exactly the shape that fails
    that way if the re-add is malformed. So both halves are asserted for both
    columns: the new value goes in, and a value nobody declared still does not.

    Probes the REAL `bookings` table inside a rolled-back transaction, the
    _STAFF_INSERT pattern already in this file. The first draft of this test
    probed a `CREATE TEMP TABLE (LIKE bookings INCLUDING CONSTRAINTS)` instead
    and was quietly worthless: LIKE copies CHECK constraints but NOT defaults,
    so `created_at` and `status` came through NOT NULL with no default and every
    probe failed on a null violation. Both NEGATIVE assertions then passed for
    entirely the wrong reason, and only the positive one exposed it. A test that
    can pass while proving nothing is worse than no test — hence the real table.

    Every probe supplies `status` explicitly, including the cancelled_by ones:
    relying on the column default would make the cancelled_by halves depend on
    the status CHECK too, and a single failure would no longer localise.
    """

    async def probe() -> list[bool]:
        engine = create_async_engine(migrated_db)
        results: list[bool] = []
        try:
            for status, cancelled_by in (
                ("pending_payment", None),
                ("not_a_real_status", None),
                ("cancelled", "expired"),
                ("cancelled", "not_a_real_actor"),
            ):
                async with engine.connect() as conn:
                    trans = await conn.begin()
                    try:
                        await conn.execute(
                            text(_BOOKING_PROBE_INSERT),
                            {
                                "status": status,
                                "cancelled_by": cancelled_by,
                            },
                        )
                        results.append(True)
                    except (IntegrityError, DBAPIError):
                        results.append(False)
                    finally:
                        await trans.rollback()
            return results
        finally:
            await engine.dispose()

    status_ok, status_junk, cancelled_ok, cancelled_junk = asyncio.run(probe())
    assert status_ok, "the widened status CHECK must admit 'pending_payment'"
    assert not status_junk, "the status CHECK must still reject an undeclared value"
    assert cancelled_ok, "the widened cancelled_by CHECK must admit 'expired'"
    assert not cancelled_junk, "the cancelled_by CHECK must still reject an undeclared value"


@pytest.mark.db
def test_the_deposit_migration_round_trips(migrated_db: str) -> None:
    """Both directions, which is 0013's rule: a downgrade that silently no-ops
    stays green while shipping a migration that cannot be rolled back.

    Owns no fixtures and restores the schema to head in its `finally`, for the
    reason test_migration_0014_round_trips states — the shared session-scoped
    schema is left at head, and leaving it lower drops columns the ORM still
    maps, so every later db test in the session would fail with UndefinedColumn
    somewhere unrelated to itself. That `finally` is also what makes this test
    order-independent, which is why it no longer needs to be last in the file.
    """
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)
    # Resolve THIS migration's own parent, not head's.
    #
    # This read `head.down_revision`, which was the same revision only for as
    # long as the deposit migration WAS head. F53's customer-CRM migration
    # landed on top and the two silently diverged: the downgrade then stopped
    # one revision short, left `payments.redirect_url` in place, and the first
    # assertion after it failed — a test broken by a feature that never touched
    # payments, reported against payments. Identify the revision by WHAT IT IS
    # so the next feature to land on top costs nothing.
    #
    # `down_revision` is typed str | list | tuple because alembic supports merge
    # revisions with several parents. This project has exactly one head
    # (test_exactly_one_migration_head) and no merges, so anything but a plain
    # str here means the history grew a shape no other test in this file expects.
    revisions = ScriptDirectory.from_config(_alembic_config()).walk_revisions()
    deposit = next((s for s in revisions if "deposit" in (s.doc or "").lower()), None)
    assert deposit is not None, "the deposit migration is no longer identifiable by its message"
    down_to = deposit.down_revision
    assert isinstance(down_to, str), f"expected a single-parent revision, got {down_to!r}"
    try:
        assert _column_type(migrated_db, "payments", "redirect_url") == ("text", "YES")
        assert _one(migrated_db, _INDEX_DEF, {"name": "idx_bookings_pending_payment"}) is not None

        command.downgrade(cfg, down_to)

        assert _column_type(migrated_db, "payments", "redirect_url") is None
        assert _one(migrated_db, _INDEX_DEF, {"name": "idx_bookings_pending_payment"}) is None
        assert _one(migrated_db, _STATUS_CONSTRAINT_DEF) != _STATUS_CHECK_DEF
    finally:
        command.upgrade(cfg, "head")


# --- 0017: the customer CRM columns ---

_CUSTOMER_CRM_COLUMNS = (
    "SELECT column_name, data_type, is_nullable, column_default, udt_name "
    "FROM information_schema.columns "
    "WHERE table_name = 'customers' AND column_name IN ('notes', 'tags') "
    "ORDER BY column_name"
)
# Spelled as POSTGRES deparses them, not as 0017 wrote them, and captured from a
# real 16.x cluster rather than transcribed. `data_type` is the bare string
# ARRAY for EVERY array column, which is what makes `udt_name` load-bearing
# rather than padding — without it text[] and int[] are indistinguishable. And
# nobody would have typed "'{}'::text[]" from the migration source.
_NOTES_COLUMN = ("text", "YES", None, "text")
_TAGS_COLUMN = ("ARRAY", "NO", "'{}'::text[]", "_text")


def _customer_crm_columns(url: str) -> dict[str, tuple[str, str, str | None, str]]:
    async def read() -> dict[str, tuple[str, str, str | None, str]]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                rows = (await conn.execute(text(_CUSTOMER_CRM_COLUMNS))).all()
                return {
                    str(row[0]): (
                        str(row[1]),
                        str(row[2]),
                        None if row[3] is None else str(row[3]),
                        str(row[4]),
                    )
                    for row in rows
                }
        finally:
            await engine.dispose()

    return asyncio.run(read())


@pytest.mark.db
def test_migration_0017_round_trips(migrated_db: str) -> None:
    """upgrade() adds a nullable TEXT and a NOT NULL TEXT[] DEFAULT '{}';
    downgrade() drops both. Runs as the migration owner (the app role cannot
    ALTER) and mutates the live session-scoped schema.

    ⚠ **This block used `"-1"` and TWO features broke it independently**, which
    is the deposit block's lesson arriving a second and a third time. "One step
    back from head" survives a RENUMBER of this migration and does not survive
    another feature landing on top of it: `-1` is one step back from CURRENT,
    and current is head. F33 landed 0018 and this test began downgrading THAT —
    dropping queue_tickets, leaving notes and tags in place, and asserting they
    were gone; F36 landed its own 0018 (renumbered to 0019 at this merge) and downgraded the fitting-room tables
    for the same reason. Both are red on the first `pytest -m db` after the
    merge, in a file neither merging branch wrote.

    main pinned the literal `"0016"`; this branch resolves it by IDENTITY —
    `_parent_of` — which survives a renumber as well as a stack, and the literal
    does not.


    Appended at the END of the file, after the env_py test, so it never shares
    an anchor with another feature's block again. It sits after the 0016 block
    that calls itself "LAST among the schema-mutating tests" — that claim is
    about leaving the shared schema at head, which this block's own finally
    also guarantees, so both are order-independent and neither is weakened.

    The finally is not decoration. Leaving the schema down drops two columns the
    ORM still maps, so every later db test in this shared session would fail
    with UndefinedColumn somewhere unrelated to itself."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)
    expected = {"notes": _NOTES_COLUMN, "tags": _TAGS_COLUMN}
    down_to = _parent_of("customer crm")
    try:
        assert _customer_crm_columns(migrated_db) == expected
        command.downgrade(cfg, down_to)
        assert _customer_crm_columns(migrated_db) == {}
        command.upgrade(cfg, "head")
        assert _customer_crm_columns(migrated_db) == expected
    finally:
        command.upgrade(cfg, "head")  # idempotent when already at head


# --- F36: the fitting-room registry, its assignments and its dress bindings ---

_FITTING_TABLES = ("fitting_rooms", "fitting_room_assignments", "fitting_assignment_dresses")
_FITTING_COLUMNS = (
    "SELECT table_name, column_name, data_type, is_nullable, column_default "
    "FROM information_schema.columns WHERE table_name IN "
    "('fitting_rooms', 'fitting_room_assignments', 'fitting_assignment_dresses')"
)
# Deliberately NOT `_INDEX_DEF`, which hardcodes `tablename = 'bookings'`.
_ANY_INDEX_DEF = "SELECT indexdef FROM pg_indexes WHERE indexname = :name"
# Non-primary unique indexes on one table. `indisprimary` is excluded because the
# PK's implicit unique index is not a decision anybody made about this feature.
# CAST(...) rather than `:table::regclass`: SQLAlchemy's text() reads `:table:`
# as a bind parameter followed by a stray colon and ships the colon to Postgres.
_UNIQUE_INDEX_COUNT = (
    "SELECT count(*) FROM pg_index WHERE indrelid = CAST(:table AS regclass) "
    "AND indisunique AND NOT indisprimary"
)
# contype='c' is CHECK. In Postgres 16 a NOT NULL lives in pg_attribute.attnotnull
# and NOT in pg_constraint, so this counts only constraints somebody wrote out —
# which is what makes a `0` here a statement about the design rather than noise.
_CHECK_COUNT = (
    "SELECT count(*) FROM pg_constraint WHERE conrelid = CAST(:table AS regclass) AND contype = 'c'"
)

# Spelled as POSTGRES deparses them, never as the migration wrote them, and
# CAPTURED from the live 16.14 cluster rather than transcribed: `pg_indexes.indexdef`
# schema-qualifies the table, inserts `USING btree`, parenthesises every conjunct of
# the predicate and re-orders nothing it is not asked to. A literal that merely looks
# right pins nothing, and pinning nothing is the entire failure mode these three exist
# to prevent for whoever edits an occupancy predicate next.
_ROOM_ACTIVE_INDEX_DEF = (
    "CREATE UNIQUE INDEX idx_fitting_room_assignments_room_active "
    "ON public.fitting_room_assignments USING btree (tenant_id, fitting_room_id) "
    "WHERE ((released_at IS NULL) AND (deleted_at IS NULL))"
)
_STAFF_ACTIVE_INDEX_DEF = (
    "CREATE UNIQUE INDEX idx_fitting_room_assignments_staff_active "
    "ON public.fitting_room_assignments USING btree (tenant_id, staff_user_id) "
    "WHERE ((released_at IS NULL) AND (deleted_at IS NULL))"
)
_DRESS_BINDING_INDEX_DEF = (
    "CREATE UNIQUE INDEX idx_fitting_assignment_dresses_unique "
    "ON public.fitting_assignment_dresses USING btree "
    "(tenant_id, fitting_room_assignment_id, dress_id) WHERE (deleted_at IS NULL)"
)


def _fitting_columns(url: str) -> dict[tuple[str, str], tuple[str, str, str | None]]:
    async def read() -> dict[tuple[str, str], tuple[str, str, str | None]]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                rows = (await conn.execute(text(_FITTING_COLUMNS))).all()
                return {
                    (str(row[0]), str(row[1])): (
                        str(row[2]),
                        str(row[3]),
                        None if row[4] is None else str(row[4]),
                    )
                    for row in rows
                }
        finally:
            await engine.dispose()

    return asyncio.run(read())


@pytest.mark.db
def test_the_fitting_rooms_migration_creates_the_three_tables(migrated_db: str) -> None:
    """The shapes D1, D2 and D4 argue for, read back off the catalog.

    Only the columns those three sections make a decision about are asserted;
    the five StandardColumns are proved by the models importing at all and by
    every other db module in this suite. What is here is what a later reader
    would otherwise have to take on trust: that `released_at` is NULLABLE (it is
    the occupancy model — a NOT NULL would make an active assignment
    unrepresentable), that `sort_order` and `is_active` carry the defaults that
    let the registry dialog omit them, and that `dress_size` and `removed_by`
    are nullable because a gown can be carried in before a size is chosen and a
    live binding has no remover yet.
    """
    columns = _fitting_columns(migrated_db)
    assert columns[("fitting_rooms", "label")] == ("text", "NO", None)
    assert columns[("fitting_rooms", "sort_order")] == ("integer", "NO", "0")
    assert columns[("fitting_rooms", "is_active")] == ("boolean", "NO", "true")

    assert columns[("fitting_room_assignments", "fitting_room_id")] == ("uuid", "NO", None)
    assert columns[("fitting_room_assignments", "staff_user_id")] == ("uuid", "NO", None)
    assert columns[("fitting_room_assignments", "booking_id")] == ("uuid", "YES", None)
    assert columns[("fitting_room_assignments", "released_at")] == (
        "timestamp with time zone",
        "YES",
        None,
    )

    assert columns[("fitting_assignment_dresses", "fitting_room_assignment_id")] == (
        "uuid",
        "NO",
        None,
    )
    assert columns[("fitting_assignment_dresses", "dress_id")] == ("uuid", "NO", None)
    assert columns[("fitting_assignment_dresses", "dress_name")] == ("text", "NO", None)
    assert columns[("fitting_assignment_dresses", "dress_size")] == ("text", "YES", None)
    assert columns[("fitting_assignment_dresses", "removed_by")] == ("uuid", "YES", None)


@pytest.mark.db
def test_the_three_partial_unique_index_definitions_are_pinned(migrated_db: str) -> None:
    """The highest-value test in the feature, and what it guards is a FUTURE edit.

    These three indexes ARE the feature: one active assignment per room, one
    active room per worker, one live binding per (assignment, dress). None of
    them is enforced anywhere in application code — D3 argues at length that a
    unique index is evaluated by the index rather than against a transaction
    snapshot, which is exactly why no lock is taken. Delete a conjunct from a
    predicate and every test that exercises the happy path stays green while the
    guarantee is gone.

    So the whole definition is pinned byte-identical, F34's discipline applied to
    the three statements that carry F36's entire structural claim. The pinned
    mutation is narrowing either assignment predicate to `deleted_at IS NULL`
    alone: `released_at` is the conjunct with a writer (D2 — `deleted_at` on that
    table has no v1 writer at all), so dropping it makes a released room
    permanently unclaimable and nothing else in the suite notices.

    The three NON-unique indexes are performance and are deliberately not pinned:
    an index that only makes a read faster should be free to be re-tuned.
    """
    assert (
        _one(migrated_db, _ANY_INDEX_DEF, {"name": "idx_fitting_room_assignments_room_active"})
        == _ROOM_ACTIVE_INDEX_DEF
    )
    assert (
        _one(migrated_db, _ANY_INDEX_DEF, {"name": "idx_fitting_room_assignments_staff_active"})
        == _STAFF_ACTIVE_INDEX_DEF
    )
    assert (
        _one(migrated_db, _ANY_INDEX_DEF, {"name": "idx_fitting_assignment_dresses_unique"})
        == _DRESS_BINDING_INDEX_DEF
    )


@pytest.mark.db
def test_fitting_room_assignments_carries_exactly_two_non_primary_unique_indexes(
    migrated_db: str,
) -> None:
    """The half that catches an ADDITION, where the test above catches an edit.

    A well-meant `(tenant_id, booking_id)` unique index added later reads as
    "one open fitting per booking" and is wrong: a bride's second fitting of the
    same day is an ordinary event, and she would be refused with a 500 nobody
    can explain. No other test anywhere in the suite would fail — the happy
    path, the races and the payload read are all indifferent to an extra index
    until the day a real boutique produces the second row.

    Counting is what makes an addition visible. Both figures are exact, and the
    `fitting_rooms` zero is D1's no-unique-label decision asserted rather than
    left as prose: a `(tenant_id, label)` unique added later would mean a
    boutique with two alcoves it genuinely both calls «הבמה» meets a 409 the
    product never designed a sentence for.
    """
    assert _one(migrated_db, _UNIQUE_INDEX_COUNT, {"table": "fitting_room_assignments"}) == "2"
    assert _one(migrated_db, _UNIQUE_INDEX_COUNT, {"table": "fitting_rooms"}) == "0"


@pytest.mark.db
def test_fitting_assignment_dresses_carries_exactly_one(migrated_db: str) -> None:
    """The same count on the child table. One live binding per (assignment,
    dress) — and its partial predicate is what lets a removed dress be carried
    back into the room, so a second unique index here would break the re-add."""
    assert _one(migrated_db, _UNIQUE_INDEX_COUNT, {"table": "fitting_assignment_dresses"}) == "1"


@pytest.mark.db
def test_the_fitting_room_tables_carry_no_check_constraints(migrated_db: str) -> None:
    """A CHECK-free table is a DECISION here, so it is asserted rather than
    assumed.

    There is no status column anywhere in this feature: `released_at IS NULL AND
    deleted_at IS NULL` is what active means and it is the whole model (D2). The
    neighbouring `bookings` table carries three CHECKs and is the obvious thing
    to copy, so a later reader reaching for `status TEXT CHECK (...)` on an
    assignment meets an assertion and this docstring instead of nothing.

    `bookings` is asserted non-zero in the same breath, because a query that
    silently matched nothing would make all three zeros vacuous.
    """
    for table in _FITTING_TABLES:
        assert _one(migrated_db, _CHECK_COUNT, {"table": table}) == "0", table
    assert _one(migrated_db, _CHECK_COUNT, {"table": "bookings"}) != "0"


def _fitting_tables_present(url: str) -> list[str]:
    async def read() -> list[str]:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public' AND table_name IN "
                            "('fitting_rooms', 'fitting_room_assignments', "
                            "'fitting_assignment_dresses') ORDER BY table_name"
                        )
                    )
                ).scalars()
                return [str(row) for row in rows]
        finally:
            await engine.dispose()

    return asyncio.run(read())


@pytest.mark.db
def test_the_fitting_rooms_migration_round_trips(migrated_db: str) -> None:
    """Both directions, which is 0013's rule: a downgrade that silently no-ops
    stays green while shipping a migration that cannot be rolled back. F36's
    downgrade is three DROP TABLEs and nothing else — it touches no existing
    table, so unlike F57's it cannot fail on live data.

    The downgrade target is resolved by IDENTITY, never as a literal and never
    as `-1`. This migration's number is resolved from `alembic heads` at build
    time and renumbered at the rebase that precedes the push, so a literal would
    rot in the one hour it matters — and `-1` would rot the day F58 lands its
    `queue_ticket_id` migration on top, which is scheduled.

    The finally is not decoration. Leaving the schema down drops three tables the
    ORM still maps, so every later db test in this shared session would fail with
    UndefinedTable somewhere unrelated to itself.
    """
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)
    down_to = _parent_of("fitting rooms")
    try:
        assert _fitting_tables_present(migrated_db) == sorted(_FITTING_TABLES)
        command.downgrade(cfg, down_to)
        assert _fitting_tables_present(migrated_db) == []
        command.upgrade(cfg, "head")
        assert _fitting_tables_present(migrated_db) == sorted(_FITTING_TABLES)
    finally:
        command.upgrade(cfg, "head")  # idempotent when already at head
