# Plan: Feature 28 — Date-bound dress reservation semantics (Epic E5)

**Spec**: `.planning/specs/dress-reservation.md` (2026-08-06, Gate 1 standing-approved, D1–D8)
**Design**: `.planning/design/screens/dress-reservation/design.md` (§0–§11; P1/P2/P3 proposed; F-R1/F-R2/F-R3 binding on the build)
**Plan written**: 2026-08-06. **Observed alembic head at plan time: `0025` (`0025_walk_in_bookings.py`). F22 holds `0026` in a live worktree and F24/F25 plans are queued ahead — this plan's number WILL shift.** The migration is numbered **head+1 as observed in the F28 worktree at build time**, re-resolved at rebase per §5.
**Depends on**: F8 (dresses/variants, the manual `reserved` flag), F13 (booking claim + advisory lock) — merged.
**Worktree**: `.worktrees/dress-reservation`, branched from `origin/main`.

---

## 0. How to read this plan

Every task is one TDD cycle: the named failing test first, then the code that makes it pass. Migration → overlap core (edge cases first) → API → claim check → storefront projection → manage UI → storefront UI + i18n → e2e. Spec D1–D8 and design §0–§11 are binding and not restated; this plan maps them to files, tests, commits. Every path was verified against the tree on 2026-08-06.

## 1. Verified facts the tasks lean on

| Claim | Verified at |
|---|---|
| Head is 0025; tenant-table template with `_STANDARD` + pointer precedent | `Backend/migrations/versions/0020_alteration_tickets.py` |
| `dresses.reserved` boolean, server_default false; "supersedes" comment to reword (D5) | `Backend/app/models/dress.py:29-30` |
| Claim lock `pg_advisory_xact_lock(hashtext(tenant_id))` — the key reservation-create must reuse | `Backend/app/booking/service.py:388` |
| `SLOT_UNAVAILABLE` raised in the claim; `DRESS_UNAVAILABLE` sits beside it | `Backend/app/booking/service.py:137` |
| `BOUTIQUE_TIMEZONE = ZoneInfo("Asia/Jerusalem")` | `Backend/app/storefront/validation.py:40` |
| `AuditAction` StrEnum (plain TEXT column — new members need no migration) | `Backend/app/models/constants.py:281` |
| Catalog audit-in-transaction pattern (`DRESS_CREATED` etc.) | `Backend/app/catalog/service.py:367-619` |
| Catalog router: `/manage` REST-ish path params, `require_role(OWNER, SHIFT_MANAGER)` router-wide | `Backend/app/catalog/router.py:181-318` |
| `public_dress` (card, untouched) / `public_dress_detail` (widens) | `Backend/app/storefront/router.py:155,165` |
| Repos dir: `dress_reservations.py` name is free | `Backend/app/db/repositories/` |
| Notes bound precedent `MAX_BOOKING_NOTES_LENGTH = 500` | `Backend/app/booking/validation.py:45` |
| Catalog validation constants module to extend | `Backend/app/catalog/validation.py:28-46` |
| `DateField` = native `<input type="date">` over shared `Input` — use it, invent nothing | `Frontend/packages/ui/src/components/DateTimeFields.tsx:10` |
| `DressEditor` composes `VariantMatrix` (:15, :366) + `MediaGallery` — pane contract to copy; panes have per-component test files (`VariantMatrix.test.tsx`, `MediaGallery.test.tsx`; no `DressEditor.test.tsx`) | `Frontend/apps/manage/src/components/`, `__tests__/` |
| Customer picker query exists: `listCustomers` | `Frontend/apps/manage/src/api.ts:1648` |
| DressPage reserved badge + `dress.*` i18n block exist; CTA-stays-usable test pinned | `Frontend/apps/storefront/src/routes/DressPage.tsx:195`, `__tests__/DressPage.test.tsx` |
| `errorMessageKey` house switch (P1: key is `errors.dressUnavailable`) | `Frontend/apps/storefront/src/routes/BookPage.tsx:843` |
| e2e: per-feature spec file pattern (`walk-in.spec.ts`), `fixtures/manage.ts` helpers, `storefront.spec.ts` route-map interception | `Frontend/e2e/` |
| Migration head test to keep green | `Backend/tests/test_migrations.py:58` |

