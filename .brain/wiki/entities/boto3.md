---
tags: [backend, storage, aws, python]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Boto3

**Purpose.** The AWS SDK, used for S3 and nothing else. `boto3>=1.36` in
[[backend/pyproject.toml]]; the single production call site is `S3MediaStorage` in
[[backend/app/storage/s3.py]], with a second throwaway client building the test bucket in
[[backend/tests/conftest.py]].

**Credentials never enter `Settings`.** There is no `aws_access_key_id` field in
[[backend/app/core/config.py]] — boto3 reads them from the process environment, which is what
keeps them out of the config object's repr and out of logs. [[backend/.env.example]] records
this in a comment rather than a key.

**The client is built lazily, in `_s3()`.** `__init__` does no network I/O and no credential
resolution, because constructing a botocore client walks the whole provider chain whose last
providers read `~/.aws` and call IMDS over the network — that would make `create_app()` unsafe
to call in the fast suite. [[backend/tests/test_storage_port.py]] pins this by monkeypatching
`boto3.client` to explode.

**Trap — the endpoint bug that MinIO could not catch.** `generate_presigned_post()` builds its
form URL from the client's `endpoint_url`, *not* from `region_name`. Left unset, botocore fell
back to the legacy global `<bucket>.s3.amazonaws.com` host, which opt-in regions such as
`il-central-1` reject outright with `IllegalLocationConstraintException` — every real upload
failed while every [[MinIO]] test passed, because MinIO always sets an explicit endpoint. The
fix computes `https://s3.<region>.amazonaws.com` when none is configured; the regression test is
`test_presigned_post_targets_the_regional_endpoint_not_the_legacy_global_one`. Side effect: an
explicit `endpoint_url` makes botocore address the bucket path-style regardless of
`media_force_path_style`, so that flag no longer decides the URL shape.

boto3 and botocore ship no `py.typed` marker, so [[backend/pyproject.toml]] carries a mypy
overrides block for `boto3.*`/`botocore.*` — with `warn_unused_ignores` on, a per-line
`# type: ignore` would itself be flagged, so the override is the only way `mypy app tests` passes.

## Related

- [[Media Storage]] · [[Media Upload Pipeline]] · [[AnyIO]] · [[MinIO]] · [[docs/infra-runbook.md]]
