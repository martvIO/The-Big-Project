"""Feature 8 storage port — local, no network, no container.

Everything here runs on the fast loop. botocore signs POST policies and GET URLs
with local HMAC and zero I/O, so a client built from explicit dummy credentials
produces a *real* policy this test can base64-decode and assert against. What
only MinIO can prove — that S3 then *enforces* those conditions — lives in
test_media_upload_s3.py.
"""

import ast
import base64
import datetime
import json
import socket
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    NoCredentialsError,
    PartialCredentialsError,
)
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.rate_limit import FixedWindowRateLimiter
from app.catalog.service import CatalogService
from app.catalog.validation import PRESIGN_TTL_SECONDS, SIGNED_GET_TTL_SECONDS
from app.core.config import Settings
from app.main import create_app
from app.models.dress_media import DressMedia
from app.storage.base import (
    MediaNotConfiguredError,
    MediaStorage,
    MediaStorageUnavailableError,
    ObjectHead,
    PresignedPost,
)
from app.storage.memory import InMemoryMediaStorage
from app.storage.s3 import S3MediaStorage
from app.storage.unconfigured import UnconfiguredMediaStorage

TESTS_DIR = Path(__file__).resolve().parent

BUCKET = "boutique-media"
TENANT_ID = "11111111-1111-4111-8111-111111111111"
DRESS_ID = "22222222-2222-4222-8222-222222222222"
MEDIA_ID = "33333333-3333-4333-8333-333333333333"
KEY = f"tenants/{TENANT_ID}/dresses/{DRESS_ID}/media/{MEDIA_ID}.jpg"
JPEG = "image/jpeg"

# Anything the AWS SDK hands us is untrusted for display: it can name the
# bucket, the account, the full key. None of it may cross the port boundary.
AWS_LEAK = "AccessDenied: arn:aws:s3:::boutique-prod-media is not accessible by this principal"

# The canonical AWS documentation example pair. Explicit dummy credentials keep
# the provider chain on its first (environment) provider, so building a client
# never reads ~/.aws and never reaches IMDS over the network.
DUMMY_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
DUMMY_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "dev",
        "media_bucket": BUCKET,
        "media_region": "il-central-1",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def dummy_aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", DUMMY_ACCESS_KEY)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", DUMMY_SECRET_KEY)
    monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)


# --- unconfigured ---


def test_unconfigured_storage_is_never_configured() -> None:
    assert UnconfiguredMediaStorage().is_configured is False


async def test_unconfigured_storage_raises_on_every_method() -> None:
    """The null object exists so no call site grows a None check — which means
    every method must fail loudly rather than return an empty success."""
    storage = UnconfiguredMediaStorage()

    with pytest.raises(MediaNotConfiguredError):
        storage.presigned_post(key=KEY, content_type=JPEG, exact_bytes=1024, expires_in=300)
    with pytest.raises(MediaNotConfiguredError):
        storage.signed_get_url(key=KEY, content_type=JPEG, filename="x.jpg", expires_in=900)
    with pytest.raises(MediaNotConfiguredError):
        await storage.head_object(key=KEY)
    with pytest.raises(MediaNotConfiguredError):
        await storage.read_prefix(key=KEY, length=16)
    with pytest.raises(MediaNotConfiguredError):
        await storage.delete_object(key=KEY)


def test_every_implementation_satisfies_the_port() -> None:
    """The annotation is the assertion: mypy checks each class structurally
    against MediaStorage, so a signature drifting from the Protocol fails the
    type step instead of at the first call site."""
    implementations: list[MediaStorage] = [
        UnconfiguredMediaStorage(),
        InMemoryMediaStorage(),
        S3MediaStorage(_settings()),
    ]
    assert [impl.is_configured for impl in implementations] == [False, True, True]


# --- construction is inert ---


def test_s3_storage_init_opens_no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _explode(self: socket.socket, address: object) -> None:
        raise AssertionError("S3MediaStorage.__init__ opened a socket")

    monkeypatch.setattr(socket.socket, "connect", _explode)
    assert S3MediaStorage(_settings()).is_configured is True


