"""Wire models for the PUBLIC storefront API.

**None of these subclass a manage schema, and none ever may.** Inheritance is
exactly how the omissions the spec mandates get silently reverted: one field
added to `DressResponse` for the owner's console and every storefront row would
carry it, with no diff on this file and no failing test in this module.
`test_storefront_api.py` asserts the non-inheritance and the exact field sets.

There is no request model here — the only client-supplied values on this surface
are `offset` and `limit`, both bounded by `Query(...)` on the route.

Four deliberate absences, each a spec requirement rather than a formatting
preference:

* **`price_visible` does not ship at all.** Once the number is omitted
  server-side, `price_agorot is None` covers both "the owner hid it" and "no
  price recorded" — which the design renders identically ("מחיר בתיאום").
  Dropping the flag makes the guarantee structural: there is no code path in
  which the flag and the number can disagree, because the flag never leaves the
  server. The key is serialised as `null` rather than dropped from the object —
  same security property, far better client typing, and a client that could
  tell the two cases apart could tell that *this* dress has a hidden price.
* **`quantity` never appears.** The public size shape is
  `{size_label, available}`; raw stock counts are boutique-confidential.
* **`out_of_stock`, `total_quantity` and `variant_count` are never even
  computed** — see the module docstring of `service.py`.
* **`capacity` is not on the hours row.** It is fitting-room throughput, which
  discloses how many parallel fittings the boutique runs.
"""

import datetime
from uuid import UUID

from pydantic import BaseModel


class StorefrontMedia(BaseModel):
    """A presigned GET valid for SIGNED_GET_TTL_SECONDS, plus its expiry so the
    client can refetch before it goes stale. `url` is null when no bucket is
    configured or signing failed — a read never fails over a missing photo.

    Media ids, storage keys, content types, byte sizes and sort orders are all
    absent: the storefront renders an <img>, and nothing else here is its
    business.
    """

    url: str | None
    url_expires_at: datetime.datetime | None


class StorefrontDress(BaseModel):
    """One catalog card. `description` is omitted on purpose — cards do not
    render it, and carrying it would multiply the 24-row payload for nothing."""

    id: UUID
    name: str
    price_agorot: int | None
    reserved: bool
    cover: StorefrontMedia | None


class SizeChip(BaseModel):
    size_label: str
    available: bool


class UnavailableRange(BaseModel):
    starts_on: datetime.date
    ends_on: datetime.date


class StorefrontDetail(BaseModel):
    """NOT a subclass of StorefrontDress: the two shapes differ (cover vs. the
    full gallery, description present vs. absent), and a shared base would make
    one file's edit silently change the other surface."""

    id: UUID
    name: str
    description: str | None
    price_agorot: int | None
    reserved: bool
    sizes: list[SizeChip]
    media: list[StorefrontMedia]
    # F28 D6. Current and future only, ascending, INCLUSIVE at both ends. Absent
    # from StorefrontDress by design — the card never becomes date-aware.
    unavailable_ranges: list[UnavailableRange]


class DressListResponse(BaseModel):
    # `items` is the house envelope key for paginated collections. `total` is
    # what the load-more button counts against.
    items: list[StorefrontDress]
    total: int
    offset: int
    limit: int


class HoursRow(BaseModel):
    """ONE ROW PER WINDOW, not per day: F7 allows a boutique a lunch break, and
    the repository orders by (day_of_week, open_time). The wire stays a straight
    projection and the client groups — a naive one-row-per-day map would keep
    only the last window and render half the boutique's hours."""

    day_of_week: int
    open_time: datetime.time
    close_time: datetime.time


class ExceptionRow(BaseModel):
    """Both times null = closed all day; both set = special hours."""

    date: datetime.date
    open_time: datetime.time | None
    close_time: datetime.time | None
    note: str | None


