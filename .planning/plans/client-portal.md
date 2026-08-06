# Plan: Feature 24 — Client portal: OTP login, "My Bookings", `.ics`, bell (Epic E5)

**Spec**: `.planning/specs/client-portal.md` (2026-08-06, Gate 1 standing-approved, D1–D8)
**Design**: `.planning/design/screens/client-portal/design.md` (§1–§14; F-P1/F-P2/F-P3 owed)
**Plan written**: 2026-08-06. **Observed alembic head at plan time: `0025` (`0025_walk_in_bookings.py`). A parallel F22 build holds `0026` in `.worktrees/waitlist-join` — this plan's number WILL shift.** The migration is numbered **head+1 as observed in the F24 worktree at build time** (0026 if F22 has not merged, 0027 if it has), and re-resolved at rebase per §5.
**Depends on**: F11 (OTP endpoints), F13 (booking core, customers), F16 (message_log lifecycle rows, tokenized manage page), F20 (subject erase) — all merged.
**Worktree**: `.worktrees/client-portal`, branched from `origin/main`.

---

## 0. How to read this plan

Every task is one TDD cycle: the named failing test first, then the code that makes it pass. Session/auth backend first, then mirrored actions, then `.ics` and bell, then UI, then e2e — the UI needs settled shapes. The spec's D1–D8 and the design's §1–§14 are binding and not restated; this plan maps them to files, tests, and commits. Every path below was verified against the tree on 2026-08-06.

## 1. Verified facts the tasks lean on

| Claim | Verified at |
|---|---|
| Head migration is 0025; template for a new tenant table is `0018_queue_tickets.py` | `Backend/migrations/versions/` |
| `generate_session_token()` | `Backend/app/auth/tokens.py:7` |
| `SESSION_COOKIE = "boutique_session"` (staff) — customer cookie must be a new name | `Backend/app/auth/cookies.py:3` |
| `get_current_staff` dependency shape to mirror | `Backend/app/auth/dependencies.py:28` |
| `session_ttl_seconds: int = 60*60*12` (staff class; portal gets its own setting) | `Backend/app/core/config.py:24` |
| OTP limiter instances built in `create_app()` — pattern for the one new mint limiter | `Backend/app/main.py:801-826` |
| `POST /storefront/otp/send` (204) / `/otp/verify` | `Backend/app/notifications/router.py:52,64` |
| `consume_verification` (single-use burn) | `Backend/app/notifications/service.py:377` |
| `ManageBookingService.lookup/confirm_attendance/cancel` — token-coupled today, C1 extracts | `Backend/app/booking/manage.py:100-168` |
| `ManageBookingResponse` (the mirror contract) | `Backend/app/booking/schemas.py:126` |
| `erase_subject` (gains session revocation) | `Backend/app/privacy/service.py:344` |
| `appointment_types.duration_minutes` NOT NULL (DTEND arithmetic) | `Backend/app/models/appointment_type.py:19` |
| `message_log.kind/status/booking_id` columns for the bell projection | `Backend/app/models/message_log.py:19-26` |
| Storefront routers mount at `main.py:1490-1494`; `_RESERVED_SEGMENTS = {manage, storefront}` unchanged | `Backend/app/main.py:469,1490` |
| Repos dir has `customers.py`, `sessions.py`, `message_log.py`; `customer_sessions.py` is free | `Backend/app/db/repositories/` |
| Router: `RouteName` union + `DOC_TITLE_KEYS` + unforced switch (`manage` case taken; `portal` free) | `Frontend/apps/storefront/src/router.tsx:27,76,359-379` |
| Storefront `he.ts` has NO `portal.*` block — free to take (804 lines; `ar.ts` mirrors) | grep, `Frontend/apps/storefront/src/i18n/he.ts` |
| `ManageBookingPage.tsx` exists (extraction source); `components/portal/` does not | `Frontend/apps/storefront/src/routes/`, `src/components/` |
| e2e interception style: `page.route("**/storefront/**")` map | `Frontend/e2e/storefront.spec.ts:470` |
| Per-feature e2e spec files are the pattern (`walk-in.spec.ts`); fixtures dir holds `manage.ts` only | `Frontend/e2e/` |
| No `.ics`/VEVENT code anywhere (spec grep confirmed) | spec §exists |

