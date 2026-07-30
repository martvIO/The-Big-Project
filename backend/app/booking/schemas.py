"""Wire shapes for the public booking surface. None of these subclass anything
from a manage schema, per the F10 rule — the public wire is defined by narrow
models, never by inheritance from a richer one.

Generous ceilings, not product policy: the real bounds (name 80, notes 500, the
dress/size pairing) live in validate_booking_request and answer a clean domain
400. These only stop a megabyte body from reaching the service layer.
"""

import datetime
import uuid

from pydantic import AwareDatetime, BaseModel, Field

from app.notifications.schemas import MAX_PHONE_INPUT_LENGTH
from app.schemas import ForbidExtraModel

# token_urlsafe(32) is 43 chars; 3x headroom.
MAX_TOKEN_INPUT_LENGTH = 128
MAX_NAME_INPUT_LENGTH = 200
MAX_NOTES_INPUT_LENGTH = 2000
# Catalog size labels cap at 32; anything longer can never match a variant.
MAX_SIZE_INPUT_LENGTH = 64


class BookingCreateRequest(BaseModel):
    phone: str = Field(min_length=1, max_length=MAX_PHONE_INPUT_LENGTH)
    verification_token: str = Field(min_length=1, max_length=MAX_TOKEN_INPUT_LENGTH)
    name: str = Field(min_length=1, max_length=MAX_NAME_INPUT_LENGTH)
    appointment_type_id: uuid.UUID
    # AwareDatetime, so a naive timestamp is a schema 400 and the service only
    # ever compares real instants against the grid.
    starts_at: AwareDatetime
    terms_version: int = Field(ge=1)
    dress_id: uuid.UUID | None = None
    dress_size: str | None = Field(default=None, max_length=MAX_SIZE_INPUT_LENGTH)
    notes: str | None = Field(default=None, max_length=MAX_NOTES_INPUT_LENGTH)


class BookingCreateResponse(BaseModel):
    """What the confirmation screen needs and nothing else — no customer id, no
    seat index, no terms bookkeeping on the anonymous wire."""

    id: uuid.UUID
    starts_at: datetime.datetime
    status: str
    appointment_type_name: str
    dress_name: str | None
    dress_size: str | None


class ManageTokenRequest(BaseModel):
    """The one request body all three manage endpoints take.

    The token is in the BODY and never a path or query parameter, so no access
    log, referrer or proxy trace carries the credential (D7). `max_length` is the
    same generous ceiling as `verification_token` — the real check is the hash
    comparison, this only stops a megabyte from reaching the service.
    """

    token: str = Field(min_length=1, max_length=MAX_TOKEN_INPUT_LENGTH)


class ManageBookingFacts(BaseModel):
    """The snapshots the page renders. No customer name, no phone, no id, no
    seat index, no notes — the link is possession-auth, so the payload carries
    the appointment's facts and no PII beyond them (spec Risk 4)."""

    starts_at: datetime.datetime
    status: str
    attendance_confirmed_at: datetime.datetime | None
    appointment_type_name: str
    dress_name: str | None
    dress_size: str | None


class ManagePolicy(BaseModel):
    """From the ACCEPTED terms version, never the current one. `terms_text` is
    deliberately absent: the page states the window and the consequence, and the
    full policy she already accepted is not what this screen is for."""

    refundable_until_hours_before: int
    forfeit_percent: int


class ManageBoutique(BaseModel):
    """The ContactPanel subset of BoutiqueResponse — four fields, not the whole
    profile, so a key a later feature adds to `profile` cannot reach this page by
    default."""

    name: str
    phone: str | None
    address: str | None
    maps_url: str | None


class ManageBookingResponse(BaseModel):
    """Lookup, confirm-attendance and cancel all answer THIS shape, post-action,
    so the page re-renders every state from one response type instead of
    branching on which call it made."""

    booking: ManageBookingFacts
    policy: ManagePolicy | None
    boutique: ManageBoutique


class OwnerBookingRow(BaseModel):
    """One line of the owner's day list.

    Deliberately WITHOUT `customer_phone` and `notes` (D18): the list is a
    glance at the day, the phone and the free text are what the owner opens a
    booking to see. Keeping them off the row means the list response is not a
    bulk PII export of the boutique's whole day.
    """

    id: uuid.UUID
    starts_at: datetime.datetime
    status: str
    attendance_confirmed_at: datetime.datetime | None
    customer_name: str
    appointment_type_name: str
    dress_name: str | None


class OwnerBookingListResponse(BaseModel):
    # `items` is the house envelope key for paginated collections.
    items: list[OwnerBookingRow]
    total: int
    offset: int
    limit: int


class OwnerBookingDetail(OwnerBookingRow):
    """Every list field plus the ones the owner opened the booking for.

    Subclassing runs NARROW → RICH here, the `DressDetailResponse(DressResponse)`
    direction, which is the opposite of the one the module docstring bars: no
    public model inherits from this, so no field added here can reach an
    anonymous surface by default.

    **`ManageBookingFacts` is not the precedent here, and must not be copied.**
    That shape is deliberately PII-free because it answers an anonymous token —
    possession-auth, so it carries the appointment's facts and nothing about
    the person. This one answers an authenticated owner over a session-authed,
    CSRF-fenced, `no-store` surface, and the reasoning inverts: the operational
    point of the screen is that she can phone the bride and read what she wrote
    (D18).

    `manage_token_hash` is nevertheless absent, and that is not an oversight —
    it is the stored half of a live control credential, so the wire carries only
    `manage_link_issued`, which is `manage_token_hash is not None`.
    """

    customer_phone: str
    notes: str | None
    dress_id: uuid.UUID | None
    dress_size: str | None
    seat_index: int
    created_at: datetime.datetime
    terms_version_accepted: int
    terms_accepted_at: datetime.datetime
    cancelled_at: datetime.datetime | None
    cancelled_by: str | None
    manage_link_issued: bool


class OwnerSlotRow(BaseModel):
    """The owner's slot grid carries `capacity` and `remaining`, which
    `SlotRow` fences off the anonymous storefront (it "discloses how many
    parallel fittings the boutique runs"). That fence is about anonymous
    visitors; an owner picking a reschedule target legitimately needs to know
    whether she is about to take the last place (D6)."""

    starts_at: datetime.datetime
    capacity: int
    remaining: int


class OwnerSlotListResponse(BaseModel):
    slots: list[OwnerSlotRow]


class RescheduleRequest(ForbidExtraModel):
    # AwareDatetime, so a naive timestamp is a schema 400 and the service only
    # ever compares real instants against the grid.
    starts_at: AwareDatetime


class PhoneCorrectionRequest(ForbidExtraModel):
    phone: str = Field(min_length=1, max_length=MAX_PHONE_INPUT_LENGTH)
