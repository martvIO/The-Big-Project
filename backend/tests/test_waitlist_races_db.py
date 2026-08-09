"""F23's centrepiece: the six interleavings only Postgres can settle.

**The races are the feature.** Spec §Test plan and plan §3 both say so, and this
file is authored WHOLE before a line of cascade or claim code exists — it is the
acceptance contract, not a regression net written after the fact. Every function
below names the shipped race test it mirrors, because the whole design argument
of F23 is that it introduces no new arbitration primitive: the offer is a guarded
UPDATE like `_expire_holds`, the claim is a guarded UPDATE followed by the SHIPPED
booking engine under the SHIPPED advisory lock and the SHIPPED partial unique
index.

**Why every driver gets its own connection.** `NullPool` + `asyncio.gather`, the
`test_deposit_races_db.py` discipline verbatim, and for the reason that file
states: a sequential loop over one connection PASSES while the code is broken,
because one transaction cannot contend with itself.

**Why the clock is frozen and injected on BOTH sides.** `NOW` is a module
constant. The offer deadline is written by the cascade and read by the claim, so
a test that cannot pin both sides of that comparison cannot pin the race at all.
Where the two sides must legitimately DISAGREE — the expiry-vs-late-claim race is
exactly the interval `now_claim < expires_at <= now_sweep` — the disagreement is
one second wide and spelled out at the test, never smuggled in as drift.

**NOW is 12:00 Jerusalem**, deliberately: outside the `[21:00, 08:00)` quiet block
(D3), so the cascade is free to issue. A file written at 22:00 local would have
every offer test passing for the wrong reason — nothing issued, nothing to race.

**Evidence is read off return values and INSERTed rows**, never off a re-read of a
row a guarded UPDATE just touched — `BookingsRepository.cancel`'s docstring
explains why ORM-enabled DML with `evaluate` synchronization cannot answer "did I
win?".

⚠ db-marked: first run is CI (no local Docker). Cleanup is not optional — this
file writes `bookings.status = 'pending_payment'` and `cancelled_by = 'expired'`,
and migration 0015's downgrade narrows both CHECKs, which Postgres refuses while
a row still holds them.
"""

import asyncio
import datetime
import secrets
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.tokens import hash_token
from app.booking.comms import BookingCommsService, CommsTenant
from app.booking.service import BookingClaim, BookingService, SlotUnavailableError
from app.booking.validation import jerusalem_day_index
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.otp_codes import OtpCodesRepository
from app.db.repositories.payments import PaymentsRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.repositories.waitlist_entries import WaitlistEntriesRepository
from app.db.tenant import tenant_session
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.constants import (
    AppointmentAudience,
    AuditAction,
    BookingStatus,
    MessageKind,
    PaymentStatus,
    ScheduledMessageKind,
    ScheduledMessageStatus,
    WaitlistEntryStatus,
)
from app.models.customer import Customer
from app.models.message_log import MessageLog
from app.models.payment import Payment
from app.models.scheduled_message import ScheduledMessage
from app.models.waitlist_entry import WaitlistEntry
from app.notifications.fake import FakeSmsSender
from app.notifications.service import NotificationService, OtpService
from app.notifications.validation import normalize_israeli_mobile
from app.payments.fake import FakeGateway, fake_webhook_body, sign_fake_webhook
from app.payments.secretbox import FakeSecretBox
from app.payments.service import GatewayCredentialService, PaymentService
from app.payments.sweeper import DepositSweeper, SweepResult
from app.payments.webhook_router import DepositBookingService
from app.storefront.validation import BOUTIQUE_TIMEZONE
from app.waitlist.cascade import WaitlistCascade
from app.waitlist.offer_service import OfferNotClaimableError, WaitlistOfferService

pytestmark = pytest.mark.db

SECRET = "webhook-secret-1"
GOOD = {"merchant_id": "m-1", "api_key": "k-1", "webhook_secret": SECRET}

TARGET_DATE = datetime.date(2026, 8, 23)
BASE_DOMAIN = "modryn.co.il"
RETURN_URL = "https://bella.modryn.co.il/book/return"
DEPOSIT_AGOROT = 30_000
SETTINGS: dict[str, object] = {"toggles": {"deposits_enabled": True}}

# 09:00 UTC == 12:00 Asia/Jerusalem in August. See the module docstring: the
# quiet-hours gate makes the WALL CLOCK load-bearing in this file.
NOW = datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.UTC)

