"""The public booking surface: the anonymous, tenant-scoped POST that creates a
booking, plus F16's three tokenized manage endpoints.

**A sibling router on /storefront, not new routes in app/storefront/router.py.**
The F11 precedent for the F11 reason: the storefront read router is
contractually GET-only, so the routes that mutate live here. Same prefix,
registered after it in create_app(); the cross-router shadowing guard in
test_storefront_api.py covers all four.

**Anonymous and cookie-blind, and CSRF is structurally N/A.** On the create the
credential is the verification token — single-use, phone-bound, minted by
/storefront/otp/verify. On the three manage routes it is the manage token, which
arrives in the BODY so no access log carries it. No cookie is read anywhere here,
so there is nothing a cross-site request could ride: the controls are
tenant-from-Host, token possession, and the per-tenant budgets in the services.
The cookie-blindness test keeps this claim true forever.

**The confirmation SMS is fired HERE, after the transaction commits**, and only
when the claim actually created a booking. It is post-commit because
`NotificationService.send_sms` structurally opens its own sessions — a provider
hang inside the booking transaction would block commits — and it is fire-and-
forget because turning a committed booking into a 503 is a lie the F14 review
already fought once.

**The deposit hold is opened in the same position and for the same reason**
(F19 D11), and it moves the SMS: a booking that owes a deposit is committed as
`pending_payment` and gets no confirmation until the money is in.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.booking.comms import BookingCommsService, CommsTenant
from app.booking.manage import ManageBookingService, ManageTenant
from app.booking.schemas import (
    BookingCreateRequest,
    BookingCreateResponse,
    ManageBookingResponse,
    ManageTokenRequest,
)
from app.booking.service import BookingService
from app.core.config import get_settings
from app.tenancy.middleware import TenantContext, get_current_tenant

NO_STORE = "no-store"
# Spelled here and imported by nothing: the portal router carries its own copy,
# the same three-line-copy convention `_no_store` follows across these routers.
ICS_MEDIA_TYPE = "text/calendar; charset=utf-8"
ICS_DISPOSITION = 'attachment; filename="appointment.ics"'


def get_booking_service(request: Request) -> BookingService:
    service: BookingService = request.app.state.booking_service
    return service


def get_comms_service(request: Request) -> BookingCommsService:
    service: BookingCommsService = request.app.state.booking_comms_service
    return service


def get_manage_service(request: Request) -> ManageBookingService:
    service: ManageBookingService = request.app.state.manage_booking_service
    return service


def _no_store(response: Response) -> None:
    """Router-level like the OTP surface: every response here names a real
    person's appointment, which must never land in a shared cache or a bfcache
    entry — and the manage page is reached from an SMS on a phone, where bfcache
    is the default."""
    response.headers["cache-control"] = NO_STORE


router = APIRouter(prefix="/storefront", dependencies=[Depends(_no_store)])

Bookings = Annotated[BookingService, Depends(get_booking_service)]
Comms = Annotated[BookingCommsService, Depends(get_comms_service)]
Manage = Annotated[ManageBookingService, Depends(get_manage_service)]


def _manage_tenant(tenant: TenantContext) -> ManageTenant:
    return ManageTenant(id=tenant.id, name=tenant.name, settings=tenant.settings)


@router.post("/bookings", status_code=201)
async def create_booking(
    request: Request, service: Bookings, comms: Comms, body: BookingCreateRequest
) -> BookingCreateResponse:
    tenant = get_current_tenant(request)
    claim = await service.create_booking(
        tenant.id,
        raw_phone=body.phone,
        verification_token=body.verification_token,
        name=body.name,
        appointment_type_id=body.appointment_type_id,
        starts_at=body.starts_at,
        terms_version=body.terms_version,
        dress_id=body.dress_id,
        dress_size=body.dress_size,
        notes=body.notes,
        marketing_consent=body.marketing_consent,
        # D19's master toggle rides in from the resolved tenant. Omit it and
        # `deposit_due` reads an absent `deposits_enabled` as OFF — every
        # booking through this route would silently skip the deposit.
        settings=tenant.settings,
    )
    # D11: the hold is opened HERE, post-commit, for the same reason the
    # confirmation SMS is fired here — PaymentService opens its own sessions and
    # re-takes the advisory lock the claim held until COMMIT. `return_url` is
    # the request's own origin rather than a configured host: the bride must
    # come back to the storefront she is standing on, and that is the one thing
    # the request already knows for certain.
    deposit = await service.open_deposit(tenant.id, claim, return_url=str(request.base_url))
    if claim.created and claim.manage_token is not None and not deposit.deposit_due:
        # `created` AND a token: two spellings of one fact, because the 0009
        # replay path carries no raw token. Awaited rather than backgrounded so
        # the send happens inside the request's own lifetime — it never raises
        # (send_confirmation swallows both provider exceptions after their
        # evidence exists), so it cannot cost the caller their 201.
        #
        # AND no deposit outstanding (D11): confirming an appointment before a
        # single agora is taken is a promise the boutique has not been paid for.
        # The condition reads the OUTCOME, not the claim, which is what makes
        # MD4's compensated booking — gateway unreachable, appointment stands
        # with no deposit — send the ordinary confirmation it is owed.
        await comms.send_confirmation(
            CommsTenant.from_settings(
                tenant_id=tenant.id, slug=tenant.slug, name=tenant.name, settings=tenant.settings
            ),
            booking=claim.booking,
            manage_token=claim.manage_token,
        )
    row = claim.booking
    return BookingCreateResponse(
        id=row.id,
        starts_at=row.starts_at,
        # From the outcome, not the row: MD4's compensating transition wrote
        # `confirmed` in its own session, so `row.status` is a stale
        # `pending_payment` on exactly the path where the difference is the
        # whole point.
        status=deposit.status,
        appointment_type_name=row.appointment_type_name,
        dress_name=row.dress_name,
        dress_size=row.dress_size,
        deposit_due=deposit.deposit_due,
        redirect_url=deposit.redirect_url,
        payment_session_id=deposit.payment_session_id,
    )


@router.post("/booking/lookup")
async def lookup_booking(
    request: Request, service: Manage, body: ManageTokenRequest
) -> ManageBookingResponse:
    """POST for a read, deliberately: a GET would put the token in the query
    string, and from there into every access log, proxy trace and Referer header
    on the path (D7)."""
    return await service.lookup(_manage_tenant(get_current_tenant(request)), token=body.token)


@router.post("/booking/confirm-attendance")
async def confirm_attendance(
    request: Request, service: Manage, body: ManageTokenRequest
) -> ManageBookingResponse:
    return await service.confirm_attendance(
        _manage_tenant(get_current_tenant(request)), token=body.token
    )


@router.post("/booking/cancel")
async def cancel_booking(
    request: Request, service: Manage, body: ManageTokenRequest
) -> ManageBookingResponse:
    return await service.cancel(_manage_tenant(get_current_tenant(request)), token=body.token)


@router.post("/booking/ics")
async def booking_ics(request: Request, service: Manage, body: ManageTokenRequest) -> Response:
    """The tokenized page's calendar download — the SAME builder the portal's
    GET serves, one rendering over two transports (F24 D5).

    POST rather than the portal's GET, and the asymmetry is the point: here the
    manage TOKEN is the credential, and tokens never ride URLs (F14 D7) or they
    land in every access log, proxy trace and Referer header on the path. The
    SPA turns the response into a blob download. On the portal the credential is
    a cookie, so a native GET link is safe there and is what opens the
    add-to-calendar sheet on iOS.

    Headers are set on this Response explicitly: FastAPI discards the
    dependency-owned Response — and with it the router's `no-store` — whenever a
    handler returns its own.
    """
    settings = get_settings()
    tenant = get_current_tenant(request)
    text = await service.ics(
        _manage_tenant(tenant),
        token=body.token,
        slug=tenant.slug,
        base_domain=settings.base_domain,
    )
    return Response(
        content=text,
        media_type=ICS_MEDIA_TYPE,
        headers={"content-disposition": ICS_DISPOSITION, "cache-control": NO_STORE},
    )
