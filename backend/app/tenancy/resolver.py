from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.repositories.tenants import TenantsRepository
from app.tenancy.middleware import TenantContext


class RepositoryTenantResolver:
    """Direct indexed lookup per request (idx_tenants_slug_unique). Caching is
    deliberately deferred to E5 — premature at pilot traffic."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._repository = TenantsRepository(session_factory)

    async def __call__(self, slug: str) -> TenantContext | None:
        tenant = await self._repository.by_slug(slug)
        if tenant is None:
            return None
        return TenantContext(id=tenant.id, slug=tenant.slug, settings=tenant.settings)
