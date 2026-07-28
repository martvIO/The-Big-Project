from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message_log import MessageLog


class MessageLogRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see StaffUsersRepository)."""

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        phone: str,
        kind: str,
        body: str,
        booking_id: UUID | None = None,
    ) -> MessageLog:
        row = MessageLog(
            tenant_id=tenant_id,
            phone=phone,
            kind=kind,
            body=body,
            booking_id=booking_id,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def update_status(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        log_id: UUID,
        *,
        status: str,
        provider_message_id: str | None = None,
        error: str | None = None,
    ) -> MessageLog | None:
        row = await self._by_id(session, tenant_id, log_id)
        if row is None:
            return None
        row.status = status
        row.provider_message_id = provider_message_id
        row.error = error
        await session.flush()
        await session.refresh(row)
        return row

    async def list_by_phone(
        self, session: AsyncSession, tenant_id: UUID, *, phone: str
    ) -> list[MessageLog]:
        stmt = (
            select(MessageLog)
            .where(
                MessageLog.tenant_id == tenant_id,
                MessageLog.phone == phone,
                MessageLog.deleted_at.is_(None),
            )
            .order_by(MessageLog.created_at)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def _by_id(
        self, session: AsyncSession, tenant_id: UUID, log_id: UUID
    ) -> MessageLog | None:
        stmt = select(MessageLog).where(
            MessageLog.tenant_id == tenant_id,
            MessageLog.id == log_id,
            MessageLog.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()
