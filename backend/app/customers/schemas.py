"""The customer CRM's wire shapes — one list envelope, one detail, one request.

Plain `BaseModel`s used as return-type ANNOTATIONS, never `response_model=`
(the shipped house form — `dashboard/schemas.py:3-5`, and there is no
`response_model=` anywhere in this repo).

**`created_at` is on neither `CustomerRow` nor `CustomerDetail`, deliberately.**
F52's D7 established that `customers.created_at` is meaningless as a "first
seen" date after F15's phone-correction collision branch: the branch re-points a
booking at an existing customer row and leaves both rows alive, so a customer's
row can post-date her own first booking. Shipping it would put a plausible,
WRONG "customer since" date on the one screen an owner would quote back to a
bride. If a first-visit date is ever wanted it is `min(bookings.starts_at)`,
which is a different query with a different meaning. Recorded here because
`created_at` on a list resource is otherwise so standard that its absence is the
thing a reader stops on.
"""

import datetime
import uuid

from pydantic import BaseModel

from app.schemas import ForbidExtraModel


class CustomerRow(BaseModel):
    """**`phone` ships, and that is a departure from `OwnerBookingRow`'s D18
    bulk-PII-export ruling** (`booking/schemas.py:107-114`), argued rather than
    inherited: a day list is a schedule, a customer directory is an index of
    PEOPLE, and the phone is the disambiguator for the shared-name case that
    `ORDER BY name, id` already exists for. The half D18's force actually lands
    on — free-text `notes` — stays detail-only."""

    id: uuid.UUID
    name: str
    phone: str
    tags: list[str]


class CustomerListResponse(BaseModel):
    """An envelope, not F51's bare array: a staff table is single-digit but a
    customer count grows without bound, so the precedent does not transfer.
    `total` is computed under the SAME predicate as the page."""

    items: list[CustomerRow]
    total: int
    offset: int
    limit: int


class CustomerBookingRow(BaseModel):
    """Four fields. `dress_name`, `dress_size`, `seat_index`, `notes`,
    `manage_token_hash` and `phone` are all on `Booking` and none of them ship:
    the booking detail renders them to the same two roles one click away, and a
    CRM row duplicating a detail view is a second place for one fact to drift.
    `appointment_type_name` is the deliberate snapshot (`models/booking.py:19-22`)
    and is correct here for the reason it is correct there — history must render
    as what the customer agreed to."""

    id: uuid.UUID
    starts_at: datetime.datetime
    status: str
    appointment_type_name: str


class SmsLogRow(BaseModel):
    """FIVE fields, and every omission is a ruling (D4).

    `provider_message_id` is an operator's correlation handle for a support
    ticket with Twilio — meaningless to a boutique owner and a third-party
    identifier this product has no reason to publish. `error` is already fenced
    by a shipped comment on the column itself, *"never reaches a response
    body"*; the UI shows `status = 'failed'`, which is the fact the owner can
    act on. `phone` is on the parent already, and repeating it per row invites
    exactly the mental model D3 exists to destroy — that a log row is identified
    by its phone number.

    `kind` and `status` are the RAW enum values (`MessageKind`,
    `MessageStatus`); the console maps each through its own key table and falls
    back to rendering the raw value for an unknown one, the `statusBadge` shape.
    """

    id: uuid.UUID
    created_at: datetime.datetime
    kind: str
    status: str
    body: str


class CustomerDetail(BaseModel):
    """`messages_total` is not decoration (D3): OTP rows are written by an
    anonymous endpoint, never carry a `booking_id`, and are always the newest,
    so fifty of them evict every confirmation and reminder from the window —
    permanently, since there is no pagination and no `kind` filter. Without the
    count the screen would answer "how many messages did you send this person"
    with "fifty"."""

    id: uuid.UUID
    name: str
    phone: str
    notes: str | None
    tags: list[str]
    bookings: list[CustomerBookingRow]
    messages: list[SmsLogRow]
    messages_total: int


class UpdateCustomerRequest(ForbidExtraModel):
    """Every field optional. `None` means NOT SUPPLIED — leave the column alone.
    `""` and `[]` mean CLEAR, the `boutique/validation.py:110` ruling.

    `extra="forbid"`, so an unknown key is a house-shape 400 rather than a
    silently ignored field."""

    notes: str | None = None
    tags: list[str] | None = None
