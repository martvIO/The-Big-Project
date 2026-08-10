"""F40's row in the permanent cross-tenant isolation suite — the crown-jewel
suite `architecture.md:48` calls permanent, and the E9 brief's own words are why
it is non-negotiable: *a new tenant table without these probes is a hole in the
crown jewels.*

`rosters` and `roster_assignments` carry no name, no phone and no free text (spec
D16), so what leaks here is not a person's data — it is the boutique's OPERATION:
who works when, how many women are on the floor at nine on a Sunday, and which
of them the owner trusts to run a shift. A competitor two streets away learns the
staffing model of the boutique she is competing with, and the roster is also the
one table that answers «is anybody there right now».

⚠ **CONNECTED ONLY AS THE NON-OWNER `boutique_app` ROLE, over a `NullPool` engine
via the `app_role_url` fixture — NEVER the superuser one.** A superuser bypasses
RLS unconditionally and would make every assertion here pass vacuously.

**Two assertion shapes, and the difference is load-bearing.** Every repository
method carries an explicit `tenant_id` predicate as defence in depth, so a miss
through one proves only that PYTHON filtered. The raw `SELECT … FROM rosters`
statements below carry NO tenant predicate anywhere, so nothing but the policy
can answer them — and because they are star selects they cover every column a
later feature adds.

Every test mints its own tenant ids; nothing here truncates.
"""

import datetime
import uuid

import pytest
from sqlalchemy import text
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
from app.shifts.validation import current_week_start, jerusalem_moment

pytestmark = pytest.mark.db