## 2. Migration `NNNN_dress_reservations.py` (NNNN = head+1 at build time)

Raw SQL, `0020`'s template: `dress_reservations` per spec D2 verbatim — `_STANDARD` columns, `dress_id UUID NOT NULL` (no FK), `starts_on DATE NOT NULL`, `ends_on DATE NOT NULL` (inclusive), `customer_id UUID` (pointer, D7), `notes TEXT`, `CHECK (ends_on >= starts_on)`, `CHECK (ends_on - starts_on <= 3650)`; partial index `idx_dress_reservations_dress (tenant_id, dress_id, ends_on) WHERE deleted_at IS NULL` with a rationale comment; `update_updated_at` trigger, house grants, `enable_tenant_rls("dress_reservations")`. **No EXCLUDE/btree_gist** (D3). No data migration for `reserved` rows (D5). Downgrade drops the table, nothing else.

## 3. Ordered task list

### Phase A — migration (commit 1)

| # | Task | Test first | Files (C=create, M=modify) |
|---|---|---|---|
| A1 | Migration per §2. | `test_migrations.py::test_migration_NNNN_creates_dress_reservations` (**db**) — table, both CHECKs, partial index pinned via `pg_indexes.indexdef`; `::test_migration_NNNN_round_trips`; `test_every_tenant_id_table_has_forced_rls` and `test_exactly_one_migration_head` stay green **unedited** | C `Backend/migrations/versions/NNNN_dress_reservations.py`, M `Backend/tests/test_migrations.py` |

### Phase B — model, validation, overlap core (commit 2)

| # | Task | Test first | Files |
|---|---|---|---|
| B1 | Validation (spec D3): `MAX_RESERVATION_SPAN_DAYS = 365`, `MAX_RESERVATION_NOTES_LENGTH = 500`, pure validators — `ends_on >= starts_on`, span ceiling, notes bound. | `test_catalog_validation.py` (fast) — inverted range, 366-day span, 365 ok, notes at/over bound, single-day range legal | M `Backend/app/catalog/validation.py`, M `Backend/tests/test_catalog_validation.py` |
| B2 | `DressReservation` model + repository: `insert`, `live_by_dress(tenant_id, dress_id)` (newest `starts_on` first), `overlapping(dress_id, starts_on, ends_on)` (D3 predicate `a1 <= b2 AND b1 <= a2`, live rows), `containing(dress_id, date)`, `soft_delete(id)`, `current_or_future_by_dress(dress_id, today)` ascending. Reword `dress.py:29` "supersedes" → "narrows" (D5). | `test_catalog_reservations_db.py` (**db**, new) — insert round-trip; **overlap edges first: adjacent (ends 18 / starts 19) NOT overlapping, same-day touch (18/18) overlapping**, contained, spanning, identical, disjoint; soft-deleted rows invisible to both queries; **RLS isolation: tenant A cannot read B's rows** (house suite pattern) | C `Backend/app/models/dress_reservation.py`, C `Backend/app/db/repositories/dress_reservations.py`, M `Backend/app/models/dress.py`, C `Backend/tests/test_catalog_reservations_db.py` |
| B3 | `CatalogService` methods beside the variant/media families: `create_reservation` — **`pg_advisory_xact_lock(hashtext(tenant_id))`, the F13 key** (D3), then validators, dress must be live (404 archived/unknown), `customer_id` when given must resolve live+non-erased (404, walk-in D3d rule), overlap SELECT → `409 RESERVATION_OVERLAP` with conflicting range in `details`, insert + `AuditAction.DRESS_RESERVATION_CREATED`; `list_reservations` (rows + resolved `customer_name`); `delete_reservation` — soft delete + `DRESS_RESERVATION_DELETED`. Audit `details`: range + ids, **never name/phone**. | `test_catalog_reservations_db.py` (**db**) — create→list→delete lifecycle + audit rows (assert no name/phone in details); overlap 409 carries the range; erased/unknown customer 404; **concurrency proof (NullPool + `asyncio.gather`, F13 precedent): two overlapping creates → exactly one 201, one `RESERVATION_OVERLAP`** | M `Backend/app/catalog/service.py`, M `Backend/app/models/constants.py`, M `Backend/tests/test_catalog_reservations_db.py` |

