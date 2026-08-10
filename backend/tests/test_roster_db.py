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

⚠ **THIS MODULE COMMITS INTO A SESSION-SCOPED DATABASE, so no row it commits may
hold a FLOOR ROLE.** `migrated_db` and `app_role_url` are `scope="session"`, and
`test_migrations.py`'s round trips downgrade past the migration that widened
`staff_users_role_check` — a committed `seamstress` row reddens
`test_adding_the_role_check_validates_existing_rows` there, in a file that never
mentions rosters. `test_shifts_db.py` and `test_atelier_db.py` both record the
same trap and the same answer, and `_staff` below refuses a floor role outright
rather than trusting a reader to remember.

**Nothing here depends on a staffer's STORED role except `assigned_by_role`,
which is a grouping and works the same over any two roles.** The authorization
matrix varies the ACTOR's role — resolved from the session cookie and never
looked up — while every committed row stays `owner` or `shift_manager`.
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

from app.auth.dependencies import NotAuthorizedError
from app.auth.service import StaffContext
from app.db.repositories.roster_assignments import RosterAssignmentsRepository
from app.db.repositories.rosters import RostersRepository
from app.db.repositories.shift_templates import ShiftTemplatesRepository
from app.db.repositories.staff_availability import StaffAvailabilityRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.models.constants import AvailabilityState, StaffRole
from app.shifts.schemas import CreateAssignmentRequest
from app.shifts.service import (
    AvailabilityConflictError,
    NotShiftManagerEligibleError,
    ShiftManagerSlotTakenError,
    ShiftNotFoundError,
    ShiftsService,
)
from app.shifts.validation import WeekOutOfRangeError, current_week_start, jerusalem_moment

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
            await repo.stamp_published(session, tenant_id, roster_id, by=uuid.uuid4())
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

        who = uuid.uuid4()
        async with tenant_session(factory, tenant_id) as session:
            stamped = await repo.stamp_published(session, tenant_id, roster_id, by=who)
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


# --- the service, end to end through real rows --------------------------------


def _service(factory: async_sessionmaker[AsyncSession]) -> ShiftsService:
    return ShiftsService(factory, clock=lambda: AT)


def _actor(tenant_id: uuid.UUID, staff_id: uuid.UUID, role: str) -> StaffContext:
    return StaffContext(
        id=staff_id,
        tenant_id=tenant_id,
        email="owner@bella.example",
        display_name="בעלת הבוטיק",
        role=role,
    )


async def _staff(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    role: str = StaffRole.OWNER.value,
    eligible: bool = False,
    display_name: str = "דנה כהן",
    last_day: datetime.date | None = None,
    deleted: bool = False,
) -> uuid.UUID:
    """Seeds `owner` by default and REFUSES a floor role — see the module
    docstring. This module COMMITS, and a floor role here reddens
    `test_migrations.py` in a file that never mentions rosters."""
    assert role in {StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value}, (
        "this module COMMITS its rows; a floor role here reddens test_migrations.py"
    )
    repo = StaffUsersRepository()
    async with tenant_session(factory, tenant_id) as session:
        row = await repo.insert(
            session,
            tenant_id=tenant_id,
            email=f"{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name=display_name,
            role=role,
        )
        row.shift_manager_eligible = eligible
        row.last_day = last_day
        staff_id = row.id
    if deleted:
        async with tenant_session(factory, tenant_id) as session:
            # F38's offboarding sets `last_day` and `deleted_at` in ONE
            # transaction, which is why the repository takes both.
            await repo.soft_delete(session, tenant_id, staff_id, last_day=LOCAL_DATE)
    return staff_id


async def _submit(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    staff_user_id: uuid.UUID,
    template_id: uuid.UUID,
    state: AvailabilityState,
    week: datetime.date = WEEK,
) -> None:
    async with tenant_session(factory, tenant_id) as session:
        await StaffAvailabilityRepository().set_state(
            session,
            tenant_id=tenant_id,
            staff_user_id=staff_user_id,
            shift_template_id=template_id,
            week_start=week,
            state=state.value,
            recorded_by=None,
        )


