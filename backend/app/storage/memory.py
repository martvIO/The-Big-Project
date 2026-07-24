from app.storage.base import (
    MediaStorageUnavailableError,
    ObjectHead,
    PresignedPost,
)


class InMemoryMediaStorage:
    """The third implementation, for tests that need a working storage without a
    container: the service's presign→confirm sequence, the API fakes, and the
    isolation suite. It lives in app/ rather than tests/ so `mypy app tests`
    checks it against the Protocol like the other two.

    There is no upload endpoint to POST to — a test simulates the browser's POST
    by calling put() with the same key the presign returned.
    """

    def __init__(self) -> None:
        self.objects: dict[str, tuple[str, bytes]] = {}

    @property
    def is_configured(self) -> bool:
        return True

    def put(self, *, key: str, content_type: str, body: bytes) -> None:
        self.objects[key] = (content_type, body)

    def presigned_post(
        self, *, key: str, content_type: str, exact_bytes: int, expires_in: int
    ) -> PresignedPost:
        return PresignedPost(
            url="https://media.test/upload",
            fields={
                "key": key,
                "Content-Type": content_type,
                "policy": "test-policy",
                "x-amz-algorithm": "AWS4-HMAC-SHA256",
                "x-amz-credential": "test-credential",
                "x-amz-date": "20260724T000000Z",
                "x-amz-signature": "test-signature",
            },
        )

    def signed_get_url(self, *, key: str, content_type: str, filename: str, expires_in: int) -> str:
        return (
            f"https://media.test/{key}?response-content-type={content_type}"
            f"&response-content-disposition=attachment%3B%20filename%3D%22{filename}%22"
            f"&X-Amz-Expires={expires_in}"
        )

    async def head_object(self, *, key: str) -> ObjectHead | None:
        stored = self.objects.get(key)
        if stored is None:
            return None
        content_type, body = stored
        return ObjectHead(content_type=content_type, byte_size=len(body))

    async def read_prefix(self, *, key: str, length: int) -> bytes:
        stored = self.objects.get(key)
        if stored is None:
            # Matches S3: a GET on a key that isn't there is an error, not an
            # empty read. Confirm heads first, so reaching this is a real race.
            raise MediaStorageUnavailableError
        return stored[1][:length]

    async def delete_object(self, *, key: str) -> None:
        self.objects.pop(key, None)
