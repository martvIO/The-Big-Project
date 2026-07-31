"""F17 db-marked service tests. CI-only — no Docker on the dev machine.

Four of these need a GENUINELY concurrent driver (two asyncio.gathered calls),
not a sequential loop, and that is the whole reason they exist: a sequential
second-delivery test passes while D24 is broken, and a sequential double-tap
test passes while D23 is broken. `.planning/architecture.md:56` makes "explicit
concurrency/race tests (double-book, waitlist claim, duplicate webhooks)"
standing strategy.

Runs as the non-owner boutique_app role over a NullPool engine — the container
superuser bypasses RLS and the 0012 grants, and each gathered call needs its own
connection or the advisory lock proves nothing.
"""

import asyncio
import datetime
import time
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.db.repositories.gateway_credentials import GatewayCredentialsRepository
from app.db.repositories.payments import PaymentsRepository
from app.db.tenant import tenant_session
from app.models.audit_log import AuditLog
from app.models.constants import AuditAction, GatewayCredentialStatus, PaymentStatus
from app.models.payment import Payment
from app.models.tenant_gateway_credential import TenantGatewayCredential
from app.payments.base import (
    GatewayCredentials,
    GatewayCredentialsRejectedError,
    GatewayNotConnectedError,
    GatewayUnavailableError,
    GatewayWebhookInvalidError,
)
from app.payments.fake import FakeGateway, fake_webhook_body, sign_fake_webhook
from app.payments.secretbox import FakeSecretBox
from app.payments.service import (
    DepositHold,
    GatewayCredentialService,
    GatewayNotFoundError,
    GatewayThrottledError,
    PaymentService,
)
from app.payments.validation import FAKE_INVALID_MERCHANT_ID

pytestmark = pytest.mark.db

SECRET = "webhook-secret-1"
GOOD = {"merchant_id": "m-1", "api_key": "k-1", "webhook_secret": SECRET}
NOW = datetime.datetime(2026, 7, 31, 9, 0, tzinfo=datetime.UTC)
HOLD_SECONDS = 900
RETURN_URL = "https://bella.example/back"


def _clock() -> datetime.datetime:
    return NOW


def _limiter(max_attempts: int = 100) -> FixedWindowRateLimiter:
    return FixedWindowRateLimiter(
        max_attempts=max_attempts, window_seconds=3600, clock=time.monotonic
    )


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _service(
    factory: async_sessionmaker[AsyncSession],
    *,
    gateway: FakeGateway | None = None,
    connect_max: int = 100,
    validate_max: int = 100,
) -> GatewayCredentialService:
    return GatewayCredentialService(
        factory,
        gateway=gateway or FakeGateway(),
        secret_box=FakeSecretBox(),
        connect_limiter=_limiter(connect_max),
        validate_limiter=_limiter(validate_max),
        clock=_clock,
    )


