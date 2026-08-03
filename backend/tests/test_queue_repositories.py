"""Round-trips for the F33 queue repository, as the non-owner app role. The
isolation half lives in test_queue_isolation.py.

`active_today` is deliberately NOT here and never will be: Ruling 3 deleted the
dedup pre-check, and the method existed only for it.
"""

import asyncio
import datetime
import uuid

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.repositories.queue_tickets import QueueTicketsRepository
from app.db.tenant import tenant_session
from app.models.constants import QueueTicketStatus, VisitType
from app.models.queue_ticket import QueueTicket

pytestmark = pytest.mark.db

TODAY = datetime.date(2026, 8, 3)
YESTERDAY = datetime.date(2026, 8, 2)

# Frozen arrival instants, only ever COMPARED: T1 < T2 < T3 < REQUEUED. The
# position query does no arithmetic on them, so the one thing that matters is
# that they are distinct and tz-aware — and that they are set EXPLICITLY rather
# than left to the column default, because `now()` is transaction-scoped in
# Postgres and every row seeded in one transaction would tie.
T1 = datetime.datetime(2026, 8, 3, 7, 0, tzinfo=datetime.UTC)
T2 = datetime.datetime(2026, 8, 3, 7, 10, tzinfo=datetime.UTC)
T3 = datetime.datetime(2026, 8, 3, 7, 20, tzinfo=datetime.UTC)
REQUEUED = datetime.datetime(2026, 8, 3, 9, 0, tzinfo=datetime.UTC)
Y1 = datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC)
Y2 = datetime.datetime(2026, 8, 2, 7, 10, tzinfo=datetime.UTC)
CONSENT_AT = datetime.datetime(2026, 8, 3, 7, 0, 30, tzinfo=datetime.UTC)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _phone() -> str:
    return f"+9725{uuid.uuid4().int % 10**8:08d}"


