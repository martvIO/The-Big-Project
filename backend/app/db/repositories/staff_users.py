from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.constants import StaffRole
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

    async def list_live(self, session: AsyncSession, tenant_id: UUID) -> list[StaffUser]:
        """created_at ASC, so the founding owner is first and the console's rows
        do not shuffle between page loads."""
        stmt = (
            select(StaffUser)
            .where(StaffUser.tenant_id == tenant_id, StaffUser.deleted_at.is_(None))
            .order_by(StaffUser.created_at)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def count_live_owners(self, session: AsyncSession, tenant_id: UUID) -> int:
        """The last-owner invariant's read. It is only correct under the caller's
        advisory lock — see app/auth/staff.py: a count taken outside the lock is a
        count another transaction has already invalidated.

        No index supports it and F51 adds none (spec D1): RLS narrows the scan to
        one tenant's single-digit staff rows.
        """
        stmt = select(func.count()).where(
            StaffUser.tenant_id == tenant_id,
            StaffUser.role == StaffRole.OWNER.value,
            StaffUser.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one()

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        email: str,
        password_hash: str,
        display_name: str,
        # A Python default rather than a required kwarg: making it required would
        # mean editing ProvisioningService.provision — a shipped file on the
        # tenant-creation path — to say what staff_users' server_default already
        # says. The one consequence is that the INSERT now emits role='owner'
        # explicitly instead of letting the default fill it.
        role: str = StaffRole.OWNER.value,
    ) -> StaffUser:
        staff = StaffUser(
            tenant_id=tenant_id,
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            role=role,
        )
        session.add(staff)
        await session.flush()
        await session.refresh(staff)
        return staff

    async def update(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        staff_id: UUID,
        *,
        display_name: str | None = None,
        role: str | None = None,
        password_hash: str | None = None,
    ) -> StaffUser | None:
        """Every argument omitted is a legal no-op, not an error: the service's
        no-op PATCH path calls straight through here, and an empty `.values()`
        would be a SQLAlchemy error rather than a 200.

        updated_at is never assigned — the DB trigger owns it, and `refresh` is
        what picks the trigger's value back up (the dresses/platform rule).
        """
        row = await self.by_id(session, tenant_id, staff_id)
        if row is None:
            return None
        if display_name is None and role is None and password_hash is None:
            return row
        if display_name is not None:
            row.display_name = display_name
        if role is not None:
            row.role = role
        if password_hash is not None:
            row.password_hash = password_hash
        await session.flush()
        await session.refresh(row)
        return row

    async def soft_delete(self, session: AsyncSession, tenant_id: UUID, staff_id: UUID) -> bool:
        """Returns whether a live row was hit — not the row, because DELETE
        answers OkResponse and the service already holds the row from its
        post-lock read. deleted_at IS NULL in the predicate is what makes a second
        call answer False rather than re-stamping the timestamp."""
        stmt = (
            update(StaffUser)
            .where(
                StaffUser.tenant_id == tenant_id,
                StaffUser.id == staff_id,
                StaffUser.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(StaffUser.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