async def _actions(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> list[str]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(AuditLog.action).order_by(AuditLog.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def _credential_rows(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[TenantGatewayCredential]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(TenantGatewayCredential).order_by(TenantGatewayCredential.created_at)
        return list((await session.execute(stmt)).scalars().all())


async def _payment_rows(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[Payment]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(Payment).order_by(Payment.created_at)
        return list((await session.execute(stmt)).scalars().all())


# --- GatewayCredentialService ---


async def test_connect_writes_one_credential_row_and_one_audit_row(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    try:
        service = _service(factory)
        status = await service.connect(tenant, fields=GOOD, actor_id=actor)
        assert status.connected is True
        assert status.configured is True
        assert status.status == GatewayCredentialStatus.VALID.value
        assert status.last_validated_at == NOW
        assert status.credential_fields == sorted(GOOD)

        rows = await _credential_rows(factory, tenant)
        assert len(rows) == 1
        assert rows[0].key_ref == "fake"
        assert rows[0].created_by == actor
        # The plaintext is nowhere in the row.
        for value in GOOD.values():
            assert value not in rows[0].ciphertext
        assert await _actions(factory, tenant) == [AuditAction.GATEWAY_CONNECTED.value]
    finally:
        await engine.dispose()


async def test_the_connect_audit_row_carries_field_names_never_values(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    try:
        await _service(factory).connect(tenant, fields=GOOD, actor_id=actor)
        async with tenant_session(factory, tenant) as session:
            row = (await session.execute(select(AuditLog))).scalars().one()
        rendered = str(row.details)
        for name in GOOD:
            assert name in rendered
        for value in GOOD.values():
            assert value not in rendered
        assert row.actor_id == actor
    finally:
        await engine.dispose()


async def test_a_rejected_ping_writes_nothing_at_all(app_role_url: str) -> None:
    """D4: validate and encrypt happen OUTSIDE and BEFORE the transaction, so a
    typo'd replacement cannot cost a boutique its working credentials."""
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    try:
        service = _service(factory)
        with pytest.raises(GatewayCredentialsRejectedError):
            await service.connect(
                tenant, fields={**GOOD, "merchant_id": FAKE_INVALID_MERCHANT_ID}, actor_id=actor
            )
        assert await _credential_rows(factory, tenant) == []
        assert await _actions(factory, tenant) == []
    finally:
        await engine.dispose()


async def test_a_rejected_rotation_leaves_the_working_credentials_untouched(
    app_role_url: str,
) -> None:
    """The reason the ordering above is a CORRECTNESS property and not a style
    choice: she typed a typo, she did not ask to be disconnected."""
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    try:
        service = _service(factory)
        await service.connect(tenant, fields=GOOD, actor_id=actor)
        with pytest.raises(GatewayCredentialsRejectedError):
            await service.connect(
                tenant, fields={**GOOD, "merchant_id": FAKE_INVALID_MERCHANT_ID}, actor_id=actor
            )
        status = await service.status(tenant)
        assert status.connected is True
        assert len(await _credential_rows(factory, tenant)) == 1
        # Still usable, not merely still present.
        credentials = await service.credentials_for(tenant)
        assert credentials.fields == GOOD
    finally:
        await engine.dispose()


async def test_rotation_supersedes_and_the_new_set_is_what_credentials_for_returns(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    rotated = {**GOOD, "api_key": "k-2"}
    try:
        service = _service(factory)
        await service.connect(tenant, fields=GOOD, actor_id=actor)
        await service.connect(tenant, fields=rotated, actor_id=actor)
        rows = await _credential_rows(factory, tenant)
        assert len(rows) == 2  # the superseded row IS the rotation trail (D6)
        assert sum(1 for row in rows if row.deleted_at is None) == 1
        assert (await service.credentials_for(tenant)).fields == rotated
    finally:
        await engine.dispose()


async def test_two_concurrent_connects_converge_on_one_active_row(app_role_url: str) -> None:
    """A double-submit, a client retry, two tabs. `connect` supersedes and then
    inserts, and idx_tenant_gateway_credentials_active_unique refuses a second
    ACTIVE row for one (tenant, provider) — so without the per-tenant advisory
    lock the loser's UPDATE matched nothing, its INSERT hit the index, and an
    unhandled IntegrityError surfaced as a 500 on an owner-only route.

    Two asyncio.gathered calls on separate connections, for the reason the
    open_deposit test gives: a sequential loop passes while this is broken,
    because sequentially the second call's UPDATE does find the first row."""
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    rotated = {**GOOD, "api_key": "k-2"}
    try:
        service = _service(factory)
        statuses = list(
            await asyncio.gather(
                service.connect(tenant, fields=GOOD, actor_id=actor),
                service.connect(tenant, fields=rotated, actor_id=actor),
            )
        )
        assert [status.connected for status in statuses] == [True, True]

        rows = await _credential_rows(factory, tenant)
        assert len(rows) == 2  # both wrote; the loser superseded the winner
        assert sum(1 for row in rows if row.deleted_at is None) == 1
        # A PUT supersedes rather than conflicts, so either set may be the
        # survivor — what must not happen is a crash or two live rows.
        assert (await service.credentials_for(tenant)).fields in (GOOD, rotated)
        assert await _actions(factory, tenant) == [
            AuditAction.GATEWAY_CONNECTED.value,
            AuditAction.GATEWAY_CONNECTED.value,
        ]
    finally:
        await engine.dispose()


async def test_revalidate_flips_valid_to_invalid_and_audits_with_a_real_actor(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    try:
        gateway = FakeGateway()
        service = _service(factory, gateway=gateway)
        await service.connect(tenant, fields=GOOD, actor_id=actor)

        # The stored set now starts refusing — the provider changed its mind,
        # which is exactly what "Validate now" exists to discover.
        class _Refusing(FakeGateway):
            async def validate_credentials(self, credentials: GatewayCredentials) -> None:
                raise GatewayCredentialsRejectedError("merchant m-1 is closed")

        refusing = _service(factory, gateway=_Refusing())
        status = await refusing.revalidate(tenant, actor_id=actor)
        assert status.connected is False
        assert status.status == GatewayCredentialStatus.INVALID.value

        rows = await _credential_rows(factory, tenant)
        assert rows[0].status == GatewayCredentialStatus.INVALID.value
        assert rows[0].validation_error is not None
        assert len(rows[0].validation_error) <= 200
        async with tenant_session(factory, tenant) as session:
            audit = (
                (await session.execute(select(AuditLog).order_by(AuditLog.created_at)))
                .scalars()
                .all()
            )
        assert [row.action for row in audit] == [
            AuditAction.GATEWAY_CONNECTED.value,
            AuditAction.GATEWAY_VALIDATION_FAILED.value,
        ]
        # AuditLogRepository.record defaults actor_id to None, so an omitted
        # argument is SILENT rather than a type error — an owner tap would be
        # indistinguishable from a system sweep (D26).
        assert audit[-1].actor_id == actor
    finally:
        await engine.dispose()


async def test_revalidate_records_the_recovery_too(app_role_url: str) -> None:
    """D26: the invalid -> valid flip is the transition that RE-ENABLES money
    movement. Auditing only the failure would leave the recovery — the state
    change an incident review most wants to place in time — with no row."""
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    try:
        service = _service(factory)
        await service.connect(tenant, fields=GOOD, actor_id=actor)
        status = await service.revalidate(tenant, actor_id=actor)
        assert status.status == GatewayCredentialStatus.VALID.value
        assert await _actions(factory, tenant) == [
            AuditAction.GATEWAY_CONNECTED.value,
            AuditAction.GATEWAY_VALIDATED.value,
        ]
        rows = await _credential_rows(factory, tenant)
        assert rows[0].validation_error is None  # a recovery CLEARS the old detail
    finally:
        await engine.dispose()


async def test_an_unreachable_provider_leaves_status_and_last_validated_at_untouched(
    app_role_url: str,
) -> None:
    """D26's asymmetry. A provider blip is not evidence that a merchant account
    is bad, and marking it invalid would take deposits offline for a boutique
    whose credentials are fine."""
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    try:
        await _service(factory).connect(tenant, fields=GOOD, actor_id=actor)
        before = (await _credential_rows(factory, tenant))[0]

        class _Down(FakeGateway):
            async def validate_credentials(self, credentials: GatewayCredentials) -> None:
                raise TimeoutError("connection reset")

        with pytest.raises(GatewayUnavailableError):
            await _service(factory, gateway=_Down()).revalidate(tenant, actor_id=actor)

        after = (await _credential_rows(factory, tenant))[0]
        assert after.status == GatewayCredentialStatus.VALID.value
        assert after.last_validated_at == before.last_validated_at
        assert after.validation_error is None
        assert await _actions(factory, tenant) == [AuditAction.GATEWAY_CONNECTED.value]
    finally:
        await engine.dispose()


async def test_a_decrypt_failure_is_unavailable_and_does_not_flip_status(
    app_role_url: str,
) -> None:
    """A blob we cannot open is OUR problem — a rotated key, a wrong context, an
    operator error. Marking it invalid would send an owner whose account is fine
    to her provider's support desk over our bug."""
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    repo = GatewayCredentialsRepository()
    try:
        service = _service(factory)
        await service.connect(tenant, fields=GOOD, actor_id=actor)
        row_id = (await _credential_rows(factory, tenant))[0].id
        # Corrupt the ciphertext in place — a rotated key looks like this.
        async with tenant_session(factory, tenant) as session:
            stored = await repo.active_for_provider_by_id(session, tenant, row_id)
            assert stored is not None
            stored.ciphertext = "fake-secretbox-v1:Y29ycnVwdA=="

        with pytest.raises(GatewayUnavailableError):
            await service.revalidate(tenant, actor_id=actor)
        with pytest.raises(GatewayUnavailableError):
            await service.credentials_for(tenant)
        assert (await _credential_rows(factory, tenant))[
            0
        ].status == GatewayCredentialStatus.VALID.value
    finally:
        await engine.dispose()


async def test_credentials_for_refuses_an_invalid_row(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    repo = GatewayCredentialsRepository()
    try:
        service = _service(factory)
        await service.connect(tenant, fields=GOOD, actor_id=actor)
        row_id = (await _credential_rows(factory, tenant))[0].id
        async with tenant_session(factory, tenant) as session:
            await repo.mark_status(
                session,
                tenant,
                row_id,
                status=GatewayCredentialStatus.INVALID.value,
                last_validated_at=NOW,
                validation_error="refused",
            )
        with pytest.raises(GatewayNotConnectedError):
            await service.credentials_for(tenant)
        # …but the VERIFICATION path still resolves (D20).
        assert (await service.verification_credentials_for(tenant)).fields == GOOD
    finally:
        await engine.dispose()


async def test_disconnect_audits_and_then_404s(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    try:
        service = _service(factory)
        await service.connect(tenant, fields=GOOD, actor_id=actor)
        status = await service.disconnect(tenant, actor_id=actor)
        assert status.connected is False
        assert status.status is None
        assert await _actions(factory, tenant) == [
            AuditAction.GATEWAY_CONNECTED.value,
            AuditAction.GATEWAY_DISCONNECTED.value,
        ]
        with pytest.raises(GatewayNotFoundError):
            await service.disconnect(tenant, actor_id=actor)
    finally:
        await engine.dispose()


async def test_the_connect_budget_trips(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant, actor = uuid.uuid4(), uuid.uuid4()
    try:
        service = _service(factory, connect_max=2)
        await service.connect(tenant, fields=GOOD, actor_id=actor)
        await service.connect(tenant, fields=GOOD, actor_id=actor)
        with pytest.raises(GatewayThrottledError):
            await service.connect(tenant, fields=GOOD, actor_id=actor)
    finally:
        await engine.dispose()


# --- PaymentService ---


async def _connected(
    factory: async_sessionmaker[AsyncSession], tenant: uuid.UUID, gateway: FakeGateway
) -> tuple[GatewayCredentialService, PaymentService]:
    credentials = _service(factory, gateway=gateway)
    await credentials.connect(tenant, fields=GOOD, actor_id=uuid.uuid4())
    payments = PaymentService(factory, gateway=gateway, credentials=credentials, clock=_clock)
    return credentials, payments


async def test_open_deposit_inserts_one_pending_row(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    try:
        _, payments = await _connected(factory, tenant, gateway)
        hold = await payments.open_deposit(
            tenant,
            booking_id=booking,
            amount_agorot=15000,
            hold_seconds=HOLD_SECONDS,
            return_url=RETURN_URL,
        )
        assert hold.created is True
        assert hold.redirect_url is not None
        assert hold.payment.status == PaymentStatus.PENDING.value
        assert hold.payment.hold_expires_at == NOW + datetime.timedelta(seconds=HOLD_SECONDS)
        assert len(gateway.sessions) == 1
        # The port carries no knowledge of the booking domain: `reference` is an
        # opaque caller-supplied string.
        assert gateway.sessions[0].reference == str(booking)
    finally:
        await engine.dispose()


async def test_open_deposit_refuses_when_the_gateway_is_disconnected(app_role_url: str) -> None:
    """D23 step 1: a disconnected credential 409s BEFORE anything is minted at
    the provider."""
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    try:
        credentials, payments = await _connected(factory, tenant, gateway)
        await credentials.disconnect(tenant, actor_id=uuid.uuid4())
        with pytest.raises(GatewayNotConnectedError):
            await payments.open_deposit(
                tenant,
                booking_id=booking,
                amount_agorot=15000,
                hold_seconds=HOLD_SECONDS,
                return_url=RETURN_URL,
            )
        assert gateway.sessions == []
        assert await _payment_rows(factory, tenant) == []
    finally:
        await engine.dispose()


async def test_two_concurrent_open_deposits_yield_one_row_and_one_session(
    app_role_url: str,
) -> None:
    """D23, and the second assertion is the one that matters. A row count of 1
    alone passes even if the gateway was called before the converge read — and
    that extra call leaves a LIVE, PAYABLE session at the provider with no row
    behind it, so a charge on it matches nothing in settle_from_webhook.

    Two asyncio.gathered calls on separate connections. A sequential loop passes
    while the ordering is broken, which is the whole reason this is not one."""
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    try:
        _, payments = await _connected(factory, tenant, gateway)

        async def _open() -> DepositHold:
            return await payments.open_deposit(
                tenant,
                booking_id=booking,
                amount_agorot=15000,
                hold_seconds=HOLD_SECONDS,
                return_url=RETURN_URL,
            )

        holds = list(await asyncio.gather(_open(), _open()))
        assert sum(1 for hold in holds if hold.created) == 1
        assert len({hold.payment.id for hold in holds}) == 1
        assert len(await _payment_rows(factory, tenant)) == 1
        # THE orphaned-session assertion.
        assert len(gateway.sessions) == 1
    finally:
        await engine.dispose()


def _signed(
    *,
    session_id: str,
    transaction_id: str,
    amount_agorot: int,
    secret: str = SECRET,
    paid: bool = True,
) -> tuple[bytes, str]:
    body = fake_webhook_body(
        provider_session_id=session_id,
        provider_transaction_id=transaction_id,
        amount_agorot=amount_agorot,
        paid=paid,
    )
    return body, sign_fake_webhook(webhook_secret=secret, body=body)


async def test_settle_marks_the_row_paid_once(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    try:
        _, payments = await _connected(factory, tenant, gateway)
        hold = await payments.open_deposit(
            tenant,
            booking_id=booking,
            amount_agorot=15000,
            hold_seconds=HOLD_SECONDS,
            return_url=RETURN_URL,
        )
        session_id = hold.payment.provider_session_id
        assert session_id is not None
        body, signature = _signed(
            session_id=session_id, transaction_id="txn-1", amount_agorot=15000
        )
        settlement = await payments.settle_from_webhook(tenant, body=body, signature=signature)
        assert settlement.newly_settled is True
        assert settlement.payment.status == PaymentStatus.PAID.value
        assert settlement.payment.paid_at == NOW

        # A sequential redelivery writes nothing (the cheap path).
        again = await payments.settle_from_webhook(tenant, body=body, signature=signature)
        assert again.newly_settled is False
    finally:
        await engine.dispose()


async def test_a_declined_webhook_leaves_the_hold_pending_AND_leaves_evidence(
    app_role_url: str,
) -> None:
    """A signed `paid=false` delivery is the decline/failure notification every
    real PSP posts to the same URL as its successes. Settling it would confirm a
    booking and fire F16's SMS against a charge that never happened.

    Asserted the way the forged-signature test is — that the AUDIT ROW EXISTS
    after the call, not merely that `newly_settled` came back False. The branch
    returns rather than raises (a decline is a legitimate notification; raising
    would make the provider retry it forever), so its evidence has to commit on
    the way out of the transaction it was written in."""
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    try:
        _, payments = await _connected(factory, tenant, gateway)
        hold = await payments.open_deposit(
            tenant,
            booking_id=booking,
            amount_agorot=15000,
            hold_seconds=HOLD_SECONDS,
            return_url=RETURN_URL,
        )
        session_id = hold.payment.provider_session_id
        assert session_id is not None
        body, signature = _signed(
            session_id=session_id, transaction_id="txn-1", amount_agorot=15000, paid=False
        )

        settlement = await payments.settle_from_webhook(tenant, body=body, signature=signature)
        assert settlement.newly_settled is False

        assert AuditAction.GATEWAY_PAYMENT_DECLINED.value in await _actions(factory, tenant)
        row = (await _payment_rows(factory, tenant))[0]
        # The hold stays PENDING so F19's expiry sweeper frees the seat on its own
        # clock — a decline is not a payment, and the bride must not be confirmed.
        assert row.status == PaymentStatus.PENDING.value
        assert row.paid_at is None
        # Nothing was charged, so nothing carries a transaction id.
        assert row.provider_transaction_id is None
        assert row.error is not None and "declined" in row.error
    finally:
        await engine.dispose()


async def test_a_decline_then_a_success_on_the_same_session_still_settles(
    app_role_url: str,
) -> None:
    """The retried card. The decline must not have poisoned the hold: it left
    `status` at 'pending' precisely so the next delivery can still settle it."""
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    try:
        _, payments = await _connected(factory, tenant, gateway)
        hold = await payments.open_deposit(
            tenant,
            booking_id=booking,
            amount_agorot=15000,
            hold_seconds=HOLD_SECONDS,
            return_url=RETURN_URL,
        )
        session_id = hold.payment.provider_session_id
        assert session_id is not None

        declined, declined_signature = _signed(
            session_id=session_id, transaction_id="txn-1", amount_agorot=15000, paid=False
        )
        await payments.settle_from_webhook(tenant, body=declined, signature=declined_signature)

        body, signature = _signed(
            session_id=session_id, transaction_id="txn-2", amount_agorot=15000
        )
        settlement = await payments.settle_from_webhook(tenant, body=body, signature=signature)
        assert settlement.newly_settled is True
        assert settlement.payment.status == PaymentStatus.PAID.value
        assert settlement.payment.provider_transaction_id == "txn-2"
    finally:
        await engine.dispose()


async def test_two_concurrent_redeliveries_produce_exactly_one_transition(
    app_role_url: str,
) -> None:
    """D24. The guard is evaluated by the DATABASE under the row lock, not by
    us, so exactly one of two concurrent deliveries can move pending -> paid.

    A sequential second-delivery test passes while D24 is broken — both
    deliveries would see no settled row, both would match the same row by
    session id, and 0012's unique index has no INSERT to refuse on this path.
    That is why this one gathers."""
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    try:
        _, payments = await _connected(factory, tenant, gateway)
        hold = await payments.open_deposit(
            tenant,
            booking_id=booking,
            amount_agorot=15000,
            hold_seconds=HOLD_SECONDS,
            return_url=RETURN_URL,
        )
        session_id = hold.payment.provider_session_id
        assert session_id is not None
        body, signature = _signed(
            session_id=session_id, transaction_id="txn-1", amount_agorot=15000
        )

        first, second = await asyncio.gather(
            payments.settle_from_webhook(tenant, body=body, signature=signature),
            payments.settle_from_webhook(tenant, body=body, signature=signature),
        )
        assert sorted([first.newly_settled, second.newly_settled]) == [False, True]
        # The loser lost a RACE with the same txn id — not a second charge. The
        # comparison that makes a distinct txn evidence must not fire here.
        assert AuditAction.GATEWAY_DUPLICATE_TRANSACTION.value not in await _actions(
            factory, tenant
        )
        rows = await _payment_rows(factory, tenant)
        assert len(rows) == 1
        assert rows[0].status == PaymentStatus.PAID.value
        assert rows[0].paid_at == NOW
        assert rows[0].provider_transaction_id == "txn-1"
    finally:
        await engine.dispose()


async def test_a_second_distinct_transaction_against_a_paid_row_leaves_evidence(
    app_role_url: str,
) -> None:
    """Two DIFFERENT provider transactions for one hosted-checkout session is a
    double charge — a retried card that both times succeeded, a provider
    duplicate capture. The transition is already right (the row is paid, once,
    by the first txn) but silence is not: the second charge exists only in the
    provider's ledger and nothing here would ever show it.

    A redelivery carries the SAME txn id and is genuinely nothing; the
    comparison is the whole difference between the two."""
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    try:
        _, payments = await _connected(factory, tenant, gateway)
        hold = await payments.open_deposit(
            tenant,
            booking_id=booking,
            amount_agorot=15000,
            hold_seconds=HOLD_SECONDS,
            return_url=RETURN_URL,
        )
        session_id = hold.payment.provider_session_id
        assert session_id is not None

        body, signature = _signed(
            session_id=session_id, transaction_id="txn-1", amount_agorot=15000
        )
        assert (
            await payments.settle_from_webhook(tenant, body=body, signature=signature)
        ).newly_settled is True

        second, second_signature = _signed(
            session_id=session_id, transaction_id="txn-2", amount_agorot=15000
        )
        settlement = await payments.settle_from_webhook(
            tenant, body=second, signature=second_signature
        )
        assert settlement.newly_settled is False

        assert AuditAction.GATEWAY_DUPLICATE_TRANSACTION.value in await _actions(factory, tenant)
        row = (await _payment_rows(factory, tenant))[0]
        assert row.status == PaymentStatus.PAID.value
        # The FIRST transaction is what this row records; the second is evidence,
        # not a re-settlement.
        assert row.provider_transaction_id == "txn-1"
        assert row.paid_at == NOW
        assert row.error is not None and "txn-2" in row.error
    finally:
        await engine.dispose()


async def test_a_webhook_settles_after_a_disconnect(app_role_url: str) -> None:
    """THE money-loss regression (D20). It fails outright against a
    settle_from_webhook that resolves through credentials_for: the charge
    succeeds at the provider, the webhook can never be verified, the row stays
    pending, F19's sweeper frees the seat, and the webhook secret sits in a
    soft-deleted row no code path reads."""
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    try:
        credentials, payments = await _connected(factory, tenant, gateway)
        hold = await payments.open_deposit(
            tenant,
            booking_id=booking,
            amount_agorot=15000,
            hold_seconds=HOLD_SECONDS,
            return_url=RETURN_URL,
        )
        session_id = hold.payment.provider_session_id
        assert session_id is not None

        await credentials.disconnect(tenant, actor_id=uuid.uuid4())

        body, signature = _signed(
            session_id=session_id, transaction_id="txn-1", amount_agorot=15000
        )
        settlement = await payments.settle_from_webhook(tenant, body=body, signature=signature)
        assert settlement.newly_settled is True
        assert settlement.payment.status == PaymentStatus.PAID.value
    finally:
        await engine.dispose()


async def test_a_webhook_settles_after_the_credential_flips_to_invalid(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    repo = GatewayCredentialsRepository()
    try:
        _, payments = await _connected(factory, tenant, gateway)
        hold = await payments.open_deposit(
            tenant,
            booking_id=booking,
            amount_agorot=15000,
            hold_seconds=HOLD_SECONDS,
            return_url=RETURN_URL,
        )
        session_id = hold.payment.provider_session_id
        assert session_id is not None

        async with tenant_session(factory, tenant) as session:
            row = await repo.active_for_provider(session, tenant, provider="fake")
            assert row is not None
            await repo.mark_status(
                session,
                tenant,
                row.id,
                status=GatewayCredentialStatus.INVALID.value,
                last_validated_at=NOW,
                validation_error="refused",
            )

        body, signature = _signed(
            session_id=session_id, transaction_id="txn-1", amount_agorot=15000
        )
        settlement = await payments.settle_from_webhook(tenant, body=body, signature=signature)
        assert settlement.newly_settled is True
    finally:
        await engine.dispose()


async def test_a_forged_signature_raises_AND_leaves_an_audit_row(app_role_url: str) -> None:
    """Asserted as .memory/patterns/commit-before-raise-in-tenant-session.md
    demands: that the ROW EXISTS after the failure, not merely that the
    exception raised. tenant_session is session.begin(), so a raise inside the
    block would roll this evidence away and a forgery would leave no trace."""
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    try:
        _, payments = await _connected(factory, tenant, gateway)
        hold = await payments.open_deposit(
            tenant,
            booking_id=booking,
            amount_agorot=15000,
            hold_seconds=HOLD_SECONDS,
            return_url=RETURN_URL,
        )
        session_id = hold.payment.provider_session_id
        assert session_id is not None
        body, _ = _signed(session_id=session_id, transaction_id="txn-1", amount_agorot=15000)

        with pytest.raises(GatewayWebhookInvalidError):
            await payments.settle_from_webhook(tenant, body=body, signature="deadbeef")

        assert AuditAction.GATEWAY_WEBHOOK_REJECTED.value in await _actions(factory, tenant)
        assert (await _payment_rows(factory, tenant))[0].status == PaymentStatus.PENDING.value
    finally:
        await engine.dispose()


async def test_an_amount_mismatch_raises_AND_leaves_evidence(app_role_url: str) -> None:
    """D14: a webhook is attacker-reachable input even behind a valid signature,
    if the signing secret ever leaks. The evidence commits, the exception then
    raises, and `status` deliberately stays 'pending' — inventing a 'failed'
    transition here would pre-empt F19's sweeper policy."""
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    try:
        _, payments = await _connected(factory, tenant, gateway)
        hold = await payments.open_deposit(
            tenant,
            booking_id=booking,
            amount_agorot=15000,
            hold_seconds=HOLD_SECONDS,
            return_url=RETURN_URL,
        )
        session_id = hold.payment.provider_session_id
        assert session_id is not None
        body, signature = _signed(session_id=session_id, transaction_id="txn-1", amount_agorot=1)

        with pytest.raises(GatewayWebhookInvalidError):
            await payments.settle_from_webhook(tenant, body=body, signature=signature)

        assert AuditAction.GATEWAY_AMOUNT_MISMATCH.value in await _actions(factory, tenant)
        row = (await _payment_rows(factory, tenant))[0]
        assert row.status == PaymentStatus.PENDING.value
        assert row.error is not None and "amount mismatch" in row.error
        assert row.paid_at is None
    finally:
        await engine.dispose()


async def test_a_late_settlement_is_honoured_as_evidence_and_distinguishable(
    app_role_url: str,
) -> None:
    """Gate 1 Q4 rules a verified webhook against an expired hold HONOURED, and
    F19 owns the rebind-or-alert. F17's obligation is only that the event is
    durable and distinguishable: GATEWAY_LATE_SETTLEMENT + payments.error +
    newly_settled=False."""
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    gateway = FakeGateway()
    repo = PaymentsRepository()
    try:
        _, payments = await _connected(factory, tenant, gateway)
        hold = await payments.open_deposit(
            tenant,
            booking_id=booking,
            amount_agorot=15000,
            hold_seconds=HOLD_SECONDS,
            return_url=RETURN_URL,
        )
        session_id = hold.payment.provider_session_id
        assert session_id is not None

        # F19's sweeper got there first.
        async with tenant_session(factory, tenant) as session:
            row = await repo.by_id(session, tenant, hold.payment.id)
            assert row is not None
            row.status = PaymentStatus.EXPIRED.value

        body, signature = _signed(
            session_id=session_id, transaction_id="txn-1", amount_agorot=15000
        )
        settlement = await payments.settle_from_webhook(tenant, body=body, signature=signature)
        assert settlement.newly_settled is False
        assert AuditAction.GATEWAY_LATE_SETTLEMENT.value in await _actions(factory, tenant)
        stored = (await _payment_rows(factory, tenant))[0]
        assert stored.error is not None and "late settlement" in stored.error
    finally:
        await engine.dispose()


async def test_settle_refuses_a_webhook_for_an_unknown_session(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant = uuid.uuid4()
    gateway = FakeGateway()
    try:
        _, payments = await _connected(factory, tenant, gateway)
        body, signature = _signed(
            session_id="fake-does-not-exist", transaction_id="txn-1", amount_agorot=15000
        )
        with pytest.raises(GatewayWebhookInvalidError):
            await payments.settle_from_webhook(tenant, body=body, signature=signature)
    finally:
        await engine.dispose()
