"""F28's date-bound reservations on real Postgres: the overlap predicate, soft
delete, and RLS isolation.

⚠ THE OVERLAP EDGES ARE THE WHOLE FEATURE AND THEY COME FIRST. The predicate is
`a1 <= b2 AND b1 <= a2` over INCLUSIVE dates, which makes two neighbouring cases
look identical and behave oppositely: a window ending on the 18th does NOT
conflict with one starting on the 19th (the cleaning buffer is already inside
`ends_on`), and a window ending on the 18th DOES conflict with one starting the
same day. Every off-by-one in this feature lands on exactly one of those two, so
they are the first two tests in the file and the reason the rest exist.

Every test takes its own engine and its own random tenant id, so counts are exact
rather than "at least one".
"""

import asyncio
import datetime
import time
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.catalog.service import (
    CatalogNotFoundError,
    CatalogService,
    ReservationOverlapError,
    ReservationView,
)
from app.catalog.validation import CatalogValidationError
from app.db.repositories.dress_reservations import DressReservationsRepository
from app.db.tenant import tenant_session
from app.models.audit_log import AuditLog
from app.models.constants import AuditAction
from app.models.customer import Customer
from app.storage.memory import InMemoryMediaStorage

pytestmark = pytest.mark.db

ACTOR_ID = uuid.uuid4()
REPO = DressReservationsRepository()

# One arbitrary August window. 12-18 is the spec's own example, so the numbers in
# the assertions below read as the copy the storefront ships.
AUG_12 = datetime.date(2026, 8, 12)
AUG_18 = datetime.date(2026, 8, 18)
AUG_19 = datetime.date(2026, 8, 19)


def _engine(app_role_url: str) -> AsyncEngine:
    return create_async_engine(app_role_url, poolclass=NullPool)


