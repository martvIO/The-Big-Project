"""Pure domain validation and product policy for the catalog — no I/O, unit
tested locally.

Every bound here lives **once**. `Settings` carries deployment identity (bucket,
region, endpoint) and never product policy: an operator raising a byte limit in
env while `validation.ts` and the DB CHECK stayed put would turn a clean 400 into
an IntegrityError 500 on confirm. Every constant `validation.ts` restates is
re-asserted against it by test_frontend_constant_parity.

Each numeric bound names its DB counterpart below it. Migration 0006's CHECKs are
absurdity ceilings at exactly 10x these caps — INT4 headroom, so tightening
product policy never needs a migration — with one deliberate exception:
`byte_size` is 2x, because that value is also a security bound the presigned POST
policy enforces.
"""

import dataclasses
from collections.abc import Sequence

from app.errors import DomainValidationError


class CatalogValidationError(DomainValidationError):
    """Domain-rule violation on a catalog write; the router maps it to the
    house-shape 400."""


MAX_DRESS_NAME_LENGTH = 200
MAX_DRESS_DESCRIPTION_LENGTH = 4000
# 1,000,000 ILS in agorot — the same sanity cap as MAX_DEPOSIT_AMOUNT_AGOROT.
# Money is integer agorot everywhere, never float.
MAX_PRICE_AGOROT = 100_000_000
# EU 32-58 even = 14 rows; x4 headroom for custom labels.
MAX_VARIANTS_PER_DRESS = 60
MAX_SIZE_LABEL_LENGTH = 32
# A boutique holds units, not pallets.
MAX_VARIANT_QUANTITY = 1000
# 12 covers front/back/detail/train/veil with room to spare. Each is an
# unprocessed original, so this is also the per-dress egress worst case.
MAX_MEDIA_PER_DRESS = 12
# A modern phone JPEG is 3-6 MB and a DSLR export 8-12 MB: 10 MiB accepts real
# boutique photography and refuses RAW-ish exports.
MAX_UPLOAD_BYTES = 10_485_760
# Lower bound on the DECLARED size; kills empty and probe uploads.
MIN_UPLOAD_BYTES = 1024
MAX_SEARCH_LENGTH = 100
# Reused from app/boutique/validation.py.
MAX_SORT_ORDER = 1_000_000

# The absurdity ceilings written into migration 0006. Declared next to the caps
# they guard so test_catalog_validation can assert the pair mechanically rather
# than a reviewer remembering the rule.
DB_MAX_PRICE_AGOROT = 1_000_000_000
DB_MAX_QUANTITY = 10_000
DB_MAX_BYTE_SIZE = 20_971_520

# The extension map is server-side and authoritative: the key extension comes
# from the declared type, never from the client filename. HEIC is excluded (no
# browser renders it; Safari transcodes on pick), GIF and SVG too — SVG is
# executable markup, and an SVG served from our bucket is stored XSS. The DB
# pins this exact set because it is a security boundary, not duplication.
ACCEPTED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# Asserted at confirm against the object's first bytes. webp is two segments,
# not one prefix: a single-prefix table passes jpeg and png and then silently
# accepts anything RIFF-shaped — a .wav, an .avi, a polyglot.
MAGIC_PREFIXES: dict[str, tuple[tuple[int, bytes], ...]] = {
    "image/jpeg": ((0, b"\xff\xd8\xff"),),
    "image/png": ((0, b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"),),
    "image/webp": ((0, b"RIFF"), (8, b"WEBP")),
}
MAGIC_PREFIX_LENGTH = 16

# The browser posts immediately: 5 minutes covers a slow mobile uplink starting
# the request, not a stolen policy sitting in a log.
PRESIGN_TTL_SECONDS = 300
# One editing session of gallery viewing.
SIGNED_GET_TTL_SECONDS = 900
# A pending row older than an hour is an abandoned upload: it stops counting
# toward the cap and is swept on the next presign for that dress. Injectable on
# CatalogService so the sweep is testable without sleeping or backdating rows.
PENDING_MEDIA_TTL_SECONDS = 3600

# The manage list is the heaviest egress path in v1 — each row carries an
# unprocessed cover. Raise the default only once thumbnails exist.
DRESS_LIST_DEFAULT_LIMIT = 24
DRESS_LIST_MAX_LIMIT = 100


@dataclasses.dataclass(frozen=True)
class VariantInput:
    size_label: str
    quantity: int
    sort_order: int = 0


def normalize_size_label(label: str) -> str:
    """Strip and collapse internal whitespace. Deliberately NOT lowercased — the
    owner's "US 6" is stored as typed; lower() in the partial unique index is
    what stops "US 6" and "us 6" becoming two stock buckets for one size."""
    return " ".join(label.split())


def matches_magic_prefix(content_type: str, prefix: bytes) -> bool:
    """True only when every documented segment of the signature is present at its
    documented offset. An unknown content type never matches."""
    segments = MAGIC_PREFIXES.get(content_type)
    if segments is None:
        return False
    return all(prefix[offset : offset + len(magic)] == magic for offset, magic in segments)


def validate_dress(
    *, name: str, description: str | None, price_agorot: int | None, sort_order: int
) -> None:
    if not name.strip():
        raise CatalogValidationError("name must not be blank")
    if len(name) > MAX_DRESS_NAME_LENGTH:
        raise CatalogValidationError("name is too long")
    if description is not None and len(description) > MAX_DRESS_DESCRIPTION_LENGTH:
        raise CatalogValidationError("description is too long")
    # NULL price = "no price recorded"; the storefront renders "מחיר בתיאום".
    if price_agorot is not None and not 0 < price_agorot <= MAX_PRICE_AGOROT:
        raise CatalogValidationError("price_agorot is out of bounds")
    if abs(sort_order) > MAX_SORT_ORDER:
        raise CatalogValidationError("sort_order is out of bounds")


def validate_variants(variants: Sequence[VariantInput]) -> None:
    """Bounds only — the labels are expected to be normalised already, and
    duplicate detection belongs to the service (it maps to 409, not 400)."""
    if len(variants) > MAX_VARIANTS_PER_DRESS:
        raise CatalogValidationError(f"at most {MAX_VARIANTS_PER_DRESS} sizes are allowed")
    for variant in variants:
        if not variant.size_label.strip():
            raise CatalogValidationError("size_label must not be blank")
        if len(variant.size_label) > MAX_SIZE_LABEL_LENGTH:
            raise CatalogValidationError("size_label is too long")
        if not 0 <= variant.quantity <= MAX_VARIANT_QUANTITY:
            raise CatalogValidationError(f"quantity must be between 0 and {MAX_VARIANT_QUANTITY}")
        if abs(variant.sort_order) > MAX_SORT_ORDER:
            raise CatalogValidationError("sort_order is out of bounds")


def validate_presign(*, content_type: str, byte_size: int) -> None:
    if content_type not in ACCEPTED_CONTENT_TYPES:
        raise CatalogValidationError(
            "content_type must be one of: " + ", ".join(sorted(ACCEPTED_CONTENT_TYPES))
        )
    if not MIN_UPLOAD_BYTES <= byte_size <= MAX_UPLOAD_BYTES:
        raise CatalogValidationError(
            f"byte_size must be between {MIN_UPLOAD_BYTES} and {MAX_UPLOAD_BYTES}"
        )


def validate_search(search: str | None) -> None:
    if search is not None and len(search) > MAX_SEARCH_LENGTH:
        raise CatalogValidationError("search is too long")