async def _audit_actions(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[tuple[str, dict[str, object]]]:
    async with tenant_session(factory, tenant_id) as session:
        rows = (
            await session.execute(
                text("SELECT action, details FROM audit_log ORDER BY created_at, action")
            )
        ).all()
        return [(str(row[0]), dict(row[1] or {})) for row in rows]


async def test_the_first_assignment_creates_the_roster_row_in_the_same_transaction(
    app_role_url: str,
) -> None:
    """D5's row is created lazily by the FIRST write, in that write's own
    transaction — so an owner who opens the builder and closes it leaves nothing
    behind, and a failed assignment leaves no orphan week either."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id)
        service = _service(factory)

        async with tenant_session(factory, tenant_id) as session:
            assert await RostersRepository().by_week(session, tenant_id, WEEK) is None

        shift = await service.assign(
            tenant_id,
            actor=_actor(tenant_id, owner, StaffRole.OWNER.value),
            body=CreateAssignmentRequest(
                week_start=WEEK, shift_template_id=template_id, staff_user_id=her
            ),
        )
        assert [row.staff_user_id for row in shift.assignments] == [her]

        async with tenant_session(factory, tenant_id) as session:
            roster = await RostersRepository().by_week(session, tenant_id, WEEK)
            assert roster is not None
            assert roster.published_at is None


async def test_a_failed_assignment_leaves_neither_the_roster_nor_the_row(
    app_role_url: str,
) -> None:
    """The other half of «same transaction»: the `AVAILABILITY_CONFLICT` refusal
    happens AFTER the roster row is created in that transaction, so the rollback
    has to take it with it — otherwise a boutique that never confirms an override
    accumulates empty published-nothing weeks."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id)
        await _submit(
            factory,
            tenant_id,
            staff_user_id=her,
            template_id=template_id,
            state=AvailabilityState.UNAVAILABLE,
        )
        service = _service(factory)

        with pytest.raises(AvailabilityConflictError):
            await service.assign(
                tenant_id,
                actor=_actor(tenant_id, owner, StaffRole.OWNER.value),
                body=CreateAssignmentRequest(
                    week_start=WEEK, shift_template_id=template_id, staff_user_id=her
                ),
            )

        async with tenant_session(factory, tenant_id) as session:
            assert await RostersRepository().by_week(session, tenant_id, WEEK) is None


async def test_an_acknowledged_override_stamps_the_row_and_the_audit_entry(
    app_role_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id, display_name="מיכל ברזילי")
        await _submit(
            factory,
            tenant_id,
            staff_user_id=her,
            template_id=template_id,
            state=AvailabilityState.UNAVAILABLE,
        )
        service = _service(factory)

        shift = await service.assign(
            tenant_id,
            actor=_actor(tenant_id, owner, StaffRole.OWNER.value),
            body=CreateAssignmentRequest(
                week_start=WEEK,
                shift_template_id=template_id,
                staff_user_id=her,
                acknowledge_override=True,
            ),
        )
        assert [row.override_of_state for row in shift.assignments] == [
            AvailabilityState.UNAVAILABLE
        ]

        actions = await _audit_actions(factory, tenant_id)
        assigned = [details for action, details in actions if action == "roster_assigned"]
        assert len(assigned) == 1
        assert assigned[0]["override_of_state"] == AvailabilityState.UNAVAILABLE.value
        # ⚠ IDS ONLY, NEVER A DISPLAY NAME: audit_log has no retention class and
        # platform operators read across tenants.
        assert "מיכל ברזילי" not in str(assigned[0])


async def test_the_upsert_moves_the_manager_flag_and_leaves_the_override_stamp(
    app_role_url: str,
) -> None:
    """Design F-2: without the UPSERT, «make Dana the manager» costs a DELETE and
    a POST — two audit rows, a window in which she is not on the shift at all,
    and the silent loss of her `override_of_state` stamp."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id, eligible=True)
        await _submit(
            factory,
            tenant_id,
            staff_user_id=her,
            template_id=template_id,
            state=AvailabilityState.UNAVAILABLE,
        )
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK,
                shift_template_id=template_id,
                staff_user_id=her,
                acknowledge_override=True,
            ),
        )
        # ⚠ The second call carries NO `acknowledge_override` and must still
        # succeed: the live row is not re-derived, only its flag moves.
        shift = await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK,
                shift_template_id=template_id,
                staff_user_id=her,
                is_shift_manager=True,
            ),
        )
        assert len(shift.assignments) == 1
        assert shift.assignments[0].is_shift_manager is True
        assert shift.assignments[0].override_of_state == AvailabilityState.UNAVAILABLE


async def test_an_upsert_that_changes_nothing_writes_no_audit_row(app_role_url: str) -> None:
    """The shipped no-op rule. A row asserting otherwise names an act nobody
    performed, and «who put whom on which shift» is exactly the question this
    table gets asked."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)
        body = CreateAssignmentRequest(
            week_start=WEEK, shift_template_id=template_id, staff_user_id=her
        )

        await service.assign(tenant_id, actor=actor, body=body)
        await service.assign(tenant_id, actor=actor, body=body)

        actions = [action for action, _ in await _audit_actions(factory, tenant_id)]
        assert actions.count("roster_assigned") == 1


async def test_an_offboarded_staffer_is_absent_from_the_builder_and_is_a_404(
    app_role_url: str,
) -> None:
    """D10's rule reaching F40: a name on this list is a name the owner would
    roster, so a woman who has left is neither offered nor assignable."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        gone = await _staff(factory, tenant_id, deleted=True)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        week = await service.roster(tenant_id, actor=actor, week_start=WEEK)
        assert gone not in [row.id for row in week.staff]

        with pytest.raises(ShiftNotFoundError):
            await service.assign(
                tenant_id,
                actor=actor,
                body=CreateAssignmentRequest(
                    week_start=WEEK, shift_template_id=template_id, staff_user_id=gone
                ),
            )


async def test_the_running_week_and_the_four_behind_it_are_readable_and_writable(
    app_role_url: str,
) -> None:
    """⚠ R-F's guard, end to end. `assert_writable_week` is forward-only and would
    make a RUNNING week un-editable — which is exactly what D7 permits and what
    the same-day override exists NOT to have to substitute for. Every test on a
    future week passes under the wrong helper, so this one names the current week
    and the four behind it."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        for weeks_back in range(5):
            week = WEEK - datetime.timedelta(days=7 * weeks_back)
            template_id = await _template(factory, tenant_id, day_of_week=weeks_back)
            payload = await service.roster(tenant_id, actor=actor, week_start=week)
            assert payload.week_start == week
            shift = await service.assign(
                tenant_id,
                actor=actor,
                body=CreateAssignmentRequest(
                    week_start=week, shift_template_id=template_id, staff_user_id=her
                ),
            )
            assert len(shift.assignments) == 1


async def test_a_week_beyond_the_window_is_refused(app_role_url: str) -> None:
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)
        with pytest.raises(WeekOutOfRangeError):
            await service.roster(
                tenant_id, actor=actor, week_start=WEEK + datetime.timedelta(days=7 * 5)
            )