OFFER_WINDOW_SECONDS = 2 * 3600
OFFER_MIN_LEAD_SECONDS = 2 * 3600
QUIET_START_HOUR = 21
QUIET_END_HOUR = 8

# The sweeper's own knobs — claim 2's `hold + poll` grace only. Production
# values, so a booking created this instant is never mistaken for an orphan.
SWEEP_HOLD_SECONDS = 900
POLL_SECONDS = 60
LIVE_HOLD_SECONDS = 900
EXPIRED_HOLD_SECONDS = 0


def _clock() -> datetime.datetime:
    return NOW


def _at(hour: int, minute: int = 0) -> datetime.datetime:
    """⚠ The ONLY correct way to build an offered instant in this file. The rule
    seeded below opens 09:00-13:00 LOCAL, and NOW is 12:00 local — a raw UTC
    instant is not on the grid."""
    return datetime.datetime.combine(
        TARGET_DATE, datetime.time(hour, minute), tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)


# The earliest instant the seeded day offers, which is therefore the one the
# cascade picks: TARGET_DATE is weeks out, so `starts_at > now + min_lead`
# excludes nothing.
SLOT = _at(9, 0)


# --- wiring -----------------------------------------------------------------


def _factory(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _loose() -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(max_attempts=10_000, window_seconds=3600, clock=lambda: 0.0)


def _phone() -> str:
    return f"+9725{uuid.uuid4().int % 10**8:08d}"


def _tenant(tenant_id: uuid.UUID) -> CommsTenant:
    return CommsTenant(id=tenant_id, slug="bella", name="בלה כלות", phone="052-1234567")


def _signed(*, session_id: str, transaction_id: str) -> tuple[bytes, str]:
    body = fake_webhook_body(
        provider_session_id=session_id,
        provider_transaction_id=transaction_id,
        amount_agorot=DEPOSIT_AGOROT,
        paid=True,
    )
    return body, sign_fake_webhook(webhook_secret=SECRET, body=body)


class _Rig:
    """Every collaborator one test needs, off one factory and one clock."""

    type_id: uuid.UUID

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        tenant_id: uuid.UUID,
        *,
        hold_seconds: int,
    ) -> None:
        self.factory = factory
        self.tenant_id = tenant_id
        self.gateway = FakeGateway()
        self.sender = FakeSmsSender()
        self.credentials = GatewayCredentialService(
            factory,
            gateway=self.gateway,
            secret_box=FakeSecretBox(),
            connect_limiter=_loose(),
            validate_limiter=_loose(),
            clock=_clock,
        )
        self.payments = PaymentService(
            factory, gateway=self.gateway, credentials=self.credentials, clock=_clock
        )
        self.comms = BookingCommsService(
            factory,
            notifications=NotificationService(factory, sender=self.sender),
            base_domain=BASE_DOMAIN,
            clock=_clock,
        )
        self.deposits = DepositBookingService(
            factory,
            payments=self.payments,
            credentials=self.credentials,
            comms=self.comms,
            clock=_clock,
        )
        self.bookings = BookingService(
            factory,
            otp=OtpService(
                factory,
                notifications=NotificationService(factory, sender=FakeSmsSender()),
                phone_limiter=_loose(),
                tenant_limiter=_loose(),
                verify_limiter=_loose(),
                ip_limiter=_loose(),
                clock=_clock,
            ),
            create_limiter=_loose(),
            phone_limiter=_loose(),
            clock=_clock,
            gateway_credentials=self.credentials,
            payments=self.payments,
            deposit_hold_seconds=hold_seconds,
        )
        self.sweeper = DepositSweeper(
            factory,
            hold_seconds=SWEEP_HOLD_SECONDS,
            poll_interval_seconds=POLL_SECONDS,
            clock=_clock,
        )
        self.cascade = self.cascade_at(NOW)
        self.offers = self.offers_at(NOW)

    def cascade_at(self, now: datetime.datetime) -> WaitlistCascade:
        """A cascade pinned to `now`. Two instances on two clocks is how the
        expiry race is armed without unpinning anything else."""
        return WaitlistCascade(
            self.factory,
            window_seconds=OFFER_WINDOW_SECONDS,
            min_lead_seconds=OFFER_MIN_LEAD_SECONDS,
            quiet_start_hour=QUIET_START_HOUR,
            quiet_end_hour=QUIET_END_HOUR,
            clock=lambda: now,
        )

    def offers_at(self, now: datetime.datetime) -> WaitlistOfferService:
        return WaitlistOfferService(
            self.factory,
            lookup_limiter=_loose(),
            gateway_credentials=self.credentials,
            clock=lambda: now,
        )

    async def settle(self, *, session_id: str, transaction_id: str) -> None:
        body, signature = _signed(session_id=session_id, transaction_id=transaction_id)
        await self.deposits.settle(_tenant(self.tenant_id), body=body, signature=signature)


