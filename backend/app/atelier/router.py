"""The atelier: one poll and six writes on /manage.

**A TENTH router on /manage**, registered after `queue_manage_router` in
`create_app()` and deliberately before `storefront_router`, so every /manage
router stays contiguous and ahead of the anonymous surfaces. Ten surfaces now
mount this prefix and a duplicated (method, path) would silently win or lose on
include order with no error at all; `test_atelier_api.py`'s `ATELIER_ROUTES`
table plus `test_no_route_is_registered_twice_across_routers` are what keep that
honest.

**THREE ROLES SPELLED AS LITERALS, not `*StaffRole`.** F57's floor router is
spelled from the enum because the set it admits IS "every role the product has";
the atelier's is not. A receptionist and a sales assistant have no business in
the workroom, and a sixth role added later must be refused here BY DEFAULT —
spelling the three is what makes that the safe direction to fail. (If the pilot
asks, it is one literal here and one NAV row, and `test_staff_role_gating.py`'s
per-role table is what makes adding it a visible act.)

**The per-route tightening on `delete`, and why F41 needs its own module.**
`RoleGate` composes by INTERSECTION (`auth/dependencies.py:44-45`), so a
per-route gate can only ever NARROW — there is no per-route widening anywhere in
this codebase. That is why `delete` can carry `require_role(OWNER,
SHIFT_MANAGER)` on top of the router's three, and equally why these seven routes
could not have been hung off an existing two-role router.

**The finer rules are the SERVICE's, not a gate's.** A seamstress on her own
ticket, a seamstress on an unassigned one, the self-claim — every one of them
depends on the TICKET's `assigned_staff_user_id`, which no `RoleGate` can see.
`delete` is the single exception and that is exactly why it is the single
per-route gate.

**⚠ THE BANDS ARE RESOLVED HERE, from `get_current_tenant(request).settings`,**
and passed into the service as a plain dict. The tenancy middleware has already
bound that mapping on the request from the same `tenants` row. Reading it back
through `TenantsRepository` would open a FOURTH session, pool checkout and
BEGIN/COMMIT on the hottest read in the feature — every five seconds per device —
because that repository is constructed with a `session_factory` and opens its own
session inside every method, so it cannot join the atelier's `tenant_session`.

**The tenant comes from the HOST**, `get_current_tenant(request)`, never
`StaffContext.tenant_id`: the two are equal in practice but are different trust
paths (`dashboard/router.py:17-26` argues this at length).

**`_no_store` is a SIXTH local three-line copy**, not an import. The alternative
points the dependency arrow backwards to save three lines;
`auth/staff_router.py:22-27` records the decision.

**No rate limiter**: no /manage router carries one and F41 does not introduce the
first. The six POSTs ARE fenced by `CsrfOriginMiddleware` (`csrf.py:48` gates on
`request.method in MUTATING_METHODS`); the GET is not, and its protection is the
session cookie and the role gate, alone.

**Real HTTP verbs and a path parameter for the target.** The `.claude/rules` RPC
/ `@QueryValue` guidance is Kotlin boilerplate for another codebase; the shipped
/manage convention is real verbs.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.atelier.schemas import (
    AssignTicketRequest,
    AtelierBoardResponse,
    AtelierTicket,
    CreateTicketRequest,
    StageRequest,
    UpdateTicketRequest,
)
from app.atelier.service import AtelierService
from app.atelier.stages import effort_bands
from app.auth.dependencies import get_current_staff, require_role
from app.auth.service import StaffContext
from app.models.constants import EffortBand, StaffRole
from app.schemas import OkResponse
from app.tenancy.middleware import TenantContext, get_current_tenant

NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    response.headers["cache-control"] = NO_STORE


def get_atelier_service(request: Request) -> AtelierService:
    service: AtelierService = request.app.state.atelier_service
    return service


router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER, StaffRole.SEAMSTRESS)),
    ],
)

Service = Annotated[AtelierService, Depends(get_atelier_service)]
Staff = Annotated[StaffContext, Depends(get_current_staff)]


def _bands(tenant: TenantContext) -> dict[EffortBand, int]:
    return effort_bands(tenant.settings)


@router.get("/atelier/tickets")
async def get_board(request: Request, service: Service) -> AtelierBoardResponse:
    tenant = get_current_tenant(request)
    return await service.board(tenant.id, bands=_bands(tenant))


@router.post("/atelier/tickets")
async def create_ticket(
    request: Request, body: CreateTicketRequest, service: Service, staff: Staff
) -> AtelierTicket:
    tenant = get_current_tenant(request)
    return await service.create(tenant.id, body, actor=staff, bands=_bands(tenant))


@router.post("/atelier/tickets/{ticket_id}/update")
async def update_ticket(
    request: Request,
    ticket_id: uuid.UUID,
    body: UpdateTicketRequest,
    service: Service,
    staff: Staff,
) -> AtelierTicket:
    tenant = get_current_tenant(request)
    return await service.update(tenant.id, ticket_id, body, actor=staff, bands=_bands(tenant))


@router.post("/atelier/tickets/{ticket_id}/assign")
async def assign_ticket(
    request: Request,
    ticket_id: uuid.UUID,
    body: AssignTicketRequest,
    service: Service,
    staff: Staff,
) -> AtelierTicket:
    """`staff` is the ACTING identity and comes from the session cookie;
    `ticket_id` is the TARGET and comes from the path. If the handler ever passed
    the path id as the actor, D9's «herself only» check would be trivially true
    and every seamstress could claim anybody's ticket."""
    return await service.assign(get_current_tenant(request).id, ticket_id, body, actor=staff)


@router.post("/atelier/tickets/{ticket_id}/stage/advance")
async def advance_stage(
    request: Request, ticket_id: uuid.UUID, body: StageRequest, service: Service, staff: Staff
) -> AtelierTicket:
    return await service.advance(get_current_tenant(request).id, ticket_id, body, actor=staff)


@router.post("/atelier/tickets/{ticket_id}/stage/undo")
async def undo_stage(
    request: Request, ticket_id: uuid.UUID, body: StageRequest, service: Service, staff: Staff
) -> AtelierTicket:
    return await service.undo(get_current_tenant(request).id, ticket_id, body, actor=staff)


@router.post(
    "/atelier/tickets/{ticket_id}/delete",
    # The ONE per-route tightening. A seamstress may not remove a garment from
    # the board: it is destructive and there is no un-delete.
    dependencies=[Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))],
)
async def delete_ticket(
    request: Request, ticket_id: uuid.UUID, service: Service, staff: Staff
) -> OkResponse:
    await service.delete(get_current_tenant(request).id, ticket_id, actor=staff)
    return OkResponse()
