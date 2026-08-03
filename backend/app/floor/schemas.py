"""The floor's wire shapes.

Plain `BaseModel`s used as return-type ANNOTATIONS, never `response_model=` (the
shipped house form). No `ForbidExtraModel`: neither POST takes a body, so there
are no extras to forbid.

**The read is an ENVELOPE, not a bare array.** F51's `/manage/staff` answers a
bare list and that was right for a list — this one is the FLOOR's, and F36 adds
rooms and occupancy to it while F58 adds the waitlist. An envelope makes those
additive; a bare array makes the first of them a breaking shape change on a
screen that polls every five seconds.

⚠ **A card was "a name, a role and a status, and deliberately nothing else"
until F36, and that sentence is now false about this very module**: `StaffCard`
carries `occupancy`, and `Occupancy.client_label` is a customer's name. F58 then
falsified F36's replacement too, by putting up to a hundred waiting names on the
same envelope. What holds instead — one rule for the whole payload — is that it
carries **the minimum customer datum required by the person standing on the
floor: the people who are physically in the boutique right now — one name per
occupied fitting room, plus the name of every walk-in currently waiting to be
served — and never the day's booking book.** Every name leaves the payload the
moment she does.

⚠ **`WaitlistEntry.id` is F33's position-page capability**, and this payload is
the only server path other than the check-in response that emits one. Disclosed
to a signed-in staffer of this tenant and to nobody else, and **the console must
never render it as a link to `/q/{id}`.**

What is still deliberately absent from a card is every stable identifier and
every contact route — no avatar, no phone, no email. `email` in particular is
the one a later reader will reach for as a key: `id` is the key, and the address
of every member of staff is not something a seamstress needs in order to see who
is on a break.
"""

import datetime
import uuid
from collections.abc import Sequence

from pydantic import BaseModel, Field

from app.catalog.validation import MAX_SIZE_LABEL_LENGTH, MAX_SORT_ORDER
from app.db.repositories.fitting_rooms import RoomRow
from app.floor.service import (
    ClientPickerRead,
    DispatchRead,
    DressPickerRead,
    FloorRead,
    WaitlistRead,
    card_status,
)
from app.models.constants import StaffCardStatus
from app.models.fitting_assignment_dress import FittingAssignmentDress
from app.models.staff_user import StaffUser
from app.schemas import ForbidExtraModel


class StaffCard(BaseModel):
    id: uuid.UUID
    display_name: str
    role: str
    status: StaffCardStatus
    # Present so the card can render «מאז 11:20» — the mitigation for a break
    # having no upper bound (D7). NULL whenever `status` is `available`, and the
    # console must not infer one from the other in the opposite direction: F36
    # adds `occupied`, which also carries no break timestamp.
    break_started_at: datetime.datetime | None
    # F36. Non-null EXACTLY when `status` is `occupied`, and null on both other
    # statuses — the two are derived from the same `occupancy` argument, so they
    # cannot disagree. A SIXTH key on this card, and the set-equality assertion
    # over it is what catches a seventh arriving unreviewed on a five-role
    # payload.
    occupancy: "Occupancy | None"

    @classmethod
    def from_row(cls, row: StaffUser, *, occupancy: "RoomRow | None" = None) -> "StaffCard":
        return cls(
            id=row.id,
            display_name=row.display_name,
            role=row.role,
            status=card_status(row, occupied=occupancy is not None),
            break_started_at=row.break_started_at,
            occupancy=Occupancy.from_row(occupancy) if occupancy is not None else None,
        )


class FloorResponse(BaseModel):
    staff: list[StaffCard]
    # EVERY LIVE ROOM — active and inactive — in (sort_order, created_at) order.
    # Inactive rooms ship so the panel can grey them: a room a staffer cannot
    # find is worse than one she can see is out of service.
    rooms: list["Room"]
    # The server's own instant at serialisation. The console computes «כבר 42
    # דק'» against it plus the elapsed device clock, so only the DELTA of a
    # boutique tablet's clock is trusted and never its absolute value.
    server_now: datetime.datetime
    # F58's ONE new envelope key, and the reason the read was an envelope from
    # the start: a bare array would have made this a breaking shape change on a
    # screen that polls every five seconds. There is no second poll and no second
    # endpoint — the waitlist rides the tick the panel already pays for.
    waitlist: "Waitlist"

    @classmethod
    def from_rows(cls, read: "FloorRead") -> "FloorResponse":
        """A PURE RENDERER of one pre-joined structure. It issues no query, and
        keeping it that way is what stops this module growing a second one."""
        return cls(
            staff=[
                StaffCard.from_row(row, occupancy=read.occupancy_by_staff_id.get(row.id))
                for row in read.staff_rows
            ],
            rooms=[
                Room.from_row(
                    row,
                    read.bindings_by_assignment_id.get(row.assignment_id, [])
                    if row.assignment_id is not None
                    else [],
                )
                for row in read.room_rows
            ],
            server_now=read.server_now,
            waitlist=Waitlist.from_read(read.waitlist),
        )


