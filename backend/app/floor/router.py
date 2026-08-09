"""The floor: the read, the two break toggles, the room registry, the claim and
its dress bindings, the two one-shot pickers, F58's five dispatch verbs and F37's
SOS page — twenty-three routes on /manage.

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

⚠ **The justification for that widening has now been falsified TWICE, and this
is its second rewrite.** F57's sentence said the floor payload carries ZERO
customer data; F36's replacement said "at most one name per occupied room"; F58
puts up to a hundred more on it. What is true, and what the widening actually
rests on:

**The floor payload carries the minimum customer datum required by the person
standing on the floor — the people who are physically in the boutique right now:
one name per occupied fitting room, plus the name of every walk-in currently
waiting to be served — and never the day's booking book.** Every name leaves the
payload the moment she does: a released fitting, a served ticket, a skipped-out
ticket, a removed ticket, or midnight Jerusalem. Nothing on it carries a phone,
an email, an address or a consent flag.

⚠ **It DOES carry each waiting ticket's id, and that id is F33's position-page
capability.** This payload is the only server path other than the check-in
response that emits one, so it is disclosed to a signed-in staffer of this tenant
and to nobody else, and **the console must never render it as a link to
`/q/{id}`.** On a surface this feature's own spec calls legally sensitive,
leaving the widest role gate in the product justified by a claim that is no
longer true — or by a new one that understates the disclosure — would be worse
than never having written one.

The distinction that keeps D11's conclusion right — two loops stay two loops:

    GET /manage/bookings?date=   the DAY BOOK. Every customer booked today, with
                                 her appointment type, dress, size, notes,
                                 status, arrival and manage-token surface, for
                                 the whole day, to anyone who opens the section.
                                 Owner and shift_manager. Neither F36 nor F58
                                 puts any of this anywhere.
    GET /manage/floor            the PEOPLE PHYSICALLY IN THE BOUTIQUE RIGHT
                                 NOW — in a fitting room or standing in the
                                 queue. One name each, and nothing else about
                                 her, until she leaves.
    GET /manage/floor/clients    today's arrivals — checked in and still in the
                                 building. A name and an appointment time,
                                 fetched when the panel mounts and after a
                                 claim, never on the tick.

**F37 adds five routes and tightens NONE** — every rule on the SOS page reads the
alert row, and a `RoleGate` can express only a pure role predicate. See the
section comment above those five.

**SIX routes NARROW that gate to owner + shift_manager**, per-route, composing
by intersection (`auth/dependencies.py:44-45`): the three registry verbs,
`handover`, and F58's `skip` and `remove`. The registry is configuration — a
seamstress renaming the boutique's rooms is not a capability anything asks for.
Skip re-orders a stranger's place in a queue and its second press removes her;
remove takes a real customer out of it, irreversibly. `handover` is there rather than in
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

**No rate limiter**: no /manage router carries one and none of F36, F58 or F37
introduces the first. The NINETEEN mutating routes ARE fenced by
CsrfOriginMiddleware (`csrf.py:48` gates on `request.method in MUTATING_METHODS`,
a method test rather than a path list, so the eight F36 adds, the five F58 adds
and the four F37 adds are fenced by construction); the FOUR GETs are not, and
their protection is
the session cookie and the role gate, alone.

**Every path's second segment is `floor`, so `vite.config.ts` needs no edit** —
`test_spa_serving.py` asserts SET EQUALITY between the live route table's second
segments and the manage dev proxy's alternation, and a mismatch breaks only a
developer's machine while production, CI and the whole suite stay green. Mounting
the registry at `/manage/rooms` would have cost that edit, and so would F58's
`/manage/queue/{id}/call`; `/manage/floor/…` costs nothing and reads better
anyway.

**Real HTTP verbs and a path parameter for the target.** The `.claude/rules` RPC
/ `@QueryValue` guidance is Kotlin boilerplate for another codebase; the shipped
/manage convention is real verbs.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.dependencies import get_current_staff, require_role
from app.auth.service import StaffContext
from app.floor.notifications import NotificationsService
from app.floor.schemas import (
    AddDressRequest,
    AssignRequest,
    ClaimRoomRequest,
    CreateRoomRequest,
    DispatchResult,
    FloorClientList,
    FloorDressList,
    FloorResponse,
    HandoverRequest,
    MarkReadRequest,
    MarkReadResponse,
    NotificationListResponse,
    NotificationView,
    RaisedAlert,
    RaiseSosRequest,
    Room,
    SkipRequest,
    SosAlertView,
    SosResponse,
    StaffCard,
    TakeNextRequest,
    UpdateRoomRequest,
    Waitlist,
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


# --- F58: the five dispatch verbs (D11) ---------------------------------------
#
# ⚠ **EVERY PATH'S SECOND SEGMENT IS `floor`**, so `apps/manage/vite.config.ts`
# needs no edit. `test_spa_serving.py` asserts SET EQUALITY between the live
# route table's second segments and the manage dev proxy's alternation, and a
# mismatch breaks ONLY a developer's machine while production, CI and the whole
# suite stay green, serving the SPA shell where the API should be.
# `/manage/queue/{id}/call` reads better and costs exactly that edit.


@router.post("/floor/rooms/{room_id}/take-next")
async def take_next(
    request: Request,
    room_id: uuid.UUID,
    service: Service,
    staff: Staff,
    body: TakeNextRequest,
) -> DispatchResult:
    """⚠ `body.staff_user_id` is the TARGET, never the actor — `claim_room`'s
    rule on the verb that puts a named customer in a room. The service's
    `_authorize` is its first statement, before any read, because a 403 raised
    after one is an existence oracle."""
    return DispatchResult.from_read(
        await service.take_next(
            get_current_tenant(request).id,
            room_id,
            staff_user_id=body.staff_user_id,
            actor=staff,
        )
    )


@router.post("/floor/rooms/{room_id}/assign")
async def assign_from_queue(
    request: Request,
    room_id: uuid.UUID,
    service: Service,
    staff: Staff,
    body: AssignRequest,
) -> DispatchResult:
    return DispatchResult.from_read(
        await service.assign(
            get_current_tenant(request).id,
            room_id,
            queue_ticket_id=body.queue_ticket_id,
            staff_user_id=body.staff_user_id,
            actor=staff,
        )
    )


@router.post("/floor/queue/{ticket_id}/call")
async def call_queue_ticket(
    request: Request, ticket_id: uuid.UUID, service: Service, staff: Staff
) -> Waitlist:
    """ALL FIVE ROLES, and no service-side check either: a summons is not
    destructive and has no target STAFFER, so there is nothing for a
    self-or-elevated rule to compare. Reception, a sales assistant and a
    seamstress all legitimately call the next woman forward."""
    return Waitlist.from_read(
        await service.call(get_current_tenant(request).id, ticket_id, actor=staff)
    )


@router.post("/floor/queue/{ticket_id}/skip", dependencies=[ELEVATED])
async def skip_queue_ticket(
    request: Request, ticket_id: uuid.UUID, service: Service, staff: Staff, body: SkipRequest
) -> Waitlist:
    """⚠ `ELEVATED`, and the ABSENCE of this route from `FLOOR_OPEN` is the
    assertion that the tightening is real.

    There is no middle gate available and that is structural rather than a
    preference: `test_the_floor_roles_reach_exactly_the_floor_routes` classifies
    on the INTERSECTION and then asserts that a floor route admits ALL THREE
    floor roles or none, so `require_role(OWNER, SHIFT_MANAGER, RECEPTION)` would
    red a test its own docstring declares untouchable. Every route in this
    product is all-five or exactly-two. The product cost is real and recorded: a
    reception staffer cannot skip a no-show — she calls a shift manager.

    `body.seen_skip_count` is the value her tile RENDERED, and it is what stops
    two ordinary single taps removing a customer with the confirm bypassed.
    """
    return Waitlist.from_read(
        await service.skip(
            get_current_tenant(request).id,
            ticket_id,
            seen_skip_count=body.seen_skip_count,
            actor=staff,
        )
    )


@router.post("/floor/queue/{ticket_id}/remove", dependencies=[ELEVATED])
async def remove_queue_ticket(
    request: Request, ticket_id: uuid.UUID, service: Service, staff: Staff
) -> Waitlist:
    """`ELEVATED` for skip's reason: this takes a real customer out of the queue,
    irreversibly and with no restore verb. No body — the target is the ticket and
    there is nothing to say about it."""
    return Waitlist.from_read(
        await service.remove(get_current_tenant(request).id, ticket_id, actor=staff)
    )


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


# --- F35: the staff notification bell (all five roles, NOTHING tightened) -----
#
# ⚠ **Two routes on THIS router, and the second path segment is still `floor`.**
# That is the whole reason they live here: `vite.config.ts`'s `MANAGE_API`
# alternation, `e2e/fixtures/manage.ts`'s `API_FAMILIES` and `test_spa_serving.py`'s
# set-equality assertion between them and the live route table all already carry
# `floor`, so an eighteenth segment would cost two edits and buy nothing while
# both producers are floor events. Mounting at `/manage/notifications` would also
# have collided in the reader's head with `app/notifications/`, which is the
# SMS/OTP module and a different thing entirely.
#
# The router's class-level `require_role(*StaffRole)` is the WHOLE gate and no
# per-route dependency narrows it: the bell's audience is every signed-in
# staffer, which is exactly the five the router already admits, so
# `test_staff_role_gating`'s default-deny walker needs no entry.
#
# The POST is CSRF-fenced by `CsrfOriginMiddleware` BY METHOD rather than by a
# path list, so it is fenced by construction. The GET's protection is the session
# cookie and the role gate alone.


def get_notifications_service(request: Request) -> NotificationsService:
    service: NotificationsService = request.app.state.notifications_service
    return service


Notifications = Annotated[NotificationsService, Depends(get_notifications_service)]


@router.get("/floor/notifications")
async def list_notifications(
    request: Request, service: Notifications, staff: Staff
) -> NotificationListResponse:
    """⚠ `staff` is not decoration: the rows are scoped to the SESSION's actor
    and never to anything the request names. There is no `staff_id` query
    parameter here and there must not be one — a route that could answer «show me
    Dana's bell» is a different feature with a different audience rule."""
    rows = await service.recent(get_current_tenant(request).id, actor_id=staff.id)
    return NotificationListResponse(items=[NotificationView.from_row(row) for row in rows])


@router.post("/floor/notifications/read")
async def mark_notifications_read(
    request: Request, service: Notifications, staff: Staff, body: MarkReadRequest
) -> MarkReadResponse:
    """ONE verb for «she tapped it» and «mark all» alike — the difference is the
    length of `ids`, and the console never sends more than the page it rendered.

    Answers HER OWN unread count so the bell updates without waiting a tick.
    """
    unread = await service.mark_read(get_current_tenant(request).id, body.ids, actor_id=staff.id)
    return MarkReadResponse(unread=unread)
