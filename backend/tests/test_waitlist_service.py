"""F22's join and manage verbs against real Postgres as the non-owner app role.

The claims here are the ones no fake can make: the token burn riding the join
transaction, the IntegrityError -> re-read collapse (one row, two identical 201
bodies) under a REAL race on the active-unique index, the check-then-spend
budget order, and the cancel's guarded-UPDATE idempotence with its audit row.

Helpers come from `test_booking_owner_db` rather than being re-typed — the seed
needs a real appointment type and the token helper mints a consumable
verification row the way the OTP service actually stores one.

⚠ db-marked: runs on CI only (no local Docker). Every test mints its own tenant
id; the container is session-scoped and nothing here truncates.
"""

import asyncio
import datetime
import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_booking_owner_db import (
    NOW,
    TARGET_DATE,
    _audit,
    _claim,
    _factory,
    _loose,
    _phone,
    _seed,
    _staff,
    _sweep_walk_in_bookings,  # noqa: F401
    _token,
)

from app.auth.rate_limit import FixedWindowRateLimiter
from app.booking.service import PhoneNotVerifiedError
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError, DomainValidationError
from app.models.audit_log import AuditLog
from app.models.constants import AuditAction, WaitlistEntryStatus
from app.models.otp_code import OtpCode
from app.models.waitlist_entry import WaitlistEntry
from app.notifications.service import NotificationService, OtpService
from app.notifications.unconfigured import UnconfiguredSmsSender
from app.waitlist.service import WaitlistService
from app.waitlist.validation import WaitlistThrottledError

pytestmark = pytest.mark.db


def _service(
    factory: async_sessionmaker[AsyncSession],
    *,
    phone_limiter: FixedWindowRateLimiter | None = None,
    tenant_limiter: FixedWindowRateLimiter | None = None,
    now: datetime.datetime = NOW,
) -> WaitlistService:
    otp = OtpService(
        factory,
        notifications=NotificationService(factory, sender=UnconfiguredSmsSender()),
        phone_limiter=_loose(),
        tenant_limiter=_loose(),
        verify_limiter=_loose(),
        ip_limiter=_loose(),
        clock=lambda: now,
    )
    return WaitlistService(
        factory,
        otp=otp,
        phone_limiter=phone_limiter or _loose(),
        tenant_limiter=tenant_limiter or _loose(),
        clock=lambda: now,
    )


