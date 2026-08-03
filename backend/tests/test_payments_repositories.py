"""F17 db-marked repository tests (test_notifications_repositories.py shape).

CI-only — this machine has no Docker, so these debut on the first CI run.

Runs as the non-owner boutique_app role: 0012 REVOKEs DELETE from app_user, and
the container superuser would bypass that (and RLS) unconditionally.
"""

import datetime
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.repositories.gateway_credentials import GatewayCredentialsRepository
from app.db.repositories.payments import PaymentsRepository
from app.db.tenant import tenant_session
from app.models.constants import GatewayCredentialStatus, PaymentStatus

pytestmark = pytest.mark.db

PROVIDER = "fake"
NOW = datetime.datetime(2026, 7, 31, 9, 0, tzinfo=datetime.UTC)
LATER = NOW + datetime.timedelta(minutes=15)
# F19: the delivery that arrives after the hold has already been swept.
TOO_LATE = LATER + datetime.timedelta(minutes=5)
# Only ever compared, and only by `by_booking_ids`: EARLIER < NOW pins which of
# two payments on one booking is "the latest" without leaning on now() ties.
EARLIER = NOW - datetime.timedelta(hours=1)
REDIRECT = "https://pay.example/checkout/fake-1"


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


# --- tenant_gateway_credentials ---


async def test_insert_then_read_the_active_row(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant = uuid.uuid4()
    repo = GatewayCredentialsRepository()
    try:
        async with tenant_session(factory, tenant) as session:
            row = await repo.insert(
                session,
                tenant_id=tenant,
                provider=PROVIDER,
                ciphertext="fake-secretbox-v1:abc",
                key_ref="fake",
                last_validated_at=NOW,
                created_by=uuid.uuid4(),
            )
            assert row.status == GatewayCredentialStatus.VALID.value
        async with tenant_session(factory, tenant) as session:
            active = await repo.active_for_provider(session, tenant, provider=PROVIDER)
            assert active is not None
            assert active.id == row.id
            assert active.ciphertext == "fake-secretbox-v1:abc"
    finally:
        await engine.dispose()


async def test_a_second_active_row_is_refused_by_the_unique_index(app_role_url: str) -> None:
    """idx_tenant_gateway_credentials_active_unique makes "one active set per
    (tenant, provider)" structural (D6). This is what converges a double
    connect onto one row instead of leaving two both claiming to be current."""
    engine, factory = _factory(app_role_url)
    tenant = uuid.uuid4()
    repo = GatewayCredentialsRepository()
    try:
        async with tenant_session(factory, tenant) as session:
            await repo.insert(
                session,
                tenant_id=tenant,
                provider=PROVIDER,
                ciphertext="a",
                key_ref="fake",
                last_validated_at=NOW,
                created_by=uuid.uuid4(),
            )
        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant) as session:
                await repo.insert(
                    session,
                    tenant_id=tenant,
                    provider=PROVIDER,
                    ciphertext="b",
                    key_ref="fake",
                    last_validated_at=NOW,
                    created_by=uuid.uuid4(),
                )
    finally:
        await engine.dispose()


