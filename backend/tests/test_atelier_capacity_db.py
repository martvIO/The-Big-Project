"""F42's load aggregate against real Postgres as the non-owner app role.

**Two sums, one statement, and the first one is what the BAR renders.**
`weekly_capacity_hours` is a RATE — hours per week. A single unfiltered
`SUM(effort_minutes)` over every undelivered ticket is a STOCK — the whole
backlog, with no date predicate anywhere and, by the repository's own words, no
bound at all. Dividing the second by the first is not a utilisation of anything,
and the error is chronic and one-directional: a 40 h/week seamstress holding six
weeks of evenly-spread forward work renders at 600 %, clamped, red — on day one,
in any boutique with a book. So the bar's numerator is `due_soon_minutes`, the
work due inside a rolling week; `assigned_minutes` keeps the total queue on the
wire under its own name so nothing is hidden.

**⚠ THE UNIT BOUNDARY.** The database stores HOURS (`weekly_capacity_hours`) and
MINUTES (`effort_minutes`), and THE SERVER NEVER MULTIPLIES THE TWO. This
aggregate returns minutes; capacity resolution returns hours; both reach the wire
in their own units under their own names, and the single `× 60` in the whole
feature is `capacityMinutes()` in the console's `lib/capacity.ts`.
`test_the_hours_and_the_minutes_never_meet_on_the_server` is the catcher: an
hours/minutes mix-up here would be wrong by 60× and dimensionally plausible on
both sides of the wire.

⚠ **THIS MODULE COMMITS INTO A SESSION-SCOPED CONTAINER, so no row it commits may
hold a FLOOR ROLE** — `test_atelier_db.py`'s trap verbatim. `migrated_db` and
`app_role_url` are `scope="session"`, pytest collects alphabetically, and a
committed `seamstress` row reddens
`test_migrations.py::test_adding_the_role_check_validates_existing_rows`, in a
file that never mentions capacity. Nothing here needs one: the aggregate GROUPs
on a plain UUID column with no FK and never reads `staff_users` at all, so every
assignee below is a bare `uuid4()` and the one test that needs a real row seeds
`owner`. The capacity WRITE does need a `seamstress` — `_require_seamstress`
refuses anything else — so `_a_seamstress` commits one and DEMOTES it to `owner`
in a `finally` on the way out.

Every test mints its own tenant id; nothing here truncates.
"""

import asyncio
import datetime
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.atelier.schemas import SetCapacityRequest
from app.atelier.service import AtelierService
from app.atelier.stages import DEFAULT_EFFORT_BANDS
from app.atelier.validation import AtelierValidationError
from app.auth.service import StaffContext
from app.db.repositories.alteration_tickets import (
    BOARD_TICKET_LIMIT,
    AlterationTicketsRepository,
)
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.audit_log import AuditLog
from app.models.constants import AuditAction, StaffRole, TicketStage
from app.models.staff_user import StaffUser
from app.storefront.validation import today_jerusalem

pytestmark = pytest.mark.db

NOW = datetime.datetime(2026, 8, 2, 11, 20, tzinfo=datetime.UTC)
TODAY = datetime.date(2026, 8, 3)
# The rolling week the bar divides by, computed exactly as the service will:
# `today_jerusalem + 7 days`, from the `today` the board already holds.
HORIZON = TODAY + datetime.timedelta(days=7)
# The uncommitted-writer interleave's two windows — `test_queue_dispatch_db.py`'s
# numbers. The winner holds its row lock for HOLD_SECONDS; the loser is issued
# ISSUE_SECONDS after the lock is known to be held.
HOLD_SECONDS = 0.6
ISSUE_SECONDS = 0.05


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


def _service(factory: async_sessionmaker[AsyncSession]) -> AtelierService:
    return AtelierService(factory, clock=lambda: NOW)


