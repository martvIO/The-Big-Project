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
