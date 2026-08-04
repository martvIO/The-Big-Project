"""The owner console's booking surface: thirteen routes on /manage.

**A fourth router on /manage, not new routes in an existing one.** The catalog
and boutique routers are the catalog's and the boutique's; bookings are neither.
Registered after the catalog router in create_app(), carrying the same shadowing
warning the pair already carries — four routers now mount this prefix and a
duplicated (method, path) would silently win or lose on include order.
`test_booking_owner_api.py`'s ROUTES table is what keeps that honest.

**Router-level `_no_store`**, for the reason `booking/router.py:59-64` and
`catalog/router.py:44-56` both state: every response here names a real person's
appointment, her phone and her free-text notes, and setting the header centrally
is what makes the invariant structural — a route added later cannot forget it.

**Path parameters and real HTTP verbs** are the shipped /manage convention
(`boutique/router.py`, `catalog/router.py`). The `.claude/rules` RPC /
`@QueryValue` guidance is Kotlin boilerplate for another codebase.

**Every send is post-commit, here, awaited and discarded** — the
`booking/router.py:18-23, 95-107` pattern for its stated reasons: post-commit
because `NotificationService.send_sms` structurally opens its own sessions and a
provider hang inside the transaction would block commits; awaited rather than
backgrounded so the send happens inside the request's own lifetime;
fire-and-forget because turning a committed mutation into a 503 is a lie. The
service answers an `OwnerMutation` carrying whether anything actually happened,
and this module branches on it. No BackgroundTasks, no asyncio.create_task.
"""

import datetime
import uuid
from collections.abc import Iterable
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.auth.dependencies import get_current_staff, require_role
from app.auth.service import StaffContext
from app.booking.comms import BookingCommsService, CommsTenant
from app.booking.owner import (
    MAX_LIST_OFFSET,
    BookingPayment,
    OwnerBookingService,
    OwnerMutation,
)
from app.booking.router import get_comms_service
from app.booking.schemas import (
    OwnerBookingDetail,
    OwnerBookingListResponse,
    OwnerBookingRow,
    OwnerSlotListResponse,
    OwnerSlotRow,
    PhoneCorrectionRequest,
    RescheduleRequest,
    WalkInBookingRequest,
)
from app.booking.slots import Slot
from app.booking.validation import BOOKING_LIST_DEFAULT_LIMIT, BOOKING_LIST_MAX_LIMIT
from app.models.booking import Booking
from app.models.constants import StaffRole
from app.models.customer import Customer
from app.tenancy.middleware import TenantContext, get_current_tenant

NO_STORE = "no-store"


def get_owner_booking_service(request: Request) -> OwnerBookingService:
    service: OwnerBookingService = request.app.state.owner_booking_service
    return service


def _no_store(response: Response) -> None:
    response.headers["cache-control"] = NO_STORE


# Authorization is the ROUTER-level RoleGate, matching the boutique and catalog
# routers: a route added here cannot forget it, and test_staff_role_gating's
# default-deny walker reads `allowed_roles` off it. Both members are admitted —
# the shift-manager console interview ruled the bookings section is F15's,
# untouched, with near-owner permissions (see spec D20 / Risk 2).
router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)),
    ],
)

# Not a guard — every handler needs the staff row for its audit entry anyway.
# The gate above is what refuses.
Owner = Annotated[StaffContext, Depends(get_current_staff)]
Service = Annotated[OwnerBookingService, Depends(get_owner_booking_service)]
Comms = Annotated[BookingCommsService, Depends(get_comms_service)]


def _comms_tenant(tenant: TenantContext) -> CommsTenant:
    return CommsTenant.from_settings(
        tenant_id=tenant.id, slug=tenant.slug, name=tenant.name, settings=tenant.settings
    )


def _row_fields(
    booking: Booking, customer: Customer | None, payment: BookingPayment | None
) -> dict[str, object]:
    return {
        "id": booking.id,
        "starts_at": booking.starts_at,
        "status": booking.status,
        "attendance_confirmed_at": booking.attendance_confirmed_at,
        "checked_in_at": booking.checked_in_at,
        # A soft-deleted customer renders blank rather than 500-ing the day
        # list: the booking is still the boutique's appointment either way.
        "customer_name": customer.name if customer is not None else "",
        "appointment_type_name": booking.appointment_type_name,
        "dress_name": booking.dress_name,
        # D18 / A1. Null on every booking with no payment row, which is every
        # booking a deposits-off boutique takes — the field is the marker, not a
        # claim that a deposit was expected.
        "payment_status": payment.status if payment is not None else None,
        "refund_due_agorot": payment.refund_due_agorot if payment is not None else None,
        # F50 / D8. On the ROW and not only the detail, the same exception
        # `checked_in_at` above takes and for the same reason: the shift board only
        # ever reads the list. It is also what makes the detail's nullable terms
        # pair readable — a null version alone cannot say whether nobody accepted
        # anything or something broke.
        "source": booking.source,
    }


