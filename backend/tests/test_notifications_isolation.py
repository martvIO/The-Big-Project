"""F11's rows in the permanent cross-tenant isolation suite: message_log (the
Spam-Law evidence trail — one tenant's send history must be invisible to every
other) and otp_codes (a foreign tenant must never read, consume, or verify
against another tenant's codes).

Runs as the non-owner boutique_app role over a NullPool engine: the container
superuser bypasses RLS unconditionally, which would make every assertion here
vacuously pass.
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

from app.db.repositories.message_log import MessageLogRepository
from app.db.repositories.otp_codes import OtpCodesRepository
from app.db.tenant import tenant_session
from app.models.constants import MessageKind, MessageStatus

pytestmark = pytest.mark.db

FUTURE = datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC)
PHONE = "+972501234567"  # deliberately IDENTICAL for both tenants: phone is not a key


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_message_log_is_invisible_across_tenants(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    repo = MessageLogRepository()
    try:
        async with tenant_session(factory, tenant_a) as session:
            row = await repo.insert(
                session,
                tenant_id=tenant_a,
                phone=PHONE,
                kind=MessageKind.OTP.value,
                body="A only",
            )
        async with tenant_session(factory, tenant_b) as session:
            assert await repo.list_by_phone(session, tenant_b, phone=PHONE) == []
            # A cross-tenant status write must be a silent miss, not a hit.
            assert (
                await repo.update_status(session, tenant_b, row.id, status=MessageStatus.SENT.value)
                is None
            )
        async with tenant_session(factory, tenant_a) as session:
            own = await repo.list_by_phone(session, tenant_a, phone=PHONE)
            assert [item.body for item in own] == ["A only"]
            assert own[0].status == MessageStatus.QUEUED.value  # B's write didn't land
    finally:
        await engine.dispose()


async def test_otp_codes_cannot_be_read_or_consumed_across_tenants(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    repo = OtpCodesRepository()
    now = datetime.datetime.now(datetime.UTC)
    try:
        async with tenant_session(factory, tenant_a) as session:
            row = await repo.insert(
                session, tenant_id=tenant_a, phone=PHONE, code_hash="h", expires_at=FUTURE
            )
            await repo.mark_consumed(
                session,
                tenant_a,
                row.id,
                verification_token_hash="vh",
                verification_expires_at=FUTURE,
            )

        async with tenant_session(factory, tenant_b) as session:
            assert await repo.latest_active_by_phone(session, tenant_b, phone=PHONE) is None
            assert await repo.increment_attempts(session, tenant_b, row.id) == 0
            assert await repo.soft_delete_active_for_phone(session, tenant_b, phone=PHONE) == 0
            # The verified token from tenant A is worthless under tenant B.
            assert (
                await repo.consume_verification(
                    session, tenant_b, phone=PHONE, verification_token_hash="vh", now=now
                )
                is False
            )

        async with tenant_session(factory, tenant_a) as session:
            # …and A's own verification survived B's probes untouched.
            assert (
                await repo.consume_verification(
                    session, tenant_a, phone=PHONE, verification_token_hash="vh", now=now
                )
                is True
            )
    finally:
        await engine.dispose()
