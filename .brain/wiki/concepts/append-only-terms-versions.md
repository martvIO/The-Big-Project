---
tags: [backend, db, boutique, booking, compliance, postgres]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Append Only Terms Versions

**What it is.** `terms_versions` holds one immutable row per publication of a boutique's
cancellation policy, numbered `1, 2, 3…` per tenant. A boutique never *edits* its terms — it
publishes a new version, and every prior version stays readable forever.

## Append-only is structural, not conventional

[[backend/migrations/versions/0005_boutique_settings.py]] does the same `REVOKE`-then-`GRANT`
dance as [[Platform Audit Log]], and for the same reason —
[[backend/migrations/versions/0002_tenants_app_role.py]]'s `ALTER DEFAULT PRIVILEGES` auto-grants
full CRUD to `app_user` on every later table:

```sql
REVOKE ALL ON terms_versions FROM app_user;
GRANT SELECT, INSERT ON terms_versions TO app_user;
```

`SELECT` **stays granted** here, unlike `platform_audit_log` — which is why this table's
`INSERT … RETURNING` works and its repository needs no client-side id or timestamp. There is also
no `updated_at` trigger on the table: rows are evidence, never updated.

[[backend/app/db/repositories/terms.py]] mirrors the grant exactly — no update method, no delete
method, and none could run if one existed. Its `deleted_at IS NULL` predicates are pure house-style
uniformity; the column is structurally always NULL.

The unique index `idx_terms_versions_tenant_version_unique` is **plain, not partial** (see
[[Partial Unique Index]]) precisely because nothing is ever deleted here — and it doubles as the
concurrency backstop for `version = max + 1`.

## Why this exists: a booking freezes the version it accepted

`bookings.terms_version_accepted` and `terms_accepted_at` are snapshotted at claim time by
[[backend/app/booking/service.py]], which refuses the claim with `TermsStaleError` if the submitted
version is not the current one — accepting a superseded policy is not acceptance.

The payoff is in `TermsVersionsRepository.by_version`, whose docstring is the sharpest statement of
the rule: **`current()` must not be substituted here.** The manage page computes a customer's
cancellation consequence from the version *she* accepted; reading the current one instead means a
boutique that republishes its policy silently rewrites the terms of appointments already agreed to.

## The version race, and why it retries exactly once

`create_terms_version` in [[backend/app/boutique/service.py]] takes no [[Advisory Lock]]. It reads
`max_version() + 1` and inserts; on `IntegrityError` it recomputes in a **fresh** `tenant_session`
and retries once, then gives up with `TermsVersionConflictError`. The fresh session is the point —
a failed flush aborts the Postgres transaction, so the same session cannot be reused for the retry.

Every *successful* creation is recorded against the throttle
(`terms_creation_max_per_window`, [[backend/app/core/config.py]]) rather than every failure,
because rows on an append-only path are permanent and spam here is permanent bloat. See
[[Rate Limiting]] — this is the precedent [[backend/app/catalog/service.py]]'s presign throttle cites.

## Related

- [[Platform Audit Log]] · [[Partial Unique Index]] · [[Rate Limiting]] · [[Least Privilege Database Role]]
- Model: [[backend/app/models/terms_version.py]] · Tests: [[backend/tests/test_boutique_service.py]]
