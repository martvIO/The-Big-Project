"""F33 through the SERVICE against real Postgres, as the non-owner app role.

What this module is for, after Ruling 3: the two things that only exist once a
row has actually been stored — the Jerusalem day the `queue_day` column carries,
and the tables F33 does NOT write.

**Deleted by Ruling 3, and named here so nobody restores them.** The
forced-interleave dedup race and its whole "asyncio.gather is not an interleave"
rationale; "a `done` ticket frees the key"; "a soft-deleted ticket frees the
key"; the service-level dedup-convergence test; and "the advisory-lock key is
namespaced". Every one of them asserted something about a unique index, a lock
or an `IntegrityError`. F33 ships none of the three — `0018` carries no unique
index but the primary key (pinned by `test_migrations.py`), `app/queue/` has no
raw statement and no `try` block — so none of those tests has a subject. A race
test needs two writers that can CONFLICT; two INSERTs that both succeed by
design are not a race, and a forced interleave over them would assert only that
Postgres can hold two transactions open.

What survives is scoping, not refusal, and it is the harder half: `queue_day` is
a stored `DATE` fed by an injectable clock, so the boundary is testable at a
chosen instant. Against a database-clock expression it would not be testable at
all — which is D4's argument made mechanical.

Every test mints its own tenant id. The container is session-scoped, exiting
`tenant_session` IS the commit (`db/tenant.py:25`), and nothing here truncates.
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

from app.auth.rate_limit import FixedWindowRateLimiter
from app.db.tenant import tenant_session
from app.models.constants import QueueTicketStatus, VisitType
from app.models.queue_ticket import QueueTicket
from app.queue.service import QueueService

pytestmark = pytest.mark.db

PHONE = "+972501234567"

# Both instants fall on the SAME UTC day (2026-07-18) and on two DIFFERENT
# Jerusalem days: 23:00 on the 18th and 00:30 on the 19th, IDT being UTC+3 in
# July. Any implementation that reaches for the UTC date gives them one day.
BEFORE_MIDNIGHT = datetime.datetime(2026, 7, 18, 20, 0, tzinfo=datetime.UTC)
AFTER_MIDNIGHT = datetime.datetime(2026, 7, 18, 21, 30, tzinfo=datetime.UTC)
# A different UTC day (the 19th) but the SAME Jerusalem day as AFTER_MIDNIGHT —
# the mirror image, and the half that a naive `now.date()` gets wrong in the
# other direction.
NEXT_MORNING = datetime.datetime(2026, 7, 19, 5, 0, tzinfo=datetime.UTC)

# Israel's spring-forward is the Friday before the last Sunday of March, at
# 02:00 local: 2026-03-27, i.e. the instant 2026-03-27T00:00Z. These two are
# 24h apart to the second and straddle it.
BEFORE_DST = datetime.datetime(2026, 3, 26, 21, 30, tzinfo=datetime.UTC)
AFTER_DST = datetime.datetime(2026, 3, 27, 21, 30, tzinfo=datetime.UTC)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _service(factory: async_sessionmaker[AsyncSession], now: datetime.datetime) -> QueueService:
    """A frozen clock, not a real one: every assertion below is an equality on a
    stored calendar day, and `datetime.now()` would make them all approximate —
    and green on a runner whose TZ happens to be Israel's."""
    return QueueService(
        factory,
        create_limiter=FixedWindowRateLimiter(200, 3600.0, lambda: 0.0),
        position_ticket_limiter=FixedWindowRateLimiter(30, 60.0, lambda: 0.0),
        position_miss_limiter=FixedWindowRateLimiter(120, 60.0, lambda: 0.0),
        clock=lambda: now,
    )


async def _check_in(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    now: datetime.datetime,
    *,
    marketing_opt_in: bool = False,
) -> uuid.UUID:
    view = await _service(factory, now).check_in(
        tenant_id,
        name="נועה",
        raw_phone=PHONE,
        visit_type=VisitType.BRIDE.value,
        marketing_opt_in=marketing_opt_in,
    )
    return view.id


async def _stored_day(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, ticket_id: uuid.UUID
) -> datetime.date:
    async with tenant_session(factory, tenant_id) as session:
        row = await session.get(QueueTicket, ticket_id)
        assert row is not None
        return row.queue_day


