import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shift_template import ShiftTemplate


class ShiftTemplatesRepository:
    """Tenant-scoped via RLS; the explicit `tenant_id` predicate is redundant
    defense-in-depth (house pattern — see `DressesRepository`).

    Every statement filters `deleted_at IS NULL`. A removed template must vanish
    from every reader — the staffer's week, the owner's editor and the roster
    readiness list — and D4's invalidation is what handles the answers that were
    given against it.
    """

    async def list_live(self, session: AsyncSession, tenant_id: UUID) -> list[ShiftTemplate]:
        """`(day_of_week, sort_order, starts_at_time)` — the order the console
        renders and the order the seed writes.

        `starts_at_time` is the third key rather than a tiebreak nobody reads:
        overlapping same-day templates are legal (D2), so two rows can share a
        `sort_order` the owner never touched, and without it the morning and the
        afternoon would swap places between page loads.
        """
        stmt = (
            select(ShiftTemplate)
            .where(ShiftTemplate.tenant_id == tenant_id, ShiftTemplate.deleted_at.is_(None))
            .order_by(
                ShiftTemplate.day_of_week,
                ShiftTemplate.sort_order,
                ShiftTemplate.starts_at_time,
            )
        )
        return list((await session.execute(stmt)).scalars().all())

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, template_id: UUID
    ) -> ShiftTemplate | None:
        stmt = select(ShiftTemplate).where(
            ShiftTemplate.tenant_id == tenant_id,
            ShiftTemplate.id == template_id,
            ShiftTemplate.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def counts(self, session: AsyncSession, tenant_id: UUID) -> dict[int, int]:
        """Live templates per weekday. The cap check needs both the per-day count
        and the total, and one grouped aggregate answers both — the total is
        `sum(...)`, which is cheaper and cannot disagree with its own parts."""
        stmt = (
            select(ShiftTemplate.day_of_week, func.count())
            .where(ShiftTemplate.tenant_id == tenant_id, ShiftTemplate.deleted_at.is_(None))
            .group_by(ShiftTemplate.day_of_week)
        )
        return {int(day): int(count) for day, count in (await session.execute(stmt)).all()}

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        day_of_week: int,
        label: str,
        starts_at_time: datetime.time,
        ends_at_time: datetime.time,
        sort_order: int = 0,
    ) -> ShiftTemplate:
        row = ShiftTemplate(
            tenant_id=tenant_id,
            day_of_week=day_of_week,
            label=label,
            starts_at_time=starts_at_time,
            ends_at_time=ends_at_time,
            sort_order=sort_order,
        )
        session.add(row)
        await session.flush()
        return row

    async def replace(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        template_id: UUID,
        *,
        day_of_week: int,
        label: str,
        starts_at_time: datetime.time,
        ends_at_time: datetime.time,
        sort_order: int,
    ) -> ShiftTemplate | None:
        """A FULL REPLACE of all five editable fields (D2), never a partial patch
        — `UpdateAppointmentTypeRequest`'s shipped rule, so an omitted key can
        never silently clear a value. `None` means no live row by that id for
        this tenant: unknown, already deleted, or another tenant's, one
        indistinguishable miss as everywhere else."""
        stmt = (
            update(ShiftTemplate)
            .where(
                ShiftTemplate.tenant_id == tenant_id,
                ShiftTemplate.id == template_id,
                ShiftTemplate.deleted_at.is_(None),
            )
            .values(
                day_of_week=day_of_week,
                label=label,
                starts_at_time=starts_at_time,
                ends_at_time=ends_at_time,
                sort_order=sort_order,
            )
            .returning(ShiftTemplate.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, template_id)

    async def soft_delete(self, session: AsyncSession, tenant_id: UUID, template_id: UUID) -> bool:
        stmt = (
            update(ShiftTemplate)
            .where(
                ShiftTemplate.tenant_id == tenant_id,
                ShiftTemplate.id == template_id,
                ShiftTemplate.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(ShiftTemplate.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