### Phase C — manage API (commit 3)

| # | Task | Test first | Files |
|---|---|---|---|
| C1 | Three endpoints on the catalog router (inherit role gate + `_no_store`): `GET /dresses/{dress_id}/reservations` → `{id, starts_on, ends_on, customer_id, customer_name, notes, created_at}`; `POST` `{starts_on, ends_on, customer_id?, notes?}` → 201 / 409 / 404; `DELETE /dresses/{dress_id}/reservations/{reservation_id}` → 204. Schemas in `catalog/schemas.py`. | `test_catalog_api.py` (fast) — auth matrix (401 anon, role gate) on all three; `test_catalog_reservations_db.py` (**db**) — archived dress 404 on all three; 409 body shape; delete frees the window (re-create same range 201) | M `Backend/app/catalog/router.py`, M `Backend/app/catalog/schemas.py`, M both test files |

### Phase D — booking-claim check (commit 4)

| # | Task | Test first | Files |
|---|---|---|---|
| D1 | Inside `create_booking`'s **already-locked** section, item path only (spec D4): one `containing` query on `starts_at.astimezone(BOUTIQUE_TIMEZONE).date()` → `409 DRESS_UNAVAILABLE`. Deposit path inherits by riding the claim. Slot engine, grid, walk-ins, owner paths: **zero lines**. | `test_booking_service.py` / db suite (**db**) — claim inside window 409, outside 201; **window edges inclusive both ends**; **Jerusalem-vs-UTC boundary: a 22:00 UTC booking is the next local day — must refuse against the local date**; non-item claim same instant 201; deposit-path claim refused; soft-deleted reservation frees the claim; **concurrency: reservation-create vs item-claim for the same dress-date via `asyncio.gather` → never both succeed** | M `Backend/app/booking/service.py`, M `Backend/tests/test_booking_service.py` |

### Phase E — storefront projection (commit 5)

| # | Task | Test first | Files |
|---|---|---|---|
| E1 | `StorefrontDetail` gains `unavailable_ranges: [{starts_on, ends_on}]` — live rows `ends_on >= today` (boutique-local), ascending (spec D6). `public_dress` card shape byte-identical. | `test_storefront_service.py` (**db**) — past rows excluded, current row with `ends_on == today` included, ascending order; dress with none → `[]`; card/list endpoints unchanged (existing suites green unedited) | M `Backend/app/storefront/service.py`, M `Backend/app/storefront/schemas.py`, M `Backend/app/storefront/router.py`, M `Backend/tests/test_storefront_service.py` |

### Phase F — manage UI (commit 6)

