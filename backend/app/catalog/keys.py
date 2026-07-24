"""The S3 key builder.

`tenants/{tenant_id}/dresses/{dress_id}/media/{media_id}{ext}`. Tenant prefix
first satisfies the checklist's "S3 keys tenant-prefixed" and leaves room for a
future IAM `s3:prefix` condition per tenant.

Nothing a client sends influences a key: `tenant_id` comes only from the
host-derived request context, `dress_id` only from a dress row this tenant
actually owns — the service resolves the parent dress *before* calling in here —
`media_id` is minted server-side, and the extension comes from the declared
content type rather than the client's filename. The original filename is not
stored at all in v1.
"""

import uuid

from app.catalog.validation import ACCEPTED_CONTENT_TYPES, CatalogValidationError


def _extension(content_type: str) -> str:
    extension = ACCEPTED_CONTENT_TYPES.get(content_type)
    if extension is None:
        raise CatalogValidationError(
            "content_type must be one of: " + ", ".join(sorted(ACCEPTED_CONTENT_TYPES))
        )
    return extension


def build_media_key(
    *, tenant_id: uuid.UUID, dress_id: uuid.UUID, media_id: uuid.UUID, content_type: str
) -> str:
    return f"tenants/{tenant_id}/dresses/{dress_id}/media/{media_id}{_extension(content_type)}"


def build_media_filename(*, media_id: uuid.UUID, content_type: str) -> str:
    """The download name on a signed GET's Content-Disposition. Derived from the
    row's own id, so no client-supplied string can ever reach that header."""
    return f"{media_id}{_extension(content_type)}"