async def test_rotation_soft_deletes_then_inserts_and_keeps_the_trail(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant = uuid.uuid4()
    repo = GatewayCredentialsRepository()
    try:
        async with tenant_session(factory, tenant) as session:
            first = await repo.insert(
                session,
                tenant_id=tenant,
                provider=PROVIDER,
                ciphertext="old",
                key_ref="fake",
                last_validated_at=NOW,
                created_by=uuid.uuid4(),
            )
            first_id = first.id
        async with tenant_session(factory, tenant) as session:
            assert await repo.soft_delete_active(session, tenant, provider=PROVIDER, now=NOW) == 1
            second = await repo.insert(
                session,
                tenant_id=tenant,
                provider=PROVIDER,
                ciphertext="new",
                key_ref="fake",
                last_validated_at=LATER,
                created_by=uuid.uuid4(),
            )
            second_id = second.id
        async with tenant_session(factory, tenant) as session:
            active = await repo.active_for_provider(session, tenant, provider=PROVIDER)
            assert active is not None and active.id == second_id
            # The superseded row survives — that IS the rotation trail D6 exists
            # for, and its ciphertext is what D20's verification path still needs.
            newest = await repo.newest_for_provider(session, tenant, provider=PROVIDER)
            assert newest is not None and newest.id == second_id
            assert first_id != second_id
    finally:
        await engine.dispose()


async def test_newest_for_provider_still_resolves_after_a_disconnect(app_role_url: str) -> None:
    """D20, and it is the money-loss regression at the repository level: after a
    disconnect the USE path must go dark and the VERIFICATION path must not."""
    engine, factory = _factory(app_role_url)
    tenant = uuid.uuid4()
    repo = GatewayCredentialsRepository()
    try:
        async with tenant_session(factory, tenant) as session:
            row = await repo.insert(
                session,
                tenant_id=tenant,
                provider=PROVIDER,
                ciphertext="live",
                key_ref="fake",
                last_validated_at=NOW,
                created_by=uuid.uuid4(),
            )
            row_id = row.id
        async with tenant_session(factory, tenant) as session:
            await repo.soft_delete_active(session, tenant, provider=PROVIDER, now=NOW)
        async with tenant_session(factory, tenant) as session:
            assert await repo.active_for_provider(session, tenant, provider=PROVIDER) is None
            newest = await repo.newest_for_provider(session, tenant, provider=PROVIDER)
            assert newest is not None
            assert newest.id == row_id
            assert newest.ciphertext == "live"
    finally:
        await engine.dispose()


async def test_newest_for_provider_ignores_an_invalid_status_too(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant = uuid.uuid4()
    repo = GatewayCredentialsRepository()
    try:
        async with tenant_session(factory, tenant) as session:
            row = await repo.insert(
                session,
                tenant_id=tenant,
                provider=PROVIDER,
                ciphertext="live",
                key_ref="fake",
                last_validated_at=NOW,
                created_by=uuid.uuid4(),
            )
            row_id = row.id
        async with tenant_session(factory, tenant) as session:
            marked = await repo.mark_status(
                session,
                tenant,
                row_id,
                status=GatewayCredentialStatus.INVALID.value,
                last_validated_at=LATER,
                validation_error="ValueError: refused",
            )
            assert marked is not None
            assert marked.status == GatewayCredentialStatus.INVALID.value
            assert marked.validation_error == "ValueError: refused"
        async with tenant_session(factory, tenant) as session:
            newest = await repo.newest_for_provider(session, tenant, provider=PROVIDER)
            assert newest is not None and newest.id == row_id
    finally:
        await engine.dispose()


async def test_soft_delete_reports_zero_when_nothing_is_connected(app_role_url: str) -> None:
    # What lets `disconnect` answer 404 rather than a silent 200.
    engine, factory = _factory(app_role_url)
    tenant = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant) as session:
            deleted = await GatewayCredentialsRepository().soft_delete_active(
                session, tenant, provider=PROVIDER, now=NOW
            )
        assert deleted == 0
    finally:
        await engine.dispose()


# --- payments ---


async def _hold(
    factory: async_sessionmaker[AsyncSession],
    tenant: uuid.UUID,
    booking: uuid.UUID,
    *,
    session_id: str = "fake-1",
    amount_agorot: int = 15000,
    redirect_url: str = REDIRECT,
) -> uuid.UUID:
    async with tenant_session(factory, tenant) as session:
        row = await PaymentsRepository().insert(
            session,
            tenant_id=tenant,
            booking_id=booking,
            provider=PROVIDER,
            amount_agorot=amount_agorot,
            provider_session_id=session_id,
            redirect_url=redirect_url,
            hold_expires_at=LATER,
        )
        return row.id


async def _expire(
    factory: async_sessionmaker[AsyncSession], tenant: uuid.UUID, payment_id: uuid.UUID
) -> None:
    """What the D6 sweeper's claim-1 UPDATE does to the row, stated directly:
    the sweeper itself is a service, and this file tests repositories."""
    async with tenant_session(factory, tenant) as session:
        row = await PaymentsRepository().by_id(session, tenant, payment_id)
        assert row is not None
        row.status = PaymentStatus.EXPIRED.value
        row.redirect_url = None
        await session.flush()


async def test_insert_a_hold_and_read_it_back(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    repo = PaymentsRepository()
    try:
        payment_id = await _hold(factory, tenant, booking)
        async with tenant_session(factory, tenant) as session:
            live = await repo.live_pending_for_booking(session, tenant, booking_id=booking)
            assert live is not None
            assert live.id == payment_id
            assert live.status == PaymentStatus.PENDING.value
            assert live.amount_agorot == 15000
            # F19 D8: the hosted-page URL is STORED, not re-minted, so the
            # converge path has something to hand a double-tap back.
            assert live.redirect_url == REDIRECT
            by_session = await repo.by_provider_session_id(
                session, tenant, provider=PROVIDER, session_id="fake-1"
            )
            assert by_session is not None and by_session.id == payment_id
    finally:
        await engine.dispose()


async def test_a_second_live_hold_for_one_booking_is_refused(app_role_url: str) -> None:
    """idx_payments_booking_pending_unique — D23's backstop for a writer that
    skipped the advisory lock."""
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    try:
        await _hold(factory, tenant, booking)
        with pytest.raises(IntegrityError):
            await _hold(factory, tenant, booking, session_id="fake-2")
    finally:
        await engine.dispose()


async def test_settle_fires_once_and_then_reports_a_miss(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    repo = PaymentsRepository()
    try:
        payment_id = await _hold(factory, tenant, booking)
        async with tenant_session(factory, tenant) as session:
            settled = await repo.settle(
                session, tenant, payment_id, provider_transaction_id="txn-1", paid_at=LATER
            )
            assert settled is not None
            assert settled.status == PaymentStatus.PAID.value
            assert settled.paid_at == LATER
            assert settled.provider_transaction_id == "txn-1"
            # F19 D8: blanked on every exit from `pending`. A live checkout URL
            # outliving its hold is a link that takes real money for a seat the
            # boutique has already given away.
            assert settled.redirect_url is None
        async with tenant_session(factory, tenant) as session:
            # The guard is `status='pending'`, so a redelivery cannot fire twice.
            assert (
                await repo.settle(
                    session, tenant, payment_id, provider_transaction_id="txn-1", paid_at=LATER
                )
                is None
            )
    finally:
        await engine.dispose()


async def test_a_replayed_transaction_id_is_refused_by_the_unique_index(app_role_url: str) -> None:
    """idx_payments_provider_txn_unique. The BACKSTOP, not the mechanism (D24) —
    proven here on the only path that can reach it, a second row carrying an
    already-settled txn id."""
    engine, factory = _factory(app_role_url)
    tenant = uuid.uuid4()
    repo = PaymentsRepository()
    try:
        first = await _hold(factory, tenant, uuid.uuid4(), session_id="fake-1")
        second = await _hold(factory, tenant, uuid.uuid4(), session_id="fake-2")
        async with tenant_session(factory, tenant) as session:
            await repo.settle(
                session, tenant, first, provider_transaction_id="txn-1", paid_at=LATER
            )
        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant) as session:
                await repo.settle(
                    session, tenant, second, provider_transaction_id="txn-1", paid_at=LATER
                )
    finally:
        await engine.dispose()


async def test_by_provider_transaction_id_finds_a_settled_row(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    repo = PaymentsRepository()
    try:
        payment_id = await _hold(factory, tenant, booking)
        async with tenant_session(factory, tenant) as session:
            await repo.settle(
                session, tenant, payment_id, provider_transaction_id="txn-9", paid_at=LATER
            )
        async with tenant_session(factory, tenant) as session:
            found = await repo.by_provider_transaction_id(
                session, tenant, provider=PROVIDER, transaction_id="txn-9"
            )
            assert found is not None and found.id == payment_id
            assert (
                await repo.by_provider_transaction_id(
                    session, tenant, provider=PROVIDER, transaction_id="txn-absent"
                )
                is None
            )
    finally:
        await engine.dispose()


async def test_record_error_leaves_the_status_alone(app_role_url: str) -> None:
    # D14: an amount mismatch persists evidence and does NOT invent a 'failed'
    # transition — that is F19's sweeper policy to decide.
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    repo = PaymentsRepository()
    try:
        payment_id = await _hold(factory, tenant, booking)
        async with tenant_session(factory, tenant) as session:
            updated = await repo.record_error(session, tenant, payment_id, error="amount mismatch")
            assert updated is not None
            assert updated.error == "amount mismatch"
            assert updated.status == PaymentStatus.PENDING.value
    finally:
        await engine.dispose()


# --- F19: the late settlement, and the owner's batch read ---


async def test_settle_late_honours_an_expired_hold(app_role_url: str) -> None:
    """F17's Gate 1 Q4 — "HONOUR IT ... the deposit is marked paid" — had no
    writer: `settle` is guarded `WHERE status='pending'` and so matches nothing
    against an expired row. That is an implementation gap, not a reopened
    ruling, and this is the statement that closes it.

    Writing `provider_transaction_id` also RE-ARMS `by_provider_transaction_id`,
    so every subsequent redelivery of the same transaction short-circuits."""
    engine, factory = _factory(app_role_url)
    tenant, booking = uuid.uuid4(), uuid.uuid4()
    repo = PaymentsRepository()
    try:
        payment_id = await _hold(factory, tenant, booking)
        await _expire(factory, tenant, payment_id)

        async with tenant_session(factory, tenant) as session:
            honoured = await repo.settle_late(
                session, tenant, payment_id, provider_transaction_id="txn-late", paid_at=TOO_LATE
            )
            assert honoured is not None
            assert honoured.status == PaymentStatus.PAID.value
            assert honoured.paid_at == TOO_LATE
            assert honoured.provider_transaction_id == "txn-late"
            assert honoured.redirect_url is None
            # No `late_paid` status: `paid_at > hold_expires_at` already carries
            # the distinction structurally, on the row itself.
            assert honoured.hold_expires_at is not None
            assert honoured.paid_at > honoured.hold_expires_at

        async with tenant_session(factory, tenant) as session:
            found = await repo.by_provider_transaction_id(
                session, tenant, provider=PROVIDER, transaction_id="txn-late"
            )
            assert found is not None and found.id == payment_id
            # The guard is `status='expired'`, so a redelivery cannot fire twice.
            assert (
                await repo.settle_late(
                    session,
                    tenant,
                    payment_id,
                    provider_transaction_id="txn-late",
                    paid_at=TOO_LATE,
                )
                is None
            )
    finally:
        await engine.dispose()


async def test_settle_late_refuses_a_row_that_is_not_expired(app_role_url: str) -> None:
    """The two writers do not overlap: `settle` owns `pending`, `settle_late`
    owns `expired`, and neither can reach the other's rows."""
    engine, factory = _factory(app_role_url)
    tenant = uuid.uuid4()
    repo = PaymentsRepository()
    try:
        pending = await _hold(factory, tenant, uuid.uuid4(), session_id="fake-1")
        paid = await _hold(factory, tenant, uuid.uuid4(), session_id="fake-2")
        async with tenant_session(factory, tenant) as session:
            await repo.settle(session, tenant, paid, provider_transaction_id="txn-1", paid_at=LATER)

        async with tenant_session(factory, tenant) as session:
            assert (
                await repo.settle_late(
                    session, tenant, pending, provider_transaction_id="txn-2", paid_at=TOO_LATE
                )
                is None
            )
            assert (
                await repo.settle_late(
                    session, tenant, paid, provider_transaction_id="txn-3", paid_at=TOO_LATE
                )
                is None
            )
            still_pending = await repo.by_id(session, tenant, pending)
            assert still_pending is not None
            assert still_pending.status == PaymentStatus.PENDING.value
            assert still_pending.provider_transaction_id is None
    finally:
        await engine.dispose()


async def test_by_booking_ids_returns_the_latest_payment_per_booking(app_role_url: str) -> None:
    """D18's batch read for the owner console. A booking can carry an expired
    hold AND a later paid one — the console renders one badge, so the newest row
    is the one that answers "where is her money"."""
    engine, factory = _factory(app_role_url)
    tenant = uuid.uuid4()
    twice, once, unknown = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    repo = PaymentsRepository()
    try:
        # The empty case issues no query at all — `list_day` on a quiet morning
        # must not pay for a round trip.
        async with tenant_session(factory, tenant) as session:
            assert await repo.by_booking_ids(session, tenant, []) == {}

        abandoned = await _hold(factory, tenant, twice, session_id="fake-1")
        await _expire(factory, tenant, abandoned)
        retried = await _hold(factory, tenant, twice, session_id="fake-2")
        solo = await _hold(factory, tenant, once, session_id="fake-3")

        async with tenant_session(factory, tenant) as session:
            # Both rows land in one transaction's now() otherwise, which would
            # make "latest" a coin flip rather than an assertion.
            older = await repo.by_id(session, tenant, abandoned)
            assert older is not None
            older.created_at = EARLIER
            newer = await repo.by_id(session, tenant, retried)
            assert newer is not None
            newer.created_at = NOW
            await session.flush()

        async with tenant_session(factory, tenant) as session:
            found = await repo.by_booking_ids(session, tenant, [twice, once, unknown])
            assert set(found) == {twice, once}
            assert found[twice].id == retried
            assert found[twice].status == PaymentStatus.PENDING.value
            assert found[once].id == solo
    finally:
        await engine.dispose()