async def _seed(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    capacity: int,
    deposit: bool,
) -> uuid.UUID:
    """⚠ ONE call per tenant. It provisions a whole boutique — the appointment
    type «מדידה ראשונה» and terms version 1 — so a second call dies on
    `idx_appointment_types_tenant_name_unique`."""
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
            name="מדידה ראשונה",
            duration_minutes=60,
            audience=AppointmentAudience.ALL.value,
            deposit_required=deposit,
            deposit_amount_agorot=DEPOSIT_AGOROT if deposit else 0,
            sort_order=0,
        )
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


async def _rig(
    url: str, *, hold_seconds: int = LIVE_HOLD_SECONDS, capacity: int = 1, deposit: bool = False
) -> tuple[AsyncEngine, _Rig]:
    engine, factory = _factory(url)
    tenant_id = uuid.uuid4()
    rig = _Rig(factory, tenant_id, hold_seconds=hold_seconds)
    await rig.credentials.connect(tenant_id, fields=GOOD, actor_id=uuid.uuid4())
    rig.type_id = await _seed(factory, tenant_id, capacity=capacity, deposit=deposit)
    return engine, rig


async def _verified(rig: _Rig, raw_phone: str) -> str:
    """A consumed OTP, minted outside the gathered section: two racers must
    contend over the SEAT, not over the OTP table."""
    token = secrets.token_urlsafe(16)
    repo = OtpCodesRepository()
    future = datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC)
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        row = await repo.insert(
            session,
            tenant_id=rig.tenant_id,
            phone=normalize_israeli_mobile(raw_phone),
            code_hash="seed",
            expires_at=future,
        )
        await repo.mark_consumed(
            session,
            rig.tenant_id,
            row.id,
            verification_token_hash=hash_token(token),
            verification_expires_at=future,
        )
    return token


async def _create(rig: _Rig, *, starts_at: datetime.datetime = SLOT) -> BookingClaim:
    """A direct booking, through the shipped storefront path."""
    phone = _phone()
    return await rig.bookings.create_booking(
        rig.tenant_id,
        raw_phone=phone,
        verification_token=await _verified(rig, phone),
        name="נועה לוי",
        appointment_type_id=rig.type_id,
        starts_at=starts_at,
        terms_version=1,
        settings=SETTINGS,
    )


async def _join(rig: _Rig, *, phone: str | None = None) -> uuid.UUID:
    """A `waiting` entry for (TARGET_DATE, the seeded type)."""
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        row = await WaitlistEntriesRepository().insert(
            session,
            tenant_id=rig.tenant_id,
            day=TARGET_DATE,
            appointment_type_id=rig.type_id,
            phone=phone or _phone(),
        )
        return row.id


async def _offer_token(rig: _Rig, entry_id: uuid.UUID) -> str:
    """The RAW token, off the `scheduled_messages` row the cascade wrote — the
    only place it exists after the transaction ends (the entry keeps sha256
    only). Reading it here is exactly what `drain_due` will do to build the SMS
    link, so the fixture and the product agree by construction."""
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        stmt = select(ScheduledMessage).where(
            ScheduledMessage.waitlist_entry_id == entry_id,
            ScheduledMessage.kind == ScheduledMessageKind.WAITLIST_OFFER.value,
            ScheduledMessage.status == ScheduledMessageStatus.PENDING.value,
        )
        row = (await session.execute(stmt)).scalars().first()
    assert row is not None, "the cascade must have queued an offer message"
    assert row.manage_token is not None, "a pending offer row carries the raw token"
    return row.manage_token


