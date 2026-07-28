"""The public booking surface: one anonymous, tenant-scoped POST.

**A sibling router on /storefront, not a new route in app/storefront/router.py.**
The F11 precedent for the F11 reason: the storefront read router is
contractually GET-only, so the one route that mutates lives here. Same prefix,
registered after it in create_app(); the cross-router shadowing guard in
test_storefront_api.py covers all three.

**Anonymous and cookie-blind, and CSRF is structurally N/A.** The credential is
the verification token — single-use, phone-bound, minted by /storefront/otp/verify.
No cookie is read, so there is nothing a cross-site request could ride: the
controls are tenant-from-Host, OTP possession, and the per-tenant create budget
in BookingService. The cookie-blindness test keeps this claim true forever.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.booking.schemas import BookingCreateRequest, BookingCreateResponse
from app.booking.service import BookingService
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def get_booking_service(request: Request) -> BookingService:
    service: BookingService = request.app.state.booking_service
    return service


def _no_store(response: Response) -> None:
    """Router-level like the OTP surface: the response names a real person's
    appointment, which must never land in a shared cache or bfcache entry."""
    response.headers["cache-control"] = NO_STORE


router = APIRouter(prefix="/storefront", dependencies=[Depends(_no_store)])

Bookings = Annotated[BookingService, Depends(get_booking_service)]


@router.post("/bookings", status_code=201)
async def create_booking(
    request: Request, service: Bookings, body: BookingCreateRequest
) -> BookingCreateResponse:
    tenant = get_current_tenant(request)
    row = await service.create_booking(
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
    return BookingCreateResponse(
        id=row.id,
        starts_at=row.starts_at,
        status=row.status,
        appointment_type_name=row.appointment_type_name,
        dress_name=row.dress_name,
        dress_size=row.dress_size,
    )
