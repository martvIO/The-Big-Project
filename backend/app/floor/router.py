"""The floor: one read and two break toggles on /manage.

**A SEVENTH router on /manage.** Registered after dashboard_router in
create_app(), carrying the same shadowing warning the other six includes carry —
a duplicated (method, path) would silently win or lose on include order, and
`test_floor_api.py`'s ROUTES table plus
`test_no_route_is_registered_twice_across_routers` are what keep that honest.
(`test_dashboard_api.py:49-51` says SIX; it is a historical note in another
feature's module and this docstring carries the new count.)

**ALL FIVE ROLES at router level, and this is the only router in the codebase
that admits more than two.** The floor payload carries ZERO customer data — a
name, a role and a status for each member of staff — which is exactly what makes
it safe to widen and is why D11 refuses to merge it into the board's poll
instead. Router-level so a route added here later cannot forget the gate, and
because test_staff_role_gating's default-deny walker reads `allowed_roles` off
the router: a /manage router without one is a red build.

**Why a new module rather than a route on an existing router — structural, not
stylistic.** `RoleGate` composes by INTERSECTION (`auth/dependencies.py:44-45`)
and the walker yields EVERY gate in the dependency tree, so a per-route
`require_role(*StaffRole)` hung on `booking/owner_router.py` would still be
refused for a seamstress by that router's own two-role gate. There is no
per-route widening in this codebase.

**`require_role(*StaffRole)` is spelled from the enum, not as five literals**, so
a sixth role is admitted here by default. That is safe ONLY because
`test_the_floor_roles_reach_exactly_the_floor_routes` pins the floor roles out of
everywhere else. Both halves ship in this PR or neither should.

**The tenant comes from the HOST**, `get_current_tenant(request)`, never
`StaffContext.tenant_id` — the two are equal in practice but are different trust
paths (`dashboard/router.py:17-26` argues this at length).

**`_no_store` is a FIFTH local three-line copy**, not an import. The alternative
points the dependency arrow backwards to save three lines;
`auth/staff_router.py:22-27` records the decision.

**No rate limiter**: no /manage router carries one and F57 does not introduce the
first. The two POSTs ARE fenced by CsrfOriginMiddleware (`csrf.py:48` gates on
`request.method in MUTATING_METHODS`); the GET is not, and its protection is the
session cookie and the role gate, alone.

**Real HTTP verbs and a path parameter for the target.** The `.claude/rules` RPC
/ `@QueryValue` guidance is Kotlin boilerplate for another codebase; the shipped
/manage convention is real verbs.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.dependencies import get_current_staff, require_role
from app.auth.service import StaffContext
from app.floor.schemas import FloorResponse, StaffCard
from app.floor.service import FloorService
from app.models.constants import StaffRole
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    response.headers["cache-control"] = NO_STORE


def get_floor_service(request: Request) -> FloorService:
    service: FloorService = request.app.state.floor_service
    return service


router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(*StaffRole)),
    ],
)

Service = Annotated[FloorService, Depends(get_floor_service)]
Staff = Annotated[StaffContext, Depends(get_current_staff)]


@router.get("/floor")
async def get_floor(request: Request, service: Service) -> FloorResponse:
    return FloorResponse.from_rows(await service.floor(get_current_tenant(request).id))


@router.post("/floor/staff/{staff_id}/break/start")
async def start_break(
    request: Request, staff_id: uuid.UUID, service: Service, staff: Staff
) -> StaffCard:
    """`staff` is the ACTING identity and comes from the session cookie;
    `staff_id` is the TARGET and comes from the path. The service's two-axis
    check is what keeps the second from ever standing in for the first."""
    row, occupancy = await service.start_break(
        get_current_tenant(request).id, staff_id, actor=staff
    )
    return StaffCard.from_row(row, occupancy=occupancy)


@router.post("/floor/staff/{staff_id}/break/end")
async def end_break(
    request: Request, staff_id: uuid.UUID, service: Service, staff: Staff
) -> StaffCard:
    """The occupancy the service hands back is the SECOND half of the card, not
    a decoration: if this staffer is standing in a fitting room the card must say
    `occupied`, or it contradicts the panel it lands in five seconds later."""
    row, occupancy = await service.end_break(get_current_tenant(request).id, staff_id, actor=staff)
    return StaffCard.from_row(row, occupancy=occupancy)
