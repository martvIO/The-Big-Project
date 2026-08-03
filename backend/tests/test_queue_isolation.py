"""F33's row in the permanent cross-tenant isolation suite — the crown-jewel
suite `architecture.md:48` calls permanent.

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
