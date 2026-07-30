from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select, update
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

    async def by_ids(
        self, session: AsyncSession, tenant_id: UUID, customer_ids: Sequence[UUID]
    ) -> list[Customer]:
        """The owner day list's name column, in one statement rather than one
        per row. An empty input short-circuits: `IN ()` is a syntax error in
        Postgres and SQLAlchemy's empty-IN rewrite is a needless round trip."""
        if not customer_ids:
            return []
        stmt = select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.id.in_(customer_ids),
            Customer.deleted_at.is_(None),
        )
        return list((await session.execute(stmt)).scalars())

    async def set_phone(
        self, session: AsyncSession, tenant_id: UUID, customer_id: UUID, *, phone: str
    ) -> Customer | None:
        """The owner's phone correction (D8), as one UPDATE.

        `upsert` is NOT the writer for this: it keys on phone, so calling it
        with the corrected number would create a SECOND customer and leave the
        booking pointing at the first. `None` means no live row by that id.

        When the corrected number already belongs to another live customer of
        this tenant, `idx_customers_tenant_phone_unique` refuses and this
        raises. The service never reaches that — it pre-checks and re-points
        `bookings.customer_id` at the existing row instead, because the number
        identifies a person and that person already has a record."""
        stmt = (
            update(Customer)
            .where(
                Customer.tenant_id == tenant_id,
                Customer.id == customer_id,
                Customer.deleted_at.is_(None),
            )
            .values(phone=phone)
            .returning(Customer.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, customer_id)

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
