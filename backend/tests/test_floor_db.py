"""F57 against real Postgres as the non-owner app role (`boutique_app`).

**The break writers.** `start_break` and `end_break` are idempotent by predicate
and classify off the database, never off the object they just wrote — the
identity-map trap this repo has documented three times
(`db/repositories/bookings.py`, `booking/owner.py`, and
`test_booking_owner_db.py`'s pinned docstring). Every assertion below is on BOTH
halves of the returned tuple, because the `wrote` flag and the rendered row fail
independently: dropping `populate_existing=True` leaves the flag right and the
row wrong.

⚠ **Every row this module COMMITS holds `owner` or `shift_manager`, never a floor
role**, and that is a hard rule rather than a preference. `migrated_db` and
`app_role_url` are `scope="session"`, so one container is shared by every
db-marked module, and pytest collects files alphabetically — `test_floor_db.py`
sorts BEFORE `test_migrations.py`. A committed `reception` row reddens three
tests there, including
`test_adding_the_role_check_validates_existing_rows`, which has nothing to do
with breaks and whose failure names 0011's constraint.

This module cannot roll back the way `test_migrations.py`'s probes do — exiting
`tenant_session` IS the commit (`db/tenant.py:25`), the forced interleave holds
one session open across another's whole transaction by construction, and the
isolation probe needs a persisted second-tenant row. So the SEED ROLE is what
gives instead of the rule. Nothing here asserts anything about the actor's role:
break toggling is role-independent at the repository layer and RLS isolation is
about `tenant_id`. The role gate is `test_floor_service.py`'s and
`test_staff_role_gating.py`'s job.

Every test mints its own tenant id: the container is session-scoped and nothing
here truncates.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.service import StaffContext
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.floor.service import FloorService
from app.models.audit_log import AuditLog
from app.models.constants import AuditAction, StaffRole

pytestmark = pytest.mark.db

# Frozen module constants rather than a real clock: every assertion below is an
# equality on the stored value, and `now()` would make them all approximate.
NOW = datetime(2026, 8, 2, 11, 20, tzinfo=UTC)
LATER = datetime(2026, 8, 2, 13, 45, tzinfo=UTC)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


def _email() -> str:
    return f"floor-{uuid.uuid4().hex[:10]}@bella.example"


async def _seed_staff(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    display_name: str = "Staff",
    role: str = StaffRole.OWNER.value,
) -> uuid.UUID:
    """Seeds `owner` by default and takes only `owner` / `shift_manager` — see
    the module docstring. The role is a parameter at all because the ordering
    test wants two distinguishable rows, not because anything here reads it."""
    assert role in {StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value}, (
        "this module COMMITS its rows; a floor role here reddens test_migrations.py"
    )
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=_email(),
            password_hash="not-a-real-hash",
            display_name=display_name,
            role=role,
        )
        return staff.id


# --- the two writers ---


async def test_a_start_writes_the_timestamp_and_reports_the_write(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.start_break(session, tenant_id, staff_id, at=NOW)
        assert wrote is True
        assert row is not None
        assert row.break_started_at == NOW

        # Re-read in its OWN session, so the assertion cannot be satisfied by the
        # instance the write left in the first session's identity map.
        async with tenant_session(factory, tenant_id) as session:
            stored = await repo.by_id(session, tenant_id, staff_id)
        assert stored is not None
        assert stored.break_started_at == NOW
    finally:
        await engine.dispose()


async def test_a_second_start_keeps_the_first_timestamp_and_reports_no_write(
    app_role_url: str,
) -> None:
    """The idempotency predicate, on BOTH halves of the tuple. `break_started_at
    IS NULL` in the WHERE is what makes a second staffer's tap keep the FIRST
    timestamp rather than move it — and the row that comes back must carry that
    first value, not the `at` this call passed in. Dropping
    `populate_existing=True` leaves `wrote` correct and this assertion red, which
    is the whole reason it is asserted separately."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await repo.start_break(session, tenant_id, staff_id, at=NOW)
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.start_break(session, tenant_id, staff_id, at=LATER)
        assert wrote is False
        assert row is not None
        assert row.break_started_at == NOW
    finally:
        await engine.dispose()