## 2. Migration `NNNN_client_portal.py` (NNNN = head+1 at build time)

Raw SQL, `0018`'s template verbatim: `customer_sessions` with `_STANDARD` columns + `customer_id UUID NOT NULL` (no FK), `token_hash TEXT NOT NULL`, `expires_at TIMESTAMPTZ NOT NULL`; partial indexes `idx_customer_sessions_token (tenant_id, token_hash) WHERE deleted_at IS NULL` and `idx_customer_sessions_customer (tenant_id, customer_id) WHERE deleted_at IS NULL` (rationale comments at the index, 0018's demand); `_updated_at_trigger`, house grants, `enable_tenant_rls("customer_sessions")`. Plus `ALTER TABLE customers ADD COLUMN bell_seen_at TIMESTAMPTZ` (NULL = never opened). Downgrade drops the table and the column, nothing else. No changes to `message_log`, `scheduled_messages`, `bookings` (spec D7).

## 3. Ordered task list

### Phase A — schema, session model, erase ripple (commit 1)

| # | Task | Test first | Files (C=create, M=modify) |
|---|---|---|---|
| A1 | Migration per §2. | `test_migrations.py::test_migration_NNNN_creates_customer_sessions` (**db**) — table + both partial indexes pinned via `pg_indexes.indexdef` + `customers.bell_seen_at` exists nullable; `::test_migration_NNNN_round_trips`; `test_every_tenant_id_table_has_forced_rls` and `test_exactly_one_migration_head` stay green **unedited** | C `Backend/migrations/versions/NNNN_client_portal.py`, M `Backend/tests/test_migrations.py` |
| A2 | `CustomerSession` model + repository: `insert`, `by_token_hash(tenant_id, token_hash)` (live: `deleted_at IS NULL AND expires_at > now()`), `revoke(session_id)` (soft delete), `revoke_all_for_customer(customer_id)`; customers repo gains `set_bell_seen(customer_id, ts)`. | `test_portal_sessions_db.py` (**db**, new) — insert round-trip; lookup misses expired and soft-deleted rows; **RLS isolation: tenant A cannot read B's sessions** (house suite pattern); revoke-all hits only that customer | C `Backend/app/models/customer_session.py`, C `Backend/app/db/repositories/customer_sessions.py`, M `Backend/app/db/repositories/customers.py`, C `Backend/tests/test_portal_sessions_db.py` |
| A3 | Erase integration (spec D2): `erase_subject` soft-deletes all the customer's `customer_sessions` **in the same transaction**. | `test_privacy_subject_requests_db.py` (**db**) — erase leaves zero live sessions; a pre-erase session token no longer authenticates (asserted properly at B2, row-level here) | M `Backend/app/privacy/service.py`, M `Backend/tests/test_privacy_subject_requests_db.py` |

### Phase B — session mint, cookie auth, me/logout (commit 2)