async def test_a_non_sunday_week_is_refused_by_the_db_check_with_the_guard_removed(
    app_role_url: str,
) -> None:
    """⚠ THE SERVICE GUARD IS NOT THE ONLY GUARD. Written as a raw INSERT so the
    service's `validate_week_start` is genuinely out of the way — the same shape
    `test_shifts_db.py` drives for `staff_availability`."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant_id) as session:
                await session.execute(
                    text("INSERT INTO rosters (tenant_id, week_start) VALUES (:t, :w)"),
                    {"t": tenant_id, "w": WEEK + datetime.timedelta(days=1)},
                )


async def test_the_builder_read_carries_every_state_and_the_eligibility_flag(
    app_role_url: str,
) -> None:
    """The payload the dialog sorts on. An ABSENT key is «not answered» and there
    is no fourth state (D8)."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        morning = await _template(factory, tenant_id)
        evening = await _template(
            factory, tenant_id, starts=datetime.time(14, 0), ends=datetime.time(20, 0)
        )
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        eligible = await _staff(factory, tenant_id, eligible=True, display_name="שירה לוי")
        quiet = await _staff(factory, tenant_id, display_name="נועה כץ")
        await _submit(
            factory,
            tenant_id,
            staff_user_id=eligible,
            template_id=morning,
            state=AvailabilityState.PREFERRED,
        )
        service = _service(factory)

        week = await service.roster(
            tenant_id, actor=_actor(tenant_id, owner, StaffRole.OWNER.value), week_start=WEEK
        )
        refs = {row.id: row for row in week.staff}
        assert refs[eligible].shift_manager_eligible is True
        assert refs[quiet].shift_manager_eligible is False
        assert refs[eligible].states == {str(morning): AvailabilityState.PREFERRED}
        # Absence, not a fourth state.
        assert refs[quiet].states == {}
        assert str(evening) not in refs[eligible].states
        assert [shift.template.id for shift in week.shifts] == [morning, evening]
        assert week.published_at is None
        assert week.edited_since_publish is False


