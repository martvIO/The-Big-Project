import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import AvailabilityException, AvailabilityRule


class AvailabilityRulesRepository:
    async def list_active(self, session: AsyncSession, tenant_id: UUID) -> list[AvailabilityRule]:
        stmt = (
            select(AvailabilityRule)
            .where(
                AvailabilityRule.tenant_id == tenant_id,
                AvailabilityRule.deleted_at.is_(None),
            )
            .order_by(AvailabilityRule.day_of_week, AvailabilityRule.open_time)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        day_of_week: int,
        open_time: datetime.time,
        close_time: datetime.time,
        capacity: int,
    ) -> AvailabilityRule:
        row = AvailabilityRule(
            tenant_id=tenant_id,
            day_of_week=day_of_week,
            open_time=open_time,
            close_time=close_time,
            capacity=capacity,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def soft_delete_all(self, session: AsyncSession, tenant_id: UUID) -> int:
        """Retires the whole active weekly set — the first half of the atomic
        replace (the caller holds the per-tenant advisory lock)."""
        stmt = (
            update(AvailabilityRule)
            .where(
                AvailabilityRule.tenant_id == tenant_id,
                AvailabilityRule.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(AvailabilityRule.id)
        )
        return len((await session.execute(stmt)).scalars().all())


class AvailabilityExceptionsRepository:
    async def list_active(
        self, session: AsyncSession, tenant_id: UUID
    ) -> list[AvailabilityException]:
        stmt = (
            select(AvailabilityException)
            .where(
                AvailabilityException.tenant_id == tenant_id,
                AvailabilityException.deleted_at.is_(None),
            )
            .order_by(AvailabilityException.date)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        date: datetime.date,
        open_time: datetime.time | None,
        close_time: datetime.time | None,
        note: str | None,
    ) -> AvailabilityException:
        row = AvailabilityException(
            tenant_id=tenant_id,
            date=date,
            open_time=open_time,
            close_time=close_time,
            note=note,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def soft_delete(self, session: AsyncSession, tenant_id: UUID, exception_id: UUID) -> bool:
        stmt = (
            update(AvailabilityException)
            .where(
                AvailabilityException.tenant_id == tenant_id,
                AvailabilityException.id == exception_id,
                AvailabilityException.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(AvailabilityException.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
