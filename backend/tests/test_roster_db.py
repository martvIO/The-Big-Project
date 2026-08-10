"""F40's roster tables against a real Postgres — the partial unique indexes, the
on-shift join and the edited-since predicate.

⚠ db-marked, and this box has no Docker — set TEST_POSTGRES_SUPERUSER_URL at a
throwaway local PG16 to run them (conftest.postgres_url documents the setup).

⚠ EVERY FIXTURE WEEK IS BUILT THROUGH `current_week_start`, NEVER FROM A
LITERAL. `rosters_week_start_check` refuses anything but a Jerusalem Sunday, so a
week built from `date.today()` trips it six days out of seven — the known
0-collected-red trap this suite exists on the right side of.

⚠ CONNECTED AS THE NON-OWNER `boutique_app` ROLE over a NullPool engine, never
the superuser one: a superuser bypasses RLS and would make the isolation half of
this feature pass vacuously. The concurrency tests need NullPool for their own
reason — `asyncio.gather` over a pooled engine hands both coroutines the same
connection and the race never happens.
"""

import asyncio
import datetime
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.repositories.roster_assignments import RosterAssignmentsRepository
from app.db.repositories.rosters import RostersRepository
from app.db.repositories.shift_templates import ShiftTemplatesRepository
from app.db.tenant import tenant_session
from app.models.constants import AvailabilityState
from app.shifts.validation import current_week_start, jerusalem_moment

pytestmark = pytest.mark.db

