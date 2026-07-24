import logging
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
    TermsThrottledError,
    TermsVersionConflictError,
)
from app.catalog.router import router as catalog_router
from app.catalog.service import (
    CatalogService,
    DuplicateSizeError,
    MediaLimitReachedError,
    MediaMismatchError,
    MediaNotUploadedError,
    MediaOrderMismatchError,
    MediaPresignThrottledError,
)
from app.catalog.validation import PENDING_MEDIA_TTL_SECONDS
from app.core.config import Settings, get_settings
from app.csrf import CsrfOriginMiddleware
from app.db.session import ensure_safe_database_role, get_session_factory
from app.errors import DomainNotFoundError, DomainValidationError
from app.storage.base import (
    MediaNotConfiguredError,
    MediaStorage,
    MediaStorageUnavailableError,
)
from app.storage.s3 import S3MediaStorage
from app.storage.unconfigured import UnconfiguredMediaStorage
from app.tenancy.middleware import (
    TENANT_NOT_FOUND_BODY,
    TenantNotResolvedError,
    TenantResolutionMiddleware,
    TenantResolver,
)
from app.tenancy.resolver import RepositoryTenantResolver

logger = logging.getLogger("app")

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
DUPLICATE_SIZE_BODY = {
    "error": {"code": "DUPLICATE_SIZE", "message": "This dress already has that size."}
}
MEDIA_LIMIT_REACHED_BODY = {
    "error": {
        "code": "MEDIA_LIMIT_REACHED",
        "message": "This dress already has the maximum number of photos.",
    }
}
MEDIA_NOT_UPLOADED_BODY = {
    "error": {"code": "MEDIA_NOT_UPLOADED", "message": "The photo was not uploaded. Try again."}
}
MEDIA_MISMATCH_BODY = {
    "error": {
        "code": "MEDIA_MISMATCH",
        "message": "The uploaded file is not the image it claimed to be.",
    }
}
MEDIA_ORDER_MISMATCH_BODY = {
    "error": {
        "code": "MEDIA_ORDER_MISMATCH",
        "message": "The photo order is out of date. Reload and try again.",
    }
}
# Fixed bodies: no bucket, region, endpoint, IAM identifier or AWS-supplied text
# may ever reach a user-facing message.
MEDIA_NOT_CONFIGURED_BODY = {
    "error": {"code": "MEDIA_NOT_CONFIGURED", "message": "Image uploads are not available."}
}
MEDIA_STORAGE_UNAVAILABLE_BODY = {
    "error": {
        "code": "MEDIA_STORAGE_UNAVAILABLE",
        "message": "Image storage is temporarily unavailable.",
    }
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


def _build_media_storage(settings: Settings) -> MediaStorage:
    """A missing bucket is never a boot failure — no bucket is a supported
    deployment. But Settings.model_config is extra="ignore", so a typo'd
    MEDIA_BUKCET degrades silently: this one INFO line (and /health's `media`
    field) is what makes the degradation observable."""
    if not settings.media_bucket:
        logger.info(
            "media storage NOT configured — upload endpoints will answer 503 MEDIA_NOT_CONFIGURED"
        )
        return UnconfiguredMediaStorage()
    logger.info(
        "media storage configured: bucket=%s region=%s endpoint=%s",
        settings.media_bucket,
        settings.media_region,
        settings.media_endpoint_url,
    )
    # __init__ does no network I/O and no credential resolution, which is what
    # keeps create_app() safe to call in the fast suite.
    return S3MediaStorage(settings)


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
    app.state.media_storage = _build_media_storage(settings)
    app.state.catalog_service = CatalogService(
        get_session_factory(),
        media_storage=app.state.media_storage,
        # Env-tunable like every other rate limit here, so it can be adjusted
        # during an incident without a code deploy.
        presign_rate_limiter=FixedWindowRateLimiter(
            max_attempts=settings.media_presign_max_per_window,
            window_seconds=settings.media_presign_window_seconds,
            clock=time.monotonic,
        ),
        pending_ttl_seconds=PENDING_MEDIA_TTL_SECONDS,
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

    # Registered on the app/errors.py BASES, not on a concrete domain class.
    # Starlette resolves a handler by walking type(exc).__mro__, so binding these
    # to app.boutique's own classes would turn every catalog 404 and domain-400
    # into an unhandled 500.
    @app.exception_handler(DomainValidationError)
    async def _domain_validation(request: Request, exc: DomainValidationError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "VALIDATION_ERROR", "message": str(exc)}}, status_code=400
        )

    @app.exception_handler(DomainNotFoundError)
    async def _not_found(request: Request, exc: DomainNotFoundError) -> JSONResponse:
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

    @app.exception_handler(DuplicateSizeError)
    async def _duplicate_size(request: Request, exc: DuplicateSizeError) -> JSONResponse:
        return JSONResponse(DUPLICATE_SIZE_BODY, status_code=409)

    @app.exception_handler(MediaLimitReachedError)
    async def _media_limit_reached(request: Request, exc: MediaLimitReachedError) -> JSONResponse:
        return JSONResponse(MEDIA_LIMIT_REACHED_BODY, status_code=409)

    @app.exception_handler(MediaNotUploadedError)
    async def _media_not_uploaded(request: Request, exc: MediaNotUploadedError) -> JSONResponse:
        return JSONResponse(MEDIA_NOT_UPLOADED_BODY, status_code=409)

    @app.exception_handler(MediaMismatchError)
    async def _media_mismatch(request: Request, exc: MediaMismatchError) -> JSONResponse:
        return JSONResponse(MEDIA_MISMATCH_BODY, status_code=409)

    @app.exception_handler(MediaOrderMismatchError)
    async def _media_order_mismatch(request: Request, exc: MediaOrderMismatchError) -> JSONResponse:
        # 409, not 400: the body is well-formed and passed schema validation —
        # it conflicts with server state, like every other media conflict.
        return JSONResponse(MEDIA_ORDER_MISMATCH_BODY, status_code=409)

    @app.exception_handler(MediaPresignThrottledError)
    async def _presign_throttled(request: Request, exc: MediaPresignThrottledError) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    # Raised by app/storage/, not app/catalog/: a bucket with no usable
    # credentials is operationally identical to no bucket and degrades the same
    # way — 503, never 500.
    @app.exception_handler(MediaNotConfiguredError)
    async def _media_not_configured(request: Request, exc: MediaNotConfiguredError) -> JSONResponse:
        return JSONResponse(MEDIA_NOT_CONFIGURED_BODY, status_code=503)

    @app.exception_handler(MediaStorageUnavailableError)
    async def _media_storage_unavailable(
        request: Request, exc: MediaStorageUnavailableError
    ) -> JSONResponse:
        return JSONResponse(MEDIA_STORAGE_UNAVAILABLE_BODY, status_code=503)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(boutique_router)
    # After the boutique router: both mount prefix="/manage", so a duplicated
    # path would silently shadow. The ROUTES table in test_catalog_api.py is
    # what keeps that honest.
    app.include_router(catalog_router)
    return app


app = create_app()
