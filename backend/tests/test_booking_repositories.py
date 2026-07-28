"""Round-trips for the two F13 repositories, as the non-owner app role. The
isolation half lives in test_booking_isolation.py; the concurrency proof for
the claim itself is test_booking_service.py's job."""

import asyncio
import datetime
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import BookingStatus

pytestmark = pytest.mark.db

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Fixed instants, far future: the repositories do no "is this bookable" math,
# so the only thing that matters is that the values are distinct and tz-aware.
T0 = datetime.datetime(2099, 8, 2, 7, 0, tzinfo=datetime.UTC)
T1 = datetime.datetime(2099, 8, 2, 7, 30, tzinfo=datetime.UTC)
ACCEPTED_AT = datetime.datetime(2099, 8, 1, 12, 0, tzinfo=datetime.UTC)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _phone() -> str:
    return f"+9725{uuid.uuid4().int % 10**8:08d}"


async def _insert_booking(
    repo: BookingsRepository,
    session: AsyncSession,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    *,
    starts_at: datetime.datetime,
    seat_index: int,
    **overrides: object,
) -> Booking:
    kwargs: dict = {
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "appointment_type_id": uuid.uuid4(),
        "starts_at": starts_at,
        "seat_index": seat_index,
        "terms_version_accepted": 1,
        "terms_accepted_at": ACCEPTED_AT,
        "appointment_type_name": "מדידת שמלה",
    }
    kwargs.update(overrides)
    return await repo.insert(session, **kwargs)


async def test_customer_upsert_attaches_and_updates_name(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = CustomersRepository()
    phone = _phone()
    try:
        async with tenant_session(factory, tenant_id) as session:
            first = await repo.upsert(session, tenant_id, phone=phone, name="נועה לוי")
            assert first.phone == phone
            assert first.name == "נועה לוי"

            found = await repo.by_phone(session, tenant_id, phone=phone)
            assert found is not None
            assert found.id == first.id

        async with tenant_session(factory, tenant_id) as session:
            # A returning customer ATTACHES — and the name she typed this time wins.
            again = await repo.upsert(session, tenant_id, phone=phone, name="נועה לוי-כהן")
            assert again.id == first.id
            assert again.name == "נועה לוי-כהן"

            assert await repo.by_id(session, tenant_id, first.id) is not None
            assert await repo.by_id(session, tenant_id, uuid.uuid4()) is None
    finally:
        await engine.dispose()


async def test_soft_deleted_customer_does_not_block_return(app_role_url: str) -> None:
    """The unique index is partial on deleted_at IS NULL: a scrubbed customer
    record must not lock her phone number out of the boutique forever."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = CustomersRepository()
    phone = _phone()
    try:
        async with tenant_session(factory, tenant_id) as session:
            first = await repo.upsert(session, tenant_id, phone=phone, name="דנה")
            first.deleted_at = datetime.datetime.now(datetime.UTC)
            await session.flush()

        async with tenant_session(factory, tenant_id) as session:
            assert await repo.by_phone(session, tenant_id, phone=phone) is None
            reborn = await repo.upsert(session, tenant_id, phone=phone, name="דנה")
            assert reborn.id != first.id
    finally:
        await engine.dispose()


async def test_booking_insert_round_trip_and_by_id(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="שירה")
            dress_id = uuid.uuid4()
            row = await _insert_booking(
                bookings,
                session,
                tenant_id,
                customer.id,
                starts_at=T0,
                seat_index=1,
                dress_id=dress_id,
                dress_name="Aurora",
                dress_size="38",
                notes="מגיעה עם אמא ושתי אחיות",
            )
            assert row.status == BookingStatus.CONFIRMED.value  # server default
            assert row.attendance_confirmed_at is None
            assert row.terms_version_accepted == 1
            assert row.appointment_type_name == "מדידת שמלה"
            assert (row.dress_id, row.dress_name, row.dress_size) == (dress_id, "Aurora", "38")

            fetched = await bookings.by_id(session, tenant_id, row.id)
            assert fetched is not None
            assert fetched.starts_at == T0
            assert await bookings.by_id(session, tenant_id, uuid.uuid4()) is None
    finally:
        await engine.dispose()


async def test_occupancy_queries_ignore_cancelled_and_respect_window(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="מאיה")
            seat1 = await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=1
            )
            await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T0, seat_index=2
            )
            await _insert_booking(
                bookings, session, tenant_id, customer.id, starts_at=T1, seat_index=1
            )

            assert await bookings.active_seats_at(session, tenant_id, starts_at=T0) == {1, 2}
            assert await bookings.count_by_start(
                session,
                tenant_id,
                from_instant=T0,
                until_instant=T1 + datetime.timedelta(minutes=30),
            ) == {T0: 2, T1: 1}
            # Half-open right edge: a window ending AT T1 excludes T1.
            assert await bookings.count_by_start(
                session, tenant_id, from_instant=T0, until_instant=T1
            ) == {T0: 2}

            # A no-show still occupies its seat; only a cancellation frees it.
            seat1.status = BookingStatus.NO_SHOW.value
            await session.flush()
            assert await bookings.active_seats_at(session, tenant_id, starts_at=T0) == {1, 2}

            seat1.status = BookingStatus.CANCELLED.value
            await session.flush()
            assert await bookings.active_seats_at(session, tenant_id, starts_at=T0) == {2}
            assert await bookings.count_by_start(
                session, tenant_id, from_instant=T0, until_instant=T1
            ) == {T0: 1}
    finally:
        await engine.dispose()


async def test_slot_seat_unique_index_rejects_double_claim_and_frees_on_cancel(
    app_role_url: str,
) -> None:
    """The structural oversell guard, exercised directly at the index: a live
    duplicate (tenant, starts_at, seat) is an IntegrityError, and a CANCELLED
    row leaves the predicate so its seat number is claimable again."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    customers = CustomersRepository()
    bookings = BookingsRepository()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await customers.upsert(session, tenant_id, phone=_phone(), name="רות")
            customer_id = customer.id
            first = await _insert_booking(
                bookings, session, tenant_id, customer_id, starts_at=T0, seat_index=1
            )
            first_id = first.id

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant_id) as session:
                await _insert_booking(
                    bookings, session, tenant_id, customer_id, starts_at=T0, seat_index=1
                )

        async with tenant_session(factory, tenant_id) as session:
            row = await bookings.by_id(session, tenant_id, first_id)
            assert row is not None
            row.status = BookingStatus.CANCELLED.value
            await session.flush()

        async with tenant_session(factory, tenant_id) as session:
            reclaimed = await _insert_booking(
                bookings, session, tenant_id, customer_id, starts_at=T0, seat_index=1
            )
            assert reclaimed.id != first_id
    finally:
        await engine.dispose()


def _f13_table_count(url: str) -> int:
    async def count() -> int:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT count(*) FROM pg_tables "
                        "WHERE tablename IN ('customers', 'bookings')"
                    )
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(count())


def test_migration_0008_round_trips(migrated_db: str) -> None:
    """downgrade drops bookings then customers; upgrade puts both back with
    their indexes, grants and policies. Runs as the migration owner (the app
    role cannot DROP), and destroys rows — so it owns no fixtures and shares no
    state with the tests above."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)

    assert _f13_table_count(migrated_db) == 2
    command.downgrade(cfg, "0007")
    assert _f13_table_count(migrated_db) == 0
    command.upgrade(cfg, "head")
    assert _f13_table_count(migrated_db) == 2
