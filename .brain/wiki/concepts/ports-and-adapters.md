---
tags: [backend, architecture, storage, sms, design]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Ports And Adapters

**What it is.** The two external dependencies this backend has — object storage and SMS — sit
behind a `typing.Protocol` port with several interchangeable adapters. Nothing else in the
codebase uses this pattern, and that restraint is the point: two ports exist because two things
are genuinely swappable.

## The ports

- **`MediaStorage`** — [[backend/app/storage/base.py]]
- **`SmsSender`** — [[backend/app/notifications/base.py]]

Both are structural `Protocol`s, not ABCs, so an adapter never inherits and `mypy` checks
conformance at every call site.

## The dependency rule that keeps them cycle-free

**Neither port imports a feature module.** The caller passes `expires_in` and `filename`; the
caller passes an already-rendered SMS body and an already-normalized phone. That is what lets TTLs
and the content-type→extension map stay in [[backend/app/catalog/validation.py]] and the templates
stay in the notifications service, with no import cycle in either direction. Both base modules say
so in their first paragraph.

## The adapters

| Port | Adapters |
|---|---|
| `MediaStorage` | [[backend/app/storage/s3.py]] · [[backend/app/storage/memory.py]] · [[backend/app/storage/unconfigured.py]] |
| `SmsSender` | [[backend/app/notifications/fake.py]] · [[backend/app/notifications/unconfigured.py]] |

Selection happens once, at app construction, from `Settings` — `_build_media_storage` and
`_build_sms_sender` in [[backend/app/main.py]].

## Two details that look like mistakes and are not

**`InMemoryMediaStorage` lives in `app/`, not `tests/`.** Deliberate: `mypy app tests` then checks
the test double against the `Protocol` exactly like the two real adapters. See [[Test Doubles]].

**Half the `MediaStorage` methods are plain `def`, half are `async`.** `presigned_post` and
`signed_get_url` are synchronous because botocore signs them with local HMAC and **zero I/O** —
making them async would be a lie costing an `await` per gallery item on every list response. The
three that really touch the network are async.

## Related

- [[Graceful Degradation]] — the `Unconfigured*` adapters are the whole reason "no bucket" is a
  supported deployment rather than a crash
- [[Product Policy Vs Deployment Identity]] · [[Test Doubles]]
- [[backend/tests/test_storage_port.py]] · [[backend/tests/test_notifications_adapters.py]]
- [[.planning/specs/gateway-port.md]] — the payments port, specified, not yet built