async def test_removing_an_assignment_answers_the_shift_and_audits_the_removal(
    app_role_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        shift = await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK, shift_template_id=template_id, staff_user_id=her
            ),
        )
        assignment_id = shift.assignments[0].id

        after = await service.unassign(tenant_id, actor=actor, assignment_id=assignment_id)
        assert after.assignments == []
        assert after.template.id == template_id

        actions = [action for action, _ in await _audit_actions(factory, tenant_id)]
        assert actions.count("roster_unassigned") == 1

        with pytest.raises(ShiftNotFoundError):
            await service.unassign(tenant_id, actor=actor, assignment_id=assignment_id)


async def test_the_shift_payload_counts_assignments_by_role(app_role_url: str) -> None:
    """`assigned_by_role` is SERVER-computed so the pane's coverage line and the
    server's own shortage count in the publish audit row cannot disagree."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)
        # ⚠ `owner`/`shift_manager` and not a floor role: this module COMMITS.
        # The grouping is what is under test and it works the same over any two.
        for role in (
            StaffRole.OWNER.value,
            StaffRole.OWNER.value,
            StaffRole.SHIFT_MANAGER.value,
        ):
            her = await _staff(factory, tenant_id, role=role)
            shift = await service.assign(
                tenant_id,
                actor=actor,
                body=CreateAssignmentRequest(
                    week_start=WEEK, shift_template_id=template_id, staff_user_id=her
                ),
            )
        assert shift.assigned_by_role == {"owner": 2, "shift_manager": 1}
        assert shift.coverage_targets == {}


@pytest.mark.parametrize(
    "role",
    [StaffRole.RECEPTION.value, StaffRole.SALES_ASSISTANT.value, StaffRole.SEAMSTRESS.value],
)
async def test_a_non_elevated_actor_is_refused_every_roster_verb(
    app_role_url: str, role: str
) -> None:
    """C4/D13 through the service, over real rows: nothing here is owner-only and
    nothing here is open."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        # ⚠ THE ROW IS `owner`; THE ACTOR IS NOT. The guard reads
        # `StaffContext.role`, resolved from the session cookie and never looked
        # up, so the matrix varies freely while the committed row stays legal.
        her = await _staff(factory, tenant_id)
        service = _service(factory)
        actor = _actor(tenant_id, her, role)

        with pytest.raises(NotAuthorizedError):
            await service.roster(tenant_id, actor=actor, week_start=WEEK)
        with pytest.raises(NotAuthorizedError):
            await service.assign(
                tenant_id,
                actor=actor,
                body=CreateAssignmentRequest(
                    week_start=WEEK, shift_template_id=template_id, staff_user_id=her
                ),
            )
        with pytest.raises(NotAuthorizedError):
            await service.unassign(tenant_id, actor=actor, assignment_id=uuid.uuid4())


