# Plan: Feature 38 — HR directory: photos, shift-manager eligibility, offboarding + retention scrub (Epic E8)

**Spec**: `.planning/specs/hr-directory.md` (2026-08-06, Gate 1 standing-approved; C1–C4, O1–O4 binding)
**Design**: `.planning/design/screens/hr-directory/design.md` (R1–R3, §1–§5, copy deck; design gate accepted)
**Plan written**: 2026-08-06. **Observed alembic head at plan time: `0026` (`0026_waitlist_entries.py`).** F24, F25 and F28 hold plans with migrations of their own, queued ahead of this one. The migration is numbered **head+1 as observed in the F38 worktree at build time** and re-resolved at rebase per §5. **Assume the number shifts.**
**Depends on**: F31, F51, F8, F20, F9 — all merged.
**Worktree**: `.worktrees/hr-directory`, branched from `origin/main`.

---

## 0. How to read this plan

Every task is one TDD cycle: the named failing test first, then the code that makes it pass. Schema → wire fields → photo pipeline → offboarding → retention → floor card → UI → e2e; the UI comes last because it needs settled shapes. The spec's C1–C4 and the design's R1–R3 are binding and not restated here. Every path below was verified against `main` on 2026-08-06.

## 1. Verified facts the tasks lean on

| Claim | Verified at |
|---|---|
| Head is `0026_waitlist_entries.py`; column-add precedent is `0023_seamstress_capacity.py` | `Backend/migrations/versions/` |
| Staff row has no `phone`/dates/photo; **no model↔migration parity test exists** — the model must be edited in the same PR | `Backend/app/models/staff_user.py` |
| `_STAFF_LOCK = pg_advisory_xact_lock(hashtext('staff:' || :tenant_id))` | `Backend/app/auth/staff.py:64` |
| `DuplicateEmailError` / `LastOwnerRequiredError` / `StaffSelfManageError` / `StaffNotFoundError`; `deactivate` takes the lock at `:284` | `Backend/app/auth/staff.py:71-87,276-284` |
| Router mounts `require_role(StaffRole.OWNER)` + `_no_store` **on the router**; `_member(row)` is the one wire builder; `DELETE /manage/staff/{staff_id}` | `Backend/app/auth/staff_router.py` |
| `StaffMember` / `CreateStaffRequest` / `UpdateStaffRequest` | `Backend/app/auth/schemas.py:50,62,71` |
| Two-phase media: `presign_media` (throttle first, then validate, then `is_configured`), `confirm_media`, `delete_media`, `sign_media` (degrade to `url=None`) | `Backend/app/catalog/service.py:559,677,754,210` |
| `build_media_key` / `build_media_filename` — nothing a client sends reaches a key | `Backend/app/catalog/keys.py` |
| `ACCEPTED_CONTENT_TYPES`, `MAGIC_PREFIXES`, `MAGIC_PREFIX_LENGTH=16`, `matches_magic_prefix`, `PRESIGN_TTL_SECONDS=300`, `SIGNED_GET_TTL_SECONDS=900`, `MIN_UPLOAD_BYTES=1024` | `Backend/app/catalog/validation.py` |
| `MediaStorage` protocol: `is_configured`, `presigned_post`, `signed_get_url`, `head_object`, `read_prefix`, `delete_object`; both storage errors | `Backend/app/storage/base.py:10-58` |
| Catalog presign limiter is built in `create_app()` — the template for the new **separate instance** | `Backend/app/main.py:775` |
| `_scrub` / `_erased_phone` helpers; `audit_action()`; `CHUNK_SIZE=500`, `MAX_CHUNKS=50`; `POLICIES` is **seven**, order load-bearing | `Backend/app/privacy/retention.py:99,147,167,413` |
| `waitlist_retention_days: int = 30` (the DAYS precedent); the floors dict + its `"… must be at least {floor} seconds"` message | `Backend/app/core/config.py:269,354-386` |
| `AuditAction.STAFF_DEACTIVATED`; the `RETENTION_*` block ends at `RETENTION_WAITLIST_ENTRIES` | `Backend/app/models/constants.py:343,663-671` |
| `test_the_registry_covers_the_seven_classes_…`; `FORBIDDEN_TABLES` | `Backend/tests/test_retention_policies.py:96,42` |
| CHECK-pinning pattern (`_ROLE_CHECK`, `test_staff_role_check_pins_the_role_set`) | `Backend/tests/test_migrations.py:107,148` |
| Route-table gates: `OWNER_ONLY` + the four `STAFF_*` templates; the whole-route-table walker assertion; the mutating-route audit assertion | `test_staff_role_gating.py:53-83`, `test_cross_tenant_walker.py:948`, `test_audit_coverage.py:242` |
| `s3` marker exists and is always paired with `db` | `Backend/pyproject.toml:90-93`, `Backend/tests/test_media_upload_s3.py:30` |
| `validate_phone` · `today_jerusalem` / `BOUTIQUE_TIMEZONE` | `Backend/app/boutique/validation.py:81`, `Backend/app/storefront/validation.py:40,86` |
| `StaffCard` is a **six-key** model with a set-equality assertion over it; `from_row` | `Backend/app/floor/schemas.py:61,78` |
| `MAPPED_CODES` (4 codes, pinned by nothing) · `pending: StaffMember \| null` · focus-restore effect · `handleDeactivate` · the one `Modal` | `Frontend/apps/manage/src/components/StaffSection.tsx:18-23,54,84-93,191,420-455` |
| `StaffMember` / `CreateStaffRequest` / `UpdateStaffRequest` / `StaffCard` wire types | `Frontend/apps/manage/src/api.ts:831,869,881,500` |
| `Checkbox`, `DateField`, `Modal`, `Skeleton` all exported today — nothing new in `packages/ui` | `Frontend/packages/ui/src/index.ts` |
| `MAX_UPLOAD_BYTES`, `ACCEPTED_CONTENT_TYPES`, `validateUploadFile` (HEIC branch) | `Frontend/apps/manage/src/validation.ts:198,206,302` |
| `MIRRORS` pins manage constants against `app/catalog/validation.py` | `Backend/tests/test_frontend_constant_parity.py:56` |
| `staff.*` he keys 252–303; the `!` guard, the ar-presence guard and the per-feature drift blocks | `Frontend/apps/manage/src/i18n/he.ts`, `src/__tests__/i18n.test.ts:1483,1534,1546+` |
| e2e: `manage.spec.ts`, `a11y.spec.ts` (`AxeBuilder … withTags(["wcag2a","wcag2aa"])`), `fixtures/` | `Frontend/e2e/` |

