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
from test_booking_owner_db import (
    NOW,
    _claim,
    _factory,
    _loose,
    _phone,
    _seed,
    _spent,
    _staff,
    _sweep_walk_in_bookings,  # noqa: F401
    _token,
)

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.tokens import hash_token
from app.booking.service import PhoneNotVerifiedError
from app.db.repositories.customer_sessions import CustomerSessionsRepository
from app.db.tenant import tenant_session
from app.notifications.service import NotificationService, OtpService
from app.notifications.unconfigured import UnconfiguredSmsSender
from app.portal.service import PortalNoBookingsError, PortalService, PortalThrottledError

pytestmark = pytest.mark.db

SESSIONS = CustomerSessionsRepository()


def _portal(
    factory: object,
    *,
    mint_limiter: FixedWindowRateLimiter | None = None,
    now: datetime.datetime = NOW,
    ttl_seconds: int = 30 * 24 * 3600,
) -> PortalService:
    otp = OtpService(
        factory,  # type: ignore[arg-type]
        notifications=NotificationService(factory, sender=UnconfiguredSmsSender()),  # type: ignore[arg-type]
        phone_limiter=_loose(),
        tenant_limiter=_loose(),
        verify_limiter=_loose(),
        ip_limiter=_loose(),
        clock=lambda: now,
    )
    return PortalService(
        factory,  # type: ignore[arg-type]
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
