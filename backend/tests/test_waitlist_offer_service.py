"""The claim's non-race branches: what each dead token answers, and what a
decline really does.

The races themselves live in `test_waitlist_races_db.py` — this file is the
lookup projection, the four terminal states, the stale-terms refusal, the
indistinguishable 404 and the decline's two writes. Real Postgres because every
one of them is a guarded UPDATE's rowcount or an RLS-scoped read.

⚠ db-marked: first run is CI (no local Docker).
"""

import asyncio
import datetime
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.booking.service import TermsStaleError
from app.booking.validation import jerusalem_day_index
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.repositories.waitlist_entries import WaitlistEntriesRepository
from app.db.tenant import tenant_session
from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityRule
from app.models.booking import Booking
from app.models.constants import (
    AppointmentAudience,
    BookingStatus,
    ScheduledMessageKind,
    ScheduledMessageStatus,
    WaitlistEntryStatus,
)
from app.models.customer import Customer
from app.models.scheduled_message import ScheduledMessage
from app.models.terms_version import TermsVersion
from app.models.waitlist_entry import WaitlistEntry
from app.storefront.validation import BOUTIQUE_TIMEZONE
from app.waitlist.cascade import WaitlistCascade
from app.waitlist.offer_service import (
    OfferNotClaimableError,
    OfferNotFoundError,
    WaitlistOfferService,
)

pytestmark = pytest.mark.db

ENTRIES = WaitlistEntriesRepository()
SCHEDULED = ScheduledMessagesRepository()
KIND = ScheduledMessageKind.WAITLIST_OFFER.value

TARGET_DATE = datetime.date(2026, 8, 23)
WINDOW_SECONDS = 2 * 3600
NOW = datetime.datetime(2026, 8, 1, 9, 0, tzinfo=datetime.UTC)


def _at(hour: int, minute: int = 0) -> datetime.datetime:
    return datetime.datetime.combine(
        TARGET_DATE, datetime.time(hour, minute), tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)


def _loose() -> FixedWindowRateLimiter:
    """A budget nothing in this file is testing. The 429 belongs to the API
    suite, where a route can actually be called sixty-one times."""
    return FixedWindowRateLimiter(max_attempts=10_000, window_seconds=3600, clock=lambda: 0.0)


