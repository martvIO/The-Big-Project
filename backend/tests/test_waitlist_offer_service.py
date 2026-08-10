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
from app.waitlist.validation import WaitlistThrottledError

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
            deposit_amount_agorot=None,
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
            # KEPT, so design row D is reachable: a bride re-opening her SMS
            # link after booking reads «התור הזה כבר נקבע.», not «הקישור אינו
            # תקין». The guarded UPDATE, not the missing hash, is what stops a
            # second delivery booking twice.
            assert entry.offer_token_hash is not None
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
    """The sequential shape of race 2, and D4 step 2's answer verbatim: the
    guarded UPDATE matches nothing and the re-read says `claimed`. A 409, not a
    404 — the token still resolves, because design row D is a LOOKUP on a
    claimed entry."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            _, token = await _armed(factory, tenant_id, type_id)
            await _offers(factory).claim(tenant_id, token=token, name="רותם לוי", terms_version=1)

            with pytest.raises(OfferNotClaimableError) as caught:
                await _offers(factory).claim(
                    tenant_id, token=token, name="רותם לוי", terms_version=1
                )
            assert caught.value.state == WaitlistEntryStatus.CLAIMED.value
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_the_link_still_answers_after_the_claim_and_after_the_decline(
    app_role_url: str,
) -> None:
    """Design rows D and G. Her SMS thread is the ONLY artefact she has, and she
    re-opens it — after booking, and after declining. Both must answer the state
    («התור הזה כבר נקבע.» / «ויתרת על ההצעה»), never «הקישור אינו תקין».

    This is why `claim` and `cancel` keep `offer_token_hash`: clearing it made
    both of these a 404 and made `offer.claimedReturning` a key no server could
    ever produce.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            _, claimed_token = await _armed(factory, tenant_id, type_id)
            await _offers(factory).claim(
                tenant_id, token=claimed_token, name="רותם לוי", terms_version=1
            )
            view = await _offers(factory).lookup(tenant_id, token=claimed_token)
            assert view.status == WaitlistEntryStatus.CLAIMED.value

            _, declined_token = await _armed(factory, tenant_id, type_id)
            await _offers(factory).decline(tenant_id, token=declined_token)
            view = await _offers(factory).lookup(tenant_id, token=declined_token)
            assert view.status == WaitlistEntryStatus.CANCELLED.value
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_the_link_still_answers_after_the_cascade_has_expired_the_offer(
    app_role_url: str,
) -> None:
    """Design row E, AFTER the sweep — and expiry is the most common way an
    offer ends, so this is the ordinary path rather than an edge.

    `test_a_passed_deadline_reads_expired_before_the_cascade_sweeps_it` covers
    the <=60-second gap where the ROW still says `offered` and `_view` projects.
    Once the cascade really moves her, the projection is not involved and only
    the surviving `offer_token_hash` keeps the lookup answering: SMS at 10:00,
    deadline at 12:00, sweep at 12:00:30, she opens her thread at 12:05 and must
    read «תוקף ההצעה הזו פג» with the rebook CTA, not «הקישור אינו תקין».
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    later = NOW + datetime.timedelta(seconds=WINDOW_SECONDS)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            entry_id, token = await _armed(factory, tenant_id, type_id)
            # D7: only an offer that really reached `sent` is allowed to burn its
            # window, so the sweep lands her in `expired` rather than `waiting`.
            async with tenant_session(factory, tenant_id) as session:
                message = await SCHEDULED.latest_for_entry(
                    session, tenant_id, waitlist_entry_id=entry_id, kind=KIND
                )
                assert message is not None
                await SCHEDULED.mark(
                    session, tenant_id, message.id, status=ScheduledMessageStatus.SENT.value
                )

            assert (await _cascade(factory, later).run(tenant_id)).expired == 1
            assert (
                await _entry(factory, tenant_id, entry_id)
            ).status == WaitlistEntryStatus.EXPIRED.value

            view = await _offers(factory, later).lookup(tenant_id, token=token)
            assert view.status == WaitlistEntryStatus.EXPIRED.value
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_the_lookup_budget_never_denies_a_bride_her_claim(app_role_url: str) -> None:
    """The BLOCKER: `_meter` is the lookup's, not the claim's.

    An anonymous client can exhaust a tenant's whole anti-scrape budget with
    junk tokens — `max_attempts` lives on the LIMITER, so it is one budget for
    the boutique. If `claim` were metered too, that would deny every bride with
    a live offer until the window rolled, and the cascade would then expire her
    offer and hand her slot back to the pool. Sixty requests, one boutique, one
    hour, repeatable.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    # One event, so the first junk lookup exhausts it.
    tight = FixedWindowRateLimiter(max_attempts=1, window_seconds=3600, clock=lambda: 0.0)
    offers = WaitlistOfferService(factory, lookup_limiter=tight, clock=lambda: NOW)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            _, token = await _armed(factory, tenant_id, type_id)

            with pytest.raises(OfferNotFoundError):
                await offers.lookup(tenant_id, token="0" * 43)
            with pytest.raises(WaitlistThrottledError):
                await offers.lookup(tenant_id, token=token)

            claim = await offers.claim(tenant_id, token=token, name="רותם לוי", terms_version=1)
            assert claim.manage_token is not None
        finally:
            await _purge(factory, tenant_id)
            await engine.dispose()

    _run(check)


def test_the_lookup_budget_never_denies_a_bride_her_decline(app_role_url: str) -> None:
    """`claim`'s twin — the decline is a mutation behind the same token check."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    tight = FixedWindowRateLimiter(max_attempts=1, window_seconds=3600, clock=lambda: 0.0)
    offers = WaitlistOfferService(factory, lookup_limiter=tight, clock=lambda: NOW)

    async def check() -> None:
        try:
            type_id = await _seed(factory, tenant_id)
            _, token = await _armed(factory, tenant_id, type_id)

            with pytest.raises(OfferNotFoundError):
                await offers.lookup(tenant_id, token="0" * 43)
            with pytest.raises(WaitlistThrottledError):
                await offers.lookup(tenant_id, token=token)

            view = await offers.decline(tenant_id, token=token)
            assert view.status == WaitlistEntryStatus.CANCELLED.value
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
    sixth state and not a skip. Two writes in one transaction, because a queued
    text outliving the entry it belongs to is an offer for a seat she has said
    no to. The token hash stays: design row G is a LOOKUP on `cancelled`."""
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
            assert entry.offer_token_hash is not None
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
