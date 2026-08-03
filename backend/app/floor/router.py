"""The floor: the read, the two break toggles, the room registry, the claim and
its dress bindings, the two one-shot pickers and F37's SOS page — eighteen routes
on /manage.

**A SEVENTH router on /manage.** Registered after dashboard_router in
create_app(), carrying the same shadowing warning the other six includes carry —
a duplicated (method, path) would silently win or lose on include order, and
`test_floor_api.py`'s ROUTES table plus
`test_no_route_is_registered_twice_across_routers` are what keep that honest.
(`test_dashboard_api.py:49-51` says SIX; it is a historical note in another
feature's module and this docstring carries the new count.)

**ALL FIVE ROLES at router level, and this is the only router in the codebase
that admits more than two.** Router-level so a route added here later cannot
forget the gate, and because test_staff_role_gating's default-deny walker reads
`allowed_roles` off the router: a /manage router without one is a red build.

⚠ **The justification for that widening changed in F36 and the sentence that
used to stand here is now false.** It said the floor payload carries ZERO
customer data. It carries a client label — on each occupied room, and on the
holder's staff card. What is true, and what the widening actually rests on:
**the floor payload carries the minimum customer datum required by the person
standing on the floor — at most one name per occupied room, for the duration of
the fitting, never the day's customer book.** On a surface this feature's own
spec calls legally sensitive, leaving the widest role gate in the product
justified by a claim that is no longer true would be worse than never having
written one.

The distinction that keeps D11's conclusion right — two loops stay two loops:

    GET /manage/bookings?date=   the DAY BOOK. Every customer booked today, with
                                 her appointment type, dress, size, notes,
                                 status, arrival and manage-token surface, for
                                 the whole day, to anyone who opens the section.
                                 Owner and shift_manager. F36 puts none of this
                                 anywhere.
    GET /manage/floor            the ≤3 PEOPLE PHYSICALLY IN FITTING ROOMS RIGHT
                                 NOW. One name each, and nothing else about her,
                                 for the duration of the fitting.
    GET /manage/floor/clients    today's arrivals — checked in and still in the
                                 building. A name and an appointment time,
                                 fetched when the panel mounts and after a
                                 claim, never on the tick.

**F37 adds five routes and tightens NONE** — every rule on the SOS page reads the
alert row, and a `RoleGate` can express only a pure role predicate. See the
section comment above those five.

**Four routes NARROW that gate to owner + shift_manager**, per-route, composing
by intersection (`auth/dependencies.py:44-45`): the three registry verbs, and
`handover`. The registry is configuration — a seamstress renaming the boutique's
rooms is not a capability anything asks for. `handover` is there rather than in
the service because its predicate depends on nothing about the target, which is
precisely what `RoleGate` is; the claim's and the release's are target-dependent
(self OR elevated) and genuinely cannot live in a gate.

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

**No rate limiter**: no /manage router carries one and neither F36 nor F37
introduces the first. The FOURTEEN mutating routes ARE fenced by
CsrfOriginMiddleware (`csrf.py:48` gates on `request.method in MUTATING_METHODS`,
a method test rather than a path list, so the eight F36 adds and the four F37
adds are fenced by construction); the FOUR GETs are not, and their protection is
the session cookie and the role gate, alone.

**Every path's second segment is `floor`, so `vite.config.ts` needs no edit** —
`test_spa_serving.py` asserts SET EQUALITY between the live route table's second
segments and the manage dev proxy's alternation, and a mismatch breaks only a
developer's machine while production, CI and the whole suite stay green. Mounting
the registry at `/manage/rooms` would have cost that edit; `/manage/floor/rooms`
costs nothing and reads better anyway.

**Real HTTP verbs and a path parameter for the target.** The `.claude/rules` RPC
/ `@QueryValue` guidance is Kotlin boilerplate for another codebase; the shipped
/manage convention is real verbs.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.dependencies import get_current_staff, require_role
from app.auth.service import StaffContext
from app.floor.schemas import (
    AddDressRequest,
    ClaimRoomRequest,
    CreateRoomRequest,
    FloorClientList,
    FloorDressList,
    FloorResponse,
    HandoverRequest,
    RaisedAlert,
    RaiseSosRequest,
    Room,
    SosAlertView,
    SosResponse,
    StaffCard,
    UpdateRoomRequest,
)
from app.floor.service import FloorService, RoomRead
from app.models.constants import StaffRole
from app.schemas import OkResponse
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


# --- F36: the registry (owner + shift_manager) --------------------------------
#
# `ELEVATED` is spelled once and hung on four routes. It composes by INTERSECTION
# with the router's five, so it can only narrow — which is exactly what these
# four need, and why widening the catalog or bookings routers was never the
# alternative for the two pickers below.
ELEVATED = Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))


def _room(read: RoomRead) -> Room:
    """Every mutation answers the SAME shape the payload's `rooms[]` elements
    carry, so the panel patches one tile in place from the server's own row and
    cannot disagree with itself. There is deliberately no separate `RoomCard`."""
    return Room.from_row(read.row, read.bindings)


@router.post("/floor/rooms", dependencies=[ELEVATED])
async def create_room(
    request: Request, service: Service, staff: Staff, body: CreateRoomRequest
) -> Room:
    return _room(
        await service.create_room(
            get_current_tenant(request).id,
            label=body.label,
            sort_order=body.sort_order,
            actor=staff,
        )
    )


@router.patch("/floor/rooms/{room_id}", dependencies=[ELEVATED])
async def update_room(
    request: Request,
    room_id: uuid.UUID,
    service: Service,
    staff: Staff,
    body: UpdateRoomRequest,
) -> Room:
    return _room(
        await service.update_room(
            get_current_tenant(request).id,
            room_id,
            label=body.label,
            sort_order=body.sort_order,
            is_active=body.is_active,
            actor=staff,
        )
    )


@router.delete("/floor/rooms/{room_id}", dependencies=[ELEVATED])
async def delete_room(
    request: Request, room_id: uuid.UUID, service: Service, staff: Staff
) -> OkResponse:
    """The one route here that does not answer a `Room` — there is no tile left
    to render. The service refuses an OCCUPIED room with a 409 naming her."""
    await service.delete_room(get_current_tenant(request).id, room_id, actor=staff)
    return OkResponse()


# --- F36: the claim, the release, the handover --------------------------------


@router.post("/floor/rooms/{room_id}/claim")
async def claim_room(
    request: Request,
    room_id: uuid.UUID,
    service: Service,
    staff: Staff,
    body: ClaimRoomRequest,
) -> Room:
    """⚠ `body.staff_user_id` is the TARGET and is passed as one. The acting
    identity is `staff`, resolved from the session cookie — the same two-axis
    separation the break routes have, on the first body in the product that
    carries a target staff id."""
    return _room(
        await service.claim(
            get_current_tenant(request).id,
            room_id,
            staff_user_id=body.staff_user_id,
            booking_id=body.booking_id,
            actor=staff,
        )
    )


@router.post("/floor/assignments/{assignment_id}/release")
async def release_assignment(
    request: Request, assignment_id: uuid.UUID, service: Service, staff: Staff
) -> Room:
    """No body: the target is the assignment and there is nothing to say about
    it. The two axes apply but cannot run first — whose assignment it is can only
    be learned by reading the row — so the refusal is a 404, not a 403."""
    return _room(await service.release(get_current_tenant(request).id, assignment_id, actor=staff))


@router.post("/floor/assignments/{assignment_id}/handover", dependencies=[ELEVATED])
async def handover_assignment(
    request: Request,
    assignment_id: uuid.UUID,
    service: Service,
    staff: Staff,
    body: HandoverRequest,
) -> Room:
    """⚠ The role check for this route is the `ELEVATED` gate above and NOWHERE
    ELSE — the service carries a comment pointing here rather than a second
    check. Two costs decided it: `FLOOR_OPEN` would have to assert that a
    seamstress may reach a route she always 403s on, and a 403 is TERMINAL for
    the whole floor screen, so a rendered-but-refused control blanks her only
    screen."""
    return _room(
        await service.handover(
            get_current_tenant(request).id,
            assignment_id,
            new_staff_id=body.staff_user_id,
            actor=staff,
        )
    )


# --- F36: the dress bindings (all five, no ownership check — D4) ---------------


@router.post("/floor/assignments/{assignment_id}/dresses")
async def add_dress(
    request: Request,
    assignment_id: uuid.UUID,
    service: Service,
    staff: Staff,
    body: AddDressRequest,
) -> Room:
    return _room(
        await service.add_dress(
            get_current_tenant(request).id,
            assignment_id,
            dress_id=body.dress_id,
            size_label=body.size_label,
            actor=staff,
        )
    )


@router.delete("/floor/assignments/{assignment_id}/dresses/{binding_id}")
async def remove_dress(
    request: Request,
    assignment_id: uuid.UUID,
    binding_id: uuid.UUID,
    service: Service,
    staff: Staff,
) -> Room:
    """`actor` is not decoration on this one: the soft delete stamps `removed_by`
    from it, and that pair IS the audit record for a binding — which is what
    keeps the deliberate absence of an ownership check accountable."""
    return _room(
        await service.remove_dress(
            get_current_tenant(request).id, assignment_id, binding_id, actor=staff
        )
    )


# --- F36: the two one-shot pickers (D16) --------------------------------------


@router.get("/floor/dresses")
async def list_dresses(request: Request, service: Service) -> FloorDressList:
    """Fetched when the dress dialog opens, never on the poll."""
    return FloorDressList.from_read(await service.dresses(get_current_tenant(request).id))


@router.get("/floor/clients")
async def list_clients(request: Request, service: Service) -> FloorClientList:
    """The ONLY producer of `booking_id` anywhere in the console. Today's
    arrivals — checked in and still in the building — never the day book."""
    return FloorClientList.from_read(await service.clients(get_current_tenant(request).id))


# --- F37: the SOS page (all five roles, NOTHING tightened) --------------------
#
# ⚠ **F36 tightened four routes; F37 tightens NONE, and that is a decision rather
# than an omission.** A per-route `RoleGate` can express only a PURE role
# predicate — one that depends on nothing about the target. Every rule in this
# feature reads the ROW: the raise is first-person and has no target rule at all,
# and accept, resolve and cancel each read `target_staff_user_id`, `raised_by` or
# `accepted_by` before they can decide. There is no gate that can say "the person
# this alert names", so all four refusals are 404s from the service.
#
# The four mutating verbs are CSRF-fenced by `CsrfOriginMiddleware` BY METHOD
# rather than by a path list, so they are fenced by construction; the one new GET
# is not, and its protection is the session cookie and the role gate alone.
#
# ⚠ Every path's second segment is still `floor`, so `vite.config.ts` needs NO
# edit. Mounting at `/manage/sos` would have cost one, and the failure would have
# broken only a developer's machine while production, CI and the whole suite
# stayed green, serving the SPA shell where the API should be.


@router.get("/floor/sos")
async def get_sos(request: Request, service: Service, staff: Staff) -> SosResponse:
    """The app-level poll — the one read in this console mounted on every
    section. `staff` is not decoration: the rows are filtered by the audience
    rule against the SESSION's actor, never against anything the request names.
    """
    return SosResponse.from_read(await service.sos(get_current_tenant(request).id, actor=staff))


@router.post("/floor/sos")
async def raise_sos(
    request: Request, service: Service, staff: Staff, body: RaiseSosRequest
) -> RaisedAlert:
    """⚠ The body carries a TARGET and never an actor. `raised_by` is `staff`,
    full stop — nobody may raise a page AS somebody else, not even an owner,
    because an SOS is a first-person statement and an owner who needs help raises
    her own. `RaiseSosRequest` is a `ForbidExtraModel` so a body carrying
    `raised_by` is a 400 rather than a silently ignored key."""
    return RaisedAlert.from_read(
        await service.raise_sos(
            get_current_tenant(request).id,
            target_staff_user_id=body.target_staff_user_id,
            fitting_room_assignment_id=body.fitting_room_assignment_id,
            note=body.note,
            actor=staff,
        )
    )


@router.post("/floor/sos/{alert_id}/accept")
async def accept_sos(
    request: Request, alert_id: uuid.UUID, service: Service, staff: Staff
) -> SosAlertView:
    """«אני מגיעה». No body: the target is the alert and there is nothing to say
    about it — `release_assignment`'s reasoning, and the same 404-not-403 rule,
    for the same reason."""
    return SosAlertView.from_read(
        await service.accept_sos(get_current_tenant(request).id, alert_id, actor=staff)
    )


@router.post("/floor/sos/{alert_id}/resolve")
async def resolve_sos(
    request: Request, alert_id: uuid.UUID, service: Service, staff: Staff
) -> SosAlertView:
    return SosAlertView.from_read(
        await service.resolve_sos(get_current_tenant(request).id, alert_id, actor=staff)
    )


@router.post("/floor/sos/{alert_id}/cancel")
async def cancel_sos(
    request: Request, alert_id: uuid.UUID, service: Service, staff: Staff
) -> SosAlertView:
    """Cancelling an ACCEPTED alert is a 409 naming the acceptor rather than a
    silent close — a colleague is already walking to that curtain."""
    return SosAlertView.from_read(
        await service.cancel_sos(get_current_tenant(request).id, alert_id, actor=staff)
    )
