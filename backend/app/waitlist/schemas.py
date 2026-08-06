"""Wire shapes for the storefront join and the manage list/cancel. Narrow
models, never inherited from a richer schema — the F10 rule.
"""

import datetime
import uuid

from pydantic import BaseModel, Field

from app.booking.schemas import MAX_TOKEN_INPUT_LENGTH
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


class ManageWaitlistResponse(BaseModel):
    """`(day, created_at)` order — FIFO visible as list order, which IS the
    position (D1: computed nowhere, returned to no one). No pagination: the
    population is bounded by the booking horizon × realistic queue depth (D5's
    recorded ceiling; F25/F29 revisit if a tenant proves it wrong)."""

    entries: list[ManageWaitlistRow]
