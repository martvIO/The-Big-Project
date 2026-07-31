"""F17 fast tests for both ports (test_notifications_adapters.py shape).

No database, no AWS, no provider. The HMAC in FakeGateway is real, so the
signature and tamper assertions below exercise a genuine comparison rather than
a stub that returns True — which is what makes them worth anything to F19.
"""

from pathlib import Path

import pytest

from app.payments.base import (
    GatewayCredentials,
    GatewayCredentialsRejectedError,
    GatewayNotConfiguredError,
    GatewayWebhookInvalidError,
    PaymentGateway,
    PaymentSession,
    WebhookEvent,
)
from app.payments.fake import FakeGateway, fake_webhook_body, sign_fake_webhook
from app.payments.secretbox import (
    FakeSecretBox,
    SecretBox,
    SecretBoxNotConfiguredError,
    SecretDecryptError,
    UnconfiguredSecretBox,
)
from app.payments.unconfigured import UnconfiguredGateway
from app.payments.validation import (
    ENCRYPTION_CONTEXT_PURPOSE,
    FAKE_INVALID_MERCHANT_ID,
    FAKE_PAY_PATH,
)

SECRET = "webhook-secret-1"
GOOD = {"merchant_id": "m-1", "api_key": "k-1", "webhook_secret": SECRET}


def _credentials(**overrides: str) -> GatewayCredentials:
    return GatewayCredentials(provider="fake", fields={**GOOD, **overrides})


def _context(tenant: str) -> dict[str, str]:
    return {"tenant_id": tenant, "purpose": ENCRYPTION_CONTEXT_PURPOSE}


# --- FakeGateway ---


async def test_fake_validate_accepts_and_records() -> None:
    gateway = FakeGateway()
    credentials = _credentials()
    # Returns None and RAISES on refusal, rather than returning a bool the
    # caller could ignore — so "it did not raise" IS the acceptance assertion.
    await gateway.validate_credentials(credentials)
    assert gateway.validations == [credentials]


async def test_fake_validate_rejects_the_sentinel_merchant_id() -> None:
    gateway = FakeGateway()
    with pytest.raises(GatewayCredentialsRejectedError):
        await gateway.validate_credentials(_credentials(merchant_id=FAKE_INVALID_MERCHANT_ID))


async def test_fake_declares_its_own_credential_shape() -> None:
    # A plausible shape, explicitly NOT a claim about any real provider's. F18
    # changes it and the console form follows with no frontend edit.
    assert FakeGateway().credential_fields == frozenset(
        {"merchant_id", "api_key", "webhook_secret"}
    )
    assert FakeGateway().provider == "fake"
    assert FakeGateway().is_configured is True


async def test_fake_create_session_records_the_call_and_mints_stable_ids() -> None:
    gateway = FakeGateway()
    first = await gateway.create_session(
        _credentials(),
        amount_agorot=15000,
        reference="booking-1",
        return_url="https://bella.example/back",
        expires_in=900,
    )
    second = await gateway.create_session(
        _credentials(),
        amount_agorot=20000,
        reference="booking-2",
        return_url="https://bella.example/back",
        expires_in=900,
    )
    assert isinstance(first, PaymentSession)
    assert first.provider_session_id != second.provider_session_id
    assert first.redirect_url.startswith(FAKE_PAY_PATH)
    assert first.provider_session_id in first.redirect_url
    assert [call.amount_agorot for call in gateway.sessions] == [15000, 20000]
    assert [call.reference for call in gateway.sessions] == ["booking-1", "booking-2"]


def test_fake_verify_webhook_accepts_a_correctly_signed_body() -> None:
    gateway = FakeGateway()
    body = fake_webhook_body(
        provider_session_id="fake-1",
        provider_transaction_id="txn-1",
        amount_agorot=15000,
        paid=True,
    )
    event = gateway.verify_webhook(
        _credentials(), body=body, signature=sign_fake_webhook(webhook_secret=SECRET, body=body)
    )
    assert event == WebhookEvent(
        provider_session_id="fake-1",
        provider_transaction_id="txn-1",
        amount_agorot=15000,
        paid=True,
    )


def test_fake_verify_webhook_rejects_a_tampered_body() -> None:
    gateway = FakeGateway()
    body = fake_webhook_body(
        provider_session_id="fake-1",
        provider_transaction_id="txn-1",
        amount_agorot=15000,
        paid=True,
    )
    signature = sign_fake_webhook(webhook_secret=SECRET, body=body)
    tampered = body.replace(b"15000", b"99900")
    # By TYPE, not merely "something raised": an assertion that any exception
    # escapes is exactly what lets D25's 503-instead-of-400 misclassification
    # ship green.
    with pytest.raises(GatewayWebhookInvalidError):
        gateway.verify_webhook(_credentials(), body=tampered, signature=signature)


def test_fake_verify_webhook_rejects_a_signature_made_with_the_wrong_secret() -> None:
    gateway = FakeGateway()
    body = fake_webhook_body(
        provider_session_id="fake-1",
        provider_transaction_id="txn-1",
        amount_agorot=15000,
        paid=True,
    )
    forged = sign_fake_webhook(webhook_secret="not-the-secret", body=body)
    with pytest.raises(GatewayWebhookInvalidError):
        gateway.verify_webhook(_credentials(), body=body, signature=forged)


