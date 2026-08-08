"""F24's client portal: one anonymous mint plus the cookie-authed surface.

**A sibling router on /storefront, not a route in app/storefront/router.py** —
the F11 precedent for the F11 reason: that router is contractually GET-only, and
mutations go to a sibling. F13, F22, F33 and F59 honoured it; F24 honours it.

**Under /storefront and NOT a new /portal API family** (spec D7). A new
top-level prefix would need a vite proxy entry, an SPA-fallback exclusion, a
third `_RESERVED_SEGMENTS` member and its own CSRF review — for nothing. The SPA
route `/portal` is served by the existing catch-all; these are its API calls.

**CSRF**: the mint reads no cookie at all (its credential is the verification
token in the body). The cookie-authed routes DO carry an ambient credential, so
they get `SameSite=Lax` on the cookie plus `CsrfOriginMiddleware` — and because
this is the FIRST cookie reader outside `/manage`, the middleware's prefix list
had to grow for that second half to be true at all: `"/storefront/portal"` is in
`csrf.PROTECTED_PREFIXES` beside `"/manage"`. Lax alone would not do, since
tenants share one registrable domain and a sibling subdomain is same-SITE.
`test_portal_api.py` measures the fence per POST rather than restating it here.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.cookies import (
    CUSTOMER_SESSION_COOKIE,
    clear_customer_session_cookie,
    set_customer_session_cookie,
)
from app.booking.manage import ManageTenant
from app.booking.schemas import ManageBookingResponse
from app.core.config import get_settings
from app.portal.dependencies import get_current_customer, get_portal_service
from app.portal.schemas import (
    PortalBellResponse,
    PortalBookingIdRequest,
    PortalBookingsResponse,
    PortalSessionRequest,
    PortalSessionResponse,
)
from app.portal.service import CustomerContext, PortalService
from app.schemas import OkResponse
from app.tenancy.middleware import TenantContext, get_current_tenant

NO_STORE = "no-store"
ICS_MEDIA_TYPE = "text/calendar; charset=utf-8"
ICS_DISPOSITION = 'attachment; filename="appointment.ics"'


def _no_store(response: Response) -> None:
    """A local three-line copy, not an import — the shipped convention on these
    routers (auth/staff_router.py:22-27 records the decision). Every body here
    names a real person's appointments, and the flow runs on a phone where
    bfcache is the default."""
    response.headers["cache-control"] = NO_STORE


router = APIRouter(prefix="/storefront/portal", dependencies=[Depends(_no_store)])

Portal = Annotated[PortalService, Depends(get_portal_service)]
Customer = Annotated[CustomerContext, Depends(get_current_customer)]


def _ics_response(body: str) -> Response:
    """`text/calendar` with an attachment disposition, and `no-store` spelled
    out — see `portal_booking_ics` for why the dependency cannot carry it."""
    return Response(
        content=body,
        media_type=ICS_MEDIA_TYPE,
        headers={
            "content-disposition": ICS_DISPOSITION,
            "cache-control": NO_STORE,
        },
    )


def _manage_tenant(tenant: TenantContext) -> ManageTenant:
    """The booking router's own helper, spelled again rather than imported: it
    is three lines and importing it would make the portal depend on a router."""
    return ManageTenant(id=tenant.id, name=tenant.name, settings=tenant.settings)


@router.post("/session")
async def create_portal_session(
    request: Request, response: Response, service: Portal, body: PortalSessionRequest
) -> PortalSessionResponse:
    tenant = get_current_tenant(request)
    settings = get_settings()
    result, token = await service.create_session(
        tenant.id, raw_phone=body.phone, verification_token=body.verification_token
    )
    set_customer_session_cookie(
        response,
        token,
        secure=settings.secure_cookies,
        max_age=settings.portal_session_ttl_seconds,
    )
    return result


@router.get("/me")
async def portal_me(customer: Customer) -> PortalSessionResponse:
    """The SPA's session bootstrap. A 401 here is not an error state — it is
    what mounts the login panel."""
    return PortalSessionResponse(customer_name=customer.name)


@router.post("/logout")
async def portal_logout(
    request: Request, response: Response, service: Portal, customer: Customer
) -> OkResponse:
    """Behind the cookie gate like every other portal route (spec's API table),
    so the auth matrix has no exception to remember. A cookie that no longer
    resolves 401s and mounts the login panel — which is the same screen logging
    out produces, so nothing is lost by refusing it.

    `customer` is the gate, not an argument: the revoke keys on the token itself
    so a second tab holding a different session is untouched.
    """
    del customer
    tenant = get_current_tenant(request)
    token = request.cookies.get(CUSTOMER_SESSION_COOKIE)
    if token:
        await service.logout(tenant.id, token)
    clear_customer_session_cookie(response, secure=get_settings().secure_cookies)
    return OkResponse()


@router.get("/bookings")
async def portal_bookings(
    request: Request, service: Portal, customer: Customer
) -> PortalBookingsResponse:
    """No query parameters at all: the customer comes from the session and the
    split comes from the server's clock."""
    return await service.list_bookings(get_current_tenant(request).id, customer)


@router.get("/booking")
async def portal_booking(
    request: Request, service: Portal, customer: Customer, id: uuid.UUID
) -> ManageBookingResponse:
    """A GET with the id in the query string, unlike the tokenized page's POST:
    a booking id is not a capability here — the cookie is — so there is nothing
    an access log must not see."""
    return await service.get_booking(_manage_tenant(get_current_tenant(request)), customer, id)


@router.get("/booking.ics")
async def portal_booking_ics(
    request: Request, service: Portal, customer: Customer, id: uuid.UUID
) -> Response:
    """A plain GET download link, unlike every other capability-bearing read in
    this product — and the exception is earned: the booking id is not a
    capability here (the cookie is), and on iOS a DIRECT `text/calendar`
    response is what opens the add-to-calendar sheet. A fetch-and-blob dance
    downloads a file she then has to find.

    ASCII filename deliberately: a Hebrew filename in `Content-Disposition` is
    an RFC 6266 encoding tarpit that ends in mojibake on at least one mobile
    client.

    The headers are set HERE rather than left to the router's `_no_store`
    dependency: FastAPI discards the dependency-owned Response when a handler
    returns its own.
    """
    settings = get_settings()
    tenant = get_current_tenant(request)
    body = await service.get_booking_ics(
        _manage_tenant(tenant), customer, id, slug=tenant.slug, base_domain=settings.base_domain
    )
    return _ics_response(body)


@router.post("/booking/confirm-attendance")
async def portal_confirm_attendance(
    request: Request, service: Portal, customer: Customer, body: PortalBookingIdRequest
) -> ManageBookingResponse:
    return await service.confirm_attendance(
        _manage_tenant(get_current_tenant(request)), customer, body.id
    )


@router.post("/booking/cancel")
async def portal_cancel_booking(
    request: Request, service: Portal, customer: Customer, body: PortalBookingIdRequest
) -> ManageBookingResponse:
    """The tokenized `/b/{token}` page and its endpoints are UNTOUCHED — this is
    a second door onto the same transition, not a replacement."""
    return await service.cancel(_manage_tenant(get_current_tenant(request)), customer, body.id)


@router.get("/bell")
async def portal_bell(request: Request, service: Portal, customer: Customer) -> PortalBellResponse:
    """What the boutique has told her, projected off `message_log` — fetched
    once on portal mount and never polled (pre-decided #18)."""
    return await service.bell(get_current_tenant(request).id, customer)


@router.post("/bell/seen")
async def portal_bell_seen(request: Request, service: Portal, customer: Customer) -> OkResponse:
    """Stamps `bell_seen_at = now()`. The SPA fires it when the panel OPENS and
    clears the badge only after this answers — the stamp is the truth, not the
    click (design F-P2)."""
    await service.mark_bell_seen(get_current_tenant(request).id, customer)
    return OkResponse()
