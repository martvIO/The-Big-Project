"""F33's and F59's rows in the permanent cross-tenant isolation suite — the
crown-jewel suite `architecture.md:48` calls permanent.

`queue_tickets` carries a woman's name, her mobile and, when she ticked the box,
a consent timestamp. One boutique's walk-in list must be invisible to every
other, and the consent column rides the same table, so "B cannot read or set A's
consent" falls out of the same assertions rather than needing a case of its own.

Connected ONLY as the non-owner `boutique_app` role over a `NullPool` engine via
`app_role_url` — never `migrated_db`. The container superuser bypasses RLS and
GRANTs unconditionally, and every assertion here would pass vacuously; that is
not a hypothetical, it is what the raw counts below were mutation-checked
against.

**Two assertion shapes, and the difference is load-bearing.** The repository's
own `by_id` carries an explicit `tenant_id` predicate as defence in depth, so a
`by_id` miss proves only that Python filtered — it is green with RLS switched
off entirely. The `SELECT count(*) FROM queue_tickets` reads below carry NO
tenant predicate, so they are answered by the policy alone. They are what makes
this module about RLS. `test_queue_repositories.py` owns the mirror image: the
predicate asserted from INSIDE the owning tenant's session, where RLS would
happily return the row.

The phone is deliberately the SAME string in both tenants. Under Ruling 3 that
proves nothing about an index — there is none — but it is still the statement
that a phone number is not a cross-tenant identity.

**F59 raises the stakes of every line above.** Until the wall board there was no
route anywhere in the product that answered with a customer's NAME to an
unauthenticated caller. There is now, it takes no body, it is reachable by
anyone who can resolve the host, and a wall screen polls it every five seconds
for months. A tenant-scoping defect on any other surface leaks to somebody who
already logged in; on this one it publishes another boutique's customers to a
television. That is why the board's isolation is asserted here, in the suite the
architecture calls permanent, rather than only in the repository suite.
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
from app.db.repositories.queue_tickets import QueueTicketsRepository
from app.db.tenant import tenant_session
from app.models.constants import QueueTicketStatus, VisitType
from app.models.queue_ticket import QueueTicket
from app.queue.service import QueueService
from app.queue.validation import QueueTicketNotFoundError

pytestmark = pytest.mark.db

# One number, both boutiques. A phone is not an identity across tenants.
PHONE = "+972501234567"
DAY = datetime.date(2026, 8, 3)
NOW = datetime.datetime(2026, 8, 3, 7, 0, tzinfo=datetime.UTC)

# ⚠ DISTINCTIVE ON PURPOSE, and every token of every one of them is searched for
# in the other tenant's payload below. Against the module's own «נועה»/«שירה» the
# cross-tenant string search would be near-vacuous — «נועה» is the name half this
# suite already seeds everywhere, so a leak could hand it back and the assertion
# would not notice. Two tokens each, so the surname half is also searched for and
# `board_display_name`'s truncation cannot be what makes the test pass.
A_NAMES = ("אביגיל רוזנבלט", "תמר בן-ציון", "שולמית פרידמן")
A_FIRST_NAMES = ["אביגיל", "תמר", "שולמית"]
B_NAME = "שירה לוי"


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _service(factory: async_sessionmaker[AsyncSession]) -> QueueService:
    return QueueService(
        factory,
        create_limiter=FixedWindowRateLimiter(200, 3600.0, lambda: 0.0),
        position_ticket_limiter=FixedWindowRateLimiter(30, 60.0, lambda: 0.0),
        position_miss_limiter=FixedWindowRateLimiter(120, 60.0, lambda: 0.0),
        board_limiter=FixedWindowRateLimiter(600, 60.0, lambda: 0.0),
        clock=lambda: NOW,
    )


async def _seed(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    created_at: datetime.datetime,
    name: str,
) -> QueueTicket:
    row = QueueTicket(
        tenant_id=tenant_id,
        queue_day=DAY,
        name=name,
        phone=PHONE,
        visit_type=VisitType.BRIDE.value,
        status=QueueTicketStatus.WAITING.value,
        created_at=created_at,
        marketing_opt_in_at=created_at,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def _visible_count(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> int:
    """No tenant predicate anywhere in the statement — RLS is the only thing
    that can answer this, which is what stops the assertion being vacuous."""
    async with tenant_session(factory, tenant_id) as session:
        return (await session.execute(text("SELECT count(*) FROM queue_tickets"))).scalar_one()


async def test_a_second_tenant_sees_nothing_of_the_firsts_queue(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    repo = QueueTicketsRepository()
    try:
        async with tenant_session(factory, tenant_a) as session:
            ticket = await _seed(session, tenant_a, created_at=NOW, name="נועה")
            ticket_id = ticket.id

        assert await _visible_count(factory, tenant_b) == 0

        async with tenant_session(factory, tenant_b) as session:
            assert await repo.by_id(session, tenant_b, ticket_id) is None
            # Her name, her number and her consent stamp, asked for without a
            # tenant predicate. RLS answers zero rows.
            rows = await session.execute(
                text("SELECT name, phone, marketing_opt_in_at FROM queue_tickets")
            )
            assert rows.all() == []

        assert await _visible_count(factory, tenant_a) == 1
    finally:
        await engine.dispose()


async def test_both_tenants_hold_a_ticket_on_the_identical_phone_and_day_and_each_sees_one(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_a) as session:
            a_ticket = await _seed(session, tenant_a, created_at=NOW, name="נועה")
            a_id, a_created = a_ticket.id, a_ticket.created_at
        async with tenant_session(factory, tenant_b) as session:
            b_ticket = await _seed(session, tenant_b, created_at=NOW, name="שירה")
            b_id = b_ticket.id

        assert a_id != b_id
        assert await _visible_count(factory, tenant_a) == 1
        assert await _visible_count(factory, tenant_b) == 1

        # Both rows survive, and each tenant's one row is her own.
        async with tenant_session(factory, tenant_a) as session:
            names = (await session.execute(text("SELECT name FROM queue_tickets"))).scalars().all()
            assert list(names) == ["נועה"]
        async with tenant_session(factory, tenant_b) as session:
            names = (await session.execute(text("SELECT name FROM queue_tickets"))).scalars().all()
            assert list(names) == ["שירה"]

        # Nothing of A's moved when B wrote the identical number on the same day.
        async with tenant_session(factory, tenant_a) as session:
            row = await session.get(QueueTicket, a_id)
            assert row is not None
            assert (row.phone, row.queue_day, row.created_at) == (PHONE, DAY, a_created)
            assert row.status == QueueTicketStatus.WAITING.value
    finally:
        await engine.dispose()


async def test_the_second_tenants_position_count_never_counts_the_firsts_queue(
    app_role_url: str,
) -> None:
    """Three of A's waiting on the same day; B's single ticket is 1, not 4.

    The count is the one query in F33 that aggregates over other people's rows,
    so it is the one that leaks a competitor's footfall as a NUMBER rather than
    as a row — «how busy is the boutique down the road» answered for free, with
    no row ever crossing the boundary.

    Two assertions, because the repository's own count carries BOTH guards and
    either alone keeps it green: the raw aggregate has no tenant predicate and
    is answered by RLS, `repo.position` is answered by whichever survives.
    """
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    repo = QueueTicketsRepository()
    try:
        async with tenant_session(factory, tenant_a) as session:
            for minute in (0, 10, 20):
                await _seed(
                    session,
                    tenant_a,
                    created_at=NOW + datetime.timedelta(minutes=minute),
                    name="נועה",
                )

        async with tenant_session(factory, tenant_b) as session:
            b_ticket = await _seed(
                session, tenant_b, created_at=NOW + datetime.timedelta(hours=1), name="שירה"
            )
            b_id = b_ticket.id

        async with tenant_session(factory, tenant_b) as session:
            waiting = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM queue_tickets "
                        "WHERE queue_day = :day AND status = 'waiting' AND deleted_at IS NULL"
                    ),
                    {"day": DAY},
                )
            ).scalar_one()
            assert waiting == 1  # not 4 — no tenant predicate in that statement

            b_row = await repo.by_id(session, tenant_b, b_id)
            assert b_row is not None
            assert await repo.position(session, tenant_b, b_row) == 1
    finally:
        await engine.dispose()


async def test_the_position_counts_predicate_refuses_a_foreign_tenant_inside_the_owners_session(
    app_role_url: str,
) -> None:
    """The mirror of `test_by_id_refuses_a_ticket_belonging_to_another_tenant`,
    for the count rather than the fetch — and the only test anywhere that can
    fail if `position`'s explicit `tenant_id` predicate is deleted.

    Everything above runs with RLS bound to the right tenant, so RLS answers it
    and the predicate is invisible. Here the session is bound to A while the
    count is asked for B: RLS returns A's rows happily, and the predicate is the
    only thing that refuses to count them. RLS is safe today only because every
    shipped path goes through `db/tenant.py`; this is what holds the second lock
    for the day a caller reaches the repository with the wrong tenant bound.
    """
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    repo = QueueTicketsRepository()
    try:
        async with tenant_session(factory, tenant_a) as session:
            third = None
            for minute in (0, 10, 20):
                third = await _seed(
                    session,
                    tenant_a,
                    created_at=NOW + datetime.timedelta(minutes=minute),
                    name="נועה",
                )
            assert third is not None
            assert await repo.position(session, tenant_a, third) == 3
            # Same session, same rows, another tenant's id: nothing is counted.
            assert await repo.position(session, tenant_b, third) == 1
    finally:
        await engine.dispose()


async def test_a_board_never_carries_another_tenants_names(app_role_url: str) -> None:
    """A10, and the most consequential assertion in F59.

    Three of A's women, then B's board — which must be empty, not "empty of rows
    B is allowed to see". Then B writes one of her own and A's board is
    unchanged, because a board that grew when the boutique down the road took a
    walk-in would be leaking whether or not it rendered a name.

    The payload is searched as a STRING, token by token, over every one of A's
    names including the surnames — so a leak cannot hide inside a field the
    assertion forgot to name, and `board_display_name` having truncated the row
    cannot be what makes the search come up empty.

    ⚠ The service-level assertions here are the module's WEAKER shape: `board`
    carries an explicit `tenant_id` predicate as defence in depth, so both locks
    hold and either alone keeps them green. The last block is the strong one —
    A's own tenant id, asked for inside a session bound to B. The predicate
    matches A's rows exactly, so nothing but the policy can refuse them, and
    that is the assertion that makes the BOARD part of this module about RLS.
    """
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    service = _service(factory)
    repo = QueueTicketsRepository()
    try:
        async with tenant_session(factory, tenant_a) as session:
            for minute, name in enumerate(A_NAMES):
                await _seed(
                    session,
                    tenant_a,
                    created_at=NOW + datetime.timedelta(minutes=minute),
                    name=name,
                )

        a_board = await service.board(tenant_a)
        assert [entry.first_name for entry in a_board.entries] == A_FIRST_NAMES
        assert a_board.waiting_total == 3

        # B's board before she has anyone: a real empty view, never A's rows and
        # never a miss.
        empty = await service.board(tenant_b)
        assert (empty.entries, empty.waiting_total) == ([], 0)

        async with tenant_session(factory, tenant_b) as session:
            await _seed(session, tenant_b, created_at=NOW, name=B_NAME)

        b_board = await service.board(tenant_b)
        assert [entry.first_name for entry in b_board.entries] == ["שירה"]
        assert b_board.waiting_total == 1

        payload = b_board.model_dump_json()
        for name in A_NAMES:
            for token in name.split():
                assert token not in payload

        # And A's board did not move when B wrote hers.
        a_again = await service.board(tenant_a)
        assert [entry.first_name for entry in a_again.entries] == A_FIRST_NAMES
        assert a_again.waiting_total == 3

        # RLS alone, both directions. A's tenant id asked for inside B's session:
        # the repository's own predicate says "give me tenant A's rows" and they
        # exist, so only the policy can answer nothing. The same call inside A's
        # session returns all three, which is what stops the empty result being
        # explained by the day, the status or a typo.
        async with tenant_session(factory, tenant_b) as session:
            foreign_rows, foreign_total = await repo.board(session, tenant_a, DAY, limit=5)
            assert (list(foreign_rows), foreign_total) == ([], 0)
            # And the raw read, with no tenant predicate at all, cannot see them
            # either — the shape the module docstring calls the load-bearing one.
            names = (await session.execute(text("SELECT name FROM queue_tickets"))).scalars().all()
            assert list(names) == [B_NAME]
        async with tenant_session(factory, tenant_a) as session:
            rows, total = await repo.board(session, tenant_a, DAY, limit=5)
            assert (len(rows), total) == (3, 3)
    finally:
        await engine.dispose()


async def test_a_boards_waiting_total_never_counts_the_other_tenants_queue(
    app_role_url: str,
) -> None:
    """A9, for the aggregate rather than the rows — the sibling of
    `test_the_second_tenants_position_count_never_counts_the_firsts_queue`.

    `waiting_total` is the second query in the product that aggregates over other
    people's rows, and F59 puts its result on a public screen with no credential
    in front of it. Row isolation alone would still answer «how busy is the
    boutique down the road» as a NUMBER, refreshed every five seconds, to anyone
    who can reach the host. Eight of A's against one of B's, so a leak cannot
    coincide with the right answer.

    `_visible_count` is here for the same reason it is everywhere else in this
    module: `board`'s own count carries an explicit `tenant_id` predicate, so the
    service-level totals below are green with RLS switched off entirely. The two
    raw counts carry no tenant predicate and are answered by the policy alone.
    """
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_a) as session:
            for minute in range(8):
                await _seed(
                    session,
                    tenant_a,
                    created_at=NOW + datetime.timedelta(minutes=minute),
                    name=A_NAMES[minute % len(A_NAMES)],
                )
        async with tenant_session(factory, tenant_b) as session:
            await _seed(session, tenant_b, created_at=NOW, name=B_NAME)

        assert await _visible_count(factory, tenant_a) == 8
        assert await _visible_count(factory, tenant_b) == 1

        service = _service(factory)
        # A is over the cap: five rows, eight in the total. B is neither.
        a_board = await service.board(tenant_a)
        assert (len(a_board.entries), a_board.waiting_total) == (5, 8)
        b_board = await service.board(tenant_b)
        assert (len(b_board.entries), b_board.waiting_total) == (1, 1)
    finally:
        await engine.dispose()


async def test_a_foreign_tenants_ticket_id_is_missing_and_never_a_refusal(
    app_role_url: str,
) -> None:
    """404, not 403. A refusal that distinguished "not yours" from "no such
    ticket" would confirm the guessed id exists — and the id is the whole
    capability, so confirming one is the entire attack.
    """
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_a) as session:
            ticket = await _seed(session, tenant_a, created_at=NOW, name="נועה")
            ticket_id = ticket.id

        service = _service(factory)
        with pytest.raises(QueueTicketNotFoundError):
            await service.position(tenant_b, ticket_id)

        # Byte-identical treatment: a wholly invented id raises the same class.
        with pytest.raises(QueueTicketNotFoundError):
            await service.position(tenant_b, uuid.uuid4())

        # And A still reads her own.
        assert (await service.position(tenant_a, ticket_id)).id == ticket_id
    finally:
        await engine.dispose()
