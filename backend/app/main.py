import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.health import router as health_router
from app.auth.dependencies import NotAuthenticatedError
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.router import RateLimitedError
from app.auth.router import router as auth_router
from app.auth.service import AuthService, InvalidCredentialsError
from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory, verify_database_role
from app.tenancy.middleware import (
    TENANT_NOT_FOUND_BODY,
    TenantNotResolvedError,
    TenantResolutionMiddleware,
    TenantResolver,
)
from app.tenancy.resolver import RepositoryTenantResolver

INVALID_CREDENTIALS_BODY = {
    "error": {"code": "INVALID_CREDENTIALS", "message": "Incorrect email or password."}
}
TOO_MANY_ATTEMPTS_BODY = {
    "error": {"code": "TOO_MANY_ATTEMPTS", "message": "Too many attempts. Try again later."}
}
NOT_AUTHENTICATED_BODY = {
    "error": {"code": "NOT_AUTHENTICATED", "message": "Authentication required."}
}


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

    app.state.auth_service = AuthService(get_session_factory(), settings)
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=settings.login_max_attempts,
        window_seconds=settings.login_window_seconds,
        clock=time.monotonic,
    )

    @app.exception_handler(TenantNotResolvedError)
    async def _tenant_not_resolved(request: Request, exc: TenantNotResolvedError) -> JSONResponse:
        # Same body as every other resolution failure — no distinguishable 404s.
        return JSONResponse(TENANT_NOT_FOUND_BODY, status_code=404)

    @app.exception_handler(InvalidCredentialsError)
    async def _invalid_credentials(request: Request, exc: InvalidCredentialsError) -> JSONResponse:
        # One body for wrong-password AND unknown-email — no account enumeration.
        return JSONResponse(INVALID_CREDENTIALS_BODY, status_code=401)

    @app.exception_handler(RateLimitedError)
    async def _rate_limited(request: Request, exc: RateLimitedError) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    @app.exception_handler(NotAuthenticatedError)
    async def _not_authenticated(request: Request, exc: NotAuthenticatedError) -> JSONResponse:
        return JSONResponse(NOT_AUTHENTICATED_BODY, status_code=401)

    app.include_router(health_router)
    app.include_router(auth_router)
    return app


app = create_app()
