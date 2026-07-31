---
tags: [backend, config, reliability, design]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Graceful Degradation

**What it is.** A deployment with **no media bucket** or **no SMS provider** is a *supported
configuration*, not a broken one. The affected endpoints answer `503` with a named code; every
other endpoint keeps working; nothing ever answers `500`.

## Null objects, not `None`

[[backend/app/storage/unconfigured.py]] and [[backend/app/notifications/unconfigured.py]] implement
their [[Ports And Adapters]] protocol and raise from every method. `UnconfiguredMediaStorage`'s
docstring gives the reason it is not simply `None`: *no call site grows a null check and no code
path can forget one.* `UnconfiguredSmsSender.send` raises rather than returning a failed
`SendResult`, because the caller's `message_log` row must record `failed` with a reason.

## Four distinct 503s, and the distinction matters

| Code | Means |
|---|---|
| `MEDIA_NOT_CONFIGURED` | no bucket, or a bucket with no usable credentials |
| `MEDIA_STORAGE_UNAVAILABLE` | the backend refused or could not be reached |
| `SMS_NOT_CONFIGURED` | no provider — known at boot, permanent |
| `SMS_UNAVAILABLE` | the provider refused this send |

The "not configured" half is checked **before** any budget is spent and before any row is written,
because a permanent condition must not invalidate a customer's live code or leave an orphan row
behind on the way to the same 503 ([[backend/app/notifications/service.py]]).

## What keeps working

With no bucket, the whole catalog still works — dress and variant CRUD, reorder, reads — with
`url` serialised as `null`. A storefront read **never fails over a missing photo**
([[backend/app/storefront/schemas.py]]). Only the write endpoints degrade.

## Neither error text ever reaches the caller

`MediaStorageUnavailableError` carries no AWS-supplied text and `SmsSendError` carries no
provider-supplied text. The originals are logged server-side with the storage key (which embeds
tenant, dress and media ids) or truncated onto the `message_log` row.

## The trap: missing is fine, *wrong* is fatal

[[backend/app/core/config.py]] draws the line explicitly. A **missing** bucket is never a boot
failure. A bucket with no region is. `MEDIA_ENDPOINT_URL` left set against real AWS in production
points every upload somewhere it must never go, so it refuses to boot — see
[[Fail Fast Configuration]]. "Degrade" applies to absence, never to misconfiguration.

## The frontend half

[[frontend/packages/ui/src/components/DressCard.tsx]] does the inverse and says why: a failed
image load means the presigned URL **expired**, not that the dress has no photo, so the page
refetches instead of degrading to the monogram.

## Related

- [[Ports And Adapters]] · [[Fail Fast Configuration]] · [[Fail Closed Defaults]]
- [[One Time Passcode]] · [[backend/app/main.py]]
