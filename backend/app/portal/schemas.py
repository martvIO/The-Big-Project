"""Wire shapes for F24's client portal. Narrow models, never inherited from a
richer schema — the F10 rule.

The one shape this module deliberately does NOT define is the booking detail:
that is `ManageBookingResponse` verbatim (spec D4). Reusing it is the mirror
guarantee — the portal detail and the tokenized page render from one contract,
so they cannot drift into two products.
"""

import datetime
import uuid

from pydantic import BaseModel, Field

from app.booking.schemas import MAX_TOKEN_INPUT_LENGTH
from app.notifications.schemas import MAX_PHONE_INPUT_LENGTH
from app.schemas import ForbidExtraModel


class PortalSessionRequest(ForbidExtraModel):
    """The login body: a phone and the single-use verification token
    `/storefront/otp/verify` minted for it. NO name and NO consent — login never
    creates a customer (spec D1), because `customers.name` is NOT NULL and only
    a booking supplies a name."""

    phone: str = Field(min_length=1, max_length=MAX_PHONE_INPUT_LENGTH)
    verification_token: str = Field(min_length=1, max_length=MAX_TOKEN_INPUT_LENGTH)


class PortalSessionResponse(BaseModel):
    """The whole body of both the mint and `GET /portal/me`. One shape on
    purpose: the SPA bootstraps on `me` and renders the same header off either.

    NO customer_id, NO phone: the cookie is the capability and she typed the
    number — an id on the wire is a handle with no consumer.
    """

    customer_name: str


class PortalBookingRow(BaseModel):
    """One line of "My Bookings". The SAME seven facts the design's §3 row
    renders and nothing else — no manage token (the portal authenticates by
    cookie and a capability on a list row would be a capability in a scroll),
    no customer name (she knows it), no notes (the boutique's free text about
    her is not this screen's).

    `pending_payment` rows appear in `upcoming` with their status: the seat is
    hers, the money is not in, and hiding the row would make an appointment she
    can still lose invisible."""

    id: uuid.UUID
    starts_at: datetime.datetime
    status: str
    attendance_confirmed_at: datetime.datetime | None
    appointment_type_name: str
    dress_name: str | None
    dress_size: str | None


class PortalBookingsResponse(BaseModel):
    """Split on `starts_at` vs now, upcoming ASC and past DESC — the ORDER IS
    THE CONTRACT, and the client re-sorts nothing. Two lists rather than one
    with a flag: the page renders two sections with two empty states, and a
    client-side split would put the boundary clock in the browser."""

    upcoming: list[PortalBookingRow]
    past: list[PortalBookingRow]


class PortalBookingIdRequest(ForbidExtraModel):
    """The body of both mirrored actions. A booking id is not a secret — the
    cookie is the capability — but it rides a POST body rather than a query
    string because these are mutations, and ForbidExtra is what keeps a manage
    token from being smuggled in beside it."""

    id: uuid.UUID
