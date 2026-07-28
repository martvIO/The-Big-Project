from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer


class CustomersRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see StaffUsersRepository)."""

    async def by_phone(
        self, session: AsyncSession, tenant_id: UUID, *, phone: str
    ) -> Customer | None:
        stmt = select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.phone == phone,
            Customer.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, customer_id: UUID
    ) -> Customer | None:
        stmt = select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.id == customer_id,
            Customer.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def upsert(
        self, session: AsyncSession, tenant_id: UUID, *, phone: str, name: str
    ) -> Customer:
        """Attach-or-insert by (tenant, phone). Safe to call without its own
        lock because every caller already holds the per-tenant advisory lock for
        the slot claim; the partial unique index is the backstop either way.

        A returning customer's `name` is UPDATED rather than ignored: she typed
        it on this booking, so it is the most recent thing she calls herself.
        """
        existing = await self.by_phone(session, tenant_id, phone=phone)
        if existing is not None:
            existing.name = name
            await session.flush()
            await session.refresh(existing)
            return existing
        row = Customer(tenant_id=tenant_id, phone=phone, name=name)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row
