from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff_user import StaffUser


class StaffUsersRepository:
    """Tenant-scoped via RLS (the session's tenant context). The explicit
    tenant_id predicate is redundant defense-in-depth: it keeps the auth-critical
    reads correct even if a future RLS regression (a missing FORCE, a policy typo,
    an over-privileged role) slipped through."""

    async def by_email(
        self, session: AsyncSession, tenant_id: UUID, email: str
    ) -> StaffUser | None:
        stmt = select(StaffUser).where(
            StaffUser.tenant_id == tenant_id,
            StaffUser.email == email,
            StaffUser.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, staff_id: UUID
    ) -> StaffUser | None:
        stmt = select(StaffUser).where(
            StaffUser.tenant_id == tenant_id,
            StaffUser.id == staff_id,
            StaffUser.deleted_at.is_(None),
        )
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