def _factory(url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _run(coro: Callable[[], Coroutine[Any, Any, None]]) -> None:
    asyncio.run(coro())


def _cascade(factory: async_sessionmaker[AsyncSession], now: datetime.datetime) -> WaitlistCascade:
    return WaitlistCascade(
        factory,
        window_seconds=WINDOW_SECONDS,
        min_lead_seconds=2 * 3600,
        quiet_start_hour=21,
        quiet_end_hour=8,
        clock=lambda: now,
    )


def _offers(
    factory: async_sessionmaker[AsyncSession], now: datetime.datetime = NOW
) -> WaitlistOfferService:
    """No gateway wired, which reads as NOT connected — so `deposit_due` is False
    and every claim below lands `confirmed`. The deposit branch is race 5's,
    where the whole hold-expiry chain is asserted end to end."""
    return WaitlistOfferService(factory, lookup_limiter=_loose(), clock=lambda: now)


async def _seed(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        await AvailabilityRulesRepository().insert(
            session,
            tenant_id=tenant_id,
            day_of_week=jerusalem_day_index(TARGET_DATE),
            open_time=datetime.time(9, 0),
            close_time=datetime.time(13, 0),
            capacity=1,
        )
        type_row = await AppointmentTypesRepository().insert(
            session,
            tenant_id=tenant_id,
            name="מדידה ראשונה",
            duration_minutes=60,
            audience=AppointmentAudience.ALL.value,
            deposit_required=False,
            deposit_amount_agorot=0,
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


async def _armed(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, type_id: uuid.UUID
) -> tuple[uuid.UUID, str]:
    """A live offer, produced by the real cascade. The raw token is read off the
    queued message — the only place it exists."""
    async with tenant_session(factory, tenant_id) as session:
        entry = await ENTRIES.insert(
            session,
            tenant_id=tenant_id,
            day=TARGET_DATE,
            appointment_type_id=type_id,
            phone=f"+9725{uuid.uuid4().int % 10**8:08d}",
        )
        entry_id = entry.id
    assert (await _cascade(factory, NOW).run(tenant_id)).offered == 1
    async with tenant_session(factory, tenant_id) as session:
        message = await SCHEDULED.latest_for_entry(
            session, tenant_id, waitlist_entry_id=entry_id, kind=KIND
        )
    assert message is not None and message.manage_token is not None
    return entry_id, message.manage_token


async def _entry(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, entry_id: uuid.UUID
) -> WaitlistEntry:
    async with tenant_session(factory, tenant_id) as session:
        row = await ENTRIES.by_id(session, tenant_id, entry_id)
    assert row is not None
    return row


async def _purge(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> None:
    async with tenant_session(factory, tenant_id) as session:
        await session.execute(
            delete(ScheduledMessage).where(ScheduledMessage.tenant_id == tenant_id)
        )
        await session.execute(delete(Booking).where(Booking.tenant_id == tenant_id))
        await session.execute(delete(WaitlistEntry).where(WaitlistEntry.tenant_id == tenant_id))
        await session.execute(delete(Customer).where(Customer.tenant_id == tenant_id))
        await session.execute(delete(TermsVersion).where(TermsVersion.tenant_id == tenant_id))
        await session.execute(
            delete(AvailabilityRule).where(AvailabilityRule.tenant_id == tenant_id)
        )
        await session.execute(delete(AppointmentType).where(AppointmentType.tenant_id == tenant_id))


def test_the_lookup_answers_the_live_offer(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            _, token = await _armed(factory, tenant_id, type_id)

            view = await _offers(factory).lookup(tenant_id, token=token)
            assert view.status == WaitlistEntryStatus.OFFERED.value
            assert view.starts_at == _at(9, 0)
            assert view.expires_at == NOW + datetime.timedelta(seconds=WINDOW_SECONDS)
            assert view.appointment_type_name == "מדידה ראשונה"
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_a_passed_deadline_reads_expired_before_the_cascade_sweeps_it(app_role_url: str) -> None:
    """The projection, and the reason it exists: the cascade sweeps on a
    60-second tick, so for up to a minute the ROW still says `offered` while the
    deadline has gone. Rendering the live offer in that minute would invite a
    claim the SQL guard then refuses."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    later = NOW + datetime.timedelta(seconds=WINDOW_SECONDS + 1)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id, token = await _armed(factory, tenant_id, type_id)

            view = await _offers(factory, later).lookup(tenant_id, token=token)
            assert view.status == WaitlistEntryStatus.EXPIRED.value
            # The ROW is untouched — this is a display projection, not a write.
            assert (
                await _entry(factory, tenant_id, entry_id)
            ).status == WaitlistEntryStatus.OFFERED.value
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_an_unknown_token_is_a_404(app_role_url: str) -> None:
    """One indistinguishable state. A prober cannot tell "never existed" from
    "already used" from "another boutique's"."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            await _seed(factory, tenant_id)
            with pytest.raises(OfferNotFoundError):
                await _offers(factory).lookup(tenant_id, token="not-a-real-token")
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_the_happy_claim_books_and_returns_a_manage_token(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id, token = await _armed(factory, tenant_id, type_id)

            claim = await _offers(factory).claim(
                tenant_id, token=token, name="רותם לוי", terms_version=1
            )
            assert claim.created is True
            assert claim.manage_token is not None
            assert claim.deposit_due is False
            assert claim.booking.status == BookingStatus.CONFIRMED.value
            assert claim.booking.starts_at == _at(9, 0)
            assert claim.booking.appointment_type_name == "מדידה ראשונה"

            entry = await _entry(factory, tenant_id, entry_id)
            assert entry.status == WaitlistEntryStatus.CLAIMED.value
            # Cleared with the transition: a second delivery of the same SMS
            # cannot even resolve the row.
            assert entry.offer_token_hash is None
            async with tenant_session(factory, tenant_id) as session:
                message = await SCHEDULED.latest_for_entry(
                    session, tenant_id, waitlist_entry_id=entry_id, kind=KIND
                )
            assert message is not None
            assert message.status == ScheduledMessageStatus.CANCELLED.value, (
                "the text about an offer she has just claimed must not still go out"
            )
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_a_claim_on_an_expired_offer_is_refused_and_books_nothing(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    later = NOW + datetime.timedelta(seconds=WINDOW_SECONDS + 1)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id, token = await _armed(factory, tenant_id, type_id)

            with pytest.raises(OfferNotClaimableError) as caught:
                await _offers(factory, later).claim(
                    tenant_id, token=token, name="רותם לוי", terms_version=1
                )
            # The row has not been swept yet, so the state it reports is the row's
            # — the DEADLINE is what refused the claim, in SQL.
            assert caught.value.state == WaitlistEntryStatus.OFFERED.value
            assert (
                await _entry(factory, tenant_id, entry_id)
            ).status == WaitlistEntryStatus.OFFERED.value
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_a_second_claim_on_a_claimed_entry_is_refused(app_role_url: str) -> None:
    """The sequential shape of race 2. The token is cleared by the first claim,
    so the second cannot even resolve the row — a 404, not a 409, and that is the
    stronger answer of the two."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            _, token = await _armed(factory, tenant_id, type_id)
            await _offers(factory).claim(tenant_id, token=token, name="רותם לוי", terms_version=1)

            with pytest.raises(OfferNotFoundError):
                await _offers(factory).claim(
                    tenant_id, token=token, name="רותם לוי", terms_version=1
                )
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_stale_terms_refuse_the_claim_and_move_no_row(app_role_url: str) -> None:
    """Accepting a superseded policy is not acceptance. The refusal comes BEFORE
    the guarded claim, so the offer is still hers and the page can re-render the
    current policy over a live offer."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id, token = await _armed(factory, tenant_id, type_id)

            with pytest.raises(TermsStaleError):
                await _offers(factory).claim(
                    tenant_id, token=token, name="רותם לוי", terms_version=99
                )
            assert (
                await _entry(factory, tenant_id, entry_id)
            ).status == WaitlistEntryStatus.OFFERED.value
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_decline_cancels_the_entry_and_its_pending_message(app_role_url: str) -> None:
    """«ויתור» takes her off the list for that day — F22's `cancelled`, not a
    sixth state and not a skip. Two writes in one transaction, because a live
    token or a queued text outliving the entry it belongs to is a claim on a seat
    she has said no to."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id, token = await _armed(factory, tenant_id, type_id)

            view = await _offers(factory).decline(tenant_id, token=token)
            assert view.status == WaitlistEntryStatus.CANCELLED.value

            entry = await _entry(factory, tenant_id, entry_id)
            assert entry.status == WaitlistEntryStatus.CANCELLED.value
            assert entry.offer_token_hash is None
            async with tenant_session(factory, tenant_id) as session:
                message = await SCHEDULED.latest_for_entry(
                    session, tenant_id, waitlist_entry_id=entry_id, kind=KIND
                )
            assert message is not None
            assert message.status == ScheduledMessageStatus.CANCELLED.value
            assert message.manage_token is None
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_a_declined_offer_cannot_be_claimed_afterwards(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            _, token = await _armed(factory, tenant_id, type_id)
            await _offers(factory).decline(tenant_id, token=token)

            with pytest.raises(OfferNotFoundError):
                await _offers(factory).claim(
                    tenant_id, token=token, name="רותם לוי", terms_version=1
                )
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_another_tenants_offer_token_is_invisible(app_role_url: str) -> None:
    """`idx_waitlist_entries_offer_token` is GLOBAL — it has to be, because the
    lookup resolves a tenant FROM the token and cannot lead with tenant_id. RLS
    inside the host-resolved session is what makes a foreign token a 404, and
    this is the assertion that claim rests on."""
    engine, factory = _factory(app_role_url)
    owner = uuid.uuid4()
    stranger = uuid.uuid4()

    async def check() -> None:
        try:
            type_id = await _seed(factory, owner)
            _, token = await _armed(factory, owner, type_id)

            with pytest.raises(OfferNotFoundError):
                await _offers(factory).lookup(stranger, token=token)
            with pytest.raises(OfferNotFoundError):
                await _offers(factory).claim(
                    stranger, token=token, name="רותם לוי", terms_version=1
                )
        finally:
            await _purge(factory, owner)
            await _purge(factory, stranger)
            await engine.dispose()

    _run(check)
