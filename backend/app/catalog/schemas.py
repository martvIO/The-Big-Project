"""Wire models for the /manage catalog API. Requests forbid unknown keys and
carry Field bounds mirroring app/catalog/validation.py exactly; deeper domain
rules (label normalisation, duplicate sizes, the accepted content-type set)
live there and surface as house-shape 400s.

`ConfigDict(from_attributes=True)` applies to **VariantResponse only** — it is
the sole pure ORM projection. DressResponse, DressDetailResponse and
MediaResponse carry fields that are not columns (out_of_stock, media_count,
cover, archived, url, …), so model_validate(row) would raise; the router builds
them from the service's frozen DressView / MediaView instead.
"""

import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.catalog.validation import (
    MAX_DRESS_DESCRIPTION_LENGTH,
    MAX_DRESS_NAME_LENGTH,
    MAX_MEDIA_PER_DRESS,
    MAX_PRICE_AGOROT,
    MAX_RESERVATION_NOTES_LENGTH,
    MAX_SIZE_LABEL_LENGTH,
    MAX_SORT_ORDER,
    MAX_UPLOAD_BYTES,
    MAX_VARIANT_QUANTITY,
    MAX_VARIANTS_PER_DRESS,
    MIN_UPLOAD_BYTES,
)
from app.schemas import ForbidExtraModel

# Long enough for any accepted type and short enough that a megabyte of junk
# never reaches the validator. The authoritative set is ACCEPTED_CONTENT_TYPES.
MAX_CONTENT_TYPE_LENGTH = 64


# --- dresses ---


class CreateDressRequest(ForbidExtraModel):
    name: str = Field(min_length=1, max_length=MAX_DRESS_NAME_LENGTH)
    description: str | None = Field(default=None, max_length=MAX_DRESS_DESCRIPTION_LENGTH)
    price_agorot: int | None = Field(default=None, ge=1, le=MAX_PRICE_AGOROT)
    price_visible: bool = True
    reserved: bool = False
    sort_order: int = Field(default=0, ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER)


class UpdateDressRequest(ForbidExtraModel):
    """Full replace — every field is required so an omitted key can never
    silently clear a value.

    The nullable scalars are required WITH NO DEFAULT: copying
    CreateDressRequest's `default=None` into this model reintroduces exactly the
    bug the full-replace rule exists to prevent.
    """

    name: str = Field(min_length=1, max_length=MAX_DRESS_NAME_LENGTH)
    description: str | None = Field(max_length=MAX_DRESS_DESCRIPTION_LENGTH)
    price_agorot: int | None = Field(ge=1, le=MAX_PRICE_AGOROT)
    price_visible: bool
    reserved: bool
    sort_order: int = Field(ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER)


# --- variants ---


class VariantRequest(ForbidExtraModel):
    size_label: str = Field(min_length=1, max_length=MAX_SIZE_LABEL_LENGTH)
    quantity: int = Field(ge=0, le=MAX_VARIANT_QUANTITY)
    sort_order: int = Field(default=0, ge=-MAX_SORT_ORDER, le=MAX_SORT_ORDER)


class ReplaceVariantsRequest(ForbidExtraModel):
    variants: list[VariantRequest] = Field(max_length=MAX_VARIANTS_PER_DRESS)


class VariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    size_label: str
    # Manage-only: the storefront shape is {size_label, available} — raw stock
    # counts are boutique-confidential (spec, Note for F10).
    quantity: int
    sort_order: int


# --- media ---


class PresignRequest(ForbidExtraModel):
    """Exactly two fields, and neither influences the key: tenant_id comes from
    the host-derived context and dress_id from a dress row this tenant owns."""

    content_type: str = Field(min_length=1, max_length=MAX_CONTENT_TYPE_LENGTH)
    byte_size: int = Field(ge=MIN_UPLOAD_BYTES, le=MAX_UPLOAD_BYTES)


class ReorderMediaRequest(ForbidExtraModel):
    media_ids: list[UUID] = Field(max_length=MAX_MEDIA_PER_DRESS)


class MediaResponse(BaseModel):
    id: UUID
    sort_order: int
    content_type: str
    byte_size: int
    # null when no bucket is configured — reads keep working with the gallery
    # unrendered, and only the media write endpoints answer 503.
    url: str | None
    url_expires_at: datetime.datetime | None


class PresignResponse(BaseModel):
    media_id: UUID
    url: str
    # Bearer material for the whole TTL: never logged, never in an error, and
    # returned with Cache-Control: no-store.
    fields: dict[str, str]
    expires_in: int
    max_bytes: int


# --- dresses (responses) ---


class DressResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    price_agorot: int | None
    price_visible: bool
    reserved: bool
    sort_order: int
    # Derived, never stored: the variant rows are the single source of truth for
    # stock, so a badge can never disagree with the matrix.
    out_of_stock: bool
    total_quantity: int
    variant_count: int
    # Ready rows only — a pending row is an unverified object.
    media_count: int
    cover: MediaResponse | None
    archived: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None


class DressDetailResponse(DressResponse):
    variants: list[VariantResponse]
    media: list[MediaResponse]
    media_uploads_enabled: bool
    # MAX_MEDIA_PER_DRESS − (ready + non-expired pending). The only number the
    # client uses to enable the file input; MEDIA_LIMIT_REACHED stays the
    # server-side authority and a stale client converges after one refetch.
    media_slots_remaining: int


class DressListResponse(BaseModel):
    # `items` is the house envelope key for paginated collections.
    items: list[DressResponse]
    total: int
    offset: int
    limit: int


# --- reservations (F28) ---


class CreateReservationRequest(ForbidExtraModel):
    """`ends_on` is INCLUSIVE. Both dates are plain `date` and not datetimes: a
    rental leaves and returns on calendar days, and letting an instant onto this
    boundary is how a UTC-vs-Jerusalem off-by-one gets in.

    The ORDER of the two dates and the span ceiling are NOT expressible as Field
    bounds — they are cross-field rules — so they live in `validate_reservation`
    and surface as the same house-shape 400.
    """

    starts_on: datetime.date
    ends_on: datetime.date
    # Optional CRM POINTER, never a name (D7). A renter who is not in CRM goes
    # in `notes`.
    customer_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=MAX_RESERVATION_NOTES_LENGTH)


class ReservationResponse(BaseModel):
    id: UUID
    starts_on: datetime.date
    ends_on: datetime.date
    customer_id: UUID | None
    # RESOLVED at read time from the live customer row — not a column, which is
    # why this is not a `from_attributes` projection. None means no pointer, or a
    # pointer whose customer is gone.
    customer_name: str | None
    notes: str | None
    created_at: datetime.datetime


class ReservationListResponse(BaseModel):
    items: list[ReservationResponse]
