"""The at-rest encryption port — the repo's first, because a credential we must
hand back to a provider cannot be hashed the way tokens and passwords are.

One file on purpose (D19): ~90 lines, and no adapter in it performs I/O. The
split into base/fake/unconfigured earns itself when kms.py lands.

Deliberately NOT the same port as PaymentGateway (D1). Which provider takes the
money and which key manager protects the credential are orthogonal: collapsing
them would make the fake gateway untestable against real KMS and the real
gateway untestable without it. Every credential blob encrypts identically
whichever provider reads it.
"""

import base64
import binascii
import json
from collections.abc import Mapping
from typing import Protocol


class SecretDecryptError(Exception):
    """A blob we cannot open — a rotated key, a wrong encryption context, an
    operator error. Deliberately does NOT flip a credential row to 'invalid':
    that would render "your merchant account was refused" to an owner whose
    account is fine and send her to a provider's support desk over our bug."""


class SecretBoxNotConfiguredError(Exception):
    """No box configured. Maps to the same wire code and body as
    GatewayNotConfiguredError (D18) — same operational fact to the owner
    ("deposits are unavailable") and the same remedy (contact the operator).
    The two stay distinguishable server-side, which is where it matters."""


class SecretBox(Protocol):
    """`async` because the real implementation is a network call (KMS), wrapped
    in anyio.to_thread.run_sync exactly as S3MediaStorage.head_object wraps
    botocore.

    `context` is the load-bearing parameter. Every call passes
    {"tenant_id": ..., "purpose": ENCRYPTION_CONTEXT_PURPOSE}. AWS KMS binds the
    encryption context into the AEAD's additional authenticated data, so a
    ciphertext blob copied into another tenant's row CANNOT be decrypted — the
    isolation is cryptographic, on top of RLS, on top of the explicit tenant_id
    predicate. That property is why KMS beats a Fernet key in env (D2), and
    FakeSecretBox emulates it so the regression test exists in CI with no AWS
    account.
    """

    @property
    def key_ref(self) -> str: ...

    @property
    def is_configured(self) -> bool: ...

    async def encrypt(self, plaintext: bytes, *, context: Mapping[str, str]) -> str: ...

    async def decrypt(self, ciphertext: str, *, context: Mapping[str, str]) -> bytes: ...


class FakeSecretBox:
    """THIS IS NOT ENCRYPTION. It is base64 of JSON, with an unmissable prefix so
    nobody reading a row can mistake it for a protected secret.

    Two things keep it out of production: the Settings validator
    (APP_ENV=production + GATEWAY_SECRET_BOX=fake is a boot failure) and
    migration 0012's `provider IN ('fake')` CHECK, which means production can
    hold no credential row at all until a real adapter widens it.

    It DOES emulate the one KMS property worth regression-testing: a context
    mismatch fails. That is the whole reason the tenant-isolation assertion for
    the ciphertext exists in CI at all.
    """

    PREFIX = "fake-secretbox-v1:"

    @property
    def key_ref(self) -> str:
        return "fake"

    @property
    def is_configured(self) -> bool:
        return True

    async def encrypt(self, plaintext: bytes, *, context: Mapping[str, str]) -> str:
        payload = json.dumps(
            {
                "context": dict(context),
                "plaintext": base64.b64encode(plaintext).decode(),
            },
            sort_keys=True,
        ).encode()
        return self.PREFIX + base64.b64encode(payload).decode()

    async def decrypt(self, ciphertext: str, *, context: Mapping[str, str]) -> bytes:
        if not ciphertext.startswith(self.PREFIX):
            raise SecretDecryptError("not a fake-secretbox blob")
        try:
            payload = json.loads(base64.b64decode(ciphertext[len(self.PREFIX) :], validate=True))
            stored_context = payload["context"]
            plaintext = base64.b64decode(payload["plaintext"], validate=True)
        except (binascii.Error, ValueError, KeyError, TypeError) as exc:
            raise SecretDecryptError("blob is malformed") from exc
        if stored_context != dict(context):
            # The emulated AAD binding. KMS would refuse this in the HSM; here it
            # is one comparison, and it is what makes the cross-tenant test real.
            raise SecretDecryptError("encryption context does not match")
        return plaintext


class UnconfiguredSecretBox:
    """Chosen over None for the reason app/storage/unconfigured.py gives: no call
    site grows a null check and no code path can forget one.

    `key_ref` RAISES rather than answering, unlike UnconfiguredGateway.provider
    (D22's carve-out). A key_ref is written to a row and identifies what a
    rotation is replacing — a wrong one is unrecoverable, so there is no
    null-safe answer to give.
    """

    @property
    def key_ref(self) -> str:
        raise SecretBoxNotConfiguredError

    @property
    def is_configured(self) -> bool:
        return False

    async def encrypt(self, plaintext: bytes, *, context: Mapping[str, str]) -> str:
        raise SecretBoxNotConfiguredError

    async def decrypt(self, ciphertext: str, *, context: Mapping[str, str]) -> bytes:
        raise SecretBoxNotConfiguredError