| # | Task | Test first | Files |
|---|---|---|---|
| F1 | `api.ts`: `listDressReservations`, `createDressReservation`, `deleteDressReservation` + types; `RESERVATION_OVERLAP` in the error mapping. | `api.test.ts` additions — methods hit the three paths, 409 details surfaced | M `Frontend/apps/manage/src/api.ts`, M its test |
| F2 | `ReservationsPane` per design §1 (pane contract = `VariantMatrix`: `dressId` null → disabled Card + C-M1 hint; archived → disabled): wedding-date `DateField` prefills `starts_on = d`, `ends_on = d + RESERVATION_BUFFER_DAYS` (**FE constant, 5**; date-parts arithmetic, never ms), both fields then free and never re-clobbered once touched; customer picker reusing `listCustomers` (§1.1, ghost md rows); notes `TextArea` maxLength 500; overlap 409 → C-M8 `role="alert"` line, values kept; delete via `Modal` (C-M13) with **post-delete focus to the pane's `role="status" tabIndex={-1}` list region** (design §8 — new here, not MediaGallery's); add success = C-M12 status, focus stays (P3). All buttons **md** (F-W1). Copy: inline Hebrew C-M1–C-M16, no exclamation marks. Reword `CREATE_HINT` + `reserved` checkbox helper (C-M1/C-M15, D5) and **update the pinned old-literal assertions the F-R1 grep finds** («יש לשמור את השמלה לפני», «סימון ידני, ללא תאריך»). Mount in `DressEditor` after `MediaGallery`. | `ReservationsPane.test.tsx` (new) — **buffer prefill arithmetic (`+5`) first**, incl. month/year rollover; touched-fields never re-clobbered; disabled create/archived states; overlap render keeps values; delete confirm flow (focus assertions live in e2e, `.memory/jsdom-has-no-dialog`); `VariantMatrix.test.tsx`/`MediaGallery.test.tsx`/`CatalogSection.test.tsx` green after the hint rewording | C `Frontend/apps/manage/src/components/ReservationsPane.tsx`, M `Frontend/apps/manage/src/components/DressEditor.tsx`, C `Frontend/apps/manage/src/__tests__/ReservationsPane.test.tsx`, M sibling tests the F-R1 grep flags |

### Phase G — storefront UI + i18n (commit 7)

| # | Task | Test first | Files |
|---|---|---|---|
| G1 | Range formatter helper per design §5: `Intl.DateTimeFormat('he-IL', {day, month: 'long'})` **with `timeZone: "UTC"`** on date-only strings (F-R2), year only when ≠ current, en-dash, `<bdi dir="ltr">` islands (same-month single island; cross-month/year split). `api.ts`: `unavailable_ranges` on `StorefrontDetail`, `DRESS_UNAVAILABLE` → `errors.dressUnavailable` in `errorMessageKey` (P1). | formatter unit test — same-month, cross-month, cross-year, **pins the `timeZone: "UTC"` call, not just output**; `api.test.ts` — key mapping | C `Frontend/apps/storefront/src/lib/dateRange.ts` (or house `lib` sibling), M `Frontend/apps/storefront/src/api.ts`, C/M tests |
| G2 | `DressPage`: D6/design §2 block between sizes and CTA, only when ranges non-empty — heading `dress.reservedDatesHeading`, one line per range, note `dress.reservedDatesNote`; no live region, no warning tone. `BookPage`: `errors.dressUnavailable` renders at the claim-failure line. i18n: two `dress.*` keys + `errors.dressUnavailable` in `he.ts`, **`ar.ts` mirrors (Hebrew values) in the same commit** (F-R3). Zero exclamation marks. | `DressPage.test.tsx` — block absent when `[]`, renders ranges + note when present, **shipped CTA-stays-usable reserved-dress test green unedited**; `BookPage.test.tsx` — 409 code → copy; `i18n-keys` floor test binds the new keys in both files | M `Frontend/apps/storefront/src/routes/DressPage.tsx`, M `…/routes/BookPage.tsx`, M `…/i18n/he.ts`, M `…/i18n/ar.ts`, M three test files |

### Phase H — e2e (commit 8)

