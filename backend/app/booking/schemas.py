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
    # F20 D6. DEFAULT FALSE, and the default is the compliance property rather
    # than a convenience: an omitted key must never be able to mean "she agreed".
    # There is no boolean column behind it — consent is the PRESENCE of a
    # timestamp on `customers`, so there is no `server_default` a later migration
    # could flip to opt-out, and the unticked case issues no statement at all.
    marketing_consent: bool = False


class BookingCreateResponse(BaseModel):
    """What the confirmation screen needs and nothing else — no customer id, no
    seat index, no terms bookkeeping on the anonymous wire.

    The three deposit fields (F19 D11/D13) answer one question the screen cannot
    otherwise ask: is money owed, and where does she pay it. `status` is
    `pending_payment` exactly when `deposit_due` is true — a seat held with the
    money not yet in. `payment_session_id` is the POLL credential, deliberately
    not the manage token: it is already client-visible by construction (it is
    embedded in the hosted-page URL the browser is about to visit) and
    possession of it authorises nothing but a status read.

    Both nullable fields stay null unless a deposit is due — including on MD4's
    compensated path, where the gateway was unreachable and the booking stands
    with no deposit taken.
    """

    id: uuid.UUID
    starts_at: datetime.datetime
    status: str
    appointment_type_name: str
    dress_name: str | None
    dress_size: str | None
    deposit_due: bool = False
    redirect_url: str | None = None
    payment_session_id: str | None = None


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
    # F19 A3, and MD3 cannot ship without it. The cancel screen renders
    # `cancelConsequenceDeposit` on ANY booking that took a deposit — including a
    # `confirmed` one that was paid weeks ago — so `status` alone cannot answer
    # it, and `cancelConsequenceFree` ("cancelling is free") survives only where
    # this is False. A BOOLEAN and never the sum: the payload is possession-authed
    # and deliberately carries no money fact about a person it refuses to name.
    deposit_taken: bool


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
    # F34: when a staffer recorded that she is physically here. On the ROW and
    # not only the detail, because the shift board only ever reads the list.
    # Orthogonal to `status` and to `attendance_confirmed_at` above — that one is
    # the BRIDE saying she is coming, this one is a staffer saying she arrived.
    checked_in_at: datetime.datetime | None
    customer_name: str
    appointment_type_name: str
    dress_name: str | None
    # F50: which surface created this booking, 'storefront' | 'walk_in'. On the ROW
    # and not only the detail, for the reason `checked_in_at` above is — the shift
    # board only ever reads the list. It is also the DISCRIMINATOR the nullable
    # terms pair on the detail below needs: a null version alone cannot say whether
    # nobody accepted anything or something broke (D8).
    source: str
    # F19 D18: the ONLY owner-facing payment surface in the product, on the list
    # she already loads every morning — no new route, no nav row. `paid` on a
    # `cancelled` booking is the action-needed marker (MD1's reschedule is the
    # button behind it), and `failed` is MD4's "booked without a deposit, the
    # provider was unavailable". Null wherever no payment row exists.
    payment_status: str | None
    # F19 A1/D16: COMPUTED from the accepted terms version against `starts_at`,
    # never stored — F19 writes no `refund_due` / `refunded` / `forfeited` row
    # anywhere, because the port ships no `refund()`. Display only, and null
    # unless the deposit was actually taken.
    refund_due_agorot: int | None


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
    # NULLABLE since F50, on both, and always as a PAIR — a walk-in booking has no
    # terms evidence because nobody accepted anything, and `source` on the row
    # above is what says WHY the pair is null rather than leaving the console
    # guessing between "created in the boutique" and "something broke".
    terms_version_accepted: int | None
    terms_accepted_at: datetime.datetime | None
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


class WalkInBookingRequest(ForbidExtraModel):
    """TWO REQUIRED UUIDS, AND EVERY ABSENCE IS A RULING (F50 D3).

    No name and no phone: a staffer picking a customer the boutique already holds
    OBTAINS NOTHING FROM THE SUBJECT, so this is not a §11 collection point, owes
    no notice, and needs no public-facing Hebrew. A dialog that typed a name and a
    number would be a fourth collection point whose notice could only be delivered
    by instructing a staffer to recite it aloud — unenforceable delivery dressed as
    compliance. An unknown customer is a 404 and F33's `/checkin` form is her
    route in.

    No `marketing_consent`, and the correct value is NO FIELD rather than `false`:
    a field is something a caller can set, and an absent field is the only spelling
    of "this surface cannot express consent" that a future caller cannot flip.

    No `starts_at`: the instant is the server's `now` and that is a safety
    mechanism before it is a timestamp — it puts the row outside four SHIPPED
    writers (the manage-link backfill's feed, `_guard_live`'s rotation guard,
    `owner.cancel`'s future-only split, and the reminder band). Letting a staffer
    pick a time re-arms all four, which is exactly why that is the remote half.

    No `notes`: a staffer's free text about a bride is personal data obtained NOT
    from her, on the one path that otherwise collects nothing — and `customers.notes`
    is the shipped home for it.

    `ForbidExtraModel`, so any of the above arriving anyway is a 400 rather than a
    silently ignored key.
    """

    customer_id: uuid.UUID
    appointment_type_id: uuid.UUID