async def test_a_shift_manager_may_build_the_roster(app_role_url: str) -> None:
    """C4: a shift manager who may assign but not publish has built a roster
    nobody can see, and this console has no submit-for-approval concept."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        manager = await _staff(factory, tenant_id, role=StaffRole.SHIFT_MANAGER.value)
        her = await _staff(factory, tenant_id)
        service = _service(factory)
        actor = _actor(tenant_id, manager, StaffRole.SHIFT_MANAGER.value)

        await service.roster(tenant_id, actor=actor, week_start=WEEK)
        shift = await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK, shift_template_id=template_id, staff_user_id=her
            ),
        )
        assert len(shift.assignments) == 1


async def test_the_manager_slot_refuses_an_ineligible_staffer_and_a_second_holder(
    app_role_url: str,
) -> None:
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        eligible = await _staff(factory, tenant_id, eligible=True)
        also_eligible = await _staff(factory, tenant_id, eligible=True)
        # ⚠ HER JOB IS SHIFT MANAGER AND HER COLUMN IS FALSE — D12's whole
        # point, and the row a role-derived implementation would let through.
        ineligible = await _staff(factory, tenant_id, role=StaffRole.SHIFT_MANAGER.value)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        with pytest.raises(NotShiftManagerEligibleError):
            await service.assign(
                tenant_id,
                actor=actor,
                body=CreateAssignmentRequest(
                    week_start=WEEK,
                    shift_template_id=template_id,
                    staff_user_id=ineligible,
                    is_shift_manager=True,
                ),
            )

        await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK,
                shift_template_id=template_id,
                staff_user_id=eligible,
                is_shift_manager=True,
            ),
        )
        # ⚠ 409 FROM THE PARTIAL UNIQUE INDEX, not from a read that raced.
        with pytest.raises(ShiftManagerSlotTakenError):
            await service.assign(
                tenant_id,
                actor=actor,
                body=CreateAssignmentRequest(
                    week_start=WEEK,
                    shift_template_id=template_id,
                    staff_user_id=also_eligible,
                    is_shift_manager=True,
                ),
            )


# --- publish, republish, and the no-op ----------------------------------------


async def test_publishing_an_unpublished_week_stamps_and_audits(app_role_url: str) -> None:
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(
            factory, tenant_id, role=StaffRole.OWNER.value, display_name="בעלת הבוטיק"
        )
        her = await _staff(factory, tenant_id, display_name="דנה כהן")
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK, shift_template_id=template_id, staff_user_id=her
            ),
        )
        week = await service.publish(tenant_id, actor=actor, week_start=WEEK)
        assert week.published_at is not None
        # ⚠ RESOLVED FROM THE STAFF ROW, not from the acting `StaffContext`: the
        # header says who published it, and that stays true when a different
        # elevated actor opens the pane a week later.
        assert week.published_by_name == "בעלת הבוטיק"
        assert week.edited_since_publish is False

        published = [
            d for a, d in await _audit_actions(factory, tenant_id) if a == "roster_published"
        ]
        assert len(published) == 1
        assert published[0]["republish"] is False
        assert published[0]["assignments"] == 1
        assert published[0]["shortages"] == 0
        # ⚠ IDS AND COUNTS ONLY, NEVER A DISPLAY NAME.
        assert "דנה כהן" not in str(published[0])


async def test_a_publish_that_changes_nothing_writes_no_row(app_role_url: str) -> None:
    """D7's no-op rule. The pane still shows its cue — telling her «nothing
    happened» when the outcome she wanted is the outcome that holds would be
    telling her she was wrong when she was right — but the table does not gain a
    row naming an act nobody performed."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK, shift_template_id=template_id, staff_user_id=her
            ),
        )
        first = await service.publish(tenant_id, actor=actor, week_start=WEEK)
        second = await service.publish(tenant_id, actor=actor, week_start=WEEK)

        assert second.published_at == first.published_at
        assert second.edited_since_publish is False
        actions = [a for a, _ in await _audit_actions(factory, tenant_id)]
        assert actions.count("roster_published") == 1