## 2. Migration `NNNN_staff_hr_directory.py` (NNNN = head+1 at build time)

Raw SQL, `0023`'s template: ten `ALTER TABLE staff_users ADD COLUMN` per the spec's data-model block (`phone`, `start_date`, `last_day`, `shift_manager_eligible NOT NULL DEFAULT false`, `scrubbed_at`, and the six photo columns). Two **named** CHECKs — `staff_users_photo_content_type_check`, `staff_users_photo_pending_content_type_check` — each `IS NULL OR IN ('image/jpeg','image/png','image/webp')`, the literal set **imported into the test** from `app.catalog.validation.ACCEPTED_CONTENT_TYPES`, never retyped. No new table, no index (`phone` is non-unique by C1, and a unique index would also collide at scrub time). Backfill in the same migration, load-bearing: `UPDATE staff_users SET last_day = (deleted_at AT TIME ZONE 'Asia/Jerusalem')::date WHERE deleted_at IS NOT NULL AND last_day IS NULL;`. Downgrade drops the two CHECKs and the ten columns.

## 3. Ordered task list

### Phase A — schema + model (commit 1)

| # | Task | Test first | Files (C=create, M=modify) |
|---|---|---|---|
| A1 | Migration per §2. | `test_migrations.py` (**db**) — the ten columns exist with the stated nullability/default; both CHECKs pinned by deparsed literal against imported `ACCEPTED_CONTENT_TYPES` (0023's rule, `_ROLE_CHECK`'s shape); a row with `content_type='image/gif'` is refused; the backfill fills `last_day` on a pre-F38 soft-deleted row and leaves a live row alone; `test_exactly_one_migration_head` and the forced-RLS sweep stay green **unedited** | C `Backend/migrations/versions/NNNN_staff_hr_directory.py`, M `Backend/tests/test_migrations.py` |
| A2 | Ten `Mapped[…]` columns on `StaffUser`, each typed as the spec's data model. **No parity test exists** — an omitted column is an `AttributeError` at first read, not a red test. | `test_boutique_models.py` — the model declares every column the migration adds (set-equality of `StaffUser.__table__.columns` against the ten names + the shipped set) | M `Backend/app/models/staff_user.py`, M `Backend/tests/test_boutique_models.py` |

