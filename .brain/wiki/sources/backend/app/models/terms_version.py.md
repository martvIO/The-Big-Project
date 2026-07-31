---
tags: [backend, models, python, boutique, terms, append-only, sqlalchemy]
sources: [backend/app/models/terms_version.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/terms_version.py
blob: ff9ee102f4eff05d7d46db18964969332c3bf08d
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/terms_version.py

**Role.** One immutable snapshot of a boutique's cancellation policy — the text plus the two numbers the refund math needs — versioned per tenant so the terms a customer accepted at booking time stay reconstructable after the boutique republishes.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TermsVersion` | class | ORM mapping for `terms_versions`; `StandardColumns` + `Base` |
| `tenant_id` | col | `UUID NOT NULL` — RLS discriminator |
| `version` | col | `INTEGER NOT NULL`, DB `CHECK (version > 0)`; unique per tenant |
| `terms_text` | col | `TEXT NOT NULL` — the Hebrew policy body shown at booking |
| `refundable_until_hours_before` | col | `INTEGER NOT NULL`, `CHECK (>= 0)` — the refund window |
| `forfeit_percent` | col | `INTEGER NOT NULL DEFAULT 100`, `CHECK (BETWEEN 0 AND 100)` — share of deposit lost outside the window; E4 evaluates it |
| `created_by` | col | `UUID NOT NULL` — the staff user who published the version |

## Behavior

Append-only here is **structural, not conventional**. [[backend/migrations/versions/0005_boutique_settings.py]] revokes everything from `app_user` and re-grants `SELECT, INSERT` only, so no code path — not a bug, not a future migration written against the app role — can `UPDATE` or `DELETE` a published version. `SELECT` is kept (unlike [[backend/app/models/platform_audit_log.py]]) so ordinary reads and `INSERT … RETURNING` both work. `StandardColumns` is inherited for uniformity, which means `updated_at` and `deleted_at` exist but are structurally always `NULL`; 0005 also skips the `update_updated_at` trigger for this table alone.

The unique index on `(tenant_id, version)` is **plain, not partial** — the only such index in the schema — precisely because nothing is ever deleted here, and it doubles as the concurrency backstop for the `version = max(version) + 1` allocation in [[backend/app/db/repositories/terms.py]]: two owners publishing at once do not both get version 4, the loser's `flush()` raises `IntegrityError`. Current policy is defined as `max(version)` per tenant, not by a flag column, so there is no "which row is current" state to get out of sync.

The read distinction that matters for correctness: `TermsVersionsRepository.by_version` must not be replaced by `current()`. F16's manage page computes a customer's cancellation consequence from the version recorded in `bookings.terms_version_accepted`; reading the current one instead would let a boutique silently rewrite the terms of appointments already agreed to — which is the exact bug that column exists to prevent. Creation is additionally throttled per tenant (`terms_creation_*` in [[backend/app/core/config.py]]) because spam on an append-only table is permanent bloat.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[SQLAlchemy]] — declarative mapping

## Depended On By

- [[backend/app/db/repositories/terms.py]] — `max_version`, `insert`, `current`, `by_version`
- [[backend/app/boutique/service.py]] — publishing a new version (owner-only route)
- [[backend/app/storefront/service.py]] and [[backend/app/storefront/router.py]] — surface the current terms to the booking page
- [[backend/app/booking/service.py]] — stamps the accepted version onto the booking
- [[backend/app/booking/manage.py]] — reads the *accepted* version for the cancellation consequence

## Concepts

- [[Row Level Security]]
- [[Least Privilege Database Role]]
- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_boutique_models.py]] — schema-shape assertions (standard columns, nullability), no database
- [[backend/tests/test_boutique_service.py]] — version allocation and throttling
- [[backend/tests/test_boutique_api.py]], [[backend/tests/test_storefront_api.py]] — publish and read paths
- [[backend/tests/test_role_guard.py]] — publishing is owner-only

## Notes

`forfeit_percent` is already *displayed* — [[backend/app/storefront/router.py]] shows it on the booking page and [[backend/app/booking/manage.py]] shows the accepted version's value on the manage page — but nothing *computes* a refund from it yet; that is E4's job. The two DB `CHECK`s on the refund bounds duplicate the validation in [[backend/app/boutique/validation.py]] on purpose: on immutable financial evidence the bound has to survive any non-router write path.

Design context: [[.planning/specs/owner-settings.md]], [[.planning/plans/owner-settings.md]].
