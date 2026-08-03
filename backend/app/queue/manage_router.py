"""The printable check-in code: one route on /manage.

**The EIGHTH router on /manage**, registered after gateway_router and before
storefront_router in create_app(), keeping every /manage router contiguous and
ahead of the anonymous surfaces. Eight surfaces now mount this prefix and a
duplicated (method, path) would silently win or lose on include order with no
error at all. `test_checkin_qr_api.py`'s ROUTES table is what keeps that honest.

**Both roles at ROUTER level**, and this one is a decision rather than a
default: the payload is a public URL and a picture of it, the same URL printed
on a sign in the window that anyone in the shop can read, so the disclosure is
zero and locking a shift manager out of reprinting a torn poster is a support
ticket for no security gain. The mechanical consequence must be got right —
this route must NOT be added to `test_staff_role_gating.py`'s OWNER_ONLY set,
or its default-deny walker reports it as `unenforced_owner_only`. Conversely,
omitting `require_role` entirely is a red build: the walker enumerates the live
route table.

**No `staff` parameter, and the tenant comes from the HOST.** `slug` is what
composes the URL, and `get_current_tenant(request)` is bound by
TenantResolutionMiddleware from the Host header and nothing else. The other
source in hand, `StaffContext.tenant_id`, is session-derived and carries no
slug at all.

**`_no_store` is another local three-line copy**, not an import — the
alternative points the dependency arrow backwards to save three lines
(`auth/staff_router.py:22-27` records the decision).

**No rate limiter, no audit row, no AuditAction member.** Nothing here writes,
and every shipped AuditAction value has a live writer. CSRF fencing is
explicitly not part of this posture either: CsrfOriginMiddleware gates on
`request.method in MUTATING_METHODS` (`csrf.py:48`) and this is a GET. The
protection is the session cookie and the role gate, alone.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.dependencies import require_role
from app.models.constants import StaffRole
from app.queue.qr import CheckinQrService
from app.queue.schemas import CheckinQrResponse
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    response.headers["cache-control"] = NO_STORE


def get_checkin_qr_service(request: Request) -> CheckinQrService:
    service: CheckinQrService = request.app.state.checkin_qr_service
    return service


router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)),
    ],
)

Service = Annotated[CheckinQrService, Depends(get_checkin_qr_service)]


@router.get("/checkin-qr")
async def get_checkin_qr(request: Request, service: Service) -> CheckinQrResponse:
    """No parameters: the answer is a total function of the tenant's own slug
    and the injected base_domain, so there is nothing to ask for and nothing
    that can miss."""
    return service.checkin_qr(get_current_tenant(request).slug)
