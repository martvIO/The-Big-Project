"""The media storage port. Nothing here imports from app/catalog/ — the caller
passes expires_in and filename, so TTLs and the content-type→extension map stay
in the catalog's validation module and there is no cycle.
"""

import dataclasses
from typing import Protocol


class MediaNotConfiguredError(Exception):
    """No bucket configured, or a bucket with no usable credentials. The two are
    operationally identical and must degrade identically (503, never 500)."""


class MediaStorageUnavailableError(Exception):
    """The storage backend could not be reached or refused the call. Carries no
    AWS-supplied text: the original is logged with the storage key, which embeds
    the tenant, dress and media ids, and never reaches the caller."""


@dataclasses.dataclass(frozen=True)
class PresignedPost:
    """A signed POST policy. `fields` carries `policy` + `x-amz-signature` and is
    bearer material for its whole TTL — never logged, never in an error."""

    url: str
    fields: dict[str, str]


@dataclasses.dataclass(frozen=True)
class ObjectHead:
    content_type: str
    byte_size: int


class MediaStorage(Protocol):
    """presigned_post and signed_get_url are plain `def`: botocore signs them
    with local HMAC and zero I/O, and making them async would be a lie costing
    an await per gallery item on every list response. The other three are real
    network calls, so they are async and the S3 implementation keeps the event
    loop off the blocking client."""

    @property
    def is_configured(self) -> bool: ...

    def presigned_post(
        self, *, key: str, content_type: str, exact_bytes: int, expires_in: int
    ) -> PresignedPost: ...

    def signed_get_url(
        self, *, key: str, content_type: str, filename: str, expires_in: int
    ) -> str: ...

    async def head_object(self, *, key: str) -> ObjectHead | None: ...

    async def read_prefix(self, *, key: str, length: int) -> bytes: ...

    async def delete_object(self, *, key: str) -> None: ...