# --- F36: the rooms -----------------------------------------------------------


class DressBinding(BaseModel):
    """One gown in one room. `dress_name` and `dress_size` are the SNAPSHOTS the
    binding row carries, not a live catalog read: the owner may rename or
    archive a dress mid-fitting and the card must render what actually went into
    the room. `dress_id` rides along so an image resolves at read time."""

    id: uuid.UUID
    dress_id: uuid.UUID
    dress_name: str
    dress_size: str | None


class RoomAssignment(BaseModel):
    """The ONE active assignment the partial unique index guarantees a room has
    at most one of, so the read never has to choose between two."""

    id: uuid.UUID
    staff_user_id: uuid.UUID
    # NULLABLE, and the reason is the ghost holder: a staffer soft-deleted from
    # `staff_users` while holding a room leaves this row live with no card on the
    # floor. The join carries no `deleted_at` filter so the name usually still
    # resolves; when the row is gone entirely the tile says so instead of lying.
    staff_display_name: str | None
    staff_role: str | None
    # null = an anonymous visit, which is the DEFAULT rather than an edge case:
    # a staffer prepping a room, or a swept booking, or an erased customer.
    # Resolved on every read from the live rows — never snapshotted here.
    client_label: str | None
    booking_id: uuid.UUID | None
    # The row's `created_at`. There is no `assigned_at` column: the row is
    # created at the instant of the claim, and a handover deliberately does not
    # restart it, because the number a shift manager reads is the CLIENT's time
    # in the room and not the current holder's.
    assigned_at: datetime.datetime
    dresses: list[DressBinding]


class Room(BaseModel):
    """ONE shape for a room, and there is deliberately no separate `RoomCard`.

    Every mutation answers exactly what the payload's `rooms[]` elements carry,
    so the panel patches one tile in place from the server's own row and cannot
    disagree with itself. The registry's answer is simply a `Room` whose
    `assignment` is usually null.
    """

    id: uuid.UUID
    label: str
    sort_order: int
    is_active: bool
    assignment: RoomAssignment | None

    @classmethod
    def from_row(cls, row: RoomRow, bindings: Sequence[FittingAssignmentDress]) -> "Room":
        """A PURE RENDERER of the repository's pre-joined row. Every assignment
        field on `RoomRow` is None together, so `assignment_id` alone decides
        whether the tile is free — no second query, ever, from this module."""
        assignment = None
        if (
            row.assignment_id is not None
            and row.staff_user_id is not None
            and row.assigned_at is not None
        ):
            assignment = RoomAssignment(
                id=row.assignment_id,
                staff_user_id=row.staff_user_id,
                staff_display_name=row.staff_display_name,
                staff_role=row.staff_role,
                client_label=row.client_label,
                booking_id=row.booking_id,
                assigned_at=row.assigned_at,
                dresses=[
                    DressBinding(
                        id=binding.id,
                        dress_id=binding.dress_id,
                        dress_name=binding.dress_name,
                        dress_size=binding.dress_size,
                    )
                    for binding in bindings
                ],
            )
        return cls(
            id=row.room_id,
            label=row.label,
            sort_order=row.sort_order,
            is_active=row.is_active,
            assignment=assignment,
        )


class Occupancy(BaseModel):
    """The staff card's half of the same fact, DENORMALISED on purpose.

    The alternative is a client-side join of `staff` against `rooms`, which is
    one line of code and one architectural cost: the staff-card renderer would
    need `rooms` passed into it, coupling two panels that are otherwise
    independent. Three short strings per occupied room, on a payload that is
    already a list of people.
    """

    assignment_id: uuid.UUID
    fitting_room_id: uuid.UUID
    room_label: str
    client_label: str | None
    assigned_at: datetime.datetime

    @classmethod
    def from_row(cls, row: RoomRow) -> "Occupancy | None":
        """`None` for a free room, so a caller can map the whole room list
        without re-testing the same three fields."""
        if row.assignment_id is None or row.assigned_at is None:
            return None
        return cls(
            assignment_id=row.assignment_id,
            fitting_room_id=row.room_id,
            room_label=row.label,
            client_label=row.client_label,
            assigned_at=row.assigned_at,
        )


