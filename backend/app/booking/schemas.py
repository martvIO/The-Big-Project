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
