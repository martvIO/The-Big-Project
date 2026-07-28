"""Round-trips for the two F11 repositories, as the non-owner app role. The
isolation half lives in test_notifications_isolation.py."""

import asyncio
import datetime
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
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

BACKEND_DIR = Path(__file__).resolve().parent.parent

FUTURE = datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC)
PAST = datetime.datetime(2000, 1, 1, tzinfo=datetime.UTC)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _phone() -> str:
    return f"+9725{uuid.uuid4().int % 10**8:08d}"


async def test_message_log_insert_and_status_transitions(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = MessageLogRepository()
    phone = _phone()
    try:
        async with tenant_session(factory, tenant_id) as session:
            row = await repo.insert(
                session,
                tenant_id=tenant_id,
                phone=phone,
                kind=MessageKind.OTP.value,
                body="קוד האימות שלך: ●●●●●●",
            )
            assert row.status == MessageStatus.QUEUED.value
            assert row.booking_id is None

            sent = await repo.update_status(
                session,
                tenant_id,
                row.id,
                status=MessageStatus.SENT.value,
                provider_message_id="fake-1",
            )
            assert sent is not None
            assert sent.status == MessageStatus.SENT.value
            assert sent.provider_message_id == "fake-1"
            assert sent.error is None

        async with tenant_session(factory, tenant_id) as session:
            failed = await repo.insert(
                session,
                tenant_id=tenant_id,
                phone=phone,
                kind=MessageKind.CONFIRMATION.value,
                body="אישור",
                booking_id=uuid.uuid4(),
            )
            marked = await repo.update_status(
                session,
                tenant_id,
                failed.id,
                status=MessageStatus.FAILED.value,
                error="provider refused",
            )
            assert marked is not None
            assert marked.status == MessageStatus.FAILED.value
            assert marked.error == "provider refused"

        async with tenant_session(factory, tenant_id) as session:
            listed = await repo.list_by_phone(session, tenant_id, phone=phone)
            assert [item.status for item in listed] == [
                MessageStatus.SENT.value,
                MessageStatus.FAILED.value,
            ]

            missing = await repo.update_status(
                session, tenant_id, uuid.uuid4(), status=MessageStatus.SENT.value
            )
            assert missing is None
    finally:
        await engine.dispose()


async def test_otp_lifecycle_columns(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = OtpCodesRepository()
    phone = _phone()
    try:
        async with tenant_session(factory, tenant_id) as session:
            first = await repo.insert(
                session, tenant_id=tenant_id, phone=phone, code_hash="h1", expires_at=FUTURE
            )
            assert first.attempts == 0
            assert await repo.latest_active_by_phone(session, tenant_id, phone=phone) is not None

            # Resend invalidates the predecessor: exactly one live code per phone.
            assert await repo.soft_delete_active_for_phone(session, tenant_id, phone=phone) == 1
            second = await repo.insert(
                session, tenant_id=tenant_id, phone=phone, code_hash="h2", expires_at=FUTURE
            )
            live = await repo.latest_active_by_phone(session, tenant_id, phone=phone)
            assert live is not None
            assert live.id == second.id

            assert await repo.increment_attempts(session, tenant_id, second.id) == 1
            assert await repo.increment_attempts(session, tenant_id, second.id) == 2

            consumed = await repo.mark_consumed(
                session,
                tenant_id,
                second.id,
                verification_token_hash="vh",
                verification_expires_at=FUTURE,
            )
            assert consumed is not None
            assert consumed.consumed_at is not None
            assert consumed.verification_token_hash == "vh"

            # Consumed → no longer the live code; double-consume cannot mint twice.
            assert await repo.latest_active_by_phone(session, tenant_id, phone=phone) is None
            assert (
                await repo.mark_consumed(
                    session,
                    tenant_id,
                    second.id,
                    verification_token_hash="vh2",
                    verification_expires_at=FUTURE,
                )
                is None
            )
    finally:
        await engine.dispose()


async def test_consume_verification_is_single_use_and_phone_bound(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = OtpCodesRepository()
    phone = _phone()
    now = datetime.datetime.now(datetime.UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            row = await repo.insert(
                session, tenant_id=tenant_id, phone=phone, code_hash="h", expires_at=FUTURE
            )
            await repo.mark_consumed(
                session,
                tenant_id,
                row.id,
                verification_token_hash="vh",
                verification_expires_at=FUTURE,
            )

            wrong_phone = await repo.consume_verification(
                session,
                tenant_id,
                phone=_phone(),
                verification_token_hash="vh",
                now=now,
            )
            assert wrong_phone is False

            claimed = await repo.consume_verification(
                session, tenant_id, phone=phone, verification_token_hash="vh", now=now
            )
            assert claimed is True

            again = await repo.consume_verification(
                session, tenant_id, phone=phone, verification_token_hash="vh", now=now
            )
            assert again is False
    finally:
        await engine.dispose()


async def test_consume_verification_respects_expiry(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    repo = OtpCodesRepository()
    phone = _phone()
    try:
        async with tenant_session(factory, tenant_id) as session:
            row = await repo.insert(
                session, tenant_id=tenant_id, phone=phone, code_hash="h", expires_at=FUTURE
            )
            await repo.mark_consumed(
                session,
                tenant_id,
                row.id,
                verification_token_hash="vh",
                verification_expires_at=PAST,
            )
            expired = await repo.consume_verification(
                session,
                tenant_id,
                phone=phone,
                verification_token_hash="vh",
                now=datetime.datetime.now(datetime.UTC),
            )
            assert expired is False
    finally:
        await engine.dispose()


def _sms_table_count(url: str) -> int:
    async def count() -> int:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT count(*) FROM pg_tables "
                        "WHERE tablename IN ('message_log', 'otp_codes')"
                    )
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(count())


def test_migration_0007_round_trips(migrated_db: str) -> None:
    """downgrade drops otp_codes then message_log; upgrade puts both back with
    their indexes, grants and policies. Runs as the migration owner (the app
    role cannot DROP), and destroys rows — so it owns no fixtures and shares no
    state with the tests above."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)

    assert _sms_table_count(migrated_db) == 2
    command.downgrade(cfg, "0006")
    assert _sms_table_count(migrated_db) == 0
    command.upgrade(cfg, "head")
    assert _sms_table_count(migrated_db) == 2
