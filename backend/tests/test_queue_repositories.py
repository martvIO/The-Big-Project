"""Round-trips for the F33 queue repository and F59's board read, as the
non-owner app role. The isolation half lives in test_queue_isolation.py.

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
from app.queue.schemas import QueueBoardEntry
from app.queue.validation import BOARD_ROW_LIMIT, board_display_name

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
T4 = datetime.datetime(2026, 8, 3, 7, 30, tzinfo=datetime.UTC)
T5 = datetime.datetime(2026, 8, 3, 7, 40, tzinfo=datetime.UTC)
REQUEUED = datetime.datetime(2026, 8, 3, 9, 0, tzinfo=datetime.UTC)
CALLED_AT = datetime.datetime(2026, 8, 3, 8, 0, tzinfo=datetime.UTC)
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
    called_at: datetime.datetime | None = None,
    name: str = "נועה",
) -> QueueTicket:
    """Seeds a row DIRECTLY rather than through the repository's `insert`, which
    takes no `created_at` — production never sets one. The position tests are
    about the count query, not about the writer, and a deterministic sort key is
    what makes "position 2" mean something.

    `called_at` is seeded here for the same reason: nothing in the shipped
    product writes it (every status transition and every call-forward is F58's),
    so the board's `called` flag has no other way to be exercised at all.

    `name` is a parameter because F59's board rows are told apart BY name — the
    payload carries no id — so a suite where every row is «נועה» could not
    assert which row landed where.
    """
    row = QueueTicket(
        tenant_id=tenant_id,
        queue_day=queue_day,
        name=name,
        phone=phone or _phone(),
        visit_type=VisitType.BRIDE.value,
        status=status,
        created_at=created_at,
        requeued_at=requeued_at,
        deleted_at=deleted_at,
        called_at=called_at,
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


# --- F59's board read: the same rows as `position`, as a list ---


def test_the_board_order_agrees_with_the_position_count(app_role_url: str) -> None:
    """THE test of this feature, and it pins the two reads against EACH OTHER
    rather than each against a literal.

    If the board orders differently from the position endpoint, a woman's phone
    says she is 3rd and the wall says she is 4th — on a screen a room full of
    strangers is reading. Index `i` of the board satisfies `position == i + 1`
    only if both reads range over an identical predicate set under an identical
    sort key, so the assertion is made row by row over the WHOLE board.

    It is also the Risk-6 alarm, and the NOISE is what makes it one: the four
    rows neither read may count are seeded alongside the five that both must.
    Widen the board's status filter on one side only and a `done` row joins the
    list while `position` answers None for it — which is this assertion going
    red. Without the noise the two reads agree vacuously and the alarm is
    decoration.
    """

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                # Seeded out of arrival order on purpose: physical row order
                # must not be what makes this pass.
                by_name = {
                    "גימל": await _seed(session, tenant_id, created_at=T3, name="גימל"),
                    "אלף": await _seed(session, tenant_id, created_at=T1, name="אלף"),
                    "הא": await _seed(session, tenant_id, created_at=T5, name="הא"),
                    "בית": await _seed(session, tenant_id, created_at=T2, name="בית"),
                    "דלת": await _seed(session, tenant_id, created_at=T4, name="דלת"),
                }
                # Four rows that belong to neither read, every one of them
                # EARLIER than «אלף» so that counting any of them shifts every
                # position by at least one.
                noise = {
                    "סיימה": await _seed(
                        session,
                        tenant_id,
                        created_at=Y1,
                        status=QueueTicketStatus.DONE.value,
                        name="סיימה",
                    ),
                    "בטיפול": await _seed(
                        session,
                        tenant_id,
                        created_at=Y1,
                        status=QueueTicketStatus.IN_SERVICE.value,
                        name="בטיפול",
                    ),
                    "נמחקה": await _seed(
                        session, tenant_id, created_at=Y1, deleted_at=T1, name="נמחקה"
                    ),
                    "אתמול": await _seed(
                        session, tenant_id, created_at=Y2, queue_day=YESTERDAY, name="אתמול"
                    ),
                }

                rows, total = await repo.board(session, tenant_id, TODAY, limit=BOARD_ROW_LIMIT)
                assert total == len(by_name)
                assert [row.name for row in rows] == ["אלף", "בית", "גימל", "דלת", "הא"]
                for index, row in enumerate(rows):
                    ticket = (by_name | noise)[row.name]
                    assert await repo.position(session, tenant_id, ticket) == index + 1
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_requeueing_moves_a_row_to_the_back_of_the_board_and_the_two_reads_still_agree(
    app_role_url: str,
) -> None:
    """COALESCE(requeued_at, created_at) is the queue's published order, and the
    board renders that order as a list. F58's skip is one column write, so it
    must move the row on the wall and on her phone by the same amount."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                by_name = {
                    "אלף": await _seed(session, tenant_id, created_at=T1, name="אלף"),
                    "בית": await _seed(session, tenant_id, created_at=T2, name="בית"),
                    "גימל": await _seed(session, tenant_id, created_at=T3, name="גימל"),
                }
                rows, _ = await repo.board(session, tenant_id, TODAY, limit=BOARD_ROW_LIMIT)
                assert [row.name for row in rows] == ["אלף", "בית", "גימל"]

                await session.execute(
                    update(QueueTicket)
                    .where(QueueTicket.id == by_name["אלף"].id)
                    .values(requeued_at=REQUEUED)
                )
                await session.refresh(by_name["אלף"])

                rows, total = await repo.board(session, tenant_id, TODAY, limit=BOARD_ROW_LIMIT)
                assert [row.name for row in rows] == ["בית", "גימל", "אלף"]
                assert total == 3
                for index, row in enumerate(rows):
                    assert await repo.position(session, tenant_id, by_name[row.name]) == index + 1
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_the_board_shows_only_todays_live_waiting_rows(app_role_url: str) -> None:
    """The four predicates, each with a row that must not appear. `in_service`
    is not waiting; `done` and `removed` are terminal; a soft-deleted row is
    gone; and a ticket nobody closed overnight must not sit at position 1 on a
    wall forever, which is why the board binds TODAY where `position` binds the
    ticket's own day."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                for status in (
                    QueueTicketStatus.IN_SERVICE,
                    QueueTicketStatus.DONE,
                    QueueTicketStatus.REMOVED,
                ):
                    await _seed(
                        session, tenant_id, created_at=T1, status=status.value, name=status.value
                    )
                await _seed(session, tenant_id, created_at=T1, deleted_at=T2, name="נמחקה")
                await _seed(session, tenant_id, created_at=Y1, queue_day=YESTERDAY, name="אתמול")
                await _seed(session, tenant_id, created_at=T3, name="היחידה")

                rows, total = await repo.board(session, tenant_id, TODAY, limit=BOARD_ROW_LIMIT)
                assert [row.name for row in rows] == ["היחידה"]
                assert total == 1
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_the_board_never_shows_another_tenants_queue(app_role_url: str) -> None:
    """The explicit tenant_id predicate, which is what refuses the row even
    inside a session where RLS would return it."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_b) as session:
                await _seed(session, tenant_b, created_at=T1, name="זרה")

            async with tenant_session(factory, tenant_a) as session:
                await _seed(session, tenant_a, created_at=T2, name="שלנו")
                rows, total = await repo.board(session, tenant_a, TODAY, limit=BOARD_ROW_LIMIT)
                assert [row.name for row in rows] == ["שלנו"]
                assert total == 1

                # …and the same session asked for tenant B's board answers
                # nothing, rather than leaking A's rows under B's id.
                rows, total = await repo.board(session, tenant_b, TODAY, limit=BOARD_ROW_LIMIT)
                assert list(rows) == []
                assert total == 0
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_the_cap_truncates_the_rows_and_never_the_total(app_role_url: str) -> None:
    """`waiting_total` is the UNTRUNCATED count and the overflow line has no
    other source: `len(entries)` would make «ועוד N» say zero forever, silently,
    on a wall."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                for index in range(BOARD_ROW_LIMIT + 3):
                    await _seed(
                        session,
                        tenant_id,
                        created_at=T1 + datetime.timedelta(minutes=index),
                        name=f"א{index}",
                    )

                rows, total = await repo.board(session, tenant_id, TODAY, limit=BOARD_ROW_LIMIT)
                assert len(rows) == BOARD_ROW_LIMIT
                assert total == BOARD_ROW_LIMIT + 3
                assert [row.name for row in rows] == [f"א{i}" for i in range(BOARD_ROW_LIMIT)]
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_a_queue_of_exactly_the_cap_is_not_an_overflow(app_role_url: str) -> None:
    """The boundary: at exactly BOARD_ROW_LIMIT the totals match, so the client
    renders no overflow line. One row either side of this is the off-by-one that
    would put «ועוד 0» on the wall."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                for index in range(BOARD_ROW_LIMIT):
                    await _seed(
                        session,
                        tenant_id,
                        created_at=T1 + datetime.timedelta(minutes=index),
                        name=f"א{index}",
                    )
                rows, total = await repo.board(session, tenant_id, TODAY, limit=BOARD_ROW_LIMIT)
                assert len(rows) == BOARD_ROW_LIMIT
                assert total == BOARD_ROW_LIMIT
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_a_second_ticket_for_the_same_phone_is_a_second_row(app_role_url: str) -> None:
    """Ruling 3 on the wall. One woman who re-scanned the QR — the ordinary
    re-entry path, since the pointer does not survive a fresh browsing context —
    renders at two positions with the same first name, and `waiting_total`
    counts her twice.

    The board MUST NOT deduplicate. The only key that would identify her is
    `phone`, and this repository's class docstring promises no read is keyed on
    it and calls that absence the security property. Deduplicating here would be
    the one read that breaks it, on the one endpoint where breaking it is worst.
    F58 owns the merge.
    """

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        phone = _phone()
        try:
            async with tenant_session(factory, tenant_id) as session:
                await _seed(session, tenant_id, created_at=T1, phone=phone, name="נועה כהן")
                await _seed(session, tenant_id, created_at=T2, phone=phone, name="נועה כהן")

                rows, total = await repo.board(session, tenant_id, TODAY, limit=BOARD_ROW_LIMIT)
                assert [row.name for row in rows] == ["נועה כהן", "נועה כהן"]
                assert total == 2
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_a_tie_on_the_sort_key_orders_by_id_and_does_not_flicker(app_role_url: str) -> None:
    """`, id ASC`. Without it a tie makes the board's own row order
    non-deterministic across polls, which on a wall screen is two names swapping
    every five seconds.

    Every row here shares one instant, which is a real tie rather than a
    contrived one: `now()` is transaction-scoped in Postgres, so any writer that
    inserts two tickets in one transaction produces exactly this. The order is
    asserted against the id order — the mechanism itself — because "the same on
    two calls" alone would pass on physical order.

    ⚠ It does NOT buy agreement with `position()` on a tie: the count has no
    second key, so tied rows both report the same number while the board gives
    them consecutive ones. Accepted residual, recorded rather than fixed by
    editing a shipped read for a one-in-a-microsecond cosmetic case.
    """

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                tied = [
                    await _seed(session, tenant_id, created_at=T1, name=f"א{index}")
                    for index in range(BOARD_ROW_LIMIT)
                ]
                expected = [row.name for row in sorted(tied, key=lambda row: row.id)]

                first, _ = await repo.board(session, tenant_id, TODAY, limit=BOARD_ROW_LIMIT)
                second, _ = await repo.board(session, tenant_id, TODAY, limit=BOARD_ROW_LIMIT)
                assert [row.name for row in first] == expected
                assert [row.name for row in second] == expected
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_an_empty_day_is_an_empty_board_and_never_a_null(app_role_url: str) -> None:
    """A screen that answered 404 when nobody is waiting would render its error
    arm for most of the shop day."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                rows, total = await repo.board(session, tenant_id, TODAY, limit=BOARD_ROW_LIMIT)
                assert list(rows) == []
                assert total == 0
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_a_called_ticket_is_still_on_the_board_and_carries_its_instant(app_role_url: str) -> None:
    """Seeded directly, because nothing in the shipped product writes
    `called_at` — F58 does, and until it ships this column is null on every row
    in production. A called ticket is still `waiting` until F58 also writes a
    status, so it stays on the board and the service turns the instant into the
    boolean the wire carries."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                await _seed(session, tenant_id, created_at=T1, name="נקראה", called_at=CALLED_AT)
                await _seed(session, tenant_id, created_at=T2, name="ממתינה")

                rows, total = await repo.board(session, tenant_id, TODAY, limit=BOARD_ROW_LIMIT)
                assert total == 2
                assert [(row.name, row.called_at) for row in rows] == [
                    ("נקראה", CALLED_AT),
                    ("ממתינה", None),
                ]
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_no_surname_reaches_the_wire(app_role_url: str) -> None:
    """⚠ THE REAL HOME of that assertion, against real SQL and a real stored
    surname. The e2e version cannot fail — a browser test can only see what the
    server chose to send — so it is deliberately not written there.

    Two halves, and both matter. The repository projects the WHOLE stored name,
    so the first assertion is what keeps the second from passing vacuously;
    `board_display_name` is what drops the surname before the schema, and the
    serialised entry is where the promise has to hold. The service composes
    exactly these two steps and nothing else.
    """

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                await _seed(session, tenant_id, created_at=T1, name="NOA COHEN")

                rows, _ = await repo.board(session, tenant_id, TODAY, limit=BOARD_ROW_LIMIT)
                assert rows[0].name == "NOA COHEN"

                entry = QueueBoardEntry(
                    position=1,
                    first_name=board_display_name(rows[0].name),
                    called=rows[0].called_at is not None,
                )
                assert entry.first_name == "NOA"
                assert "COHEN" not in entry.model_dump_json()
        finally:
            await engine.dispose()

    asyncio.run(check())


