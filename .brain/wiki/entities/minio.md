---
tags: [backend, storage, testing, docker]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# MinIO

**Purpose.** The S3-compatible server that stands in for AWS in the test suite. Pinned as
`minio/minio:RELEASE.2025-04-22T22-12-26Z` in [[backend/tests/conftest.py]] and started through
[[Testcontainers]] (`testcontainers[postgres,minio]` in [[backend/pyproject.toml]]).

**MinIO over moto, by binding decision.** A fake that merely returns a signed form proves
nothing; MinIO performs genuine SigV4 verification and actually *enforces* the POST-policy
conditions, so the exact-key / exact-Content-Type / exact-byte-length assertions in
[[backend/tests/test_media_upload_s3.py]] mean something. That file carries
`pytestmark = [pytest.mark.db, pytest.mark.s3]` — the `s3` marker is always applied alongside
`db`, so `pytest -m "not db"` (the local loop, no Docker) skips it. See [[DB Test Marker]].

The `minio_container` fixture yields a frozen `MinioEndpoint` dataclass — URL, keys, bucket —
and deliberately **never a client**: a module-level client anywhere would start the container
during collection, including under `-m "not db"`. The bucket is created with the [[Boto3]]
client the project already depends on rather than the `minio` SDK, so tests grow no second
untyped import.

**Trap.** MinIO always sets an explicit `endpoint_url`, which is exactly why its suite stayed
green through the `generate_presigned_post` regional-endpoint bug that broke every real
`il-central-1` upload. Anything about endpoint resolution must be asserted on the fast loop in
[[backend/tests/test_storage_port.py]], not here. MinIO also accepts any region; the tests sign
with `us-east-1` because that is what an unconfigured S3 client assumes.

## Related

- [[Boto3]] · [[Media Storage]] · [[Testcontainers]] · [[Docker]] · [[DB Test Marker]]
