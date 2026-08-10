import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from starlette.routing import Match
from starlette.types import Scope

from app.api.routes.health import router as health_router
from app.atelier.router import router as atelier_router
from app.atelier.service import AtelierService
from app.atelier.validation import TicketAlreadyAssignedError, TicketStageConflictError
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
    BookingAwaitingPaymentError,
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
    DressUnavailableError,
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
    ReservationOverlapError,
)
from app.catalog.validation import PENDING_MEDIA_TTL_SECONDS
from app.core.config import Settings, get_settings
from app.csrf import CsrfOriginMiddleware
from app.customers.router import router as customers_router
from app.customers.service import CustomersService
from app.dashboard.router import router as dashboard_router
from app.dashboard.service import DashboardService
from app.db.session import ensure_safe_database_role, get_session_factory
from app.errors import DomainNotFoundError, DomainValidationError
from app.floor.notifications import NotificationsService
from app.floor.router import router as floor_router
from app.floor.service import FloorService
from app.floor.validation import (
    QueueEmptyError,
    QueueTicketChangedError,
    QueueTicketNotWaitingError,
    RoomOccupiedError,
    SosAlreadyAcceptedError,
    SosClosedError,
    StaffOccupiedError,
)
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
from app.notifications.twilio import TwilioSmsSender
from app.notifications.unconfigured import UnconfiguredSmsSender
from app.payments.base import (
    GatewayCredentialsRejectedError,
    GatewayNotConfiguredError,
    GatewayNotConnectedError,
    GatewayUnavailableError,
    GatewayWebhookInvalidError,
    PaymentAlreadyHeldError,
    PaymentGateway,
)
from app.payments.fake import FakeGateway
from app.payments.fake_pay import FakePayService, register_fake_pay
from app.payments.lemonsqueezy import LEMONSQUEEZY_PROVIDER, LemonSqueezyGateway
from app.payments.router import router as gateway_router
from app.payments.secretbox import (
    FakeSecretBox,
    SecretBox,
    SecretBoxNotConfiguredError,
    SecretDecryptError,
    UnconfiguredSecretBox,
)
from app.payments.service import (
    GatewayCredentialService,
    GatewayThrottledError,
    PaymentService,
)
from app.payments.unconfigured import UnconfiguredGateway
from app.payments.webhook_router import DepositBookingService
from app.payments.webhook_router import router as webhook_router
from app.platform.auth import OperatorAuthService
from app.platform.auth_router import router as platform_auth_router
from app.platform.join_router import router as platform_join_router
from app.platform.router import ConsoleCommandRefused
from app.platform.router import invites_router as platform_invites_router
from app.platform.router import router as platform_router
from app.platform.service import ProvisioningService
from app.portal.router import router as portal_router
from app.portal.service import PortalNoBookingsError, PortalService, PortalThrottledError
from app.privacy.router import router as privacy_router
from app.privacy.service import PrivacyService, SubjectHasActiveBookingError
from app.privacy.validation import (
    MARKETING_WITHDRAW_MAX_PER_WINDOW,
    MARKETING_WITHDRAW_WINDOW_SECONDS,
    SUBJECT_ERASE_MAX_PER_WINDOW,
    SUBJECT_ERASE_WINDOW_SECONDS,
    SUBJECT_EXPORT_MAX_PER_WINDOW,
    SUBJECT_EXPORT_WINDOW_SECONDS,
    PrivacyThrottledError,
)
from app.queue.manage_router import router as queue_manage_router
from app.queue.qr import CheckinQrService
from app.queue.router import router as queue_router
from app.queue.service import QueueService
from app.queue.validation import CheckinThrottledError
from app.security_headers import SecurityHeadersMiddleware, build_csp
from app.shifts.router import router as shifts_router
from app.shifts.service import (
    AvailabilityConflictError,
    NoOpeningHoursError,
    NotShiftManagerEligibleError,
    ShiftManagerSlotTakenError,
    ShiftsService,
    SubmissionClosedError,
    TemplatesAlreadySeededError,
)
from app.shifts.validation import (
    MAX_COVERAGE_TARGET,
    CoverageTargetInvalidError,
    TemplateLimitReachedError,
    WeekOutOfRangeError,
)
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
from app.waitlist.manage_router import router as waitlist_manage_router
from app.waitlist.offer_router import router as waitlist_offer_router
from app.waitlist.offer_service import OfferNotClaimableError, WaitlistOfferService
from app.waitlist.router import router as waitlist_router
from app.waitlist.service import WaitlistService
from app.waitlist.validation import WaitlistThrottledError

logger = logging.getLogger("app")

