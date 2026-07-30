"""The F13 claim, against real Postgres as the non-owner app role.

The headline is the concurrency proof: NullPool + asyncio.gather gives every
racer its own connection (the test_boutique_service precedent), so the
per-tenant advisory lock and the seat unique index are exercised for real —
capacity 1 yields exactly one booking, capacity 3 exactly three.
"""

import asyncio
import datetime
import secrets
import uuid

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.tokens import hash_token
from app.booking.service import (
    BOOKABLE_HORIZON,
    BookingNotFoundError,
    BookingService,
    BookingThrottledError,
    PhoneNotVerifiedError,
    SlotUnavailableError,
    TermsStaleError,
)
from app.booking.validation import jerusalem_day_index
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.dress_variants import DressVariantsRepository
from app.db.repositories.dresses import DressesRepository
from app.db.repositories.otp_codes import OtpCodesRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import AppointmentAudience, BookingStatus
from app.notifications.service import NotificationService, OtpService
from app.notifications.unconfigured import UnconfiguredSmsSender
from app.notifications.validation import normalize_israeli_mobile
from app.storefront.validation import BOUTIQUE_TIMEZONE

pytestmark = pytest.mark.db

NOW = datetime.datetime(2026, 7, 28, 12, 0, tzinfo=datetime.UTC)
FUTURE = datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC)
# Outlives even the late-clock test below, whose "now" is pushed past SLOT.
FAR_FUTURE = datetime.datetime(2100, 1, 1, tzinfo=datetime.UTC)
PAST = datetime.datetime(2000, 1, 1, tzinfo=datetime.UTC)

# A fixed boutique day about a month after the frozen NOW: comfortably future
# so the engine never drops it as past, and comfortably INSIDE the publishable
# horizon, which is the window a real customer can ever be offered. (An earlier
# revision used 2099 — the grid materializes any date it is handed, so those
# bookings only ever succeeded because nothing checked that the requested day
# was one the boutique actually publishes.) The weekly rule is derived from
# THIS date's weekday, so the grid always opens it. Wall times go through
# BOUTIQUE_TIMEZONE, the same zone the engine uses — never a hardcoded offset.
TARGET_DATE = datetime.date(2026, 8, 23)


def _slot(hour: int, minute: int = 0, *, date: datetime.date = TARGET_DATE) -> datetime.datetime:
    return datetime.datetime.combine(
        date, datetime.time(hour, minute), tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)


SLOT = _slot(10, 0)


def _clock() -> datetime.datetime:
    return NOW


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _phone() -> str:
    return f"+9725{uuid.uuid4().int % 10**8:08d}"


def _loose_limiter() -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(max_attempts=10_000, window_seconds=3600, clock=lambda: 0.0)


def _service(
    factory: async_sessionmaker[AsyncSession],
    *,
    create_limiter: FixedWindowRateLimiter | None = None,
    phone_limiter: FixedWindowRateLimiter | None = None,
    clock: datetime.datetime | None = None,
) -> BookingService:
    fixed = clock if clock is not None else NOW
    otp = OtpService(
        factory,
        notifications=NotificationService(factory, sender=UnconfiguredSmsSender()),
        phone_limiter=_loose_limiter(),
        tenant_limiter=_loose_limiter(),
        verify_limiter=_loose_limiter(),
        clock=lambda: fixed,
    )
    return BookingService(
        factory,
        otp=otp,
        create_limiter=create_limiter if create_limiter is not None else _loose_limiter(),
        phone_limiter=phone_limiter if phone_limiter is not None else _loose_limiter(),
        clock=lambda: fixed,
    )


