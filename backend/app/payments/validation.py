"""Credential-shape validation and every named constant this feature owns.

Deliberately NOT env-tunable — the F8/F10 rule quoted at the top of
app/notifications/validation.py: `Settings` carries deployment identity, never
product policy. The rate-limit windows are the only exception and they live in
`Settings` with the login/presign ones.
"""

import json
from collections.abc import Iterable, Mapping

from app.errors import DomainValidationError

# A provider key or secret. Anything longer is a paste error, and the cap is
# what keeps a hostile blob out of the KMS call.
MAX_CREDENTIAL_FIELD_VALUE_LENGTH = 512
# AWS KMS `Encrypt` accepts at most 4096 PLAINTEXT bytes. This cap exists so the
# fake box and the future KmsSecretBox cannot disagree about what fits —
# otherwise a credential set that saves in staging fails in production.
MAX_CREDENTIAL_BLOB_BYTES = 3000
# The AAD label bound into every encryption context. A second purpose gets its
# own constant; this one is never widened.
ENCRYPTION_CONTEXT_PURPOSE = "gateway_credentials"
# MAX_PROVIDER_ERROR_LENGTH from notifications/service.py, same reason: provider
# exception text is unbounded and the column it lands in lives forever.
MAX_VALIDATION_ERROR_LENGTH = 200
# The fake gateway's deterministic rejection path — one sentinel, one branch, so
# staging can demonstrate the invalid state on demand.
FAKE_INVALID_MERCHANT_ID = "invalid"
# Where the fake's redirect points. F19 decides what serves it.
FAKE_PAY_PATH = "/fake-pay"
# What replaces a credential value that a provider exception echoed back.
SECRET_MASK = "[redacted]"


def validate_credential_fields(
    fields: Mapping[str, str], *, expected: frozenset[str]
) -> dict[str, str]:
    """The key set must EQUAL the adapter's declared `credential_fields`.

    Not a superset check and not a subset check: a partial update would require
    reading back what it is not replacing, and the API has no read path for a
    field value by construction (that is the whole write-only design). So a
    missing key is as much a client error as an unknown one.
    """
    supplied = set(fields)
    unknown = supplied - expected
    if unknown:
        raise DomainValidationError(f"unknown credential fields: {', '.join(sorted(unknown))}")
    missing = expected - supplied
    if missing:
        raise DomainValidationError(f"missing credential fields: {', '.join(sorted(missing))}")

    cleaned: dict[str, str] = {}
    for name in sorted(expected):
        value = fields[name].strip()
        if not value:
            raise DomainValidationError(f"{name} is required")
        if len(value) > MAX_CREDENTIAL_FIELD_VALUE_LENGTH:
            raise DomainValidationError(f"{name} is too long")
        cleaned[name] = value

    # Measured on the exact bytes the SecretBox will be handed, never on the
    # request body: the ceiling being defended is KMS's plaintext limit.
    if len(serialize_credentials(cleaned)) > MAX_CREDENTIAL_BLOB_BYTES:
        raise DomainValidationError("credentials are too large")
    return cleaned


def serialize_credentials(fields: Mapping[str, str]) -> bytes:
    """The exact plaintext the SecretBox encrypts. Sorted keys and no whitespace
    so the same credential set always produces the same bytes — which is what
    lets MAX_CREDENTIAL_BLOB_BYTES measure what actually reaches KMS."""
    return json.dumps(dict(fields), sort_keys=True, separators=(",", ":")).encode()


def deserialize_credentials(plaintext: bytes) -> dict[str, str]:
    """A blob that decrypts but is not a flat str->str map is a corrupt
    credential set, not a usable one — raise rather than hand the adapter an int
    it would stringify into a wrong API key."""
    decoded = json.loads(plaintext)
    if not isinstance(decoded, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in decoded.items()
    ):
        raise ValueError("credential blob is not a flat string map")
    return {str(key): str(value) for key, value in decoded.items()}


def scrub_provider_error(exc: Exception, *, secrets: Iterable[str] = ()) -> str:
    """What `tenant_gateway_credentials.validation_error` and `payments.error`
    store — NotificationService._scrub's shape, both halves.

    Masking runs BEFORE truncation, never after: several provider SDKs echo the
    failing request in their exception, and truncating first would leave a
    secret's prefix behind in a column that lives forever right beside the
    ciphertext that exists to hide it.
    """
    detail = f"{type(exc).__name__}: {exc}"
    for secret in secrets:
        if secret:
            detail = detail.replace(secret, SECRET_MASK)
    return detail[:MAX_VALIDATION_ERROR_LENGTH]