def _row(
    booking: Booking, customer: Customer | None, payment: BookingPayment | None
) -> OwnerBookingRow:
    return OwnerBookingRow(**_row_fields(booking, customer, payment))  # type: ignore[arg-type]


def _detail(
    booking: Booking, customer: Customer | None, payment: BookingPayment | None
) -> OwnerBookingDetail:
    return OwnerBookingDetail(
        **_row_fields(booking, customer, payment),  # type: ignore[arg-type]
        customer_phone=customer.phone if customer is not None else "",
        notes=booking.notes,
        dress_id=booking.dress_id,
        dress_size=booking.dress_size,
        seat_index=booking.seat_index,
        created_at=booking.created_at,
        terms_version_accepted=booking.terms_version_accepted,
        terms_accepted_at=booking.terms_accepted_at,
        cancelled_at=booking.cancelled_at,
        cancelled_by=booking.cancelled_by,
        # The hash itself never reaches the wire — it is the stored half of a
        # live control credential. Its existence is all the owner is told.
        manage_link_issued=booking.manage_token_hash is not None,
    )


async def _customer_of(
    service: OwnerBookingService, tenant_id: uuid.UUID, booking: Booking
) -> Customer | None:
    return (await _customers(service, tenant_id, [booking.customer_id])).get(booking.customer_id)


async def _customers(
    service: OwnerBookingService, tenant_id: uuid.UUID, ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, Customer]:
    return await service.customers_for(tenant_id, ids)


async def _detail_of(
    service: OwnerBookingService, tenant_id: uuid.UUID, booking: Booking
) -> OwnerBookingDetail:
    return _detail(
        booking,
        await _customer_of(service, tenant_id, booking),
        (await service.payments_for(tenant_id, [booking])).get(booking.id),
    )