async def _seed_boutique(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    capacity: int = 1,
    with_terms: bool = True,
) -> uuid.UUID:
    """One weekly rule covering TARGET_DATE (09:00–13:00), one appointment
    type, and terms v1. Returns the appointment type id."""
    async with tenant_session(factory, tenant_id) as session:
        await AvailabilityRulesRepository().insert(
            session,
            tenant_id=tenant_id,
            day_of_week=jerusalem_day_index(TARGET_DATE),
            open_time=datetime.time(9, 0),
            close_time=datetime.time(13, 0),
            capacity=capacity,
        )
        type_row = await AppointmentTypesRepository().insert(
            session,
            tenant_id=tenant_id,
            name="מדידת שמלה",
            duration_minutes=60,
            audience=AppointmentAudience.ALL.value,
            deposit_required=False,
            deposit_amount_agorot=None,
            sort_order=0,
        )
        if with_terms:
            await TermsVersionsRepository().insert(
                session,
                tenant_id=tenant_id,
                version=1,
                terms_text="תנאי ביטול",
                refundable_until_hours_before=48,
                forfeit_percent=50,
                created_by=uuid.uuid4(),
            )
        return type_row.id


async def _mint_verified_token(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    raw_phone: str,
    *,
    verification_expires_at: datetime.datetime = FUTURE,
) -> str:
    """Seed the otp_codes row a completed OTP verify would leave behind."""
    token = secrets.token_urlsafe(16)
    repo = OtpCodesRepository()
    async with tenant_session(factory, tenant_id) as session:
        row = await repo.insert(
            session,
            tenant_id=tenant_id,
            phone=normalize_israeli_mobile(raw_phone),
            code_hash="seed",
            expires_at=FUTURE,
        )
        await repo.mark_consumed(
            session,
            tenant_id,
            row.id,
            verification_token_hash=hash_token(token),
            verification_expires_at=verification_expires_at,
        )
    return token


async def test_generic_booking_happy_path(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed_boutique(factory, tenant_id)
        token = await _mint_verified_token(factory, tenant_id, phone)
        booking = (
            await _service(factory).create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=token,
                name="  נועה לוי ",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )
        ).booking
        assert booking.starts_at == SLOT
        assert booking.seat_index == 1
        assert booking.status == BookingStatus.CONFIRMED.value
        assert booking.terms_version_accepted == 1
        assert booking.terms_accepted_at == NOW
        assert booking.appointment_type_name == "מדידת שמלה"
        assert (booking.dress_id, booking.dress_name, booking.dress_size) == (None, None, None)

        async with tenant_session(factory, tenant_id) as session:
            customer = await CustomersRepository().by_phone(session, tenant_id, phone=phone)
            assert customer is not None
            assert customer.id == booking.customer_id
            assert customer.name == "נועה לוי"  # stripped
    finally:
        await engine.dispose()