def _manager(tenant_id: uuid.UUID) -> StaffContext:
    return StaffContext(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="manager@bella.example",
        display_name="מנהלת",
        role=StaffRole.SHIFT_MANAGER.value,
    )


@asynccontextmanager
async def _a_seamstress(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    display_name: str = "נועה",
    hours: int | None = None,
) -> AsyncIterator[uuid.UUID]:
    """A COMMITTED `seamstress` row for the length of the block, DEMOTED to
    `owner` on the way out.

    The capacity write is the one path in this feature that genuinely needs the
    role — `_require_seamstress` refuses anything else — but the module docstring
    above forbids leaving a floor role committed, because
    `test_migrations.py::test_adding_the_role_check_validates_existing_rows`
    re-adds 0011's TWO-value CHECK over whatever this session-scoped database
    holds. The demotion is in a `finally`, so a failing assertion still cleans up
    and the red lands in this file rather than in one that never mentions
    capacity.
    """
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"seamstress-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name=display_name,
            role=StaffRole.SEAMSTRESS.value,
        )
        staff.weekly_capacity_hours = hours
        staff_id = staff.id
    try:
        yield staff_id
    finally:
        async with tenant_session(factory, tenant_id) as session:
            await session.execute(
                update(StaffUser).where(StaffUser.id == staff_id).values(role=StaffRole.OWNER.value)
            )