async def test_a_republish_after_an_edit_restamps_and_audits(app_role_url: str) -> None:
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id)
        also = await _staff(factory, tenant_id)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK, shift_template_id=template_id, staff_user_id=her
            ),
        )
        await service.publish(tenant_id, actor=actor, week_start=WEEK)
        await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK, shift_template_id=template_id, staff_user_id=also
            ),
        )
        # ⚠ THE EDIT DOES NOT MOVE `published_at` (D3's failure mode); it flips
        # the header line instead.
        mid = await service.roster(tenant_id, actor=actor, week_start=WEEK)
        assert mid.published_at is not None
        assert mid.edited_since_publish is True

        await service.publish(tenant_id, actor=actor, week_start=WEEK)
        published = [
            d for a, d in await _audit_actions(factory, tenant_id) if a == "roster_published"
        ]
        assert [row["republish"] for row in published] == [False, True]
        assert published[1]["assignments"] == 2


async def test_a_publish_after_a_removal_counts_as_changed(app_role_url: str) -> None:
    """⚠ A REMOVAL IS AN EDIT, and it is the case a naive `MAX(created_at)`
    misses — the owner takes somebody off a published week and presses «פרסום
    מחדש», and a no-op there would leave the board reporting a woman who is not
    coming."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        shift = await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK, shift_template_id=template_id, staff_user_id=her
            ),
        )
        await service.publish(tenant_id, actor=actor, week_start=WEEK)
        await service.unassign(tenant_id, actor=actor, assignment_id=shift.assignments[0].id)
        await service.publish(tenant_id, actor=actor, week_start=WEEK)

        published = [
            d for a, d in await _audit_actions(factory, tenant_id) if a == "roster_published"
        ]
        assert [row["republish"] for row in published] == [False, True]
        assert published[1]["assignments"] == 0


async def test_a_week_with_no_roster_row_is_publishable_and_says_nobody(
    app_role_url: str,
) -> None:
    """⚠ D5 END TO END. «Published with nobody on it» is a real, deliberate
    statement — it is how an owner says the boutique is closed that Saturday —
    and it is NOT the same fact as «no roster published»: the first answers
    `(False, ROSTER)` for every staffer and the second `(True, FALLBACK)`."""
    tenant_id = uuid.uuid4()
    repo = RosterAssignmentsRepository()
    rosters = RostersRepository()
    async with _engine(app_role_url) as factory:
        await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        async with tenant_session(factory, tenant_id) as session:
            # No roster row at all: rule 3's input.
            assert await rosters.by_week(session, tenant_id, WEEK) is None
            assert await repo.on_shift_staff_ids(session, tenant_id, AT) == set()

        week = await service.publish(tenant_id, actor=actor, week_start=WEEK)
        assert week.published_at is not None
        assert all(shift.assignments == [] for shift in week.shifts)

        async with tenant_session(factory, tenant_id) as session:
            row = await rosters.by_week(session, tenant_id, WEEK)
            assert row is not None and row.published_at is not None
            # Published, and nobody is on: the SET is empty for the same reason
            # as before, but the ROW now exists, which is what rule 2 keys on.
            assert await repo.on_shift_staff_ids(session, tenant_id, AT) == set()


async def test_the_published_read_answers_an_unpublished_week_rather_than_404ing(
    app_role_url: str,
) -> None:
    """D6: «no roster yet» is a real, renderable answer. A 404 would make the
    console branch on a status code to say it."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        payload = await service.published(tenant_id, week_start=WEEK)
        assert payload.published is False
        assert payload.published_at is None
        assert payload.shifts == []
        assert payload.week_start == WEEK

        # A DRAFT with somebody on it answers exactly the same way (D6).
        await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK, shift_template_id=template_id, staff_user_id=her
            ),
        )
        draft = await service.published(tenant_id, week_start=WEEK)
        assert draft.published is False
        assert draft.shifts == []

        await service.publish(tenant_id, actor=actor, week_start=WEEK)
        live = await service.published(tenant_id, week_start=WEEK)
        assert live.published is True
        assert live.published_at is not None
        assert [row.staff_user_id for shift in live.shifts for row in shift.assignments] == [her]