# 10:00 Sunday in Jerusalem, expressed as the UTC instant the resolver receives.
AT = datetime.datetime(2026, 11, 8, 8, 0, tzinfo=datetime.UTC)
LOCAL_DATE, LOCAL_TIME, DAY_INDEX = jerusalem_moment(AT)
WEEK = current_week_start(LOCAL_DATE)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def _engine(app_role_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine, factory = _factory(app_role_url)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _db_now(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> datetime.datetime:
    """`clock_timestamp()`, not `now()`: `now()` is the TRANSACTION start time, so
    a marker read with it can land BEFORE rows written earlier in a
    later-starting transaction, and `changed_since` would then report an edit
    nobody made."""
    async with tenant_session(factory, tenant_id) as session:
        value = (await session.execute(text("SELECT clock_timestamp()"))).scalar_one()
        assert isinstance(value, datetime.datetime)
        return value


async def _template(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    day_of_week: int = DAY_INDEX,
    starts: datetime.time = datetime.time(9, 0),
    ends: datetime.time = datetime.time(14, 0),
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await ShiftTemplatesRepository().insert(
            session,
            tenant_id=tenant_id,
            day_of_week=day_of_week,
            label="משמרת בוקר",
            starts_at_time=starts,
            ends_at_time=ends,
        )
        return row.id


async def _roster(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    week_start: datetime.date = WEEK,
    published: bool = False,
) -> uuid.UUID:
    repo = RostersRepository()
    async with tenant_session(factory, tenant_id) as session:
        row = await repo.create(session, tenant_id=tenant_id, week_start=week_start)
        roster_id = row.id
    if published:
        async with tenant_session(factory, tenant_id) as session:
            await repo.stamp_published(
                session,
                tenant_id,
                roster_id,
                at=datetime.datetime.now(datetime.UTC),
                by=uuid.uuid4(),
            )
    return roster_id


async def _assign(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    roster_id: uuid.UUID,
    template_id: uuid.UUID,
    staff_user_id: uuid.UUID,
    is_shift_manager: bool = False,
    override_of_state: str | None = None,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await RosterAssignmentsRepository().insert(
            session,
            tenant_id=tenant_id,
            roster_id=roster_id,
            shift_template_id=template_id,
            staff_user_id=staff_user_id,
            assigned_by=uuid.uuid4(),
            is_shift_manager=is_shift_manager,
            override_of_state=override_of_state,
        )
        return row.id


# --- the week key and the round trip ------------------------------------------


def test_the_fixture_instant_is_a_sunday_morning_in_jerusalem() -> None:
    """The whole file rests on it, so it is asserted rather than assumed —
    `rosters_week_start_check` refuses a non-Sunday key outright."""
    assert DAY_INDEX == 0
    assert LOCAL_TIME.isoformat() == "10:00:00"
    assert WEEK == LOCAL_DATE


async def test_a_roster_round_trips_as_a_draft_and_then_as_published(app_role_url: str) -> None:
    """`published_at IS NULL` is DRAFT and it is the only other state (D6)."""
    tenant_id = uuid.uuid4()
    repo = RostersRepository()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            row = await repo.by_week(session, tenant_id, WEEK)
            assert row is not None
            assert (row.id, row.published_at, row.published_by) == (roster_id, None, None)

        at = datetime.datetime.now(datetime.UTC)
        who = uuid.uuid4()
        async with tenant_session(factory, tenant_id) as session:
            stamped = await repo.stamp_published(session, tenant_id, roster_id, at=at, by=who)
            assert stamped is not None
            assert stamped.published_by == who
            assert stamped.published_at is not None

        async with tenant_session(factory, tenant_id) as session:
            # And a week with no row at all is None, which is rule 3's input and
            # is NOT the same fact as a draft (D5).
            assert await repo.by_week(session, tenant_id, WEEK + datetime.timedelta(days=7)) is None


async def test_the_week_index_admits_one_live_roster_and_one_after_a_soft_delete(
    app_role_url: str,
) -> None:
    """`idx_rosters_week_unique` is PARTIAL, so a soft-deleted week does not
    block a new one — which is what keeps «remove everything and start again»
    from needing a hard delete."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        await _roster(factory, tenant_id)
        with pytest.raises(IntegrityError):
            await _roster(factory, tenant_id)

        async with tenant_session(factory, tenant_id) as session:
            await session.execute(
                text("UPDATE rosters SET deleted_at = now() WHERE week_start = :w"),
                {"w": WEEK},
            )
        # Now the slot is free again.
        assert await _roster(factory, tenant_id) is not None


async def test_the_assignment_triple_admits_one_live_row_and_one_after_a_soft_delete(
    app_role_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id)
        template_id = await _template(factory, tenant_id)
        staff_id = uuid.uuid4()
        first = await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=staff_id,
        )
        with pytest.raises(IntegrityError):
            await _assign(
                factory,
                tenant_id,
                roster_id=roster_id,
                template_id=template_id,
                staff_user_id=staff_id,
            )

        async with tenant_session(factory, tenant_id) as session:
            removed = await repo.soft_delete(session, tenant_id, first)
            # ⚠ The row is returned AS IT WAS, so the audit row can describe what
            # was removed rather than a row whose `deleted_at` the ORM has just
            # stamped onto the same instance.
            assert removed is not None
            assert removed.staff_user_id == staff_id

        assert await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=staff_id,
        )


async def test_a_soft_deleted_assignment_leaves_every_live_read(app_role_url: str) -> None:
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id)
        template_id = await _template(factory, tenant_id)
        staff_id = uuid.uuid4()
        assignment_id = await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=staff_id,
        )
        async with tenant_session(factory, tenant_id) as session:
            assert len(await repo.by_roster(session, tenant_id, roster_id)) == 1
            await repo.soft_delete(session, tenant_id, assignment_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.by_roster(session, tenant_id, roster_id) == []
            assert await repo.by_id(session, tenant_id, assignment_id) is None
            assert (
                await repo.live_for_triple(
                    session,
                    tenant_id,
                    roster_id=roster_id,
                    shift_template_id=template_id,
                    staff_user_id=staff_id,
                )
                is None
            )
            assert (
                await repo.by_staff_and_roster(
                    session, tenant_id, roster_id=roster_id, staff_user_id=staff_id
                )
                == []
            )


async def test_the_manager_index_admits_exactly_one_per_shift(app_role_url: str) -> None:
    """D12, structurally. Two managers on one shift is not a rule the service
    enforces by reading first — it is a rule the index refuses."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id)
        template_id = await _template(factory, tenant_id)
        await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=uuid.uuid4(),
            is_shift_manager=True,
        )
        with pytest.raises(IntegrityError):
            await _assign(
                factory,
                tenant_id,
                roster_id=roster_id,
                template_id=template_id,
                staff_user_id=uuid.uuid4(),
                is_shift_manager=True,
            )
        # A second NON-manager on the same shift is ordinary and must not be
        # caught by the partial predicate.
        assert await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=uuid.uuid4(),
        )


async def test_the_override_stamp_survives_a_manager_flag_move(app_role_url: str) -> None:
    """`set_manager_flag` names ONE column. Touching `override_of_state` here
    would erase the record of what the owner knowingly did (design F-5)."""
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id)
        template_id = await _template(factory, tenant_id)
        assignment_id = await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=uuid.uuid4(),
            override_of_state=AvailabilityState.UNAVAILABLE.value,
        )
        async with tenant_session(factory, tenant_id) as session:
            moved = await repo.set_manager_flag(
                session, tenant_id, assignment_id, is_shift_manager=True
            )
            assert moved is not None
            assert moved.is_shift_manager is True
            assert moved.override_of_state == AvailabilityState.UNAVAILABLE.value