# --- F58: the waitlist (D2) ---------------------------------------------------


class WaitlistEntry(BaseModel):
    """One waiting walk-in. EIGHT fields, and the set equality over them is what
    catches a ninth arriving unreviewed on a five-role payload."""

    # ⚠ The ticket id, and it IS F33's capability — whoever holds it can POST
    # /storefront/checkin/position and read that ticket's status. On THIS surface
    # that is not a disclosure: the caller is a signed-in staffer of this tenant,
    # behind the session cookie and the role gate, and what the capability buys
    # is `{id, status, position, called_at}` with no name and no phone in it. It
    # is here because every verb in this feature takes it as the target and there
    # is no lesser id. `TicketView`'s own docstring says the id is issued "by NO
    # OTHER SERVER PATH EVER"; this payload is the second path, deliberately, and
    # the module docstring names it rather than leaving that promise quietly
    # broken. **The console must never render it as a link to `/q/{id}`.**
    id: uuid.UUID
    name: str
    visit_type: str
    # 1-based, and DERIVED FROM THIS LIST'S OWN ORDER (index + 1) — never a
    # second count query. Two derivations of one number are two chances for the
    # wall, her phone and this panel to disagree, which is F59's D3 argument one
    # surface over.
    position: int
    # `created_at`, NOT the sort key. Two facts, two columns: this is when she
    # walked in and it never moves, while `COALESCE(requeued_at, created_at)` is
    # what a skip moves — sending that one would reset the rendered clock to zero
    # on every skip and the panel would say «הגיעה זה עתה» about a woman who has
    # been standing there forty minutes. Sent as an INSTANT so the CLIENT
    # computes the minutes against the envelope's `server_now`, which is
    # `assigned_at`'s rule unchanged.
    arrived_at: datetime.datetime
    # A BOOLEAN, not the timestamp: the panel needs to know WHETHER, and the
    # instant would let anyone with the screen time how long a named woman has
    # been standing at a counter.
    called: bool
    # So the second-skip rule is LEGIBLE rather than surprising. The next skip on
    # an entry with `skip_count >= 1` removes her, and that is destructive with
    # no undo — a control that silently changes meaning on its second press is
    # the shape this number exists to prevent. It is also what the client sends
    # back as `seen_skip_count`, which is what stops the confirm being bypassed.
    skip_count: int
    # D9. "Another live ticket today carries the same phone." The phone itself
    # never reaches the wire — the flag is all that survives the grouping.
    duplicate: bool


class Waitlist(BaseModel):
    entries: list[WaitlistEntry]
    # F36's FloorDressList rule verbatim: the UI renders one line saying the list
    # is partial and names NO count and NO limit, because both are the server's
    # to change without a copy edit.
    truncated: bool

    @classmethod
    def from_read(cls, read: "WaitlistRead") -> "Waitlist":
        """A PURE RENDERER, like `from_rows`. `position` is `index + 1` over the
        server's own order and is computed HERE rather than carried on the read,
        so there is exactly one place it can come from."""
        return cls(
            entries=[
                WaitlistEntry(
                    id=entry.id,
                    name=entry.name,
                    visit_type=entry.visit_type,
                    position=index + 1,
                    arrived_at=entry.arrived_at,
                    called=entry.called,
                    skip_count=entry.skip_count,
                    duplicate=entry.duplicate,
                )
                for index, entry in enumerate(read.entries)
            ],
            truncated=read.truncated,
        )


class DispatchResult(BaseModel):
    """What the two dispatch verbs answer. The tile AND the queue, because they
    are two halves of one act: a client that patched the tile from the response
    and waited up to five seconds for the row to leave the list would render the
    same woman as both in-service and waiting."""

    room: Room
    waitlist: Waitlist

    @classmethod
    def from_read(cls, read: "DispatchRead") -> "DispatchResult":
        return cls(
            room=Room.from_row(read.room.row, read.room.bindings),
            waitlist=Waitlist.from_read(read.waitlist),
        )


# --- F36: the two one-shot pickers (D16) --------------------------------------


class FloorDress(BaseModel):
    """Strictly less than the boutique's own storefront already publishes to an
    anonymous visitor: a name and its size labels. No price, no description, no
    media, no `reserved` flag, no stock quantity."""

    id: uuid.UUID
    name: str
    sizes: list[str]