INVALID_CREDENTIALS_BODY = {
    "error": {"code": "INVALID_CREDENTIALS", "message": "Incorrect email or password."}
}
SUBJECT_HAS_ACTIVE_BOOKING_BODY = {
    "error": {
        "code": "SUBJECT_HAS_ACTIVE_BOOKING",
        # It tells the owner what to DO, because the refusal is not the end of
        # the request — the erasure duty yields to performing a contract the
        # subject is still party to, and the owner has to resolve the booking
        # before the duty can be discharged.
        "message": "Cancel or complete her upcoming booking before erasing her record.",
    }
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
# F28. `details` carries the CONFLICTING range — the one catalog 409 that names
# what it collided with, because the remedy is to change those exact dates and
# the pane can only say which without a second round trip. Built through
# `_body_with_details` for that helper's own reason: the base is a module
# constant shared by every request.
# F39's five. Each is a code the console maps to a Hebrew sentence, which is
# why none of them is a `DomainValidationError` subclass answering the generic
# VALIDATION_ERROR — an unmapped code renders the server's ENGLISH message,
# right-aligned, in a Hebrew console, on a green build (F38's build note).
WEEK_OUT_OF_RANGE_BODY = {
    "error": {
        "code": "WEEK_OUT_OF_RANGE",
        "message": "That week is outside the submission window.",
    }
}
SUBMISSION_CLOSED_BODY = {
    "error": {
        "code": "SUBMISSION_CLOSED",
        "message": "The deadline for that week has passed.",
    }
}
TEMPLATES_ALREADY_SEEDED_BODY = {
    "error": {
        "code": "TEMPLATES_ALREADY_SEEDED",
        "message": "Shifts already exist. Edit them by hand instead.",
    }
}
NO_OPENING_HOURS_BODY = {
    "error": {
        "code": "NO_OPENING_HOURS",
        "message": "No opening hours are set, so there is nothing to create shifts from.",
    }
}
TEMPLATE_LIMIT_REACHED_BODY = {
    "error": {
        "code": "TEMPLATE_LIMIT_REACHED",
        "message": "That day already has the maximum number of shifts.",
    }
}
# F40 D10. The bound is INTERPOLATED from the constant rather than typed into
# the sentence: O3 calls MAX_COVERAGE_TARGET a fat-finger guard rather than a
# product rule, so it will move, and a literal here would leave this message and
# the console's own Hebrew one disagreeing about the same field in the same
# session (design F-33).
# F40's other three. None is a `DomainValidationError` subclass, for the reason
# F39's five record: Starlette walks `type(exc).__mro__`, so a subclass without
# its own handler answers a quiet, plausible VALIDATION_ERROR 400 — and the
# console, which maps CODES to Hebrew, renders the server's English sentence
# right-aligned on a green build.
AVAILABILITY_CONFLICT_BODY = {
    "error": {
        "code": "AVAILABILITY_CONFLICT",
        "message": "She marked herself unavailable for that shift. Acknowledge the override.",
    }
}
NOT_SHIFT_MANAGER_ELIGIBLE_BODY = {
    "error": {
        "code": "NOT_SHIFT_MANAGER_ELIGIBLE",
        "message": "Only staff marked as eligible can be assigned as shift manager.",
    }
}
SHIFT_MANAGER_SLOT_TAKEN_BODY = {
    "error": {
        "code": "SHIFT_MANAGER_SLOT_TAKEN",
        "message": "That shift already has a shift manager.",
    }
}
COVERAGE_TARGET_INVALID_BODY = {
    "error": {
        "code": "COVERAGE_TARGET_INVALID",
        "message": f"A coverage target must be a whole number between 0 and {MAX_COVERAGE_TARGET}.",
    }
}
RESERVATION_OVERLAP_BODY = {
    "error": {
        "code": "RESERVATION_OVERLAP",
        "message": "This dress is already reserved for part of those dates.",
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
# F28. Its OWN code beside SLOT_UNAVAILABLE, because the remedy differs: every
# time on this day is equally refused for this gown, so «choose another time»
# would walk her down the same day's slot list. The client must branch on the
# code — the two 409s need different recoveries, and only one of them refetches
# slots.
DRESS_UNAVAILABLE_BODY = {
    "error": {
        "code": "DRESS_UNAVAILABLE",
        "message": "This dress is not available on the date you chose. Choose another date.",
    }
}
TERMS_STALE_BODY = {
    "error": {
        "code": "TERMS_STALE",
        "message": "The booking terms changed. Review and accept them again.",
    }
}
# F24's login refusal, and its OWN code rather than the house 404: the portal
# login panel renders a designed «no bookings for this number» state off it, and
# NOT_FOUND would be indistinguishable from an archived dress on the same origin.
# Not an enumeration oracle — the caller has just proved possession of the phone,
# so this discloses only her own data to herself (spec D1).
PORTAL_NO_BOOKINGS_BODY = {
    "error": {
        "code": "PORTAL_NO_BOOKINGS",
        "message": "There are no bookings for this phone number at this boutique.",
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
# Its OWN code rather than a reuse of BOOKING_CANCELLED (F19 D14, A2): an unpaid
# hold is neither cancelled nor standing, and the storefront renders a THIRD
# state off this distinction. Reusing the cancelled code would tell a bride
# mid-checkout that her appointment was cancelled.
BOOKING_AWAITING_PAYMENT_BODY = {
    "error": {
        "code": "BOOKING_AWAITING_PAYMENT",
        "message": "This appointment is waiting for payment.",
    }
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
# F17's five. Fixed bodies: no provider name, merchant identifier, field value or
# provider-supplied text may ever reach a user-facing message — the media/SMS
# precedent, and it matters more here because the secret is in the object the
# failing call was handed.
GATEWAY_NOT_CONFIGURED_BODY = {
    "error": {"code": "GATEWAY_NOT_CONFIGURED", "message": "Deposits are not available."}
}
GATEWAY_NOT_CONNECTED_BODY = {
    "error": {"code": "GATEWAY_NOT_CONNECTED", "message": "Connect a payment account first."}
}
GATEWAY_CREDENTIALS_REJECTED_BODY = {
    "error": {
        "code": "GATEWAY_CREDENTIALS_REJECTED",
        "message": "The payment account details were refused.",
    }
}
GATEWAY_UNAVAILABLE_BODY = {
    "error": {
        "code": "GATEWAY_UNAVAILABLE",
        "message": "The payment provider is temporarily unavailable.",
    }
}
GATEWAY_WEBHOOK_INVALID_BODY = {
    "error": {"code": "GATEWAY_WEBHOOK_INVALID", "message": "The webhook could not be verified."}
}
PAYMENT_ALREADY_HELD_BODY = {
    "error": {
        "code": "PAYMENT_ALREADY_HELD",
        "message": "A deposit is already pending for this booking.",
    }
}
# F36's two, F58's two and F37's one, and they are the ONLY bodies in this module
# that can grow a third key. Two codes rather than one with a discriminating `details`:
# two causes, two Hebrew sentences, two remedies (take another room vs. release
# her other room first), and a `details`-key sniff in the console is a worse
# place for that branch than an error code. All are frozen two-key dicts HERE —
# `details` is added by the handler, at raise time, from a copy.
ROOM_OCCUPIED_BODY = {
    "error": {"code": "ROOM_OCCUPIED", "message": "This fitting room is already claimed."}
}
STAFF_OCCUPIED_BODY = {
    "error": {
        "code": "STAFF_OCCUPIED",
        "message": "That staff member is already in a fitting room.",
    }
}
# F58's take-next. A 409 with NO `details`, ever — there is nobody to name — so
# it is a plain frozen body rather than a `_body_with_details` caller.
QUEUE_EMPTY_BODY = {"error": {"code": "QUEUE_EMPTY", "message": "Nobody is waiting in the queue."}}
# F58's other two, and both DO grow a third key at raise time, so they are frozen
# two-key dicts here and `_body_with_details` copies them — exactly F36's two.
QUEUE_TICKET_NOT_WAITING_BODY = {
    "error": {
        "code": "QUEUE_TICKET_NOT_WAITING",
        "message": "That queue entry is no longer waiting.",
    }
}
QUEUE_TICKET_CHANGED_BODY = {
    "error": {"code": "QUEUE_TICKET_CHANGED", "message": "That queue entry changed. Reload."}
}
# F37. The losing accept, and the cancel of an already-accepted alert. `details`
# names the owner — which is the whole reason `sos_alerts.accepted_by` exists: a
# 409 that says «somebody» is unanswerable, and a second GET to discover her
# would race the resolve it is trying to describe.
SOS_ALREADY_ACCEPTED_BODY = {
    "error": {
        "code": "SOS_ALREADY_ACCEPTED",
        "message": "This SOS has already been accepted.",
    }
}
# ⚠ This one NEVER grows `details`, and that is deliberate: five of the six
# `_DetailedConflictError` codes already carry the key, and a sixth would make it
# the default. There is also nobody to name — a closed alert's remedy is "there
# is nothing to do".
SOS_CLOSED_BODY = {"error": {"code": "SOS_CLOSED", "message": "This SOS is already closed."}}


def _body_with_details(base: dict[str, Any], details: dict[str, str] | None) -> dict[str, Any]:
    """The `DomainValidationError` technique: a fixed body plus one value known
    only at raise time.

    ⚠ Copies rather than mutates — `base["error"]` is a module constant shared by
    every request, and stamping `details` onto it would leak one boutique's
    staffer name into the next tenant's 409.

    ⚠ Falsy `details` OMITS the key entirely rather than writing a null. The
    occupant can release between the index violation and the occupant read, and
    a 409 that names nobody is better than «{{name}} כבר בחדר הזה.» rendering
    with an empty interpolation on a legally binding surface. F37's accept has
    the same shape for a different reason: the acceptor's staff row can be
    removed between her accept and the loser's read.

    ⚠ **Renamed from `_occupied_body` in F37**, and it is a rename rather than a
    copy: F37's two conflicts have nothing to do with occupancy, and two copies
    of six lines that must stay identical is how the leak this function exists
    to prevent gets reintroduced in one of them.
    """
    error = dict(base["error"])
    if details:
        error["details"] = details
    return {"error": error}


# F41's two, and they are TWO AND NOT ONE. Both are 409s on the atelier board,
# but the console's copy and the user's next move differ: a stage conflict says
# the GARMENT moved on and the remedy is to look again; an assignment conflict
# says a PERSON took it, and the next tick will name her. Collapsing them into
# the shipped generic CONFLICT (`TERMS_CONFLICT_BODY` above) would make the
# console branch on a message string.
TICKET_STAGE_CONFLICT_BODY = {
    "error": {
        "code": "TICKET_STAGE_CONFLICT",
        "message": "This ticket has already moved on. Reload and try again.",
    }
}
TICKET_ALREADY_ASSIGNED_BODY = {
    "error": {
        "code": "TICKET_ALREADY_ASSIGNED",
        "message": "Someone else has taken this ticket.",
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
# "platform" joined them in F25: the storefront catch-all must DECLINE the
# console's shell and API alike, or a GET /platform on a tenant host would be
# answered with the boutique's own HTML instead of reaching the tenancy fence.
_RESERVED_SEGMENTS = frozenset({"manage", "storefront", "platform"})

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
    platform = STATIC_ROOT / "platform"
    if not (manage / "index.html").is_file() or not (storefront / "index.html").is_file():
        # Absence is a supported state, never a boot failure: no dev machine has
        # run `pnpm -r build`, and neither has the test suite. A deploy whose
        # copy step failed then still answers /health, which is what makes it
        # diagnosable rather than dead. CI asserts the files exist before
        # `railway up` so this cannot go unnoticed in production.
        logger.info("SPA bundles not found under %s — serving the API only", STATIC_ROOT)
        return

    for prefix, app_dir in (
        ("/manage/assets", manage),
        ("/assets", storefront),
        # F25's console, built with `base: "/platform/"` — same shape as manage,
        # so the three static trees are disjoint on one origin.
        ("/platform/assets", platform),
    ):
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
    for prefix, app_dir in (("/manage", manage), ("", storefront), ("/platform", platform)):
        if not app_dir.is_dir():
            # ⚠ THE THIRD APP IS ALLOWED TO BE ABSENT ON ITS OWN, and the two
            # above are not. The guard at the top of this function still boot-
            # fails to API-only when manage or storefront is missing, because
            # `railway up` shipping a deploy without a storefront is a dead
            # origin. A missing console is not: it costs the operator a screen
            # while every boutique keeps trading, so a partial copy degrades to
            # exactly what it copied instead of taking the other two down.
            continue
        for entry in sorted(app_dir.iterdir()):
            if entry.is_file() and entry.name != "index.html":
                _serve_file(app, f"{prefix}/{entry.name}", entry)

    # Exact path, no subtree: apps/manage has no client-side router (App.tsx
    # drives its sections from useState), so exactly one URL is the console and
    # a subtree fallback would invent deep links the app cannot restore.
    _serve_file(app, "/manage", manage / "index.html")
    # Same exact-path rule, same reason: apps/platform has one screen driven from
    # useState and no client router, so a subtree fallback would invent deep links
    # it cannot restore. `_serve_file` no-ops when the file is absent, which is
    # what makes the missing-console case degrade rather than raise.
    _serve_file(app, "/platform", platform / "index.html")
    # F26 D1. A SECOND exact path into the SAME bundle — not a subtree fallback,
    # for the rule above: apps/platform has no client router, so exactly two URLs
    # are screens and anything else must stay a 404. `App.tsx` branches on
    # `location.pathname` before its `me()` bootstrap, so this path renders the
    # join panel and never calls the console's auth.
    #
    # The alternatives were an apex that 404s by design, a tenant host that does
    # not exist until redemption succeeds, and a fourth workspace app for one
    # form (spec D1). This is one line.
    _serve_file(app, "/platform/join", platform / "index.html")

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
    if settings.sms_provider == "twilio":
        sender = TwilioSmsSender(settings)
        if sender.is_configured:
            logger.info("SMS sender: TWILIO — real sends from %s", sender.from_number)
        else:
            # Incomplete credentials degrade to the same 503 as no provider, so
            # without this line the only symptom is a silent boutique.
            logger.warning(
                "SMS sender: TWILIO selected but one or more TWILIO_* variables are "
                "missing — OTP send will answer 503 SMS_NOT_CONFIGURED"
            )
        return sender
    logger.info("SMS sender NOT configured — OTP send will answer 503 SMS_NOT_CONFIGURED")
    return UnconfiguredSmsSender()


def _build_payment_gateway(settings: Settings) -> PaymentGateway:
    """Mirrors _build_sms_sender: absence is a supported deployment that answers
    503, and Settings.model_config is extra="ignore" — so a typo'd
    PAYMENT_PROVDER degrades silently and this INFO line is what makes the
    degradation observable."""
    if settings.payment_provider == "fake":
        logger.info("payment gateway: FAKE (records, never charges) — no real money will move")
        return FakeGateway()
    if settings.payment_provider == "lemonsqueezy":
        # Names the adapter and nothing else — credentials are per-tenant and
        # never reach Settings, so there is nothing here to leak. "TEST MODE" is
        # in the line because it is the whole safety posture: production is a
        # boot failure and every checkout asserts test mode on both sides.
        logger.info(
            "payment gateway: %s (TEST MODE ONLY — never a production path)",
            LEMONSQUEEZY_PROVIDER,
        )
        return LemonSqueezyGateway()
    logger.info(
        "payment gateway NOT configured — gateway routes will answer 503 GATEWAY_NOT_CONFIGURED"
    )
    return UnconfiguredGateway()


def _build_secret_box(settings: Settings) -> SecretBox:
    """Its own builder, never folded into the one above (D1): which provider
    takes the money and which key manager protects the credential are orthogonal
    axes, and a deployment can legitimately have one without the other — which
    is exactly the misconfiguration the Settings validator boot-fails on."""
    if settings.gateway_secret_box == "fake":
        logger.info("secret box: FAKE (base64, NOT encryption) — never permitted in production")
        return FakeSecretBox()
    logger.info("secret box NOT configured — credential writes will answer 503")
    return UnconfiguredSecretBox()


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
        # F25's console-host fence. Settings validates the label is in
        # RESERVED_SLUGS at boot, so it can never collide with a boutique.
        platform_host_label=settings.platform_host_label,
    )
    # Added after (= runs before) tenant resolution: a cross-origin forgery is
    # rejected without touching the database.
    app.add_middleware(CsrfOriginMiddleware)
    # Added LAST = OUTERMOST, and that is the whole point: it is what puts the
    # headers on the TENANT_NOT_FOUND 404 that TenantResolutionMiddleware
    # returns from its own dispatch without reaching a handler.
    # The CSP is built HERE, from these Settings, because the media origin it
    # admits is a deployment fact — a deployment with no bucket gets a strictly
    # tighter policy rather than a broken one (D3).
    app.add_middleware(SecurityHeadersMiddleware, csp=build_csp(settings))

    app.state.auth_service = AuthService(get_session_factory(), settings)
    # No clock wired: the parameter exists so the db suite can freeze the
    # window, and production reads a real one (D8).
    app.state.dashboard_service = DashboardService(get_session_factory())
    # No clock wired, same as the dashboard: the parameter exists so the db suite
    # can freeze the break timestamp, and production reads a real one.
    app.state.floor_service = FloorService(get_session_factory())
    # F35's bell. A SEPARATE service on the same router: its two reads share no
    # repository with any floor verb, and the one place the features meet — the
    # unread count — lives on `FloorService.sos` precisely so it rides that
    # verb's existing session instead of opening a second one.
    app.state.notifications_service = NotificationsService(get_session_factory())
    # No clock: nothing the CRM answers is time-derived — the booking history is
    # ordered by starts_at with no window and the SMS log has no band.
    app.state.customers_service = CustomersService(get_session_factory())
    # No clock: `erased_at`, the withdrawal stamp and the live-booking guard
    # are all `func.now()` INSIDE the erase transaction, so they share the
    # statement's own instant and no injected clock could make them agree more.
    #
    # THREE LIMITER INSTANCES, one per subject route, never one with three
    # keys: `max_attempts` is per instance, so a shared limiter would give all
    # three routes a single ceiling and let a morning of lookups lock out the
    # erase they were leading to. Their budgets are module constants rather
    # than Settings — see `privacy/validation.py` for why.
    app.state.privacy_service = PrivacyService(
        get_session_factory(),
        export_limiter=FixedWindowRateLimiter(
            max_attempts=SUBJECT_EXPORT_MAX_PER_WINDOW,
            window_seconds=SUBJECT_EXPORT_WINDOW_SECONDS,
            clock=time.monotonic,
        ),
        erase_limiter=FixedWindowRateLimiter(
            max_attempts=SUBJECT_ERASE_MAX_PER_WINDOW,
            window_seconds=SUBJECT_ERASE_WINDOW_SECONDS,
            clock=time.monotonic,
        ),
        withdraw_limiter=FixedWindowRateLimiter(
            max_attempts=MARKETING_WITHDRAW_MAX_PER_WINDOW,
            window_seconds=MARKETING_WITHDRAW_WINDOW_SECONDS,
            clock=time.monotonic,
        ),
    )
    # No clock wired, same as the dashboard and the floor: the parameter exists
    # so the db suite can freeze `today_jerusalem` — which the overdue flag, the
    # delivered window and the due-date horizon all read — and production reads a
    # real one.
    app.state.atelier_service = AtelierService(get_session_factory())
    # F39. No clock wired either, and for the same reason plus one: the db suite
    # freezes it to drive the deadline boundary one second either side, and
    # `today_jerusalem` decides which week is «current» for D1's whole window.
    app.state.shifts_service = ShiftsService(get_session_factory())
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=settings.login_max_attempts,
        window_seconds=settings.login_window_seconds,
        clock=time.monotonic,
    )
    # F25's console. Its OWN service beside the staff one — the two auth
    # populations never share a lookup path (spec D3), and folding operators into
    # AuthService would put a tenant predicate one refactor away from the
    # platform's front door.
    app.state.platform_auth_service = OperatorAuthService(get_session_factory(), settings)
    # THE SAME CLASS THE CLI HAS ALWAYS CALLED, unchanged (pre-decided #20). It
    # owns its own audit rows — the failure ones included — which is why the
    # console's router validates nothing the service already validates.
    app.state.provisioning_service = ProvisioningService(get_session_factory())
    # ⚠ ITS OWN LIMITER INSTANCE, and this is the SIXTH time this file states the
    # rule: max_attempts lives on the LIMITER, so a key on `login_rate_limiter`
    # above would give the console the staff ceiling — one tenant's brute-force
    # could then close the platform's front door, and a console lockout could
    # close a boutique's. Two budgets, two instances
    # (`.memory/limiter-max-is-per-instance`).
    app.state.platform_login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=settings.platform_login_max_attempts,
        window_seconds=settings.platform_login_window_seconds,
        clock=time.monotonic,
    )
    # …and a THIRD instance for the same reason, not a key on the one above: the
    # global arm's ceiling has to be an order of magnitude wider than the
    # per-email one, and `max_attempts` lives on the LIMITER. Sharing would give
    # every email address the flood ceiling.
    app.state.platform_login_global_rate_limiter = FixedWindowRateLimiter(
        max_attempts=settings.platform_login_global_max_attempts,
        window_seconds=settings.platform_login_window_seconds,
        clock=time.monotonic,
    )
    # F26's anonymous join surface, and this is the SEVENTH statement of the same
    # rule: max_attempts lives on the LIMITER, so a key on either limiter above
    # would give signup the console login's ceiling — a flood of bad invite codes
    # could then close the platform's front door, and a console lockout could
    # close signup. Two budgets, two instances
    # (`.memory/limiter-max-is-per-instance`).
    #
    # What it protects is `platform_audit_log`: every refusal on the join routes
    # writes an INSERT-only row that no retention policy prunes, so an unmetered
    # anonymous surface can permanently fill a table the app can neither read nor
    # delete from. Failures only, so an owner redeeming her own link never
    # throttles herself.
    app.state.invite_redeem_rate_limiter = FixedWindowRateLimiter(
        max_attempts=settings.invite_redeem_max_attempts,
        window_seconds=settings.invite_redeem_window_seconds,
        clock=time.monotonic,
    )
    # …and a fourth instance for the global arm, not a key on the one above: its
    # ceiling has to be an order of magnitude wider, and `max_attempts` lives on
    # the LIMITER. Sharing would give every single code the flood ceiling.
    app.state.invite_redeem_global_rate_limiter = FixedWindowRateLimiter(
        max_attempts=settings.invite_redeem_global_max_attempts,
        window_seconds=settings.invite_redeem_window_seconds,
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
    # Its own service beside the auth one, never methods on it: AuthService
    # verifies credentials and issues sessions, and folding administration in
    # would put the login path's fake into every staff CRUD test.
    #
    # Constructed HERE and not up with auth_service, because F38 gave it the
    # storage port: offboarding deletes the leaver's photo object. The
    # dependency is required rather than defaulted, so this ordering is a boot
    # failure if it ever regresses rather than a silent bucket leak.
    app.state.staff_service = StaffService(
        get_session_factory(),
        media_storage=app.state.media_storage,
        # A SEPARATE instance from the catalog's below, and the separation is the
        # whole point: `max_attempts` lives on the limiter, so two keys sharing
        # one instance share one ceiling — a morning of dress-gallery uploads
        # would then 429 an owner trying to set one avatar. Same env knobs,
        # because the budgets are the same SHAPE even though they must not be
        # the same bucket.
        presign_rate_limiter=FixedWindowRateLimiter(
            max_attempts=settings.media_presign_max_per_window,
            window_seconds=settings.media_presign_window_seconds,
            clock=time.monotonic,
        ),
    )
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
    # ⚠ HOISTED ABOVE StorefrontService AND BookingService, DELIBERATELY, and the
    # order IS the feature. `deposit_due()` is
    #     deposits_enabled AND deposit_required AND amount > 0 AND gateway_connected
    # and both of those services take `gateway_credentials` as an OPTIONAL argument
    # defaulting to None, which reads as NOT CONNECTED. Built before this block, they
    # silently took that default and every deposit in the product became
    # uncollectable — the storefront disclosed none and POST /storefront/bookings
    # answered `deposit_due: false` with a gateway connected AND validated. It failed
    # in the safe direction, so nothing alerted; found only by walking the journey
    # against a real database (2026-08-10). `tests/test_deposit_wiring.py` asserts the
    # object graph so a future reordering reds instead of going quiet.
    app.state.payment_gateway = _build_payment_gateway(settings)
    app.state.secret_box = _build_secret_box(settings)
    # TWO limiter instances, not one with two keys. max_attempts lives on the
    # LIMITER, so a second key on an existing budget could never trip first —
    # the rule main.py states four times above. The connect budget exists for a
    # stronger reason than the validate one: rotation is insert-only on a table
    # whose DELETE is revoked (D6, D7), so a loop on PUT is permanent,
    # unreclaimable table growth plus unbounded KMS request spend. Verbatim why
    # terms_creation_max_per_window exists.
    app.state.gateway_credential_service = GatewayCredentialService(
        get_session_factory(),
        gateway=app.state.payment_gateway,
        secret_box=app.state.secret_box,
        connect_limiter=FixedWindowRateLimiter(
            max_attempts=settings.gateway_connect_max_per_tenant_window,
            window_seconds=settings.gateway_connect_window_seconds,
            clock=time.monotonic,
        ),
        validate_limiter=FixedWindowRateLimiter(
            max_attempts=settings.gateway_validate_max_per_tenant_window,
            window_seconds=settings.gateway_validate_window_seconds,
            clock=time.monotonic,
        ),
    )

    app.state.storefront_service = StorefrontService(
        get_session_factory(),
        media_storage=app.state.media_storage,
        # The disclosure half of deposit_due(): without this the storefront hides
        # every deposit, whatever the boutique has configured.
        gateway_credentials=app.state.gateway_credential_service,
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
        # ⚠ ITS OWN INSTANCE, beside phone_limiter and tenant_limiter and never a
        # third key on either: max_attempts lives on the LIMITER, so two keys
        # sharing one instance share one ceiling
        # (.memory/limiter-max-is-per-instance).
        ip_limiter=FixedWindowRateLimiter(
            max_attempts=settings.otp_send_max_per_ip_window,
            window_seconds=settings.otp_send_ip_window_seconds,
            clock=time.monotonic,
        ),
        dev_code=settings.otp_dev_code,
    )
    app.state.booking_service = BookingService(
        get_session_factory(),
        otp=app.state.otp_service,
        # The USE half of deposit_due(). It must be the SAME instance the
        # storefront holds, or the page she reads and the flow she enters could
        # disagree about whether money is owed.
        gateway_credentials=app.state.gateway_credential_service,
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
    # F22's join. The OTP service is the SAME instance the booking flow spends
    # — correct, not accidental (D3): one phone proving itself is one proof,
    # whichever flow consumes it, and a second send budget would double the
    # SMS-cost exposure per phone. The join's own budgets are TWO OWN limiter
    # instances, the rule this file has now stated five times: max_attempts
    # lives on the LIMITER, so a key on booking-create's budget would let a
    # waitlist rush close the booking flow — and vice versa.
    app.state.waitlist_service = WaitlistService(
        get_session_factory(),
        otp=app.state.otp_service,
        phone_limiter=FixedWindowRateLimiter(
            max_attempts=settings.waitlist_join_max_per_phone_window,
            window_seconds=settings.waitlist_join_phone_window_seconds,
            clock=time.monotonic,
        ),
        tenant_limiter=FixedWindowRateLimiter(
            max_attempts=settings.waitlist_join_max_per_tenant_window,
            window_seconds=settings.waitlist_join_tenant_window_seconds,
            clock=time.monotonic,
        ),
    )
    # F24's portal. The OTP service is the SAME instance the booking and waitlist
    # flows use — deliberately (spec D3): the metered resource on send/verify is
    # the SMS spend and the guess surface, which is identical whichever flow
    # asks, and the same person logging in and booking is one actor on one phone.
    # The MINT brake is its own instance, the rule this file has now stated six
    # times: max_attempts lives on the LIMITER, so a key on an existing budget
    # would hand this path somebody else's ceiling.
    app.state.portal_service = PortalService(
        get_session_factory(),
        otp=app.state.otp_service,
        mint_limiter=FixedWindowRateLimiter(
            max_attempts=settings.portal_login_max_per_tenant_window,
            window_seconds=settings.portal_login_window_seconds,
            clock=time.monotonic,
        ),
        session_ttl_seconds=settings.portal_session_ttl_seconds,
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
    # F33's walk-in queue and F59's wall board. FOUR limiter instances, and the
    # rule this file has already stated four times is the reason: max_attempts
    # lives on the LIMITER, so a second key on an existing budget could never
    # trip first. Concretely, reusing the OTP budgets would let a bride-heavy
    # morning close the door queue (and the per-phone half answers a spent
    # allowance with a silent 204, so the failure would be invisible); reusing
    # booking-create's would let a morning of walk-ins close the front door;
    # reusing the storefront read brake would let one leaked position-poll loop
    # 429 the catalog for every shopper on the site.
    #
    # All four live here rather than on app.state because only the service has
    # what their keys need — the parsed body for the ticket key, the lookup
    # result for the miss key — which is also what keeps the queue router at
    # dependencies=[Depends(_no_store)], byte-identical in posture to the OTP
    # and booking siblings.
    app.state.queue_service = QueueService(
        get_session_factory(),
        create_limiter=FixedWindowRateLimiter(
            max_attempts=settings.checkin_create_max_per_window,
            window_seconds=settings.checkin_create_window_seconds,
            clock=time.monotonic,
        ),
        # Its own instance again. Keyed on the ticket id the caller already
        # holds, so a 429 on it discloses nothing.
        position_ticket_limiter=FixedWindowRateLimiter(
            max_attempts=settings.checkin_position_max_per_ticket_window,
            window_seconds=settings.checkin_position_ticket_window_seconds,
            clock=time.monotonic,
        ),
        # And a third. Sharing this one with the ticket budget above would give
        # the ticket key the miss ceiling and the two would trip each other —
        # which is the same rule, stated for the case where it is least obvious
        # because both keys belong to the same feature.
        position_miss_limiter=FixedWindowRateLimiter(
            max_attempts=settings.checkin_position_max_misses_per_window,
            window_seconds=settings.checkin_position_miss_window_seconds,
            clock=time.monotonic,
        ),
        # And a fourth, for the public wall board. Not any of the three above,
        # and the create budget is the vivid case: one wall screen polling every
        # five seconds is 720 reads an hour, 3.6x that ENTIRE ceiling, spent
        # about seventeen minutes into the shop day — after which the wall
        # screen answers 429 to every woman scanning the QR at the door. The
        # ticket budget is sized for one client holding one ticket, so a
        # per-tenant board key trips it at three screens; the miss brake is the
        # trap the comment above names in writing.
        #
        # Its ceiling is a DIFFERENT number from the miss brake's rather than
        # the same one, deliberately: a limiter ceiling is sized by traffic, and
        # this key aggregates every screen in the shop plus every phone in the
        # room. config.py carries that arithmetic; the "same shape, different
        # instance" lesson is the comment above, not a number.
        board_limiter=FixedWindowRateLimiter(
            max_attempts=settings.queue_board_max_per_window,
            window_seconds=settings.queue_board_window_seconds,
            clock=time.monotonic,
        ),
    )
    # base_domain, not the request's own host: the URL a poster carries has to
    # resolve to the tenant's own storefront in dev, staging and production
    # alike, and Settings is where deployment identity lives. Its own service
    # rather than a method on QueueService above — it needs no session factory,
    # no limiter and no clock, and threading base_domain through the anonymous
    # surface's service to reach a /manage read would be the larger change.
    app.state.checkin_qr_service = CheckinQrService(base_domain=settings.base_domain)

    # F19 is the consumer the comment that used to sit here was waiting for.
    # PaymentService stays the single writer of `payments`; the booking-side
    # half is DepositBookingService, and the two are separate because
    # settle_from_webhook and honour_late_settlement each state in their own
    # docstrings that they do not touch `bookings` — a seat decision needs the
    # advisory lock and the occupancy reads that live in the booking domain.
    app.state.payment_service = PaymentService(
        get_session_factory(),
        gateway=app.state.payment_gateway,
        credentials=app.state.gateway_credential_service,
    )
    app.state.deposit_booking_service = DepositBookingService(
        get_session_factory(),
        payments=app.state.payment_service,
        credentials=app.state.gateway_credential_service,
        comms=app.state.booking_comms_service,
    )
    # Built unconditionally, REGISTERED conditionally: the guard is one place
    # (register_fake_pay), and two references cost nothing on a deployment that
    # never routes to them. F18 deletes this line with the module.
    app.state.fake_pay_service = FakePayService(
        get_session_factory(), credentials=app.state.gateway_credential_service
    )

    # F23's offer claim, built HERE rather than beside its waitlist siblings
    # because it needs `gateway_credential_service`, which the payments block
    # above constructs.
    #
    # F23's offer claim. NO otp service at all: possession of a token texted to
    # her phone is the proof, the same posture as `/b/{token}`. Its anti-scrape
    # budget is a SEVENTH own instance, the rule this file keeps restating —
    # max_attempts lives on the LIMITER, so a key on the join's budget would let
    # a waitlist rush close the offer surface and vice versa.
    app.state.waitlist_offer_service = WaitlistOfferService(
        get_session_factory(),
        lookup_limiter=FixedWindowRateLimiter(
            max_attempts=settings.waitlist_offer_lookup_max_per_window,
            window_seconds=settings.waitlist_offer_lookup_window_seconds,
            clock=time.monotonic,
        ),
        gateway_credentials=app.state.gateway_credential_service,
    )

    @app.exception_handler(TenantNotResolvedError)
    async def _tenant_not_resolved(request: Request, exc: TenantNotResolvedError) -> JSONResponse:
        # Same body as every other resolution failure — no distinguishable 404s.
        return JSONResponse(TENANT_NOT_FOUND_BODY, status_code=404)

    # ⚠ THE UNROUTED 404, and it is registered by STATUS CODE rather than by
    # exception type. Starlette raises its own `HTTPException(404)` from the
    # router when nothing matched, and answered `{"detail": "Not Found"}` — while
    # every HANDLED error below is `{"error": {code, message}}`. Both frontends
    # read `response.data.error.message` (FRONTEND.md mandates it, and each
    # `api.ts`'s `errorMessage()` is built on it), so `error` was undefined here
    # and every stale-URL 404 reached the user as the generic fallback string.
    #
    # ⚠ It cannot swallow the SPA catch-all or the exact `/manage` route: both
    # are real routes that MATCH, so no 404 is ever raised for them. Nor the
    # 405s — `_SpaFallbackRoute.matches` declines EXEMPT_PATHS and the reserved
    # segments before a method is looked at, leaving the partial match to raise
    # 405 and not 404. `test_spa_serving.py` pins all three.
    #
    # ⚠ NOT registered for `StarletteHTTPException` generally: that would also
    # capture the 405 and every other status Starlette raises, which is exactly
    # the collapse this app has spent nine handlers avoiding.
    @app.exception_handler(404)
    async def _unrouted(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(NOT_FOUND_BODY, status_code=404)

    @app.exception_handler(InvalidCredentialsError)
    async def _invalid_credentials(request: Request, exc: InvalidCredentialsError) -> JSONResponse:
        # One body for wrong-password AND unknown-email — no account enumeration.
        return JSONResponse(INVALID_CREDENTIALS_BODY, status_code=401)

    # F25 D5. ONE handler for all five console refusals: the console branches on
    # the CODE STRING, so five exception classes would be five places to forget
    # the next one. The code is the service's own message verbatim — an unmapped
    # message arrives as itself at 400 rather than as a 500 or as somebody else's
    # refusal.
    @app.exception_handler(ConsoleCommandRefused)
    async def _console_refused(request: Request, exc: ConsoleCommandRefused) -> JSONResponse:
        return JSONResponse(
            {
                "error": {
                    "code": exc.code,
                    # English, and it is never what an operator reads: the console
                    # owns the Hebrew per code (design deck §6) and falls through
                    # to its own generic sentence for anything unlisted.
                    "message": "The platform refused that command.",
                }
            },
            status_code=exc.status,
        )

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

    @app.exception_handler(ReservationOverlapError)
    async def _reservation_overlap(request: Request, exc: ReservationOverlapError) -> JSONResponse:
        return JSONResponse(
            _body_with_details(RESERVATION_OVERLAP_BODY, exc.details), status_code=409
        )

    # F39's five. `WEEK_OUT_OF_RANGE` and `TEMPLATE_LIMIT_REACHED` are 400s —
    # the request is malformed against the server's rules. The other three are
    # 409s: the body is well-formed and conflicts with server state.
    @app.exception_handler(WeekOutOfRangeError)
    async def _week_out_of_range(request: Request, exc: WeekOutOfRangeError) -> JSONResponse:
        return JSONResponse(WEEK_OUT_OF_RANGE_BODY, status_code=400)

    @app.exception_handler(TemplateLimitReachedError)
    async def _template_limit(request: Request, exc: TemplateLimitReachedError) -> JSONResponse:
        return JSONResponse(TEMPLATE_LIMIT_REACHED_BODY, status_code=400)

    # F40's, and it lands here with its error class rather than with its route:
    # a coded error shipped without its own handler answers a quiet, plausible
    # VALIDATION_ERROR 400 that the console has no Hebrew string for.
    @app.exception_handler(CoverageTargetInvalidError)
    async def _coverage_target(request: Request, exc: CoverageTargetInvalidError) -> JSONResponse:
        return JSONResponse(COVERAGE_TARGET_INVALID_BODY, status_code=400)

    # F40's other three. `NOT_SHIFT_MANAGER_ELIGIBLE` is a 400 — the request is
    # malformed against the server's rules. The other two are 409s: the body is
    # well-formed and conflicts with server state.
    @app.exception_handler(NotShiftManagerEligibleError)
    async def _not_eligible(request: Request, exc: NotShiftManagerEligibleError) -> JSONResponse:
        return JSONResponse(NOT_SHIFT_MANAGER_ELIGIBLE_BODY, status_code=400)

    @app.exception_handler(AvailabilityConflictError)
    async def _availability_conflict(
        request: Request, exc: AvailabilityConflictError
    ) -> JSONResponse:
        return JSONResponse(AVAILABILITY_CONFLICT_BODY, status_code=409)

    @app.exception_handler(ShiftManagerSlotTakenError)
    async def _manager_slot_taken(
        request: Request, exc: ShiftManagerSlotTakenError
    ) -> JSONResponse:
        return JSONResponse(SHIFT_MANAGER_SLOT_TAKEN_BODY, status_code=409)

    @app.exception_handler(SubmissionClosedError)
    async def _submission_closed(request: Request, exc: SubmissionClosedError) -> JSONResponse:
        return JSONResponse(SUBMISSION_CLOSED_BODY, status_code=409)

    @app.exception_handler(TemplatesAlreadySeededError)
    async def _templates_seeded(request: Request, exc: TemplatesAlreadySeededError) -> JSONResponse:
        return JSONResponse(TEMPLATES_ALREADY_SEEDED_BODY, status_code=409)

    @app.exception_handler(NoOpeningHoursError)
    async def _no_opening_hours(request: Request, exc: NoOpeningHoursError) -> JSONResponse:
        return JSONResponse(NO_OPENING_HOURS_BODY, status_code=409)

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

    @app.exception_handler(DressUnavailableError)
    async def _dress_unavailable(request: Request, exc: DressUnavailableError) -> JSONResponse:
        return JSONResponse(DRESS_UNAVAILABLE_BODY, status_code=409)

    @app.exception_handler(TermsStaleError)
    async def _terms_stale(request: Request, exc: TermsStaleError) -> JSONResponse:
        return JSONResponse(TERMS_STALE_BODY, status_code=409)

    # Its own class like the other three throttles; the F21 reparenting note
    # on StorefrontThrottledError covers this one too.
    @app.exception_handler(BookingThrottledError)
    async def _booking_throttled(request: Request, exc: BookingThrottledError) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    # F23's offer claim losing a race, or reaching a row that has already moved.
    # The SAME body a direct booker gets — she is owed the outcome, not a report
    # on which internal transition beat her, and a new code here would be an
    # oracle over the waitlist's internals on an anonymous route.
    @app.exception_handler(OfferNotClaimableError)
    async def _offer_not_claimable(request: Request, exc: OfferNotClaimableError) -> JSONResponse:
        return JSONResponse(SLOT_UNAVAILABLE_BODY, status_code=409)

    # F22's join budgets — its own class for the reason the four above are four.
    # F23's offer surface shares the CLASS (one 429 body, no new code) while
    # keeping its own limiter INSTANCE, which is the part that matters.
    @app.exception_handler(WaitlistThrottledError)
    async def _waitlist_throttled(request: Request, exc: WaitlistThrottledError) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    # F24's mint brake — its own class for the reason the five above are five.
    @app.exception_handler(PortalThrottledError)
    async def _portal_throttled(request: Request, exc: PortalThrottledError) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    # 404 with its own code, for BOOKING_LINK_INVALID's reason one surface over:
    # the login panel renders a state off it and NOT_FOUND would collapse into
    # every other 404 on the origin.
    @app.exception_handler(PortalNoBookingsError)
    async def _portal_no_bookings(request: Request, exc: PortalNoBookingsError) -> JSONResponse:
        return JSONResponse(PORTAL_NO_BOOKINGS_BODY, status_code=404)

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

    @app.exception_handler(BookingAwaitingPaymentError)
    async def _booking_awaiting_payment(
        request: Request, exc: BookingAwaitingPaymentError
    ) -> JSONResponse:
        # 409, the same class as every other refused verb on the bride's page.
        # Without this registration the guard added in F19 A2 is an unhandled
        # 500 on the tokenized page — a worse outcome than the bug it fixes.
        return JSONResponse(BOOKING_AWAITING_PAYMENT_BODY, status_code=409)

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

    # F17's payment errors. Deliberately NOT registered here:
    # GatewayNotFoundError subclasses DomainNotFoundError and is bound to the
    # base above, and a bad credential shape is a DomainValidationError. Listing
    # them would be a second, drifting spelling of the same binding — the F51
    # note on DuplicateEmailError makes the same point.
    #
    # Raised by app/payments/, same containment as the media and SMS pairs: no
    # provider name, merchant identifier or field value ever reaches a body.
    @app.exception_handler(GatewayNotConfiguredError)
    async def _gateway_not_configured(
        request: Request, exc: GatewayNotConfiguredError
    ) -> JSONResponse:
        return JSONResponse(GATEWAY_NOT_CONFIGURED_BODY, status_code=503)

    # The SAME code and body (D18): one operational fact to the owner
    # ("deposits are unavailable") and one remedy (contact the operator). A
    # second wire code for one fact is what booking-comms D10 declined as "a
    # fourth spelling of too many attempts". The two stay distinguishable
    # server-side, which is where the difference matters.
    @app.exception_handler(SecretBoxNotConfiguredError)
    async def _secret_box_not_configured(
        request: Request, exc: SecretBoxNotConfiguredError
    ) -> JSONResponse:
        return JSONResponse(GATEWAY_NOT_CONFIGURED_BODY, status_code=503)

    # 409, not 503: the platform is fine — THIS boutique has no valid
    # credentials, and she is the one who can fix it.
    @app.exception_handler(GatewayNotConnectedError)
    async def _gateway_not_connected(
        request: Request, exc: GatewayNotConnectedError
    ) -> JSONResponse:
        return JSONResponse(GATEWAY_NOT_CONNECTED_BODY, status_code=409)

    # 400, not 409: the request is well-formed but its CONTENT is wrong, and the
    # owner's remedy is to retype it — the reading MediaMismatchError applies in
    # reverse.
    @app.exception_handler(GatewayCredentialsRejectedError)
    async def _gateway_credentials_rejected(
        request: Request, exc: GatewayCredentialsRejectedError
    ) -> JSONResponse:
        return JSONResponse(GATEWAY_CREDENTIALS_REJECTED_BODY, status_code=400)

    @app.exception_handler(GatewayUnavailableError)
    async def _gateway_unavailable(request: Request, exc: GatewayUnavailableError) -> JSONResponse:
        return JSONResponse(GATEWAY_UNAVAILABLE_BODY, status_code=503)

    # A blob we cannot open is operationally identical to an unreachable
    # provider — deposits are temporarily unavailable and the remedy is the
    # operator's. It deliberately does NOT flip the credential to 'invalid'; see
    # GatewayCredentialService._decrypt.
    @app.exception_handler(SecretDecryptError)
    async def _secret_decrypt_failed(request: Request, exc: SecretDecryptError) -> JSONResponse:
        return JSONResponse(GATEWAY_UNAVAILABLE_BODY, status_code=503)

    # 400, NEVER 503 (D25). An HMAC mismatch is an authentication failure, not a
    # provider outage: 503 invites a retry of the forgery, buries the event among
    # real outages in logs and alerting, and leaves the checklist row "webhook
    # signature verification + replay protection" unprovable from outside. F19
    # owns the webhook route; F17 owns the error that makes 400 the only sane
    # mapping.
    @app.exception_handler(GatewayWebhookInvalidError)
    async def _gateway_webhook_invalid(
        request: Request, exc: GatewayWebhookInvalidError
    ) -> JSONResponse:
        return JSONResponse(GATEWAY_WEBHOOK_INVALID_BODY, status_code=400)

    # 409, not 400: the request is well-formed — the booking's existing hold is
    # what refuses it. Mapped exactly as SlotUnavailableError maps the slot-seat
    # collision, so a lost race is never an unhandled 500 (D23).
    @app.exception_handler(PaymentAlreadyHeldError)
    async def _payment_already_held(request: Request, exc: PaymentAlreadyHeldError) -> JSONResponse:
        return JSONResponse(PAYMENT_ALREADY_HELD_BODY, status_code=409)

    # F36's two. 409, not 400: the request is well-formed — a partial unique
    # index refused it, and the ruling requires the body to NAME the current
    # occupant. `message` is English prose the console never renders for a MAPPED
    # code, so the datum has to travel in `details` or the UI cannot reach it.
    @app.exception_handler(RoomOccupiedError)
    async def _room_occupied(request: Request, exc: RoomOccupiedError) -> JSONResponse:
        return JSONResponse(_body_with_details(ROOM_OCCUPIED_BODY, exc.details), status_code=409)

    @app.exception_handler(StaffOccupiedError)
    async def _staff_occupied(request: Request, exc: StaffOccupiedError) -> JSONResponse:
        return JSONResponse(_body_with_details(STAFF_OCCUPIED_BODY, exc.details), status_code=409)

    # F37's two, and BOTH blocks are required rather than one on the shared base:
    # this module registers a handler PER CONCRETE CLASS and there is no
    # `_DetailedConflictError` handler anywhere. A missing block does not fall
    # back to a generic 409 — it answers 500.
    #
    # SOS_ALREADY_ACCEPTED carries `details` when there is somebody to name and
    # omits the key when there is not; SOS_CLOSED never carries it and is not
    # even routed through the `details` argument, so the asymmetry is visible in
    # the code rather than only in a comment.
    @app.exception_handler(SosAlreadyAcceptedError)
    async def _sos_already_accepted(request: Request, exc: SosAlreadyAcceptedError) -> JSONResponse:
        return JSONResponse(
            _body_with_details(SOS_ALREADY_ACCEPTED_BODY, exc.details), status_code=409
        )

    @app.exception_handler(SosClosedError)
    async def _sos_closed(request: Request, exc: SosClosedError) -> JSONResponse:
        return JSONResponse(SOS_CLOSED_BODY, status_code=409)

    @app.exception_handler(QueueEmptyError)
    async def _queue_empty(request: Request, exc: QueueEmptyError) -> JSONResponse:
        return JSONResponse(QUEUE_EMPTY_BODY, status_code=409)

    # F58's other two. Registered separately even though both subclass
    # `_DetailedConflictError`: Starlette resolves on the MRO, so a handler on the shared
    # base would answer both with one code and there would be no way to tell
    # «היא כבר בטיפול.» from «מצב הכניסה השתנה. רענני ונסי שוב.» — two causes, two
    # remedies, the argument that split ROOM_OCCUPIED from STAFF_OCCUPIED.
    @app.exception_handler(QueueTicketNotWaitingError)
    async def _ticket_not_waiting(
        request: Request, exc: QueueTicketNotWaitingError
    ) -> JSONResponse:
        return JSONResponse(
            _body_with_details(QUEUE_TICKET_NOT_WAITING_BODY, exc.details), status_code=409
        )

    @app.exception_handler(QueueTicketChangedError)
    async def _ticket_changed(request: Request, exc: QueueTicketChangedError) -> JSONResponse:
        return JSONResponse(
            _body_with_details(QUEUE_TICKET_CHANGED_BODY, exc.details), status_code=409
        )

    # 409, not 400: both requests are well-formed — a CONCURRENT WRITER is what
    # refuses them, and each names a different one. F41's only two new codes;
    # `AtelierValidationError` needs no handler at all because it subclasses
    # DomainValidationError, and a missing ticket rides DomainNotFoundError.
    @app.exception_handler(TicketStageConflictError)
    async def _ticket_stage_conflict(
        request: Request, exc: TicketStageConflictError
    ) -> JSONResponse:
        return JSONResponse(TICKET_STAGE_CONFLICT_BODY, status_code=409)

    @app.exception_handler(TicketAlreadyAssignedError)
    async def _ticket_already_assigned(
        request: Request, exc: TicketAlreadyAssignedError
    ) -> JSONResponse:
        return JSONResponse(TICKET_ALREADY_ASSIGNED_BODY, status_code=409)

    # Its own class like the other four throttles; the F21 reparenting note on
    # StorefrontThrottledError covers this one too.
    @app.exception_handler(GatewayThrottledError)
    async def _gateway_throttled(request: Request, exc: GatewayThrottledError) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    # The TENTH handler returning this same shared body, and F33's only new
    # handler: QueueTicketNotFoundError inherits DomainNotFoundError, so the 404
    # needs none. One class for all three check-in budgets, because all three
    # keys are about a boutique or about a ticket the caller already holds and
    # none is about a person — which is what makes one shared 429 safe here
    # where the OTP surface needed two different answers. No Retry-After: the
    # shared body names no duration, every window is a Settings field so it can
    # change without a deploy, and a header naming a wait would contradict the
    # next .env edit. The F21 reparenting note on StorefrontThrottledError
    # covers this one too.
    @app.exception_handler(CheckinThrottledError)
    async def _checkin_throttled(request: Request, exc: CheckinThrottledError) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    @app.exception_handler(PrivacyThrottledError)
    async def _privacy_throttled(request: Request, exc: PrivacyThrottledError) -> JSONResponse:
        return JSONResponse(TOO_MANY_ATTEMPTS_BODY, status_code=429)

    @app.exception_handler(SubjectHasActiveBookingError)
    async def _subject_has_booking(
        request: Request, exc: SubjectHasActiveBookingError
    ) -> JSONResponse:
        return JSONResponse(SUBJECT_HAS_ACTIVE_BOOKING_BODY, status_code=409)

    app.include_router(health_router)
    app.include_router(auth_router)
    # F25's console auth, and it is deliberately NOT under /manage: the tenancy
    # middleware fences /platform* to the console host in both directions, and a
    # /manage prefix would put the platform's front door behind a tenant's
    # hostname. Registered beside the staff auth router so the two doors sit
    # together and neither can silently shadow the other — different prefixes, so
    # there is nothing to shadow, which is the point.
    app.include_router(platform_auth_router)
    # The console's four lifecycle routes, on the same fenced prefix.
    app.include_router(platform_router)
    # F26's three operator invite routes. Its own APIRouter only because the
    # prefix differs; the operator gate is declared the same way, on the router.
    app.include_router(platform_invites_router)
    # ⚠ AND THE ANONYMOUS PAIR, from its OWN module (spec D6). Two routers under
    # one prefix is the whole design: an operator route cannot lose its gate, and
    # a join route cannot acquire one, by anybody editing a shared dependency
    # list. `test_staff_role_gating` names both of these in its allowlist with a
    # written justification, so a THIRD anonymous /platform route is a deliberate
    # act rather than a diff nobody re-read.
    app.include_router(platform_join_router)
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
    # F39's shifts. Mounted after the staff router (spec D7) and carrying the
    # same shadowing warning every /manage include carries — a duplicated
    # (method, path) would silently win or lose on include order, and
    # `test_shifts_api.py`'s ROUTES table plus
    # `test_no_route_is_registered_twice_across_routers` are what keep that
    # honest. It is the SECOND router whose gate admits more than two roles;
    # `test_staff_role_gating.py`'s per-role reach equalities are what make that
    # safe, and both halves ship in this commit or neither should.
    app.include_router(shifts_router)
    # The sixth /manage router, after the staff one. Same hazard, now with six
    # surfaces on one prefix: a duplicated (method, path) would silently shadow
    # whichever was included first. The ROUTES table in test_dashboard_api.py is
    # what keeps that honest for this one.
    app.include_router(dashboard_router)
    # F57's floor. The SEVENTH router carrying prefix="/manage" exactly, and the
    # ONLY one whose gate admits more than two roles — require_role(*StaffRole),
    # spelled from the enum. That is safe only because
    # test_the_floor_roles_reach_exactly_the_floor_routes pins the three floor
    # roles out of every other /manage route; the two ship together or neither
    # should. Same shadowing hazard as the six above: the ROUTES table in
    # test_floor_api.py is what keeps this one honest.
    app.include_router(floor_router)
    # The next one, after the floor. Same hazard again. Same hazard again, and the ROUTES
    # table in test_payments_api.py is what keeps it honest — plus
    # test_staff_role_gating.py imports that table, so these four rows also get
    # a real end-to-end 403 assertion rather than only the structural one.
    app.include_router(gateway_router)
    # The EIGHTH, after the gateway one. Same hazard again, now with eight
    # surfaces on one prefix: a duplicated (method, path) would silently shadow
    # whichever was included first. The ROUTES table in test_customers_api.py is
    # what keeps that honest for these three.
    app.include_router(customers_router)
    # F20's privacy surface, the ELEVENTH /manage router and still ahead of
    # every anonymous one. Same shadowing hazard as the ten above — a
    # duplicated (method, path) would silently win or lose on include order
    # with no error at all — and PRIVACY_ROUTES in test_privacy_api.py is what
    # keeps these five honest. It is also the only /manage router with a route
    # deliberately LEFT at the router gate while its siblings tighten
    # (marketing-withdraw, Gate 1 Q4), which is why
    # test_staff_role_gating.py grew a positive absence assertion for it.
    app.include_router(privacy_router)
    # F22's console waitlist — the next /manage router, after the privacy one,
    # still contiguous with its siblings and ahead of every anonymous surface.
    # Same shadowing hazard; the manage walk in test_waitlist_api.py keeps its
    # two routes honest.
    app.include_router(waitlist_manage_router)
    # The NINTH /manage router, after the customers one and deliberately BEFORE
    # storefront_router: every /manage router stays contiguous and ahead of the
    # anonymous surfaces. Same shadowing hazard as the eight above, now with
    # nine surfaces on one prefix — the ROUTES table in test_checkin_qr_api.py
    # is what keeps this one honest.
    app.include_router(queue_manage_router)
    # F41's atelier. The TENTH /manage router, after the queue one and
    # deliberately BEFORE storefront_router: every /manage router stays
    # contiguous and ahead of the anonymous surfaces. Same shadowing hazard as
    # the nine above, now with ten surfaces on one prefix — a duplicated
    # (method, path) would silently win or lose on include order with no error at
    # all, and the ATELIER_ROUTES table in test_atelier_api.py is what keeps
    # these seven honest. It is also the only /manage router whose gate names
    # `seamstress`, which is why test_staff_role_gating.py's walker became a
    # per-role set equality in the same PR.
    app.include_router(atelier_router)
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
    # F22's join — the SIXTH /storefront sibling, after the booking router it is
    # F13's create shape minus the booking of. Same anonymous posture; asserted
    # in test_waitlist_api.py. Same shadowing hazard as every router above.
    app.include_router(waitlist_router)
    # F23's three tokenized offer routes — same /storefront prefix, registered
    # after the join for the same shadowing reason, and covered by the same
    # cross-router shadowing guard.
    app.include_router(waitlist_offer_router)
    # F24's client portal — the SEVENTH /storefront sibling, and the FIRST
    # anonymous-prefix router in the tree that reads a cookie. It carries its own
    # `/storefront/portal` prefix rather than new routes on the read router,
    # which is contractually GET-only. Same shadowing hazard as every router
    # above; test_portal_api.py's path literals keep it honest.
    app.include_router(portal_router)
    # The FOURTH /storefront sibling (F19 D9): the provider webhook and the
    # payment-status poll. Deliberately NOT routes on storefront_router — that
    # router carries a per-tenant _throttle, and 429-ing a provider's retry
    # burst would turn a transient outage into permanently unconfirmed bookings
    # and unrecorded money.
    app.include_router(webhook_router)
    # F19 D21, and a dev harness rather than a surface: FakeGateway redirects to
    # /fake-pay and posts no webhook of its own, so without this page every
    # staging deposit lands on a 404 and is swept into `cancelled` one tick
    # later. Registered ONLY when the fake gateway is the configured provider,
    # which Settings._forbid_fake_payment_paths_in_production already makes
    # impossible in production. F18 DELETES this line and app/payments/fake_pay.py
    # when a real adapter's hosted page replaces it.
    register_fake_pay(app, settings)
    # The FIFTH /storefront sibling — still the fifth, because F59 added a third
    # ROUTE to it rather than a sixth router: F33's walk-in check-in, its
    # position read and F59's public board, all three POSTs. Same anonymous
    # posture as the other three siblings, asserted in test_checkin_api.py and
    # test_queue_board_api.py. The board's POST is argued from the DERIVED
    # ROUTES table in test_storefront_api.py and NOT from F33's capability
    # rule — its request carries no id and no body at all. Same shadowing hazard
    # as every router above — a duplicated (method, path) would silently win or
    # lose on include order — and the explicit /storefront path literal in
    # test_storefront_api.py is what keeps all three honest.
    app.include_router(queue_router)
    # LAST, after every router: the mounts and the catch-all only ever see what
    # no API route claimed.
    _register_spas(app)
    return app


app = create_app()