async def test_the_retry_answers_409_when_the_manager_slot_went_in_the_race(
    app_role_url: str,
) -> None:
    """⚠ THE RETRY IS PART OF THE HANDLER, NOT AFTER IT. `assign` catches the
    triple index's `IntegrityError` and runs `_apply_assignment` a second time;
    if THAT attempt hits the manager index the caller must get the same designed
    409 the first attempt would have given her, not a 500.

    The race is forced rather than raced: `live_for_triple` is made to miss ONCE,
    which is exactly the window the retry exists for — the loser of two identical
    inserts sees no live row, inserts, and violates the triple. Here she also
    wants the manager slot, and a third staffer already holds it.

    Measured, not assumed: an INSERT violating BOTH partial uniques is reported
    against whichever index has the lower OID, and `0036` creates the triple
    first — so the first attempt lands on the RETRY branch every time rather than
    on the manager branch. That is what puts the manager conflict on the retry.
    """
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        holder = await _staff(factory, tenant_id, eligible=True, display_name="נועה לוי")
        her = await _staff(factory, tenant_id, eligible=True)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        # A third staffer holds the shift's one manager slot.
        await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK,
                shift_template_id=template_id,
                staff_user_id=holder,
                is_shift_manager=True,
            ),
        )
        # And SHE is already on the shift, as an ordinary assignment.
        await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK, shift_template_id=template_id, staff_user_id=her
            ),
        )

        real = RosterAssignmentsRepository.live_for_triple
        misses = {"left": 1}

        async def _miss_once(self: object, *args: object, **kwargs: object) -> object:
            if misses["left"]:
                misses["left"] -= 1
                return None
            return await real(self, *args, **kwargs)  # type: ignore[arg-type]

        RosterAssignmentsRepository.live_for_triple = _miss_once  # type: ignore[method-assign,assignment]
        try:
            with pytest.raises(ShiftManagerSlotTakenError):
                await service.assign(
                    tenant_id,
                    actor=actor,
                    body=CreateAssignmentRequest(
                        week_start=WEEK,
                        shift_template_id=template_id,
                        staff_user_id=her,
                        is_shift_manager=True,
                    ),
                )
        finally:
            RosterAssignmentsRepository.live_for_triple = real  # type: ignore[method-assign]

        assert misses["left"] == 0, "the forced miss never fired — the race was not reproduced"

        # And the slot still belongs to the holder: a refused retry writes nothing.
        shift = await service.roster(tenant_id, actor=actor, week_start=WEEK)
        managers = [
            row.staff_user_id
            for block in shift.shifts
            for row in block.assignments
            if row.is_shift_manager
        ]
        assert managers == [holder]


async def test_the_open_published_read_carries_no_submitted_state(
    app_role_url: str,
) -> None:
    """⚠ D13's OWN JUSTIFICATION, ASSERTED RATHER THAN NARRATED. The published
    week is open to every role because «the floor board already names every
    colleague, a roster discloses nothing new». `override_of_state` is not
    nothing new — it is the submitted answer, and it is the exact datum that
    gates `/shifts/week/submissions` and the builder read beside it. Shipping it
    on the open route tells a seamstress which named colleagues said they could
    not work and were rostered anyway.

    The BUILDER still carries it (F-5's stamp is the whole point of the pane's
    «שובצה למרות…» line), so this pins the split rather than the field.
    """
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        template_id = await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        await _submit(
            factory,
            tenant_id,
            staff_user_id=her,
            template_id=template_id,
            state=AvailabilityState.UNAVAILABLE,
        )
        await service.assign(
            tenant_id,
            actor=actor,
            body=CreateAssignmentRequest(
                week_start=WEEK,
                shift_template_id=template_id,
                staff_user_id=her,
                acknowledge_override=True,
            ),
        )
        await service.publish(tenant_id, actor=actor, week_start=WEEK)

        builder = await service.roster(tenant_id, actor=actor, week_start=WEEK)
        assigned = [row for shift in builder.shifts for row in shift.assignments]
        assert [row.override_of_state for row in assigned] == [AvailabilityState.UNAVAILABLE]

        open_read = await service.published(tenant_id, week_start=WEEK)
        rows = [row for shift in open_read.shifts for row in shift.assignments]
        # She is on the published roster — the route's whole job — but WHY she is
        # on it is the builder's business.
        assert [row.staff_user_id for row in rows] == [her]
        assert [row.override_of_state for row in rows] == [None]


