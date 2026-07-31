import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from starlette.routing import Match
from starlette.types import Scope

from app.api.routes.health import router as health_router
from app.auth.dependencies import NotAuthenticatedError, NotAuthorizedError
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.router import RateLimitedError
from app.auth.router import router as auth_router
from app.auth.service import AuthService, InvalidCredentialsError
from app.auth.staff import (
    DuplicateEmailError,
    LastOwnerRequiredError,
    StaffSelfManageError,
    StaffService,
)
from app.auth.staff_router import router as staff_router
from app.booking.comms import BookingCommsService
from app.booking.manage import (
    BookingAlreadyStartedError,
    BookingCancelledError,
    BookingLinkInvalidError,
    BookingLookupThrottledError,
    ManageBookingService,
)
from app.booking.owner import (
    BookingTransitionInvalidError,
    CustomerAlreadyBookedError,
    OwnerBookingService,
    OwnerResendThrottledError,
)
from app.booking.owner_router import router as owner_booking_router
from app.booking.router import router as booking_router
from app.booking.service import (
    BookingService,
    BookingThrottledError,
    PhoneNotVerifiedError,
    SlotUnavailableError,
    TermsStaleError,
)
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
from app.dashboard.router import router as dashboard_router
from app.dashboard.service import DashboardService
from app.db.session import ensure_safe_database_role, get_session_factory
from app.errors import DomainNotFoundError, DomainValidationError
from app.notifications.base import SmsNotConfiguredError, SmsSender, SmsSendError
from app.notifications.fake import FakeSmsSender
from app.notifications.router import router as otp_router
from app.notifications.service import (
    NotificationService,
    OtpExpiredError,
    OtpInvalidError,
    OtpService,
    OtpThrottledError,
)
from app.notifications.unconfigured import UnconfiguredSmsSender
from app.security_headers import SecurityHeadersMiddleware
from app.storage.base import (
    MediaNotConfiguredError,
    MediaStorage,
    MediaStorageUnavailableError,
)
from app.storage.s3 import S3MediaStorage
from app.storage.unconfigured import UnconfiguredMediaStorage
from app.storefront.router import router as storefront_router
from app.storefront.service import StorefrontService
from app.storefront.validation import StorefrontThrottledError
from app.tenancy.middleware import (
    EXEMPT_PATHS,
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
# ONE body for every unadmitted role — naming the required role would tell a
# probe which roles exist.
NOT_AUTHORIZED_BODY = {
    "error": {"code": "NOT_AUTHORIZED", "message": "This action is not available for your account."}
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
# Fixed bodies: no provider name, account identifier or provider-supplied text
# may ever reach a user-facing message (the media-error precedent).
SMS_NOT_CONFIGURED_BODY = {
    "error": {"code": "SMS_NOT_CONFIGURED", "message": "Phone verification is not available."}
}
SMS_UNAVAILABLE_BODY = {
    "error": {
        "code": "SMS_UNAVAILABLE",
        "message": "Could not send the verification code. Try again.",
    }
}
OTP_INVALID_BODY = {"error": {"code": "OTP_INVALID", "message": "The code is incorrect."}}
OTP_EXPIRED_BODY = {
    "error": {"code": "OTP_EXPIRED", "message": "The code expired. Request a new one."}
}
PHONE_NOT_VERIFIED_BODY = {
    "error": {"code": "PHONE_NOT_VERIFIED", "message": "Verify your phone number and try again."}
}
# ONE body for taken, off-grid, past and closed — distinguishing them would
# tell a prober the shape of the boutique's grid.
SLOT_UNAVAILABLE_BODY = {
    "error": {"code": "SLOT_UNAVAILABLE", "message": "That time was just taken. Choose another."}
}
TERMS_STALE_BODY = {
    "error": {
        "code": "TERMS_STALE",
        "message": "The booking terms changed. Review and accept them again.",
    }
}
# ONE body for unknown, rotated and malformed manage tokens — distinguishing them
# would turn the lookup into an oracle for "is this token shaped right".
BOOKING_LINK_INVALID_BODY = {
    "error": {"code": "BOOKING_LINK_INVALID", "message": "This link is no longer valid."}
}
BOOKING_ALREADY_STARTED_BODY = {
    "error": {
        "code": "BOOKING_ALREADY_STARTED",
        "message": "This appointment has already started.",
    }
}
BOOKING_CANCELLED_BODY = {
    "error": {"code": "BOOKING_CANCELLED", "message": "This appointment was cancelled."}
}
# ONE body for every refused owner transition — an illegal status pair, a
# no-show before the appointment, a cancel after it (D19).
BOOKING_TRANSITION_INVALID_BODY = {
    "error": {
        "code": "BOOKING_TRANSITION_INVALID",
        "message": "That change is not allowed for this booking's current state.",
    }
}
CUSTOMER_ALREADY_BOOKED_BODY = {
    "error": {
        "code": "CUSTOMER_ALREADY_BOOKED",
        "message": "This customer already has a booking at that time.",
    }
}
DUPLICATE_EMAIL_BODY = {
    "error": {
        "code": "DUPLICATE_EMAIL",
        "message": "A staff member with this email already exists.",
    }
}
# No count in the message: how many owners exist is not the owner's problem to
# solve, and naming it would leak the tenant's staffing to a probe.
LAST_OWNER_REQUIRED_BODY = {
    "error": {
        "code": "LAST_OWNER_REQUIRED",
        "message": "The boutique must always have at least one owner.",
    }
}
STAFF_SELF_MANAGE_BODY = {
    "error": {
        "code": "STAFF_SELF_MANAGE",
        "message": "You cannot change your own role or deactivate your own account.",
    }
}


# The built SPAs: Frontend/apps/{manage,storefront}/dist copied to
# app/static/{manage,storefront} by the deploy-staging job. NEVER committed, and
# deliberately NOT listed in .gitignore either: `railway up` respects
# .gitignore, so a gitignored static tree would be dropped from the upload with
# no error at all. Keeping it untracked is the whole mechanism — it exists only
# inside a CI runner, and a developer who builds locally excludes it via
# .git/info/exclude rather than teaching git to hide it from Railway too. Same
# reason the directory is `static/` and not `dist/` or `staticfiles/`:
# .gitignore already ignores both names anywhere in the tree.
STATIC_ROOT = Path(__file__).resolve().parent / "static"

# The API owns these first path segments; the SPA fallback must never claim them.
_RESERVED_SEGMENTS = frozenset({"manage", "storefront"})

# Nothing here is content-hashed, so nothing here may be cached without asking.
# ETag + Last-Modified alone make a response heuristically cacheable (RFC 9111
# §4.2.2): a shell cached that way survives a deploy, then requests the hashed
# bundle names it was built against, and the /assets Mount 404s them — a blank
# page nobody can recover from but a hard reload. `no-cache` still allows the
# 304, so the cost is a conditional request rather than the bytes. The hashed
# files under /assets/ need no header: a new build gives them new names.
_REVALIDATE = {"cache-control": "no-cache"}


class _SpaFallbackRoute(APIRoute):
    """The storefront catch-all, which DECLINES to match anything the API owns
    rather than matching it and answering 404.

    That distinction is the whole design. Starlette returns on the first FULL
    match and remembers only the first PARTIAL one, so a catch-all that fully
    matches `GET /storefront/otp/send` wins outright and the POST route's
    partial — the thing that produces the 405 — is never handled. Answering 404
    from inside the handler does not help: by then the 405 is already lost.
    Returning Match.NONE leaves the partial as the only candidate, so the 405
    survives.

    `/docs` needs the same treatment for a different reason: declining lets the
    request fall through to Starlette's own 404, which is what keeps "the docs
    are dark outside dev" true instead of answering the storefront shell with a
    200. The rstrip is for redirect_slashes — when nothing matches `/docs`,
    Starlette retries `/docs/`, and an unnormalized comparison would let the
    retry through.
    """

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        path = str(scope.get("path", ""))
        if path.rstrip("/") in EXEMPT_PATHS:
            return Match.NONE, {}
        if path.lstrip("/").split("/", 1)[0] in _RESERVED_SEGMENTS:
            return Match.NONE, {}
        return super().matches(scope)


def _serve_file(app: FastAPI, url_path: str, file_path: Path) -> None:
    """One exact route per file. HEAD is spelled out because FastAPI's APIRoute,
    unlike Starlette's Route, does not add it to a GET route — without it every
    document here 405s the uptime monitors and link-preview crawlers that reach
    a public URL with HEAD first, while the /assets Mounts next door answer 200.
    OPTIONS is still left to Starlette's 405 path, and a Mount is still the
    wrong tool: it would match every method AND every path under it."""
    if not file_path.is_file():
        return

    async def _endpoint() -> FileResponse:
        return FileResponse(file_path, headers=_REVALIDATE)

    app.add_api_route(url_path, _endpoint, methods=["GET", "HEAD"], include_in_schema=False)


def _register_spas(app: FastAPI) -> None:
    """Called LAST, after every include_router, so every API route wins first."""
    manage = STATIC_ROOT / "manage"
    storefront = STATIC_ROOT / "storefront"
    if not (manage / "index.html").is_file() or not (storefront / "index.html").is_file():
        # Absence is a supported state, never a boot failure: no dev machine has
        # run `pnpm -r build`, and neither has the test suite. A deploy whose
        # copy step failed then still answers /health, which is what makes it
        # diagnosable rather than dead. CI asserts the files exist before
        # `railway up` so this cannot go unnoticed in production.
        logger.info("SPA bundles not found under %s — serving the API only", STATIC_ROOT)
        return

    for prefix, app_dir in (("/manage/assets", manage), ("/assets", storefront)):
        assets = app_dir / "assets"
        if assets.is_dir():
            app.mount(prefix, StaticFiles(directory=assets), name=f"{app_dir.name}-assets")

    # Vite copies public/ verbatim to the root of dist/, so the dist root IS the
    # list — derived, never hardcoded. A hardcoded tuple drifts the moment
    # anyone adds an og-image or the sitemap.xml F49 needs: on the storefront
    # side an unlisted file falls to the catch-all and returns the HTML shell
    # with a 200, which nosniff then makes the browser refuse. Silently dead.
    # `base: "/manage/"` puts the console's copies under /manage/, which is what
    # keeps the two trees disjoint.
    for prefix, app_dir in (("/manage", manage), ("", storefront)):
        for entry in sorted(app_dir.iterdir()):
            if entry.is_file() and entry.name != "index.html":
                _serve_file(app, f"{prefix}/{entry.name}", entry)

    # Exact path, no subtree: apps/manage has no client-side router (App.tsx
    # drives its sections from useState), so exactly one URL is the console and
    # a subtree fallback would invent deep links the app cannot restore.
    _serve_file(app, "/manage", manage / "index.html")

    storefront_index = storefront / "index.html"

    async def _storefront_shell(path: str) -> FileResponse:
        return FileResponse(storefront_index, headers=_REVALIDATE)

    # HEAD for the same reason as _serve_file. It cannot cost the API its 405s:
    # `matches` declines EXEMPT_PATHS and the reserved segments before a method
    # is ever looked at, so HEAD /manage/settings never reaches this route.
    app.router.routes.append(
        _SpaFallbackRoute(
            "/{path:path}", _storefront_shell, methods=["GET", "HEAD"], include_in_schema=False
        )
    )


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


def _build_sms_sender(settings: Settings) -> SmsSender:
    """Mirrors _build_media_storage: absence is a supported deployment that
    answers 503, and extra="ignore" makes a typo'd SMS_PROVDER silent — this
    INFO line is what makes the degradation observable."""
    if settings.sms_provider == "fake":
        logger.info("SMS sender: FAKE (in-memory outbox) — no real SMS will be sent")
        return FakeSmsSender()
    logger.info("SMS sender NOT configured — OTP send will answer 503 SMS_NOT_CONFIGURED")
    return UnconfiguredSmsSender()


def create_app(resolver: TenantResolver | None = None) -> FastAPI:
    settings = get_settings()
    is_dev = settings.app_env == "dev"
    app = FastAPI(
        title="Boutique Platform API",
        version=settings.app_version,
        lifespan=lifespan,
        # Dark outside dev. F10 makes this origin publicly reachable, and the
        # first crawler that finds {slug}.{domain} also finds /openapi.json — a
        # complete, uncredentialed description of every /manage route and of
        # exactly the fields the storefront allowlist exists to fence off
        # (quantity, price_visible, out_of_stock, capacity, terms_text, the
        # presign shape). Pulled forward from the F21 hardening gate because
        # F21 lands after the pilot is already public.
        docs_url="/docs" if is_dev else None,
        redoc_url="/redoc" if is_dev else None,
        openapi_url="/openapi.json" if is_dev else None,
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
    # Added LAST = OUTERMOST, and that is the whole point: it is what puts the
    # headers on the TENANT_NOT_FOUND 404 that TenantResolutionMiddleware
    # returns from its own dispatch without reaching a handler.
    app.add_middleware(SecurityHeadersMiddleware)

    app.state.auth_service = AuthService(get_session_factory(), settings)
    # Its own service beside the auth one, never methods on it: AuthService
    # verifies credentials and issues sessions, and folding administration in
    # would put the login path's fake into every staff CRUD test.
    app.state.staff_service = StaffService(get_session_factory())
    # No clock wired: the parameter exists so the db suite can freeze the
    # window, and production reads a real one (D8).
    app.state.dashboard_service = DashboardService(get_session_factory())
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
    # The anonymous surface has no session to key a limit on, so the storefront
    # reads get their own per-tenant bucket — see app/storefront/router.py._throttle
    # for why per-tenant and not per-IP, and why the window is sized so wide.
    app.state.storefront_rate_limiter = FixedWindowRateLimiter(
        max_attempts=settings.storefront_read_max_per_window,
        window_seconds=settings.storefront_read_window_seconds,
        clock=time.monotonic,
    )
    # Its own service, never CatalogService: routing public reads through the
    # console's service would compute out_of_stock/total_quantity/variant_count
    # on every anonymous request and keep them off the wire only by the response
    # model remembering to omit them. See app/storefront/service.py.
    app.state.storefront_service = StorefrontService(
        get_session_factory(),
        media_storage=app.state.media_storage,
    )
    app.state.sms_sender = _build_sms_sender(settings)
    app.state.notification_service = NotificationService(
        get_session_factory(), sender=app.state.sms_sender
    )
    app.state.otp_service = OtpService(
        get_session_factory(),
        notifications=app.state.notification_service,
        phone_limiter=FixedWindowRateLimiter(
            max_attempts=settings.otp_send_max_per_phone_window,
            window_seconds=settings.otp_send_phone_window_seconds,
            clock=time.monotonic,
        ),
        tenant_limiter=FixedWindowRateLimiter(
            max_attempts=settings.otp_send_max_per_tenant_window,
            window_seconds=settings.otp_send_tenant_window_seconds,
            clock=time.monotonic,
        ),
        verify_limiter=FixedWindowRateLimiter(
            max_attempts=settings.otp_verify_max_per_phone_window,
            window_seconds=settings.otp_verify_phone_window_seconds,
            clock=time.monotonic,
        ),
        dev_code=settings.otp_dev_code,
    )
    app.state.booking_service = BookingService(
        get_session_factory(),
        otp=app.state.otp_service,
        create_limiter=FixedWindowRateLimiter(
            max_attempts=settings.booking_create_max_per_window,
            window_seconds=settings.booking_create_window_seconds,
            clock=time.monotonic,
        ),
        # Its own instance, not a second key on the one above: max_attempts is
        # per LIMITER, so sharing would give the phone budget the tenant's
        # ceiling and it could never trip first.
        phone_limiter=FixedWindowRateLimiter(
            max_attempts=settings.booking_create_max_per_phone_window,
            window_seconds=settings.booking_create_phone_window_seconds,
            clock=time.monotonic,
        ),
    )
    # base_domain, not a hardcoded host: the manage link the SMS carries has to
    # resolve to the tenant's own storefront in dev, staging and production
    # alike, and Settings is where deployment identity lives.
    app.state.booking_comms_service = BookingCommsService(
        get_session_factory(),
        notifications=app.state.notification_service,
        base_domain=settings.base_domain,
    )
    app.state.manage_booking_service = ManageBookingService(
        get_session_factory(),
        # Its own instance again, never a shared one: max_attempts is per limiter,
        # so a second key on an existing budget could never trip first.
        lookup_limiter=FixedWindowRateLimiter(
            max_attempts=settings.booking_lookup_max_per_tenant_window,
            window_seconds=settings.booking_lookup_window_seconds,
            clock=time.monotonic,
        ),
    )
    # After booking_comms_service and storefront_service: it holds both. The
    # storefront service is INJECTED rather than re-implemented — GET
    # /manage/slots is its list_slots plus an owner projection (D6), and a
    # second materializer is the one thing app/booking/slots.py exists to forbid.
    app.state.owner_booking_service = OwnerBookingService(
        get_session_factory(),
        storefront=app.state.storefront_service,
        comms=app.state.booking_comms_service,
        # Its own instance, for the fourth time and the same reason: max_attempts
        # lives on the LIMITER, not per key, so a second key on an existing
        # budget could never trip first. Resend, phone correction and reschedule
        # share this one because all three spend real SMS credit on an owner tap;
        # owner cancel does not, because `cancelled` is terminal and its ceiling
        # is the number of bookings the boutique has (D10).
        sms_limiter=FixedWindowRateLimiter(
            max_attempts=settings.booking_owner_sms_max_per_tenant_window,
            window_seconds=settings.booking_owner_sms_window_seconds,
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

    # 403, not 401: the session is live and the staffer is who she says she is —
    # her role is what refuses the action.
    @app.exception_handler(NotAuthorizedError)
    async def _not_authorized(request: Request, exc: NotAuthorizedError) -> JSONResponse:
        return JSONResponse(NOT_AUTHORIZED_BODY, status_code=403)

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

    # Its own handler rather than a reuse of RateLimitedError: the login form and
    # the anonymous read surface have unrelated budgets, keys and operational
    # meanings. Reparenting all four throttle errors onto one base is a
    # behaviour-neutral cleanup owned by F21.
    @app.exception_handler(StorefrontThrottledError)
    async def _storefront_throttled(
        request: Request, exc: StorefrontThrottledError
    ) -> JSONResponse:
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

    # Raised by app/notifications/, same containment as the media pair: a
    # missing provider degrades to 503, and provider text never reaches a body.
    @app.exception_handler(SmsNotConfiguredError)
    async def _sms_not_configured(request: Request, exc: SmsNotConfiguredError) -> JSONResponse:
        return JSONResponse(SMS_NOT_CONFIGURED_BODY, status_code=503)

    @app.exception_handler(SmsSendError)
    async def _sms_unavailable(request: Request, exc: SmsSendError) -> JSONResponse:
        return JSONResponse(SMS_UNAVAILABLE_BODY, status_code=503)

    @app.exception_handler(OtpInvalidError)
    async def _otp_invalid(request: Request, exc: OtpInvalidError) -> JSONResponse:
        return JSONResponse(OTP_INVALID_BODY, status_code=400)

    @app.exception_handler(OtpExpiredError)
    async def _otp_expired(request: Request, exc: OtpExpiredError) -> JSONResponse:
        return JSONResponse(OTP_EXPIRED_BODY, status_code=400)

    # Its own class for the same reason as StorefrontThrottledError: the OTP
    # send budget and the login budget are unrelated keys with unrelated
    # operational meanings. Reparenting onto one base stays owned by F21.
    @app.exception_handler(OtpThrottledError)
    async def _otp_throttled(request: Request, exc: OtpThrottledError) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    # 403, not 401: the caller is not asked to authenticate — the request is
    # simply not accompanied by proof of the phone it names.
    @app.exception_handler(PhoneNotVerifiedError)
    async def _phone_not_verified(request: Request, exc: PhoneNotVerifiedError) -> JSONResponse:
        return JSONResponse(PHONE_NOT_VERIFIED_BODY, status_code=403)

    @app.exception_handler(SlotUnavailableError)
    async def _slot_unavailable(request: Request, exc: SlotUnavailableError) -> JSONResponse:
        return JSONResponse(SLOT_UNAVAILABLE_BODY, status_code=409)

    @app.exception_handler(TermsStaleError)
    async def _terms_stale(request: Request, exc: TermsStaleError) -> JSONResponse:
        return JSONResponse(TERMS_STALE_BODY, status_code=409)

    # Its own class like the other three throttles; the F21 reparenting note
    # on StorefrontThrottledError covers this one too.
    @app.exception_handler(BookingThrottledError)
    async def _booking_throttled(request: Request, exc: BookingThrottledError) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    # 404, and NOT the shared NOT_FOUND body: the page renders its own
    # invalid-link state off this code, and reusing NOT_FOUND would make it
    # indistinguishable from an archived dress on the same origin.
    @app.exception_handler(BookingLinkInvalidError)
    async def _booking_link_invalid(request: Request, exc: BookingLinkInvalidError) -> JSONResponse:
        return JSONResponse(BOOKING_LINK_INVALID_BODY, status_code=404)

    # 409, not 403: the token is valid and the caller is who she says she is —
    # the appointment's state is what refuses the action.
    @app.exception_handler(BookingAlreadyStartedError)
    async def _booking_already_started(
        request: Request, exc: BookingAlreadyStartedError
    ) -> JSONResponse:
        return JSONResponse(BOOKING_ALREADY_STARTED_BODY, status_code=409)

    @app.exception_handler(BookingCancelledError)
    async def _booking_cancelled(request: Request, exc: BookingCancelledError) -> JSONResponse:
        return JSONResponse(BOOKING_CANCELLED_BODY, status_code=409)

    @app.exception_handler(BookingLookupThrottledError)
    async def _booking_lookup_throttled(
        request: Request, exc: BookingLookupThrottledError
    ) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    # 409, not 400: the request is well-formed — the booking's state (or the
    # clock) is what refuses it.
    @app.exception_handler(BookingTransitionInvalidError)
    async def _booking_transition_invalid(
        request: Request, exc: BookingTransitionInvalidError
    ) -> JSONResponse:
        return JSONResponse(BOOKING_TRANSITION_INVALID_BODY, status_code=409)

    @app.exception_handler(CustomerAlreadyBookedError)
    async def _customer_already_booked(
        request: Request, exc: CustomerAlreadyBookedError
    ) -> JSONResponse:
        return JSONResponse(CUSTOMER_ALREADY_BOOKED_BODY, status_code=409)

    # The existing 429 body, deliberately: a fourth spelling of "too many
    # attempts" would be a new code for the same fact (D10).
    @app.exception_handler(OwnerResendThrottledError)
    async def _owner_resend_throttled(
        request: Request, exc: OwnerResendThrottledError
    ) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    # F51's three. Deliberately NOT registered beside them, so a reviewer can
    # check this list is complete rather than short: StaffNotFoundError
    # subclasses DomainNotFoundError and is bound to the base above; the
    # current_password failures are DomainValidationError; NotAuthorizedError is
    # F31's app-wide 403; NotAuthenticatedError is the app-wide 401; and a forged
    # Origin is answered by the middleware before routing.
    @app.exception_handler(DuplicateEmailError)
    async def _duplicate_email(request: Request, exc: DuplicateEmailError) -> JSONResponse:
        return JSONResponse(DUPLICATE_EMAIL_BODY, status_code=409)

    @app.exception_handler(LastOwnerRequiredError)
    async def _last_owner_required(request: Request, exc: LastOwnerRequiredError) -> JSONResponse:
        return JSONResponse(LAST_OWNER_REQUIRED_BODY, status_code=409)

    # 409, not 403: the request is well-formed and the caller is authorized — the
    # identity of the TARGET is what refuses it.
    @app.exception_handler(StaffSelfManageError)
    async def _staff_self_manage(request: Request, exc: StaffSelfManageError) -> JSONResponse:
        return JSONResponse(STAFF_SELF_MANAGE_BODY, status_code=409)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(boutique_router)
    # After the boutique router: both mount prefix="/manage", so a duplicated
    # path would silently shadow. The ROUTES table in test_catalog_api.py is
    # what keeps that honest.
    app.include_router(catalog_router)
    # The fourth /manage router, after the catalog one. Same hazard, now with
    # four surfaces on one prefix: a duplicated (method, path) would silently
    # shadow whichever was included first. The ROUTES table in
    # test_booking_owner_api.py is what keeps that honest for this one.
    app.include_router(owner_booking_router)
    # The fifth /manage router, after the owner booking one. Same hazard, now
    # with five surfaces on one prefix: a duplicated (method, path) would
    # silently shadow whichever was included first. The ROUTES table in
    # test_staff_api.py is what keeps that honest for this one.
    app.include_router(staff_router)
    # The sixth /manage router, after the staff one. Same hazard, now with six
    # surfaces on one prefix: a duplicated (method, path) would silently shadow
    # whichever was included first. The ROUTES table in test_dashboard_api.py is
    # what keeps that honest for this one.
    app.include_router(dashboard_router)
    # Its own prefix, never under /manage: CsrfOriginMiddleware and any future
    # edge rule keyed on /manage must not cover — or exempt — anonymous traffic.
    app.include_router(storefront_router)
    # Same /storefront prefix, sibling router: the read router is contractually
    # GET-only, so the OTP mutations live in app/notifications/router.py. The
    # cross-router shadowing guard in test_storefront_api.py covers the pair.
    app.include_router(otp_router)
    # The third /storefront sibling: the booking create plus F16's three
    # tokenized manage routes. Same anonymous posture as the OTP pair; asserted
    # in test_booking_api.py and test_booking_manage_api.py.
    app.include_router(booking_router)
    # LAST, after every router: the mounts and the catch-all only ever see what
    # no API route claimed.
    _register_spas(app)
    return app


app = create_app()
