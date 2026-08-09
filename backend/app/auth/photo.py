"""Staff profile photos: the key builder, the bounds and the read-side signer.

Pure — no I/O, no session, no `app.state` — so it unit-tests locally and can be
imported by both `auth/staff_router.py` (the console list) and `floor/schemas.py`
(the board card) without either depending on the other.

**Everything shared with the catalog's media pipeline is IMPORTED, never
re-declared**: the accepted type→extension map, the magic-prefix table, the
lower size bound and the signed-GET TTL all live in `app/catalog/validation.py`
and are tuned there once. A second copy of `ACCEPTED_CONTENT_TYPES` in this file
would drift from the DB CHECK the day either side is widened — and that set is a
security boundary (0006's own words), not duplication.

Two values are deliberately this feature's OWN, and both are asserted against
their catalog twin in `test_staff_photo.py` so a copy-paste of the wrong one is
a red rather than a quiet regression:
  * `MAX_STAFF_PHOTO_BYTES`, a fifth of the catalog's cap;
  * the throttle instance, which lives in `main.py` beside the catalog's (a
    limiter's `max_attempts` is PER INSTANCE, so two keys on one limiter share a
    single ceiling — `.memory/limiter-max-is-per-instance`).
"""

import logging
import uuid

from app.catalog.validation import (
    ACCEPTED_CONTENT_TYPES,
    MIN_UPLOAD_BYTES,
    SIGNED_GET_TTL_SECONDS,
)
from app.errors import DomainValidationError
from app.models.staff_user import StaffUser
from app.storage.base import (
    MediaNotConfiguredError,
    MediaStorage,
    MediaStorageUnavailableError,
)

logger = logging.getLogger(__name__)

# A DELIBERATE FIFTH of the catalog's MAX_UPLOAD_BYTES. A 44 px avatar on a board
# that polls every ~5 s is not boutique photography, and unlike a dress gallery
# this payload is re-rendered on every tick by every screen in the shop.
MAX_STAFF_PHOTO_BYTES = 2_097_152


def _extension(content_type: str) -> str:
    extension = ACCEPTED_CONTENT_TYPES.get(content_type)
    if extension is None:
        # RAISES rather than returning "". A `.get()` whose None renders as the
        # empty string in an f-string produces a plausible-looking, extensionless
        # key that uploads fine and serves wrong forever.
        raise DomainValidationError(
            "content_type must be one of: " + ", ".join(sorted(ACCEPTED_CONTENT_TYPES))
        )
    return extension


def build_staff_photo_key(
    *,
    tenant_id: uuid.UUID,
    staff_user_id: uuid.UUID,
    photo_id: uuid.UUID,
    content_type: str,
) -> str:
    """`build_media_key`'s rule for staff: nothing a client sends reaches the key.

    `tenant_id` comes only from the host-derived request context, `staff_user_id`
    only from a row this tenant actually owns (the service resolves it under the
    lock *before* calling in here), `photo_id` is minted server-side, and the
    extension comes from the declared content type rather than any filename. The
    original filename is not stored at all.
    """
    return f"tenants/{tenant_id}/staff/{staff_user_id}/photo/{photo_id}{_extension(content_type)}"


def validate_staff_photo_presign(*, content_type: str, byte_size: int) -> None:
    if content_type not in ACCEPTED_CONTENT_TYPES:
        raise DomainValidationError(
            "content_type must be one of: " + ", ".join(sorted(ACCEPTED_CONTENT_TYPES))
        )
    if not MIN_UPLOAD_BYTES <= byte_size <= MAX_STAFF_PHOTO_BYTES:
        raise DomainValidationError(
            f"byte_size must be between {MIN_UPLOAD_BYTES} and {MAX_STAFF_PHOTO_BYTES}"
        )


def sign_staff_photo(storage: MediaStorage, row: StaffUser) -> str | None:
    """Mint a presigned GET for one staffer's live photo, degrading to `None`.

    Module-level and storage-injected so the console list AND the floor board
    sign through the SAME function. `sign_media`'s reasoning applies unchanged:
    the degradation rule is a security-relevant invariant, and an invariant that
    exists in two places is one that will eventually hold in only one of them.

    Plain `def`, not `async`: signing is local HMAC with zero I/O, so awaiting it
    would be a lie costing an await per staff row on a five-second poll.

    ⚠ The `except` is not defensive clutter. A bucket whose credentials rotated
    is still `is_configured`, so branching on that flag alone would let a signing
    failure propagate out of a plain `GET /manage/staff` — or out of the board's
    poll — as a 503 and take the whole screen down with the avatars. Only the
    photo WRITE endpoints answer 503. The storage port already logged the
    operation and the key.
    """
    if row.photo_key is None or row.photo_content_type is None or not storage.is_configured:
        return None
    try:
        return storage.signed_get_url(
            key=row.photo_key,
            content_type=row.photo_content_type,
            # The key's own basename IS `{photo_id}{ext}` — server-minted — so
            # the Content-Disposition filename needs no column of its own and no
            # client-supplied string can ever reach that header.
            filename=row.photo_key.rsplit("/", 1)[-1],
            expires_in=SIGNED_GET_TTL_SECONDS,
        )
    except (MediaNotConfiguredError, MediaStorageUnavailableError):
        logger.warning(
            "staff photo url signing failed, serialising a null url: tenant_id=%s staff_user_id=%s",
            row.tenant_id,
            row.id,
        )
        return None