async def test_her_week_carries_the_published_flag_and_only_her_shifts(
    app_role_url: str,
) -> None:
    """D17's block, and the three distinct facts it renders as three distinct
    sentences (D5): not published; published and she is on nothing; published
    with her shifts."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        morning = await _template(factory, tenant_id)
        evening = await _template(
            factory, tenant_id, starts=datetime.time(14, 0), ends=datetime.time(20, 0)
        )
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        her = await _staff(factory, tenant_id)
        service = _service(factory)
        owner_actor = _actor(tenant_id, owner, StaffRole.OWNER.value)
        her_actor = _actor(tenant_id, her, StaffRole.SEAMSTRESS.value)
        settings: dict[str, object] = {}

        week = await service.week(tenant_id, actor=her_actor, settings=settings, week_start=WEEK)
        assert week.roster_published is False
        assert week.rostered_template_ids == []

        await service.assign(
            tenant_id,
            actor=owner_actor,
            body=CreateAssignmentRequest(
                week_start=WEEK, shift_template_id=morning, staff_user_id=her
            ),
        )
        # ⚠ A DRAFT ANSWERS `(False, [])` EVEN WITH HER ON IT (D6). Telling her
        # «you work Sunday morning» off an unpublished week is exactly the promise
        # this feature must not make.
        draft = await service.week(tenant_id, actor=her_actor, settings=settings, week_start=WEEK)
        assert draft.roster_published is False
        assert draft.rostered_template_ids == []

        await service.publish(tenant_id, actor=owner_actor, week_start=WEEK)
        mine = await service.week(tenant_id, actor=her_actor, settings=settings, week_start=WEEK)
        assert mine.roster_published is True
        assert mine.rostered_template_ids == [morning]
        assert evening not in mine.rostered_template_ids

        # And a colleague on nothing gets the OTHER sentence: published, empty.
        nobody = await _staff(factory, tenant_id)
        hers = await service.week(
            tenant_id,
            actor=_actor(tenant_id, nobody, StaffRole.RECEPTION.value),
            settings=settings,
            week_start=WEEK,
        )
        assert hers.roster_published is True
        assert hers.rostered_template_ids == []


async def test_a_published_week_with_zero_assignments_differs_from_no_roster(
    app_role_url: str,
) -> None:
    """⚠ R-G's guard through REAL ROWS rather than through A2's pure matrix. The
    two answers differ only in whether a published `rosters` row exists, and
    collapsing them puts the whole boutique on shift on a Saturday the owner
    deliberately emptied."""
    tenant_id = uuid.uuid4()
    rosters = RostersRepository()
    async with _engine(app_role_url) as factory:
        await _template(factory, tenant_id)
        owner = await _staff(factory, tenant_id, role=StaffRole.OWNER.value)
        service = _service(factory)
        actor = _actor(tenant_id, owner, StaffRole.OWNER.value)

        async with tenant_session(factory, tenant_id) as session:
            assert await rosters.by_week(session, tenant_id, WEEK) is None

        await service.publish(tenant_id, actor=actor, week_start=WEEK)

        async with tenant_session(factory, tenant_id) as session:
            row = await rosters.by_week(session, tenant_id, WEEK)
            assert row is not None
            assert row.published_at is not None


@pytest.mark.parametrize(
    "role",
    [StaffRole.RECEPTION.value, StaffRole.SALES_ASSISTANT.value, StaffRole.SEAMSTRESS.value],
)
async def test_publish_is_elevated_but_the_published_read_is_open(
    app_role_url: str, role: str
) -> None:
    """D13's split: the BUILDER is elevated, the PUBLISHED week reads to every
    role. A staffer who cannot see the published roster cannot plan."""
    tenant_id = uuid.uuid4()
    async with _engine(app_role_url) as factory:
        await _template(factory, tenant_id)
        her = await _staff(factory, tenant_id)
        service = _service(factory)
        actor = _actor(tenant_id, her, role)

        with pytest.raises(NotAuthorizedError):
            await service.publish(tenant_id, actor=actor, week_start=WEEK)

        payload = await service.published(tenant_id, week_start=WEEK)
        assert payload.published is False