| # | Task | Test first | Files |
|---|---|---|---|
| B1 | Portal module + login service (spec D1): `POST /storefront/portal/session {phone, verification_token}` → new per-tenant `FixedWindowRateLimiter` (own instance, **never a key on an existing budget**) → `consume_verification` (burn) → customer by (tenant, normalized phone) → found: mint token via `generate_session_token`, sha256 store, set cookie, `{customer_name}`; not found (incl. erased-by-construction): `404 {code: PORTAL_NO_BOOKINGS}`. Config: `portal_session_ttl_seconds` (default 30d), `portal_login_max_per_tenant_window`/`portal_login_window_seconds`. Cookie `boutique_customer_session`: host-only, HttpOnly, Secure(prod), SameSite=Lax, path=/ — constant beside `SESSION_COOKIE`. | `test_portal_service.py` (**db**, new) — happy mint (row + cookie attrs + name); unknown phone → `PORTAL_NO_BOOKINGS`; verification token burned single-use (second mint 401 `PHONE_NOT_VERIFIED`); mint limiter 429 **without touching the OTP budgets** (`.memory/limiter-max-is-per-instance`); erased customer can never match | C `Backend/app/portal/__init__.py`, C `Backend/app/portal/schemas.py`, C `Backend/app/portal/service.py`, C `Backend/app/portal/router.py`, M `Backend/app/auth/cookies.py`, M `Backend/app/core/config.py`, M `Backend/app/main.py`, C `Backend/tests/test_portal_service.py` |
| B2 | `get_current_customer` dependency mirroring `get_current_staff` (cookie → sha256 → live row → `CustomerContext(customer_id, name, phone)`; `NotAuthenticatedError` 401 house body). `GET /storefront/portal/me` → `{customer_name}`; `POST /storefront/portal/logout` → revoke + clear cookie. All portal routes `_no_store`. | `test_portal_api.py` (fast, new) — TestClient: me without cookie 401; garbage cookie 401; `test_portal_service.py` (**db**) — mint→me→logout lifecycle; expiry honored; post-erase token 401 (closes A3's loop) | C `Backend/app/portal/dependencies.py`, M `Backend/app/portal/router.py`, C `Backend/tests/test_portal_api.py` |
| B3 | Cross-tenant walker registration: **populate, don't exempt** — mint via the storefront OTP flow under `otp_dev_code` (the waitlist QUEUE_TICKET precedent) so cookie-authed portal routes walk cross-tenant; fallback: exemption with a written reason ("customer-cookie plumbing", not "too hard"). | `test_cross_tenant_walker.py::test_the_walk_and_the_exemptions_are_the_whole_route_table` reds on the new routes until this lands — that red IS the failing test first | M `Backend/tests/test_cross_tenant_walker.py` |

### Phase C — "My Bookings" + mirrored actions (commit 3)

| # | Task | Test first | Files |
|---|---|---|---|
| C1 | **The extraction the spec's D4 owns**: split `ManageBookingService` so token-resolution is separated from the transitions — `lookup/confirm_attendance/cancel` become thin token-resolvers over shared internals (`_load_response(booking)`, `_confirm(booking)`, `_cancel(booking)`) that own the whole guard set (`BookingLinkInvalidError` stays token-side; `BookingAlreadyStartedError`/`BookingCancelledError`/`BookingAwaitingPaymentError` move into the shared core). Pure refactor. | `test_booking_manage_api.py` and the manage service suites stay green **unedited** — that is the refactor's contract; no new test | M `Backend/app/booking/manage.py` |
| C2 | `GET /storefront/portal/bookings` → `{upcoming, past}` rows (`id, starts_at, status, attendance_confirmed_at, appointment_type_name, dress_name, dress_size`; upcoming ASC / past DESC, split on now; `pending_payment` in upcoming). `GET /storefront/portal/booking?id=` → **`ManageBookingResponse` verbatim** via C1's `_load_response`, resolved by (session customer_id, id); unknown or not-hers → house 404. | `test_portal_service.py` (**db**) — list scoped to the session's customer only; split/order; pending_payment placement; detail shape equals the token-page shape for the same booking (field-for-field); cross-customer id 404, not-found 404, indistinguishable bodies | M `Backend/app/portal/service.py`, M `Backend/app/portal/schemas.py`, M `Backend/app/portal/router.py`, M `Backend/tests/test_portal_service.py` |
| C3 | `POST /storefront/portal/booking/confirm-attendance {id}` / `…/cancel {id}` → C1's shared transitions. Same 409 matrix, `cancelled_by='customer'`, seat freed, pending reminder cancelled. Tokenized endpoints untouched. | `test_portal_service.py` (**db**) — portal cancel frees the seat + cancels the reminder row + stamps `cancelled_by='customer'` (**same assertions as the token-page cancel suite**); confirm writes `attendance_confirmed_at`; 409 matrix started/cancelled/awaiting-payment; `test_portal_api.py` — every portal route 401 without cookie (auth matrix complete) | M `Backend/app/portal/router.py`, M `Backend/app/portal/service.py`, M both test files |

### Phase D — `.ics` (commit 4)

| # | Task | Test first | Files |
|---|---|---|---|
| D1 | Pure stdlib builder `build_ics(booking, appointment_type, boutique, slug, base_domain) -> str` per spec D5: one VEVENT, CRLF, 75-octet folding, `UID:{booking_id}@{slug}.{base_domain}`, `DTSTAMP` now-UTC, `DTSTART`/`DTEND` UTC `Z` instants (DTEND = starts_at + `duration_minutes`, read regardless of type `deleted_at`), `SUMMARY`/`LOCATION`/`STATUS:CONFIRMED`, **no token anywhere**. | `test_booking_ics.py` (**non-db**, new) — UTC `Z` formatting; DTEND arithmetic; an IDT (summer) and an IST (winter) booking; CRLF + folding on a long Hebrew SUMMARY; `assert "token" not in` output for a booking whose row carries one | C `Backend/app/booking/ics.py`, C `Backend/tests/test_booking_ics.py` |
| D2 | Two thin routes, one builder: `GET /storefront/portal/booking.ics?id=` (cookie; `Content-Type: text/calendar; charset=utf-8`, `Content-Disposition: attachment; filename="appointment.ics"`) and `POST /storefront/booking/ics {token}` (token in body — F14 D7). Only `confirmed`/`completed` serve; others answer the manage page's transition 409/404. | `test_portal_api.py` + `test_booking_manage_api.py` — content-type + disposition asserted; cancelled → 409; cross-customer → 404; rotated token → `BOOKING_LINK_INVALID`; body identical across both transports for one booking | M `Backend/app/portal/router.py`, M `Backend/app/booking/router.py`, M `Backend/app/booking/manage.py` (thin ics entry), M both test files |

### Phase E — bell backend (commit 5)

| # | Task | Test first | Files |
|---|---|---|---|
| E1 | `GET /storefront/portal/bell` → projection over `message_log` (her bookings' rows, `kind != 'otp'`, `status = 'sent'`, joined to bookings for `starts_at`/type name, `created_at` DESC cap 20) + `unread_count` vs `customers.bell_seen_at` (NULL = all unread). `POST /storefront/portal/bell/seen` → `set_bell_seen(now())`. Repo query in `message_log.py`. **Never returns `body`** — wire shape is `{id, kind, created_at, booking_id, starts_at, appointment_type_name}`. | `test_portal_service.py` (**db**) — OTP and failed rows excluded; another customer's rows excluded; order + cap; unread vs `bell_seen_at` incl. NULL; seen-stamp flips count to 0; response schema has no `body` field (set-equality on keys) | M `Backend/app/db/repositories/message_log.py`, M `Backend/app/portal/service.py`, M `Backend/app/portal/schemas.py`, M `Backend/app/portal/router.py`, M `Backend/tests/test_portal_service.py` |

### Phase F — storefront UI (commits 6–7)

| # | Task | Test first | Files |
|---|---|---|---|
| F1 | Router: exact literal `/portal` → `RouteName "portal"`, `DOC_TITLE_KEYS.portal = "document.portal"`, switch `case "portal"`. **The render-pair test lands first** — the switch is not compiler-forced; a missing case renders the catalog under the portal title and stays green (spec trap). `PortalPage.tsx` bootstraps on `portalMe()`: 401 → login panel, 200 → dashboard. | `router.test.tsx` — the `/portal` render-pair assertion (title + component), red before the case exists | M `Frontend/apps/storefront/src/router.tsx`, C `Frontend/apps/storefront/src/routes/PortalPage.tsx`, M `Frontend/apps/storefront/src/__tests__/router.test.tsx` |
| F2 | `api.ts`: `portalMe`, `portalLogin` (verify+mint chain — design P1), `portalLogout`, `portalBookings`, `portalBooking`, `portalConfirmAttendance`, `portalCancel`, `portalBell`, `portalBellSeen`, `portalIcsUrl(id)` (plain href), `manageIcs(token)` (POST + blob helper); `PORTAL_NO_BOOKINGS` in the error-key map. `PortalLogin.tsx` per design §2: OTP block copied from the verify step (single code field, `dir="ltr"`, 60s cooldown, one send/resend label); state table D/S1/C/S2/E1–E7/N/X; **E7 retry re-fires the mint alone, never a second verify on a burned token**; `PHONE_NOT_VERIFIED` → `portal.verifyExpired` (F-P1, never `errors.phoneNotVerified`); phone edit collapses code + clears token state. Login-half i18n keys (he + ar mirror). | `PortalLogin.test.tsx` (new) — chain fires verify then mint on one click; E3/E5/E7 mappings; collapse clears state; N renders the shared empty component; `api.test.ts` — new methods + error key | C `Frontend/apps/storefront/src/components/portal/PortalLogin.tsx`, M `Frontend/apps/storefront/src/api.ts`, M `Frontend/apps/storefront/src/i18n/he.ts`, M `…/ar.ts`, C `Frontend/apps/storefront/src/__tests__/PortalLogin.test.tsx`, M `…/api.test.ts` |
| F3 | **Extract, don't fork** (F-P3): pull the facts-card and cancel-two-step pieces out of `ManageBookingPage.tsx` into shared components; `ManageBookingPage` re-composes them (its tests stay green). `PortalBookingList.tsx` (design §3: rows, badges per P3, section empties, shared EmptyState, skeleton + `manage.loadFailed`/`retry`) and `PortalBookingDetail.tsx` (design §4: manage states verbatim, back link, house-404, `.ics` `<a download>` on L/L2/completed-P only). Tokenized page gains the same `.ics` control via `manageIcs(token)` blob. | `ManageBookingPage.test.tsx` green **unedited** through the extraction; `PortalBookingList.test.tsx` + `PortalBookingDetail.test.tsx` (new) — badge policy (no badge on confirmed/completed/no_show); order as given; 409 re-render from response body; ics control absent on C/A states | M `Frontend/apps/storefront/src/routes/ManageBookingPage.tsx`, C `Frontend/apps/storefront/src/components/portal/PortalBookingList.tsx`, C `…/PortalBookingDetail.tsx`, C shared extracted component(s) under `src/components/booking/`, M `Frontend/apps/storefront/src/routes/PortalPage.tsx`, C two test files |
| F4 | `PortalBell.tsx` per design §5: disclosure (aria-expanded/controls), badge "9+" cap `aria-hidden` with count in the accessible name, open → focus panel heading, `portalBellSeen()` on open with **badge clearing only after the 2xx** (F-P2) and **not fired on a failed fetch**; items from `kind` + i18n only (unknown kinds skipped); empty + load-failed states per design. | `PortalBell.test.tsx` (new) — badge clears after resolved POST, not on click; failed fetch → no badge, no seen POST, retry path; unknown kind renders nothing | C `Frontend/apps/storefront/src/components/portal/PortalBell.tsx`, C `Frontend/apps/storefront/src/__tests__/PortalBell.test.tsx` |
| F5 | Remaining i18n: full `portal.*` table from design §11 + `document.portal` in `he.ts`; `ar.ts` mirrors with Hebrew values (pre-decided #47). **Zero exclamation marks.** Reused rows (`booking.*`, `manage.*`, `errors.*`) referenced, never duplicated. | `i18n-keys.test.ts` — floor extended for the `portal.` prefix; ar-presence guard binds on the new keys | M `Frontend/apps/storefront/src/i18n/he.ts`, M `…/ar.ts`, M `Frontend/apps/storefront/src/__tests__/i18n-keys.test.ts` |

### Phase G — e2e (commit 8)

| # | Task | Test first | Files |
|---|---|---|---|
| G1 | `portal.spec.ts` (per-feature file, `walk-in.spec.ts` pattern) with its own `page.route("**/storefront/**")` interception map in the `storefront.spec.ts:470` style, stubbing OTP + all eleven portal endpoints (the harness proves the journey, not the contract — the db-marked tests are the contract side; keep both). Journeys: login phone→code→dashboard; `PORTAL_NO_BOOKINGS` state; empty + populated bookings; detail + cancel dialog (danger on final confirm only); bell badge → open → seen POST observed → badge cleared; `.ics` download triggered (portal GET + token-page POST/blob); logout. **axe zero-violation** on: login (incl. an error state + a dead-end block), empty dashboard, populated dashboard, detail + cancel reveal open, bell open (empty + populated), session-expired panel. RTL rendering; focus lands on `#content` after navigation (router contract). Focus/dialog assertions live HERE, not vitest (`.memory/jsdom-has-no-dialog`). | this IS the test | C `Frontend/e2e/portal.spec.ts` |

## 4. Build environment — RECORD, these are facts not suggestions

- **No Docker locally.** Tests marked `db` or `s3` run **on CI only**. Do not chase local db-test failures.
- **The local fast lane (`-m 'not db'`) points at a CLOSED Postgres port by design (F21).** A test dialing a real DB without the `db` marker fails locally — that is correct behavior, not a bug. Every new db-touching test MUST carry the `db` marker.
- **The worktree has no `Backend/.env`.** Config-default tests behave differently than the main checkout (`.memory/local-env-breaks-config-tests` — there the failure is REAL if it appears).
- **Local gates, all must pass before push**: `make lint` · backend non-db tests (`make test`) · `make fe-test` · `make fe-build` · `make e2e`.
- Write db-marked tests carefully against the spec's test plan; their first run is CI (`.memory/boutique-ci-first-run-surprises`).

## 5. Build discipline

**Commit boundaries** (conventional, scoped):
1. `feat(portal): customer_sessions migration, model, repository, erase revocation` — A1–A3 (a session table absent from erase is silently incomplete; one commit).
2. `feat(portal): OTP session mint, cookie auth, me and logout, walker registration` — B1–B3.
3. `feat(portal): bookings list and detail, mirrored confirm and cancel via shared transitions` — C1–C3.
4. `feat(booking): stdlib ics builder and both download routes` — D1–D2.
5. `feat(portal): bell projection over message_log` — E1.
6. `feat(portal): /portal route, session bootstrap, login panel` — F1–F2.
7. `feat(portal): bookings UI, detail extraction, ics control, bell panel, i18n` — F3–F5.
8. `test(e2e): portal journeys with axe` — G1.

**Migration renumber protocol**: built at observed-head+1 in the worktree. **F22 is landing `0026` in parallel — assume this plan's number shifts.** Immediately before the pre-push rebase, re-run `alembic heads` against rebased main; if a sibling took the number, renumber (filename + `revision` + `down_revision`) in one `fix(portal):` commit. A reserved-but-wrong number breaks alembic outright and reds every db test (`.memory/parallel-alembic-numbering`).

**Pathspec**: git tracks `backend/`/`frontend/` **lowercase**. `git add Backend/…` silently skips modified tracked files — lowercase every pathspec, verify with `git show --stat` (`.memory/git-add-uppercase-pathspec-trap`).

**Frontend build check**: `pnpm build` before staging any `.ts`/`.tsx`.

**After any merge-conflict resolution**: parse every touched test file's collection count — a broken file reads as one `Tests no tests` line (`.memory/silently-unexecuted-test-files`).

## 6. Risks this plan adds to the spec's list

- **R-A**: C1's refactor of `ManageBookingService` is the mirror guarantee's foundation — if the token/transition split turns invasive, stop and keep the token paths byte-compatible (their suites green unedited is the tripwire, not a nice-to-have).
- **R-B**: B3's walker population needs a customer cookie inside the walker harness; if the plumbing resists, exemption-with-reason is acceptable but the reason must name the plumbing, and the cross-customer 404s remain covered by C2/C3's db tests.
- **R-C**: F3's extraction can silently change `ManageBookingPage` behavior while its tests pass — run the manage-page e2e journeys in `storefront.spec.ts` locally after F3, not only at G1.
- **R-D**: two features touch `he.ts`/`ar.ts` in parallel (F22 adds `waitlist.*`) — expect an i18n merge conflict at rebase; re-run the collection-count check on `i18n-keys.test.ts` after resolving.
