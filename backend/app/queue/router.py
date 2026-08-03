"""The public walk-in surface: two anonymous, tenant-scoped POSTs.

**A sibling router on /storefront, not new routes in app/storefront/router.py.**
The F11 precedent for the F11 reason: that router's module docstring makes four
promises and "GET only; HEAD stays a 405, deliberately" is one of them. Nothing
in code enforces it — the enforcement is the convention that mutations go to a
sibling, plus the explicit path literal in test_storefront_api.py. F11 honoured
it, F13 honoured it, F33 honours it.

**BOTH routes are POSTs, including the read**, and that overrules the brief's
sketch of a public GET keyed by the ticket UUID. The codebase rules the other
way in writing, twice: a GET would put the capability in the query string, and
from there into every access log, proxy trace and Referer header on the path.
The id still lands in one access-log line per page load because the storefront
route is /q/{ticket_id} — but once per page load instead of once every five
seconds for the length of her visit.

**The ticket id IS the capability**, issued exactly once, at creation, in the
response to the request that created it, and by no other server path ever. That
is only true because the create has no duplicate branch: a capability the server
re-issues to anyone who guesses the phone number that owns it is not a
capability.

**Anonymous, and CSRF is structurally N/A on two independent grounds.**
CsrfOriginMiddleware only inspects paths under /manage, and these routes read no
cookie and carry no ambient credential, so there is nothing a cross-site request
could ride. The controls are tenant-from-Host and the three service-held
budgets. The cookie-blindness tests keep the second claim true forever.

**No router-level throttle.** Unlike the read router, the sibling routers carry
only Depends(_no_store): the per-ticket key needs the parsed body and the miss
key needs the lookup result, so both budgets live where the service is.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.queue.schemas import CheckinCreateRequest, PositionRequest, TicketView
from app.queue.service import QueueService
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def get_queue_service(request: Request) -> QueueService:
    service: QueueService = request.app.state.queue_service
    return service


def _no_store(response: Response) -> None:
    """A local three-line copy, not an import — the shipped convention on these
    routers. Router-level so the create cannot drift from the read: both bodies
    name one person's live place in a queue, and the position page is opened on
    a phone, where bfcache is the default."""
    response.headers["cache-control"] = NO_STORE


router = APIRouter(prefix="/storefront", dependencies=[Depends(_no_store)])

Queue = Annotated[QueueService, Depends(get_queue_service)]


@router.post("/checkin", status_code=201)
async def check_in(request: Request, service: Queue, body: CheckinCreateRequest) -> TicketView:
    """201 always, one shape always. There is no second outcome, so there is no
    second status code — which is, for free, a status line that cannot leak
    anything about who is already in the queue."""
    tenant = get_current_tenant(request)
    return await service.check_in(
        tenant.id,
        name=body.name,
        raw_phone=body.phone,
        visit_type=body.visit_type,
        marketing_opt_in=body.marketing_opt_in,
    )


@router.post("/checkin/position")
async def queue_position(request: Request, service: Queue, body: PositionRequest) -> TicketView:
    tenant = get_current_tenant(request)
    return await service.position(tenant.id, body.ticket_id)