async def _insert(
    engine: AsyncEngine,
    tenant_id: uuid.UUID,
    dress_id: uuid.UUID,
    starts_on: datetime.date,
    ends_on: datetime.date,
    *,
    customer_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> uuid.UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with tenant_session(factory, tenant_id) as session:
        row = await REPO.insert(
            session,
            tenant_id=tenant_id,
            dress_id=dress_id,
            starts_on=starts_on,
            ends_on=ends_on,
            customer_id=customer_id,
            notes=notes,
        )
        return row.id


async def _overlapping(
    engine: AsyncEngine,
    tenant_id: uuid.UUID,
    dress_id: uuid.UUID,
    starts_on: datetime.date,
    ends_on: datetime.date,
) -> list[uuid.UUID]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with tenant_session(factory, tenant_id) as session:
        rows = await REPO.overlapping(
            session,
            tenant_id,
            dress_id,
            starts_on=starts_on,
            ends_on=ends_on,
        )
        return [row.id for row in rows]


# --- the two edges everything else rests on ---


@pytest.mark.asyncio
async def test_adjacent_windows_do_not_overlap(app_role_url: str) -> None:
    """Ends 18, next starts 19: LEGAL. The cleaning and return buffer is already
    inside `ends_on`, so demanding a further gap would block the boutique from
    renting the gown on a day it is provably back."""
    engine = _engine(app_role_url)
    tenant_id, dress_id = uuid.uuid4(), uuid.uuid4()
    try:
        await _insert(engine, tenant_id, dress_id, AUG_12, AUG_18)
        assert (
            await _overlapping(
                engine, tenant_id, dress_id, AUG_19, AUG_19 + datetime.timedelta(days=6)
            )
            == []
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_same_day_touch_overlaps(app_role_url: str) -> None:
    """Ends 18, next starts 18: CONFLICT. `ends_on` is inclusive — the 18th is an
    unavailable day, not a boundary."""
    engine = _engine(app_role_url)
    tenant_id, dress_id = uuid.uuid4(), uuid.uuid4()
    try:
        first = await _insert(engine, tenant_id, dress_id, AUG_12, AUG_18)
        assert await _overlapping(engine, tenant_id, dress_id, AUG_18, AUG_19) == [first]
    finally:
        await engine.dispose()


# --- the rest of the predicate ---


@pytest.mark.asyncio
async def test_contained_spanning_identical_and_disjoint(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    tenant_id, dress_id = uuid.uuid4(), uuid.uuid4()
    try:
        existing = await _insert(engine, tenant_id, dress_id, AUG_12, AUG_18)
        # Contained: 14-16 sits wholly inside 12-18.
        assert await _overlapping(
            engine, tenant_id, dress_id, datetime.date(2026, 8, 14), datetime.date(2026, 8, 16)
        ) == [existing]
        # Spanning: 10-20 swallows it.
        assert await _overlapping(
            engine, tenant_id, dress_id, datetime.date(2026, 8, 10), datetime.date(2026, 8, 20)
        ) == [existing]
        # Identical.
        assert await _overlapping(engine, tenant_id, dress_id, AUG_12, AUG_18) == [existing]
        # Disjoint, both sides.
        assert (
            await _overlapping(
                engine, tenant_id, dress_id, datetime.date(2026, 8, 1), datetime.date(2026, 8, 11)
            )
            == []
        )
        assert (
            await _overlapping(
                engine, tenant_id, dress_id, datetime.date(2026, 9, 1), datetime.date(2026, 9, 5)
            )
            == []
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_another_dress_never_conflicts(app_role_url: str) -> None:
    """The predicate is per DRESS (D1). A gown booked 12-18 says nothing about
    any other gown in the shop."""
    engine = _engine(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        await _insert(engine, tenant_id, uuid.uuid4(), AUG_12, AUG_18)
        assert await _overlapping(engine, tenant_id, uuid.uuid4(), AUG_12, AUG_18) == []
    finally:
        await engine.dispose()


# --- soft delete ---


@pytest.mark.asyncio
async def test_soft_deleted_rows_are_invisible_to_both_readers(app_role_url: str) -> None:
    """A deleted reservation frees the window — that is the ENTIRE delete
    contract, and both readers must honour it or delete+re-add (the spec's
    substitute for an edit endpoint) is broken."""
    engine = _engine(app_role_url)
    tenant_id, dress_id = uuid.uuid4(), uuid.uuid4()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        reservation_id = await _insert(engine, tenant_id, dress_id, AUG_12, AUG_18)
        async with tenant_session(factory, tenant_id) as session:
            assert await REPO.soft_delete(session, tenant_id, reservation_id) is True
        assert await _overlapping(engine, tenant_id, dress_id, AUG_12, AUG_18) == []
        async with tenant_session(factory, tenant_id) as session:
            assert await REPO.live_by_dress(session, tenant_id, dress_id) == []
            assert await REPO.containing(session, tenant_id, dress_id, AUG_12) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_soft_delete_of_an_already_deleted_row_is_false(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    tenant_id, dress_id = uuid.uuid4(), uuid.uuid4()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        reservation_id = await _insert(engine, tenant_id, dress_id, AUG_12, AUG_18)
        async with tenant_session(factory, tenant_id) as session:
            assert await REPO.soft_delete(session, tenant_id, reservation_id) is True
        async with tenant_session(factory, tenant_id) as session:
            assert await REPO.soft_delete(session, tenant_id, reservation_id) is False
            assert await REPO.soft_delete(session, tenant_id, uuid.uuid4()) is False
    finally:
        await engine.dispose()


# --- the readers ---


@pytest.mark.asyncio
async def test_insert_round_trips_every_column(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    tenant_id, dress_id, customer_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await _insert(
            engine,
            tenant_id,
            dress_id,
            AUG_12,
            AUG_18,
            customer_id=customer_id,
            notes="חתונה בקיסריה",
        )
        async with tenant_session(factory, tenant_id) as session:
            rows = await REPO.live_by_dress(session, tenant_id, dress_id)
        assert len(rows) == 1
        assert rows[0].dress_id == dress_id
        assert rows[0].starts_on == AUG_12
        assert rows[0].ends_on == AUG_18
        assert rows[0].customer_id == customer_id
        assert rows[0].notes == "חתונה בקיסריה"
        assert rows[0].deleted_at is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_by_dress_is_newest_start_first(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    tenant_id, dress_id = uuid.uuid4(), uuid.uuid4()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await _insert(engine, tenant_id, dress_id, AUG_12, AUG_18)
        await _insert(
            engine, tenant_id, dress_id, datetime.date(2026, 10, 1), datetime.date(2026, 10, 5)
        )
        await _insert(
            engine, tenant_id, dress_id, datetime.date(2026, 6, 1), datetime.date(2026, 6, 5)
        )
        async with tenant_session(factory, tenant_id) as session:
            rows = await REPO.live_by_dress(session, tenant_id, dress_id)
        assert [row.starts_on for row in rows] == [
            datetime.date(2026, 10, 1),
            AUG_12,
            datetime.date(2026, 6, 1),
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_containing_is_inclusive_at_both_ends(app_role_url: str) -> None:
    """The claim check reads through this. Both ends inclusive, and the day
    either side of the window is free."""
    engine = _engine(app_role_url)
    tenant_id, dress_id = uuid.uuid4(), uuid.uuid4()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await _insert(engine, tenant_id, dress_id, AUG_12, AUG_18)
        async with tenant_session(factory, tenant_id) as session:
            assert await REPO.containing(session, tenant_id, dress_id, AUG_12) is not None
            assert await REPO.containing(session, tenant_id, dress_id, AUG_18) is not None
            assert (
                await REPO.containing(session, tenant_id, dress_id, datetime.date(2026, 8, 15))
                is not None
            )
            assert (
                await REPO.containing(session, tenant_id, dress_id, datetime.date(2026, 8, 11))
                is None
            )
            assert await REPO.containing(session, tenant_id, dress_id, AUG_19) is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_current_or_future_by_dress_excludes_the_past_and_ascends(
    app_role_url: str,
) -> None:
    """The storefront projection (D6): a window that ENDS today is still shown —
    the gown is away for the rest of it — and one that ended yesterday is gone."""
    engine = _engine(app_role_url)
    tenant_id, dress_id = uuid.uuid4(), uuid.uuid4()
    today = datetime.date(2026, 8, 8)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await _insert(
            engine, tenant_id, dress_id, datetime.date(2026, 7, 1), datetime.date(2026, 8, 7)
        )
        ends_today = await _insert(engine, tenant_id, dress_id, datetime.date(2026, 8, 1), today)
        future = await _insert(engine, tenant_id, dress_id, AUG_12, AUG_18)
        async with tenant_session(factory, tenant_id) as session:
            rows = await REPO.current_or_future_by_dress(session, tenant_id, dress_id, today)
        assert [row.id for row in rows] == [ends_today, future]
    finally:
        await engine.dispose()


# --- isolation ---


@pytest.mark.asyncio
async def test_rls_hides_another_tenants_reservations(app_role_url: str) -> None:
    """Same dress id, two tenants: neither reader may see across. The `tenant_id`
    predicate in the repository is defense-in-depth, so this must fail if the
    migration's `enable_tenant_rls` ever regresses — hence the shared dress id."""
    engine = _engine(app_role_url)
    tenant_a, tenant_b, dress_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        mine = await _insert(engine, tenant_a, dress_id, AUG_12, AUG_18)
        theirs = await _insert(engine, tenant_b, dress_id, AUG_12, AUG_18)
        async with tenant_session(factory, tenant_a) as session:
            assert [row.id for row in await REPO.live_by_dress(session, tenant_a, dress_id)] == [
                mine
            ]
            assert await REPO.containing(session, tenant_a, dress_id, AUG_12) is not None
            # B's row is invisible even when A asks for it by its own id.
            assert await REPO.soft_delete(session, tenant_a, theirs) is False
        assert await _overlapping(engine, tenant_b, dress_id, AUG_12, AUG_18) == [theirs]
    finally:
        await engine.dispose()


# --- the service: the lock, the audit rows, the 409 ---


def _service(engine: AsyncEngine) -> CatalogService:
    return CatalogService(
        async_sessionmaker(engine, expire_on_commit=False),
        media_storage=InMemoryMediaStorage(),
        presign_rate_limiter=FixedWindowRateLimiter(
            max_attempts=10_000, window_seconds=3600, clock=time.monotonic
        ),
        pending_ttl_seconds=3600,
    )


async def _dress(service: CatalogService, tenant_id: uuid.UUID) -> uuid.UUID:
    created = await service.create_dress(
        tenant_id,
        name="Aurora",
        description=None,
        price_agorot=None,
        price_visible=True,
        reserved=False,
        sort_order=0,
        actor_id=ACTOR_ID,
    )
    return created.row.id


async def _customer(
    engine: AsyncEngine, tenant_id: uuid.UUID, *, erased: bool = False
) -> uuid.UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with tenant_session(factory, tenant_id) as session:
        row = Customer(
            tenant_id=tenant_id,
            phone=f"+9725{uuid.uuid4().int % 10**8:08d}",
            name="נועה",
            erased_at=datetime.datetime.now(datetime.UTC) if erased else None,
        )
        session.add(row)
        await session.flush()
        return row.id


async def _audit_rows(engine: AsyncEngine, tenant_id: uuid.UUID) -> list[AuditLog]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with tenant_session(factory, tenant_id) as session:
        result = await session.execute(select(AuditLog).order_by(AuditLog.created_at))
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_create_list_delete_lifecycle(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    service = _service(engine)
    tenant_id = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant_id)
        customer_id = await _customer(engine, tenant_id)
        created = await service.create_reservation(
            tenant_id,
            dress_id,
            starts_on=AUG_12,
            ends_on=AUG_18,
            customer_id=customer_id,
            notes="חתונה בקיסריה",
            actor_id=ACTOR_ID,
        )
        assert created.row.starts_on == AUG_12
        assert created.customer_name == "נועה"

        listed = await service.list_reservations(tenant_id, dress_id)
        assert [view.row.id for view in listed] == [created.row.id]
        assert listed[0].customer_name == "נועה"

        await service.delete_reservation(tenant_id, dress_id, created.row.id, actor_id=ACTOR_ID)
        assert await service.list_reservations(tenant_id, dress_id) == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_frees_the_window_for_an_identical_re_create(app_role_url: str) -> None:
    """Delete + re-add IS the edit path (the spec ships no PATCH), so a freed
    window that still collides would make a postponed wedding unrecordable."""
    engine = _engine(app_role_url)
    service = _service(engine)
    tenant_id = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant_id)
        first = await service.create_reservation(
            tenant_id, dress_id, starts_on=AUG_12, ends_on=AUG_18, actor_id=ACTOR_ID
        )
        with pytest.raises(ReservationOverlapError):
            await service.create_reservation(
                tenant_id, dress_id, starts_on=AUG_12, ends_on=AUG_18, actor_id=ACTOR_ID
            )
        await service.delete_reservation(tenant_id, dress_id, first.row.id, actor_id=ACTOR_ID)
        again = await service.create_reservation(
            tenant_id, dress_id, starts_on=AUG_12, ends_on=AUG_18, actor_id=ACTOR_ID
        )
        assert again.row.id != first.row.id
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_overlap_409_carries_the_conflicting_range(app_role_url: str) -> None:
    """The manage pane says WHICH dates collide, so the owner can fix the form
    without leaving it. `details` carries the range and nothing else."""
    engine = _engine(app_role_url)
    service = _service(engine)
    tenant_id = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant_id)
        await service.create_reservation(
            tenant_id, dress_id, starts_on=AUG_12, ends_on=AUG_18, actor_id=ACTOR_ID
        )
        with pytest.raises(ReservationOverlapError) as caught:
            await service.create_reservation(
                tenant_id,
                dress_id,
                starts_on=AUG_18,
                ends_on=AUG_19,
                actor_id=ACTOR_ID,
            )
        assert caught.value.details == {"starts_on": "2026-08-12", "ends_on": "2026-08-18"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_adjacent_create_is_accepted_by_the_service(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    service = _service(engine)
    tenant_id = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant_id)
        await service.create_reservation(
            tenant_id, dress_id, starts_on=AUG_12, ends_on=AUG_18, actor_id=ACTOR_ID
        )
        await service.create_reservation(
            tenant_id,
            dress_id,
            starts_on=AUG_19,
            ends_on=datetime.date(2026, 8, 25),
            actor_id=ACTOR_ID,
        )
        assert len(await service.list_reservations(tenant_id, dress_id)) == 2
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_unknown_and_archived_dress_are_404_on_every_verb(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    service = _service(engine)
    tenant_id = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant_id)
        reservation = await service.create_reservation(
            tenant_id, dress_id, starts_on=AUG_12, ends_on=AUG_18, actor_id=ACTOR_ID
        )
        await service.archive_dress(tenant_id, dress_id, actor_id=ACTOR_ID)
        for target in (dress_id, uuid.uuid4()):
            with pytest.raises(CatalogNotFoundError):
                await service.list_reservations(tenant_id, target)
            with pytest.raises(CatalogNotFoundError):
                await service.create_reservation(
                    tenant_id, target, starts_on=AUG_12, ends_on=AUG_18, actor_id=ACTOR_ID
                )
            with pytest.raises(CatalogNotFoundError):
                await service.delete_reservation(
                    tenant_id, target, reservation.row.id, actor_id=ACTOR_ID
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_erased_or_unknown_customer_is_404(app_role_url: str) -> None:
    """The walk-in's D3d rule: after a §14 erase there is no data subject here,
    and pointing a new reservation at her would resurrect a processing
    relationship the erasure record says ended. Indistinguishable from unknown."""
    engine = _engine(app_role_url)
    service = _service(engine)
    tenant_id = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant_id)
        erased = await _customer(engine, tenant_id, erased=True)
        for customer_id in (erased, uuid.uuid4()):
            with pytest.raises(CatalogNotFoundError):
                await service.create_reservation(
                    tenant_id,
                    dress_id,
                    starts_on=AUG_12,
                    ends_on=AUG_18,
                    customer_id=customer_id,
                    actor_id=ACTOR_ID,
                )
        assert await service.list_reservations(tenant_id, dress_id) == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_validation_rejects_before_any_row_is_written(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    service = _service(engine)
    tenant_id = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant_id)
        with pytest.raises(CatalogValidationError):
            await service.create_reservation(
                tenant_id, dress_id, starts_on=AUG_18, ends_on=AUG_12, actor_id=ACTOR_ID
            )
        assert await service.list_reservations(tenant_id, dress_id) == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_audit_rows_carry_the_range_and_no_name_or_phone(app_role_url: str) -> None:
    """The walk-in audit rule, verbatim: `customer_id` resolves both, and a name
    copied into an audit row survives the erase that scrubs the customer."""
    engine = _engine(app_role_url)
    service = _service(engine)
    tenant_id = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant_id)
        customer_id = await _customer(engine, tenant_id)
        created = await service.create_reservation(
            tenant_id,
            dress_id,
            starts_on=AUG_12,
            ends_on=AUG_18,
            customer_id=customer_id,
            notes="נועה 0501234567",
            actor_id=ACTOR_ID,
        )
        await service.delete_reservation(tenant_id, dress_id, created.row.id, actor_id=ACTOR_ID)

        rows = await _audit_rows(engine, tenant_id)
        by_action = {row.action: row for row in rows}
        assert AuditAction.DRESS_RESERVATION_CREATED in by_action
        assert AuditAction.DRESS_RESERVATION_DELETED in by_action
        create_row = by_action[AuditAction.DRESS_RESERVATION_CREATED]
        assert create_row.actor_id == ACTOR_ID
        assert create_row.details["starts_on"] == "2026-08-12"
        assert create_row.details["ends_on"] == "2026-08-18"
        assert create_row.details["customer_id"] == str(customer_id)
        for row in rows:
            serialised = str(row.details)
            assert "נועה" not in serialised
            assert "0501234567" not in serialised
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_two_concurrent_overlapping_creates_leave_exactly_one(app_role_url: str) -> None:
    """The lock's proof. Both requests pass validation and both run the overlap
    SELECT; without `pg_advisory_xact_lock(hashtext(tenant_id))` — the SAME key
    the booking claim takes — both see an empty result under READ COMMITTED and
    the gown goes to two weddings.

    ⚠ NullPool and separate engines: a pooled connection would serialise these
    by accident and the test would pass against an unlocked service.
    """
    engine_a, engine_b = _engine(app_role_url), _engine(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        service_a, service_b = _service(engine_a), _service(engine_b)
        dress_id = await _dress(service_a, tenant_id)
        results = await asyncio.gather(
            service_a.create_reservation(
                tenant_id, dress_id, starts_on=AUG_12, ends_on=AUG_18, actor_id=ACTOR_ID
            ),
            service_b.create_reservation(
                tenant_id,
                dress_id,
                starts_on=datetime.date(2026, 8, 14),
                ends_on=datetime.date(2026, 8, 20),
                actor_id=ACTOR_ID,
            ),
            return_exceptions=True,
        )
        overlaps = [r for r in results if isinstance(r, ReservationOverlapError)]
        created = [r for r in results if isinstance(r, ReservationView)]
        assert len(created) == 1, results
        assert len(overlaps) == 1, results
        assert len(await service_a.list_reservations(tenant_id, dress_id)) == 1
    finally:
        await engine_a.dispose()
        await engine_b.dispose()
