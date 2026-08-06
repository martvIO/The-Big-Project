"""The public waitlist join: one anonymous, tenant-scoped POST.

**A sibling router on /storefront, not a route in app/storefront/router.py** —
the F11 precedent for the F11 reason: that router is contractually GET-only,
and mutations go to a sibling. F11 honoured it, F13, F33, F59 — F22 honours it.

**Anonymous, and CSRF is structurally N/A** on the sibling routers' two
grounds: this path is under no `CsrfOriginMiddleware.PROTECTED_PREFIXES`, and this route
reads no cookie and carries no ambient credential — the controls are
tenant-from-Host, the two join budgets, and OTP possession itself (the
verification token in the body). The cookie-blindness test keeps the second
claim true forever.

**201 always, one shape always** — the idempotent duplicate answers the same
body through the same status line, so a second submission discloses nothing a
first one did not.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.tenancy.middleware import get_current_tenant
from app.waitlist.schemas import WaitlistJoinRequest, WaitlistJoinResponse
from app.waitlist.service import WaitlistService

NO_STORE = "no-store"


def get_waitlist_service(request: Request) -> WaitlistService:
    service: WaitlistService = request.app.state.waitlist_service
    return service


def _no_store(response: Response) -> None:
    """A local three-line copy, not an import — the shipped convention on these
    routers (auth/staff_router.py:22-27 records the decision). The body names
    one person's place on a list, and the flow runs on a phone where bfcache is
    the default."""
    response.headers["cache-control"] = NO_STORE


router = APIRouter(prefix="/storefront", dependencies=[Depends(_no_store)])

Waitlist = Annotated[WaitlistService, Depends(get_waitlist_service)]


@router.post("/waitlist", status_code=201)
async def join_waitlist(
    request: Request, service: Waitlist, body: WaitlistJoinRequest
) -> WaitlistJoinResponse:
    tenant = get_current_tenant(request)
    return await service.join(
        tenant.id,
        raw_phone=body.phone,
        verification_token=body.verification_token,
        day=body.day,
        appointment_type_id=body.appointment_type_id,
    )
