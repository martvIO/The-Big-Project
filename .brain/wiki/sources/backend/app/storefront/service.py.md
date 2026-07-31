---
tags: [backend, storefront, python, public-api, catalog, booking, slots, media]
sources: [backend/app/storefront/service.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storefront/service.py
blob: 1f23e60e08e4c155ec9df8db383bafa83c8b858d
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/storefront/service.py

**Role.** All read logic behind the anonymous storefront — dress list, dress detail, bookable slot grid, appointment types, current terms and the boutique/about payload — assembled from repositories directly rather than through `CatalogService`, so that boutique-confidential data is *structurally unreachable* on the public path rather than merely omitted from a response model.

**Module.** [[backend/app/storefront/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `StorefrontService` | class | Holds the session factory, a [[backend/app/storage/base.py]] `MediaStorage`, an optional injectable `Clock`, and eight repository handles |
| `.list_dresses` | method | Three statements: page, count, covers. `offset`/`limit` clamped |
| `.get_dress` | method | Three statements: dress, active variants, ready media |
| `.list_slots` | method | Three statements (rules, exceptions, booked counts) + the pure slot engine |
| `.list_appointment_types` | method | One statement, active types only |
| `.get_terms` | method | One statement; a boutique with no published policy is a 404 |
| `.get_boutique` | method | Two statements; `name`/`settings` come from the already-resolved tenant |
| `slot_window` | fn | Pure — resolves and clamps a requested date window into the publishable band |
| `upcoming_exceptions` | fn | Pure — today-onward, capped at `UPCOMING_EXCEPTIONS_LIMIT` |
| `StorefrontDressView` · `StorefrontDressListView` · `StorefrontSizeView` · `StorefrontDressDetailView` · `StorefrontBoutiqueView` | dataclass | Frozen view types carrying exactly what the public wire needs |
| `MAX_LIST_OFFSET` | const | `1_000_000` |

## Behavior

**Why this module exists rather than a call into `CatalogService`.** The shorter path is the wrong one: `CatalogService.list_dresses` calls `DressVariantsRepository.aggregate_by_dress` to compute `out_of_stock`, `total_quantity` and `variant_count`. Routing the public list through it would recompute the boutique's raw stock position on every anonymous request and keep it off the wire only by the response model remembering to omit it. Here `aggregate_by_dress` is never called at all — one statement less per page, and the leak is unreachable rather than absent. `count_active` is skipped for the same reason, and `StorefrontSizeView` folds `quantity` to a boolean `available` at the one place the count is read.

**Every read is inside `tenant_session`**, so RLS plus the repositories' explicit `tenant_id` predicate scope it twice. Media signing runs *outside* the session — `sign_media` is local HMAC, never a storage network call, which keeps the "no `MediaStorage` network method inside a `tenant_session`" invariant intact; the storefront makes no storage network call at all.

**Archived rows are 404s, not filtered rows.** `get_dress` calls `by_id`, which pins `deleted_at IS NULL`, and raises `CatalogNotFoundError` on a miss — an archived dress is indistinguishable from a nonexistent one, which is exactly the intended "השמלה כבר לא זמינה" state. `by_id_any_state` must never appear in this module and `test_storefront_module_never_references_by_id_any_state` greps the source for the symbol.

**Unbounded caller values are clamped, not validated.** `MAX_LIST_OFFSET` exists because Python ints are unbounded and `offset` reaches the driver as `OFFSET $n::BIGINT`: without a ceiling, `?offset=2**63` dies in asyncpg's encoder as a 500 with no handler above it rather than as a 400. `slot_window` clamps for the same class of reason and is the subtler one — both bounds are clamped against **`today`**, never against the caller's own value, because `date + timedelta` raises `OverflowError` within 60 days of `date.max` and `?from=9999-12-31` is among the first things anyone probes on a public endpoint. `to < from` (compared against what the caller *asked for*, before the floor clamp moves) is the one caller error that raises `SlotWindowError` → a house-shape 400; a `to` beyond the ceiling is silently clamped, since a picker asking for more than it can render is a UI bug rather than a user error. A wholly-past window comes back inverted and materializes to no slots — the same empty answer, without a second rule that could disagree with the engine's own "drop everything at or before now".

**`list_slots` converts calendar dates to instants at its own boundary.** The engine keys `booked` by UTC start instant while the window is boutique *calendar* dates, so the window edges become boutique-midnight instants via `BOUTIQUE_TIMEZONE`, with the right edge half-open (start of the day *after* `window_end`). The exception query is bounded on **both** sides in SQL — the window bounds the response either way, but an unbounded upper predicate would still scan every future exception the boutique ever recorded, on every anonymous request. Full slots are **dropped** by the engine rather than marked, so the response discloses nothing about booking density.

**`list_appointment_types` applies no audience filter.** `brides_only` marks a type for brides and an anonymous visitor cannot be classified as one, so a server-side filter here would be theatre; the field ships so the UI can label the option, and real enforcement waits on a client identity.

## Depends On

- [[backend/app/db/tenant.py]] — `tenant_session`, on every read
- [[backend/app/storefront/validation.py]] — bounds, `BOUTIQUE_TIMEZONE`, `Clock`, `today_jerusalem`, `SlotWindowError`
- [[backend/app/catalog/service.py]] — `CatalogNotFoundError`, `MediaView`, `sign_media` (types and local signing only; no service call)
- [[backend/app/booking/slots.py]] — `Slot`, `materialize_slots`, the pure grid engine
- [[backend/app/booking/validation.py]] — `SLOT_WINDOW_DEFAULT_DAYS`, `SLOT_WINDOW_MAX_DAYS`
- [[backend/app/db/repositories/dresses.py]] · [[backend/app/db/repositories/dress_variants.py]] · [[backend/app/db/repositories/dress_media.py]] · [[backend/app/db/repositories/availability.py]] · [[backend/app/db/repositories/appointment_types.py]] · [[backend/app/db/repositories/bookings.py]] · [[backend/app/db/repositories/terms.py]]
- [[backend/app/storage/base.py]] — the `MediaStorage` port
- [[SQLAlchemy]]

## Depended On By

- [[backend/app/main.py]] — constructs it into `app.state.storefront_service`
- [[backend/app/storefront/router.py]] — the `Storefront` dependency
- [[backend/app/booking/owner.py]] — reuses `list_slots` so the owner grid is the same computation plus an owner projection

## Concepts

- [[Row Level Security]]
- [[Tenant Context]]
- [[Rate Limiting]]

## Tests

- [[backend/tests/test_storefront_api.py]] — router-level, against a duck-typed fake plus real-service cases
- [[backend/tests/test_storefront_integration.py]] — the load-bearing **statement-count** pair, which is what pins "the public list never buys the aggregate"
- [[backend/tests/test_storefront_isolation.py]] — drives the service and every repository handle it holds as tenant B against tenant A's rows
- [[backend/tests/test_storefront_validation.py]] — `slot_window` clamping, including `date.max`/`date.min` and the inverted-window 400
- [[backend/tests/test_slot_engine.py]] — the pure engine underneath `list_slots`

## Notes

`get_boutique` takes `name` and `settings` as parameters rather than re-reading the tenant row: `RepositoryTenantResolver` already SELECTed the whole `tenants` row to route the request, so a second read would buy nothing. [[backend/app/booking/manage.py]] follows the same pattern.

`upcoming_exceptions` duplicates, as a pure function, the cutoff the SQL `on_or_after` filter already applies — deliberately, so the truncation rule is unit-testable with no I/O and so a caller holding a pre-fetched list applies the identical rule.

Design context: [[.planning/specs/storefront-browse.md]], [[.planning/specs/availability-slot-engine.md]], [[.planning/specs/storefront-booking-ui.md]].
