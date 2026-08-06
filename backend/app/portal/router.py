"""F24's client portal: one anonymous mint plus the cookie-authed surface.

**A sibling router on /storefront, not a route in app/storefront/router.py** —
the F11 precedent for the F11 reason: that router is contractually GET-only, and
mutations go to a sibling. F13, F22, F33 and F59 honoured it; F24 honours it.

**Under /storefront and NOT a new /portal API family** (spec D7). A new
top-level prefix would need a vite proxy entry, an SPA-fallback exclusion, a
third `_RESERVED_SEGMENTS` member and its own CSRF review — for nothing. The SPA
route `/portal` is served by the existing catch-all; these are its API calls.

**CSRF**: the mint reads no cookie at all (its credential is the verification
token in the body). The cookie-authed routes DO carry an ambient credential, and
they are covered exactly as every shipped cookie POST is — `SameSite=Lax` on the
cookie plus `CsrfOriginMiddleware`, which inspects any request that carries an
`Origin`. This is the FIRST anonymous-prefix router in the tree that reads a
cookie, so that pairing is stated here rather than assumed.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.cookies import (
    CUSTOMER_SESSION_COOKIE,
    clear_customer_session_cookie,
    set_customer_session_cookie,
)
from app.core.config import get_settings
from app.portal.dependencies import get_current_customer, get_portal_service
from app.portal.schemas import PortalSessionRequest, PortalSessionResponse
from app.portal.service import CustomerContext, PortalService
from app.schemas import OkResponse
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    """A local three-line copy, not an import — the shipped convention on these
    routers (auth/staff_router.py:22-27 records the decision). Every body here
    names a real person's appointments, and the flow runs on a phone where
    bfcache is the default."""
    response.headers["cache-control"] = NO_STORE


router = APIRouter(prefix="/storefront/portal", dependencies=[Depends(_no_store)])

Portal = Annotated[PortalService, Depends(get_portal_service)]
Customer = Annotated[CustomerContext, Depends(get_current_customer)]


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
