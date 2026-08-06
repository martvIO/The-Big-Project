"""F24's portal service against real Postgres as the non-owner app role.

The claims here are the ones no fake can make: the verification-token burn
riding the mint's own transaction (single-use is the token's contract, and the
mint is its third consumer after `create_booking` and the waitlist join), the
liveness of a minted session across a real expiry boundary, the customer lookup
that an F20-erased phone can never satisfy, and the mint brake's own instance.

Helpers come from `test_booking_owner_db` rather than being re-typed: every
setup here needs a REAL booking made through `create_booking`, and `_token`
mints a consumable verification row the way `OtpService` actually stores one.

⚠ db-marked: runs on CI only (no local Docker). Every test mints its own tenant
id; the container is session-scoped and nothing here truncates.
"""

import datetime
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_booking_owner_db import (
    NOW,
    SLOT_A,
    SLOT_B,
    SLOT_C,
    _claim,
    _comms,
    _comms_tenant,
    _factory,
    _loose,
    _phone,
    _row,
    _seed,
    _slot,
    _spent,
    _staff,
    _sweep_walk_in_bookings,  # noqa: F401
    _token,
)

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.tokens import hash_token
from app.booking.manage import (
    BookingAlreadyStartedError,
    BookingAwaitingPaymentError,
    BookingCancelledError,
    ManageBookingService,
    ManageTenant,
)
from app.booking.service import BookingNotFoundError, PhoneNotVerifiedError
from app.booking.tokens import manage_token_hash
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.customer_sessions import CustomerSessionsRepository
from app.db.repositories.message_log import BELL_LIMIT, MessageLogRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import (
    BookingCancelledBy,
    BookingStatus,
    MessageKind,
    MessageStatus,
    ScheduledMessageStatus,
)
from app.models.scheduled_message import ScheduledMessage
from app.notifications.service import NotificationService, OtpService
from app.notifications.unconfigured import UnconfiguredSmsSender
from app.portal.service import (
    CustomerContext,
    PortalNoBookingsError,
    PortalService,
    PortalThrottledError,
)

pytestmark = pytest.mark.db

SESSIONS = CustomerSessionsRepository()
MESSAGES = MessageLogRepository()


def _portal(
    factory: async_sessionmaker[AsyncSession],
    *,
    mint_limiter: FixedWindowRateLimiter | None = None,
    now: datetime.datetime = NOW,
    ttl_seconds: int = 30 * 24 * 3600,
) -> PortalService:
    otp = OtpService(
        factory,
        notifications=NotificationService(factory, sender=UnconfiguredSmsSender()),
        phone_limiter=_loose(),
        tenant_limiter=_loose(),
        verify_limiter=_loose(),
        ip_limiter=_loose(),
        clock=lambda: now,
    )
    return PortalService(
        factory,
        otp=otp,
        mint_limiter=mint_limiter or _loose(),
        session_ttl_seconds=ttl_seconds,
        clock=lambda: now,
    )


# --- the mint ---------------------------------------------------------------