# --- changed_since ------------------------------------------------------------


async def test_changed_since_is_false_after_a_stamp_and_true_after_an_insert(
    app_role_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id)
        template_id = await _template(factory, tenant_id)
        await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=uuid.uuid4(),
        )
        marker = await _db_now(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.changed_since(session, tenant_id, roster_id, marker) is False

        await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=uuid.uuid4(),
        )
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.changed_since(session, tenant_id, roster_id, marker) is True


async def test_changed_since_sees_a_removal(app_role_url: str) -> None:
    """⚠ THE CASE A NAIVE `MAX(created_at)` MISSES, and the reason `changed_since`
    has no `deleted_at IS NULL` filter. A REMOVAL IS AN EDIT: an owner who takes
    somebody off a published week and presses «פרסום מחדש» must get a stamp and
    an audit row, not a silent no-op."""
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id)
        template_id = await _template(factory, tenant_id)
        assignment_id = await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=uuid.uuid4(),
        )
        marker = await _db_now(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.changed_since(session, tenant_id, roster_id, marker) is False
            await repo.soft_delete(session, tenant_id, assignment_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.changed_since(session, tenant_id, roster_id, marker) is True


async def test_changed_since_sees_a_manager_flag_move(app_role_url: str) -> None:
    """The third kind of edit, and the one that moves no row count at all."""
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id)
        template_id = await _template(factory, tenant_id)
        assignment_id = await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=uuid.uuid4(),
        )
        marker = await _db_now(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await repo.set_manager_flag(session, tenant_id, assignment_id, is_shift_manager=True)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.changed_since(session, tenant_id, roster_id, marker) is True


async def test_changed_since_ignores_another_weeks_roster(app_role_url: str) -> None:
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        this_week = await _roster(factory, tenant_id)
        next_week = await _roster(factory, tenant_id, week_start=WEEK + datetime.timedelta(days=7))
        template_id = await _template(factory, tenant_id)
        marker = await _db_now(factory, tenant_id)
        await _assign(
            factory,
            tenant_id,
            roster_id=next_week,
            template_id=template_id,
            staff_user_id=uuid.uuid4(),
        )
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.changed_since(session, tenant_id, this_week, marker) is False
            assert await repo.changed_since(session, tenant_id, next_week, marker) is True


# --- on_shift_staff_ids: D15's seam -------------------------------------------


async def test_on_shift_staff_ids_returns_only_the_covered_staffers(app_role_url: str) -> None:
    """The SQL twin of `template_covers`, half-open at both ends and keyed on the
    weekday — one statement, and the set it returns is what a later F37/F42
    adoption would `SELECT` over (D15)."""
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id, published=True)
        morning = await _template(factory, tenant_id)  # 09:00–14:00, Sunday
        evening = await _template(
            factory, tenant_id, starts=datetime.time(14, 0), ends=datetime.time(20, 0)
        )
        monday = await _template(factory, tenant_id, day_of_week=1)

        on_now, off_now, wrong_day = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=morning,
            staff_user_id=on_now,
        )
        await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=evening,
            staff_user_id=off_now,
        )
        await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=monday,
            staff_user_id=wrong_day,
        )

        async with tenant_session(factory, tenant_id) as session:
            assert await repo.on_shift_staff_ids(session, tenant_id, AT) == {on_now}


async def test_on_shift_staff_ids_is_half_open_on_the_handover(app_role_url: str) -> None:
    """14:00 belongs to the incoming shift alone. Under a closed interval the
    board would credit the outgoing staffer with it, for one minute a day, in a
    way no functional test would ever notice."""
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id, published=True)
        morning = await _template(factory, tenant_id)
        evening = await _template(
            factory, tenant_id, starts=datetime.time(14, 0), ends=datetime.time(20, 0)
        )
        outgoing, incoming = uuid.uuid4(), uuid.uuid4()
        await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=morning,
            staff_user_id=outgoing,
        )
        await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=evening,
            staff_user_id=incoming,
        )
        # 14:00 Jerusalem, winter, is 12:00Z.
        handover = datetime.datetime(2026, 11, 8, 12, 0, tzinfo=datetime.UTC)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.on_shift_staff_ids(session, tenant_id, handover) == {incoming}


