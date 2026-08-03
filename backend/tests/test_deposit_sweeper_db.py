"""F19's expiry sweeper against real Postgres as the non-owner app role.

Four things live here and nowhere else, because a fake would assert the mock:

1. **Claim 1 actually frees the seat.** Both partial unique indexes exclude
   `status = 'cancelled'`, so "released" is a DDL fact — proved by inserting a
   second booking onto the same (starts_at, seat_index) afterwards, not by
   reading a status string back.
2. **The claim is exactly-once under two concurrent sweepers.** The guarded
   `WHERE status='pending'` is evaluated by the database under the row lock;
   there is no locking clause and none is wanted (D6).
3. **Claim 2 catches what claim 1 structurally cannot** — the crashed checkout
   that committed a `pending_payment` booking and never got a `payments` row.
   Without it every gateway failure at checkout leaks a seat permanently.
4. **The race width is the injected clock and nothing else.** `deposit_hold_seconds`
   moves it, which is what D6 means by "reversible in a deploy".

NullPool + asyncio.gather gives every racer its own connection (the
test_booking_comms_db precedent), which is what makes the concurrency test real.

**Cleanup is not optional here.** These tests are the only ones in the suite that
write `bookings.status = 'pending_payment'` and `cancelled_by = 'expired'`, and
migration 0015's downgrade narrows both CHECKs — which Postgres refuses while any
row still holds the value. A leaked row from this file reds seven unrelated
migration round-trip tests, so every test deletes its bookings in a `finally`.
`payments` rows are left: 0012 REVOKEs DELETE on that table from app_user, and
`status='expired'` was already legal there before F19, so they threaten nothing.
"""

import asyncio
import datetime
import uuid

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.payments import PaymentsRepository
from app.db.tenant import tenant_session
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.constants import (
    AuditAction,
    BookingCancelledBy,
    BookingStatus,
    PaymentStatus,
)
from app.models.payment import Payment
from app.payments.sweeper import DepositSweeper, SweepResult

pytestmark = pytest.mark.db

NOW = datetime.datetime(2026, 8, 3, 12, 0, tzinfo=datetime.UTC)
SLOT = datetime.datetime(2026, 9, 14, 7, 0, tzinfo=datetime.UTC)
HOLD_SECONDS = 900
POLL_SECONDS = 60
PROVIDER = "fake"