def test_fake_verify_webhook_rejects_a_signed_but_unparseable_body() -> None:
    # A correctly signed blob that is not a webhook is still not a webhook.
    gateway = FakeGateway()
    body = b"not json"
    with pytest.raises(GatewayWebhookInvalidError):
        gateway.verify_webhook(
            _credentials(),
            body=body,
            signature=sign_fake_webhook(webhook_secret=SECRET, body=body),
        )


# --- UnconfiguredGateway (D22) ---


async def test_unconfigured_gateway_answers_metadata_and_raises_only_on_io() -> None:
    """D22: the metadata properties ANSWER so that GET /manage/gateway can be
    200 `configured: false` structurally, rather than by a remembered branch two
    features from now."""
    gateway = UnconfiguredGateway()
    assert gateway.is_configured is False
    assert gateway.provider is None
    assert gateway.credential_fields == frozenset()

    with pytest.raises(GatewayNotConfiguredError):
        await gateway.validate_credentials(_credentials())
    with pytest.raises(GatewayNotConfiguredError):
        await gateway.create_session(
            _credentials(),
            amount_agorot=1,
            reference="r",
            return_url="https://bella.example/back",
            expires_in=900,
        )
    with pytest.raises(GatewayNotConfiguredError):
        gateway.verify_webhook(_credentials(), body=b"{}", signature="x")


# --- SecretBox ---


async def test_fake_secret_box_round_trips_and_labels_itself() -> None:
    box = FakeSecretBox()
    assert box.is_configured is True
    assert box.key_ref == "fake"
    ciphertext = await box.encrypt(b"merchant-secret", context=_context("tenant-a"))
    # Unmissable: nobody reading a row can mistake this for encryption.
    assert ciphertext.startswith("fake-secretbox-v1:")
    assert await box.decrypt(ciphertext, context=_context("tenant-a")) == b"merchant-secret"


async def test_fake_secret_box_refuses_another_tenants_context() -> None:
    """The emulated KMS guarantee, and the only place it is testable without an
    AWS account: KMS binds the encryption context into the AEAD's additional
    authenticated data, so a ciphertext copied into another tenant's row cannot
    be decrypted. That is isolation on top of RLS, and this test is its
    regression."""
    box = FakeSecretBox()
    ciphertext = await box.encrypt(b"merchant-secret", context=_context("tenant-a"))
    with pytest.raises(SecretDecryptError):
        await box.decrypt(ciphertext, context=_context("tenant-b"))


async def test_fake_secret_box_refuses_a_wrong_purpose() -> None:
    box = FakeSecretBox()
    ciphertext = await box.encrypt(b"x", context=_context("tenant-a"))
    with pytest.raises(SecretDecryptError):
        await box.decrypt(
            ciphertext, context={"tenant_id": "tenant-a", "purpose": "something_else"}
        )


async def test_fake_secret_box_refuses_a_malformed_blob() -> None:
    box = FakeSecretBox()
    for blob in ("", "not-base64!!", "fake-secretbox-v1:not-base64!!"):
        with pytest.raises(SecretDecryptError):
            await box.decrypt(blob, context=_context("tenant-a"))


async def test_unconfigured_secret_box_raises_on_every_member() -> None:
    box = UnconfiguredSecretBox()
    assert box.is_configured is False
    # key_ref raises rather than answering None (D22's carve-out): a key_ref is
    # WRITTEN to a row and a wrong one is unrecoverable, so there is no
    # null-safe answer to give.
    with pytest.raises(SecretBoxNotConfiguredError):
        _ = box.key_ref
    with pytest.raises(SecretBoxNotConfiguredError):
        await box.encrypt(b"x", context=_context("tenant-a"))
    with pytest.raises(SecretBoxNotConfiguredError):
        await box.decrypt("x", context=_context("tenant-a"))


# --- containment ---


def test_credentials_repr_prints_field_names_and_no_value() -> None:
    """The assertion that survives a refactor of the dataclass. A stray log line
    or a traceback must never render a merchant secret — and here the secret is
    IN the object, so the containment has to be structural."""
    credentials = _credentials()
    rendered = repr(credentials)
    for name in GOOD:
        assert name in rendered
    for value in GOOD.values():
        assert value not in rendered
    # str() falls back to __repr__, so both spellings are covered by the above.
    assert str(credentials) == rendered


def test_the_port_does_not_import_the_database_layer() -> None:
    """base.py's contract, asserted rather than trusted: DepositHold/Settlement
    carry a Payment model and therefore live in service.py. A base.py that
    learned about a model would let F18's adapter reach the database."""
    from app.payments import base

    assert base.__file__, "base module has no file on disk — the scan below is vacuous"
    source = Path(base.__file__).read_text()
    assert "app.db" not in source
    assert "app.models" not in source


def test_adapters_satisfy_the_protocols() -> None:
    # Protocol conformance is structural; assigning to the annotation is the check.
    gateway: PaymentGateway = FakeGateway()
    unconfigured_gateway: PaymentGateway = UnconfiguredGateway()
    box: SecretBox = FakeSecretBox()
    unconfigured_box: SecretBox = UnconfiguredSecretBox()
    assert gateway is not unconfigured_gateway
    assert box is not unconfigured_box