def test_s3_storage_init_resolves_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Building a botocore client walks the whole credential chain, whose last
    providers read ~/.aws and call IMDS over the network. create_app() must stay
    safe to call in the fast suite whatever the local environment holds, so the
    client is built on first use and never in __init__."""

    def _explode(*args: object, **kwargs: object) -> Any:
        raise AssertionError("S3MediaStorage.__init__ built the botocore client")

    monkeypatch.setattr("app.storage.s3.boto3.client", _explode)
    S3MediaStorage(_settings())


# --- POST policy shape (local HMAC, no network) ---


def _presign(storage: S3MediaStorage, **overrides: Any) -> PresignedPost:
    kwargs: dict[str, Any] = {
        "key": KEY,
        "content_type": JPEG,
        "exact_bytes": 1024,
        "expires_in": 300,
    }
    kwargs.update(overrides)
    return storage.presigned_post(**kwargs)


def _policy(post: PresignedPost) -> dict[str, Any]:
    decoded: dict[str, Any] = json.loads(base64.b64decode(post.fields["policy"]))
    return decoded


def _condition_names(conditions: list[Any]) -> set[str]:
    names: set[str] = set()
    for condition in conditions:
        if isinstance(condition, dict):
            names.update(name.lower() for name in condition)
        elif isinstance(condition, list) and condition:
            head = str(condition[0]).lower()
            names.add(str(condition[1]).lstrip("$").lower() if head == "eq" else head)
    return names


def _exact_match(conditions: list[Any], field: str) -> Any:
    """An S3 POST policy expresses an exact match either as {"field": value} or
    as ["eq", "$field", value]; the two are equivalent and botocore emits the
    former. Normalise both so this asserts the security property, not botocore's
    choice of spelling."""
    for condition in conditions:
        if isinstance(condition, dict):
            for name, value in condition.items():
                if name.lower() == field.lower():
                    return value
        elif (
            isinstance(condition, list)
            and len(condition) == 3
            and condition[0] == "eq"
            and str(condition[1]).lstrip("$").lower() == field.lower()
        ):
            return condition[2]
    return None


def test_presigned_post_pins_the_exact_key(dummy_aws_credentials: None) -> None:
    """The condition that stops a client writing outside its tenant prefix, or
    over another dress's object, whatever it puts in the form."""
    conditions = _policy(_presign(S3MediaStorage(_settings())))["conditions"]
    pinned = _exact_match(conditions, "key")
    assert pinned == KEY
    assert pinned.startswith(f"tenants/{TENANT_ID}/")


def test_presigned_post_pins_the_declared_content_type(dummy_aws_credentials: None) -> None:
    post = _presign(S3MediaStorage(_settings()))
    assert _exact_match(_policy(post)["conditions"], "Content-Type") == JPEG
    # Content-Type travels as a form field, not a header: the browser owns the
    # request's Content-Type (the multipart boundary).
    assert post.fields["Content-Type"] == JPEG


def test_presigned_post_length_range_has_both_bounds_equal(dummy_aws_credentials: None) -> None:
    """Exact, not MIN..MAX. "Declare 1 KiB, post 10 MiB" is the deliberate way
    to plant a large orphan the DB can never find again; pinning the range to
    the declared value makes it structurally impossible and leaves MEDIA_MISMATCH
    for content-type and magic-byte failures only."""
    conditions = _policy(_presign(S3MediaStorage(_settings()), exact_bytes=4096))["conditions"]
    ranges = [c for c in conditions if isinstance(c, list) and c[0] == "content-length-range"]
    assert ranges == [["content-length-range", 4096, 4096]]


def test_presigned_post_carries_no_acl_and_no_encryption_condition(
    dummy_aws_credentials: None,
) -> None:
    """The bucket is Object-Ownership "bucket owner enforced", where ACLs are
    disabled and an acl form field makes S3 reject the POST outright. SSE is a
    bucket property (F2 §B3), and pinning the header would break MinIO and every
    other S3-compatible target. Both omissions are load-bearing."""
    post = _presign(S3MediaStorage(_settings()))
    names = _condition_names(_policy(post)["conditions"])
    fields = {name.lower() for name in post.fields}
    assert "acl" not in names | fields
    assert "x-amz-server-side-encryption" not in names | fields