def _factory(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _sweeper(
    factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime.datetime = NOW,
    hold_seconds: int = HOLD_SECONDS,
) -> DepositSweeper:
    return DepositSweeper(
        factory,
        hold_seconds=hold_seconds,
        poll_interval_seconds=POLL_SECONDS,
        clock=lambda: now,
    )


async def _booking(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    status: str = BookingStatus.PENDING_PAYMENT.value,
    # 1-based: 0008 pins `CHECK (seat_index >= 1 AND seat_index <= 1000)`, and
    # create_booking picks the lowest free index from range(1, capacity + 1).
    seat_index: int = 1,
    starts_at: datetime.datetime = SLOT,
    created_at: datetime.datetime | None = None,
) -> uuid.UUID:
    """A booking row and nothing else. The slot engine, the OTP dance and the
    terms snapshot are other suites' business — no FK anywhere on this table by
    house rule, so the sweeper's predicates are reachable without them."""
    async with tenant_session(factory, tenant_id) as session:
        row = await BookingsRepository().insert(
            session,
            tenant_id=tenant_id,
            customer_id=uuid.uuid4(),
            appointment_type_id=uuid.uuid4(),
            starts_at=starts_at,
            seat_index=seat_index,
            status=status,
            terms_version_accepted=1,
            terms_accepted_at=NOW,
            appointment_type_name="מדידה ראשונה",
        )
        booking_id = row.id
        if created_at is not None:
            # `created_at` is a server default, and claim 2's grace window is a
            # predicate on it — so the crash cases have to be able to age a row.
            await session.execute(
                update(Booking)
                .where(Booking.id == booking_id)
                .values(created_at=created_at)
                .execution_options(synchronize_session=False)
            )
    return booking_id


async def _payment(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    booking_id: uuid.UUID,
    *,
    hold_expires_at: datetime.datetime,
    status: str = PaymentStatus.PENDING.value,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await PaymentsRepository().insert(
            session,
            tenant_id=tenant_id,
            booking_id=booking_id,
            provider=PROVIDER,
            amount_agorot=50_000,
            provider_session_id=f"sess-{uuid.uuid4().hex[:12]}",
            redirect_url="https://pay.example.test/checkout/abc",
            hold_expires_at=hold_expires_at,
        )
        payment_id = row.id
        if status != PaymentStatus.PENDING.value:
            await session.execute(
                update(Payment)
                .where(Payment.id == payment_id)
                .values(status=status)
                .execution_options(synchronize_session=False)
            )
    return payment_id


async def _read_booking(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, booking_id: uuid.UUID
) -> Booking:
    async with tenant_session(factory, tenant_id) as session:
        row = await BookingsRepository().by_id(session, tenant_id, booking_id)
    assert row is not None
    return row


async def _read_payment(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, payment_id: uuid.UUID
) -> Payment:
    async with tenant_session(factory, tenant_id) as session:
        row = await PaymentsRepository().by_id(session, tenant_id, payment_id)
    assert row is not None
    return row


async def _audit(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> list[AuditLog]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(AuditLog).where(AuditLog.tenant_id == tenant_id).order_by(AuditLog.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def _cleanup(
    engine: AsyncEngine, factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> None:
    """See the module docstring: `pending_payment` and `cancelled_by='expired'`
    rows left behind break migration 0015's downgrade for the whole suite."""
    try:
        async with tenant_session(factory, tenant_id) as session:
            await session.execute(delete(Booking).where(Booking.tenant_id == tenant_id))
    finally:
        await engine.dispose()


# --- claim 1: the ordinary expiry ---


async def test_an_expired_hold_expires_the_payment_and_frees_the_seat(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        booking_id = await _booking(factory, tenant_id)
        payment_id = await _payment(
            factory, tenant_id, booking_id, hold_expires_at=NOW - datetime.timedelta(seconds=1)
        )

        assert await _sweeper(factory).sweep(tenant_id) == SweepResult(expired=1, released=1)

        payment = await _read_payment(factory, tenant_id, payment_id)
        assert payment.status == PaymentStatus.EXPIRED.value
        # D8: a live checkout URL outliving its hold takes real money for a seat
        # the boutique has already given away.
        assert payment.redirect_url is None

        booking = await _read_booking(factory, tenant_id, booking_id)
        assert booking.status == BookingStatus.CANCELLED.value
        assert booking.cancelled_by == BookingCancelledBy.EXPIRED.value
        assert booking.cancelled_at == NOW

        # The seat is genuinely free, not merely relabelled: 0008's partial
        # unique index excludes `cancelled`, so the same (starts_at, seat_index)
        # takes a new booking. This is the assertion a fake cannot make.
        await _booking(factory, tenant_id, status=BookingStatus.CONFIRMED.value)
    finally:
        await _cleanup(engine, factory, tenant_id)


async def test_the_expiry_leaves_an_audit_row_naming_both_rows(app_role_url: str) -> None:
    """`audit_log` is the only trace an abandoned checkout leaves, and no router
    reads it — so if it is not written at the moment of the sweep it is gone."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        booking_id = await _booking(factory, tenant_id)
        payment_id = await _payment(
            factory, tenant_id, booking_id, hold_expires_at=NOW - datetime.timedelta(seconds=1)
        )

        await _sweeper(factory).sweep(tenant_id)

        [row] = await _audit(factory, tenant_id)
        assert row.action == AuditAction.DEPOSIT_HOLD_EXPIRED.value
        assert row.entity == "payments"
        assert row.details == {
            "payment_id": str(payment_id),
            "booking_id": str(booking_id),
            "seat_released": True,
        }
    finally:
        await _cleanup(engine, factory, tenant_id)


async def test_a_hold_whose_clock_has_not_run_out_is_left_alone(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        booking_id = await _booking(factory, tenant_id)
        payment_id = await _payment(
            factory, tenant_id, booking_id, hold_expires_at=NOW + datetime.timedelta(seconds=1)
        )

        assert await _sweeper(factory).sweep(tenant_id) == SweepResult()

        assert (await _read_payment(factory, tenant_id, payment_id)).status == (
            PaymentStatus.PENDING.value
        )
        assert (await _read_booking(factory, tenant_id, booking_id)).status == (
            BookingStatus.PENDING_PAYMENT.value
        )
        assert await _audit(factory, tenant_id) == []
    finally:
        await _cleanup(engine, factory, tenant_id)


async def test_the_hold_length_is_what_moves_the_race_width(app_role_url: str) -> None:
    """D6's claim that the hold is one env var and not a money decision — and
    the distinction that claim makes, which the first draft of this test got
    backwards.

    `deposit_hold_seconds` is applied by `open_deposit`, which STORES
    `now + hold_seconds` into `payments.hold_expires_at`. Claim 1 then reads that
    stored column and nothing else. So handing the SWEEPER a shorter
    `hold_seconds` does not retroactively expire a hold already written under a
    longer one, and the original assertion here — same row, shorter sweeper hold,
    now swept — asserted a behaviour that would be a bug if it were true: a
    deploy that lowered the env var would mass-expire every hold in flight.

    What the env var really moves is CLAIM 2's grace window, and both halves are
    pinned below.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        # Claim 1 is driven by the STORED expiry, not by the sweeper's config.
        booking_id = await _booking(factory, tenant_id)
        opened_at = NOW - datetime.timedelta(seconds=120)
        await _payment(
            factory,
            tenant_id,
            booking_id,
            hold_expires_at=opened_at + datetime.timedelta(seconds=HOLD_SECONDS),
        )
        assert await _sweeper(factory).sweep(tenant_id) == SweepResult()

        short = DepositSweeper(
            factory,
            hold_seconds=60,
            poll_interval_seconds=POLL_SECONDS,
            clock=lambda: opened_at + datetime.timedelta(seconds=61),
        )
        assert await short.sweep(tenant_id) == SweepResult(), (
            "a shorter sweeper hold must NOT retroactively expire a hold already "
            "written under a longer one — that would mass-expire every hold in "
            "flight on the deploy that lowered the setting"
        )

        # The same row, once its OWN stored expiry has passed, is claim 1's.
        late = DepositSweeper(
            factory,
            hold_seconds=HOLD_SECONDS,
            poll_interval_seconds=POLL_SECONDS,
            clock=lambda: opened_at + datetime.timedelta(seconds=HOLD_SECONDS + 1),
        )
        assert await late.sweep(tenant_id) == SweepResult(expired=1, released=1)
    finally:
        await _cleanup(engine, factory, tenant_id)


async def test_the_hold_length_moves_claim_twos_grace_window(app_role_url: str) -> None:
    """The other half of D6's env-var claim, and the one that IS the sweeper's
    own configuration: an orphaned booking — committed `pending_payment` with no
    payments row at all — becomes claim 2's business exactly `hold + poll` after
    it was created, so lowering the hold shortens how long a leaked seat stays
    leaked."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        created = NOW - datetime.timedelta(seconds=200)
        await _booking(factory, tenant_id, created_at=created)

        # 900 + poll: nowhere near due.
        assert await _sweeper(factory).sweep(tenant_id) == SweepResult()

        short = DepositSweeper(
            factory,
            hold_seconds=60,
            poll_interval_seconds=POLL_SECONDS,
            clock=lambda: NOW,
        )
        assert await short.sweep(tenant_id) == SweepResult(orphaned=1)
    finally:
        await _cleanup(engine, factory, tenant_id)


async def test_a_paid_hold_is_never_swept(app_role_url: str) -> None:
    """The ordering property. A webhook that settled a microsecond before the
    sweep leaves a `paid` row, which the guarded WHERE cannot match — so the
    booking behind real money is never cancelled out from under it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        booking_id = await _booking(factory, tenant_id)
        payment_id = await _payment(
            factory,
            tenant_id,
            booking_id,
            hold_expires_at=NOW - datetime.timedelta(seconds=1),
            status=PaymentStatus.PAID.value,
        )

        assert await _sweeper(factory).sweep(tenant_id) == SweepResult()

        assert (await _read_payment(factory, tenant_id, payment_id)).status == (
            PaymentStatus.PAID.value
        )
        assert (await _read_booking(factory, tenant_id, booking_id)).status == (
            BookingStatus.PENDING_PAYMENT.value
        )
    finally:
        await _cleanup(engine, factory, tenant_id)


async def test_two_concurrent_sweeps_expire_a_hold_exactly_once(app_role_url: str) -> None:
    """The exactly-once claim, and the reason D6 wants no locking clause: the
    second sweeper BLOCKS on the row lock and then matches nothing, rather than
    skipping the row and deferring it a whole poll interval."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        booking_id = await _booking(factory, tenant_id)
        await _payment(
            factory, tenant_id, booking_id, hold_expires_at=NOW - datetime.timedelta(seconds=1)
        )

        first, second = await asyncio.gather(
            _sweeper(factory).sweep(tenant_id), _sweeper(factory).sweep(tenant_id)
        )

        assert sorted([first.expired, second.expired]) == [0, 1]
        assert sorted([first.released, second.released]) == [0, 1]
        # And exactly one audit row, so the owner's only trace is not doubled.
        assert len(await _audit(factory, tenant_id)) == 1
    finally:
        await _cleanup(engine, factory, tenant_id)


# --- claim 2: the orphan and crash backstop ---


async def test_a_checkout_that_died_before_its_payments_row_is_cancelled(
    app_role_url: str,
) -> None:
    """The seat leak claim 1 structurally cannot see. `open_deposit` opens its
    own session, so everything between `create_booking`'s COMMIT and the payment
    INSERT leaves a `pending_payment` booking with no `payments` row at all — and
    the sweeper is the only writer that can move it, because every owner and
    customer verb 409s on an unpaid hold."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        booking_id = await _booking(
            factory,
            tenant_id,
            created_at=NOW - datetime.timedelta(seconds=HOLD_SECONDS + POLL_SECONDS + 1),
        )

        assert await _sweeper(factory).sweep(tenant_id) == SweepResult(orphaned=1)

        booking = await _read_booking(factory, tenant_id, booking_id)
        assert booking.status == BookingStatus.CANCELLED.value
        assert booking.cancelled_by == BookingCancelledBy.EXPIRED.value
        assert booking.cancelled_at == NOW

        [row] = await _audit(factory, tenant_id)
        assert row.action == AuditAction.DEPOSIT_HOLD_EXPIRED.value
        assert row.entity == "bookings"
        assert row.details == {"booking_id": str(booking_id), "orphan": True}
    finally:
        await _cleanup(engine, factory, tenant_id)


async def test_claim_two_leaves_a_booking_inside_the_grace_alone(app_role_url: str) -> None:
    """The `+ poll_interval` grace is what guarantees claim 2 never races the
    ordinary path — a hold opened one tick ago is still claim 1's business, and
    its `payments` row may not have committed yet."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        booking_id = await _booking(
            factory,
            tenant_id,
            created_at=NOW - datetime.timedelta(seconds=HOLD_SECONDS + POLL_SECONDS - 1),
        )

        assert await _sweeper(factory).sweep(tenant_id) == SweepResult()

        assert (await _read_booking(factory, tenant_id, booking_id)).status == (
            BookingStatus.PENDING_PAYMENT.value
        )
    finally:
        await _cleanup(engine, factory, tenant_id)


async def test_claim_two_never_touches_a_booking_that_still_holds_a_live_payment(
    app_role_url: str,
) -> None:
    """An old booking whose hold is still running: claim 1 refuses it because the
    clock has not run out, and claim 2 must refuse it because a `pending` row
    EXISTS. Without the NOT EXISTS, a long hold would be cancelled under a live
    hosted page the bride is still paying on."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        booking_id = await _booking(
            factory,
            tenant_id,
            created_at=NOW - datetime.timedelta(days=1),
        )
        await _payment(
            factory, tenant_id, booking_id, hold_expires_at=NOW + datetime.timedelta(seconds=30)
        )

        assert await _sweeper(factory).sweep(tenant_id) == SweepResult()

        assert (await _read_booking(factory, tenant_id, booking_id)).status == (
            BookingStatus.PENDING_PAYMENT.value
        )
    finally:
        await _cleanup(engine, factory, tenant_id)


async def test_claim_two_ignores_a_booking_that_is_not_awaiting_payment(app_role_url: str) -> None:
    """An ordinary confirmed booking older than the grace, with no payment row at
    all — which is every pre-F19 booking in the table. The status guard is the
    only thing standing between the sweeper and the whole book."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        booking_id = await _booking(
            factory,
            tenant_id,
            status=BookingStatus.CONFIRMED.value,
            created_at=NOW - datetime.timedelta(days=30),
        )

        assert await _sweeper(factory).sweep(tenant_id) == SweepResult()

        assert (await _read_booking(factory, tenant_id, booking_id)).status == (
            BookingStatus.CONFIRMED.value
        )
    finally:
        await _cleanup(engine, factory, tenant_id)


async def test_both_claims_run_in_one_tick_for_the_same_tenant(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        held = await _booking(factory, tenant_id, seat_index=1)
        await _payment(
            factory, tenant_id, held, hold_expires_at=NOW - datetime.timedelta(seconds=1)
        )
        orphan = await _booking(
            factory,
            tenant_id,
            seat_index=2,
            created_at=NOW - datetime.timedelta(seconds=HOLD_SECONDS + POLL_SECONDS + 1),
        )

        assert await _sweeper(factory).sweep(tenant_id) == SweepResult(
            expired=1, released=1, orphaned=1
        )

        for booking_id in (held, orphan):
            assert (await _read_booking(factory, tenant_id, booking_id)).status == (
                BookingStatus.CANCELLED.value
            )
    finally:
        await _cleanup(engine, factory, tenant_id)


async def test_a_tenant_with_nothing_to_sweep_writes_nothing(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        assert await _sweeper(factory).sweep(tenant_id) == SweepResult()
        assert await _audit(factory, tenant_id) == []
    finally:
        await _cleanup(engine, factory, tenant_id)