@router.get("/bookings")
async def list_bookings(
    request: Request,
    staff: Owner,
    service: Service,
    # Required, and deliberately alone: the console has no all-bookings view,
    # and pre-decided #48's calendar widens this same route with an optional
    # from/to pair when it arrives rather than shipping two spellings of one
    # filter now (D17).
    date: datetime.date,
    # `le=MAX_LIST_OFFSET` at the boundary, and the service clamps again below
    # it: `offset` binds into OFFSET $n::BIGINT, so an unbounded Python int from
    # a non-router caller would die in asyncpg's encoder as a 500.
    offset: Annotated[int, Query(ge=0, le=MAX_LIST_OFFSET)] = 0,
    limit: Annotated[int, Query(ge=1, le=BOOKING_LIST_MAX_LIMIT)] = BOOKING_LIST_DEFAULT_LIMIT,
) -> OwnerBookingListResponse:
    """One Jerusalem calendar day, CANCELLED ROWS INCLUDED — a cancelled row is
    the owner's evidence that the slot re-opened, so it is a constant in the
    repository query and never a `?status=` parameter (D17)."""
    tenant = get_current_tenant(request)
    rows, total = await service.list_day(tenant.id, date=date, offset=offset, limit=limit)
    customers = await _customers(service, tenant.id, {row.customer_id for row in rows})
    # One batch read behind the page, never one per row (D18).
    payments = await service.payments_for(tenant.id, rows)
    return OwnerBookingListResponse(
        items=[_row(row, customers.get(row.customer_id), payments.get(row.id)) for row in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


# F50's create, and the ONLY route on this router with no booking id — there is no
# booking yet. A verb sub-path on the COLLECTION, the `/no-show` `/complete`
# `/check-in` shape one level up. It cannot shadow and cannot be shadowed: every
# other POST here is `/bookings/{booking_id}/<verb>`, two segments deeper.
#
# No route-level `dependencies=`: it inherits the router's
# (OWNER, SHIFT_MANAGER) gate and deliberately does NOT join
# test_staff_role_gating's OWNER_ONLY set. A shift manager runs the floor, and a
# board she cannot act on is not a shift manager's board.
#
# Sends nothing, so it takes no `Comms`: the service returns `manage_token=None`
# because a walk-in gets no SMS control link at all (D2).
@router.post("/bookings/walk-in")
async def create_walk_in_booking(
    request: Request, staff: Owner, service: Service, body: WalkInBookingRequest
) -> OwnerBookingDetail:
    """A real booking for a customer the boutique already holds, starting now and
    already checked in — so every floor verb downstream works on it because it is
    an ordinary booking.

    An unknown customer, an ERASED customer and an unknown or archived appointment
    type are one indistinguishable 404. That is `BookingNotFoundError`'s own rule
    and it is also the right disclosure answer: this route must not tell an
    authenticated caller which of the two ids was the bad one."""
    tenant = get_current_tenant(request)
    result = await service.create_walk_in(
        tenant.id,
        customer_id=body.customer_id,
        appointment_type_id=body.appointment_type_id,
        staff=staff,
    )
    return await _detail_of(service, tenant.id, result.booking)


@router.get("/bookings/{booking_id}")
async def get_booking(
    request: Request, staff: Owner, service: Service, booking_id: uuid.UUID
) -> OwnerBookingDetail:
    tenant = get_current_tenant(request)
    return await _detail_of(service, tenant.id, await service.detail(tenant.id, booking_id))


# Four verb sub-paths rather than one PATCH carrying a `status` field (D7): the
# four transitions are not four values of one operation. Cancel is guarded on a
# FUTURE starts_at, sends an SMS and cancels a pending reminder; no-show and
# complete are guarded on a past one and send nothing; confirm is the undo of a
# mis-tap. One handler would collapse four preconditions and two side-effect
# sets into one body of ifs and one error code.


@router.post("/bookings/{booking_id}/confirm")
async def confirm_booking(
    request: Request, staff: Owner, service: Service, booking_id: uuid.UUID
) -> OwnerBookingDetail:
    """The undo of a mis-tapped no-show or completed. Sends nothing (D13)."""
    tenant = get_current_tenant(request)
    result = await service.confirm(tenant.id, booking_id, staff=staff)
    return await _detail_of(service, tenant.id, result.booking)


@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(
    request: Request, staff: Owner, service: Service, comms: Comms, booking_id: uuid.UUID
) -> OwnerBookingDetail:
    tenant = get_current_tenant(request)
    result = await service.cancel(tenant.id, booking_id, staff=staff)
    if result.changed:
        await comms.notify_owner_cancel(_comms_tenant(tenant), booking=result.booking)
    return await _detail_of(service, tenant.id, result.booking)


@router.post("/bookings/{booking_id}/no-show")
async def mark_no_show(
    request: Request, staff: Owner, service: Service, booking_id: uuid.UUID
) -> OwnerBookingDetail:
    tenant = get_current_tenant(request)
    result = await service.no_show(tenant.id, booking_id, staff=staff)
    return await _detail_of(service, tenant.id, result.booking)


@router.post("/bookings/{booking_id}/complete")
async def mark_completed(
    request: Request, staff: Owner, service: Service, booking_id: uuid.UUID
) -> OwnerBookingDetail:
    tenant = get_current_tenant(request)
    result = await service.complete(tenant.id, booking_id, staff=staff)
    return await _detail_of(service, tenant.id, result.booking)


# F34's pair, and they are two verbs rather than one `/check-in` carrying
# `{"checked_in": bool}` for the reason the four above are four: two guards
# (check-in requires `status = 'confirmed'`, the undo requires nothing), two
# audit actions and two `details` shapes. One handler would collapse all of that
# into a body of ifs.
#
# Both send nothing — check-in texts nobody, the `no-show`/`complete`/`confirm`
# row of F15's post-commit table — and neither takes a request body, so neither
# needs a ForbidExtraModel. Both inherit `_no_store` and the router-level
# RoleGate by construction.


@router.post("/bookings/{booking_id}/check-in")
async def check_in_booking(
    request: Request, staff: Owner, service: Service, booking_id: uuid.UUID
) -> OwnerBookingDetail:
    """Record that this person is physically in the boutique.

    A repeat tap is a 200 carrying the FIRST staffer's timestamp, not an error:
    the outcome the caller wanted is the outcome that holds. The only refusal is
    a booking that is no longer `confirmed`, which rides F15's
    BOOKING_TRANSITION_INVALID — F34 invents no error code."""
    tenant = get_current_tenant(request)
    result = await service.check_in(tenant.id, booking_id, staff=staff)
    return await _detail_of(service, tenant.id, result.booking)


@router.post("/bookings/{booking_id}/undo-check-in")
async def undo_booking_check_in(
    request: Request, staff: Owner, service: Service, booking_id: uuid.UUID
) -> OwnerBookingDetail:
    """The undo of a mis-tapped check-in, with no status guard and no clock
    bound — so its only failure is a 404. A bride checked in and then cancelled
    must still have the mis-tap undoable (D5)."""
    tenant = get_current_tenant(request)
    result = await service.undo_check_in(tenant.id, booking_id, staff=staff)
    return await _detail_of(service, tenant.id, result.booking)


@router.post("/bookings/{booking_id}/reschedule")
async def reschedule_booking(
    request: Request,
    staff: Owner,
    service: Service,
    comms: Comms,
    booking_id: uuid.UUID,
    body: RescheduleRequest,
) -> OwnerBookingDetail:
    """`notify_owner_reschedule` reads the live token off the pending reminder
    the service's transaction already wrote, so the SMS carries the same link
    the future reminder will send. That ordering is enforced by the transaction
    boundary rather than by two calls in the right sequence (D11)."""
    tenant = get_current_tenant(request)
    result = await service.reschedule(
        tenant.id, booking_id, new_starts_at=body.starts_at, staff=staff
    )
    if result.changed:
        await comms.notify_owner_reschedule(_comms_tenant(tenant), booking=result.booking)
    return await _detail_of(service, tenant.id, result.booking)


@router.post("/bookings/{booking_id}/phone")
async def correct_booking_phone(
    request: Request,
    staff: Owner,
    service: Service,
    comms: Comms,
    booking_id: uuid.UUID,
    body: PhoneCorrectionRequest,
) -> OwnerBookingDetail:
    """The corrected number is owner-attested — no OTP — because requiring one
    would require the bride to be reachable at the number that demonstrably does
    not work (D8). The rotation is part of the service's write; this only sends
    the confirmation carrying the token that write minted."""
    tenant = get_current_tenant(request)
    result = await service.correct_phone(tenant.id, booking_id, phone=body.phone, staff=staff)
    await _send_rotation(comms, tenant, result)
    return await _detail_of(service, tenant.id, result.booking)


@router.post("/bookings/{booking_id}/resend-link")
async def resend_booking_link(
    request: Request, staff: Owner, service: Service, comms: Comms, booking_id: uuid.UUID
) -> OwnerBookingDetail:
    """Resend is not a re-send: it invalidates the old link, and the Hebrew says
    so. A plain resend is impossible anyway once the reminder has fired —
    `bookings` stores only the sha256 and `cancel_pending` clears the raw token
    off the terminal row, so nothing on the platform can reproduce a sent link."""
    tenant = get_current_tenant(request)
    result = await service.resend_link(tenant.id, booking_id, staff=staff)
    await _send_rotation(comms, tenant, result)
    return await _detail_of(service, tenant.id, result.booking)


async def _send_rotation(
    comms: BookingCommsService, tenant: TenantContext, result: OwnerMutation
) -> None:
    """sha256 is one-way, so the raw token minted inside the transaction travels
    out on the result or the message has no link to put in it."""
    if result.manage_token is None:
        return
    await comms.send_confirmation(
        _comms_tenant(tenant), booking=result.booking, manage_token=result.manage_token
    )


@router.get("/slots")
async def list_owner_slots(
    request: Request,
    staff: Owner,
    service: Service,
    from_date: Annotated[datetime.date | None, Query(alias="from")] = None,
    to_date: Annotated[datetime.date | None, Query(alias="to")] = None,
) -> OwnerSlotListResponse:
    """A sibling of GET /storefront/slots, not a reuse of it (D6): that route
    spends the anonymous read budget, its projection is contractually blind to
    `capacity` and `remaining`, and the console's dev proxy forwards /manage
    only. The computation is still shared — this is StorefrontService.list_slots
    plus an owner projection, never a second materializer.

    `to < from` raises SlotWindowError, a DomainValidationError subclass, so the
    handler bound to the base already answers it as a 400 with no new code.
    """
    tenant = get_current_tenant(request)
    slots: list[Slot] = await service.list_slots(tenant.id, from_date=from_date, to_date=to_date)
    return OwnerSlotListResponse(
        slots=[
            OwnerSlotRow(starts_at=slot.starts_at, capacity=slot.capacity, remaining=slot.remaining)
            for slot in slots
        ]
    )
