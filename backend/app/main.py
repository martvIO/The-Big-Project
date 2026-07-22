from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.db.session import get_engine, verify_database_role


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Dev is exempt (local runs use the postgres superuser); every other
    # environment must prove its role cannot bypass RLS before serving traffic.
    if get_settings().app_env != "dev":
        await verify_database_role(get_engine())
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Boutique Platform API",
        version=get_settings().app_version,
        lifespan=lifespan,
    )
    app.include_router(health_router)
    return app


app = create_app()
