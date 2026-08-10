"""Wire shapes for the storefront join and the manage list/cancel. Narrow
models, never inherited from a richer schema — the F10 rule.
"""

import datetime
import uuid

from pydantic import BaseModel, Field

from app.booking.schemas import MAX_NAME_INPUT_LENGTH, MAX_TOKEN_INPUT_LENGTH
from app.notifications.schemas import MAX_PHONE_INPUT_LENGTH
from app.schemas import ForbidExtraModel


class WaitlistJoinRequest(ForbidExtraModel):
    """EXACTLY the four fields of D2 — no name, no consent, no dress. The
    ForbidExtra posture is what keeps a field D1 deliberately omitted from
    riding in unnoticed as dead weight the schema silently drops."""

    phone: str = Field(min_length=1, max_length=MAX_PHONE_INPUT_LENGTH)
    verification_token: str = Field(min_length=1, max_length=MAX_TOKEN_INPUT_LENGTH)
    day: datetime.date
    appointment_type_id: uuid.UUID


class WaitlistJoinResponse(BaseModel):
    """The WHOLE 201 body, identical on a fresh join and on the idempotent
    duplicate — one shape, one status, no branch a caller can observe.

    NO id, deliberately (D2): there is no customer-side management in F22, and
    an id on the wire is a capability shape with no consumer (F58's A29
    lesson). NO phone echo either — she typed it."""

    day: datetime.date
    appointment_type_id: uuid.UUID
    status: str


class WaitlistOfferTokenRequest(ForbidExtraModel):
    """The lookup and the decline body. The token travels in a BODY, never a
    path or a query — `manage.py` D7's rule, and the reason is that an access log
    holding a live claim credential is a credential leak with a retention
    policy."""

    token: str = Field(min_length=1, max_length=MAX_TOKEN_INPUT_LENGTH)


class WaitlistOfferClaimRequest(ForbidExtraModel):
    """EXACTLY three fields. No phone (the entry carries the proven one), no
    verification token (possession of the offer token IS the proof, the same
    posture as `/b/{token}`), no dress, no consent, no notes."""

    token: str = Field(min_length=1, max_length=MAX_TOKEN_INPUT_LENGTH)
    name: str = Field(min_length=1, max_length=MAX_NAME_INPUT_LENGTH)
    terms_version: int


class WaitlistOfferResponse(BaseModel):
    """What `/w/{token}` renders from, and nothing more.

    NO phone echo and NO entry id: she typed neither and the page needs neither.
    NO boutique name — the storefront layout already has it from the host.

    `status` is a PROJECTION, not the row's column: an `offered` row whose
    deadline has passed reads `expired` here, because the cascade sweeps on a
    60-second tick and the page must never render a live offer over a dead
    deadline. The claim's own SQL guard says the same thing, which is what keeps
    this a display concern rather than a second source of truth.
    """

    status: str
    starts_at: datetime.datetime | None
    expires_at: datetime.datetime | None
    appointment_type_name: str | None


class ManageWaitlistRow(BaseModel):
    """One row of the console list (D5). The phone ships deliberately: it is
    the disambiguator and the owner's only way to call her —
    `customers/schemas.py`'s reasoning. `customer_name` is a decoration off one
    (tenant, phone) customers lookup; null for a phone the boutique has never
    booked."""

    id: uuid.UUID
    day: datetime.date
    appointment_type_id: uuid.UUID
    appointment_type_name: str | None
    phone: str
    customer_name: str | None
    status: str
    created_at: datetime.datetime
    # F23 D8. The console's WHOLE share of the offer: is anyone holding this
    # slot right now, and until when. Null on every row that is not `offered`.
    #
    # ⚠ NOT `offer_token_hash`, which sits one column away on the same row. It
    # is the live claim credential and it ships to nobody — not even an owner,
    # who has no use for it and whose session is one shoulder away from a bride
    # whose seat it would take.
    offer_starts_at: datetime.datetime | None = None
    offer_expires_at: datetime.datetime | None = None


class ManageWaitlistResponse(BaseModel):
    """`(day, created_at)` order — FIFO visible as list order, which IS the
    position (D1: computed nowhere, returned to no one). No pagination: the
    population is bounded by the booking horizon × realistic queue depth (D5's
    recorded ceiling; F25/F29 revisit if a tenant proves it wrong)."""

    entries: list[ManageWaitlistRow]
