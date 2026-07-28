import contextlib
import logging
from collections.abc import Iterator
from typing import Any

import boto3
from anyio import to_thread
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
)

from app.core.config import Settings
from app.storage.base import (
    MediaNotConfiguredError,
    MediaStorageUnavailableError,
    ObjectHead,
    PresignedPost,
)

logger = logging.getLogger("storage")

# HeadObject has no response body, so S3 reports a miss as the bare HTTP status;
# GetObject reports NoSuchKey. Everything else — including a 500, a throttle or
# a timeout — is an outage, never "your upload never arrived".
_MISSING_OBJECT_CODES = frozenset({"404", "NotFound", "NoSuchKey"})


def _is_missing_object(exc: ClientError) -> bool:
    response = getattr(exc, "response", None) or {}
    code = str(response.get("Error", {}).get("Code", ""))
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in _MISSING_OBJECT_CODES or status == 404


class S3MediaStorage:
    """S3 (or any S3-compatible endpoint) behind the media storage port.

    __init__ performs no network I/O and no credential resolution: building a
    botocore client walks the whole provider chain, whose last providers read
    ~/.aws and call IMDS over the network. The client is built on first use
    instead, which is what keeps create_app() safe to call in the fast suite
    whatever the local environment holds.

    AWS credentials are deliberately not Settings fields — boto3 reads them from
    the process environment, so they never enter our config object, never appear
    in a repr and never get logged.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.media_bucket:
            raise ValueError("S3MediaStorage requires MEDIA_BUCKET; use UnconfiguredMediaStorage")
        self._bucket = settings.media_bucket
        self._region = settings.media_region
        self._endpoint_url = settings.media_endpoint_url
        self._force_path_style = settings.media_force_path_style
        self._client: Any = None

    @property
    def is_configured(self) -> bool:
        return True

    def _s3(self) -> Any:
        if self._client is None:
            # generate_presigned_post() builds its form `url` from the client's
            # endpoint_url, not from region_name — leaving endpoint_url unset lets
            # botocore fall back to the legacy global `bucket.s3.amazonaws.com`
            # host, which AWS opt-in regions (il-central-1 included) reject with
            # IllegalLocationConstraintException. Always resolve a real endpoint.
            endpoint_url = self._endpoint_url or f"https://s3.{self._region}.amazonaws.com"
            self._client = boto3.client(
                "s3",
                region_name=self._region,
                endpoint_url=endpoint_url,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"} if self._force_path_style else {},
                ),
            )
        return self._client

    @contextlib.contextmanager
    def _mapped_errors(self, *, operation: str, key: str) -> Iterator[None]:
        # `from None` keeps the original off any rendered traceback: an AWS
        # message can name the bucket, the account and the full key.
        try:
            yield
        except (NoCredentialsError, PartialCredentialsError):
            logger.warning("media storage credentials unusable: op=%s key=%s", operation, key)
            raise MediaNotConfiguredError from None
        except (ClientError, BotoCoreError) as exc:
            # The key embeds tenant_id, dress_id and media_id, so this one line
            # is enough to correlate the failure with the row that caused it.
            logger.warning(
                "media storage call failed: op=%s key=%s error=%s",
                operation,
                key,
                type(exc).__name__,
                exc_info=exc,
            )
            raise MediaStorageUnavailableError from None

    def presigned_post(
        self, *, key: str, content_type: str, exact_bytes: int, expires_in: int
    ) -> PresignedPost:
        """A POST policy, not a PUT: only POST makes S3 itself enforce the exact
        key AND the exact Content-Type AND a length range.

        The range is exact rather than MIN..MAX, so an object whose size differs
        from the row that authorised it cannot exist. No `acl` field (the bucket
        is bucket-owner-enforced, where ACLs are disabled and an acl field makes
        S3 reject the POST) and no server-side-encryption condition (encryption
        is a bucket property; pinning the header would break every S3-compatible
        target). Both omissions are load-bearing — see spec Decisions 4.
        """
        with self._mapped_errors(operation="presigned_post", key=key):
            response = self._s3().generate_presigned_post(
                Bucket=self._bucket,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", exact_bytes, exact_bytes],
                ],
                ExpiresIn=expires_in,
            )
        return PresignedPost(url=response["url"], fields=dict(response["fields"]))

    def signed_get_url(self, *, key: str, content_type: str, filename: str, expires_in: int) -> str:
        """S3 cannot emit X-Content-Type-Options on a presigned GET, so these two
        response overrides are half the sniffing defense. `attachment` — never
        `inline` — is ignored for subresource loads, so <img src> still renders,
        while a top-level navigation to a polyglot object downloads instead of
        executing."""
        with self._mapped_errors(operation="signed_get_url", key=key):
            url: str = self._s3().generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": key,
                    "ResponseContentType": content_type,
                    "ResponseContentDisposition": f'attachment; filename="{filename}"',
                },
                ExpiresIn=expires_in,
            )
        return url

    async def head_object(self, *, key: str) -> ObjectHead | None:
        def _head() -> ObjectHead | None:
            try:
                response = self._s3().head_object(Bucket=self._bucket, Key=key)
            except ClientError as exc:
                if _is_missing_object(exc):
                    return None
                raise
            return ObjectHead(
                content_type=str(response.get("ContentType", "")),
                byte_size=int(response["ContentLength"]),
            )

        with self._mapped_errors(operation="head_object", key=key):
            return await to_thread.run_sync(_head)

    async def read_prefix(self, *, key: str, length: int) -> bytes:
        def _read() -> bytes:
            response = self._s3().get_object(
                Bucket=self._bucket, Key=key, Range=f"bytes=0-{length - 1}"
            )
            body = response["Body"]
            try:
                return bytes(body.read())
            finally:
                body.close()

        with self._mapped_errors(operation="read_prefix", key=key):
            return await to_thread.run_sync(_read)

    async def delete_object(self, *, key: str) -> None:
        def _delete() -> None:
            self._s3().delete_object(Bucket=self._bucket, Key=key)

        with self._mapped_errors(operation="delete_object", key=key):
            await to_thread.run_sync(_delete)