async def _armed(rig: _Rig) -> tuple[uuid.UUID, str]:
    """One `waiting` entry, cascaded into a live offer. Through the product on
    both halves: no test writes `status='offered'` by hand, so the fixture
    cannot drift from what the cascade actually produces."""
    entry_id = await _join(rig)
    result = await rig.cascade.run(rig.tenant_id)
    assert result.offered == 1, f"the cascade must issue exactly one offer, got {result!r}"
    return entry_id, await _offer_token(rig, entry_id)


# --- reads ------------------------------------------------------------------


async def _entry(rig: _Rig, entry_id: uuid.UUID) -> WaitlistEntry:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        row = await WaitlistEntriesRepository().by_id(session, rig.tenant_id, entry_id)
    assert row is not None
    return row


async def _bookings(rig: _Rig) -> list[Booking]:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        stmt = select(Booking).where(Booking.tenant_id == rig.tenant_id)
        return list((await session.execute(stmt)).scalars().all())


async def _booking(rig: _Rig, booking_id: uuid.UUID) -> Booking:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        row = await BookingsRepository().by_id(session, rig.tenant_id, booking_id)
    assert row is not None
    return row


async def _payment_for(rig: _Rig, booking_id: uuid.UUID) -> Payment:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        rows = await PaymentsRepository().by_booking_ids(session, rig.tenant_id, [booking_id])
    assert booking_id in rows
    return rows[booking_id]


async def _offer_messages(rig: _Rig) -> list[ScheduledMessage]:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        stmt = select(ScheduledMessage).where(
            ScheduledMessage.tenant_id == rig.tenant_id,
            ScheduledMessage.kind == ScheduledMessageKind.WAITLIST_OFFER.value,
        )
        return list((await session.execute(stmt)).scalars().all())