def test_presigned_post_expires_within_the_requested_window(dummy_aws_credentials: None) -> None:
    before = datetime.datetime.now(datetime.UTC)
    policy = _policy(_presign(S3MediaStorage(_settings()), expires_in=300))
    expiration = datetime.datetime.strptime(policy["expiration"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.UTC
    )
    assert before < expiration <= before + datetime.timedelta(seconds=301)


def test_presigned_post_returns_the_fields_the_browser_must_post(
    dummy_aws_credentials: None,
) -> None:
    post = _presign(S3MediaStorage(_settings()))
    assert post.url
    assert {
        "key",
        "Content-Type",
        "policy",
        "x-amz-algorithm",
        "x-amz-credential",
        "x-amz-date",
        "x-amz-signature",
    } <= set(post.fields)
    assert post.fields["key"] == KEY


# --- signed GET shape ---


def test_signed_get_url_forces_the_stored_type_and_an_attachment_download(
    dummy_aws_credentials: None,
) -> None:
    """S3 cannot emit X-Content-Type-Options on a presigned GET, so the response
    overrides are half the sniffing defense. attachment (never inline) is what
    turns a top-level navigation to a polyglot object from render into download;
    it is ignored for subresource loads, so <img src> still renders."""
    url = S3MediaStorage(_settings()).signed_get_url(
        key=KEY, content_type=JPEG, filename=f"{MEDIA_ID}.jpg", expires_in=900
    )
    assert "response-content-type=image%2Fjpeg" in url
    assert f"filename%3D%22{MEDIA_ID}.jpg%22" in url
    assert "attachment" in url
    assert "inline" not in url
    assert "X-Amz-Expires=900" in url


# --- failure contract ---


class _StubS3Client:
    """Stands in for the botocore client: every call raises the one configured
    error, so the mapping is asserted without a network."""

    def __init__(self, error: BaseException) -> None:
        self._error = error

    def generate_presigned_post(self, **kwargs: Any) -> dict[str, Any]:
        raise self._error

    def generate_presigned_url(self, *args: Any, **kwargs: Any) -> str:
        raise self._error

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        raise self._error

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        raise self._error

    def delete_object(self, **kwargs: Any) -> dict[str, Any]:
        raise self._error


def _client_error(code: str, status: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": AWS_LEAK},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "HeadObject",
    )


def _stub_storage(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> S3MediaStorage:
    def _client(*args: object, **kwargs: object) -> _StubS3Client:
        return _StubS3Client(error)

    monkeypatch.setattr("app.storage.s3.boto3.client", _client)
    return S3MediaStorage(_settings())


def _assert_no_aws_text(message: str) -> None:
    assert AWS_LEAK not in message
    assert "AccessDenied" not in message
    assert "arn:aws" not in message
    assert BUCKET not in message


async def test_client_error_becomes_unavailable_and_leaks_no_aws_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _stub_storage(monkeypatch, _client_error("AccessDenied", 403))

    raised: list[MediaStorageUnavailableError] = []
    with pytest.raises(MediaStorageUnavailableError) as presign:
        storage.presigned_post(key=KEY, content_type=JPEG, exact_bytes=1024, expires_in=300)
    raised.append(presign.value)
    with pytest.raises(MediaStorageUnavailableError) as signed_get:
        storage.signed_get_url(key=KEY, content_type=JPEG, filename="x.jpg", expires_in=900)
    raised.append(signed_get.value)
    with pytest.raises(MediaStorageUnavailableError) as read:
        await storage.read_prefix(key=KEY, length=16)
    raised.append(read.value)
    with pytest.raises(MediaStorageUnavailableError) as delete:
        await storage.delete_object(key=KEY)
    raised.append(delete.value)

    for error in raised:
        _assert_no_aws_text(str(error))
        _assert_no_aws_text(repr(error))


async def test_boto_core_error_becomes_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = _stub_storage(monkeypatch, ConnectTimeoutError(endpoint_url="https://s3.example"))
    with pytest.raises(MediaStorageUnavailableError) as raised:
        await storage.delete_object(key=KEY)
    assert "s3.example" not in str(raised.value)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(NoCredentialsError(), id="no_credentials"),
        pytest.param(
            PartialCredentialsError(provider="env", cred_var="aws_secret_access_key"),
            id="partial_credentials",
        ),
    ],
)
async def test_missing_credentials_become_not_configured(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    """A bucket without usable credentials is operationally identical to no
    bucket — it must degrade to 503 MEDIA_NOT_CONFIGURED, never 500. This is the
    exact state F8 ships into while the AWS account is still not-started."""
    storage = _stub_storage(monkeypatch, error)

    with pytest.raises(MediaNotConfiguredError):
        storage.presigned_post(key=KEY, content_type=JPEG, exact_bytes=1024, expires_in=300)
    with pytest.raises(MediaNotConfiguredError):
        await storage.head_object(key=KEY)
    with pytest.raises(MediaNotConfiguredError):
        await storage.read_prefix(key=KEY, length=16)
    with pytest.raises(MediaNotConfiguredError):
        await storage.delete_object(key=KEY)


@pytest.mark.parametrize(
    ("code", "status"),
    [
        pytest.param("404", 404, id="head_miss"),
        pytest.param("NoSuchKey", 404, id="no_such_key"),
    ],
)
async def test_head_object_returns_none_for_a_genuine_miss(
    monkeypatch: pytest.MonkeyPatch, code: str, status: int
) -> None:
    storage = _stub_storage(monkeypatch, _client_error(code, status))
    assert await storage.head_object(key=KEY) is None


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(_client_error("InternalError", 500), id="server_error"),
        pytest.param(_client_error("SlowDown", 503), id="throttled"),
        pytest.param(ConnectTimeoutError(endpoint_url="https://s3.example"), id="connect_timeout"),
    ],
)
async def test_head_object_never_reads_an_outage_as_a_missing_object(
    monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    """None is the confirm path's "your upload never arrived" (409
    MEDIA_NOT_UPLOADED) and it deletes nothing but the owner's confidence. An
    outage must answer 503 with the pending row untouched and confirmable."""
    storage = _stub_storage(monkeypatch, error)
    with pytest.raises(MediaStorageUnavailableError):
        await storage.head_object(key=KEY)


# --- the service passes the production TTLs ---


class _RecordingStorage:
    """Records the expires_in every call site asks for. The MinIO rows sign with
    expires_in=1 to test S3's *enforcement* of expiry without sleeping 15
    minutes, so without this fake the production defaults would never be
    asserted anywhere."""

    def __init__(self) -> None:
        self.presign_expires_in: list[int] = []
        self.signed_get_expires_in: list[int] = []
        self.signed_get_filenames: list[str] = []

    @property
    def is_configured(self) -> bool:
        return True

    def presigned_post(
        self, *, key: str, content_type: str, exact_bytes: int, expires_in: int
    ) -> PresignedPost:
        self.presign_expires_in.append(expires_in)
        return PresignedPost(url="https://media.test/upload", fields={"key": key})

    def signed_get_url(self, *, key: str, content_type: str, filename: str, expires_in: int) -> str:
        self.signed_get_expires_in.append(expires_in)
        self.signed_get_filenames.append(filename)
        return f"https://media.test/{key}"

    async def head_object(self, *, key: str) -> ObjectHead | None:
        return None

    async def read_prefix(self, *, key: str, length: int) -> bytes:
        return b""

    async def delete_object(self, *, key: str) -> None:
        return None


def _catalog_service(storage: MediaStorage) -> CatalogService:
    # The engine is never connected: both assertions below are about what the
    # service asks the storage port for, not about the database.
    engine = create_async_engine("postgresql+asyncpg://unused:unused@127.0.0.1:1/unused")
    return CatalogService(
        async_sessionmaker(engine, expire_on_commit=False),
        media_storage=storage,
        presign_rate_limiter=FixedWindowRateLimiter(
            max_attempts=1, window_seconds=1, clock=time.monotonic
        ),
    )


def test_service_presigns_with_the_production_ttl() -> None:
    storage = _RecordingStorage()
    _catalog_service(storage)._sign_upload(key=KEY, content_type=JPEG, byte_size=4096)
    assert storage.presign_expires_in == [PRESIGN_TTL_SECONDS]


def test_service_signs_gallery_urls_with_the_production_ttl() -> None:
    storage = _RecordingStorage()
    row = DressMedia(
        id=uuid.UUID(MEDIA_ID),
        tenant_id=uuid.UUID(TENANT_ID),
        dress_id=uuid.UUID(DRESS_ID),
        storage_key=KEY,
        content_type=JPEG,
        byte_size=4096,
        status="ready",
        sort_order=0,
    )
    view = _catalog_service(storage)._media_view(row)

    assert storage.signed_get_expires_in == [SIGNED_GET_TTL_SECONDS]
    # The download name comes from the row's own id — the original filename is
    # never stored, so no client string can reach a Content-Disposition header.
    assert storage.signed_get_filenames == [f"{MEDIA_ID}.jpg"]
    assert view.url is not None
    assert view.url_expires_at is not None


def test_unconfigured_storage_serialises_a_null_url_instead_of_raising() -> None:
    """Reads keep working with no bucket: only the media WRITE endpoints answer
    503. A read that raised would take the whole catalog down with the bucket."""
    row = DressMedia(
        id=uuid.UUID(MEDIA_ID),
        tenant_id=uuid.UUID(TENANT_ID),
        dress_id=uuid.UUID(DRESS_ID),
        storage_key=KEY,
        content_type=JPEG,
        byte_size=4096,
        status="ready",
        sort_order=0,
    )
    view = _catalog_service(UnconfiguredMediaStorage())._media_view(row)
    assert view.url is None
    assert view.url_expires_at is None


class _UnsignableStorage(InMemoryMediaStorage):
    """Configured, but signing raises — the credential-rotation state, where
    `is_configured` still answers True and only the call fails."""

    def __init__(self, error: Exception) -> None:
        super().__init__()
        self._error = error

    def signed_get_url(self, *, key: str, content_type: str, filename: str, expires_in: int) -> str:
        raise self._error


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(MediaNotConfiguredError(), id="credentials_gone"),
        pytest.param(MediaStorageUnavailableError(), id="storage_down"),
    ],
)
def test_a_read_degrades_to_a_null_url_when_signing_fails(error: Exception) -> None:
    """Branching on `is_configured` alone is not enough: a bucket whose IAM key
    rotated is still configured, and letting the failure propagate would turn a
    plain GET /manage/dresses into a 503. The spec confines that 503 to presign,
    confirm and media delete — reads degrade to `url: null`, like no bucket."""
    row = DressMedia(
        id=uuid.UUID(MEDIA_ID),
        tenant_id=uuid.UUID(TENANT_ID),
        dress_id=uuid.UUID(DRESS_ID),
        storage_key=KEY,
        content_type=JPEG,
        byte_size=4096,
        status="ready",
        sort_order=0,
    )
    view = _catalog_service(_UnsignableStorage(error))._media_view(row)
    assert view.url is None
    assert view.url_expires_at is None