async def _capacity_audit(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[AuditLog]:
    async with tenant_session(factory, tenant_id) as session:
        return list(
            (
                await session.scalars(
                    select(AuditLog).where(
                        AuditLog.action == AuditAction.ATELIER_CAPACITY_SET.value
                    )
                )
            ).all()
        )


async def _seed(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    due_date: datetime.date,
    effort_minutes: int,
    assigned_staff_user_id: uuid.UUID | None = None,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await AlterationTicketsRepository().insert(
            session,
            tenant_id=tenant_id,
            customer_id=uuid.uuid4(),
            due_date=due_date,
            effort_minutes=effort_minutes,
            at=NOW,
            assigned_staff_user_id=assigned_staff_user_id,
        )
        return row.id


async def _load(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> dict[uuid.UUID | None, tuple[int, int]]:
    async with tenant_session(factory, tenant_id) as session:
        return await AlterationTicketsRepository().load_by_assignee(
            session, tenant_id, horizon=HORIZON
        )


async def test_load_counts_undelivered_work_at_every_stage(app_role_url: str) -> None:
    """`delivered_at IS NULL` IS THE WHOLE DEFINITION OF "not yet delivered", AND
    IT IS ONE COLUMN.

    It is NOT `stage != 'delivered'`: `stage` is derived in PYTHON by `stage_of`
    as the rightmost stamped column and has no SQL expression at all, so
    re-deriving the rightmost-stamp rule here would be a second copy of the state
    machine, in a second language, that a concurrent write can desynchronise.

    So a ticket at `intake` counts IN FULL, and so does one at `in_progress`,
    `qc` and `ready`. A seamstress holding ten un-started jobs is not free, and a
    numerator that only counted started work would read her as idle on the exact
    morning she is drowning.

    ⚠ A ticket that was delivered and then UNDONE re-enters the load
    immediately — F41's undo clears `delivered_at`, so the row rejoins the
    aggregate on the next tick with no other write. That is correct (the garment
    is back in the workroom) and it is the one path by which a bar goes UP with
    nobody assigning anything."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    other_tenant = uuid.uuid4()
    her = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        due = TODAY + datetime.timedelta(days=2)

        await _seed(factory, tenant_id, due_date=due, effort_minutes=10, assigned_staff_user_id=her)
        for minutes, stage in (
            (20, TicketStage.IN_PROGRESS),
            (30, TicketStage.QC),
            (40, TicketStage.READY),
        ):
            ticket = await _seed(
                factory, tenant_id, due_date=due, effort_minutes=minutes, assigned_staff_user_id=her
            )
            async with tenant_session(factory, tenant_id) as session:
                await repo.advance_stage(session, tenant_id, ticket, stage, at=NOW)

        # Delivered and then UNDONE: back in the room, back in the load.
        undone = await _seed(
            factory, tenant_id, due_date=due, effort_minutes=50, assigned_staff_user_id=her
        )
        async with tenant_session(factory, tenant_id) as session:
            await repo.advance_stage(session, tenant_id, undone, TicketStage.DELIVERED, at=NOW)
        async with tenant_session(factory, tenant_id) as session:
            await repo.undo_stage(session, tenant_id, undone, TicketStage.DELIVERED)

        # Excluded, each for its own clause.
        delivered = await _seed(
            factory, tenant_id, due_date=due, effort_minutes=900, assigned_staff_user_id=her
        )
        async with tenant_session(factory, tenant_id) as session:
            await repo.advance_stage(session, tenant_id, delivered, TicketStage.DELIVERED, at=NOW)
        deleted = await _seed(
            factory, tenant_id, due_date=due, effort_minutes=800, assigned_staff_user_id=her
        )
        async with tenant_session(factory, tenant_id) as session:
            await repo.soft_delete(session, tenant_id, deleted)
        await _seed(
            factory, other_tenant, due_date=due, effort_minutes=700, assigned_staff_user_id=her
        )

        assert await _load(factory, tenant_id) == {her: (150, 150)}
    finally:
        await engine.dispose()


async def test_the_bar_counts_only_work_due_inside_the_week(app_role_url: str) -> None:
    """THE FILTER, AND IT IS THE WHOLE FEATURE.

    Without it the bar divides a STOCK by a RATE: every undelivered ticket the
    boutique holds against one week of capacity. It would read permanently red in
    a perfectly healthy shop, and a bar that is red in the steady state is a bar
    nobody reads — which is the failure this feature exists to avoid.

    Both edges of the horizon, because a boundary asserted from one side is not a
    boundary: `today + 7` is IN, `today + 8` is OUT.

    OVERDUE ROWS ARE INSIDE THE HORIZON AND THAT IS ARITHMETIC, NOT A SPECIAL
    CASE — `due_date < today <= horizon` — so a job ten days late is in
    `due_soon_minutes` in full, which is correct, because late work is the most
    urgent work there is.

    Mutation: delete the FILTER and the 30-day ticket reddens the bar → red."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    her = uuid.uuid4()
    try:
        await _seed(
            factory,
            tenant_id,
            due_date=TODAY + datetime.timedelta(days=30),
            effort_minutes=400,
            assigned_staff_user_id=her,
        )
        await _seed(
            factory,
            tenant_id,
            due_date=TODAY - datetime.timedelta(days=10),
            effort_minutes=25,
            assigned_staff_user_id=her,
        )
        await _seed(
            factory, tenant_id, due_date=HORIZON, effort_minutes=7, assigned_staff_user_id=her
        )
        await _seed(
            factory,
            tenant_id,
            due_date=HORIZON + datetime.timedelta(days=1),
            effort_minutes=8,
            assigned_staff_user_id=her,
        )

        assert await _load(factory, tenant_id) == {her: (32, 440)}
    finally:
        await engine.dispose()


async def test_a_seamstress_whose_every_job_is_due_later_is_still_in_the_result(
    app_role_url: str,
) -> None:
    """The `COALESCE` on the FILTERed sum, and why there is no `HAVING`.

    Every group is wanted. The FILTER narrows one SUM, never the group set, so a
    seamstress whose whole book is next month is present with `due_soon_minutes =
    0` and a real `assigned_minutes` — which is exactly the row a manager wants
    to reassign work TO.

    Without the COALESCE that first sum comes back NULL, and the fold above would
    put a None on the wire where the console expects a number."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    her = uuid.uuid4()
    try:
        await _seed(
            factory,
            tenant_id,
            due_date=TODAY + datetime.timedelta(days=45),
            effort_minutes=90,
            assigned_staff_user_id=her,
        )
        assert await _load(factory, tenant_id) == {her: (0, 90)}
    finally:
        await engine.dispose()


async def test_load_groups_null_as_the_unassigned_pile(app_role_url: str) -> None:
    """The NULL group is kept DELIBERATELY: it is the unassigned pile, which is
    the first thing a capacity view must show, and dropping it here would mean a
    second statement to get it back.

    It carries its own two sums like any other group, and the envelope reads its
    UNFILTERED one — no bar means no rate, so the pile is a total and not a
    utilisation."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    her = uuid.uuid4()
    try:
        await _seed(
            factory, tenant_id, due_date=TODAY + datetime.timedelta(days=1), effort_minutes=15
        )
        await _seed(
            factory, tenant_id, due_date=TODAY + datetime.timedelta(days=60), effort_minutes=60
        )
        await _seed(
            factory,
            tenant_id,
            due_date=TODAY + datetime.timedelta(days=1),
            effort_minutes=5,
            assigned_staff_user_id=her,
        )

        assert await _load(factory, tenant_id) == {None: (15, 75), her: (5, 5)}
    finally:
        await engine.dispose()


async def test_a_seamstress_with_no_tickets_is_absent_from_the_result(app_role_url: str) -> None:
    """She does not appear AT ALL — no zero row, no placeholder. The envelope's
    fold is what reads her as `(0, 0)`, through `load.get(row.id, (0, 0))`, and
    that default is what keeps a seamstress with an empty book visible in the
    panel instead of vanishing from it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    idle = uuid.uuid4()
    busy = uuid.uuid4()
    try:
        await _seed(
            factory,
            tenant_id,
            due_date=TODAY + datetime.timedelta(days=1),
            effort_minutes=45,
            assigned_staff_user_id=busy,
        )
        load = await _load(factory, tenant_id)
        assert load == {busy: (45, 45)}
        assert idle not in load
    finally:
        await engine.dispose()


async def test_a_truncated_board_still_reports_exact_load(app_role_url: str) -> None:
    """THE AGGREGATE IS UNCAPPED, DELIBERATELY, and this is the test that pays
    for the partial index F42's migration buys.

    Folding the load in Python over the tickets the board already fetched is
    FREE — zero statements — and it is wrong in exactly the boutique that needs
    the feature: the board read stops at BOARD_TICKET_LIMIT, so a truncated
    payload would silently UNDER-count every bar, and the boutique whose board
    truncates is by definition the overloaded one. A bar that understates load is
    worse than no bar: it is a green light computed from a partial view, with
    nothing on screen saying so.

    So `truncated: true` and a correct set of bars coexist, and must.

    Mutation: fold the load over `board()`'s ticket list → under-counts by the
    truncated tail → red."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    her = uuid.uuid4()
    count = BOARD_TICKET_LIMIT + 20
    try:
        repo = AlterationTicketsRepository()
        # One transaction: 520 tickets, each 1 minute, all due inside the week.
        async with tenant_session(factory, tenant_id) as session:
            for _ in range(count):
                await repo.insert(
                    session,
                    tenant_id=tenant_id,
                    customer_id=uuid.uuid4(),
                    due_date=TODAY + datetime.timedelta(days=1),
                    effort_minutes=1,
                    at=NOW,
                    assigned_staff_user_id=her,
                )

        async with tenant_session(factory, tenant_id) as session:
            rows, truncated = await repo.board(session, tenant_id, today=TODAY)
        assert truncated is True
        assert len(rows) == BOARD_TICKET_LIMIT

        # The board saw 500. The aggregate sees all 520.
        assert await _load(factory, tenant_id) == {her: (count, count)}
        assert sum(row.effort_minutes for row in rows) == BOARD_TICKET_LIMIT
    finally:
        await engine.dispose()


async def test_the_hours_and_the_minutes_never_meet_on_the_server(app_role_url: str) -> None:
    """THE UNITS CATCHER, and it is here because a 60× error is dimensionally
    plausible on both sides of the wire.

    `weekly_capacity_hours` is HOURS and `effort_minutes` is MINUTES. The server
    never multiplies or divides the two: this aggregate answers PURE MINUTE SUMS,
    the capacity reaches the wire as hours under its own name, and the single
    `× 60` in the entire feature is `capacityMinutes()` in the console.

    A seamstress with 12 recorded hours holding one 30-minute ticket reports
    **30** — never 1800 (`× 60`), never 0 (`// 60`), never 720 (her hours in
    minutes). And a second seamstress with a different capacity holding an
    identical ticket reports the SAME number, which is the sharper half: the
    aggregate must not read that column at all.

    `owner`, not `seamstress` — this module commits, and the aggregate never
    looks at the role (or at `staff_users`) either way. See the module
    docstring."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:

        async def _staff_with_capacity(hours: int | None, name: str) -> uuid.UUID:
            async with tenant_session(factory, tenant_id) as session:
                staff = await StaffUsersRepository().insert(
                    session,
                    tenant_id=tenant_id,
                    email=f"capacity-{uuid.uuid4().hex[:10]}@bella.example",
                    password_hash="not-a-real-hash",
                    display_name=name,
                    role=StaffRole.OWNER.value,
                )
                staff.weekly_capacity_hours = hours
                return staff.id

        twelve = await _staff_with_capacity(12, "Twelve")
        forty = await _staff_with_capacity(40, "Forty")

        for assignee in (twelve, forty):
            await _seed(
                factory,
                tenant_id,
                due_date=TODAY + datetime.timedelta(days=1),
                effort_minutes=30,
                assigned_staff_user_id=assignee,
            )

        assert await _load(factory, tenant_id) == {twelve: (30, 30), forty: (30, 30)}

        # The column really was written — otherwise the equality above would hold
        # vacuously against a repository that could not see it.
        async with tenant_session(factory, tenant_id) as session:
            stored = await StaffUsersRepository().by_id(session, tenant_id, twelve)
        assert stored is not None
        assert stored.weekly_capacity_hours == 12
    finally:
        await engine.dispose()


# --- F42 Task 8: the forced interleave, the audit ordering, the budget --------
#
# ⚠ `asyncio.gather` IS DELIBERATELY NOT USED FOR THE INTERLEAVE, for F34's,
# F57's and F41's reason verbatim (`test_floor_db.py:250-263`): gather does not
# ORDER two transactions, so the loser most often loads AFTER the winner commits,
# its in-memory instance is already correct, and the branch the test exists to
# prove goes green without the mechanism ever being exercised.
#
# The mechanism is `tenant_session`'s own shape — exiting the context manager IS
# the commit (`db/tenant.py:25`) — and two NESTED tenant_sessions on one NullPool
# factory take two separate connections.


async def test_the_capacity_answer_is_the_DATABASES_ROW_and_not_the_one_the_check_loaded(
    app_role_url: str,
) -> None:
    """⚠ `populate_existing=True` INSIDE `StaffUsersRepository._refreshed`, and
    this is the ONLY test in the feature that can see it.

    The capacity path is the shape the flag exists for: the caller MUST load the
    row before writing (for `_require_seamstress` and for the audit row's
    `from`), so the identity map is populated when the UPDATE runs, and
    `expire_on_commit=False` (`db/session.py:66`) hands that same instance back
    on any plain re-read. Every other capacity test opens a fresh session per
    operation and cannot observe the flag at all.

    ⚠ AND WHAT IT PINS HERE IS THE **SIBLING COLUMNS**, NOT THE HOURS — the plan
    predicted the hours and the prediction does not survive contact.
    `set_weekly_capacity_hours` carries NO guard predicate (last-write-wins is
    D6's design), so its UPDATE matches whenever the row is live and `evaluate`
    stamps exactly the value the database wrote: the two agree by construction
    and no interleave can separate them. The only zero-row cause is a concurrent
    soft delete, and there `_refreshed`'s own `deleted_at IS NULL` answers None
    from SQL whatever the identity map holds.

    What the flag does decide is every OTHER column of the answer. Without it the
    response carries the display name and the role the CHECK read, so a manager
    who saves hours four seconds after a colleague renamed or re-roled the same
    staffer sees the write echo back the name she no longer has — and
    `assignable` computed from a role the database has already changed.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = StaffUsersRepository()
    try:
        async with _a_seamstress(factory, tenant_id, display_name="נועה") as staff_id:
            # The LOSER's session, held open across the winner's whole transaction.
            async with tenant_session(factory, tenant_id) as loser:
                loaded = await repo.by_id(loser, tenant_id, staff_id)
                assert loaded is not None
                assert loaded.display_name == "נועה"
                assert loaded.weekly_capacity_hours is None

                # The WINNER renames her and sets hours in a second session.
                # Exiting this block is the commit.
                async with tenant_session(factory, tenant_id) as winner:
                    await repo.update(winner, tenant_id, staff_id, display_name="דנה")
                    await repo.set_weekly_capacity_hours(winner, tenant_id, staff_id, hours=40)

                refreshed = await repo.set_weekly_capacity_hours(
                    loser, tenant_id, staff_id, hours=12
                )

            assert refreshed is not None
            # The DATABASE's name, not the one the check read four seconds ago.
            assert refreshed.display_name == "דנה"
            assert refreshed is loaded, (
                "the identity map hands back the same object either way — which is "
                "precisely why its ATTRIBUTES have to be repopulated"
            )
            # The hours are the loser's own and that is DESIGNED: the write is
            # unconditional and the last one in wins the row outright (D6).
            assert refreshed.weekly_capacity_hours == 12
            async with tenant_session(factory, tenant_id) as session:
                stored = await repo.by_id(session, tenant_id, staff_id)
            assert stored is not None
            assert (stored.weekly_capacity_hours, stored.display_name) == (12, "דנה")
    finally:
        await engine.dispose()


async def test_the_capacity_audit_row_carries_the_value_it_REPLACED(app_role_url: str) -> None:
    """⚠ THE CAPTURE OF `before` INTO A LOCAL, BEFORE THE WRITE — and it is here
    rather than only in the fast suite because a MONKEYPATCHED repository never
    stamps anything, so moving the capture after the write leaves a fake-driven
    test green (F57's note records exactly this).

    Against a real session, `update(StaffUser)` is ORM-enabled DML whose default
    `evaluate` synchronization writes the SET value onto the identity-mapped
    instance the service is still holding — the very row `_require_seamstress`
    just returned. A capture taken afterwards therefore reads the NEW hours and
    the audit row names its destination twice, silently, with the number it
    exists to preserve gone for good.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    actor = _manager(tenant_id)
    try:
        async with _a_seamstress(factory, tenant_id, hours=12) as staff_id:
            answer = await _service(factory).set_capacity(
                tenant_id,
                staff_id,
                SetCapacityRequest(weekly_capacity_hours=30),
                actor=actor,
                tenant_default=None,
            )
            assert answer.weekly_capacity_hours == 30

            rows = await _capacity_audit(factory, tenant_id)
            assert len(rows) == 1
            assert rows[0].actor_id == actor.id
            assert rows[0].entity == str(staff_id)
            assert rows[0].details["to"] == 30
            assert rows[0].details["from"] == 12, (
                "the capture ran after the write, so `from` is the value the row "
                "ARRIVED at and the entry names its destination twice"
            )
    finally:
        await engine.dispose()


async def test_a_capacity_write_answers_the_REFRESHED_row_through_all_three_verbs(
    app_role_url: str,
) -> None:
    """Set, change, and CLEAR — the third being the one `null` exists for, and the
    only one whose answer is not the number that was sent.

    The response is capacity facts only. It is NOT a `SeamstressRef`: that model
    requires both load sums, this path has no aggregate, and the only value
    reachable without a second business statement on a write is `(0, 0)` — which
    would collapse her bar and drop her «עומס יתר» word for up to five seconds on
    this feature's own primary surface, at the moment a manager is looking at it.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    actor = _manager(tenant_id)
    service = _service(factory)
    try:
        async with _a_seamstress(factory, tenant_id, display_name="נועה") as staff_id:

            async def _set(hours: int | None) -> dict[str, object]:
                answer = await service.set_capacity(
                    tenant_id,
                    staff_id,
                    SetCapacityRequest(weekly_capacity_hours=hours),
                    actor=actor,
                    tenant_default=40,
                )
                return dict(answer.model_dump())

            first = await _set(24)
            assert (first["weekly_capacity_hours"], first["capacity_is_default"]) == (24, False)
            assert (first["display_name"], first["assignable"]) == ("נועה", True)
            assert set(first) == {
                "id",
                "display_name",
                "assignable",
                "weekly_capacity_hours",
                "capacity_is_default",
            }

            changed = await _set(36)
            assert (changed["weekly_capacity_hours"], changed["capacity_is_default"]) == (36, False)

            cleared = await _set(None)
            # The BOUTIQUE's number comes back, flagged as the boutique's — not
            # the `null` that was sent and not a zero.
            assert (cleared["weekly_capacity_hours"], cleared["capacity_is_default"]) == (40, True)

            # …and the COLUMN really is null, which is the fact the resolution
            # above is derived from.
            async with tenant_session(factory, tenant_id) as session:
                stored = await StaffUsersRepository().by_id(session, tenant_id, staff_id)
            assert stored is not None
            assert stored.weekly_capacity_hours is None

            rows = sorted(await _capacity_audit(factory, tenant_id), key=lambda r: r.created_at)
            assert [(r.details["from"], r.details["to"]) for r in rows] == [
                (None, 24),
                (24, 36),
                (36, None),
            ]
    finally:
        await engine.dispose()


async def test_a_row_soft_deleted_between_the_check_and_the_update_is_the_ONLY_404(
    app_role_url: str,
) -> None:
    """⚠ THE ROUTE'S ONLY 404, AND IT IS A RACE RATHER THAN A REFUSAL — every
    ordinary miss (a receptionist, a retired staffer, an unknown id, another
    tenant's) is one indistinguishable 400 through `_require_seamstress`, whose
    `by_id` already filters `tenant_id` AND `deleted_at IS NULL`.

    ⚠ AND IT IS NOT REACHABLE BY DELETING HER FIRST. A soft delete that lands
    BEFORE the call is refused by `_require_seamstress` with the same 400 as
    everything else — the 404 needs the delete to commit strictly BETWEEN the
    check and the UPDATE, which is a window nothing sequential can enter.

    So it is forced with an UNCOMMITTED delete holding the row lock
    (`test_queue_dispatch_db.py`'s shape, and NOT `asyncio.gather`, which does not
    order anything): the service's `by_id` is a plain SELECT and reads straight
    past it under READ COMMITTED, so the check passes on a live row; its UPDATE
    then blocks on that lock; the delete commits; Postgres re-evaluates the
    UPDATE's `deleted_at IS NULL` against the new row version, matches ZERO rows,
    and `_refreshed` answers None.

    Nothing is audited — the value never changed, so a row here would claim a
    write that did not happen.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = StaffUsersRepository()
    try:
        async with _a_seamstress(factory, tenant_id, hours=12) as staff_id:
            deleted = asyncio.Event()

            async def _uncommitted_delete() -> None:
                async with tenant_session(factory, tenant_id) as winner:
                    assert await repo.soft_delete(winner, tenant_id, staff_id) is True
                    deleted.set()
                    # Still UNCOMMITTED for this long, and holding the row's write
                    # lock. Exiting the block is the commit (`db/tenant.py:25`),
                    # which is what releases the service's blocked UPDATE into its
                    # zero-row branch.
                    await asyncio.sleep(HOLD_SECONDS)

            winner_task = asyncio.create_task(_uncommitted_delete())
            await deleted.wait()
            await asyncio.sleep(ISSUE_SECONDS)

            with pytest.raises(DomainNotFoundError):
                await _service(factory).set_capacity(
                    tenant_id,
                    staff_id,
                    SetCapacityRequest(weekly_capacity_hours=30),
                    actor=_manager(tenant_id),
                    tenant_default=None,
                )
            await winner_task

            assert await _capacity_audit(factory, tenant_id) == []
            # Her hours are untouched: the UPDATE matched nothing.
            async with tenant_session(factory, tenant_id) as session:
                stored = await session.scalar(
                    select(StaffUser.weekly_capacity_hours).where(StaffUser.id == staff_id)
                )
            assert stored == 12

            # …and once she is gone, the ordinary path is the ordinary 400 again.
            with pytest.raises(AtelierValidationError):
                await _service(factory).set_capacity(
                    tenant_id,
                    staff_id,
                    SetCapacityRequest(weekly_capacity_hours=30),
                    actor=_manager(tenant_id),
                    tenant_default=None,
                )
    finally:
        await engine.dispose()


async def test_the_board_poll_issues_exactly_FOUR_business_statements(app_role_url: str) -> None:
    """⚠ D3's BUDGET, COUNTED AGAINST A REAL CONNECTION AND NOT AGAINST FAKES.

    F41 fixed the poll at THREE and called that number the budget. F42 makes it
    FOUR — tickets, customers' names in one `IN`, the assignee union, and the
    load aggregate — and §Conflicts 8 sizes the result at ≈7 statements, ≈12
    round trips and 3 pool checkouts per tick per device. F29 is handed that
    figure by name.

    The BANDS and the CAPACITY DEFAULT add NOTHING and that is the whole reason
    the router resolves both off `TenantContext.settings`: `TenantsRepository`
    opens its own session inside every method, so either one read through it
    would be a fifth statement, a fifth pool checkout and a fifth BEGIN/COMMIT
    every five seconds per device. This test is what would notice.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    executed: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _record(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        executed.append(statement)

    try:
        her = uuid.uuid4()
        await _seed(
            factory,
            tenant_id,
            due_date=TODAY + datetime.timedelta(days=1),
            effort_minutes=30,
            assigned_staff_user_id=her,
        )
        executed.clear()

        body = await _service(factory).board(
            tenant_id, bands=DEFAULT_EFFORT_BANDS, default_capacity_hours=36
        )

        # `set_config` is the tenant binding, not business — one per session, and
        # the poll opens exactly one.
        bindings = [s for s in executed if "set_config" in s]
        business = [s for s in executed if "set_config" not in s]
        assert len(bindings) == 1, f"one tenant binding per poll, got {len(bindings)}"
        assert len(business) == 4, "the poll's budget is FOUR statements:\n" + "\n---\n".join(
            business
        )
        assert sum("GROUP BY" in s for s in business) == 1, "the load aggregate is ONE statement"
        assert body.default_weekly_capacity_hours == 36
        # The service's own Jerusalem day plus seven — NOT this module's TODAY,
        # which the aggregate tests pass in by hand.
        assert body.due_soon_through == today_jerusalem(lambda: NOW) + datetime.timedelta(days=7)
        assert body.seamstresses == []  # no staff row: the union's second leg is a JOIN
        assert body.unassigned_minutes == 0
    finally:
        await engine.dispose()
