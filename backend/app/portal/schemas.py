"""Wire shapes for F24's client portal. Narrow models, never inherited from a
richer schema — the F10 rule.

The one shape this module deliberately does NOT define is the booking detail:
that is `ManageBookingResponse` verbatim (spec D4). Reusing it is the mirror
guarantee — the portal detail and the tokenized page render from one contract,
so they cannot drift into two products.
"""

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