async def test_two_check_ins_either_side_of_jerusalem_midnight_open_two_queue_days(
    app_role_url: str,
) -> None:
    """The same UTC day, the same phone, two Jerusalem days — so the second one
    is FIRST in a new day's queue rather than second in the old one.

    Under Ruling 3 this asserts scoping and nothing about dedup: the second
    create was always going to succeed. What would break without the Jerusalem
    conversion is the number on her screen, which would read 2 and put her
    behind a woman who went home last night.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        assert BEFORE_MIDNIGHT.date() == AFTER_MIDNIGHT.date()  # one UTC day

        first = await _check_in(factory, tenant_id, BEFORE_MIDNIGHT)
        second = await _check_in(factory, tenant_id, AFTER_MIDNIGHT)

        assert await _stored_day(factory, tenant_id, first) == datetime.date(2026, 7, 18)
        assert await _stored_day(factory, tenant_id, second) == datetime.date(2026, 7, 19)

        view = await _service(factory, AFTER_MIDNIGHT).position(tenant_id, second)
        assert view.position == 1
    finally:
        await engine.dispose()


async def test_a_later_arrival_on_the_new_jerusalem_day_queues_behind_the_first(
    app_role_url: str,
) -> None:
    """NEXT_MORNING is a different UTC day from AFTER_MIDNIGHT and the same
    Jerusalem day. The pair pins the conversion in BOTH directions: one
    implementation that splits on the UTC date fails the test above, and the
    opposite one — anything that lumps a whole UTC day together — fails here.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        assert AFTER_MIDNIGHT.date() != NEXT_MORNING.date()  # two UTC days

        midnight_ticket = await _check_in(factory, tenant_id, AFTER_MIDNIGHT)
        morning_ticket = await _check_in(factory, tenant_id, NEXT_MORNING)

        day = datetime.date(2026, 7, 19)
        assert await _stored_day(factory, tenant_id, midnight_ticket) == day
        assert await _stored_day(factory, tenant_id, morning_ticket) == day

        view = await _service(factory, NEXT_MORNING).position(tenant_id, morning_ticket)
        assert view.position == 2
    finally:
        await engine.dispose()


async def test_the_spring_forward_moves_the_boundary_and_skips_a_jerusalem_day_at_that_hour(
    app_role_url: str,
) -> None:
    """21:30Z on two consecutive UTC days, across Israel's 2026 spring-forward,
    lands on Jerusalem days that are TWO apart: 2026-03-26 and 2026-03-28.

    2026-03-27 is unreachable at that hour, because the offset moved from +2 to
    +3 and 23:30 became 00:30. This is the assertion that separates a real
    IANA conversion from every shortcut: a fixed +02:00 gives 03-26/03-27, a
    fixed +03:00 gives 03-27/03-28, and the UTC date gives 03-26/03-27. All
    three are red here; only `Asia/Jerusalem` is green.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        before = await _check_in(factory, tenant_id, BEFORE_DST)
        after = await _check_in(factory, tenant_id, AFTER_DST)

        assert datetime.timedelta(hours=24) == (AFTER_DST - BEFORE_DST)
        assert await _stored_day(factory, tenant_id, before) == datetime.date(2026, 3, 26)
        assert await _stored_day(factory, tenant_id, after) == datetime.date(2026, 3, 28)

        # A new day's queue on each side, so each is first in her own.
        assert (await _service(factory, AFTER_DST).position(tenant_id, before)).position == 1
        assert (await _service(factory, AFTER_DST).position(tenant_id, after)).position == 1
    finally:
        await engine.dispose()


@pytest.mark.parametrize("marketing_opt_in", [False, True])
async def test_a_check_in_writes_no_customers_row_on_either_branch(
    app_role_url: str, marketing_opt_in: bool
) -> None:
    """Ruling 2's behavioural half — the companion to the fast suite's source
    guard, which can only prove the import is absent.

    The count is taken inside the tenant's OWN session, which is where a forged
    row would land: `CustomersRepository.upsert` is tenant-scoped, so a
    re-introduced call would take this count from 0 to 1 under RLS. The earlier
    draft had this form writing `customers.marketing_opt_in_at` from an
    anonymous POST with no possession proof of any kind — a permanent,
    authoritative, forgeable consent timestamp, plus a free rename of a real
    customer via `existing.name = name`.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            before = (await session.execute(text("SELECT count(*) FROM customers"))).scalar_one()

        ticket_id = await _check_in(
            factory, tenant_id, BEFORE_MIDNIGHT, marketing_opt_in=marketing_opt_in
        )

        async with tenant_session(factory, tenant_id) as session:
            after = (await session.execute(text("SELECT count(*) FROM customers"))).scalar_one()
            row = await session.get(QueueTicket, ticket_id)
            assert row is not None
            # The consent went to the ticket, or nowhere at all.
            assert (row.marketing_opt_in_at is not None) is marketing_opt_in

        assert after == before == 0
    finally:
        await engine.dispose()


async def test_a_done_ticket_still_reads_back_and_reports_no_position(
    app_role_url: str,
) -> None:
    """C11's seed. Nothing in F33 can reach a terminal — no status write exists
    anywhere in the feature and F58 owns every transition — so the only way to
    exercise the closed-ticket read is to seed the status directly.

    It matters because `done` is the storefront poll's success terminal (D10):
    the one place in the product where a 200 ends a loop. If the read answered a
    position for a finished ticket, the screen would show a number forever after
    the woman had already been served.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        ticket_id = await _check_in(factory, tenant_id, BEFORE_MIDNIGHT)
        async with tenant_session(factory, tenant_id) as session:
            row = await session.get(QueueTicket, ticket_id)
            assert row is not None
            row.status = QueueTicketStatus.DONE.value

        view = await _service(factory, BEFORE_MIDNIGHT).position(tenant_id, ticket_id)
        assert view.status == QueueTicketStatus.DONE.value
        assert view.position is None
        assert view.id == ticket_id
    finally:
        await engine.dispose()