async def test_item_booking_snapshots_survive_renames(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed_boutique(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            dress = await DressesRepository().insert(
                session,
                tenant_id=tenant_id,
                name="Aurora",
                description=None,
                price_agorot=None,
                price_visible=True,
                reserved=False,
                sort_order=0,
            )
            dress_id = dress.id
            await DressVariantsRepository().insert(
                session,
                tenant_id=tenant_id,
                dress_id=dress_id,
                size_label="38",
                quantity=1,
                sort_order=0,
            )
        token = await _mint_verified_token(factory, tenant_id, phone)
        booking = (
            await _service(factory).create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=token,
                name="שירה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
                dress_id=dress_id,
                dress_size="  38 ",  # normalized before matching and snapshotting
                notes="מגיעה עם אמא",
            )
        ).booking
        assert (booking.dress_id, booking.dress_name, booking.dress_size) == (
            dress_id,
            "Aurora",
            "38",
        )

        # Rename the dress and the type AFTER the booking: history must not move.
        async with tenant_session(factory, tenant_id) as session:
            dress_row = await DressesRepository().by_id(session, tenant_id, dress_id)
            assert dress_row is not None
            dress_row.name = "Borealis"
            type_row = await AppointmentTypesRepository().by_id(session, tenant_id, type_id)
            assert type_row is not None
            type_row.name = "פגישה"
            await session.flush()
        async with tenant_session(factory, tenant_id) as session:
            frozen = await BookingsRepository().by_id(session, tenant_id, booking.id)
            assert frozen is not None
            assert frozen.dress_name == "Aurora"
            assert frozen.appointment_type_name == "מדידת שמלה"
    finally:
        await engine.dispose()


async def test_two_racers_capacity_one_yield_exactly_one_booking(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed_boutique(factory, tenant_id, capacity=1)
        service = _service(factory)

        async def race() -> Booking:
            phone = _phone()
            token = await _mint_verified_token(factory, tenant_id, phone)
            return (
                await service.create_booking(
                    tenant_id,
                    raw_phone=phone,
                    verification_token=token,
                    name="רייסר",
                    appointment_type_id=type_id,
                    starts_at=SLOT,
                    terms_version=1,
                )
            ).booking

        results = await asyncio.gather(race(), race(), return_exceptions=True)
        winners = [r for r in results if not isinstance(r, BaseException)]
        losers = [r for r in results if isinstance(r, SlotUnavailableError)]
        assert len(winners) == 1, f"expected one winner, got {results!r}"
        assert len(losers) == 1, f"expected one SlotUnavailableError, got {results!r}"
    finally:
        await engine.dispose()


async def test_five_racers_capacity_three_yield_three_distinct_seats(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed_boutique(factory, tenant_id, capacity=3)
        service = _service(factory)

        async def race() -> Booking:
            phone = _phone()
            token = await _mint_verified_token(factory, tenant_id, phone)
            return (
                await service.create_booking(
                    tenant_id,
                    raw_phone=phone,
                    verification_token=token,
                    name="רייסרית",
                    appointment_type_id=type_id,
                    starts_at=SLOT,
                    terms_version=1,
                )
            ).booking

        results = await asyncio.gather(*(race() for _ in range(5)), return_exceptions=True)
        winners = [r for r in results if not isinstance(r, BaseException)]
        losers = [r for r in results if isinstance(r, SlotUnavailableError)]
        assert len(winners) == 3, f"expected three winners, got {results!r}"
        assert len(losers) == 2
        assert sorted(w.seat_index for w in winners) == [1, 2, 3]

        async with tenant_session(factory, tenant_id) as session:
            assert await BookingsRepository().active_seats_at(
                session, tenant_id, starts_at=SLOT
            ) == {1, 2, 3}
    finally:
        await engine.dispose()


async def test_cancellation_frees_the_seat_for_a_new_claim(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed_boutique(factory, tenant_id, capacity=1)
        service = _service(factory)
        first_phone = _phone()
        first_token = await _mint_verified_token(factory, tenant_id, first_phone)
        first = (
            await service.create_booking(
                tenant_id,
                raw_phone=first_phone,
                verification_token=first_token,
                name="ראשונה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )
        ).booking

        # Full → a third party is refused.
        blocked_phone = _phone()
        blocked_token = await _mint_verified_token(factory, tenant_id, blocked_phone)
        with pytest.raises(SlotUnavailableError):
            await service.create_booking(
                tenant_id,
                raw_phone=blocked_phone,
                verification_token=blocked_token,
                name="חסומה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )

        async with tenant_session(factory, tenant_id) as session:
            row = await BookingsRepository().by_id(session, tenant_id, first.id)
            assert row is not None
            row.status = BookingStatus.CANCELLED.value
            await session.flush()

        # …and the LOSER's token survived its lost claim (the burn rolled
        # back with the transaction), so the same token claims the freed seat.
        reclaimed = (
            await service.create_booking(
                tenant_id,
                raw_phone=blocked_phone,
                verification_token=blocked_token,
                name="חסומה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )
        ).booking
        assert reclaimed.seat_index == 1
        assert reclaimed.id != first.id
    finally:
        await engine.dispose()


async def test_an_identical_recreate_returns_the_first_booking(app_role_url: str) -> None:
    """The lost-201 retry, which is the common case on a flaky mobile network:
    the claim COMMITTED, the response never arrived, and the spent token makes
    the naive retry a 403 whose copy tells her to request a fresh code and
    resubmit. She does — and the boutique must not end up holding two
    appointments for her. Capacity 2, so a second seat was genuinely free:
    this proves idempotency, not a full slot."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed_boutique(factory, tenant_id, capacity=2)
        service = _service(factory)
        first = (
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=await _mint_verified_token(factory, tenant_id, phone),
                name="נועה לוי",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
                notes="מגיעה עם אמא",
            )
        ).booking
        replay = (
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=await _mint_verified_token(factory, tenant_id, phone),
                name="נועה לוי",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
                notes="שלחתי שוב",
            )
        ).booking
        assert replay.id == first.id
        assert replay.seat_index == first.seat_index
        # The row is returned, never rewritten from the replay's payload: the
        # first submission is the one she agreed to.
        assert replay.notes == "מגיעה עם אמא"

        async with tenant_session(factory, tenant_id) as session:
            assert await BookingsRepository().active_seats_at(
                session, tenant_id, starts_at=SLOT
            ) == {1}
    finally:
        await engine.dispose()


async def test_two_simultaneous_identical_creates_yield_exactly_one_booking(
    app_role_url: str,
) -> None:
    """The same retry, raced — a double-submit rather than a sequential one.
    The per-tenant advisory lock serializes both claims, so the loser's
    idempotency read runs against the winner's COMMITTED row and converges on
    it. Both callers succeed, both hold the same appointment. Capacity 2, so
    without the check this would be two seats rather than a 409."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed_boutique(factory, tenant_id, capacity=2)
        service = _service(factory)

        async def race(token: str) -> Booking:
            return (
                await service.create_booking(
                    tenant_id,
                    raw_phone=phone,
                    verification_token=token,
                    name="נועה לוי",
                    appointment_type_id=type_id,
                    starts_at=SLOT,
                    terms_version=1,
                )
            ).booking

        first_token = await _mint_verified_token(factory, tenant_id, phone)
        second_token = await _mint_verified_token(factory, tenant_id, phone)
        results = await asyncio.gather(
            race(first_token), race(second_token), return_exceptions=True
        )
        winners = [r for r in results if not isinstance(r, BaseException)]
        assert len(winners) == 2, f"expected both to succeed, got {results!r}"
        assert len({w.id for w in winners}) == 1, f"expected one booking, got {results!r}"

        async with tenant_session(factory, tenant_id) as session:
            assert await BookingsRepository().active_seats_at(
                session, tenant_id, starts_at=SLOT
            ) == {1}
    finally:
        await engine.dispose()


async def test_her_own_cancellation_lets_her_rebook_the_same_instant(app_role_url: str) -> None:
    """0009's predicate is 0008's: a cancelled row is not an active booking, so
    a customer who cancels and changes her mind claims the very same instant
    again — a fresh row, not the cancelled one handed back."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed_boutique(factory, tenant_id, capacity=1)
        service = _service(factory)
        first = (
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=await _mint_verified_token(factory, tenant_id, phone),
                name="נועה לוי",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )
        ).booking
        async with tenant_session(factory, tenant_id) as session:
            row = await BookingsRepository().by_id(session, tenant_id, first.id)
            assert row is not None
            row.status = BookingStatus.CANCELLED.value
            await session.flush()

        again = (
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=await _mint_verified_token(factory, tenant_id, phone),
                name="נועה לוי",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )
        ).booking
        assert again.id != first.id
        assert again.seat_index == 1
        assert again.status == BookingStatus.CONFIRMED.value
    finally:
        await engine.dispose()


async def test_off_grid_instants_are_slot_unavailable(app_role_url: str) -> None:
    """An arbitrary timestamp is not a slot: outside the window, off the
    30-minute grid, on a day without a rule, or in the past — all the same 409,
    and none of them writes anything."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed_boutique(factory, tenant_id)
        service = _service(factory)
        closed_day = _slot(10, 0, date=TARGET_DATE + datetime.timedelta(days=1))
        for wrong in (
            _slot(3, 0),  # before opening
            _slot(13, 0),  # close_time is exclusive
            _slot(10, 17),  # off the 30-minute grid
            closed_day,  # weekday with no rule
        ):
            phone = _phone()
            token = await _mint_verified_token(factory, tenant_id, phone)
            with pytest.raises(SlotUnavailableError):
                await service.create_booking(
                    tenant_id,
                    raw_phone=phone,
                    verification_token=token,
                    name="בדיקה",
                    appointment_type_id=type_id,
                    starts_at=wrong,
                    terms_version=1,
                )

        # A PAST instant: same grid, but the clock has moved beyond it. The
        # token must outlive that clock, or this would 403 before the grid.
        late = _service(factory, clock=SLOT + datetime.timedelta(minutes=1))
        phone = _phone()
        token = await _mint_verified_token(
            factory, tenant_id, phone, verification_expires_at=FAR_FUTURE
        )
        with pytest.raises(SlotUnavailableError):
            await late.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=token,
                name="מאחרת",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )
    finally:
        await engine.dispose()


async def test_unproven_phone_is_rejected_and_writes_nothing(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed_boutique(factory, tenant_id)
        service = _service(factory)

        # No token at all was ever minted for this phone.
        with pytest.raises(PhoneNotVerifiedError):
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token="never-minted",
                name="נועה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )

        # A real token bound to a DIFFERENT phone.
        foreign_token = await _mint_verified_token(factory, tenant_id, _phone())
        with pytest.raises(PhoneNotVerifiedError):
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=foreign_token,
                name="נועה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )

        # An EXPIRED verification.
        expired = await _mint_verified_token(
            factory, tenant_id, phone, verification_expires_at=PAST
        )
        with pytest.raises(PhoneNotVerifiedError):
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=expired,
                name="נועה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )

        # A SPENT token: book once, then replay it for another slot.
        replay_phone = _phone()
        replay_token = await _mint_verified_token(factory, tenant_id, replay_phone)
        await service.create_booking(
            tenant_id,
            raw_phone=replay_phone,
            verification_token=replay_token,
            name="ראשונה",
            appointment_type_id=type_id,
            starts_at=SLOT,
            terms_version=1,
        )
        with pytest.raises(PhoneNotVerifiedError):
            await service.create_booking(
                tenant_id,
                raw_phone=replay_phone,
                verification_token=replay_token,
                name="ראשונה",
                appointment_type_id=type_id,
                starts_at=_slot(10, 30),
                terms_version=1,
            )

        # None of the refused attempts left a customer behind.
        async with tenant_session(factory, tenant_id) as session:
            assert await CustomersRepository().by_phone(session, tenant_id, phone=phone) is None
    finally:
        await engine.dispose()


async def test_stale_or_absent_terms_are_rejected(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    stale_tenant = uuid.uuid4()
    bare_tenant = uuid.uuid4()
    try:
        service = _service(factory)
        type_id = await _seed_boutique(factory, stale_tenant)
        phone = _phone()
        token = await _mint_verified_token(factory, stale_tenant, phone)
        with pytest.raises(TermsStaleError):
            await service.create_booking(
                stale_tenant,
                raw_phone=phone,
                verification_token=token,
                name="נועה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=2,  # current is 1
            )

        # A boutique with NO terms at all cannot take acceptances.
        bare_type = await _seed_boutique(factory, bare_tenant, with_terms=False)
        bare_phone = _phone()
        bare_token = await _mint_verified_token(factory, bare_tenant, bare_phone)
        with pytest.raises(TermsStaleError):
            await service.create_booking(
                bare_tenant,
                raw_phone=bare_phone,
                verification_token=bare_token,
                name="נועה",
                appointment_type_id=bare_type,
                starts_at=SLOT,
                terms_version=1,
            )
    finally:
        await engine.dispose()


async def test_returning_customer_attaches_instead_of_duplicating(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed_boutique(factory, tenant_id, capacity=2)
        service = _service(factory)
        first = (
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=await _mint_verified_token(factory, tenant_id, phone),
                name="נועה לוי",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )
        ).booking
        second = (
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=await _mint_verified_token(factory, tenant_id, phone),
                name="נועה לוי-כהן",
                appointment_type_id=type_id,
                starts_at=_slot(10, 30),
                terms_version=1,
            )
        ).booking
        assert second.customer_id == first.customer_id
        # A DIFFERENT instant is a different appointment, not a replay: the
        # idempotency guard is keyed on the instant, so two visits still book.
        assert second.id != first.id
        assert second.starts_at == _slot(10, 30)
        async with tenant_session(factory, tenant_id) as session:
            customer = await CustomersRepository().by_phone(session, tenant_id, phone=phone)
            assert customer is not None
            assert customer.name == "נועה לוי-כהן"
    finally:
        await engine.dispose()


async def test_unknown_or_archived_type_dress_and_size_are_404(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed_boutique(factory, tenant_id)
        service = _service(factory)

        async def attempt(**overrides: object) -> None:
            phone = _phone()
            kwargs: dict = {
                "raw_phone": phone,
                "verification_token": await _mint_verified_token(factory, tenant_id, phone),
                "name": "נועה",
                "appointment_type_id": type_id,
                "starts_at": SLOT,
                "terms_version": 1,
            }
            kwargs.update(overrides)
            await service.create_booking(tenant_id, **kwargs)

        with pytest.raises(BookingNotFoundError):
            await attempt(appointment_type_id=uuid.uuid4())

        with pytest.raises(BookingNotFoundError):
            await attempt(dress_id=uuid.uuid4(), dress_size="38")

        async with tenant_session(factory, tenant_id) as session:
            dress = await DressesRepository().insert(
                session,
                tenant_id=tenant_id,
                name="Aurora",
                description=None,
                price_agorot=None,
                price_visible=True,
                reserved=False,
                sort_order=0,
            )
            dress_id = dress.id
            await DressVariantsRepository().insert(
                session,
                tenant_id=tenant_id,
                dress_id=dress_id,
                size_label="38",
                quantity=1,
                sort_order=0,
            )

        # A size that is not one of the dress's active variants.
        with pytest.raises(BookingNotFoundError):
            await attempt(dress_id=dress_id, dress_size="52")

        # An archived dress is indistinguishable from a missing one.
        async with tenant_session(factory, tenant_id) as session:
            assert await DressesRepository().soft_delete(session, tenant_id, dress_id)
        with pytest.raises(BookingNotFoundError):
            await attempt(dress_id=dress_id, dress_size="38")

        # An archived appointment type likewise.
        async with tenant_session(factory, tenant_id) as session:
            assert await AppointmentTypesRepository().soft_delete(session, tenant_id, type_id)
        with pytest.raises(BookingNotFoundError):
            await attempt()
    finally:
        await engine.dispose()


async def test_create_throttle_spends_only_on_verified_attempts(app_role_url: str) -> None:
    """The budget is spent by proven callers, never by unproven ones.

    Metering before verification is a free denial of service: anyone who knows
    the boutique's hostname posts garbage tokens until the hourly ceiling is
    spent, and every real bride gets a 429 for the rest of the window. So an
    unverified attempt must cost NOTHING, and a verified one must cost a slot
    even when the claim itself goes on to fail."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed_boutique(factory, tenant_id, capacity=2)
        service = _service(
            factory,
            create_limiter=FixedWindowRateLimiter(
                max_attempts=1, window_seconds=3600, clock=lambda: 0.0
            ),
        )

        # Twenty unauthenticated attempts against a budget of one.
        for _ in range(20):
            with pytest.raises(PhoneNotVerifiedError):
                await service.create_booking(
                    tenant_id,
                    raw_phone=phone,
                    verification_token="garbage",
                    name="תוקפת",
                    appointment_type_id=type_id,
                    starts_at=SLOT,
                    terms_version=1,
                )

        # …and the real customer's booking still goes through.
        booking = (
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=await _mint_verified_token(factory, tenant_id, phone),
                name="נועה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )
        ).booking
        assert booking.seat_index == 1

        # That verified attempt DID spend the budget.
        with pytest.raises(BookingThrottledError):
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=await _mint_verified_token(factory, tenant_id, phone),
                name="נועה",
                appointment_type_id=type_id,
                starts_at=_slot(10, 30),
                terms_version=1,
            )
    finally:
        await engine.dispose()


async def test_a_rolled_back_claim_still_spends_the_budget(app_role_url: str) -> None:
    """The token un-burns on rollback so a race loser can retry — that must not
    also mean one SMS buys unlimited attempts. A FAILED verified attempt spends
    a slot, because the meter lives in memory, not in the transaction."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed_boutique(factory, tenant_id)
        # The PER-PHONE budget, because that is the one this property protects.
        service = _service(
            factory,
            phone_limiter=FixedWindowRateLimiter(
                max_attempts=1, window_seconds=3600, clock=lambda: 0.0
            ),
        )
        token = await _mint_verified_token(factory, tenant_id, phone)
        # Verified, then fails on stale terms → the whole transaction rolls back.
        with pytest.raises(TermsStaleError):
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=token,
                name="נועה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=99,
            )
        # The token survived (that is the retry affordance)…
        # …but the attempt is paid for, so the retry loop is bounded.
        with pytest.raises(BookingThrottledError):
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=token,
                name="נועה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )
    finally:
        await engine.dispose()


async def test_one_phone_cannot_spend_the_whole_tenant_budget(app_role_url: str) -> None:
    """The per-phone budget must bite BEFORE the tenant's, so one verified
    number cannot close the boutique.

    ONE pair of limiters for the whole test, shared by both customers — the
    only arrangement that can actually fail. Handing the second customer a
    fresh limiter would prove nothing: she would book even if the per-phone
    budget did not exist at all, which is exactly how a per-phone key that
    shares the tenant's ceiling (and so can never trip first) passed for real
    isolation once already.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    noisy = _phone()
    quiet = _phone()
    try:
        type_id = await _seed_boutique(factory, tenant_id, capacity=3)
        tenant_limiter = FixedWindowRateLimiter(
            max_attempts=60, window_seconds=3600, clock=lambda: 0.0
        )
        phone_limiter = FixedWindowRateLimiter(
            max_attempts=2, window_seconds=3600, clock=lambda: 0.0
        )
        service = _service(factory, create_limiter=tenant_limiter, phone_limiter=phone_limiter)

        async def book(phone: str, name: str, starts_at: datetime.datetime) -> Booking:
            return (
                await service.create_booking(
                    tenant_id,
                    raw_phone=phone,
                    verification_token=await _mint_verified_token(factory, tenant_id, phone),
                    name=name,
                    appointment_type_id=type_id,
                    starts_at=starts_at,
                    terms_version=1,
                )
            ).booking

        await book(noisy, "רועשת", SLOT)
        await book(noisy, "רועשת", _slot(10, 30))
        # Her own budget is spent while the tenant's 60 is barely touched.
        with pytest.raises(BookingThrottledError):
            await book(noisy, "רועשת", _slot(11, 0))
        assert not tenant_limiter.is_blocked(f"booking:create:{tenant_id}")

        # …and on the SAME limiters another customer is unaffected.
        booking = await book(quiet, "שקטה", _slot(11, 0))
        assert booking.seat_index == 1
    finally:
        await engine.dispose()


async def test_a_freed_middle_seat_is_reclaimed_not_appended(app_role_url: str) -> None:
    """Seats are claimed lowest-free, NOT `count + 1`. At capacity 3 with seats
    {1,2,3} taken, cancelling seat 2 must let the next claim take seat 2 — the
    count-based shorthand would try seat 3, hit the still-live row and answer a
    false SLOT_UNAVAILABLE on a slot that genuinely has room."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed_boutique(factory, tenant_id, capacity=3)
        service = _service(factory)
        booked = []
        for _ in range(3):
            phone = _phone()
            booked.append(
                (
                    await service.create_booking(
                        tenant_id,
                        raw_phone=phone,
                        verification_token=await _mint_verified_token(factory, tenant_id, phone),
                        name="לקוחה",
                        appointment_type_id=type_id,
                        starts_at=SLOT,
                        terms_version=1,
                    )
                ).booking
            )
        assert sorted(row.seat_index for row in booked) == [1, 2, 3]

        middle = next(row for row in booked if row.seat_index == 2)
        async with tenant_session(factory, tenant_id) as session:
            row = await BookingsRepository().by_id(session, tenant_id, middle.id)
            assert row is not None
            row.status = BookingStatus.CANCELLED.value
            await session.flush()

        phone = _phone()
        reclaimed = (
            await service.create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=await _mint_verified_token(factory, tenant_id, phone),
                name="מחליפה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
            )
        ).booking
        assert reclaimed.seat_index == 2
        async with tenant_session(factory, tenant_id) as session:
            assert await BookingsRepository().active_seats_at(
                session, tenant_id, starts_at=SLOT
            ) == {1, 2, 3}
    finally:
        await engine.dispose()


async def test_beyond_the_publishable_window_is_refused(app_role_url: str) -> None:
    """A day the boutique never publishes is not bookable, even though the
    engine would happily materialize it.

    `_offered_slot` re-materializes the requested date on demand, so without
    the horizon guard a caller could post the SAME weekday 91 days out — the
    weekly rule opens it, every other check passes — and claim an appointment
    at a time `/storefront/slots` (clamped to SLOT_WINDOW_MAX_DAYS) would never
    have offered.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed_boutique(factory, tenant_id)
        far = _slot(10, 0, date=TARGET_DATE + datetime.timedelta(days=91))
        with pytest.raises(SlotUnavailableError):
            await _service(factory).create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=await _mint_verified_token(factory, tenant_id, phone),
                name="מוקדם מדי",
                appointment_type_id=type_id,
                starts_at=far,
                terms_version=1,
            )
    finally:
        await engine.dispose()


async def test_absurd_timestamps_are_refused_not_crashed(app_role_url: str) -> None:
    """`AwareDatetime` accepts the whole datetime range, and `.astimezone()` on
    a year-9999 instant raises OverflowError — a 500 on an anonymous route. The
    horizon guard turns both ends into the ordinary 409."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed_boutique(factory, tenant_id)
        service = _service(factory)
        for absurd in (
            datetime.datetime(9999, 12, 31, 23, 0, tzinfo=datetime.UTC),
            datetime.datetime(1, 1, 1, 0, 30, tzinfo=datetime.UTC),
            NOW + BOOKABLE_HORIZON + datetime.timedelta(days=1),
        ):
            phone = _phone()
            token = await _mint_verified_token(factory, tenant_id, phone)
            with pytest.raises(SlotUnavailableError):
                await service.create_booking(
                    tenant_id,
                    raw_phone=phone,
                    verification_token=token,
                    name="בדיקה",
                    appointment_type_id=type_id,
                    starts_at=absurd,
                    terms_version=1,
                )
    finally:
        await engine.dispose()


async def test_dress_size_matching_is_case_insensitive_and_snapshots_the_catalog_label(
    app_role_url: str,
) -> None:
    """0006's uniqueness index is on lower(size_label), so "us 6" and "US 6"
    are ONE size everywhere else in the product — they must not be two here.
    What gets stored is the boutique's own spelling, never the customer's."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed_boutique(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            dress = await DressesRepository().insert(
                session,
                tenant_id=tenant_id,
                name="Aurora",
                description=None,
                price_agorot=None,
                price_visible=True,
                reserved=False,
                sort_order=0,
            )
            dress_id = dress.id
            await DressVariantsRepository().insert(
                session,
                tenant_id=tenant_id,
                dress_id=dress_id,
                size_label="US 6",
                quantity=1,
                sort_order=0,
            )
        booking = (
            await _service(factory).create_booking(
                tenant_id,
                raw_phone=phone,
                verification_token=await _mint_verified_token(factory, tenant_id, phone),
                name="נועה",
                appointment_type_id=type_id,
                starts_at=SLOT,
                terms_version=1,
                dress_id=dress_id,
                dress_size="us 6",
            )
        ).booking
        assert booking.dress_size == "US 6"
    finally:
        await engine.dispose()