class BoutiqueResponse(BaseModel):
    """FLAT, not a nested `profile` object: every field here is public identity
    that the design renders in one header block, and the flat shape is what the
    spec binds.

    The profile fields are read out of the settings JSONB by EXPLICIT KEY, so a
    key a later feature adds to `profile` cannot reach the public page by
    default. `toggles` is not read at all — browse-only F10 renders no
    appointment type, and `brides_only`'s storefront semantics land with E3 #14.
    """

    # `name` is tenants.name — the display name, not the slug.
    name: str
    essence: str | None
    description: str | None
    phone: str | None
    address: str | None
    maps_url: str | None
    instagram: str | None
    hours: list[HoursRow]
    exceptions: list[ExceptionRow]
    # F20 D13 — the two documents and the platform sub-processor list, on the
    # fetch `StorefrontLayout` already makes on every route.
    #
    # There is deliberately NO `/storefront/privacy`. `PrivacyPage` copies
    # `AccessibilityPage`'s refusal to render a spinner or an error in place of
    # a legally-required document — and that argument only transfers if the page
    # has no network dependency of its own. A page-level fetch would put a 500,
    # a dropped connection or a 429 off the shared per-tenant read budget
    # between a bride and her §11 notice. Folded into this response, the failure
    # mode is identical to the layout's: the whole page fails, never the
    # document alone.
    #
    # The notice is on the hot path regardless — it must render INSIDE the
    # booking form's `details` step, at the moment she types her name — so a
    # second endpoint would buy a second failure mode and no saved bytes.
    privacy_notice_text: str
    privacy_dpa_text: str
    privacy_subprocessors_text: str


class SlotRow(BaseModel):
    """A bookable start time, and NOTHING else.

    An earlier draft also shipped `remaining`. It looked like the safe half of
    `capacity` — but the engine drops full slots, so with no bookings yet
    `remaining` equals `capacity` exactly, for every slot, on every response.
    That republishes verbatim the one field F10's allowlist fences off this
    surface ("discloses how many parallel fittings the boutique runs"), just
    under a different key, and the wire-absence walk cannot see it because the
    key it forbids is spelled differently.

    The picker does not need it either: every slot the engine returns is by
    construction bookable, so the time IS the whole message. A scarcity cue
    ("last spot") is a real product idea, and the feature that adds it should
    add a deliberately COARSE signal on top of a real booking count — not a
    number that happens to equal capacity today.
    """

    starts_at: datetime.datetime


class SlotListResponse(BaseModel):
    slots: list[SlotRow]


class StorefrontTerms(BaseModel):
    """The current cancellation policy — what a customer must be shown before
    accepting. NOT a subclass of the manage-side TermsVersionResponse: `id`,
    `tenant_id`, `created_by` and the timestamps are operator provenance, not
    booking-page content. `version` ships because the booking POST sends back
    the version the customer accepted."""

    version: int
    terms_text: str
    refundable_until_hours_before: int
    forfeit_percent: int


class AppointmentTypeRow(BaseModel):
    """What a customer can book, and what it costs to hold.

    `audience` is DISCLOSED, not enforced: an anonymous visitor cannot be
    classified as a bride, so the field exists for the UI to label the option
    and real enforcement waits for a client identity (E5). `deposit_*` ships
    because a customer is entitled to see a deposit before choosing a time, not
    after — E4's payment step reads the same fields.

    F27 D5 adds a master switch ABOVE the per-type value: with the tenant's
    `brides_only` toggle on, every row discloses as brides-only regardless of
    its own `audience`. Still disclosure, still not enforcement — the toggle
    changes what the page SAYS, never who the endpoint serves.

    **F19 narrowed WHEN the pair carries a deposit, and that is a change to a
    live public contract.** The keys always ship, but they now carry
    `false`/`null` unless the deposit is actually collectable: the boutique's
    `deposits_enabled` toggle is on AND a gateway is connected AND valid (D10's
    `is_connected`, D19's `deposit_due`). A boutique that configured a deposit
    and has no working gateway therefore looks, on this surface, exactly like a
    boutique that never configured one — F17's Q1 ruling, "hide the deposit
    entirely and book as if deposits were off". `StorefrontService` clears the
    pair; the router's projection is unchanged.
    """

    id: UUID
    name: str
    duration_minutes: int
    audience: str
    deposit_required: bool
    deposit_amount_agorot: int | None