| # | Task | Test first | Files |
|---|---|---|---|
| H1 | `dress-reservation.spec.ts` (per-feature file, `walk-in.spec.ts` pattern) using the `fixtures/manage.ts` helpers + its own route map: manage — open a dress, add a reservation via the date inputs (prefill visible), row appears, overlapping add shows the inline conflict with the range, delete via modal clears it and focus lands on the list region; storefront (`storefront.spec.ts` route-map style, dress-detail stub widened with `unavailable_ranges`) — range block + fittings note render RTL (`<bdi>`), CTA still opens booking, BookPage `DRESS_UNAVAILABLE` shows the copy. **axe zero-violation**: pane create-disabled, loaded, overlap-error, modal-open; dress page with ranges; BookPage error state (design §8). Fixtures: stubs for the three manage endpoints + a dress with past/current/future ranges. | this IS the test | C `Frontend/e2e/dress-reservation.spec.ts`, M `Frontend/e2e/fixtures/manage.ts` (reservation builders), M `Frontend/e2e/storefront.spec.ts` fixtures only if the shared stub is imported |

## 4. Build environment — RECORD, these are facts not suggestions

- **No Docker locally.** Tests marked `db` or `s3` run **on CI only**. Do not chase local db-test failures.
- **The local fast lane (`-m 'not db'`) points at a CLOSED Postgres port by design (F21).** A test dialing a real DB without the `db` marker fails locally — that is correct behavior, not a bug. Every new db-touching test MUST carry the `db` marker.
- **The worktree has no `Backend/.env`.** Config-default tests behave differently than the main checkout (`.memory/local-env-breaks-config-tests` — there the failure is REAL if it appears).
- **Local gates, all must pass before push**: `make lint` · backend non-db tests (`make test`) · `make fe-test` · `make fe-build` · `make e2e`.
- Write db-marked tests carefully against the spec's test plan; their first run is CI (`.memory/boutique-ci-first-run-surprises`).

## 5. Build discipline

**Commit boundaries** (conventional, scoped):
1. `feat(catalog): dress_reservations migration` — A1.
2. `feat(catalog): reservation model, overlap core under the tenant lock` — B1–B3.
3. `feat(catalog): reservation CRUD endpoints` — C1.
4. `feat(booking): refuse item claims inside a reservation window` — D1.
5. `feat(storefront): unavailable_ranges on the dress detail` — E1.
6. `feat(manage): ReservationsPane in the dress editor` — F1–F2.
7. `feat(storefront): reserved-dates block, DRESS_UNAVAILABLE copy, i18n he+ar` — G1–G2.
8. `test(e2e): dress-reservation journeys with axe` — H1.

**Migration renumber protocol**: built at observed-head+1 in the worktree. **F22 holds `0026` and F24/F25 are queued ahead — assume the number shifts.** Immediately before the pre-push rebase, re-run `alembic heads` against rebased main; if a sibling took the number, renumber (filename + `revision` + `down_revision`) in one `fix(catalog):` commit, then re-run the head test. A reserved-but-wrong number breaks alembic outright and reds every db test (`.memory/parallel-alembic-numbering`).

**Pathspec**: git tracks `backend/`/`frontend/` **lowercase**. `git add Backend/…` silently skips modified tracked files — lowercase every pathspec, verify with `git show --stat` (`.memory/git-add-uppercase-pathspec-trap`).

**Frontend build check**: `pnpm build` before staging any `.ts`/`.tsx`.

**After any merge-conflict resolution**: parse every touched test file's collection count — a broken file reads as one `Tests no tests` line (`.memory/silently-unexecuted-test-files`).

## 6. Risks this plan adds to the spec's list

- **R-A**: D1's local-date comparison is the trap that passes every test written in UTC+2/+3 — the 22:00 UTC boundary test in D1 is the tripwire; it must exist before the check compiles green.
- **R-B**: reservation-create must take the F13 lock **key**, not merely *a* lock — B3's gather test plus D1's create-vs-claim race are the proof; if either is flaky on CI, fix the lock, not the test.
- **R-C**: F2 rewords two shipped strings — run the F-R1 grep across manage unit AND e2e suites before commit 6, or pinned copy assertions red on CI only.
- **R-D**: F24/F25 land ahead in the same files' neighborhoods (`he.ts`/`ar.ts`, `api.ts`, migrations) — expect merge conflicts at rebase; re-run the collection-count check and `alembic heads` after resolving.
