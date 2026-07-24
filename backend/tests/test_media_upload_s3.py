"""Feature 8 media upload against a real MinIO — the assertions no fake can
make, because they are about what the *storage* enforces, not what we ask for.

MinIO over moto by binding decision: it performs genuine SigV4 verification,
really enforces POST-policy conditions and accepts a browser-shaped multipart
body. moto validates permissively, which would make every row below vacuous.

The two expiry rows sign with expires_in=1 deliberately: they test S3's
enforcement of the expiry field, not our default values — those are asserted
without a network in test_storage_port.py. Sleeping 300 s in CI is not an option.
"""

import time
import uuid

import httpx
import pytest
from conftest import MinioEndpoint

from app.core.config import Settings
from app.storage.base import PresignedPost
from app.storage.s3 import S3MediaStorage

pytestmark = [pytest.mark.db, pytest.mark.s3]

# MinIO accepts any region; us-east-1 is what an unconfigured S3 client assumes.
MINIO_REGION = "us-east-1"

TENANT_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
OTHER_TENANT_ID = uuid.UUID("66666666-6666-4666-8666-666666666666")
DRESS_ID = uuid.UUID("77777777-7777-4777-8777-777777777777")

JPEG = "image/jpeg"
PNG = "image/png"
JPEG_MAGIC = b"\xff\xd8\xff"


def _key(tenant_id: uuid.UUID = TENANT_ID) -> str:
    return f"tenants/{tenant_id}/dresses/{DRESS_ID}/media/{uuid.uuid4()}.jpg"


def _jpeg(size: int) -> bytes:
    return JPEG_MAGIC + b"\x00" * (size - len(JPEG_MAGIC))


@pytest.fixture
def storage(minio_container: MinioEndpoint, monkeypatch: pytest.MonkeyPatch) -> S3MediaStorage:
    # Credentials never enter Settings — boto3 reads them from the process
    # environment, in production and here alike.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", minio_container.access_key)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", minio_container.secret_key)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    return S3MediaStorage(
        Settings(
            app_env="dev",
            database_url=None,
            media_bucket=minio_container.bucket,
            media_region=MINIO_REGION,
            media_endpoint_url=minio_container.url,
            media_force_path_style=True,
        )
    )


def _presign(
    storage: S3MediaStorage,
    *,
    key: str | None = None,
    exact_bytes: int = 1024,
    expires_in: int = 300,
) -> PresignedPost:
    return storage.presigned_post(
        key=key or _key(), content_type=JPEG, exact_bytes=exact_bytes, expires_in=expires_in
    )


def _post(
    presigned: PresignedPost,
    payload: bytes,
    *,
    part_type: str = JPEG,
    overrides: dict[str, str] | None = None,
) -> httpx.Response:
    """A browser-shaped multipart POST: every presign field first, `file` last
    (S3 ignores anything after it). httpx preserves that order."""
    form = dict(presigned.fields)
    form.update(overrides or {})
    return httpx.post(
        presigned.url,
        data=form,
        files={"file": ("dress.jpg", payload, part_type)},
        timeout=30.0,
    )


def _upload(storage: S3MediaStorage, key: str, payload: bytes) -> None:
    response = _post(_presign(storage, key=key, exact_bytes=len(payload)), payload)
    assert response.status_code == 204, response.text


def test_posting_a_different_content_type_is_rejected(storage: S3MediaStorage) -> None:
    """An SVG or HTML payload uploaded under a jpeg presign is stored XSS on the
    storefront. The policy — not our code — is what refuses it."""
    response = _post(_presign(storage), _jpeg(1024), part_type=PNG, overrides={"Content-Type": PNG})
    assert response.status_code == 403


def test_posting_more_bytes_than_declared_is_rejected(storage: S3MediaStorage) -> None:
    """Declaring 1 KiB and posting 1 MiB is the deliberate way to plant a large
    orphan the DB can never find again. The exact range is what kills it."""
    response = _post(_presign(storage, exact_bytes=1024), _jpeg(1024 * 1024))
    assert not response.is_success
    assert "EntityTooLarge" in response.text


def test_posting_fewer_bytes_than_declared_is_rejected(storage: S3MediaStorage) -> None:
    response = _post(_presign(storage, exact_bytes=1024 * 1024), _jpeg(1024))
    assert not response.is_success
    assert "EntityTooSmall" in response.text


def test_rewriting_the_key_to_another_tenant_prefix_is_rejected(storage: S3MediaStorage) -> None:
    """The key is computed server-side from the host-derived tenant and a dress
    row this tenant owns. A client that edits the field back to another tenant's
    prefix is refused by S3, so tenant prefixing is an enforced boundary rather
    than a naming convention."""
    response = _post(_presign(storage), _jpeg(1024), overrides={"key": _key(OTHER_TENANT_ID)})
    assert response.status_code == 403


def test_posting_after_the_policy_expires_is_rejected(storage: S3MediaStorage) -> None:
    presigned = _presign(storage, expires_in=1)
    time.sleep(1.5)
    assert _post(presigned, _jpeg(1024)).status_code == 403


def test_signed_get_downloads_the_object_and_then_expires(storage: S3MediaStorage) -> None:
    key = _key()
    media_id = key.rsplit("/", 1)[-1]
    _upload(storage, key, _jpeg(2048))

    fresh = storage.signed_get_url(key=key, content_type=JPEG, filename=media_id, expires_in=900)
    served = httpx.get(fresh, timeout=30.0)
    assert served.status_code == 200
    assert served.headers["content-type"] == JPEG
    assert served.headers["content-disposition"] == f'attachment; filename="{media_id}"'

    stale = storage.signed_get_url(key=key, content_type=JPEG, filename=media_id, expires_in=1)
    time.sleep(1.5)
    assert httpx.get(stale, timeout=30.0).status_code == 403


async def test_delete_object_then_head_object_is_none(storage: S3MediaStorage) -> None:
    key = _key()
    payload = _jpeg(3072)
    _upload(storage, key, payload)

    head = await storage.head_object(key=key)
    assert head is not None
    assert head.content_type == JPEG
    assert head.byte_size == len(payload)

    await storage.delete_object(key=key)
    assert await storage.head_object(key=key) is None