async def _kinds(rig: _Rig) -> list[str]:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        stmt = select(MessageLog.kind).order_by(MessageLog.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def _actions(rig: _Rig) -> list[str]:
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        stmt = select(AuditLog.action).order_by(AuditLog.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def _purge(rig: _Rig) -> None:
    """MANDATORY. A leaked `pending_payment` or `cancelled_by='expired'` row
    makes migration 0015's own downgrade fail and takes the round-trip suite
    with it."""
    async with tenant_session(rig.factory, rig.tenant_id) as session:
        await session.execute(
            delete(ScheduledMessage).where(ScheduledMessage.tenant_id == rig.tenant_id)
        )
        await session.execute(delete(MessageLog).where(MessageLog.tenant_id == rig.tenant_id))
        await session.execute(delete(Booking).where(Booking.tenant_id == rig.tenant_id))
        await session.execute(delete(WaitlistEntry).where(WaitlistEntry.tenant_id == rig.tenant_id))
        await session.execute(delete(Customer).where(Customer.tenant_id == rig.tenant_id))
        await session.execute(delete(AuditLog).where(AuditLog.tenant_id == rig.tenant_id))


# --- race 1: a claim and a direct booker on the last seat -------------------


async def test_a_claim_and_a_direct_booker_race_the_last_seat_and_exactly_one_wins(
    app_role_url: str,
) -> None:
    """Mirrors `test_deposit_races_db.py::test_two_brides_race_for_the_last_seat…`.

    D4's central promise: the claim is exactly as double-book-proof as a direct
    booking, because it IS a direct booking — same
    `pg_advisory_xact_lock(hashtext(tenant_id))`, same `offered_slot`, same
    `idx_bookings_slot_seat_unique`. Two drivers, one seat, either order.

    **The losing-claim assertion is the subtle one and it is design F-O2**: when
    the direct booker wins, the claim's whole transaction rolls back INCLUDING
    the guarded `offered -> claimed` UPDATE, so the entry reads `offered`, not
    `expired` and not `claimed`. The page then renders «התור הזה נתפס בינתיים»
    over a live offer, and a reload re-renders the live offer. That is correct
    (D4: no eager advance) and must not be "fixed".
    """
    engine, rig = await _rig(app_role_url, capacity=1)
    try:
        entry_id, token = await _armed(rig)

        claimed, created = await asyncio.gather(
            rig.offers.claim(
                rig.tenant_id, token=token, name="רותם לוי", terms_version=1, settings=SETTINGS
            ),
            _create(rig),
            return_exceptions=True,
        )

        rows = await _bookings(rig)
        assert len(rows) == 1, f"exactly one seat, exactly one row: {rows!r}"

        entry = await _entry(rig, entry_id)
        if isinstance(claimed, BookingClaim):
            assert isinstance(created, SlotUnavailableError), f"a third outcome: {created!r}"
            assert entry.status == WaitlistEntryStatus.CLAIMED.value
            assert claimed.manage_token is not None
            assert rows[0].id == claimed.booking.id
        else:
            assert isinstance(claimed, SlotUnavailableError), f"a third outcome: {claimed!r}"
            assert isinstance(created, BookingClaim)
            # F-O2. The rollback covers step 2 of D4.
            assert entry.status == WaitlistEntryStatus.OFFERED.value
            assert entry.offer_token_hash is not None, (
                "the token survives the rollback with the status — otherwise the "
                "page could never render the live offer again"
            )
    finally:
        await _purge(rig)
        await engine.dispose()


# --- race 2: two deliveries of one offer token ------------------------------


async def test_two_deliveries_of_one_offer_token_book_once_and_mint_one_manage_token(
    app_role_url: str,
) -> None:
    """Mirrors `::test_two_concurrent_deliveries_confirm_once_text_once_and_log_once`.

    An SMS delivered twice — a provider retry, a bride double-tapping — is one
    offer, so it is one booking and one manage token. The arbiter is D4 step 2's
    single guarded UPDATE (`status='offered' AND offer_expires_at > now`), not a
    lock and not a pre-check: the loser matches zero rows and is TOLD the state
    it lost to rather than being handed a second seat.
    """
    engine, rig = await _rig(app_role_url, capacity=2)
    try:
        _, token = await _armed(rig)

        first, second = await asyncio.gather(
            rig.offers.claim(
                rig.tenant_id, token=token, name="רותם לוי", terms_version=1, settings=SETTINGS
            ),
            rig.offers.claim(
                rig.tenant_id, token=token, name="רותם לוי", terms_version=1, settings=SETTINGS
            ),
            return_exceptions=True,
        )

        winners = [r for r in (first, second) if isinstance(r, BookingClaim)]
        losers = [r for r in (first, second) if not isinstance(r, BookingClaim)]
        assert len(winners) == 1, f"exactly one delivery may book: {first!r} / {second!r}"
        assert len(losers) == 1
        assert isinstance(losers[0], OfferNotClaimableError), f"a third outcome: {losers[0]!r}"
        # The capacity is 2, so the seat was never the constraint — the ENTRY
        # was. A `SlotUnavailableError` here would mean the guard leaked.
        assert losers[0].state == WaitlistEntryStatus.CLAIMED.value

        rows = await _bookings(rig)
        assert len(rows) == 1, f"one offer, one booking, whatever the delivery count: {rows!r}"
        assert winners[0].manage_token is not None
    finally:
        await _purge(rig)
        await engine.dispose()


# --- race 3: the expiry sweep and a late claim ------------------------------


async def test_the_expiry_sweep_and_a_late_claim_never_both_win(
    app_role_url: str,
) -> None:
    """Mirrors `::test_the_sweeper_and_the_webhook_never_both_win_the_same_hold`.

    The genuine window is one second wide and it is spelled out rather than
    stumbled into: the expiry matches `offer_expires_at <= now_sweep` and the
    claim matches `offer_expires_at > now_claim`, so BOTH predicates hold exactly
    when `now_claim < offer_expires_at <= now_sweep`. Arming the claim one second
    behind the sweep is what makes either arm reachable; without it one driver
    would be structurally impossible and the test would prove nothing.

    Two guarded UPDATEs on one row, no locking clause on either: the loser blocks
    on the row lock, wakes, and matches nothing because the status has moved.
    """
    engine, rig = await _rig(app_role_url, capacity=1)
    try:
        entry_id, token = await _armed(rig)
        deadline = (await _entry(rig, entry_id)).offer_expires_at
        assert deadline == NOW + datetime.timedelta(seconds=OFFER_WINDOW_SECONDS)

        sweeping = rig.cascade_at(deadline)
        claiming = rig.offers_at(deadline - datetime.timedelta(seconds=1))

        swept, claimed = await asyncio.gather(
            sweeping.run(rig.tenant_id),
            claiming.claim(
                rig.tenant_id, token=token, name="רותם לוי", terms_version=1, settings=SETTINGS
            ),
            return_exceptions=True,
        )
        assert not isinstance(swept, BaseException), f"the cascade must never raise: {swept!r}"

        entry = await _entry(rig, entry_id)
        rows = await _bookings(rig)
        if isinstance(claimed, BookingClaim):
            assert entry.status == WaitlistEntryStatus.CLAIMED.value
            assert swept.expired == 0, "the expiry UPDATE must have matched nothing"
            assert len(rows) == 1
        else:
            assert isinstance(claimed, OfferNotClaimableError), f"a third outcome: {claimed!r}"
            assert entry.status == WaitlistEntryStatus.EXPIRED.value
            assert swept.expired == 1
            assert rows == [], "an expired offer books nothing"
    finally:
        await _purge(rig)
        await engine.dispose()


# --- race 4: two cascade ticks ----------------------------------------------


async def test_two_cascade_ticks_never_produce_two_live_offers_for_one_pair(
    app_role_url: str,
) -> None:
    """Mirrors `::test_the_crash_window_is_repaired_exactly_once_by_concurrent_redeliveries`.

    Two worker replicas on the same 60-second tick, or one replica whose previous
    tick ran long. The arbiter is the guarded `WHERE status='waiting'` UPDATE and
    nothing else — D3 statement 1 takes no lock, because losing is a no-op rather
    than an error. The `scheduled_messages` offer-side pending-unique index is the
    second line: two ticks that somehow both moved a row would still converge to
    one queued SMS instead of texting a bride twice.

    Two `waiting` entries for one pair, deliberately: if the guard were missing,
    the natural failure is not "one entry offered twice" but "both entries
    offered at once", which is the broadcast blast #13 forbids.
    """
    engine, rig = await _rig(app_role_url, capacity=2)
    try:
        first = await _join(rig)
        second = await _join(rig)

        left, right = await asyncio.gather(
            rig.cascade.run(rig.tenant_id),
            rig.cascade_at(NOW).run(rig.tenant_id),
            return_exceptions=True,
        )
        assert not isinstance(left, BaseException), f"the cascade must never raise: {left!r}"
        assert not isinstance(right, BaseException), f"the cascade must never raise: {right!r}"
        assert left.offered + right.offered == 1, "one pair, one tick's worth of offers"

        states = {(await _entry(rig, first)).status, (await _entry(rig, second)).status}
        assert states == {
            WaitlistEntryStatus.OFFERED.value,
            WaitlistEntryStatus.WAITING.value,
        }, "sequential, never a broadcast"
        # FIFO: the older entry is the one holding the offer.
        assert (await _entry(rig, first)).status == WaitlistEntryStatus.OFFERED.value

        messages = await _offer_messages(rig)
        assert len(messages) == 1, f"one offer, one queued SMS: {messages!r}"
        assert messages[0].waitlist_entry_id == first
        assert messages[0].booking_id is None, "an offer row's subject is an ENTRY (the XOR)"
    finally:
        await _purge(rig)
        await engine.dispose()


# --- race 5: the cascade re-entry — the epic's named hardest problem --------


async def test_an_unpaid_claim_hold_expires_and_the_next_fifo_entry_is_offered(
    app_role_url: str,
) -> None:
    """Mirrors `::test_an_orphaned_hold_is_swept_and_the_seat_really_goes_to_another_bride`.

    **The epic's named hardest problem, end to end, and the whole answer is that
    F23 writes no deposit code** (D5). A claim on a deposit-on type rides the
    shipped `create_booking` branch to `pending_payment` and the shipped
    `open_deposit` hold; the EXISTING `DepositSweeper` cancels it; and the freed
    seat is found by D2's poller on its next tick because the cascade is keyed off
    `waiting` entries, not off a cancellation hook that would have to exist in six
    places. No re-fire, no coupling, nothing subscribes to anything.

    **The claimer stays `claimed` — terminal, never back to `waiting`.** Requeuing
    her to the head of the FIFO would let one bride hold a slot indefinitely by
    claiming and not paying in a loop, which is precisely the "must not hold the
    slot forever" failure the epic names. She may rejoin (the active-unique
    predicate excludes `claimed`) or book directly.
    """
    engine, rig = await _rig(
        app_role_url, capacity=1, deposit=True, hold_seconds=EXPIRED_HOLD_SECONDS
    )
    try:
        first = await _join(rig)
        second = await _join(rig)
        assert (await rig.cascade.run(rig.tenant_id)).offered == 1
        token = await _offer_token(rig, first)

        claim = await rig.offers.claim(
            rig.tenant_id, token=token, name="רותם לוי", terms_version=1, settings=SETTINGS
        )
        assert claim.booking.status == BookingStatus.PENDING_PAYMENT.value
        assert claim.deposit_due is True
        outcome = await rig.bookings.open_deposit(rig.tenant_id, claim, return_url=RETURN_URL)
        assert outcome.redirect_url is not None, "the shipped deposit branch, unchanged"
        assert (await _entry(rig, first)).status == WaitlistEntryStatus.CLAIMED.value

        # She does not pay. The EXISTING sweeper — which knows nothing about
        # waitlists — releases the seat.
        assert await rig.sweeper.sweep(rig.tenant_id) == SweepResult(expired=1, released=1)
        assert (await _booking(rig, claim.booking.id)).status == BookingStatus.CANCELLED.value

        # The next tick finds free capacity and a `waiting` entry. No hook fired.
        assert (await rig.cascade.run(rig.tenant_id)).offered == 1
        assert (await _entry(rig, second)).status == WaitlistEntryStatus.OFFERED.value
        assert (await _entry(rig, first)).status == WaitlistEntryStatus.CLAIMED.value, (
            "terminal — a claim-and-do-not-pay loop must not be able to hold a slot"
        )
    finally:
        await _purge(rig)
        await engine.dispose()


# --- race 6: a late webhook after a waitlist claimer took the seat ----------


async def test_a_late_webhook_after_a_waitlist_claimer_took_the_seat_has_exactly_two_outcomes(
    app_role_url: str,
) -> None:
    """Mirrors `::test_a_late_delivery_racing_a_new_bride_has_exactly_two_outcomes`,
    with the second bride arriving through the waitlist instead of `/book`.

    F19's shipped shape is unchanged and that IS the assertion (D5): the waitlist
    changes the PROBABILITY of the owner-alert branch, never its mechanism. Both
    drivers take `hashtext(tenant_id)`, so there are exactly two endings —
    rebound-and-confirmed with the claim refused, or `DEPOSIT_LATE_UNRESOLVED`
    plus `PAYMENT_RECEIVED_NO_SLOT` with the claimer holding the seat.

    A third ending — both holding it, or neither, or a 500 out of the honour
    path — is what this asserts against.
    """
    engine, rig = await _rig(
        app_role_url, capacity=1, deposit=True, hold_seconds=EXPIRED_HOLD_SECONDS
    )
    try:
        hers = await _create(rig)
        held = await rig.bookings.open_deposit(rig.tenant_id, hers, return_url=RETURN_URL)
        assert held.payment_session_id is not None
        assert await rig.sweeper.sweep(rig.tenant_id) == SweepResult(expired=1, released=1)

        entry_id, token = await _armed(rig)

        settled, claimed = await asyncio.gather(
            rig.settle(session_id=held.payment_session_id, transaction_id="txn-late"),
            rig.offers.claim(
                rig.tenant_id, token=token, name="רותם לוי", terms_version=1, settings=SETTINGS
            ),
            return_exceptions=True,
        )
        assert settled is None, "the honour path must never raise"

        actions = await _actions(rig)
        honoured = AuditAction.DEPOSIT_LATE_HONOURED.value in actions
        unresolved = AuditAction.DEPOSIT_LATE_UNRESOLVED.value in actions
        assert honoured != unresolved, "the honour path resolves one way or the other, once"

        booking = await _booking(rig, hers.booking.id)
        assert (await _payment_for(rig, hers.booking.id)).status == PaymentStatus.PAID.value
        entry = await _entry(rig, entry_id)

        if isinstance(claimed, SlotUnavailableError):
            assert honoured
            assert booking.status == BookingStatus.CONFIRMED.value
            assert entry.status == WaitlistEntryStatus.OFFERED.value, "F-O2 again"
            assert MessageKind.PAYMENT_RECEIVED_NO_SLOT.value not in await _kinds(rig)
        else:
            assert isinstance(claimed, BookingClaim), f"a third outcome: {claimed!r}"
            assert unresolved
            assert booking.status == BookingStatus.CANCELLED.value
            assert entry.status == WaitlistEntryStatus.CLAIMED.value
            assert MessageKind.PAYMENT_RECEIVED_NO_SLOT.value in await _kinds(rig)
    finally:
        await _purge(rig)
        await engine.dispose()
