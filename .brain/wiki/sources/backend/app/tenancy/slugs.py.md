---
tags: [backend, tenancy, python, security, dns, slugs]
sources: [backend/app/tenancy/slugs.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/tenancy/slugs.py
blob: 8b354e970fb13e63ca54ebbf6f18f69c1b63849d
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/tenancy/slugs.py

**Role.** Pulls the leftmost DNS label out of a `Host` header against the configured base domain, and decides whether that label is a legal, non-reserved boutique slug — the only place tenant identity is derived from anything the client sends.

**Module.** [[backend/app/tenancy/_index]] · **Layer.** tenancy

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `RESERVED_SLUGS` | frozenset | 12 subdomains no boutique may take: `admin`, `api`, `app`, `assets`, `cdn`, `docs`, `mail`, `staging`, `static`, `status`, `support`, `www` |
| `is_valid_slug` | fn | LDH label (1–63 chars, no leading/trailing hyphen) **and** not reserved |
| `extract_slug` | fn | `<label>.<base_domain>` → `label`, else `None` |
| `_SLUG_RE` | const | `^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$` — lowercase only, so an uppercase slug is invalid, not normalised |

## Behavior

`extract_slug` fails closed on every ambiguity and returns `None` rather than raising, so its caller has exactly one rejection path. Three guards run before any parsing: a missing header, a `]` anywhere in the host (an IPv6 literal, whose brackets would otherwise survive the `rsplit(":", 1)` port strip and produce a nonsense label), and any non-ASCII byte. The ASCII check is the security-interesting one — it rejects IDN and homograph hosts outright, and it blocks Unicode case-folding surprises such as `"U+212A KELVIN SIGN".lower() == "k"`, which could otherwise fold a foreign host into a legitimate slug. After stripping an optional port, lowercasing and dropping a trailing root dot, the host must end in `"." + base_domain`; the remainder must be non-empty and must contain no further dot, so the apex domain, a deeper nesting like `a.b.example.com`, and any foreign domain all return `None`. `is_valid_slug` is applied *after* extraction by [[backend/app/tenancy/middleware.py]], which is what makes a reserved slug 404 without ever touching the database.

The same `is_valid_slug` is called at creation time by [[backend/app/platform/service.py]], so reservation is enforced on both ends — a slug the request path would refuse can never be provisioned in the first place. The 63-character ceiling and the LDH shape come from DNS label rules, not from taste: a slug that cannot be a DNS label cannot ever be reached.

## Depends On

- Standard library `re` only.

## Depended On By

- [[backend/app/tenancy/middleware.py]] — `extract_slug` then `is_valid_slug` on every non-exempt request
- [[backend/app/platform/service.py]] — `is_valid_slug` guards `provision`
- [[backend/tests/test_slugs.py]]

## Concepts

- [[Tenant Resolution]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_slugs.py]] — `TestIsValidSlug` and `TestExtractSlug`
- [[backend/tests/test_middleware.py]] — `test_reserved_slug_never_reaches_resolver`, `test_apex_and_foreign_hosts_are_404_without_resolver_call`, `test_host_header_with_port_and_case_resolves`
- [[backend/tests/test_tenancy_integration.py]] — `test_reserved_slug_is_404_even_with_a_row` (a row can exist and still be unreachable)

## Notes

`base_domain` defaults to `localtest.me` in [[backend/app/core/config.py]] — its wildcard subdomains resolve to 127.0.0.1, so `{slug}.localtest.me` works locally with no `/etc/hosts` edit. A boot validator refuses to start a non-dev deployment that left it at that value, because no real host ends in `.localtest.me` and `extract_slug` would return `None` for every request.