async def _rows(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[WaitlistEntry]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = (
            select(WaitlistEntry)
            .where(WaitlistEntry.tenant_id == tenant_id)
            .order_by(WaitlistEntry.created_at)
        )
        return list((await session.execute(stmt)).scalars().all())


async def _live_verifications(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, phone: str
) -> int:
    """Rows the consume statement would still accept — i.e. tokens not yet
    burned. The burn is `verification_consumed_at = now()` on a guarded UPDATE
    (`OtpCodesRepository.consume_verification`), so its exact live predicate is
    re-spelled here."""
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(OtpCode).where(
            OtpCode.tenant_id == tenant_id,
            OtpCode.phone == phone,
            OtpCode.deleted_at.is_(None),
            OtpCode.verification_token_hash.is_not(None),
            OtpCode.verification_consumed_at.is_(None),
        )
        return len(list((await session.execute(stmt)).scalars().all()))


# --- the join ----------------------------------------------------------------


async def test_a_verified_join_writes_one_waiting_row_and_answers_it(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        view = await _service(factory).join(
            tenant_id,
            raw_phone=phone,
            verification_token=await _token(factory, tenant_id, phone),
            day=TARGET_DATE,
            appointment_type_id=type_id,
        )

        assert view.day == TARGET_DATE
        assert view.appointment_type_id == type_id
        assert view.status == WaitlistEntryStatus.WAITING.value

        rows = await _rows(factory, tenant_id)
        assert len(rows) == 1
        assert rows[0].phone == phone
        assert rows[0].status == WaitlistEntryStatus.WAITING.value
    finally:
        await engine.dispose()


async def test_a_duplicate_join_is_idempotent_and_still_burns_the_token(
    app_role_url: str,
) -> None:
    """D2 step 5: the IntegrityError -> re-read path. One row, the SAME 201
    body — and the second token is spent, because single-use is the token's
    contract and the burn rides the transaction the savepoint protects."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        service = _service(factory)
        first = await service.join(
            tenant_id,
            raw_phone=phone,
            verification_token=await _token(factory, tenant_id, phone),
            day=TARGET_DATE,
            appointment_type_id=type_id,
        )
        second_token = await _token(factory, tenant_id, phone)
        second = await service.join(
            tenant_id,
            raw_phone=phone,
            verification_token=second_token,
            day=TARGET_DATE,
            appointment_type_id=type_id,
        )

        assert second == first
        assert len(await _rows(factory, tenant_id)) == 1
        # Burned either way: no spendable verification row survives the
        # duplicate join.
        assert await _live_verifications(factory, tenant_id, phone) == 0
    finally:
        await engine.dispose()


async def test_two_concurrent_joins_collapse_to_one_row_and_two_identical_bodies(
    app_role_url: str,
) -> None:
    """The whole race answer (D2): the unique index serialises the pair, the
    loser's savepoint rolls back and the re-read answers the winner's row —
    F13's double-book standard applied to the entry. NullPool gives each racer
    its own connection, so this is a real two-connection race."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        service = _service(factory)
        token_a = await _token(factory, tenant_id, phone)
        token_b = await _token(factory, tenant_id, phone)

        async def join(token: str) -> Any:
            return await service.join(
                tenant_id,
                raw_phone=phone,
                verification_token=token,
                day=TARGET_DATE,
                appointment_type_id=type_id,
            )

        first, second = await asyncio.gather(join(token_a), join(token_b))

        assert first == second
        assert len(await _rows(factory, tenant_id)) == 1
    finally:
        await engine.dispose()


async def test_an_unknown_or_archived_type_is_404_and_writes_nothing(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        await _seed(factory, tenant_id)
        with pytest.raises(DomainNotFoundError):
            await _service(factory).join(
                tenant_id,
                raw_phone=phone,
                verification_token=await _token(factory, tenant_id, phone),
                day=TARGET_DATE,
                appointment_type_id=uuid.uuid4(),
            )
        assert await _rows(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_another_tenants_type_is_the_same_404(app_role_url: str) -> None:
    """The cross-tenant refusal the walker cannot drive (the join is UNWALKABLE
    for the bookings route's token reason), asserted at the service instead."""
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    phone = _phone()
    try:
        await _seed(factory, tenant_a)
        foreign_type = await _seed(factory, tenant_b)
        with pytest.raises(DomainNotFoundError):
            await _service(factory).join(
                tenant_a,
                raw_phone=phone,
                verification_token=await _token(factory, tenant_a, phone),
                day=TARGET_DATE,
                appointment_type_id=foreign_type,
            )
        assert await _rows(factory, tenant_a) == []
    finally:
        await engine.dispose()


async def test_a_day_outside_the_window_is_400_before_any_budget_or_burn(
    app_role_url: str,
) -> None:
    """Validation is step 1: the refusal costs no budget and no token — the
    verification survives to join a legal day."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        service = _service(
            factory, phone_limiter=FixedWindowRateLimiter(1, 3600, clock=lambda: 0.0)
        )
        token = await _token(factory, tenant_id, phone)
        with pytest.raises(DomainValidationError):
            await service.join(
                tenant_id,
                raw_phone=phone,
                verification_token=token,
                day=NOW.date() - datetime.timedelta(days=30),
                appointment_type_id=type_id,
            )
        # Neither spent: the SAME token and the 1-attempt budget still carry a
        # successful join.
        view = await service.join(
            tenant_id,
            raw_phone=phone,
            verification_token=token,
            day=TARGET_DATE,
            appointment_type_id=type_id,
        )
        assert view.status == WaitlistEntryStatus.WAITING.value
    finally:
        await engine.dispose()


async def test_an_unverified_caller_is_refused_and_spends_no_budget(app_role_url: str) -> None:
    """F13's metering-after-proof, applied verbatim: a garbage token gets
    PHONE_NOT_VERIFIED and the budgets stay whole — an anonymous caller cannot
    drain a boutique's join allowance with junk."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        service = _service(
            factory, phone_limiter=FixedWindowRateLimiter(1, 3600, clock=lambda: 0.0)
        )
        with pytest.raises(PhoneNotVerifiedError):
            await service.join(
                tenant_id,
                raw_phone=phone,
                verification_token="garbage",
                day=TARGET_DATE,
                appointment_type_id=type_id,
            )
        # The 1-attempt phone budget is untouched — a real join still fits.
        await service.join(
            tenant_id,
            raw_phone=phone,
            verification_token=await _token(factory, tenant_id, phone),
            day=TARGET_DATE,
            appointment_type_id=type_id,
        )
    finally:
        await engine.dispose()


async def test_the_join_budgets_trip_on_their_own_instances(app_role_url: str) -> None:
    """`.memory/limiter-max-is-per-instance`: the join budget is its own two
    instances. A spent phone budget answers 429 BEFORE the token is consumed —
    check-then-spend — so the verification survives the throttle. The
    same-instance-as-booking hazard is pinned at the wiring in
    test_waitlist_api.py, where create_app is in hand."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        service = _service(
            factory, phone_limiter=FixedWindowRateLimiter(1, 3600, clock=lambda: 0.0)
        )
        await service.join(
            tenant_id,
            raw_phone=phone,
            verification_token=await _token(factory, tenant_id, phone),
            day=TARGET_DATE,
            appointment_type_id=type_id,
        )
        token = await _token(factory, tenant_id, phone)
        with pytest.raises(WaitlistThrottledError):
            await service.join(
                tenant_id,
                raw_phone=phone,
                verification_token=token,
                day=TARGET_DATE + datetime.timedelta(days=1),
                appointment_type_id=type_id,
            )
        # Checked BEFORE the proof, so the throttle spent nothing of hers.
        assert await _live_verifications(factory, tenant_id, phone) == 1
    finally:
        await engine.dispose()


# --- the manage list and cancel (C1) -----------------------------------------


async def _join(
    factory: async_sessionmaker[AsyncSession],
    service: WaitlistService,
    tenant_id: uuid.UUID,
    type_id: uuid.UUID,
    *,
    phone: str,
    day: datetime.date = TARGET_DATE,
) -> None:
    await service.join(
        tenant_id,
        raw_phone=phone,
        verification_token=await _token(factory, tenant_id, phone),
        day=day,
        appointment_type_id=type_id,
    )


async def test_the_manage_list_is_fifo_decorated_and_day_filterable(app_role_url: str) -> None:
    """List order IS the position; `customer_name` decorates a phone the
    boutique has booked before and stays null for one it has not; the day
    filter narrows to one day."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    known_phone = _phone()
    stranger_phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        # A real booking mints the customer row the decoration reads.
        await _claim(factory, tenant_id, type_id, phone=known_phone)
        service = _service(factory)
        await _join(factory, service, tenant_id, type_id, phone=stranger_phone)
        await _join(factory, service, tenant_id, type_id, phone=known_phone)
        await _join(
            factory,
            service,
            tenant_id,
            type_id,
            phone=stranger_phone,
            day=TARGET_DATE + datetime.timedelta(days=1),
        )

        listed = await service.list_entries(tenant_id)
        assert [row.phone for row in listed.entries] == [
            stranger_phone,
            known_phone,
            stranger_phone,
        ]
        assert [row.customer_name for row in listed.entries] == [None, "נועה לוי", None]
        assert listed.entries[0].appointment_type_name == "מדידה ראשונה"
        assert listed.entries[0].status == WaitlistEntryStatus.WAITING.value

        one_day = await service.list_entries(tenant_id, day=TARGET_DATE)
        assert [row.phone for row in one_day.entries] == [stranger_phone, known_phone]
    finally:
        await engine.dispose()


async def test_cancel_is_idempotent_and_audited_without_the_phone(app_role_url: str) -> None:
    """The guarded UPDATE (D5): first tap cancels and writes ONE audit row whose
    `details` key set is exactly {entry_id, day, appointment_type_id} — a later
    phone added there is a key-set failure, not a quiet leak. The double-tap
    returns the row as-is and writes nothing."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        service = _service(factory)
        await _join(factory, service, tenant_id, type_id, phone=phone)
        entry = (await _rows(factory, tenant_id))[0]
        actor = _staff(tenant_id)

        first = await service.cancel_entry(tenant_id, entry_id=entry.id, actor=actor)
        assert first.status == WaitlistEntryStatus.CANCELLED.value

        second = await service.cancel_entry(tenant_id, entry_id=entry.id, actor=actor)
        assert second.status == WaitlistEntryStatus.CANCELLED.value

        rows = [
            row
            for row in await _audit(factory, tenant_id)
            if row.action == AuditAction.WAITLIST_ENTRY_CANCELLED.value
        ]
        assert len(rows) == 1
        assert isinstance(rows[0], AuditLog)
        assert set(rows[0].details) == {"entry_id", "day", "appointment_type_id"}
        assert rows[0].details["entry_id"] == str(entry.id)
        assert rows[0].actor_id == actor.id
        assert phone not in str(rows[0].details)
    finally:
        await engine.dispose()


async def test_cancel_of_an_unknown_or_foreign_entry_is_404(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_a)
        service = _service(factory)
        await _join(factory, service, tenant_a, type_id, phone=phone)
        entry = (await _rows(factory, tenant_a))[0]

        with pytest.raises(DomainNotFoundError):
            await service.cancel_entry(tenant_a, entry_id=uuid.uuid4(), actor=_staff(tenant_a))
        with pytest.raises(DomainNotFoundError):
            await service.cancel_entry(tenant_b, entry_id=entry.id, actor=_staff(tenant_b))
    finally:
        await engine.dispose()


async def test_a_cancelled_entry_leaves_the_manage_list(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        service = _service(factory)
        await _join(factory, service, tenant_id, type_id, phone=phone)
        entry = (await _rows(factory, tenant_id))[0]
        await service.cancel_entry(tenant_id, entry_id=entry.id, actor=_staff(tenant_id))
        listed = await service.list_entries(tenant_id)
        assert listed.entries == []
    finally:
        await engine.dispose()