async def test_an_end_clears_the_timestamp_and_reports_the_write(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await repo.start_break(session, tenant_id, staff_id, at=NOW)
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.end_break(session, tenant_id, staff_id)
        assert wrote is True
        assert row is not None
        assert row.break_started_at is None

        async with tenant_session(factory, tenant_id) as session:
            stored = await repo.by_id(session, tenant_id, staff_id)
        assert stored is not None
        assert stored.break_started_at is None
    finally:
        await engine.dispose()


async def test_a_second_end_reports_no_write_and_still_renders_the_row(
    app_role_url: str,
) -> None:
    """Zero rows with a LIVE row back means the target state already holds. That
    is a 200-unchanged and not an error, which is exactly why this returns a
    `(bool, row)` pair rather than F34's four-member `CheckInOutcome`: a break has
    no status guard, so there is no second, opposite cause of zero rows for a
    third member to name."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.end_break(session, tenant_id, staff_id)
        assert wrote is False
        assert row is not None
        assert row.break_started_at is None
    finally:
        await engine.dispose()


async def test_both_writers_miss_a_soft_deleted_target(app_role_url: str) -> None:
    """`(False, None)` — the pair the service maps to 404. `deleted_at IS NULL`
    is in the UPDATE predicate AND in the re-read, so a deactivated colleague is
    indistinguishable from one who never existed."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await repo.soft_delete(session, tenant_id, staff_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.start_break(session, tenant_id, staff_id, at=NOW) == (False, None)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.end_break(session, tenant_id, staff_id) == (False, None)
    finally:
        await engine.dispose()


async def test_both_writers_miss_an_unknown_id(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        missing = uuid.uuid4()
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.start_break(session, tenant_id, missing, at=NOW) == (False, None)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.end_break(session, tenant_id, missing) == (False, None)
    finally:
        await engine.dispose()


async def test_list_live_carries_the_break_column_and_no_soft_deleted_row(
    app_role_url: str,
) -> None:
    """The floor read is `list_live`, unchanged and unwidened — F57 adds no
    reader. What this pins is that the new column travels with it and that the
    shipped `deleted_at IS NULL` still holds now that a second surface depends on
    it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        available = await _seed_staff(factory, tenant_id, display_name="Available")
        resting = await _seed_staff(factory, tenant_id, display_name="Resting")
        gone = await _seed_staff(factory, tenant_id, display_name="Gone")
        async with tenant_session(factory, tenant_id) as session:
            await repo.start_break(session, tenant_id, resting, at=NOW)
            await repo.soft_delete(session, tenant_id, gone)

        async with tenant_session(factory, tenant_id) as session:
            rows = await repo.list_live(session, tenant_id)
        assert [row.id for row in rows] == [available, resting]
        assert [row.break_started_at for row in rows] == [None, NOW]
    finally:
        await engine.dispose()


# --- the forced interleave, and why it is not asyncio.gather -----------------
#
# `asyncio.gather` is deliberately NOT used here, for F34's reason verbatim
# (`test_booking_owner_db.py:1313-1336`): gather does not ORDER two
# transactions, so the loser most often loads AFTER the winner commits, the
# in-memory instance is then already correct, and the zero-row branch these
# tests exist to prove goes green without the mechanism ever being exercised.
#
# The mechanism: `tenant_session` is `async with session_factory() as session,
# session.begin()`, so EXITING the context manager IS the commit
# (`db/tenant.py:25`), and two nested tenant_sessions on one NullPool factory
# take two separate connections. Under READ COMMITTED the loser's UPDATE and
# its re-read both see the winner's committed write.


async def test_a_second_start_landing_in_the_gap_renders_the_winners_timestamp(
    app_role_url: str,
) -> None:
    """⚠ THE MUTATION-CHECK TARGET. This is the ONLY test in the feature that
    fails when `populate_existing=True` is removed from
    `StaffUsersRepository._refreshed`, and every other test in this module
    passes without it — verified by running the mutation, not assumed.

    Why the others cannot catch it: they each open a FRESH `tenant_session` per
    operation, so the identity map is empty when the UPDATE runs and there is no
    instance to poison. The bug needs the row LOADED IN THE SAME SESSION that
    then writes — which is precisely the shape `FloorService.end_break` has,
    because it must capture `previous_break_started_at` before the write.

    The poisoning, step by step. The loser loads the row while
    `break_started_at IS NULL`. The winner starts a break at NOW and commits.
    The loser's `UPDATE ... WHERE break_started_at IS NULL` now matches ZERO
    rows — but `update(StaffUser)` is ORM-enabled DML whose default `evaluate`
    synchronization re-evaluates that predicate IN PYTHON against the
    identity-mapped instance, which still reads None, so it stamps
    `break_started_at = LATER` onto an object the database never touched. With
    `expire_on_commit=False` (`db/session.py:66`) a plain re-read hands that
    object straight back.

    So without the flag this returns `(False, <row claiming LATER>)`: the panel
    would render the LOSING staffer's timestamp on a break she did not start,
    and «מאז 13:45» would be shown for a break that began at 11:20.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)

        # The LOSER's session, held open across the winner's whole transaction.
        async with tenant_session(factory, tenant_id) as loser:
            loaded = await repo.by_id(loser, tenant_id, staff_id)
            assert loaded is not None
            assert loaded.break_started_at is None  # the predicate WOULD match

            # The WINNER commits in a second session. Exiting this block is the
            # commit.
            async with tenant_session(factory, tenant_id) as winner:
                won, _ = await repo.start_break(winner, tenant_id, staff_id, at=NOW)
                assert won is True

            # Only now does the loser's guarded UPDATE run. Zero rows.
            wrote, row = await repo.start_break(loser, tenant_id, staff_id, at=LATER)

        assert wrote is False
        assert row is not None
        # The DATABASE's value, not this request's own intent.
        assert row.break_started_at == NOW
        assert row.break_started_at != LATER

        # …and nothing was written, read back on a fresh connection.
        async with tenant_session(factory, tenant_id) as session:
            stored = await repo.by_id(session, tenant_id, staff_id)
        assert stored is not None
        assert stored.break_started_at == NOW
    finally:
        await engine.dispose()


async def test_an_end_landing_in_the_gap_after_a_concurrent_end_writes_nothing(
    app_role_url: str,
) -> None:
    """The other direction of the same race. The loser's `IS NOT NULL` predicate
    matches zero rows because the winner already cleared it, so the second
    manager's tap is a no-op rather than an error — and the row she renders is
    the cleared one.

    This one does NOT discriminate `populate_existing` (evaluate stamps None,
    which is what the database says anyway), and it is here for the `(False,
    row)` mapping under a real race rather than as a second mutation target.
    Stated so a later reader does not mistake it for one.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await repo.start_break(session, tenant_id, staff_id, at=NOW)

        async with tenant_session(factory, tenant_id) as loser:
            loaded = await repo.by_id(loser, tenant_id, staff_id)
            assert loaded is not None
            assert loaded.break_started_at == NOW

            async with tenant_session(factory, tenant_id) as winner:
                won, _ = await repo.end_break(winner, tenant_id, staff_id)
                assert won is True

            wrote, row = await repo.end_break(loser, tenant_id, staff_id)

        assert wrote is False
        assert row is not None
        assert row.break_started_at is None
    finally:
        await engine.dispose()


# --- the service path, against a REAL identity map ---------------------------


async def test_the_end_audit_row_carries_the_timestamp_the_break_actually_started(
    app_role_url: str,
) -> None:
    """⚠ The one assertion in the feature that `test_floor_service.py` CANNOT
    make, and the reason this test exists in the db module instead.

    That module drives the service against monkeypatched repositories, so no
    ORM-enabled UPDATE ever runs and no instance is ever stamped — it proves the
    service passes the value it captured, not that the value was still there to
    capture. Here the write is real.

    `FloorService.end_break` calls `by_id` and then `end_break` IN ONE SESSION.
    Both hand back the same instance out of one identity map, and the UPDATE's
    `evaluate` synchronization sets `break_started_at = NULL` on it. So a service
    that read `before.break_started_at` AFTER the write — the natural way to
    write it — would record `previous_break_started_at: null` on every single
    end, and the audit row would say a break stopped without saying what stopped.
    Nothing else in the suite would go red.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await repo.start_break(session, tenant_id, staff_id, at=NOW)

        actor = StaffContext(
            id=staff_id,
            tenant_id=tenant_id,
            email="owner@bella.example",
            display_name="Staff",
            role=StaffRole.OWNER.value,
        )
        # F36 gave both break writers a second return value: the room this
        # staffer is standing in, or None. The card's `occupied` is derived from
        # it, so the route cannot answer «פנויה» about somebody in room 2.
        row, occupancy = await FloorService(factory, clock=lambda: LATER).end_break(
            tenant_id, staff_id, actor=actor
        )
        assert row.break_started_at is None
        assert occupancy is None

        async with tenant_session(factory, tenant_id) as session:
            rows = list(
                (
                    await session.execute(
                        select(AuditLog).where(AuditLog.action == AuditAction.STAFF_BREAK_ENDED)
                    )
                )
                .scalars()
                .all()
            )
        assert len(rows) == 1
        assert rows[0].details == {
            "target": str(staff_id),
            "previous_break_started_at": NOW.isoformat(),
        }
    finally:
        await engine.dispose()


# --- RLS isolation ----------------------------------------------------------


async def test_another_tenants_staffer_can_neither_be_read_nor_toggled(
    app_role_url: str,
) -> None:
    """Every tenant table in this repo carries an isolation probe and
    `staff_users` is no exception just because F57 adds no table — F57 adds two
    WRITERS to it, and the shipped probe
    (`test_staff_management_db.py:611`) covers F51's verbs, not these.

    The session is bound to tenant B while the ARGUMENTS name tenant A, so a
    pass here is RLS doing the work and not the repository's redundant
    `tenant_id` predicate: with the policy off, the predicate alone would still
    let `tenant_id == A` through on B's connection. Both writers must answer
    `(False, None)` — the pair the service maps to 404, indistinguishable from a
    staffer who never existed.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        theirs = await _seed_staff(factory, elsewhere, display_name="Theirs")
        await _seed_staff(factory, here, display_name="Mine")

        async with tenant_session(factory, here) as session:
            assert await repo.by_id(session, elsewhere, theirs) is None
            assert await repo.start_break(session, elsewhere, theirs, at=NOW) == (False, None)
            assert await repo.end_break(session, elsewhere, theirs) == (False, None)
            assert [row.display_name for row in await repo.list_live(session, here)] == ["Mine"]

        # The foreign row is untouched — a silent cross-tenant write would
        # otherwise look identical to a correctly refused one.
        async with tenant_session(factory, elsewhere) as session:
            survivor = await repo.by_id(session, elsewhere, theirs)
        assert survivor is not None
        assert survivor.break_started_at is None
    finally:
        await engine.dispose()
