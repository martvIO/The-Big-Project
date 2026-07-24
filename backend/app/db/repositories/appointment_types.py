from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment_type import AppointmentType


class AppointmentTypesRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see StaffUsersRepository)."""

    async def list_active(self, session: AsyncSession, tenant_id: UUID) -> list[AppointmentType]:
        stmt = (
            select(AppointmentType)
            .where(
                AppointmentType.tenant_id == tenant_id,
                AppointmentType.deleted_at.is_(None),
            )
            .order_by(AppointmentType.sort_order, AppointmentType.created_at)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, type_id: UUID
    ) -> AppointmentType | None:
        stmt = select(AppointmentType).where(
            AppointmentType.tenant_id == tenant_id,
            AppointmentType.id == type_id,
            AppointmentType.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        name: str,
        duration_minutes: int,
        audience: str,
        deposit_required: bool,
        deposit_amount_agorot: int | None,
        sort_order: int,
    ) -> AppointmentType:
        row = AppointmentType(
            tenant_id=tenant_id,
            name=name,
            duration_minutes=duration_minutes,
            audience=audience,
            deposit_required=deposit_required,
            deposit_amount_agorot=deposit_amount_agorot,
            sort_order=sort_order,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def update_fields(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        type_id: UUID,
        *,
        name: str,
        duration_minutes: int,
        audience: str,
        deposit_required: bool,
        deposit_amount_agorot: int | None,
        sort_order: int,
    ) -> AppointmentType | None:
        row = await self.by_id(session, tenant_id, type_id)
        if row is None:
            return None
        row.name = name
        row.duration_minutes = duration_minutes
        row.audience = audience
        row.deposit_required = deposit_required
        row.deposit_amount_agorot = deposit_amount_agorot
        row.sort_order = sort_order
        await session.flush()
        await session.refresh(row)  # picks up the trigger-maintained updated_at
        return row

    async def soft_delete(self, session: AsyncSession, tenant_id: UUID, type_id: UUID) -> bool:
        stmt = (
            update(AppointmentType)
            .where(
                AppointmentType.tenant_id == tenant_id,
                AppointmentType.id == type_id,
                AppointmentType.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(AppointmentType.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
