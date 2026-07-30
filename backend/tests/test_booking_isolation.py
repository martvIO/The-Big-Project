"""F13/F16's rows in the permanent cross-tenant isolation suite: customers (a
bride's phone and name under one boutique must be invisible to every other),
bookings (a foreign tenant reads nothing, and its bookings never contend for
another tenant's seats — the slot-seat unique index is scoped per tenant), and
scheduled_messages, which is the codebase's FIRST table read by a background
process rather than by a request.

That last one is why the poller enumerates tenants and claims one
`tenant_session` at a time (D6) instead of taking an RLS exemption: cross-tenant
leakage is the recorded existential risk, and a worker that could see every
tenant's queue would be the widest possible hole in it. The claim test here is
what makes that structural rather than conventional.

Runs as the non-owner boutique_app role over a NullPool engine: the container
superuser bypasses RLS unconditionally, which would make every assertion here
vacuously pass.
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

from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.tenant import tenant_session
from app.models.constants import ScheduledMessageKind, ScheduledMessageStatus

pytestmark = pytest.mark.db

PHONE = "+972501234567"  # deliberately IDENTICAL for both tenants: phone is not a key
T0 = datetime.datetime(2099, 8, 2, 7, 0, tzinfo=datetime.UTC)
ACCEPTED_AT = datetime.datetime(2099, 8, 1, 12, 0, tzinfo=datetime.UTC)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_same_phone_under_two_tenants_is_two_customers(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    repo = CustomersRepository()
    try:
        async with tenant_session(factory, tenant_a) as session:
            mine = await repo.upsert(session, tenant_a, phone=PHONE, name="נועה אצל א")

        async with tenant_session(factory, tenant_b) as session:
            # B sees no customer for that phone — and creating one is an
            # INSERT, not an attach to A's record.
            assert await repo.by_phone(session, tenant_b, phone=PHONE) is None
            theirs = await repo.upsert(session, tenant_b, phone=PHONE, name="נועה אצל ב")
            assert theirs.id != mine.id
            assert await repo.by_id(session, tenant_b, mine.id) is None

        async with tenant_session(factory, tenant_a) as session:
            # …and B's upsert did not rewrite A's record.
            own = await repo.by_phone(session, tenant_a, phone=PHONE)
            assert own is not None
            assert own.id == mine.id
            assert own.name == "נועה אצל א"
    finally:
        await engine.dispose()


async def test_bookings_invisible_and_seats_uncontended_across_tenants(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    window_end = T0 + datetime.timedelta(hours=1)
    try:
        async with tenant_session(factory, tenant_a) as session:
            customer_a = await customers.upsert(session, tenant_a, phone=PHONE, name="A")
            booking_a = await bookings.insert(
                session,
                tenant_id=tenant_a,
                customer_id=customer_a.id,
                appointment_type_id=uuid.uuid4(),
                starts_at=T0,
                seat_index=1,
                terms_version_accepted=1,
                terms_accepted_at=ACCEPTED_AT,
                appointment_type_name="מדידה",
            )

        async with tenant_session(factory, tenant_b) as session:
            # B reads nothing of A's.
            assert await bookings.by_id(session, tenant_b, booking_a.id) is None
            assert await bookings.active_seats_at(session, tenant_b, starts_at=T0) == set()
            assert (
                await bookings.count_by_start(
                    session, tenant_b, from_instant=T0, until_instant=window_end
                )
                == {}
            )

            # And B claiming the SAME instant and seat number succeeds: the
            # unique index is (tenant_id, starts_at, seat_index) — one
            # boutique's fully-booked Sunday does not consume another's.
            customer_b = await customers.upsert(session, tenant_b, phone=PHONE, name="B")
            await bookings.insert(
                session,
                tenant_id=tenant_b,
                customer_id=customer_b.id,
                appointment_type_id=uuid.uuid4(),
                starts_at=T0,
                seat_index=1,
                terms_version_accepted=1,
                terms_accepted_at=ACCEPTED_AT,
                appointment_type_name="מדידה",
            )

        async with tenant_session(factory, tenant_a) as session:
            # A's occupancy is untouched by B's identical claim.
            assert await bookings.active_seats_at(session, tenant_a, starts_at=T0) == {1}
            assert await bookings.count_by_start(
                session, tenant_a, from_instant=T0, until_instant=window_end
            ) == {T0: 1}
    finally:
        await engine.dispose()


async def test_scheduled_messages_are_invisible_and_unclaimable_across_tenants(
    app_role_url: str,
) -> None:
    """The poller's blast radius, pinned. A worker draining tenant B must not see,
    claim, cancel or read the TOKEN off tenant A's due reminder — the token is a
    live credential for A's booking, and a leak here would hand B's tenant the
    ability to cancel A's appointments."""
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    repo = ScheduledMessagesRepository()
    booking_a = uuid.uuid4()
    kind = ScheduledMessageKind.REMINDER.value
    due = T0 - datetime.timedelta(days=1)
    try:
        async with tenant_session(factory, tenant_a) as session:
            row_a = await repo.insert(
                session,
                tenant_id=tenant_a,
                booking_id=booking_a,
                kind=kind,
                send_after=due,
                manage_token="a-live-token",
            )

        async with tenant_session(factory, tenant_b) as session:
            # Nothing of A's is claimable, readable or cancellable from B.
            assert await repo.claim_due(session, tenant_b, now=T0, limit=50) == []
            assert (
                await repo.pending_for_booking(session, tenant_b, booking_id=booking_a, kind=kind)
                is None
            )
            assert (
                await repo.cancel_pending(session, tenant_b, booking_id=booking_a, kind=kind) == 0
            )
            assert (
                await repo.mark(
                    session, tenant_b, row_a.id, status=ScheduledMessageStatus.SENT.value
                )
                is None
            )
            # And B scheduling the SAME booking id is its own row: the
            # pending-unique index is (tenant_id, booking_id, kind).
            await repo.insert(
                session,
                tenant_id=tenant_b,
                booking_id=booking_a,
                kind=kind,
                send_after=due,
                manage_token="b-own-token",
            )

        async with tenant_session(factory, tenant_a) as session:
            [claimed] = await repo.claim_due(session, tenant_a, now=T0, limit=50)
            assert claimed.id == row_a.id
            assert claimed.manage_token == "a-live-token"
    finally:
        await engine.dispose()
