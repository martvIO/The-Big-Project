from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff_user import StaffUser


class StaffUsersRepository:
    """Tenant-scoped: RLS restricts every query to the session's tenant context,
    so no explicit tenant_id filter is needed (nor sufficient) for isolation."""

    async def by_email(self, session: AsyncSession, email: str) -> StaffUser | None:
        stmt = select(StaffUser).where(StaffUser.email == email, StaffUser.deleted_at.is_(None))
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_id(self, session: AsyncSession, staff_id: UUID) -> StaffUser | None:
        stmt = select(StaffUser).where(StaffUser.id == staff_id, StaffUser.deleted_at.is_(None))
        return (await session.execute(stmt)).scalar_one_or_none()

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        email: str,
        password_hash: str,
        display_name: str,
    ) -> StaffUser:
        staff = StaffUser(
            tenant_id=tenant_id,
            email=email,
            password_hash=password_hash,
            display_name=display_name,
        )
        session.add(staff)
        await session.flush()
        await session.refresh(staff)
        return staff
