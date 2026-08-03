"""The floor's wire shapes.

Plain `BaseModel`s used as return-type ANNOTATIONS, never `response_model=` (the
shipped house form). No `ForbidExtraModel`: neither POST takes a body, so there
are no extras to forbid.

**The read is an ENVELOPE, not a bare array.** F51's `/manage/staff` answers a
bare list and that was right for a list — this one is the FLOOR's, and F36 adds
rooms and occupancy to it while F58 adds the waitlist. An envelope makes those
additive; a bare array makes the first of them a breaking shape change on a
screen that polls every five seconds.

**A card is a name, a role and a status, and deliberately nothing else** — no
avatar, no phone, no email. `email` in particular is the one a later reader will
reach for as a stable key: `id` is the key, and the address of every member of
staff is not something a seamstress needs in order to see who is on a break.
"""

import datetime
import uuid
from collections.abc import Sequence

from pydantic import BaseModel, Field

from app.catalog.validation import MAX_SIZE_LABEL_LENGTH, MAX_SORT_ORDER
from app.db.repositories.fitting_rooms import RoomRow
from app.floor.service import card_status
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

    @classmethod
    def from_row(cls, row: StaffUser) -> "StaffCard":
        return cls(
            id=row.id,
            display_name=row.display_name,
            role=row.role,
            status=card_status(row),
            break_started_at=row.break_started_at,
        )


class FloorResponse(BaseModel):
    staff: list[StaffCard]

    @classmethod
    def from_rows(cls, rows: list[StaffUser]) -> "FloorResponse":
        return cls(staff=[StaffCard.from_row(row) for row in rows])


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


class AddDressRequest(ForbidExtraModel):
    """`size_label` is optional: a sample gown carried in before a size is
    chosen binds with a null size and the card renders the name alone."""

    dress_id: uuid.UUID
    size_label: str | None = Field(default=None, max_length=MAX_SIZE_LABEL_LENGTH)
