"""F17's rows in the permanent cross-tenant isolation suite: a boutique's
merchant credentials and its money rows must be invisible to every other tenant.

Runs as the non-owner boutique_app role over a NullPool engine: the container
superuser bypasses RLS unconditionally, which would make every assertion here
vacuously pass. (test_notifications_isolation.py shape.)

Note what this file deliberately does NOT re-prove:
test_tenant_isolation.py::test_every_tenant_id_table_has_forced_rls picks both
new tables up with no edit at all, because 0012 calls enable_tenant_rls on both.
That mechanical sweep is what keeps FUTURE tables honest; these tests are about
the two specific read paths F19 will build on — including
`newest_for_provider`, which ignores deleted_at and status and therefore has to
be shown NOT to be a hole in the tenant boundary as well.
"""

import datetime
import uuid

import pytest
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

PROVIDER = "fake"  # deliberately IDENTICAL for both tenants: provider is not a key
NOW = datetime.datetime(2026, 7, 31, 9, 0, tzinfo=datetime.UTC)
LATER = NOW + datetime.timedelta(minutes=15)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_credentials_are_invisible_across_tenants(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    repo = GatewayCredentialsRepository()
    try:
        async with tenant_session(factory, tenant_a) as session:
            row = await repo.insert(
                session,
                tenant_id=tenant_a,
                provider=PROVIDER,
                ciphertext="A only",
                key_ref="fake",
                last_validated_at=NOW,
                created_by=uuid.uuid4(),
            )
            row_id = row.id

        async with tenant_session(factory, tenant_b) as session:
            assert await repo.active_for_provider(session, tenant_b, provider=PROVIDER) is None
            # The non-partial D20 index must NOT be a way around the boundary.
            assert await repo.newest_for_provider(session, tenant_b, provider=PROVIDER) is None
            # A cross-tenant status write is a silent miss, not a hit.
            assert (
                await repo.mark_status(
                    session,
                    tenant_b,
                    row_id,
                    status=GatewayCredentialStatus.INVALID.value,
                    last_validated_at=LATER,
                    validation_error="forged",
                )
                is None
            )
            # …and neither is a cross-tenant disconnect.
            assert (
                await repo.soft_delete_active(session, tenant_b, provider=PROVIDER, now=LATER) == 0
            )

        async with tenant_session(factory, tenant_a) as session:
            own = await repo.active_for_provider(session, tenant_a, provider=PROVIDER)
            assert own is not None
            assert own.ciphertext == "A only"
            assert own.status == GatewayCredentialStatus.VALID.value  # B's write didn't land
            assert own.validation_error is None
    finally:
        await engine.dispose()


async def test_payments_are_invisible_and_unsettleable_across_tenants(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    booking = uuid.uuid4()  # identical id under both tenants: booking_id is not a key either
    repo = PaymentsRepository()
    try:
        async with tenant_session(factory, tenant_a) as session:
            row = await repo.insert(
                session,
                tenant_id=tenant_a,
                booking_id=booking,
                provider=PROVIDER,
                amount_agorot=15000,
                provider_session_id="fake-1",
                hold_expires_at=LATER,
            )
            payment_id = row.id

        async with tenant_session(factory, tenant_b) as session:
            assert (
                await repo.live_pending_for_booking(session, tenant_b, booking_id=booking) is None
            )
            assert (
                await repo.by_provider_session_id(
                    session, tenant_b, provider=PROVIDER, session_id="fake-1"
                )
                is None
            )
            # A forged webhook under the wrong tenant cannot take A's money.
            assert (
                await repo.settle(
                    session,
                    tenant_b,
                    payment_id,
                    provider_transaction_id="stolen",
                    paid_at=LATER,
                )
                is None
            )
            assert await repo.record_error(session, tenant_b, payment_id, error="forged") is None

        async with tenant_session(factory, tenant_a) as session:
            own = await repo.by_id(session, tenant_a, payment_id)
            assert own is not None
            assert own.status == PaymentStatus.PENDING.value  # B's settle didn't land
            assert own.provider_transaction_id is None
            assert own.error is None
    finally:
        await engine.dispose()
