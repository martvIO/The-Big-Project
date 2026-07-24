"""Feature 8 catalog bounds, size normalisation, the magic-prefix table and the
key builder — pure units, no database, no network.

The bound-vs-CHECK guards at the bottom are the 10x rule made mechanical rather
than remembered: migration 0006's absurdity ceilings and this module's product
caps are asserted against each other here, so tightening one without the other
fails the fast loop instead of an IntegrityError in production.
"""

import re
import uuid

import pytest

from app.catalog.keys import build_media_filename, build_media_key
from app.catalog.validation import (
    ACCEPTED_CONTENT_TYPES,
    DB_MAX_BYTE_SIZE,
    DB_MAX_PRICE_AGOROT,
    DB_MAX_QUANTITY,
    DRESS_LIST_DEFAULT_LIMIT,
    DRESS_LIST_MAX_LIMIT,
    MAGIC_PREFIX_LENGTH,
    MAGIC_PREFIXES,
    MAX_DRESS_DESCRIPTION_LENGTH,
    MAX_DRESS_NAME_LENGTH,
    MAX_MEDIA_PER_DRESS,
    MAX_PRICE_AGOROT,
    MAX_SEARCH_LENGTH,
    MAX_SIZE_LABEL_LENGTH,
    MAX_SORT_ORDER,
    MAX_UPLOAD_BYTES,
    MAX_VARIANT_QUANTITY,
    MAX_VARIANTS_PER_DRESS,
    MIN_UPLOAD_BYTES,
    PENDING_MEDIA_TTL_SECONDS,
    PRESIGN_TTL_SECONDS,
    SIGNED_GET_TTL_SECONDS,
    CatalogValidationError,
    VariantInput,
    matches_magic_prefix,
    normalize_size_label,
    validate_dress,
    validate_presign,
    validate_search,
    validate_variants,
)

JPEG = "image/jpeg"
PNG = "image/png"
WEBP = "image/webp"

JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x02\x00\x00\x01"
PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
WEBP_HEADER = b"RIFF\x24\x00\x00\x00WEBPVP8 "


def _variant(size_label: str = "38", quantity: int = 1, sort_order: int = 0) -> VariantInput:
    return VariantInput(size_label=size_label, quantity=quantity, sort_order=sort_order)


# --- the constants table, asserted by value ---


def test_every_bound_matches_the_spec_table() -> None:
    """Each of these is mirrored into frontend/apps/manage/src/validation.ts and
    guarded there by test_frontend_constant_parity.py; this is the server-side
    half of that pair."""
    assert MAX_DRESS_NAME_LENGTH == 200
    assert MAX_DRESS_DESCRIPTION_LENGTH == 4000
    assert MAX_PRICE_AGOROT == 100_000_000
    assert MAX_VARIANTS_PER_DRESS == 60
    assert MAX_SIZE_LABEL_LENGTH == 32
    assert MAX_VARIANT_QUANTITY == 1000
    assert MAX_MEDIA_PER_DRESS == 12
    assert MAX_UPLOAD_BYTES == 10_485_760
    assert MIN_UPLOAD_BYTES == 1024
    assert MAX_SEARCH_LENGTH == 100
    assert MAX_SORT_ORDER == 1_000_000


def test_ttls_and_paging_defaults_match_the_spec_table() -> None:
    assert PRESIGN_TTL_SECONDS == 300
    assert SIGNED_GET_TTL_SECONDS == 900
    assert PENDING_MEDIA_TTL_SECONDS == 3600
    assert DRESS_LIST_DEFAULT_LIMIT == 24
    assert DRESS_LIST_MAX_LIMIT == 100


def test_bounds_stay_inside_their_db_check_ceilings() -> None:
    """The 10x rule, mechanically: a product cap raised past its CHECK would turn
    a clean 400 into an IntegrityError 500 on the write path."""
    assert MAX_PRICE_AGOROT * 10 == DB_MAX_PRICE_AGOROT
    assert MAX_VARIANT_QUANTITY * 10 == DB_MAX_QUANTITY
    # byte_size is the one deliberate 2x exception: it is also a security bound
    # the presigned POST policy enforces.
    assert MAX_UPLOAD_BYTES < DB_MAX_BYTE_SIZE
    assert DB_MAX_BYTE_SIZE == 20_971_520
    assert MIN_UPLOAD_BYTES > 0


# --- size-label normalisation ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param(" 38 ", "38", id="surrounding_whitespace"),
        pytest.param("US  6", "US 6", id="collapsed_internal_whitespace"),
        pytest.param("US\t6", "US 6", id="tab_becomes_a_single_space"),
        pytest.param("מידה מיוחדת", "מידה מיוחדת", id="hebrew_is_untouched"),
        pytest.param("38", "38", id="already_normal"),
    ],
)
def test_normalize_size_label(raw: str, expected: str) -> None:
    assert normalize_size_label(raw) == expected


