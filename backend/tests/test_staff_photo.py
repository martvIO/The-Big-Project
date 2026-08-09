"""F38's staff photo module — pure key building, bounds and signing, no database
and no network, so this whole module runs in the fast local pass.

The load-bearing assertions here are the ones about what is IMPORTED rather than
re-declared: every value this feature shares with the catalog's media pipeline
(the accepted types, the magic table, the floor, the signed-GET TTL) comes from
`app/catalog/validation.py`, and a copy-paste that re-declared any of them would
drift silently the first time one side is tuned.
"""

import uuid

import pytest

from app.auth.photo import (
    MAX_STAFF_PHOTO_BYTES,
    build_staff_photo_key,
    sign_staff_photo,
    validate_staff_photo_presign,
)
from app.catalog.validation import (
    ACCEPTED_CONTENT_TYPES,
    MAX_UPLOAD_BYTES,
    MIN_UPLOAD_BYTES,
    SIGNED_GET_TTL_SECONDS,
)
from app.errors import DomainValidationError
from app.models.staff_user import StaffUser
from app.storage.base import (
    MediaNotConfiguredError,
    MediaStorageUnavailableError,
    ObjectHead,
    PresignedPost,
)

TENANT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
STAFF_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
PHOTO_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")


def _key(content_type: str = "image/jpeg") -> str:
    return build_staff_photo_key(
        tenant_id=TENANT_ID,
        staff_user_id=STAFF_ID,
        photo_id=PHOTO_ID,
        content_type=content_type,
    )


class FakeStorage:
    """A structurally complete `MediaStorage`, not just the two members
    `sign_staff_photo` touches.

    Complete deliberately: mypy checks the Protocol at the call site, so a
    partial fake would need a `cast` — and a cast is exactly what would let a
    later signature change on the real port sail past every test in this file.
    The unused members raise, so a test that reaches one by accident says so
    instead of silently returning None.

    `is_configured` and `signed_get_url` are plain, not async: signing is local
    HMAC with zero I/O, and awaiting it would be a lie costing an await per staff
    row on a board that polls every 5 s.
    """

    def __init__(self, *, configured: bool = True, raises: Exception | None = None) -> None:
        self._configured = configured
        self._raises = raises
        self.calls: list[dict[str, object]] = []

    @property
    def is_configured(self) -> bool:
        return self._configured

    def presigned_post(
        self, *, key: str, content_type: str, exact_bytes: int, expires_in: int
    ) -> PresignedPost:
        raise NotImplementedError

    def signed_get_url(self, *, key: str, content_type: str, filename: str, expires_in: int) -> str:
        self.calls.append(
            {
                "key": key,
                "content_type": content_type,
                "filename": filename,
                "expires_in": expires_in,
            }
        )
        if self._raises is not None:
            raise self._raises
        return f"https://bucket.example/{key}?signed"

    async def head_object(self, *, key: str) -> ObjectHead | None:
        raise NotImplementedError

    async def read_prefix(self, *, key: str, length: int) -> bytes:
        raise NotImplementedError

    async def delete_object(self, *, key: str) -> None:
        raise NotImplementedError


def _row(*, key: str | None = None, content_type: str | None = None) -> StaffUser:
    return StaffUser(
        id=STAFF_ID,
        tenant_id=TENANT_ID,
        email="dana@bella.example",
        password_hash="$argon2id$never-on-the-wire",
        display_name="דנה",
        role="owner",
        photo_key=key,
        photo_content_type=content_type,
    )


# --- the key ---------------------------------------------------------------


def test_the_key_is_tenant_prefixed_and_carries_nothing_a_client_sent() -> None:
    """`build_media_key`'s rule, restated for staff: the tenant comes from the
    host-derived request context, the staff id from a row this tenant owns, the
    photo id is minted server-side and the extension comes from the DECLARED
    content type — never from a filename. The tenant prefix leads so a future IAM
    `s3:prefix` condition per tenant stays possible."""
    assert _key() == (f"tenants/{TENANT_ID}/staff/{STAFF_ID}/photo/{PHOTO_ID}.jpg")
    assert _key().startswith(f"tenants/{TENANT_ID}/")


