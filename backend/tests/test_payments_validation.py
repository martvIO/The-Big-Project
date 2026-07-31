"""F17 fast tests: the credential-shape table and the named constants, each
asserted against its documented reason (test_notifications_validation.py shape).
No database, no provider, no AWS."""

import json

import pytest

from app.errors import DomainValidationError
from app.payments.validation import (
    ENCRYPTION_CONTEXT_PURPOSE,
    MAX_CREDENTIAL_BLOB_BYTES,
    MAX_CREDENTIAL_FIELD_VALUE_LENGTH,
    MAX_VALIDATION_ERROR_LENGTH,
    SECRET_MASK,
    deserialize_credentials,
    scrub_provider_error,
    serialize_credentials,
    validate_credential_fields,
)

EXPECTED = frozenset({"api_key", "merchant_id", "webhook_secret"})
GOOD = {"merchant_id": "m-1", "api_key": "k-1", "webhook_secret": "s-1"}


def test_exact_key_set_is_accepted_and_returned() -> None:
    assert validate_credential_fields(GOOD, expected=EXPECTED) == GOOD


def test_an_unknown_key_is_refused_by_name() -> None:
    with pytest.raises(DomainValidationError) as exc:
        validate_credential_fields({**GOOD, "extra": "x"}, expected=EXPECTED)
    assert str(exc.value) == "unknown credential fields: extra"


def test_a_missing_key_is_refused_by_name() -> None:
    partial = {key: value for key, value in GOOD.items() if key != "webhook_secret"}
    with pytest.raises(DomainValidationError) as exc:
        validate_credential_fields(partial, expected=EXPECTED)
    assert str(exc.value) == "missing credential fields: webhook_secret"


def test_unknown_is_reported_before_missing_and_both_are_sorted() -> None:
    # Deterministic message ordering: a set's iteration order would make this
    # assertion — and the owner-facing 400 — nondeterministic.
    with pytest.raises(DomainValidationError) as exc:
        validate_credential_fields({"zeta": "1", "alpha": "2"}, expected=EXPECTED)
    assert str(exc.value) == "unknown credential fields: alpha, zeta"


def test_a_blank_value_is_refused() -> None:
    with pytest.raises(DomainValidationError) as exc:
        validate_credential_fields({**GOOD, "api_key": "   "}, expected=EXPECTED)
    assert str(exc.value) == "api_key is required"


def test_an_over_length_value_is_refused() -> None:
    over = "x" * (MAX_CREDENTIAL_FIELD_VALUE_LENGTH + 1)
    with pytest.raises(DomainValidationError) as exc:
        validate_credential_fields({**GOOD, "api_key": over}, expected=EXPECTED)
    assert str(exc.value) == "api_key is too long"


def test_a_value_exactly_at_the_length_cap_is_accepted() -> None:
    at_cap = "x" * MAX_CREDENTIAL_FIELD_VALUE_LENGTH
    assert (
        validate_credential_fields({**GOOD, "api_key": at_cap}, expected=EXPECTED)["api_key"]
        == at_cap
    )


def test_an_over_size_blob_is_refused_because_kms_encrypt_caps_plaintext_at_4096() -> None:
    """MAX_CREDENTIAL_BLOB_BYTES exists because AWS KMS `Encrypt` accepts at most
    4096 plaintext bytes. The cap keeps the fake box and the future KmsSecretBox
    from disagreeing about what fits — otherwise a credential set that saves in
    staging fails in production. Raising it has to argue with this test."""
    assert MAX_CREDENTIAL_BLOB_BYTES < 4096
    # Three fields each under the per-value cap, summing past the blob cap.
    fat = {key: "x" * MAX_CREDENTIAL_FIELD_VALUE_LENGTH for key in EXPECTED}
    assert len(serialize_credentials(fat)) < MAX_CREDENTIAL_BLOB_BYTES
    wide = frozenset(f"field_{index}" for index in range(20))
    too_much = {key: "x" * MAX_CREDENTIAL_FIELD_VALUE_LENGTH for key in wide}
    with pytest.raises(DomainValidationError) as exc:
        validate_credential_fields(too_much, expected=wide)
    assert str(exc.value) == "credentials are too large"


def test_values_are_stripped_before_storage() -> None:
    assert (
        validate_credential_fields({**GOOD, "api_key": " k-1 "}, expected=EXPECTED)["api_key"]
        == "k-1"
    )


def test_serialize_round_trips_and_is_stable_under_key_order() -> None:
    blob = serialize_credentials(GOOD)
    assert deserialize_credentials(blob) == GOOD
    assert blob == serialize_credentials(dict(reversed(list(GOOD.items()))))


def test_deserialize_refuses_a_non_string_payload() -> None:
    # A blob that decrypts but does not carry a flat str->str map is a corrupt
    # credential set, not a usable one — fail loudly rather than hand the adapter
    # an int it will stringify into a wrong API key.
    with pytest.raises(ValueError):
        deserialize_credentials(json.dumps({"api_key": 7}).encode())


def test_provider_error_is_truncated_to_the_message_log_ceiling() -> None:
    """MAX_VALIDATION_ERROR_LENGTH is MAX_PROVIDER_ERROR_LENGTH from
    notifications/service.py, for the same reason: provider exception text is
    unbounded and this column lives forever."""
    assert MAX_VALIDATION_ERROR_LENGTH == 200
    detail = scrub_provider_error(ValueError("y" * 500))
    assert len(detail) == MAX_VALIDATION_ERROR_LENGTH
    assert detail.startswith("ValueError: ")


def test_an_echoed_credential_value_is_masked_before_truncation() -> None:
    """An SDK that echoes the failing request must not persist the merchant
    secret in a forever-column. Masking after truncation would leave the
    secret's prefix behind, which is why the order is load-bearing."""
    secret = "sk-live-supersecret"
    detail = scrub_provider_error(ValueError(f"rejected key {secret} at edge"), secrets=[secret])
    assert secret not in detail
    assert SECRET_MASK in detail

    long_secret = "z" * 300
    padded = scrub_provider_error(ValueError(f"{'a' * 150}{long_secret}"), secrets=[long_secret])
    assert "z" not in padded


def test_encryption_context_purpose_is_a_single_label() -> None:
    # The AAD label. A second purpose gets its own constant; this one is never
    # widened, because widening it makes two ciphertext classes interchangeable.
    assert ENCRYPTION_CONTEXT_PURPOSE == "gateway_credentials"


def test_no_rejection_message_ever_names_a_value() -> None:
    """The source-level half of the API containment sweep.

    Every DomainValidationError this module raises reaches the owner verbatim
    through the house 400 handler (it echoes str(exc) by design), so a message
    that interpolated a VALUE instead of a field NAME would put a merchant
    secret in an HTTP response body. Every rejection path is driven here with
    the values set to sentinels.
    """
    sentinel = "SUPER-SECRET-MERCHANT-KEY-8f3a"
    over = sentinel + "x" * MAX_CREDENTIAL_FIELD_VALUE_LENGTH
    cases: list[dict[str, str]] = [
        {**GOOD, "extra": sentinel},  # unknown key
        {"merchant_id": sentinel, "api_key": sentinel},  # missing key
        {**GOOD, "api_key": "   "},  # blank value
        {**GOOD, "api_key": over},  # over-length value
        {key: over for key in EXPECTED},  # over-size blob
    ]
    seen = 0
    for case in cases:
        with pytest.raises(DomainValidationError) as exc:
            validate_credential_fields(case, expected=EXPECTED)
        assert sentinel not in str(exc.value), case
        seen += 1
    assert seen == len(cases), "a case stopped raising — the sweep went vacuous"
