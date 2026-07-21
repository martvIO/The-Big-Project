from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Boutique Platform API",
        version=get_settings().app_version,
    )
    app.include_router(health_router)
    return app


app = create_app()