# --- create_app() selection ---


def _app_with_settings(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> FastAPI:
    async def _resolver(slug: str) -> None:
        return None

    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    return create_app(resolver=_resolver)


def test_create_app_selects_unconfigured_storage_without_a_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No bucket is a supported deployment, not a boot failure: the app comes up
    and only the media write endpoints answer 503."""
    app = _app_with_settings(monkeypatch, _settings(media_bucket=None))
    assert isinstance(app.state.media_storage, UnconfiguredMediaStorage)
    assert app.state.media_storage.is_configured is False


def test_create_app_selects_s3_storage_with_a_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    """S3MediaStorage.__init__ does no network I/O, which is what keeps
    create_app() safe to call in the fast suite whatever the local .env holds."""
    app = _app_with_settings(monkeypatch, _settings())
    assert isinstance(app.state.media_storage, S3MediaStorage)


def test_create_app_gives_the_catalog_service_the_same_storage_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app_with_settings(monkeypatch, _settings(media_bucket=None))
    assert app.state.catalog_service._storage is app.state.media_storage


# --- marker guard ---


# Spelled in two halves so the needle this test scans for never appears
# literally in this file — otherwise the guard would have to skip itself.
S3_MARKER = "s3"


def _module_pytestmark(source: str) -> set[str]:
    markers: set[str] = set()
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign):
            continue
        assigned = {target.id for target in node.targets if isinstance(target, ast.Name)}
        if "pytestmark" not in assigned:
            continue
        for child in ast.walk(node.value):
            if isinstance(child, ast.Attribute):
                markers.add(child.attr)
    return markers


def test_no_s3_marker_without_db() -> None:
    """`make test` is `pytest -m "not db"`. An s3-only file is therefore
    collected locally, requests minio_container, hits _docker_running() and
    fails the whole no-Docker loop. s3 is a companion marker, never a solo one —
    and only as a module-level pytestmark, so this guard can see it."""
    needle = f"pytest.mark.{S3_MARKER}"
    offenders = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        if needle not in source:
            continue
        if not {S3_MARKER, "db"} <= _module_pytestmark(source):
            offenders.append(path.name)
    assert offenders == [], f"marked {S3_MARKER} without a module-level db marker: {offenders}"
