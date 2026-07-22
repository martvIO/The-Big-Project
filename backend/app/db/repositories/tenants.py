from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.constants import TenantStatus
from app.models.tenant import Tenant


class TenantsRepository:
    """Platform-scoped repository — the tenants table has no tenant_id and no RLS.
    updated_at is maintained by the DB trigger, never set here.

    Requires a session factory built with expire_on_commit=False (as
    get_session_factory() provides): methods return ORM entities after their
    transaction commits, which would otherwise raise DetachedInstanceError."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def insert(self, slug: str, name: str) -> Tenant:
        async with self._session_factory() as session, session.begin():
            tenant = Tenant(slug=slug, name=name)
            session.add(tenant)
            await session.flush()
            await session.refresh(tenant)
            return tenant

    async def by_id(self, tenant_id: UUID) -> Tenant | None:
        async with self._session_factory() as session:
            stmt = select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
            return (await session.execute(stmt)).scalar_one_or_none()

    async def by_slug(self, slug: str) -> Tenant | None:
        """Active tenants only — suspension and soft-deletion both make a slug
        unresolvable (Feature 4 serves 404 for those)."""
        async with self._session_factory() as session:
            stmt = select(Tenant).where(
                Tenant.slug == slug,
                Tenant.deleted_at.is_(None),
                Tenant.status == TenantStatus.ACTIVE,
            )
            return (await session.execute(stmt)).scalar_one_or_none()

    async def suspend(self, tenant_id: UUID) -> bool:
        async with self._session_factory() as session, session.begin():
            stmt = (
                update(Tenant)
                .where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
                .values(status=TenantStatus.SUSPENDED)
                .returning(Tenant.id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def soft_delete(self, tenant_id: UUID) -> bool:
        async with self._session_factory() as session, session.begin():
            stmt = (
                update(Tenant)
                .where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
                .values(deleted_at=func.now())
                .returning(Tenant.id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def list_active(self) -> list[Tenant]:
        async with self._session_factory() as session:
            stmt = (
                select(Tenant)
                .where(Tenant.deleted_at.is_(None), Tenant.status == TenantStatus.ACTIVE)
                .order_by(Tenant.created_at)
            )
            return list((await session.execute(stmt)).scalars().all())
