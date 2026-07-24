from app.storage.base import (
    MediaNotConfiguredError,
    ObjectHead,
    PresignedPost,
)


class UnconfiguredMediaStorage:
    """Chosen over None so no call site grows a null check and no code path can
    forget one: every method fails loudly, the router maps that to a single 503,
    and the rest of the catalog — dress and variant CRUD, reorder, reads — keeps
    working with url serialised as null."""

    @property
    def is_configured(self) -> bool:
        return False

    def presigned_post(
        self, *, key: str, content_type: str, exact_bytes: int, expires_in: int
    ) -> PresignedPost:
        raise MediaNotConfiguredError

    def signed_get_url(self, *, key: str, content_type: str, filename: str, expires_in: int) -> str:
        raise MediaNotConfiguredError

    async def head_object(self, *, key: str) -> ObjectHead | None:
        raise MediaNotConfiguredError

    async def read_prefix(self, *, key: str, length: int) -> bytes:
        raise MediaNotConfiguredError

    async def delete_object(self, *, key: str) -> None:
        raise MediaNotConfiguredError