async def test_on_shift_staff_ids_is_empty_for_a_draft_roster(app_role_url: str) -> None:
    """⚠ D6: A DRAFT IS NEVER AUTHORITATIVE, even with assignments on it. The
    empty set here is NOT «nobody is rostered» — the caller tells the two apart by
    asking whether a published `rosters` row exists at all (D5)."""
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id, published=False)
        template_id = await _template(factory, tenant_id)
        await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=uuid.uuid4(),
        )
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.on_shift_staff_ids(session, tenant_id, AT) == set()


async def test_a_soft_deleted_template_stops_resolving(app_role_url: str) -> None:
    """The owner deletes a shift; the assignments against it stop putting anybody
    on the floor, with nothing having to sweep them."""
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id, published=True)
        template_id = await _template(factory, tenant_id)
        staff_id = uuid.uuid4()
        await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=staff_id,
        )
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.on_shift_staff_ids(session, tenant_id, AT) == {staff_id}
            await ShiftTemplatesRepository().soft_delete(session, tenant_id, template_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.on_shift_staff_ids(session, tenant_id, AT) == set()


async def test_a_soft_deleted_assignment_stops_resolving(app_role_url: str) -> None:
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id, published=True)
        template_id = await _template(factory, tenant_id)
        staff_id = uuid.uuid4()
        assignment_id = await _assign(
            factory,
            tenant_id,
            roster_id=roster_id,
            template_id=template_id,
            staff_user_id=staff_id,
        )
        async with tenant_session(factory, tenant_id) as session:
            await repo.soft_delete(session, tenant_id, assignment_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.on_shift_staff_ids(session, tenant_id, AT) == set()


async def test_another_weeks_published_roster_never_answers_for_this_instant(
    app_role_url: str,
) -> None:
    """The week key comes from the LOCAL date, so last week's published roster
    cannot put anybody on this week's floor."""
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    async with _engine(app_role_url) as factory:
        last_week = await _roster(
            factory, tenant_id, week_start=WEEK - datetime.timedelta(days=7), published=True
        )
        template_id = await _template(factory, tenant_id)
        await _assign(
            factory,
            tenant_id,
            roster_id=last_week,
            template_id=template_id,
            staff_user_id=uuid.uuid4(),
        )
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.on_shift_staff_ids(session, tenant_id, AT) == set()


# --- concurrency: the indexes, not a read that raced --------------------------


async def test_two_concurrent_identical_assignments_leave_exactly_one_live_row(
    app_role_url: str,
) -> None:
    """NullPool + `asyncio.gather`, the F13/F39 precedent. Over a pooled engine
    both coroutines get the same connection and the race never happens."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id)
        template_id = await _template(factory, tenant_id)
        staff_id = uuid.uuid4()

        async def write() -> bool:
            try:
                await _assign(
                    factory,
                    tenant_id,
                    roster_id=roster_id,
                    template_id=template_id,
                    staff_user_id=staff_id,
                )
            except IntegrityError:
                return False
            return True

        outcomes = await asyncio.gather(write(), write(), return_exceptions=False)
        assert sorted(outcomes) == [False, True]

        async with tenant_session(factory, tenant_id) as session:
            rows = await RosterAssignmentsRepository().by_roster(session, tenant_id, roster_id)
            assert len(rows) == 1


async def test_two_concurrent_manager_writes_leave_exactly_one(app_role_url: str) -> None:
    """D12's concurrency guard, proved from the INDEX rather than from a read. A
    service that read first and then wrote would let both through under exactly
    this interleaving."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        roster_id = await _roster(factory, tenant_id)
        template_id = await _template(factory, tenant_id)

        async def write(staff_user_id: uuid.UUID) -> bool:
            try:
                await _assign(
                    factory,
                    tenant_id,
                    roster_id=roster_id,
                    template_id=template_id,
                    staff_user_id=staff_user_id,
                    is_shift_manager=True,
                )
            except IntegrityError:
                return False
            return True

        outcomes = await asyncio.gather(write(uuid.uuid4()), write(uuid.uuid4()))
        assert sorted(outcomes) == [False, True]

        async with tenant_session(factory, tenant_id) as session:
            rows = await RosterAssignmentsRepository().by_roster(session, tenant_id, roster_id)
            assert [row.is_shift_manager for row in rows] == [True]
