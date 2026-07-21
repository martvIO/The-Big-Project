from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory, verify_database_role
from app.tenancy.middleware import TenantResolutionMiddleware, TenantResolver
from app.tenancy.resolver import RepositoryTenantResolver


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Dev is exempt (local runs use the postgres superuser); every other
    # environment must prove its role cannot bypass RLS before serving traffic.
    if get_settings().app_env != "dev":
        await verify_database_role(get_engine())
    yield


def create_app(resolver: TenantResolver | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Boutique Platform API",
        version=settings.app_version,
        lifespan=lifespan,
    )
    if resolver is None:
        resolver = RepositoryTenantResolver(get_session_factory())
    app.add_middleware(
        TenantResolutionMiddleware,
        resolver=resolver,
        base_domain=settings.base_domain,
    )
    app.include_router(health_router)
    return app


app = create_app()