async def test_a_verified_phone_with_a_booking_mints_a_session(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        await _claim(factory, tenant_id, type_id, phone=phone)
        result, token = await _portal(factory).create_session(
            tenant_id,
            raw_phone=phone,
            verification_token=await _token(factory, tenant_id, phone),
        )
        # The NAME the booking supplied — login never creates a customer and
        # never invents one (spec D1).
        assert result.customer_name == "נועה לוי"
        async with tenant_session(factory, tenant_id) as session:
            row = await SESSIONS.active_by_token_hash(session, tenant_id, hash_token(token), NOW)
            assert row is not None
            # Only the HASH is stored — the raw token exists in the cookie and
            # nowhere else, exactly as the staff table holds it.
            assert row.token_hash == hash_token(token)
            assert row.token_hash != token
            assert row.expires_at == NOW + datetime.timedelta(days=30)
    finally:
        await engine.dispose()


async def test_an_unknown_phone_is_portal_no_bookings_and_writes_no_session(
    app_role_url: str,
) -> None:
    """No customer row means no booking at this boutique. Refusing is the whole
    of D1: login must never CREATE a customer, because `customers.name` is NOT
    NULL and only a booking supplies a name."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    stranger = _phone()
    try:
        await _seed(factory, tenant_id)
        with pytest.raises(PortalNoBookingsError):
            await _portal(factory).create_session(
                tenant_id,
                raw_phone=stranger,
                verification_token=await _token(factory, tenant_id, stranger),
            )
    finally:
        await engine.dispose()


async def test_an_erased_customer_can_never_mint_a_session(app_role_url: str) -> None:
    """By CONSTRUCTION and not by a branch: F20 rewrites `phone` to
    `erased:{id}`, so the (tenant, normalized phone) lookup misses and she takes
    the same PORTAL_NO_BOOKINGS path a stranger takes."""
    from app.privacy.service import PrivacyService

    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    past = NOW - datetime.timedelta(days=30)
    try:
        type_id = await _seed(factory, tenant_id, date=(past - datetime.timedelta(days=2)).date())
        claim = await _claim(
            factory,
            tenant_id,
            type_id,
            starts_at=past,
            now=past - datetime.timedelta(days=7),
            phone=phone,
        )
        await PrivacyService(
            factory,
            export_limiter=_loose(),
            erase_limiter=_loose(),
            withdraw_limiter=_loose(),
        ).erase_subject(
            tenant_id,
            customer_id=claim.booking.customer_id,
            actor=_staff(tenant_id),
            reason=None,
        )
        with pytest.raises(PortalNoBookingsError):
            await _portal(factory).create_session(
                tenant_id,
                raw_phone=phone,
                verification_token=await _token(factory, tenant_id, phone),
            )
    finally:
        await engine.dispose()


async def test_the_verification_token_is_single_use_across_two_mints(app_role_url: str) -> None:
    """The burn rides the mint's transaction, so a token spent on a login cannot
    be replayed into a second session — `create_booking`'s contract, third
    consumer."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        await _claim(factory, tenant_id, type_id, phone=phone)
        token = await _token(factory, tenant_id, phone)
        portal = _portal(factory)
        await portal.create_session(tenant_id, raw_phone=phone, verification_token=token)
        with pytest.raises(PhoneNotVerifiedError):
            await portal.create_session(tenant_id, raw_phone=phone, verification_token=token)
    finally:
        await engine.dispose()


async def test_an_unknown_phone_still_burns_its_token(app_role_url: str) -> None:
    """The refusal is NOT a free retry: the burn happens before the customer
    lookup, so a caller cannot walk phone numbers on one verification."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    stranger = _phone()
    try:
        await _seed(factory, tenant_id)
        token = await _token(factory, tenant_id, stranger)
        portal = _portal(factory)
        with pytest.raises(PortalNoBookingsError):
            await portal.create_session(tenant_id, raw_phone=stranger, verification_token=token)
        with pytest.raises(PhoneNotVerifiedError):
            await portal.create_session(tenant_id, raw_phone=stranger, verification_token=token)
    finally:
        await engine.dispose()


async def test_the_mint_brake_is_its_own_instance_and_spares_the_otp_budgets(
    app_role_url: str,
) -> None:
    """`.memory/limiter-max-is-per-instance`: a key on an existing budget would
    hand this path somebody else's ceiling. A SPENT mint limiter must 429 while
    the OTP service's own limiters are untouched — and it must refuse BEFORE the
    token is burned, so a braked bride can retry with the code she already
    holds (design state E7)."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        await _claim(factory, tenant_id, type_id, phone=phone)
        token = await _token(factory, tenant_id, phone)
        with pytest.raises(PortalThrottledError):
            await _portal(factory, mint_limiter=_spent()).create_session(
                tenant_id, raw_phone=phone, verification_token=token
            )
        # The unspent token still works through a portal whose OWN limiter is
        # loose — proof the throttle neither burned it nor touched the OTP side.
        result, _ = await _portal(factory).create_session(
            tenant_id, raw_phone=phone, verification_token=token
        )
        assert result.customer_name == "נועה לוי"
    finally:
        await engine.dispose()


# --- resolve / logout -------------------------------------------------------


async def test_the_mint_me_logout_lifecycle(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        portal = _portal(factory)
        _, token = await portal.create_session(
            tenant_id,
            raw_phone=phone,
            verification_token=await _token(factory, tenant_id, phone),
        )
        context = await portal.resolve_session(tenant_id, token)
        assert context is not None
        assert context.id == claim.booking.customer_id
        assert context.tenant_id == tenant_id
        assert context.name == "נועה לוי"

        await portal.logout(tenant_id, token)
        assert await portal.resolve_session(tenant_id, token) is None
    finally:
        await engine.dispose()


async def test_a_session_stops_resolving_once_its_ttl_has_passed(app_role_url: str) -> None:
    """Fixed expiry, no sliding renewal (spec D2). The clock moves; the row does
    not."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        await _claim(factory, tenant_id, type_id, phone=phone)
        _, token = await _portal(factory, ttl_seconds=3600).create_session(
            tenant_id,
            raw_phone=phone,
            verification_token=await _token(factory, tenant_id, phone),
        )
        assert await _portal(factory).resolve_session(tenant_id, token) is not None
        later = _portal(factory, now=NOW + datetime.timedelta(hours=2))
        assert await later.resolve_session(tenant_id, token) is None
    finally:
        await engine.dispose()


async def test_an_erase_kills_a_live_portal_session(app_role_url: str) -> None:
    """Closes the loop test_privacy_subject_requests_db opens at row level: the
    revocation is only worth anything if the TOKEN stops authenticating."""
    from app.privacy.service import PrivacyService

    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    past = NOW - datetime.timedelta(days=30)
    try:
        type_id = await _seed(factory, tenant_id, date=(past - datetime.timedelta(days=2)).date())
        claim = await _claim(
            factory,
            tenant_id,
            type_id,
            starts_at=past,
            now=past - datetime.timedelta(days=7),
            phone=phone,
        )
        portal = _portal(factory)
        _, token = await portal.create_session(
            tenant_id,
            raw_phone=phone,
            verification_token=await _token(factory, tenant_id, phone),
        )
        assert await portal.resolve_session(tenant_id, token) is not None

        await PrivacyService(
            factory,
            export_limiter=_loose(),
            erase_limiter=_loose(),
            withdraw_limiter=_loose(),
        ).erase_subject(
            tenant_id,
            customer_id=claim.booking.customer_id,
            actor=_staff(tenant_id),
            reason=None,
        )
        assert await portal.resolve_session(tenant_id, token) is None
    finally:
        await engine.dispose()


async def test_a_session_never_resolves_under_another_tenant(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_a)
        await _claim(factory, tenant_a, type_id, phone=phone)
        portal = _portal(factory)
        _, token = await portal.create_session(
            tenant_a,
            raw_phone=phone,
            verification_token=await _token(factory, tenant_a, phone),
        )
        assert await portal.resolve_session(tenant_b, token) is None
    finally:
        await engine.dispose()


# --- "My Bookings" and the mirrored actions ---------------------------------


def _manage_tenant(tenant_id: uuid.UUID) -> ManageTenant:
    return ManageTenant(id=tenant_id, name="בלה כלות", settings={})


async def _sign_in(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, phone: str
) -> tuple[PortalService, CustomerContext]:
    portal = _portal(factory)
    _, token = await portal.create_session(
        tenant_id,
        raw_phone=phone,
        verification_token=await _token(factory, tenant_id, phone),
    )
    customer = await portal.resolve_session(tenant_id, token)
    assert customer is not None
    return portal, customer


async def test_the_list_is_split_ordered_and_scoped_to_her_alone(app_role_url: str) -> None:
    """Three claims in one seed, because they share it: the split is on the
    SERVER's clock, upcoming reads ASC and past DESC, and another customer's
    bookings are not on the wire at all."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    hers, neighbours = _phone(), _phone()
    past_date = (NOW - datetime.timedelta(days=10)).date()
    try:
        type_id = await _seed(factory, tenant_id, capacity=3)
        past_type_id = await _seed(factory, tenant_id, capacity=3, date=past_date)
        near = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=hers)
        far = await _claim(factory, tenant_id, type_id, starts_at=SLOT_B, phone=hers)
        old = await _claim(
            factory,
            tenant_id,
            past_type_id,
            starts_at=_slot(10, date=past_date),
            now=NOW - datetime.timedelta(days=20),
            phone=hers,
        )
        stranger = await _claim(factory, tenant_id, type_id, starts_at=SLOT_C, phone=neighbours)

        portal, customer = await _sign_in(factory, tenant_id, hers)
        view = await portal.list_bookings(tenant_id, customer)

        assert [row.id for row in view.upcoming] == [near.booking.id, far.booking.id]
        assert [row.id for row in view.past] == [old.booking.id]
        assert stranger.booking.id not in {row.id for row in view.upcoming + view.past}
        # The row is the design's seven facts and carries NO manage token — a
        # capability on a list row is a capability in a scroll.
        assert set(view.upcoming[0].model_dump()) == {
            "id",
            "starts_at",
            "status",
            "attendance_confirmed_at",
            "appointment_type_name",
            "dress_name",
            "dress_size",
        }
    finally:
        await engine.dispose()


async def test_a_pending_payment_hold_appears_in_upcoming_with_its_status(
    app_role_url: str,
) -> None:
    """The seat is hers and the money is not in. Hiding the row would make an
    appointment she can still lose invisible (spec D4)."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        async with tenant_session(factory, tenant_id) as session:
            booking = await session.get(Booking, claim.booking.id)
            assert booking is not None
            booking.status = BookingStatus.PENDING_PAYMENT.value

        portal, customer = await _sign_in(factory, tenant_id, phone)
        view = await portal.list_bookings(tenant_id, customer)
        assert [row.status for row in view.upcoming] == [BookingStatus.PENDING_PAYMENT.value]
        assert view.past == []
    finally:
        await engine.dispose()


async def test_the_portal_detail_is_field_for_field_the_token_pages_detail(
    app_role_url: str,
) -> None:
    """The mirror guarantee, asserted as an EQUALITY between the two transports
    for one booking rather than as two similar shapes (spec D4)."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        token = claim.manage_token
        assert token is not None
        async with tenant_session(factory, tenant_id) as session:
            booking = await session.get(Booking, claim.booking.id)
            assert booking is not None
            booking.manage_token_hash = manage_token_hash(token)

        portal, customer = await _sign_in(factory, tenant_id, phone)
        through_session = await portal.get_booking(
            _manage_tenant(tenant_id), customer, claim.booking.id
        )
        through_token = await ManageBookingService(
            factory,
            lookup_limiter=_loose(),
            clock=lambda: NOW,
        ).lookup(_manage_tenant(tenant_id), token=token)
        assert through_session == through_token
    finally:
        await engine.dispose()


async def test_another_customers_booking_is_the_same_404_as_an_unknown_id(
    app_role_url: str,
) -> None:
    """No cross-customer existence oracle: a probe cannot learn that a booking
    id belongs to somebody else at this boutique."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    hers, neighbours = _phone(), _phone()
    try:
        type_id = await _seed(factory, tenant_id, capacity=2)
        await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=hers)
        stranger = await _claim(factory, tenant_id, type_id, starts_at=SLOT_B, phone=neighbours)
        portal, customer = await _sign_in(factory, tenant_id, hers)
        tenant = _manage_tenant(tenant_id)
        for booking_id in (stranger.booking.id, uuid.uuid4()):
            with pytest.raises(BookingNotFoundError):
                await portal.get_booking(tenant, customer, booking_id)
            with pytest.raises(BookingNotFoundError):
                await portal.cancel(tenant, customer, booking_id)
            with pytest.raises(BookingNotFoundError):
                await portal.confirm_attendance(tenant, customer, booking_id)
    finally:
        await engine.dispose()


async def test_the_portal_confirm_writes_attendance_confirmed_at(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        portal, customer = await _sign_in(factory, tenant_id, phone)
        view = await portal.confirm_attendance(
            _manage_tenant(tenant_id), customer, claim.booking.id
        )
        assert view.booking.attendance_confirmed_at == NOW
        row = await _row(factory, tenant_id, claim.booking.id)
        assert row is not None and row.attendance_confirmed_at == NOW
    finally:
        await engine.dispose()


async def test_the_portal_cancel_frees_the_seat_stamps_customer_and_kills_the_reminder(
    app_role_url: str,
) -> None:
    """THE SAME ASSERTIONS AS THE TOKEN-PAGE CANCEL SUITE, on purpose: the
    mirror is only real if the portal's cancel does all three things the
    tokenized one does — and it does them because it IS the same code."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        comms, _ = _comms(factory)
        # The reminder row the confirmation flow would have written. Through the
        # product's own writer, so a pending row exists to be cancelled.
        assert (
            await comms.reschedule_reminder(
                _comms_tenant(tenant_id),
                booking_id=claim.booking.id,
                starts_at=claim.booking.starts_at,
            )
            is not None
        )

        portal, customer = await _sign_in(factory, tenant_id, phone)
        view = await portal.cancel(_manage_tenant(tenant_id), customer, claim.booking.id)
        assert view.booking.status == BookingStatus.CANCELLED.value

        row = await _row(factory, tenant_id, claim.booking.id)
        assert row is not None
        assert row.status == BookingStatus.CANCELLED.value
        assert row.cancelled_by == BookingCancelledBy.CUSTOMER.value
        assert row.cancelled_at is not None

        async with tenant_session(factory, tenant_id) as session:
            scheduled = list(
                (
                    await session.execute(
                        select(ScheduledMessage).where(
                            ScheduledMessage.tenant_id == tenant_id,
                            ScheduledMessage.booking_id == claim.booking.id,
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert scheduled and all(
            row.status == ScheduledMessageStatus.CANCELLED.value for row in scheduled
        )

        # The seat is free STRUCTURALLY — both partial unique indexes exclude
        # `cancelled` — so she can rebook the same instant immediately.
        rebooked = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=phone)
        assert rebooked.booking.id != claim.booking.id
    finally:
        await engine.dispose()


async def test_the_portal_actions_answer_the_same_409_matrix(app_role_url: str) -> None:
    """Started, cancelled and awaiting-payment, through the SHARED transitions.
    A second guard set would be a second product."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        portal, customer = await _sign_in(factory, tenant_id, phone)
        tenant = _manage_tenant(tenant_id)

        # started: the clock has passed starts_at.
        after = _portal(factory, now=SLOT_A + datetime.timedelta(minutes=1))
        with pytest.raises(BookingAlreadyStartedError):
            await after.confirm_attendance(tenant, customer, claim.booking.id)
        with pytest.raises(BookingAlreadyStartedError):
            await after.cancel(tenant, customer, claim.booking.id)

        # awaiting payment.
        async with tenant_session(factory, tenant_id) as session:
            booking = await session.get(Booking, claim.booking.id)
            assert booking is not None
            booking.status = BookingStatus.PENDING_PAYMENT.value
        with pytest.raises(BookingAwaitingPaymentError):
            await portal.confirm_attendance(tenant, customer, claim.booking.id)
        with pytest.raises(BookingAwaitingPaymentError):
            await portal.cancel(tenant, customer, claim.booking.id)

        # cancelled: confirm refuses, cancel is the idempotent 200.
        async with tenant_session(factory, tenant_id) as session:
            booking = await session.get(Booking, claim.booking.id)
            assert booking is not None
            booking.status = BookingStatus.CANCELLED.value
        with pytest.raises(BookingCancelledError):
            await portal.confirm_attendance(tenant, customer, claim.booking.id)
        repeat = await portal.cancel(tenant, customer, claim.booking.id)
        assert repeat.booking.status == BookingStatus.CANCELLED.value
    finally:
        await engine.dispose()


# --- the `.ics` (spec D5) ---------------------------------------------------


async def test_both_ics_transports_answer_the_same_bytes_for_one_booking(
    app_role_url: str,
) -> None:
    """ONE builder, two doors — asserted as byte equality rather than as two
    plausible files. If these ever diverge, one of her calendars is wrong and
    nothing else in the product would notice."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        token = claim.manage_token
        assert token is not None
        async with tenant_session(factory, tenant_id) as session:
            booking = await session.get(Booking, claim.booking.id)
            assert booking is not None
            booking.manage_token_hash = manage_token_hash(token)

        portal, customer = await _sign_in(factory, tenant_id, phone)
        through_session = await portal.get_booking_ics(
            _manage_tenant(tenant_id),
            customer,
            claim.booking.id,
            slug="bella",
            base_domain="modryn.co.il",
        )
        through_token = await ManageBookingService(
            factory, lookup_limiter=_loose(), clock=lambda: NOW
        ).ics(
            _manage_tenant(tenant_id),
            token=token,
            slug="bella",
            base_domain="modryn.co.il",
        )
        assert through_session == through_token
        assert f"UID:{claim.booking.id}@bella.modryn.co.il" in through_session
        # The whole D5 rule, on a booking whose row carries a live link.
        assert token not in through_session
    finally:
        await engine.dispose()


async def test_the_ics_reads_the_duration_from_an_archived_appointment_type(
    app_role_url: str,
) -> None:
    """A booking snapshots the type's NAME but never its length, so DTEND has to
    come from the live row — and archiving a type is how a boutique retires an
    offering, not how it shortens a fitting somebody already booked."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        async with tenant_session(factory, tenant_id) as session:
            assert await AppointmentTypesRepository().soft_delete(session, tenant_id, type_id)

        portal, customer = await _sign_in(factory, tenant_id, phone)
        text = await portal.get_booking_ics(
            _manage_tenant(tenant_id),
            customer,
            claim.booking.id,
            slug="bella",
            base_domain="modryn.co.il",
        )
        # 60 minutes from the seeded type, not a fallback constant.
        starts = claim.booking.starts_at.astimezone(datetime.UTC)
        ends = starts + datetime.timedelta(minutes=60)
        assert f"DTSTART:{starts.strftime('%Y%m%dT%H%M%SZ')}" in text
        assert f"DTEND:{ends.strftime('%Y%m%dT%H%M%SZ')}" in text
    finally:
        await engine.dispose()


async def test_a_cancelled_booking_serves_no_ics_on_either_transport(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        portal, customer = await _sign_in(factory, tenant_id, phone)
        await portal.cancel(_manage_tenant(tenant_id), customer, claim.booking.id)
        with pytest.raises(BookingCancelledError):
            await portal.get_booking_ics(
                _manage_tenant(tenant_id),
                customer,
                claim.booking.id,
                slug="bella",
                base_domain="modryn.co.il",
            )
    finally:
        await engine.dispose()


# --- the bell (spec D6) -----------------------------------------------------


async def _log(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    phone: str,
    booking_id: uuid.UUID | None,
    kind: str,
    status: str = MessageStatus.SENT.value,
    body: str = "גוף ההודעה",
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await MESSAGES.insert(
            session,
            tenant_id=tenant_id,
            phone=phone,
            kind=kind,
            body=body,
            booking_id=booking_id,
        )
        if status != MessageStatus.QUEUED.value:
            await MESSAGES.update_status(session, tenant_id, row.id, status=status)
        return row.id


async def test_the_bell_shows_only_sent_non_otp_rows_for_her_own_bookings(
    app_role_url: str,
) -> None:
    """Four exclusions in one seed, because a bell that leaks any of them is the
    same bug: an OTP row (masked body, not news), a FAILED row (never reached
    her — the bell mirrors her inbox, not our attempts), another customer's row,
    and a row with no booking at all."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    hers, neighbours = _phone(), _phone()
    try:
        type_id = await _seed(factory, tenant_id, capacity=2)
        mine = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=hers)
        theirs = await _claim(factory, tenant_id, type_id, starts_at=SLOT_B, phone=neighbours)

        wanted = await _log(
            factory,
            tenant_id,
            phone=hers,
            booking_id=mine.booking.id,
            kind=MessageKind.CONFIRMATION.value,
        )
        await _log(
            factory,
            tenant_id,
            phone=hers,
            booking_id=mine.booking.id,
            kind=MessageKind.OTP.value,
            body="הקוד שלך ●●●",
        )
        await _log(
            factory,
            tenant_id,
            phone=hers,
            booking_id=mine.booking.id,
            kind=MessageKind.REMINDER.value,
            status=MessageStatus.FAILED.value,
        )
        await _log(
            factory,
            tenant_id,
            phone=neighbours,
            booking_id=theirs.booking.id,
            kind=MessageKind.CONFIRMATION.value,
        )
        await _log(
            factory, tenant_id, phone=hers, booking_id=None, kind=MessageKind.CONFIRMATION.value
        )

        portal, customer = await _sign_in(factory, tenant_id, hers)
        view = await portal.bell(tenant_id, customer)
        assert [item.id for item in view.items] == [wanted]
        assert view.items[0].starts_at == mine.booking.starts_at
        assert view.items[0].appointment_type_name == mine.booking.appointment_type_name
        # The shape carries no `body`, asserted against the model rather than
        # against a rendered string.
        assert set(view.items[0].model_dump()) == {
            "id",
            "kind",
            "created_at",
            "booking_id",
            "starts_at",
            "appointment_type_name",
        }
    finally:
        await engine.dispose()


async def test_the_bell_is_newest_first_and_capped(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        for _ in range(BELL_LIMIT + 5):
            await _log(
                factory,
                tenant_id,
                phone=phone,
                booking_id=claim.booking.id,
                kind=MessageKind.REMINDER.value,
            )
        portal, customer = await _sign_in(factory, tenant_id, phone)
        view = await portal.bell(tenant_id, customer)
        assert len(view.items) == BELL_LIMIT
        created = [item.created_at for item in view.items]
        assert created == sorted(created, reverse=True)
    finally:
        await engine.dispose()


async def test_a_never_opened_bell_counts_everything_and_the_stamp_clears_it(
    app_role_url: str,
) -> None:
    """NULL `bell_seen_at` is "never opened", so every message is unread — which
    is why the column ships with no default."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, phone=phone)
        for kind in (MessageKind.CONFIRMATION.value, MessageKind.REMINDER.value):
            await _log(factory, tenant_id, phone=phone, booking_id=claim.booking.id, kind=kind)

        portal, customer = await _sign_in(factory, tenant_id, phone)
        assert (await portal.bell(tenant_id, customer)).unread_count == 2

        # The stamp is taken from the service's clock, which the seeded rows
        # predate (they carry the DB's real `now()`), so a LATER instant is what
        # marks them read.
        future = _portal(factory, now=datetime.datetime.now(datetime.UTC) + datetime.timedelta(1))
        await future.mark_bell_seen(tenant_id, customer)
        after = await portal.bell(tenant_id, customer)
        assert after.unread_count == 0
        # The items are still there — seen is not deleted.
        assert len(after.items) == 2
    finally:
        await engine.dispose()
