import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.otp_code import OtpCode


class OtpCodesRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see StaffUsersRepository)."""

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        phone: str,
        code_hash: str,
        expires_at: datetime.datetime,
    ) -> OtpCode:
        row = OtpCode(
            tenant_id=tenant_id,
            phone=phone,
            code_hash=code_hash,
            expires_at=expires_at,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def latest_active_by_phone(
        self, session: AsyncSession, tenant_id: UUID, *, phone: str
    ) -> OtpCode | None:
        """The single live (unconsumed, not soft-deleted) code for this phone.
        send() maintains the one-live-code invariant; created_at DESC makes this
        read correct even if a race ever leaves two."""
        stmt = (
            select(OtpCode)
            .where(
                OtpCode.tenant_id == tenant_id,
                OtpCode.phone == phone,
                OtpCode.consumed_at.is_(None),
                OtpCode.deleted_at.is_(None),
            )
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def soft_delete_active_for_phone(
        self, session: AsyncSession, tenant_id: UUID, *, phone: str
    ) -> int:
        stmt = (
            update(OtpCode)
            .where(
                OtpCode.tenant_id == tenant_id,
                OtpCode.phone == phone,
                OtpCode.consumed_at.is_(None),
                OtpCode.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(OtpCode.id)
        )
        return len((await session.execute(stmt)).scalars().all())

    async def increment_attempts(self, session: AsyncSession, tenant_id: UUID, otp_id: UUID) -> int:
        """SQL-level increment (attempts = attempts + 1), returning the NEW
        value — read-modify-write would race concurrent guesses into free tries."""
        stmt = (
            update(OtpCode)
            .where(
                OtpCode.tenant_id == tenant_id,
                OtpCode.id == otp_id,
                OtpCode.deleted_at.is_(None),
            )
            .values(attempts=OtpCode.attempts + 1)
            .returning(OtpCode.attempts)
        )
        value = (await session.execute(stmt)).scalar_one_or_none()
        return int(value) if value is not None else 0

    async def mark_consumed(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        otp_id: UUID,
        *,
        verification_token_hash: str,
        verification_expires_at: datetime.datetime,
    ) -> OtpCode | None:
        """consumed_at + the minted verification in one write, guarded on
        consumed_at IS NULL so a raced double-verify cannot mint twice."""
        stmt = (
            update(OtpCode)
            .where(
                OtpCode.tenant_id == tenant_id,
                OtpCode.id == otp_id,
                OtpCode.consumed_at.is_(None),
                OtpCode.deleted_at.is_(None),
            )
            .values(
                consumed_at=func.now(),
                verification_token_hash=verification_token_hash,
                verification_expires_at=verification_expires_at,
            )
            .returning(OtpCode.id)
        )
        updated = (await session.execute(stmt)).scalar_one_or_none()
        if updated is None:
            return None
        refreshed = select(OtpCode).where(OtpCode.id == updated, OtpCode.tenant_id == tenant_id)
        return (await session.execute(refreshed)).scalar_one_or_none()

    async def consume_verification(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        phone: str,
        verification_token_hash: str,
        now: datetime.datetime,
    ) -> bool:
        """Single-use by column: the guarded UPDATE is the atomic claim. The
        phone predicate binds the token to the number it verified — a stolen
        token cannot book for a different phone."""
        stmt = (
            update(OtpCode)
            .where(
                OtpCode.tenant_id == tenant_id,
                OtpCode.phone == phone,
                OtpCode.verification_token_hash == verification_token_hash,
                OtpCode.verification_consumed_at.is_(None),
                OtpCode.verification_expires_at > now,
                OtpCode.deleted_at.is_(None),
            )
            .values(verification_consumed_at=func.now())
            .returning(OtpCode.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