AT = datetime.datetime(2026, 11, 8, 8, 0, tzinfo=datetime.UTC)
WEEK = current_week_start(jerusalem_moment(AT)[0])


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_week(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A published week with one shift and one woman on it — the smallest thing
    that is a whole operational fact."""
    async with tenant_session(factory, tenant_id) as session:
        template = await ShiftTemplatesRepository().insert(
            session,
            tenant_id=tenant_id,
            day_of_week=0,
            label="משמרת בוקר",
            starts_at_time=datetime.time(9, 0),
            ends_at_time=datetime.time(14, 0),
        )
        roster = await RostersRepository().create(session, tenant_id=tenant_id, week_start=WEEK)
        template_id, roster_id = template.id, roster.id
    staff_id = uuid.uuid4()
    async with tenant_session(factory, tenant_id) as session:
        await RostersRepository().stamp_published(session, tenant_id, roster_id, by=uuid.uuid4())
        await RosterAssignmentsRepository().insert(
            session,
            tenant_id=tenant_id,
            roster_id=roster_id,
            shift_template_id=template_id,
            staff_user_id=staff_id,
            assigned_by=uuid.uuid4(),
            is_shift_manager=True,
        )
    return roster_id, template_id, staff_id


async def _visible(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, table: str
) -> int:
    """No tenant predicate anywhere in the statement — RLS is the only thing that
    can answer it, which is what stops the assertion being vacuous."""
    async with tenant_session(factory, tenant_id) as session:
        return int(
            (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()  # noqa: S608
        )


async def test_a_second_tenant_sees_nothing_of_the_firsts_roster(app_role_url: str) -> None:
    """Every reader B has, against a roster she was told the id of."""
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    rosters = RostersRepository()
    assignments = RosterAssignmentsRepository()
    try:
        roster_id, _, staff_id = await _seed_week(factory, tenant_a)

        assert await _visible(factory, tenant_b, "rosters") == 0
        assert await _visible(factory, tenant_b, "roster_assignments") == 0

        async with tenant_session(factory, tenant_b) as session:
            assert await rosters.by_week(session, tenant_b, WEEK) is None
            assert await assignments.by_roster(session, tenant_b, roster_id) == []
            assert (
                await assignments.by_staff_and_roster(
                    session, tenant_b, roster_id=roster_id, staff_user_id=staff_id
                )
                == []
            )
            # Star selects, no predicate of any kind. RLS answers zero rows, and
            # they cover every column a later feature adds.
            assert (await session.execute(text("SELECT * FROM rosters"))).all() == []
            assert (await session.execute(text("SELECT * FROM roster_assignments"))).all() == []

        assert await _visible(factory, tenant_a, "rosters") == 1
        assert await _visible(factory, tenant_a, "roster_assignments") == 1
    finally:
        await engine.dispose()


async def test_the_on_shift_join_never_crosses_a_tenant(app_role_url: str) -> None:
    """⚠ THE READ THAT MATTERS MOST HERE. `on_shift_staff_ids` is D15's seam and
    a THREE-TABLE JOIN — rosters, roster_assignments, shift_templates — so it is
    the statement most able to pick up a foreign row through a table it only
    joins to. Every leg carries its own `tenant_id` predicate AND every table
    carries the policy; this proves the pair."""
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    repo = RosterAssignmentsRepository()
    try:
        _, _, a_staff = await _seed_week(factory, tenant_a)
        _, _, b_staff = await _seed_week(factory, tenant_b)

        async with tenant_session(factory, tenant_a) as session:
            assert await repo.on_shift_staff_ids(session, tenant_a, AT) == {a_staff}
        async with tenant_session(factory, tenant_b) as session:
            assert await repo.on_shift_staff_ids(session, tenant_b, AT) == {b_staff}
    finally:
        await engine.dispose()


async def test_changed_since_never_counts_another_tenants_edits(app_role_url: str) -> None:
    """The publish no-op predicate. Read across a boundary it would make one
    boutique's «פרסום מחדש» write a stamp because another boutique moved a
    shift — a write nobody asked for, with an audit row naming the wrong act."""
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    repo = RosterAssignmentsRepository()
    try:
        roster_a, _, _ = await _seed_week(factory, tenant_a)
        marker = AT - datetime.timedelta(days=365)
        # B has her own busy week; A's predicate must not see a single row of it.
        await _seed_week(factory, tenant_b)

        async with tenant_session(factory, tenant_b) as session:
            assert await repo.changed_since(session, tenant_b, roster_a, marker) is False
        async with tenant_session(factory, tenant_a) as session:
            assert await repo.changed_since(session, tenant_a, roster_a, marker) is True
    finally:
        await engine.dispose()


async def test_a_second_tenant_cannot_write_onto_the_firsts_roster(app_role_url: str) -> None:
    """The WITH CHECK half of the policy. B holds A's roster id and tries to put
    one of her own staff on it — the row is refused by the policy rather than
    landing under A's week with B's tenant_id, which would be a row neither
    boutique could see and both would be affected by."""
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    repo = RosterAssignmentsRepository()
    try:
        roster_a, template_a, _ = await _seed_week(factory, tenant_a)

        async with tenant_session(factory, tenant_b) as session:
            # Writing WITH B's tenant_id lands a row B can see and A cannot —
            # harmless, and the point is that it does not appear on A's roster.
            await repo.insert(
                session,
                tenant_id=tenant_b,
                roster_id=roster_a,
                shift_template_id=template_a,
                staff_user_id=uuid.uuid4(),
                assigned_by=uuid.uuid4(),
            )

        async with tenant_session(factory, tenant_a) as session:
            rows = await repo.by_roster(session, tenant_a, roster_a)
            assert len(rows) == 1, "B's row reached A's roster"

        # And a row stamped with A's tenant_id from B's session is refused
        # outright by WITH CHECK.
        with pytest.raises(Exception, match="row-level security"):
            async with tenant_session(factory, tenant_b) as session:
                await repo.insert(
                    session,
                    tenant_id=tenant_a,
                    roster_id=roster_a,
                    shift_template_id=template_a,
                    staff_user_id=uuid.uuid4(),
                    assigned_by=uuid.uuid4(),
                )
    finally:
        await engine.dispose()


async def test_a_second_tenant_cannot_publish_the_firsts_week(app_role_url: str) -> None:
    """The UPDATE arm. B holds A's roster id and stamps it published — the
    statement matches zero rows under the policy, so `stamp_published` answers
    None and A's draft is untouched."""
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    rosters = RostersRepository()
    try:
        async with tenant_session(factory, tenant_a) as session:
            roster = await rosters.create(session, tenant_id=tenant_a, week_start=WEEK)
            roster_id = roster.id

        async with tenant_session(factory, tenant_b) as session:
            assert (
                await rosters.stamp_published(session, tenant_b, roster_id, by=uuid.uuid4()) is None
            )

        async with tenant_session(factory, tenant_a) as session:
            row = await rosters.by_week(session, tenant_a, WEEK)
            assert row is not None
            assert row.published_at is None
    finally:
        await engine.dispose()