class FloorDressList(BaseModel):
    dresses: list[FloorDress]
    # The UI renders one line pointing at «שמלות» rather than silently hiding
    # gowns — a hidden item is the one failure a picker may not have.
    truncated: bool

    @classmethod
    def from_read(cls, read: "DressPickerRead") -> "FloorDressList":
        """A PURE RENDERER, like `from_rows`. `.get(id, [])` because the sizes
        map is sparse: a gown with no live variants is ordinary."""
        return cls(
            dresses=[
                FloorDress(id=row.id, name=row.name, sizes=read.sizes_by_dress_id.get(row.id, []))
                for row in read.dresses
            ],
            truncated=read.truncated,
        )


class FloorClient(BaseModel):
    """The people physically in the building — today's checked-in arrivals, not
    the day book. A booking id, a label and a time, and nothing else: no phone,
    no notes, no dress, no size, no status, no manage token, no customer_id."""

    booking_id: uuid.UUID
    client_label: str | None
    starts_at: datetime.datetime


class FloorClientList(BaseModel):
    clients: list[FloorClient]
    truncated: bool

    @classmethod
    def from_read(cls, read: "ClientPickerRead") -> "FloorClientList":
        """`.get(...)` rather than `[...]`: a customer erased since check-in
        leaves her booking live and her row anonymous, which is the same rule the
        payload's `client_label` follows and deliberately not an error."""
        return cls(
            clients=[
                FloorClient(
                    booking_id=row.id,
                    client_label=read.names_by_customer_id.get(row.customer_id),
                    starts_at=row.starts_at,
                )
                for row in read.bookings
            ],
            truncated=read.truncated,
        )


# --- F36: the request bodies --------------------------------------------------


class CreateRoomRequest(ForbidExtraModel):
    """`label` carries NO Field bound: `normalize_room_label` strips first and
    bounds the stripped string, and a `max_length` here would refuse a legal
    forty-character label typed with a trailing space."""

    label: str
    sort_order: int = Field(default=0, ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER)


class UpdateRoomRequest(ForbidExtraModel):
    """Every field optional, and `None` means NOT SUPPLIED — never "clear it".
    The dialog's three controls are independent, so a reorder must leave the
    label alone."""

    label: str | None = None
    sort_order: int | None = Field(default=None, ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER)
    is_active: bool | None = None


class ClaimRoomRequest(ForbidExtraModel):
    """⚠ `staff_user_id` is the TARGET and only ever the target.

    This is the first body in the product to carry a target staff id, which is
    the exact shape `FloorService._authorize`'s docstring names as the hazard:
    a body-supplied id doubling as the caller's identity turns "any staffer on
    herself" into "any staffer on anyone". The acting identity is the
    `StaffContext` resolved from the session cookie, and no code path on the
    claim route may read this field as one.

    Both fields default to None: the caller, and an anonymous visit.
    """

    staff_user_id: uuid.UUID | None = None
    booking_id: uuid.UUID | None = None


class HandoverRequest(ForbidExtraModel):
    """Required — a handover with no recipient is not a release."""

    staff_user_id: uuid.UUID


class TakeNextRequest(ForbidExtraModel):
    """⚠ `staff_user_id` is the TARGET and only ever the target — `ClaimRoomRequest`'s
    rule, verbatim, on the verb that puts a named customer in a room. There is no
    `booking_id`: take-next's client is the head of the queue and nothing else
    can be bound to it."""

    staff_user_id: uuid.UUID | None = None


class AssignRequest(ForbidExtraModel):
    """Push-assign. `queue_ticket_id` is REQUIRED — an assign with no ticket is a
    claim, and the claim already exists."""

    queue_ticket_id: uuid.UUID
    staff_user_id: uuid.UUID | None = None


class SkipRequest(ForbidExtraModel):
    """⚠ `seen_skip_count` is the value the CLIENT RENDERED, and it is the whole
    of what stops two ordinary single taps removing a customer.

    Both managers' tiles said 0, so neither showed the confirm — it is gated on
    `>= 1` — and without this field the second tap escalates to `removed` on a
    count nobody saw. The server refuses on a mismatch (409
    `QUEUE_TICKET_CHANGED`) rather than escalating, so the confirm cannot be
    bypassed by a stale tile.

    No default: a caller that omits it is a caller that did not read a count, and
    guessing 0 for her is the failure this field exists to prevent.
    """

    seen_skip_count: int = Field(ge=0)


class AddDressRequest(ForbidExtraModel):
    """`size_label` is optional: a sample gown carried in before a size is
    chosen binds with a null size and the card renders the name alone."""

    dress_id: uuid.UUID
    size_label: str | None = Field(default=None, max_length=MAX_SIZE_LABEL_LENGTH)