@pytest.mark.parametrize("content_type", sorted(ACCEPTED_CONTENT_TYPES))
def test_every_accepted_type_produces_its_own_extension(content_type: str) -> None:
    assert _key(content_type).endswith(ACCEPTED_CONTENT_TYPES[content_type])


def test_an_unknown_content_type_raises_rather_than_building_an_extensionless_key() -> None:
    """The failure mode this refuses is silent: a `.get()` returning None and an
    f-string rendering it as the empty string gives a key that looks plausible,
    uploads fine, and serves with no extension forever."""
    with pytest.raises(DomainValidationError):
        _key("image/gif")


# --- the bounds ------------------------------------------------------------


def test_the_staff_cap_is_below_the_catalog_cap() -> None:
    """The assertion a copy-paste fails. 2 MiB is a deliberate FIFTH of the
    catalog's 10 MiB: a 44 px avatar on a board that polls every ~5 s is not
    boutique photography, and this payload is re-rendered on every tick.

    Written as a comparison rather than as `== 2_097_152` so that raising the
    catalog's cap can never silently carry the staff cap up with it."""
    assert MAX_STAFF_PHOTO_BYTES < MAX_UPLOAD_BYTES


@pytest.mark.parametrize("byte_size", [MIN_UPLOAD_BYTES, MAX_STAFF_PHOTO_BYTES])
def test_both_bounds_are_inclusive(byte_size: int) -> None:
    validate_staff_photo_presign(content_type="image/jpeg", byte_size=byte_size)


@pytest.mark.parametrize("byte_size", [MIN_UPLOAD_BYTES - 1, MAX_STAFF_PHOTO_BYTES + 1, 0, -1])
def test_a_size_outside_the_bounds_is_refused(byte_size: int) -> None:
    """The floor is the IMPORTED `MIN_UPLOAD_BYTES` and kills empty and probe
    uploads; the ceiling is the staff cap and not the catalog's."""
    with pytest.raises(DomainValidationError):
        validate_staff_photo_presign(content_type="image/jpeg", byte_size=byte_size)


def test_an_unaccepted_content_type_is_refused_before_any_size_check() -> None:
    with pytest.raises(DomainValidationError):
        validate_staff_photo_presign(content_type="image/svg+xml", byte_size=MIN_UPLOAD_BYTES)


# --- signing, and its degrade-to-null posture ------------------------------


def test_a_confirmed_photo_signs_with_the_shared_ttl_and_a_derived_filename() -> None:
    """The Content-Disposition filename is the key's own basename — i.e. the
    server-minted `{photo_id}{ext}` — so no client-supplied string can ever reach
    that header, and no second column has to store it."""
    storage = FakeStorage()
    key = _key()
    url = sign_staff_photo(storage, _row(key=key, content_type="image/jpeg"))
    assert url == f"https://bucket.example/{key}?signed"
    assert storage.calls == [
        {
            "key": key,
            "content_type": "image/jpeg",
            "filename": f"{PHOTO_ID}.jpg",
            "expires_in": SIGNED_GET_TTL_SECONDS,
        }
    ]


def test_a_staffer_with_no_photo_signs_nothing_at_all() -> None:
    storage = FakeStorage()
    assert sign_staff_photo(storage, _row()) is None
    assert storage.calls == []


def test_an_unconfigured_bucket_degrades_to_none_without_calling_storage() -> None:
    storage = FakeStorage(configured=False)
    assert sign_staff_photo(storage, _row(key=_key(), content_type="image/jpeg")) is None
    assert storage.calls == []


@pytest.mark.parametrize("error", [MediaNotConfiguredError(), MediaStorageUnavailableError()])
def test_a_signing_failure_degrades_to_none_rather_than_failing_the_read(
    error: Exception,
) -> None:
    """`sign_media`'s posture verbatim, and it is a security-relevant invariant
    rather than politeness: a bucket whose credentials rotated is still
    `is_configured`, so branching on that alone would let a signing failure
    propagate out of a plain GET /manage/staff — or worse, out of the floor
    board's five-second poll — as a 503 and take the whole screen down with the
    avatars. Only the photo WRITE endpoints answer 503."""
    storage = FakeStorage(raises=error)
    assert sign_staff_photo(storage, _row(key=_key(), content_type="image/jpeg")) is None
