"""Wire models for the PUBLIC storefront API.

**None of these subclass a manage schema, and none ever may.** Inheritance is
exactly how the omissions the spec mandates get silently reverted: one field
added to `DressResponse` for the owner's console and every storefront row would
carry it, with no diff on this file and no failing test in this module.
`test_storefront_api.py` asserts the non-inheritance and the exact field sets.

There is no request model here. The only client-supplied value on this surface is
`offset`, bounded by a `Query(ge=0)` on the route.

Three deliberate absences, each a spec requirement rather than a formatting
preference (`.planning/specs/catalog-management.md`, the two "Note for F10"
blocks):

* **`price_visible` does not ship at all.** Once the number is omitted server-side,
  `price_agorot is None` covers both "the owner hid it" and "no price recorded" —
  which the design renders identically ("מחיר בתיאום"). Dropping the flag makes
  the guarantee structural: there is no code path in which the flag and the
  number can disagree, because the flag never leaves the server. The key is
  serialised as `null` rather than dropped from the object — same security
  property, far better client typing, and the reviewer's question is answered
  here rather than in review.
* **`quantity` never appears.** The public variant shape is
  `{size_label, available}`; raw stock counts are boutique-confidential.
* **`capacity` is not on the hours rule.** It is fitting-room throughput, which is
  the boutique's operational data, not opening hours.
"""

import datetime
from uuid import UUID

from pydantic import BaseModel


class PublicMediaResponse(BaseModel):
    """A presigned GET valid for SIGNED_GET_TTL_SECONDS, plus its expiry so the
    client can refetch before it goes stale. `url` is null when no bucket is
    configured or signing failed — a read never fails over a missing photo.

    Media ids, storage keys, content types, byte sizes and sort orders are all
    absent: the storefront renders an <img>, and nothing else here is its
    business.
    """

    url: str | None
    url_expires_at: datetime.datetime | None


class PublicDressResponse(BaseModel):
    """One catalog card. `description` is omitted on purpose — cards do not
    render it, and carrying it would multiply the 24-row payload for nothing."""

    id: UUID
    name: str
    price_agorot: int | None
    reserved: bool
    cover: PublicMediaResponse | None


class PublicVariantResponse(BaseModel):
    size_label: str
    available: bool


class PublicDressDetailResponse(BaseModel):
    """NOT a subclass of PublicDressResponse: the two shapes differ (cover vs.
    the full gallery, description present vs. absent), and a shared base would
    make one file's edit silently change the other surface."""

    id: UUID
    name: str
    description: str | None
    price_agorot: int | None
    reserved: bool
    variants: list[PublicVariantResponse]
    media: list[PublicMediaResponse]


class PublicDressListResponse(BaseModel):
    # `items` is the house envelope key for paginated collections. `limit` ships
    # even though the client cannot set it — it is what the client pages with.
    items: list[PublicDressResponse]
    total: int
    offset: int
    limit: int


class PublicProfileResponse(BaseModel):
    phone: str | None
    address: str | None
    description: str | None
    maps_url: str | None


class PublicHoursRuleResponse(BaseModel):
    day_of_week: int
    open_time: datetime.time
    close_time: datetime.time


class PublicHoursExceptionResponse(BaseModel):
    """Both times null = closed all day; both set = special hours."""

    date: datetime.date
    open_time: datetime.time | None
    close_time: datetime.time | None
    note: str | None


class PublicBoutiqueResponse(BaseModel):
    # `name` is tenants.name — the display name, not the slug.
    name: str
    profile: PublicProfileResponse
    rules: list[PublicHoursRuleResponse]
    exceptions: list[PublicHoursExceptionResponse]