async def _seed(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    created_at: datetime.datetime,
    queue_day: datetime.date = TODAY,
    status: str = QueueTicketStatus.WAITING.value,
    requeued_at: datetime.datetime | None = None,
    deleted_at: datetime.datetime | None = None,
    phone: str | None = None,
) -> QueueTicket:
    """Seeds a row DIRECTLY rather than through the repository's `insert`, which
    takes no `created_at` — production never sets one. The position tests are
    about the count query, not about the writer, and a deterministic sort key is
    what makes "position 2" mean something."""
    row = QueueTicket(
        tenant_id=tenant_id,
        queue_day=queue_day,
        name="נועה",
        phone=phone or _phone(),
        visit_type=VisitType.BRIDE.value,
        status=status,
        created_at=created_at,
        requeued_at=requeued_at,
        deleted_at=deleted_at,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


def test_insert_round_trips_every_column_and_lands_the_defaults(app_role_url: str) -> None:
    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        phone = _phone()
        try:
            async with tenant_session(factory, tenant_id) as session:
                ticket = await repo.insert(
                    session,
                    tenant_id=tenant_id,
                    queue_day=TODAY,
                    name="נועה",
                    phone=phone,
                    visit_type=VisitType.EVENING.value,
                )
                ticket_id = ticket.id

            async with tenant_session(factory, tenant_id) as session:
                stored = await repo.by_id(session, tenant_id, ticket_id)
                assert stored is not None
                assert stored.queue_day == TODAY
                assert stored.name == "נועה"
                assert stored.phone == phone
                assert stored.visit_type == VisitType.EVENING.value
                # The three columns F58 owns arrive at their DB defaults, which
                # is the whole of what F33 writes to them.
                assert stored.status == QueueTicketStatus.WAITING.value
                assert stored.skip_count == 0
                assert stored.called_at is None
                assert stored.requeued_at is None
                # No consent given, and NULL is the only "no consent on record"
                # sentinel.
                assert stored.marketing_opt_in_at is None
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_insert_records_the_consent_timestamp_when_the_box_was_ticked(app_role_url: str) -> None:
    """The instant comes from the caller's injected clock, not from the DB — the
    same reason `queue_day` is a stored column."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                ticket = await repo.insert(
                    session,
                    tenant_id=tenant_id,
                    queue_day=TODAY,
                    name="נועה",
                    phone=_phone(),
                    visit_type=VisitType.BRIDE.value,
                    marketing_opt_in_at=CONSENT_AT,
                )
                ticket_id = ticket.id

            async with tenant_session(factory, tenant_id) as session:
                stored = await repo.by_id(session, tenant_id, ticket_id)
                assert stored is not None
                assert stored.marketing_opt_in_at == CONSENT_AT
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_by_id_finds_the_live_ticket_and_refuses_the_absent_and_the_deleted(
    app_role_url: str,
) -> None:
    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                live = await _seed(session, tenant_id, created_at=T1)
                gone = await _seed(session, tenant_id, created_at=T2)
                live_id, gone_id = live.id, gone.id

            async with tenant_session(factory, tenant_id) as session:
                await session.execute(
                    update(QueueTicket).where(QueueTicket.id == gone_id).values(deleted_at=REQUEUED)
                )

            async with tenant_session(factory, tenant_id) as session:
                assert (await repo.by_id(session, tenant_id, live_id)) is not None
                assert (await repo.by_id(session, tenant_id, gone_id)) is None
                assert (await repo.by_id(session, tenant_id, uuid.uuid4())) is None
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_by_id_refuses_a_ticket_belonging_to_another_tenant(app_role_url: str) -> None:
    """The explicit tenant_id predicate, and this is the test that makes it more
    than decoration.

    The read runs inside tenant A's session, so RLS would happily return the row
    — the predicate is what refuses it. RLS is safe today only because every
    shipped path goes through `db/tenant.py`; a future caller reaching this repo
    outside `tenant_session`, or with the wrong tenant bound, would otherwise
    turn a guessed UUID into a cross-tenant read of a woman's name and phone."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_a) as session:
                ticket = await _seed(session, tenant_a, created_at=T1)
                ticket_id = ticket.id

            async with tenant_session(factory, tenant_a) as session:
                assert (await repo.by_id(session, tenant_a, ticket_id)) is not None
                assert (await repo.by_id(session, tenant_b, ticket_id)) is None
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_position_counts_the_earlier_waiting_tickets_of_the_same_day(app_role_url: str) -> None:
    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                first = await _seed(session, tenant_id, created_at=T1)
                second = await _seed(session, tenant_id, created_at=T2)
                third = await _seed(session, tenant_id, created_at=T3)

                assert await repo.position(session, tenant_id, first) == 1
                assert await repo.position(session, tenant_id, second) == 2
                assert await repo.position(session, tenant_id, third) == 3
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_position_is_null_for_a_ticket_that_is_not_waiting(app_role_url: str) -> None:
    """A ticket in service, done or removed has no place in a queue, and
    reporting one would be a number with no referent."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                await _seed(session, tenant_id, created_at=T1)
                for status in (
                    QueueTicketStatus.IN_SERVICE,
                    QueueTicketStatus.DONE,
                    QueueTicketStatus.REMOVED,
                ):
                    ticket = await _seed(session, tenant_id, created_at=T2, status=status.value)
                    assert await repo.position(session, tenant_id, ticket) is None, status
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_position_ignores_closed_deleted_and_other_day_tickets(app_role_url: str) -> None:
    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                await _seed(session, tenant_id, created_at=T1, status=QueueTicketStatus.DONE.value)
                await _seed(
                    session, tenant_id, created_at=T1, status=QueueTicketStatus.REMOVED.value
                )
                await _seed(
                    session, tenant_id, created_at=T1, status=QueueTicketStatus.IN_SERVICE.value
                )
                await _seed(session, tenant_id, created_at=T1, deleted_at=T2)
                await _seed(session, tenant_id, created_at=Y1, queue_day=YESTERDAY)

                mine = await _seed(session, tenant_id, created_at=T3)
                # Five earlier rows, none of them countable.
                assert await repo.position(session, tenant_id, mine) == 1
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_a_ticket_left_waiting_from_an_earlier_day_does_not_render_position_one(
    app_role_url: str,
) -> None:
    """The `:day` binding, asserted directly — bind the count to
    `today_jerusalem(clock)` instead of to the ticket's own `queue_day` and a
    ticket left waiting from an earlier day counts zero earlier sort keys and
    renders 1, telling someone who walked out yesterday that she is next.

    Nothing in the shipped product can close a ticket (every status transition is
    F58's), so a stale waiting ticket is the NORMAL state of things, not an edge
    case."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                await _seed(session, tenant_id, created_at=Y1, queue_day=YESTERDAY)
                stale = await _seed(session, tenant_id, created_at=Y2, queue_day=YESTERDAY)
                today_first = await _seed(session, tenant_id, created_at=T1)

                assert await repo.position(session, tenant_id, stale) == 2
                # …and today's queue is independent of yesterday's two rows.
                assert await repo.position(session, tenant_id, today_first) == 1
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_requeueing_the_earliest_ticket_moves_it_to_the_back_and_shifts_the_rest(
    app_role_url: str,
) -> None:
    """COALESCE(requeued_at, created_at) rather than created_at alone is what
    makes F58's skip a ONE-COLUMN write instead of a renumbering pass. It ships
    in F33 even though nothing writes requeued_at yet, because the ordering is
    F33's published contract and F58 must not be able to change it."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                first = await _seed(session, tenant_id, created_at=T1)
                second = await _seed(session, tenant_id, created_at=T2)
                third = await _seed(session, tenant_id, created_at=T3)
                assert await repo.position(session, tenant_id, first) == 1

                await session.execute(
                    update(QueueTicket)
                    .where(QueueTicket.id == first.id)
                    .values(requeued_at=REQUEUED)
                )
                await session.refresh(first)

                assert await repo.position(session, tenant_id, first) == 3
                assert await repo.position(session, tenant_id, second) == 1
                assert await repo.position(session, tenant_id, third) == 2
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_ties_on_the_sort_key_do_not_crash(app_role_url: str) -> None:
    """Two rows sharing an instant is not hypothetical: `now()` is
    transaction-scoped, so any future writer that inserts two tickets in one
    transaction produces exactly this. The comparison is strict, so tied rows
    report the same number rather than raising or skipping one."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                left = await _seed(session, tenant_id, created_at=T1)
                right = await _seed(session, tenant_id, created_at=T1)
                after = await _seed(session, tenant_id, created_at=T2)

                assert await repo.position(session, tenant_id, left) == 1
                assert await repo.position(session, tenant_id, right) == 1
                assert await repo.position(session, tenant_id, after) == 3
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_two_tickets_for_one_phone_on_one_day_both_exist_and_report_consecutive_positions(
    app_role_url: str,
) -> None:
    """Ruling 3, asserted as a DECISION rather than left to be discovered.

    There is no uniqueness on this table, so a second submission of the same
    phone mints a second ticket. That is what closes the presence oracle and what
    makes the day-long targeted denial impossible; the cost is that F58 has to
    merge or remove the duplicate, and it is stated here rather than smoothed
    over because it is the thing a reviewer notices first."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        phone = _phone()
        try:
            async with tenant_session(factory, tenant_id) as session:
                first = await _seed(session, tenant_id, created_at=T1, phone=phone)
                second = await _seed(session, tenant_id, created_at=T2, phone=phone)

                assert first.id != second.id
                assert await repo.position(session, tenant_id, first) == 1
                assert await repo.position(session, tenant_id, second) == 2
                assert (await repo.by_id(session, tenant_id, first.id)) is not None
                assert (await repo.by_id(session, tenant_id, second.id)) is not None
        finally:
            await engine.dispose()

    asyncio.run(check())
