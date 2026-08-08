"""The public walk-in surface: three anonymous, tenant-scoped POSTs — F33's
check-in and its position read, and F59's wall board.

**A sibling router on /storefront, not new routes in app/storefront/router.py.**
The F11 precedent for the F11 reason: that router's module docstring makes four
promises and "GET only; HEAD stays a 405, deliberately" is one of them. Nothing
in code enforces it — the enforcement is the convention that mutations go to a
sibling, plus the explicit path literal in test_storefront_api.py. F11 honoured
it, F13 honoured it, F33 honoured it, F59 honours it.

**ALL THREE routes are POSTs, including both reads — but for TWO different
reasons, and mis-citing one for the other would be a security rationale that
does not apply.**

*F33's two*, and that overrules the brief's sketch of a public GET keyed by the
ticket UUID. The codebase rules the other way in writing, twice: a GET would put
the capability in the query string, and from there into every access log, proxy
trace and Referer header on the path. The id still lands in one access-log line
per page load because the storefront route is /q/{ticket_id} — but once per page
load instead of once every five seconds for the length of her visit.

**The ticket id IS the capability**, issued exactly once, at creation, in the
response to the request that created it, and by no other server path ever. That
is only true because the create has no duplicate branch: a capability the server
re-issues to anyone who guesses the phone number that owns it is not a
capability.

*F59's one* carries **no capability at all** — no id in the request, no id in the
response (QueueBoardEntry has no `id` field and must never gain one), and in fact
no request body whatsoever. So the log-leak argument above does not transfer to
it, and its POST is argued somewhere else entirely: `ROUTES` in
test_storefront_api.py is DERIVED over every GET under /storefront, five guards
parametrize over it, and one of them asserts 429 on each against a limiter
configured to block everything. That limiter is a router-level dependency of the
GET-only read router, which this sibling does not carry — so a GET here would
answer 200 and redden it. The only two escapes are worse than a POST: give the
board a second key on the catalog's 6000/60s read brake (the exact failure
main.py names verbatim) or weaken a guard protecting six shipped public reads.

**Anonymous, and CSRF is structurally N/A on two independent grounds.**
these paths are under no `CsrfOriginMiddleware.PROTECTED_PREFIXES`, and they read no
cookie and carry no ambient credential, so there is nothing a cross-site request
could ride. The controls are tenant-from-Host and the four service-held budgets.
The cookie-blindness tests keep the second claim true forever.

**No router-level throttle.** Unlike the read router, the sibling routers carry
only Depends(_no_store): the per-ticket key needs the parsed body, the miss key
needs the lookup result and the board key needs the resolved tenant, so all four
budgets live where the service is.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.queue.schemas import (
    CheckinCreateRequest,
    PositionRequest,
    QueueBoardView,
    TicketView,
)
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


@router.post("/queue")
async def queue_board(request: Request, service: Queue) -> QueueBoardView:
    """No body parameter at all, and that is the whole request shape. The tenant
    comes from the Host as the first statement, never from anything a caller
    could name — this endpoint answers with women's first names, so a
    caller-nameable tenant would be every boutique's queue readable from one
    host. 200 always, one shape always: an empty queue is an empty list."""
    tenant = get_current_tenant(request)
    return await service.board(tenant.id)