### Phase B — profile fields on the wire (commit 2)

| # | Task | Test first | Files |
|---|---|---|---|
| B1 | `StaffMember` gains `phone`, `start_date`, `last_day`, `shift_manager_eligible`, `photo_url`, `photo_confirmed_at`; `CreateStaffRequest`/`UpdateStaffRequest` gain `phone?`, `start_date?`, `shift_manager_eligible?`. `phone` validates through the **imported** `validate_phone`; dates are `datetime.date` on the wire. `_member(row)` becomes storage-aware (`photo_url` signed per read with `sign_media`'s degrade-to-null posture). `StaffService.create`/`update` persist the three, F51's send-only-what-moved rule and its per-field `STAFF_UPDATED` audit rows extending to them unchanged. | `test_staff_service.py` (**db**) — create with and without the three; PATCH one field writes one audit row and leaves the rest untouched; a no-op PATCH writes none; bad phone → house 400. `test_staff_api.py` — the response key set is exactly the eleven | M `Backend/app/auth/schemas.py`, M `Backend/app/auth/staff.py`, M `Backend/app/auth/staff_router.py`, M both test files |

### Phase C — photo pipeline (commit 3)

| # | Task | Test first | Files |
|---|---|---|---|
| C1 | `app/auth/photo.py`: `MAX_STAFF_PHOTO_BYTES = 2_097_152`, `build_staff_photo_key(tenant_id, staff_user_id, photo_id, content_type)` (`tenants/{tenant_id}/staff/{staff_user_id}/photo/{photo_id}{ext}`) and `validate_staff_photo_presign`. `ACCEPTED_CONTENT_TYPES` / `MIN_UPLOAD_BYTES` / the magic table are **imported from `app/catalog/validation.py`**, never re-declared. | `test_staff_photo.py` (**non-db**, new) — key shape and tenant prefix; an unknown content type raises rather than producing an extensionless key; the 2 MiB and 1 KiB bounds; `MAX_STAFF_PHOTO_BYTES < MAX_UPLOAD_BYTES` asserted so a copy-paste of the catalog cap fails | C `Backend/app/auth/photo.py`, C `Backend/tests/test_staff_photo.py` |
| C2 | `StaffService.presign_photo` / `confirm_photo` / `delete_photo`, following `confirm_media`'s sequence exactly: throttle → validate → `is_configured` → `_STAFF_LOCK` inside `tenant_session` → row resolve → write pending triple → **every storage call outside the session** → `head_object` → content-type match → `read_prefix(MAGIC_PREFIX_LENGTH)` → `matches_magic_prefix` → promote in a second transaction. Replace best-effort-deletes the superseded object **after** the audit row naming its key. A **dedicated** `FixedWindowRateLimiter` instance keyed `presign:staff:{tenant_id}`, constructed in `create_app()` beside `main.py:775`. Reuses `_STAFF_LOCK`, not a new lock prefix. | `test_staff_photo.py` (**db**) — presign writes only the pending triple and leaves a live photo rendering; confirm promotes and is idempotent on retry; magic mismatch → 400 **and** the object deleted; content-type mismatch → 400; over-cap and bad type → 400; unconfigured storage → 503 on all three writes while `GET /manage/staff` still answers 200 with `photo_url: null`; the throttle 429s **without spending the catalog's budget** (assert the catalog limiter's counter is untouched — `.memory/limiter-max-is-per-instance`) | M `Backend/app/auth/staff.py`, M `Backend/app/main.py`, M `Backend/tests/test_staff_photo.py` |
| C3 | Three routes on the existing owner-only router: `POST /manage/staff/{staff_id}/photo/presign`, `POST …/photo/confirm`, `DELETE …/photo`. Confirm and delete return the updated `StaffMember`. | `test_staff_api.py` — the ROUTES table gains the three; each answers 404 for an unknown staff id and inherits the router gate (no per-route decorator) | M `Backend/app/auth/staff_router.py`, M `Backend/tests/test_staff_api.py` |
| C4 | Register the three routes in every route-table gate: `OWNER_ONLY` in `test_staff_role_gating.py`, the walk in `test_cross_tenant_walker.py` (**populate, don't exempt** — an owner cookie already exists in that harness; an exemption is acceptable only with a written plumbing reason), and `test_audit_coverage.py`'s mutating-route assertion. | All three suites red on the new routes until this lands — **that red is the failing test** | M `Backend/tests/test_staff_role_gating.py`, M `Backend/tests/test_cross_tenant_walker.py`, M `Backend/tests/test_audit_coverage.py` |

### Phase D — offboarding (commit 4)

| # | Task | Test first | Files |
|---|---|---|---|
| D1 | `DELETE /manage/staff/{staff_id}?last_day=YYYY-MM-DD` — optional, defaulting to `today_jerusalem()`; rejected if `> today + 1 year` or `< start_date`. One `tenant_session`, `_STAFF_LOCK` **before any read**, F51's three guards keeping their shipped bodies and wire codes, then `UPDATE last_day` + null the six photo columns + `soft_delete`, then `STAFF_DEACTIVATED` with `details` gaining `last_day` and `photo_storage_key`. Best-effort `delete_object` **after** the transaction, logged not raised. **No session sweep** — `revoke_for_staff_user` must not be called here. | `test_staff_management_db.py` (**db**) — `last_day` + `deleted_at` + the audit row land in one transaction; the default is today-Jerusalem; a blank body still stamps a date (a NULL would silently exempt her from the clock); both bounds reject; the three F51 guards still fire and none of them writes `last_day`; the audit row carries the key even when the delete is stubbed to raise | M `Backend/app/auth/staff.py`, M `Backend/app/auth/staff_router.py`, M `Backend/tests/test_staff_management_db.py` |
| D2 | **The retention proof.** No production code — this task is the assertion that offboarding keeps operational history. | `test_staff_management_db.py` (**db**) — after offboarding, her `fitting_room_assignments`, `sos_alerts.target_staff_user_id`, `alteration_tickets.assigned_staff_user_id` and `audit_log.actor_id` rows all still exist and still resolve by id, and the room read renders the D11 ghost-holder (`staff_display_name: null`) rather than dropping the row; her live session is a **401 on the next request** with no sweep call anywhere (F31's `resolve_session` seam) | M `Backend/tests/test_staff_management_db.py` |

### Phase E — retention (commit 5)

| # | Task | Test first | Files |
|---|---|---|---|
| E1 | `Settings.staff_retention_days: int = 365 * 7`, beside `waitlist_retention_days`, with the same "flagged for counsel at F21" comment, plus a floor of `365 * 3`. ⚠ **The existing floors loop hardcodes `"… must be at least {floor} seconds"`** — a days field must not ride that dict or the error names the wrong unit. Smallest correct fix: one two-line check after the loop with a days-worded message. | `test_config.py` — the default is 2555; `STAFF_RETENTION_DAYS=7` refuses at boot; the message says **days**, not seconds; the seconds fields' messages are unchanged | M `Backend/app/core/config.py`, M `Backend/tests/test_config.py` |
| E2 | `_scrub_staff_users` per the spec's body verbatim (`.astimezone(BOUTIQUE_TIMEZONE).date()` before the date compare; `scrubbed_at IS NULL` as the D22 self-falsifying guard; `email` per-row via `_erased_phone`'s form; `phone → NULL`; `password_hash` deliberately untouched). Registered **last** in `POLICIES` as `RetentionPolicy("staff_users", RetentionAction.SCRUB, ("staff_users",), _scrub_staff_users)`. `AuditAction.RETENTION_STAFF_USERS = "retention_staff_users"`. | `test_retention_policies.py` — rename `…_seven_classes_…` → `…_eight_classes_…` and add the row; `staff_users` is not in `FORBIDDEN_TABLES`; `audit_action()` resolves for it (a missing enum member is a `ValueError` here, not a 03:00 no-op); the bookings-before-customers order assertion stays green | M `Backend/app/privacy/retention.py`, M `Backend/app/models/constants.py`, M `Backend/tests/test_retention_policies.py` |
| E3 | No new production code — the real-Postgres proof. | `test_retention_db.py` (**db**) — both boundary directions (`last_day` one day inside and one day outside the window); the D22 loop (already a loop over `POLICIES`) proves the new predicate is falsified by its own UPDATE; a **live** staffer past seven years is never touched; a `last_day IS NULL` row is never touched; two rows in one chunk get **distinct** `erased:{id}` emails; a dry run writes nothing | M `Backend/tests/test_retention_db.py` |

### Phase F — floor card (commit 6)

| # | Task | Test first | Files |
|---|---|---|---|
| F1 | `StaffCard` gains `photo_url: str \| None` and `photo_confirmed_at`, signed per read with the degrade-to-null posture. **The set-equality assertion over the card's keys is what makes this a deliberate widening** — update it in the same commit. | `test_floor_service.py` — the card's key set is exactly eight; a photo signs; a storage failure yields `photo_url: null` **without failing the board read**; a staffer with no photo carries nulls | M `Backend/app/floor/schemas.py`, M `Backend/tests/test_floor_service.py` |

### Phase G — manage UI (commits 7–8)

| # | Task | Test first | Files |
|---|---|---|---|
| G1 | `api.ts`: the six new `StaffMember` fields, the three new request fields, `StaffCard`'s two, and `staffPhotoPresign` / `staffPhotoConfirm` / `staffPhotoDelete` / `deactivateStaff(id, lastDay)`. `validation.ts`: `MAX_STAFF_PHOTO_BYTES = 2_097_152` + a `validateStaffPhotoFile` reusing `validateUploadFile`'s HEIC/type branches with the smaller cap, and the last-day range message (hardcoded Hebrew, F51's deck rule). | `api.test.ts` — the four methods and their bodies; `validation.test.ts` — 2 MiB boundary, HEIC message, `last_day < start_date`; `test_frontend_constant_parity.py` — `MAX_STAFF_PHOTO_BYTES` added to the manage MIRRORS tuple against `app/auth/photo.py` (red until `validation.ts` declares it) | M `Frontend/apps/manage/src/api.ts`, M `…/validation.ts`, M `…/__tests__/api.test.ts`, M `…/validation.test.ts`, M `Backend/tests/test_frontend_constant_parity.py` |
| G2 | Edit panel per design R1: `Input(phone, type=tel, dir=ltr)`, `DateField(start date)`, `Checkbox(shift_manager_eligible)` with its `description`; the create form gains the same three. List row gains the muted eligibility words (**not** a second Badge) and a read-only 44 px avatar cell. **`size="md"` only (F-W1).** | `StaffSection.test.tsx` — the three render in edit and create; save sends only what moved; the row shows the eligibility words when set and nothing when not; every touch control asserts `size="md"` | M `Frontend/apps/manage/src/components/StaffSection.tsx`, M `…/__tests__/StaffSection.test.tsx` |
| G3 | Photo block per design §1: a **real, visible, focusable** `<input type="file">` (never `display:none`), `accept` the three types, no `multiple`, `help` = purpose line + formats, one `role="status"` region for uploading→verifying→terminal, `role="alert"` failures that **keep the previous photo visible**, `[הסרת תמונה]` through the widened `pending: { kind: "offboard" \| "photo"; row }` state on the **one** `Modal` (R3 — a second Modal duplicates the focus-restore effect). Five new codes added to `MAPPED_CODES`. | `StaffSection.test.tsx` — presign→confirm sequence on one pick; a failed confirm leaves the old preview rendered and announces in the alert region; the status region carries both progress and terminal text; the remove confirm is two-step; all five codes render Hebrew, and a sixth unmapped code is asserted to fall through to English so the gap stays visible | M `…/StaffSection.tsx`, M `…/StaffSection.test.tsx` |
| G4 | Offboard dialog per design §4: `DateField(last day)` defaulted to today-Jerusalem, the retention note, `<Trans>` body with a bare `<bdi>`, danger on the row trigger **and** the footer confirm, `role="status"` success line with name + date. Four F51 key **values** change (`deactivateCta/Aria/Title/Confirm`) — their names do not. | `StaffSection.test.tsx` — the date defaults to today and is sent; an out-of-range date is refused client-side before any call; the row leaves the list and the status line names her and the date; the guard refusals keep their existing alert slot; the four changed strings asserted at their new values | M `…/StaffSection.tsx`, M `…/StaffSection.test.tsx` |
| G5 | `FloorPanel.tsx`: 44 px `rounded-full` avatar at the inline start (`me-3`, `shrink-0`), `alt=""` with the initial fallback `aria-hidden`, and **URL pinning keyed by `(id, photo_confirmed_at)`** so the ~5 s poll does not re-download every face. `onError` drops that id's pin and falls back to the initial, letting the next tick adopt a fresh URL. | `FloorPanel.test.tsx` — the photo renders; a poll returning a **different signed URL with the same `photo_confirmed_at`** does not change `src` (this is the load-bearing assertion); a changed `photo_confirmed_at` does; `onError` falls back and the next poll re-adopts; `alt` is empty | M `Frontend/apps/manage/src/components/FloorPanel.tsx`, M `…/__tests__/FloorPanel.test.tsx` |
| G6 | The full copy deck from design §copy into `he.ts`, mirrored into `ar.ts` **untranslated** (Hebrew values standing in, never `""`). Zero exclamation marks. | `i18n.test.ts` — a new per-feature `HE_F38` block: ar-presence, ar-value drift, the `!` guard, and no digits in the new values except where the deck has them (`2MB`) | M `Frontend/apps/manage/src/i18n/he.ts`, M `…/ar.ts`, M `…/__tests__/i18n.test.ts` |

### Phase H — e2e (commit 9)

| # | Task | Test first | Files |
|---|---|---|---|
| H1 | Extend `manage.spec.ts` (staff journeys, `page.route` interception in the shipped style) and `a11y.spec.ts`: upload → verify → ready; a failed upload keeping the old photo; eligibility toggle; offboard dialog with its date input; board avatars. **axe zero violations** on: list with photos, list without, edit panel mid-upload, the offboard modal open, the photo-remove modal open — all RTL. 44 px target assertions. Focus/dialog behaviour lives **here**, not in vitest (`.memory/jsdom-has-no-dialog`). | this IS the test | M `Frontend/e2e/manage.spec.ts`, M `Frontend/e2e/a11y.spec.ts`, M `Frontend/e2e/fixtures/manage.ts` |

## 4. Build environment — RECORD, these are facts not suggestions

- **No Docker locally.** Tests marked `db` or `s3` run **on CI only**. Do not chase local db-test failures.
- **The local fast lane (`-m 'not db'`) points at a CLOSED Postgres port by design (F21).** A test dialing a real DB without the `db` marker fails locally — that is correct behavior, not a bug. Every new db-touching test MUST carry the `db` marker; every storage-touching one MUST carry `s3` **in addition to** `db`.
- **The worktree has no `Backend/.env`.** Config-default tests behave differently than the main checkout (`.memory/local-env-breaks-config-tests` — there the failure is REAL if it appears). E1 edits `test_config.py`, so expect this.
- **Local gates, all must pass before push**: `make lint` · backend non-db tests (`make test`) · `make fe-test` · `make fe-build` · `make e2e`.
- Write db- and s3-marked tests carefully against the spec's test plan; their first run is CI (`.memory/boutique-ci-first-run-surprises`).

## 5. Build discipline

**Commit boundaries** (conventional, scoped):
1. `feat(staff): hr directory migration and model columns` — A1–A2.
2. `feat(staff): phone, start date and shift-manager eligibility on the wire` — B1.
3. `feat(staff): profile photo presign, confirm and delete over F8 storage` — C1–C4.
4. `feat(staff): offboarding with last day, photo deletion and retained history` — D1–D2.
5. `feat(privacy): eighth retention policy, the ex-staff scrub` — E1–E3.
6. `feat(floor): staff card photo` — F1.
7. `feat(manage): staff profile fields, photo control and offboard dialog` — G1–G4.
8. `feat(manage): board avatars with pinned urls, hebrew and arabic copy` — G5–G6.
9. `test(e2e): staff directory journeys with axe` — H1.

**Migration renumber protocol**: built at observed-head+1 **in the worktree**. F24, F25 and F28 are queued in parallel — assume this plan's number shifts. Immediately before the pre-push rebase, re-run `alembic heads` against rebased main; if a sibling took the number, renumber (filename + `revision` + `down_revision`) in one `fix(staff):` commit. A reserved-but-wrong number breaks alembic outright and reds every db test (`.memory/parallel-alembic-numbering`).

**Pathspec**: git tracks `backend/`/`frontend/` **lowercase**. `git add Backend/…` silently skips modified tracked files — lowercase every pathspec, verify with `git show --stat` (`.memory/git-add-uppercase-pathspec-trap`).

**Frontend build check**: `pnpm build` before staging any `.ts`/`.tsx`.

**After any merge-conflict resolution**: parse every touched test file's collection count — a broken file reads as one `Tests no tests` line (`.memory/silently-unexecuted-test-files`).

## 6. Risks this plan adds to the spec's list

- **R-A**: C2 threads storage into `StaffService`, which until now touched nothing but the DB. If the constructor churn reaches `main.py` wiring in more than the two expected places (service construction + the new limiter), stop and keep the photo methods on a thin collaborator rather than growing the service's dependency set.
- **R-B**: F1 widens a model whose key set is asserted by set-equality in two suites. Grep for the assertion before editing; a silently-passing widening there is how a seventh key arrived unreviewed once already.
- **R-C**: `test_retention_policies.py` and `test_retention_db.py` are shared with F22's merged waitlist row. Expect no conflict, but re-run their collection counts after rebase.
- **R-D**: G6 touches `he.ts`/`ar.ts`, which several parallel features also touch — expect an i18n merge conflict at rebase, and re-run `i18n.test.ts`'s collection count after resolving.
- **R-E**: E1's floors loop message is worded in seconds. Riding the days field on that dict passes every test that only checks *that* it raises, and ships an error message naming the wrong unit — assert the message text, not just the raise.
