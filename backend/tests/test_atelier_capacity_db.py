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
`owner`.

Every test mints its own tenant id; nothing here truncates.
"""

import datetime
import uuid

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.repositories.alteration_tickets import (
    BOARD_TICKET_LIMIT,
    AlterationTicketsRepository,
)
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.models.constants import StaffRole, TicketStage

pytestmark = pytest.mark.db

NOW = datetime.datetime(2026, 8, 2, 11, 20, tzinfo=datetime.UTC)
TODAY = datetime.date(2026, 8, 3)
# The rolling week the bar divides by, computed exactly as the service will:
# `today_jerusalem + 7 days`, from the `today` the board already holds.
HORIZON = TODAY + datetime.timedelta(days=7)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
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
