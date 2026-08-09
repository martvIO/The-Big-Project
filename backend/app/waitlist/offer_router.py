"""`/w/{token}`'s three POSTs — the tokenized offer surface (D6).

**A third sibling router on /storefront**, the F11 precedent one more time: the
storefront read router is contractually GET-only, so mutations live beside it.

**The token travels in a BODY on all three, never a path or a query.** That is
`manage.py` D7's rule and the reason is that the page's URL is `/w/{token}` in
the BROWSER — a client-side route the SPA parses — while the API never sees it
in a line an access log, a proxy or a referrer header would keep.

**Anonymous, and CSRF is structurally N/A** on the sibling routers' two grounds:
no `CsrfOriginMiddleware.PROTECTED_PREFIXES` covers this path, and these routes
read no cookie and carry no ambient credential. Possession of a token texted to
her phone is the proof, the same posture as `/b/{token}`.

**The claim's tail is `POST /storefront/bookings`'s, deliberately verbatim**: the
deposit hold is opened post-commit and the confirmation SMS is fired only when
nothing is owed. Writing a second, subtly different tail here would be the same
mistake as a second oversell path, one layer up.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.booking.comms import BookingCommsService, CommsTenant
from app.booking.schemas import BookingCreateResponse
from app.booking.service import BookingService
from app.tenancy.middleware import get_current_tenant
from app.waitlist.offer_service import WaitlistOfferService
from app.waitlist.schemas import (
    WaitlistOfferClaimRequest,
    WaitlistOfferResponse,
    WaitlistOfferTokenRequest,
)

NO_STORE = "no-store"


def get_offer_service(request: Request) -> WaitlistOfferService:
    service: WaitlistOfferService = request.app.state.waitlist_offer_service
    return service


def get_booking_service(request: Request) -> BookingService:
    service: BookingService = request.app.state.booking_service
    return service


def get_comms_service(request: Request) -> BookingCommsService:
    service: BookingCommsService = request.app.state.booking_comms_service
    return service


def _no_store(response: Response) -> None:
    """A local three-line copy, not an import — the shipped convention on these
    routers. Every body here names one person's offer, on a phone where bfcache
    is the default."""
    response.headers["cache-control"] = NO_STORE


router = APIRouter(prefix="/storefront", dependencies=[Depends(_no_store)])

Offers = Annotated[WaitlistOfferService, Depends(get_offer_service)]
Bookings = Annotated[BookingService, Depends(get_booking_service)]
Comms = Annotated[BookingCommsService, Depends(get_comms_service)]


@router.post("/waitlist/offer")
async def lookup_offer(
    request: Request, service: Offers, body: WaitlistOfferTokenRequest
) -> WaitlistOfferResponse:
    tenant = get_current_tenant(request)
    return await service.lookup(tenant.id, token=body.token)


@router.post("/waitlist/claim", status_code=201)
async def claim_offer(
    request: Request,
    service: Offers,
    bookings: Bookings,
    comms: Comms,
    body: WaitlistOfferClaimRequest,
) -> BookingCreateResponse:
    tenant = get_current_tenant(request)
    claim = await service.claim(
        tenant.id,
        token=body.token,
        name=body.name,
        terms_version=body.terms_version,
        # D19's master toggle rides in from the resolved tenant. Omit it and
        # `deposit_due` reads an absent `deposits_enabled` as OFF — every claim
        # through this route would silently skip the deposit the direct path
        # collects.
        settings=tenant.settings,
    )
    deposit = await bookings.open_deposit(tenant.id, claim, return_url=str(request.base_url))
    if claim.manage_token is not None and not deposit.deposit_due:
        # The shipped condition, one surface over: no confirmation until nothing
        # is owed, because confirming an appointment before an agora is taken is
        # a promise the boutique has not been paid for. `deposit.deposit_due` is
        # the OUTCOME, so MD4's compensated booking still gets its text.
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
        # `pending_payment` on exactly the path where the difference matters.
        status=deposit.status,
        appointment_type_name=row.appointment_type_name,
        dress_name=row.dress_name,
        dress_size=row.dress_size,
        deposit_due=deposit.deposit_due,
        redirect_url=deposit.redirect_url,
        payment_session_id=deposit.payment_session_id,
    )


@router.post("/waitlist/decline")
async def decline_offer(
    request: Request, service: Offers, body: WaitlistOfferTokenRequest
) -> WaitlistOfferResponse:
    tenant = get_current_tenant(request)
    return await service.decline(tenant.id, token=body.token)
