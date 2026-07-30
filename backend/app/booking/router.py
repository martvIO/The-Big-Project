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
from app.tenancy.middleware import TenantContext, get_current_tenant

NO_STORE = "no-store"


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
    )
    if claim.created and claim.manage_token is not None:
        # `created` AND a token: two spellings of one fact, because the 0009
        # replay path carries no raw token. Awaited rather than backgrounded so
        # the send happens inside the request's own lifetime — it never raises
        # (send_confirmation swallows both provider exceptions after their
        # evidence exists), so it cannot cost the caller their 201.
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
        status=row.status,
        appointment_type_name=row.appointment_type_name,
        dress_name=row.dress_name,
        dress_size=row.dress_size,
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