# --- F58's five writers, the refusal projection and the panel's two reads -----
#
# ⚠ WHAT THIS MODULE CAN AND CANNOT SEE — mutations RUN, not reasoned about.
#
# Every test here is single-threaded, so it proves the STATEMENT and never the
# INTERLEAVE. `AND skip_count = :seen_skip_count` does red here (a test can hand
# it a stale count deliberately) but what it red-flags is only that the conjunct
# is spelled; the DAMAGE it prevents — a woman removed by two ordinary single
# taps with the confirm never rendered — needs two transactions and is
# `test_queue_dispatch_db.py`'s. `skip_count = skip_count + 1` cannot lose an
# update here at all, and is pinned there too.
#
# The plan predicted the `seen_skip_count` mutation would stay GREEN in this
# module. It was wrong, and in the safe direction.


def test_claim_by_id_takes_the_named_ticket_and_refuses_every_other_state(
    app_role_url: str,
) -> None:
    """D4's conditional UPDATE. Rowcount 0 — spelled `None` — on a non-`waiting`,
    soft-deleted, foreign-tenant or missing ticket, which is what makes the
    service's refusal read the ONLY place those four are told apart."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        other_tenant = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                waiting = await _seed(session, tenant_id, created_at=T1)
                served = await _seed(
                    session, tenant_id, created_at=T2, status=QueueTicketStatus.IN_SERVICE.value
                )
                deleted = await _seed(session, tenant_id, created_at=T3, deleted_at=T3)

                taken = await repo.claim_by_id(session, tenant_id, waiting.id)
                assert taken is not None
                assert (taken.id, taken.name, taken.visit_type, taken.called_at) == (
                    waiting.id,
                    "נועה",
                    VisitType.BRIDE.value,
                    None,
                )
                assert await repo.claim_by_id(session, tenant_id, waiting.id) is None
                assert await repo.claim_by_id(session, tenant_id, served.id) is None
                assert await repo.claim_by_id(session, tenant_id, deleted.id) is None
                assert await repo.claim_by_id(session, tenant_id, uuid.uuid4()) is None
                assert await repo.claim_by_id(session, other_tenant, waiting.id) is None
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_close_moves_an_in_service_ticket_to_done_and_never_resurrects_a_removed_one(
    app_role_url: str,
) -> None:
    """⚠ `AND status = 'in_service'` is the conjunct, and the removed row is what
    proves it. A manager who removed a woman mid-fitting must not have that
    removal rewritten as `done` when the staffer frees the room, and rowcount 0
    there raises nothing — the room is free, which is what she asked for."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                served = await _seed(
                    session, tenant_id, created_at=T1, status=QueueTicketStatus.IN_SERVICE.value
                )
                removed = await _seed(
                    session, tenant_id, created_at=T2, status=QueueTicketStatus.REMOVED.value
                )

                assert await repo.close(session, tenant_id, served.id) is True
                assert await repo.close(session, tenant_id, served.id) is False
                assert await repo.close(session, tenant_id, removed.id) is False

                await session.refresh(served)
                await session.refresh(removed)
                assert served.status == QueueTicketStatus.DONE.value
                assert removed.status == QueueTicketStatus.REMOVED.value
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_the_first_skip_requeues_her_and_clears_the_call_and_the_second_removes_her(
    app_role_url: str,
) -> None:
    """D6, in one statement, and three of its parts are asserted here.

    ⚠ `called_at = NULL` is the one a reader is most likely to think decorative:
    she was called and did not come — that is WHY she is being skipped — so
    leaving the stamp would highlight her on F59's public wall board at the BACK
    of the queue and leave her own page reading «אפשר לגשת לדלפק» indefinitely.

    ⚠ The `CASE` reads the PRE-update `skip_count`, because every SET expression
    in one UPDATE is evaluated against the old row. `skip_count + 1 >=
    SKIP_LIMIT` therefore means "this is her second skip", which is the rule.
    """

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                ticket = await _seed(session, tenant_id, created_at=T1, called_at=CALLED_AT)

                first = await repo.skip(
                    session, tenant_id, ticket.id, now=REQUEUED, seen_skip_count=0
                )
                assert first is not None
                assert (first.skip_count, first.status) == (1, QueueTicketStatus.WAITING.value)
                await session.refresh(ticket)
                assert ticket.requeued_at == REQUEUED
                assert ticket.called_at is None

                second = await repo.skip(session, tenant_id, ticket.id, now=T5, seen_skip_count=1)
                assert second is not None
                assert (second.skip_count, second.status) == (2, QueueTicketStatus.REMOVED.value)
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_a_skip_sending_a_stale_count_writes_nothing(app_role_url: str) -> None:
    """⚠ THE CONJUNCT THAT STOPS TWO ORDINARY SINGLE TAPS REMOVING A CUSTOMER.

    Single-threaded, this only shows that the predicate is spelled at all — the
    race it exists for is `test_queue_dispatch_db.py`'s
    `test_a_concurrent_second_first_skip_is_refused_rather_than_removing_her`,
    where dropping the conjunct removes a woman with the confirm never shown.
    """

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                ticket = await _seed(session, tenant_id, created_at=T1)

                assert (
                    await repo.skip(session, tenant_id, ticket.id, now=REQUEUED, seen_skip_count=1)
                    is None
                )
                await session.refresh(ticket)
                assert ticket.skip_count == 0
                assert ticket.requeued_at is None
                assert ticket.status == QueueTicketStatus.WAITING.value
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_a_second_call_keeps_the_first_timestamp_and_leaves_her_waiting(
    app_role_url: str,
) -> None:
    """⚠ `status` IS NOT TOUCHED, and F59's spec records that its board breaks if
    it is: D3's predicate there is `status == 'waiting'`, so flipping the status
    at call time drops the called row off the wall board the instant it is
    called — the opposite of the feature. The one contract F59 could not enforce
    for itself.

    `called_at IS NULL` in the predicate is `release()`'s shipped idempotence one
    table over: a re-call keeps the FIRST stamp rather than moving it.
    """

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                ticket = await _seed(session, tenant_id, created_at=T1)

                first = await repo.call(session, tenant_id, ticket.id, now=CALLED_AT)
                assert first is not None
                assert first.called_at == CALLED_AT
                assert await repo.call(session, tenant_id, ticket.id, now=T5) is None

                await session.refresh(ticket)
                assert ticket.called_at == CALLED_AT
                assert ticket.status == QueueTicketStatus.WAITING.value
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_remove_writes_removed_once_and_only_from_waiting(app_role_url: str) -> None:
    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                ticket = await _seed(session, tenant_id, created_at=T1)
                served = await _seed(
                    session, tenant_id, created_at=T2, status=QueueTicketStatus.IN_SERVICE.value
                )

                assert await repo.remove(session, tenant_id, ticket.id) is True
                assert await repo.remove(session, tenant_id, ticket.id) is False
                assert await repo.remove(session, tenant_id, served.id) is False

                await session.refresh(ticket)
                await session.refresh(served)
                assert ticket.status == QueueTicketStatus.REMOVED.value
                assert served.status == QueueTicketStatus.IN_SERVICE.value
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_status_of_answers_the_pair_the_three_refusal_tables_need(app_role_url: str) -> None:
    """A PROJECTION and never `by_id`, and the reason is not the answer — the two
    return the same facts. `by_id` is a `select(QueueTicket)` ENTITY read, so it
    would pull `phone` and `marketing_opt_in_at` into the same session as an
    ORM-enabled UPDATE and put a `QueueTicket` in the identity map at exactly the
    moment `_refreshed`'s docstring says this repo has been bitten three times.

    ⚠ MUTATION PERFORMED, and it did NOT come back the way the plan predicted.
    Reimplementing `status_of` as `by_id(...)` → `(row.status, row.skip_count)`
    reds the last two lines — `('waiting', 0)` for a ticket that has just been
    skipped to 1. The entity read hands back the instance already in the identity
    map, which `synchronize_session=False` deliberately did not refresh, so the
    refusal read would answer the PRE-skip count and `skip` would refuse a caller
    who sent the value it had just been told. The minimisation argument was the
    stated reason for the projection; this is the second one, and it is a live
    defect rather than a policy.
    """

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                ticket = await _seed(session, tenant_id, created_at=T1)
                deleted = await _seed(session, tenant_id, created_at=T2, deleted_at=T2)

                assert await repo.status_of(session, tenant_id, ticket.id) == (
                    QueueTicketStatus.WAITING.value,
                    0,
                )
                assert await repo.status_of(session, tenant_id, deleted.id) is None
                assert await repo.status_of(session, tenant_id, uuid.uuid4()) is None
                assert await repo.status_of(session, uuid.uuid4(), ticket.id) is None

                await repo.skip(session, tenant_id, ticket.id, now=REQUEUED, seen_skip_count=0)
                assert await repo.status_of(session, tenant_id, ticket.id) == (
                    QueueTicketStatus.WAITING.value,
                    1,
                )
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_the_panel_read_is_the_boards_rows_in_the_boards_order(app_role_url: str) -> None:
    """⚠ `_live_waiting()` and `_sort_key()` CALLED, never re-spelled — the same
    noise the board's own agreement test seeds, for the same reason: a one-sided
    widening has to SHIFT a position, and an all-waiting seed makes the assertion
    blind. Every noise row is earlier than «אלף».

    The `phone` column IS selected and never leaves this list: it is the key
    D9's duplicate flag groups on, computed in the service, and no wire shape
    carries it.
    """

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                await _seed(session, tenant_id, created_at=T3, name="גימל")
                await _seed(session, tenant_id, created_at=T1, name="אלף", called_at=CALLED_AT)
                await _seed(session, tenant_id, created_at=T2, name="בית")
                await _seed(
                    session,
                    tenant_id,
                    created_at=Y1,
                    status=QueueTicketStatus.DONE.value,
                    name="סיימה",
                )
                await _seed(
                    session,
                    tenant_id,
                    created_at=Y1,
                    status=QueueTicketStatus.IN_SERVICE.value,
                    name="בטיפול",
                )
                await _seed(session, tenant_id, created_at=Y1, deleted_at=T1, name="נמחקה")
                await _seed(session, tenant_id, created_at=Y2, queue_day=YESTERDAY, name="אתמול")

                rows = await repo.waiting_for_panel(session, tenant_id, TODAY, limit=100)

                assert [row.name for row in rows] == ["אלף", "בית", "גימל"]
                assert [row.called_at for row in rows] == [CALLED_AT, None, None]
                assert [row.skip_count for row in rows] == [0, 0, 0]
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_the_panel_read_is_capped_and_the_cap_is_what_truncated_is_derived_from(
    app_role_url: str,
) -> None:
    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            async with tenant_session(factory, tenant_id) as session:
                for index in range(4):
                    await _seed(
                        session,
                        tenant_id,
                        created_at=T1 + datetime.timedelta(minutes=index),
                        name=f"ממתינה {index}",
                    )

                assert len(await repo.waiting_for_panel(session, tenant_id, TODAY, limit=3)) == 3
                assert len(await repo.waiting_for_panel(session, tenant_id, TODAY, limit=9)) == 4
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_the_in_service_projection_is_todays_phones_and_nothing_else(app_role_url: str) -> None:
    """⚠ `_live_waiting` CANNOT be reused here and that is the whole point of the
    second statement: its third predicate is `status == 'waiting'` and these are
    the rows that are NOT. A phone-only projection — no name, no id, nothing that
    could be rendered by accident."""

    async def check() -> None:
        engine, factory = _factory(app_role_url)
        repo = QueueTicketsRepository()
        tenant_id = uuid.uuid4()
        try:
            served, waiting_phone, yesterday, swept = (_phone() for _ in range(4))
            async with tenant_session(factory, tenant_id) as session:
                await _seed(
                    session,
                    tenant_id,
                    created_at=T1,
                    status=QueueTicketStatus.IN_SERVICE.value,
                    phone=served,
                )
                await _seed(session, tenant_id, created_at=T2, phone=waiting_phone)
                await _seed(
                    session,
                    tenant_id,
                    created_at=Y1,
                    queue_day=YESTERDAY,
                    status=QueueTicketStatus.IN_SERVICE.value,
                    phone=yesterday,
                )
                await _seed(
                    session,
                    tenant_id,
                    created_at=T3,
                    status=QueueTicketStatus.IN_SERVICE.value,
                    deleted_at=T3,
                    phone=swept,
                )

                assert await repo.in_service_phones(session, tenant_id, TODAY) == {served}
        finally:
            await engine.dispose()

    asyncio.run(check())
