---
tags: [backend, config, design, security]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Product Policy Vs Deployment Identity

**What it is.** A standing rule about where a number is allowed to live.
**`Settings` carries deployment identity. It never carries product policy.**

| | examples | lives in |
|---|---|---|
| **Deployment identity** — differs per environment | which bucket, which region, which endpoint, which SMS adapter, the base domain, the database URL | [[backend/app/core/config.py]] |
| **Product policy** — the same everywhere the product runs | byte caps, presign TTLs, OTP length / TTL / attempt cap, slot interval, list limits, name lengths | `app/<module>/validation.py` |

Both the `media_*` and `sms_*` blocks in `Settings` say so in their own comments, and each names
the validation module that owns the policy half.

## Why it is a rule and not a preference

A product-policy number is not written once. `MAX_UPLOAD_BYTES` exists three times: in
[[backend/app/catalog/validation.py]], in [[frontend/apps/manage/src/validation.ts]], and as a
`CHECK` in [[backend/migrations/versions/0006_catalog.py]]. If it were env-tunable, an operator
raising the limit in one deployment would leave the browser validator and the database constraint
where they were — and the failure surfaces as an `IntegrityError` **500 on confirm**, after the
upload, instead of a clean 400 before it. That exact sentence is the comment above the media block
in `config.py`.

The invariant [[backend/tests/test_frontend_constant_parity.py]] enforces only holds if there is
exactly one authoritative value. An environment variable is a second one.

## The documented exceptions

The interesting part of this rule is the list of things that *do* live in `Settings` anyway, each
with a stated reason:

- **every rate-limit ceiling and window** — login, OTP send and verify, presign, storefront reads,
  booking create, owner SMS, terms creation. These must be tightenable **during an incident
  without a code deploy**, and no client or `CHECK` mirrors them.
- **`worker_poll_interval_seconds`** — deploy-tunable, and a missed window self-heals because the
  claim is `send_after <= now()` rather than an exact-time match.
- **`session_ttl_seconds`** — a session lifetime is an operational posture, not a product bound.

Everything else that looks numeric belongs in a `validation.py`. "It's a number, so it goes in
`Settings`" is exactly the wrong reflex here.

## Related

- [[Input Validation At The Boundary]] · [[Fail Fast Configuration]] · [[Graceful Degradation]]
- [[backend/app/notifications/validation.py]] · [[backend/app/booking/validation.py]]
- [[backend/tests/test_config.py]]
