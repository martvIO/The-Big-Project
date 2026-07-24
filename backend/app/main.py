import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes.health import router as health_router
from app.auth.dependencies import NotAuthenticatedError
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.router import RateLimitedError
from app.auth.router import router as auth_router
from app.auth.service import AuthService, InvalidCredentialsError
from app.boutique.router import router as boutique_router
from app.boutique.service import (
    BoutiqueSettingsService,
    DuplicateDateError,
    DuplicateNameError,
    NotFoundError,
    TermsThrottledError,
    TermsVersionConflictError,
)
from app.boutique.validation import BoutiqueValidationError
from app.core.config import get_settings
from app.csrf import CsrfOriginMiddleware
from app.db.session import ensure_safe_database_role, get_session_factory
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
NOT_FOUND_BODY = {"error": {"code": "NOT_FOUND", "message": "Resource not found."}}
DUPLICATE_NAME_BODY = {
    "error": {
        "code": "DUPLICATE_NAME",
        "message": "An active appointment type with this name already exists.",
    }
}
DUPLICATE_DATE_BODY = {
    "error": {
        "code": "DUPLICATE_DATE",
        "message": "An availability exception for this date already exists.",
    }
}
TERMS_CONFLICT_BODY = {
    "error": {"code": "CONFLICT", "message": "A concurrent policy update won. Try again."}
}


def _validation_summary(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors()[:3]:
        loc = ".".join(str(item) for item in err["loc"] if item != "body")
        parts.append(f"{loc}: {err['msg']}" if loc else str(err["msg"]))
    return "; ".join(parts) or "Invalid request."


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await ensure_safe_database_role()
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
    # Added after (= runs before) tenant resolution: a cross-origin forgery is
    # rejected without touching the database.
    app.add_middleware(CsrfOriginMiddleware)

    app.state.auth_service = AuthService(get_session_factory(), settings)
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=settings.login_max_attempts,
        window_seconds=settings.login_window_seconds,
        clock=time.monotonic,
    )
    app.state.boutique_service = BoutiqueSettingsService(
        get_session_factory(),
        terms_rate_limiter=FixedWindowRateLimiter(
            max_attempts=settings.terms_creation_max_per_window,
            window_seconds=settings.terms_creation_window_seconds,
            clock=time.monotonic,
        ),
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

    @app.exception_handler(RequestValidationError)
    async def _request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # House shape + 400 platform-wide — this intentionally also normalizes
        # malformed bodies on the auth routes (no default 422s anywhere).
        return JSONResponse(
            {"error": {"code": "VALIDATION_ERROR", "message": _validation_summary(exc)}},
            status_code=400,
        )

    @app.exception_handler(BoutiqueValidationError)
    async def _domain_validation(request: Request, exc: BoutiqueValidationError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "VALIDATION_ERROR", "message": str(exc)}}, status_code=400
        )

    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(NOT_FOUND_BODY, status_code=404)

    @app.exception_handler(DuplicateNameError)
    async def _duplicate_name(request: Request, exc: DuplicateNameError) -> JSONResponse:
        return JSONResponse(DUPLICATE_NAME_BODY, status_code=409)

    @app.exception_handler(DuplicateDateError)
    async def _duplicate_date(request: Request, exc: DuplicateDateError) -> JSONResponse:
        return JSONResponse(DUPLICATE_DATE_BODY, status_code=409)

    @app.exception_handler(TermsVersionConflictError)
    async def _terms_conflict(request: Request, exc: TermsVersionConflictError) -> JSONResponse:
        return JSONResponse(TERMS_CONFLICT_BODY, status_code=409)

    @app.exception_handler(TermsThrottledError)
    async def _terms_throttled(request: Request, exc: TermsThrottledError) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(boutique_router)
    return app


app = create_app()