def test_case_variants_survive_normalisation_and_collide_under_lower() -> None:
    """Normalisation deliberately does NOT lowercase — the owner's "US 6" is
    stored as typed. lower() in the partial unique index is what stops "US 6"
    and "us 6" becoming two stock buckets for one physical size."""
    assert normalize_size_label("US 6") == "US 6"
    assert normalize_size_label("us 6") == "us 6"
    assert normalize_size_label("US 6").lower() == normalize_size_label(" us  6 ").lower()


# --- content types and their extensions ---


def test_accepted_content_types_are_exactly_the_three_browser_safe_formats() -> None:
    """HEIC is excluded (no browser renders it), GIF and SVG too — SVG is
    executable markup, and an SVG served from our bucket is stored XSS. The
    extension map is server-side and authoritative: the key extension is derived
    from the declared type, never from the client filename."""
    assert ACCEPTED_CONTENT_TYPES == {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }


# --- magic prefixes ---


def test_magic_prefix_table_pins_the_documented_signatures() -> None:
    assert MAGIC_PREFIXES[JPEG] == ((0, b"\xff\xd8\xff"),)
    assert MAGIC_PREFIXES[PNG] == ((0, b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"),)
    # webp is two segments, not one prefix: RIFF at 0 AND WEBP at offset 8.
    assert MAGIC_PREFIXES[WEBP] == ((0, b"RIFF"), (8, b"WEBP"))
    assert set(MAGIC_PREFIXES) == set(ACCEPTED_CONTENT_TYPES)
    assert MAGIC_PREFIX_LENGTH == 16


def test_png_signature_is_the_full_eight_bytes() -> None:
    assert MAGIC_PREFIXES[PNG][0][1] == bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


@pytest.mark.parametrize(
    ("content_type", "prefix"),
    [
        pytest.param(JPEG, JPEG_HEADER, id="jpeg"),
        pytest.param(PNG, PNG_HEADER, id="png"),
        pytest.param(WEBP, WEBP_HEADER, id="webp"),
    ],
)
def test_matches_magic_prefix_accepts_a_real_header(content_type: str, prefix: bytes) -> None:
    assert matches_magic_prefix(content_type, prefix) is True


def test_riff_shaped_payload_that_is_not_webp_is_rejected() -> None:
    """A single-prefix table passes jpeg and png and then silently accepts
    anything RIFF-shaped — a .wav, an .avi, a polyglot. Both segments matter."""
    wav = b"RIFF\x24\x00\x00\x00WAVEfmt "
    assert matches_magic_prefix(WEBP, wav) is False


def test_html_payload_declared_as_an_image_is_rejected() -> None:
    html = b"<!DOCTYPE html><script>"
    for content_type in ACCEPTED_CONTENT_TYPES:
        assert matches_magic_prefix(content_type, html) is False


def test_cross_format_headers_are_rejected() -> None:
    assert matches_magic_prefix(JPEG, PNG_HEADER) is False
    assert matches_magic_prefix(PNG, JPEG_HEADER) is False
    assert matches_magic_prefix(WEBP, JPEG_HEADER) is False


def test_unknown_content_type_never_matches() -> None:
    assert matches_magic_prefix("image/svg+xml", b"<svg xmlns=") is False


def test_truncated_read_does_not_match() -> None:
    assert matches_magic_prefix(WEBP, b"RIFF") is False


# --- key builder ---


def test_build_media_key_matches_the_documented_shape() -> None:
    tenant_id = uuid.uuid4()
    dress_id = uuid.uuid4()
    media_id = uuid.uuid4()
    pattern = rf"^tenants/{tenant_id}/dresses/{dress_id}/media/[0-9a-f-]{{36}}\.(jpg|png|webp)$"
    for content_type, extension in ACCEPTED_CONTENT_TYPES.items():
        key = build_media_key(
            tenant_id=tenant_id,
            dress_id=dress_id,
            media_id=media_id,
            content_type=content_type,
        )
        assert re.fullmatch(pattern, key) is not None, key
        assert key.endswith(f"{media_id}{extension}")


def test_build_media_key_puts_the_tenant_prefix_first() -> None:
    """Tenant-first leaves room for a future IAM s3:prefix condition per tenant,
    and is what the isolation suite re-asserts end to end."""
    tenant_id = uuid.uuid4()
    key = build_media_key(
        tenant_id=tenant_id, dress_id=uuid.uuid4(), media_id=uuid.uuid4(), content_type=JPEG
    )
    assert key.startswith(f"tenants/{tenant_id}/")


def test_build_media_key_refuses_an_unaccepted_content_type() -> None:
    with pytest.raises(CatalogValidationError):
        build_media_key(
            tenant_id=uuid.uuid4(),
            dress_id=uuid.uuid4(),
            media_id=uuid.uuid4(),
            content_type="image/svg+xml",
        )


def test_build_media_filename_is_the_media_id_plus_the_declared_extension() -> None:
    """The original filename is not stored at all in v1 — the download name comes
    from the row's own id, so a crafted client filename cannot reach a header."""
    media_id = uuid.uuid4()
    assert build_media_filename(media_id=media_id, content_type=PNG) == f"{media_id}.png"


# --- dress fields ---


def test_valid_dress_passes() -> None:
    validate_dress(
        name="Aurora",
        description="Ivory silk, cathedral train.",
        price_agorot=1_200_00,
        sort_order=3,
    )


def test_dress_without_a_price_or_description_passes() -> None:
    # NULL price = "no price recorded"; the storefront renders "מחיר בתיאום".
    validate_dress(name="Aurora", description=None, price_agorot=None, sort_order=0)


def test_blank_dress_name_rejected() -> None:
    with pytest.raises(CatalogValidationError):
        validate_dress(name="   ", description=None, price_agorot=None, sort_order=0)


def test_dress_name_length_cap() -> None:
    validate_dress(
        name="a" * MAX_DRESS_NAME_LENGTH, description=None, price_agorot=None, sort_order=0
    )
    with pytest.raises(CatalogValidationError):
        validate_dress(
            name="a" * (MAX_DRESS_NAME_LENGTH + 1),
            description=None,
            price_agorot=None,
            sort_order=0,
        )


def test_dress_description_length_cap() -> None:
    validate_dress(
        name="Aurora",
        description="a" * MAX_DRESS_DESCRIPTION_LENGTH,
        price_agorot=None,
        sort_order=0,
    )
    with pytest.raises(CatalogValidationError):
        validate_dress(
            name="Aurora",
            description="a" * (MAX_DRESS_DESCRIPTION_LENGTH + 1),
            price_agorot=None,
            sort_order=0,
        )


def test_price_agorot_bounds() -> None:
    validate_dress(name="Aurora", description=None, price_agorot=1, sort_order=0)
    validate_dress(name="Aurora", description=None, price_agorot=MAX_PRICE_AGOROT, sort_order=0)
    for price in (0, -1, MAX_PRICE_AGOROT + 1):
        with pytest.raises(CatalogValidationError):
            validate_dress(name="Aurora", description=None, price_agorot=price, sort_order=0)


def test_dress_sort_order_bounds() -> None:
    validate_dress(name="Aurora", description=None, price_agorot=None, sort_order=MAX_SORT_ORDER)
    for sort_order in (MAX_SORT_ORDER + 1, -MAX_SORT_ORDER - 1):
        with pytest.raises(CatalogValidationError):
            validate_dress(
                name="Aurora", description=None, price_agorot=None, sort_order=sort_order
            )


# --- variants ---


def test_valid_variant_matrix_passes() -> None:
    validate_variants([_variant("38", 2, 0), _variant("40", 0, 1), _variant("US 6", 1, 2)])


def test_empty_variant_matrix_is_valid() -> None:
    # Zero variants is what a freshly created dress looks like — out_of_stock,
    # but the manage UI shows "לא הוגדרו מידות".
    validate_variants([])


def test_variant_count_cap() -> None:
    validate_variants([_variant(str(index)) for index in range(MAX_VARIANTS_PER_DRESS)])
    with pytest.raises(CatalogValidationError):
        validate_variants([_variant(str(index)) for index in range(MAX_VARIANTS_PER_DRESS + 1)])


def test_blank_size_label_rejected() -> None:
    with pytest.raises(CatalogValidationError):
        validate_variants([_variant("")])


def test_size_label_length_cap() -> None:
    validate_variants([_variant("a" * MAX_SIZE_LABEL_LENGTH)])
    with pytest.raises(CatalogValidationError):
        validate_variants([_variant("a" * (MAX_SIZE_LABEL_LENGTH + 1))])


def test_variant_quantity_bounds() -> None:
    validate_variants([_variant("38", 0)])
    validate_variants([_variant("38", MAX_VARIANT_QUANTITY)])
    for quantity in (-1, MAX_VARIANT_QUANTITY + 1):
        with pytest.raises(CatalogValidationError):
            validate_variants([_variant("38", quantity)])


def test_variant_sort_order_bounds() -> None:
    with pytest.raises(CatalogValidationError):
        validate_variants([_variant("38", 1, MAX_SORT_ORDER + 1)])


# --- presign request bounds ---


def test_valid_presign_request_passes() -> None:
    for content_type in ACCEPTED_CONTENT_TYPES:
        validate_presign(content_type=content_type, byte_size=MIN_UPLOAD_BYTES)
        validate_presign(content_type=content_type, byte_size=MAX_UPLOAD_BYTES)


def test_unaccepted_content_type_rejected() -> None:
    for content_type in ("image/svg+xml", "image/gif", "image/heic", "text/html", ""):
        with pytest.raises(CatalogValidationError):
            validate_presign(content_type=content_type, byte_size=4096)


def test_byte_size_bounds() -> None:
    for byte_size in (0, -1, MIN_UPLOAD_BYTES - 1, MAX_UPLOAD_BYTES + 1, DB_MAX_BYTE_SIZE):
        with pytest.raises(CatalogValidationError):
            validate_presign(content_type=JPEG, byte_size=byte_size)


# --- search ---


def test_search_length_cap() -> None:
    validate_search(None)
    validate_search("a" * MAX_SEARCH_LENGTH)
    with pytest.raises(CatalogValidationError):
        validate_search("a" * (MAX_SEARCH_LENGTH + 1))
