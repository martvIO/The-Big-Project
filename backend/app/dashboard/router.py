"""The console's landing read: one route on /manage.

**A sixth router on /manage.** Registered after staff_router in create_app(),
carrying the same shadowing warning the catalog, owner-booking and staff
includes carry — six routers now mount this prefix and a duplicated
(method, path) would silently win or lose on include order.
`test_dashboard_api.py`'s ROUTES table is what keeps that honest.

**Both roles at ROUTER level.** The SMC epic's locked table admits owner and
shift manager, and there is no per-role projection: a shift manager sees the
same six answers the owner does. Router-level so a route added here later cannot
forget the gate, and because test_staff_role_gating's default-deny walker reads
`allowed_roles` off the router — a /manage router without one is a red build.
It must NOT be added to that module's OWNER_ONLY set: a both-roles route there
reports as `unenforced_owner_only`.

**No `staff` parameter, and the tenant comes from the HOST.**
`get_current_tenant(request)` is what every shipped /manage handler without
exception uses, and TenantResolutionMiddleware binds it from the Host header and
nothing else. The other source in hand, `StaffContext.tenant_id`, is
session-derived; the two are equal in practice because `get_current_staff`
resolves the session against the host-derived id under RLS, but they are
different trust paths. F52 is the first /manage route with NO independent reason
to inject `staff` at all — no audit row, no self-guard (D9) — which makes it
exactly the route where an implementer reaches for the session id because it is
already in hand. The RoleGate above runs router-level and needs no binding here.

**`_no_store` is a fourth local three-line copy**, not an import. The
alternative points the dependency arrow backwards to save three lines;
`auth/staff_router.py:22-27` records the decision.

**No rate limiter**, and the reason is one leg, not two: no /manage router
carries one and F52 does not introduce the first. CSRF fencing is explicitly NOT
part of this route's posture — CsrfOriginMiddleware gates on
`request.method in MUTATING_METHODS` (`csrf.py:48`) and this is a GET. The
protection here is the session cookie and the role gate, alone.

**Real HTTP verbs** are the shipped /manage convention; the `.claude/rules` RPC
/ `@QueryValue` guidance is Kotlin boilerplate for another codebase.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.dependencies import require_role
from app.dashboard.schemas import DashboardResponse
from app.dashboard.service import DashboardService
from app.models.constants import StaffRole
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    response.headers["cache-control"] = NO_STORE


def get_dashboard_service(request: Request) -> DashboardService:
    service: DashboardService = request.app.state.dashboard_service
    return service


router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)),
    ],
)

Service = Annotated[DashboardService, Depends(get_dashboard_service)]


@router.get("/dashboard")
async def get_dashboard(request: Request, service: Service) -> DashboardResponse:
    """No parameters, deliberately: `today` comes from a real clock, so the
    window arithmetic is total with no overflow guard (D2). A later `?weeks=`
    would silently break that."""
    return await service.dashboard(get_current_tenant(request).id)
