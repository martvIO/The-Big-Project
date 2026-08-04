# Plan: Feature 50 — Owner-created bookings, the walk-in half (Epic E3 carve-out, SMC-6)

**Spec**: `.planning/specs/walk-in-bookings.md` (2026-08-04, Gate 1 self-approved under Interview Q1, revised 2026-08-04 after adversarial review)
**Plan written**: 2026-08-04, against `main` @ `1a02ffe` (head migration `0024_privacy_consent`)
**Migration**: **YES — one.** `0025_walk_in_bookings.py`. Re-resolve the number with `alembic heads` immediately before the pre-push rebase; keep it the LAST commit on the branch so a renumber is one amend to one file.
**Depends on**: F15, F34, F53, F20 — all merged.

**What the spec's review changed that this plan is built on** — D1 gained a `downgrade()` that is deliberately able to fail; D1b grew a seventh site because `api.ts:1056-1057` is a *different interface*; D2's "never in the feed" gained a bounded exception (Risk 8); D9 gained a terminal guard the `refresh()`-for-`reschedule()` swap forces; the frontend section named a test file that does not exist and missed a fourth one that will not compile.

---

## 0. How to read this plan

Everything below was opened. Section 1 records what moved between the spec and the tree and the reading taken. Section 2 is the migration, column by column. Section 3 is the ordered task list, one TDD cycle each. Section 4 is the test inventory with `db` marks and the **single-line deletion** that reddens each one. Section 5 is build discipline. Section 6 is risks the plan found that the spec did not.

**The rule this plan is written to serve, because this repo's worst defects have all been in the proofs**: every test names the one line whose deletion makes it red. Where no such line exists, the test is called out as structural and the thing that proves it bites is named instead. A seeded fixture where widening a filter adds no rows, a SQL `LIMIT` hidden behind a Python slice, a mutation test that asserted nothing — all three shipped here before.

---

## 1. Drift found against the spec, and the reading taken

The spec was written today against this same head, so drift is small. Four items are load-bearing.

### DR-1 — The migration is **0025**, and that number has moved ten times in a week.
`Backend/migrations/versions/` runs 0001…0024; `0024_privacy_consent.py` merged four hours before the spec was written. So `revision = "0025"`, `down_revision = "0024"`.
**Reading**: the number in this document is a *starting value*, not a fact. Re-run `alembic heads` against the **rebased** branch immediately before push. `.memory/parallel-alembic-numbering` records that a reserved-but-wrong number breaks alembic outright and reds **every** db test — the check is not skippable, and keeping the migration as the last commit makes the fix `git commit --amend` on one file.

### DR-2 — `test_migrations.py` is 2 800+ lines and already holds every idiom this feature needs. Nothing is invented.
| What F50 needs | Shipped precedent | Line |
|---|---|---|
| `ADD CONSTRAINT` validating a **populated** table | `test_adding_the_role_check_validates_existing_rows` | 0011 family |
| a CHECK proved droppable/re-addable **by explicit name** | `_constraint_accepts(migrated_db, _ADD_ROLE_CHECK, [...])` | `:107-134` |
| a downgrade **asserted to fail** | `test_the_downgrade_refuses_to_narrow_past_a_floor_role_row` | `:352` |
| a round-trip | `test_migration_0011_round_trips` … `test_the_privacy_migration_round_trips` | `:369` … `:2828` |
| re-pinning an indexdef/constraintdef against a literal after a later migration | F34's test | `test_migration_0014_round_trips` region |

**Reading**: every migration test in §4 is written in one of these five idioms. No new helper.

### DR-3 — `AppointmentTypesRepository.by_id` filters `deleted_at` only, and "archived" **is** soft-deleted here.
`db/repositories/appointment_types.py:24-32` filters `tenant_id`, `id`, `deleted_at IS NULL`. `models/appointment_type.py:12`: *"Soft delete = archive: E3 bookings reference types by id + snapshot."*
**Reading**: the spec's "returns `None` for an unknown or archived type" is exactly right, and the service's step 3 needs no extra predicate. `create_booking:332-334` already maps that `None` to `BookingNotFoundError` and F50 copies it verbatim.

### DR-4 — `OwnerBookingRow` already carries a precedent for the D18 exception F50 is about to take again.
`booking/schemas.py:136-158`. `checked_in_at` (F34) sits on the row with a five-line comment arguing why — *"On the ROW and not only the detail, because the shift board only ever reads the list."* `source` is the second such addition and the spec's Risk 6 already records the erosion.
**Reading**: write `source`'s comment in that same shape — one sentence on why the row and not only the detail, pointing at D8. A reviewer comparing the two should see one pattern, not two exceptions.

### DR-5 — smaller confirmations
| Spec claim | Verified | Note |
|---|---|---|
| `0008:69-70` terms columns are plain NOT NULLs, only CHECK is inline `> 0` | ✅ verbatim | conflict-table row 2 stands |
| the only `ADD CONSTRAINT`s in 24 migrations are `staff_users_*`, `customers_marketing_*`, `payments`, `tenant_gateway_credentials`, `provider` | ✅ `grep -rn "ADD CONSTRAINT"` | no terms CHECK exists to lean on |
| both F20 CHECKs are on **`customers`** | ✅ `0024:62`, `:70` | the walk-in path writes no `customers` column, so both are satisfied trivially and no `IntegrityError` path exists |
| `MarketingConsentSource` has one member and its docstring refuses F33's stronger case | ✅ `constants.py:203-217` | D3(b)'s "no field at all" stands |
| `record_marketing_consent` carries `AND marketing_consent_at IS NULL` in the WHERE | ✅ `customers.py:185-218` | an existing consent and its original timestamp survive untouched |
| `list_confirmed_without_manage_token` predicate | ✅ `bookings.py:744-762` verbatim | |
| `_guard_live` refuses `starts_at <= now` | ✅ `owner.py:1106-1128` | |
| `insert`'s docstring carries the advisory-lock precondition (`:113-119`) and names this feature (`:117-119`) | ✅ *"F15's owner-side reschedule is the next caller; owner-side creation is out of F15 (Interview Q6) and belongs to the owner-created-bookings spec"* | D5's separate writer is what keeps that docstring true — and R-5 updates the sentence, because F50 *is* that spec |
| `SPEC_ERROR_CODES` is set equality | ✅ `test_booking_owner_api.py:117` | F50 adds no member |
| `EmptyState` has an `action?: ReactNode` slot | ✅ `packages/ui/src/components/EmptyState.tsx:4-9` | the spec's placement argument was corrected to its real ground |
| `i18n.test.ts` per-feature floors | ✅ `:252`, `:330`, `:492`, `:592`, `:627`, `:768`, `:1073`, `:1277` | `HE_F50` gets one |

---

## 2. Migration `0025_walk_in_bookings.py` — column by column

Raw SQL in the 0011/0015/0024 house style. **No new table. No index. No GRANT. No RLS call. No trigger.** Each absence is argued in the spec's D1 and the reasons are not repeated here — but the *test* that each absence is real is in §4.

```python
revision = "0025"          # ⚠ re-resolve from `alembic heads` on the rebased branch
down_revision = "0024"
```

### Column on `bookings`

| Column | Type | Null | Default | Why |
|---|---|---|---|---|
| `source` | `TEXT` | no | `'storefront'` | The **discriminator the terms CHECK needs**, not a label. Without it a NULL `terms_version_accepted` has two indistinguishable meanings and only one of them is legal. `NOT NULL DEFAULT` is metadata-only in PG 11+ (non-volatile default, no rewrite), and the default is what makes the terms CHECK true of 100 % of existing rows with **no backfill UPDATE** — every row that exists today was created by the storefront. `0017`'s `tags TEXT[] NOT NULL DEFAULT '{}'` is the precedent. |

### Columns widened on `bookings`

| Column | From | To | Why |
|---|---|---|---|
| `terms_version_accepted` | `INTEGER NOT NULL CHECK (> 0)` | `INTEGER NULL CHECK (> 0)` | Dropping NOT NULL never fails on existing data and never rewrites. **The inline `> 0` CHECK is deliberately untouched** — a CHECK over NULL evaluates to NULL, not FALSE, so it passes on a walk-in row; hunting its Postgres-generated name to drop and re-add buys nothing. |
| `terms_accepted_at` | `TIMESTAMPTZ NOT NULL` | `TIMESTAMPTZ NULL` | ditto |

### CHECK constraints — exactly two, both NAMED, both their own statement

Named and separate is the 0011/0015/0024 shape: an inline CHECK on `ADD COLUMN` takes a Postgres-generated name, and the remote half's widening (`'owner'`) then depends on guessing it.

```sql
ALTER TABLE bookings ADD COLUMN source TEXT NOT NULL DEFAULT 'storefront';

ALTER TABLE bookings ADD CONSTRAINT bookings_source_check
  CHECK (source IN ('storefront','walk_in'));

ALTER TABLE bookings ALTER COLUMN terms_version_accepted DROP NOT NULL;
ALTER TABLE bookings ALTER COLUMN terms_accepted_at DROP NOT NULL;

-- ⚠ THE EXEMPTION IS ENUMERATED, NOT THE REQUIREMENT.
ALTER TABLE bookings ADD CONSTRAINT bookings_terms_evidence_check
  CHECK (source = 'walk_in' OR
         (terms_version_accepted IS NOT NULL AND terms_accepted_at IS NOT NULL));
```

**The direction is the whole design of the second constraint.** Written the other way round — `source <> 'storefront' OR (…)` — it says the same thing today and the **opposite** thing tomorrow: the remote/scheduled half adds `'owner'` to `bookings_source_check` and would silently inherit a terms exemption it must not have. Written this way, a third source value is a **failing INSERT** until its author decides about terms on purpose. That is the hand-off to the second half of F50, and §4's `source='owner'` test is what pins it.

Ordering matters and is not cosmetic: `ADD CONSTRAINT` validates existing rows, so the terms CHECK must be added **after** the two `DROP NOT NULL`s (it is satisfied either way, but the statement order is what makes the "no backfill UPDATE" claim checkable by reading the file top to bottom).

### `downgrade()` — ships, and is **deliberately able to fail**

```sql
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_terms_evidence_check;
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_source_check;
ALTER TABLE bookings ALTER COLUMN terms_accepted_at    SET NOT NULL;   -- raises on a walk_in row
ALTER TABLE bookings ALTER COLUMN terms_version_accepted SET NOT NULL; -- raises on a walk_in row
ALTER TABLE bookings DROP COLUMN IF EXISTS source;
```

No pre-clean, no `IF EXISTS` on the two `SET NOT NULL`s. On a table holding any walk-in row they raise, and **that is the refusal**: the only ways to make them succeed are to `DELETE` real appointment records or to stamp terms evidence nobody gave, and this feature exists because the second is not allowed. F57's `test_the_downgrade_refuses_to_narrow_past_a_floor_role_row` (`test_migrations.py:352`) is the precedent, and its docstring the argument — *"a lenient downgrade leaves the database describing a state its own schema forbids."* Both halves are pinned in §4: a round-trip with no walk-in rows, a raise with one.

### The ORM half, which is not optional

`models/booking.py` declares every column explicitly and nothing derives a mapping from a migration. Three edits at `:48-49` and one addition:

```python
source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'storefront'"))
terms_version_accepted: Mapped[int | None] = mapped_column(Integer, nullable=True)
terms_accepted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
```

---

## 3. Ordered task list

Each task is **one TDD cycle: the named failing test first, then the code that makes it pass.** Backend before frontend throughout — the frontend needs settled API shapes.

The migration is **written at A1 but committed LAST** (§5). Everything from A2 on assumes the columns exist locally.

⚠ **Sites P1 and P2 (the privacy 500) must land in the same commit as the migration.** A build that splits them ships a green suite and a 500 on the one route the Privacy Protection Authority is the audience for. The privacy regression test (T-P) is written **before** the migration.

### Phase A — schema and model

| # | Task | Test first | Files |
|---|---|---|---|
| **A1** | Migration 0025: one column, two named CHECKs, two dropped NOT NULLs, the refusing downgrade. | `test_migrations.py::test_the_terms_evidence_check_exempts_only_walk_in` (**db**) — a `storefront` row with NULL terms is rejected, a `walk_in` row with NULL terms is accepted | `Backend/migrations/versions/0025_walk_in_bookings.py` |
| **A2** | `Booking` model: `source` added, both terms columns nullable. | `test_boutique_models.py` model-import smoke — the ORM round-trips a NULL-terms `walk_in` row | `Backend/app/models/booking.py` |

### Phase P — the ripple, before anything new reads it

**This phase exists because the migration breaks shipped code, and two of the breaks are 500s on a legally-mandated route.** It is second, not last.

| # | Task | Test first | Files |
|---|---|---|---|
| **P1** | `privacy/service.py:237` — `versions = sorted({row.terms_version_accepted for row in bookings})` raises `TypeError: '<' not supported between instances of 'NoneType' and 'int'`. Add `if row.terms_version_accepted is not None` to the comprehension. | **T-P** below (**db**) | `Backend/app/privacy/service.py` |
| **P2** | `privacy/schemas.py:125-126` — `ExportedBooking` is a plain `BaseModel` constructed explicitly at `service.py:289-290`, so `None` is a `ValidationError` → 500. → `int \| None` / `datetime.datetime \| None`. The §13 export must show the absence honestly. | ditto | `Backend/app/privacy/schemas.py` |
| **P3** | `booking/schemas.py:205-206` — `OwnerBookingDetail` terms fields → `int \| None` / `datetime \| None`. `owner_router.py:139-140` needs no edit (already a pass-through). | `test_booking_owner_api.py` — a walk-in detail serialises | `Backend/app/booking/schemas.py` |
| **P4** | `booking/manage.py:225` — narrow with an **explicit `if booking.terms_version_accepted is None`** branch, never a cast. Unreachable at runtime (a walk-in has no token, D2), but unreachable-by-construction plus `# type: ignore` is how a static guarantee becomes a runtime crash the day someone mints a deliverable token. | mypy; no runtime test — see §4's structural note | `Backend/app/booking/manage.py` |
| **P5** | `booking/owner.py:308` — same treatment inside `payments_for`'s `if payment.status == PAID` block: an explicit `is None` `continue`, not a cast. A walk-in has no `payments` row at all (D4). | ditto | `Backend/app/booking/owner.py` |

### Phase B — the write path

| # | Task | Test first | Files |
|---|---|---|---|
| **B1** | `BookingsRepository.insert_walk_in`, beside `insert`. Takes `tenant_id, customer_id, appointment_type_id, appointment_type_name, at`. Writes `source='walk_in'`, `starts_at=at`, `checked_in_at=at`, `seat_index=1`, terms NULL, `manage_token_hash` NULL, `dress_*`/`notes` NULL. **Not** defaulted arguments on `insert` — its docstring carries an advisory-lock precondition this caller deliberately does not satisfy, and folding a lock-free caller into it is how that docstring stops being true. Carries the `# ponytail:` ceiling comment on `seat_index = 1`. | `test_bookings_db.py::test_insert_walk_in_writes_one_instant_across_starts_at_and_checked_in_at` (**db**) | `Backend/app/db/repositories/bookings.py` |
| **B2** | `AuditAction.BOOKING_WALK_IN_CREATED = "booking_walk_in_created"`. `audit_log.action` is plain TEXT with no CHECK (`0003_auth.py:71-79`) — **no migration**. | `test_booking_owner_service.py` (**db**) — the audit row exists with `actor_id`, `entity`, both ids in `details`, and **no phone and no name** | `Backend/app/models/constants.py` |
| **B3** | `OwnerBookingService.create_walk_in`. One `tenant_session`. `now = self._now()` once. `customers.by_id` → None **or** `erased_at is not None` ⇒ `BookingNotFoundError`; `types.by_id` → None ⇒ the same; `insert_walk_in`, `IntegrityError` ⇒ `SlotUnavailableError`; audit row in the same transaction; return `OwnerMutation(booking=…, changed=True, manage_token=None)`. `__init__` gains `self._types = AppointmentTypesRepository()`. **No `_transition` five-step shape** and **deliberately not idempotent**. | `test_booking_owner_service.py` (**db**) — the six cases in §4 | `Backend/app/booking/owner.py` |
| **B4** | `POST /manage/bookings/walk-in` on `owner_router.py`. Body `WalkInBookingRequest{customer_id, appointment_type_id}` (two required UUIDs, `ForbidExtraModel`). Renders through the existing `_detail_of`. **No route-level `dependencies=`** — it inherits the router's `(OWNER, SHIFT_MANAGER)` and does **not** join `OWNER_ONLY`. | `test_booking_owner_api.py` — route wiring, 401, the shift-manager 200 | `Backend/app/booking/owner_router.py`, `Backend/app/booking/schemas.py` |
| **B5** | `OwnerBookingRow` gains `source: str`; `_row_fields` (`owner_router.py:100-119`) gains one line. Comment in F34's `checked_in_at` shape (DR-4). | `test_booking_owner_api.py` — **the two full-dict `==` literals red-fail first and are updated as a visible edit** | `Backend/app/booking/schemas.py`, `Backend/app/booking/owner_router.py` |

### Phase F — frontend

| # | Task | Test first | Files |
|---|---|---|---|
| **F1** | `api.ts` types: `OwnerBookingRow.source: string` (required); `OwnerBookingDetail` terms → nullable (`:375-376`); **separately** `ExportedBooking` terms → nullable (`:1056-1057`, type-only, no renderer — do **not** merge the two interfaces); `WalkInBookingRequest`; `createWalkInBooking`. | typecheck — **and it reds five test factories at once**, which is the point | `Frontend/apps/manage/src/api.ts` |
| **F2** | The five factories gain `source: "storefront"`: `BookingsSection.test.tsx:24`, `BoardSection.test.tsx:34` + `:50`, `BookingDetail.test.tsx:54` + `:81`. | this *is* the test edit; `pnpm build` green is the gate | those three files |
| **F3** | `BookingDetail.tsx:365-372` — the **single** `<Fact label={t("booking.terms")}>` gains a second body: existing contents when `terms_version_accepted !== null`, `t("booking.termsNone")` otherwise. One Fact, two bodies. | `BookingDetail.test.tsx` — a walk-in detail renders `booking.termsNone` and neither the version nor the date | `Frontend/apps/manage/src/components/BookingDetail.tsx` |
| **F4** | `WalkInDialog.tsx` — new, the only new component. `Modal` from `@boutique/ui`, `RescheduleDialog`/`SosRaiseDialog` shape. Three steps in one dialog: search `Input` → `api.listCustomers({ q, offset: 0, limit: 10 })` debounced, radio list with `<fieldset>`/`<legend>`; `Select` from `api.listAppointmentTypes()` fetched once on open; confirm Button disabled until both chosen. Six states per the spec. | `WalkInDialog.test.tsx` — new | `Frontend/apps/manage/src/components/WalkInDialog.tsx` |
| **F5** | `BoardSection.tsx` — one `<Button variant="secondary">` «תור חדש» **outside the `Card`**, between the freshness bar and the `role="status"` cue, when `rows !== null && terminal === null`; one `useState`; one `create` handler copying `mutate`'s discipline (`:229-285`) with `poll.refresh()` **and the `let terminated` guard** (D9). One muted `booking.sourceWalkIn` word beside the type name in the `attendance_confirmed_at` treatment (`:551-554`). | `BoardSection.test.tsx` extended | `Frontend/apps/manage/src/components/BoardSection.tsx` |
| **F6** | `he.ts` + `ar.ts`: ~14 `walkin.*` keys plus `board.newWalkIn`, `booking.termsNone`, `booking.sourceWalkIn`. Flat dotted literals. `ar.ts` takes the Hebrew as values (Interview Q3 / pre-decided #47). | `i18n.test.ts` — see F7 | `Frontend/apps/manage/src/i18n/` |
| **F7** | `i18n.test.ts` — **`const HE_F50 = entries(he.translation, (key) => key.startsWith("walkin."))`, spread into `HE`**, plus a `toBeGreaterThanOrEqual` floor and a register block. Without the spread all ~14 keys are invisible to the resolve check, both register guards and the ar-presence guard, and the file's own comment says so: *"A block declared and not spread is skipped silently and greenly."* | the block itself | `Frontend/apps/manage/src/__tests__/i18n.test.ts` |
| **F8** | E2E + axe. | `frontend/e2e/` — see §4 | — |

---

## 4. Test inventory — with `db` marks and, for every test, the SINGLE-LINE DELETION that makes it RED

**db-marked tests run locally.** `Backend/tests/conftest.py:84-112` accepts `TEST_POSTGRES_SUPERUSER_URL` to override Testcontainers. Running them before pushing is what has produced first-run-green CI on this project.

```
# Homebrew PG16 is up on 5432 (prior features left f33_test … f59_test behind):
export TEST_POSTGRES_SUPERUSER_URL=postgresql+asyncpg://postgres@127.0.0.1:5432/postgres

# or a throwaway cluster:
initdb -D /tmp/pg16/data -U postgres --auth=trust
pg_ctl -D /tmp/pg16/data -o "-p 55432" -l /tmp/pg16/log start
export TEST_POSTGRES_SUPERUSER_URL=postgresql+asyncpg://postgres@127.0.0.1:55432/postgres
```

It must be a **superuser** URL — `app_role_url` derives a non-superuser from it, and running the suite *as* a superuser bypasses RLS, which makes every isolation assertion pass vacuously.

⚠ **`test_config.py` shows two false local failures** — `Backend/.env` leaks `MEDIA_BUCKET`. Known, recorded in `.memory`, CI is green. Do not chase them.

### Migration — `test_migrations.py`, all **db**

| Test | Asserts | **Single-line deletion that reds it** |
|---|---|---|
| `test_source_defaults_to_storefront_on_every_pre_existing_row` | On a table **populated before** the migration, every row reads `'storefront'`. | `DEFAULT 'storefront'` from the `ADD COLUMN` line. (Deleting `NOT NULL` alone would *also* red it — the column would be NULL, not `'storefront'`.) |
| `test_the_terms_evidence_check_exempts_only_walk_in` | `storefront` + NULL terms **rejected**; `walk_in` + NULL terms **accepted**; `storefront` + real terms accepted; `walk_in` + real terms accepted. All four. | the whole `ADD CONSTRAINT bookings_terms_evidence_check` statement. |
| `test_the_terms_evidence_check_refuses_an_undeclared_source` | `INSERT … source='owner', terms NULL` raises. **This is the hand-off to F50's second half asserted as behaviour.** | flipping the CHECK to `source <> 'storefront' OR (…)` — the exact inversion D1 declined. ⚠ **This is the only test in the feature that can tell the two directions apart**, because they are equivalent on every value that exists today. Without it D1's central argument is untested prose. |
| `test_the_source_check_rejects_a_third_value` | `source='queue'` raises. | the whole `ADD CONSTRAINT bookings_source_check` statement. |
| `test_both_new_constraints_are_droppable_and_re_addable_by_name` | `DROP CONSTRAINT bookings_source_check` then re-add succeeds; same for the terms one. The `_constraint_accepts` idiom (`:107-134`). | replacing either `ADD CONSTRAINT <name>` with an inline `CHECK` on the `ADD COLUMN` — the generated name makes the drop fail. |
| `test_the_inline_positive_version_check_still_binds` | `terms_version_accepted = 0` on a **storefront** row still raises; `= NULL` on a walk-in row does not. | any edit that drops or re-adds the inline `> 0` CHECK. Proves the spec's "a CHECK over NULL is not FALSE" claim rather than asserting it in prose. |
| `test_the_status_check_and_both_partial_unique_indexes_survive` | `pg_get_constraintdef` for the status CHECK and `pg_indexes.indexdef` for `idx_bookings_slot_seat_unique` and `idx_bookings_tenant_customer_starts_unique`, **re-pinned against literals after 0025**. F34's test extended, not re-invented. | any stray `DROP INDEX`/`ALTER … DROP CONSTRAINT` the migration might grow. **Structural** — it exists to catch a line that is not there, so it cannot be reddened by deleting one. What proves it bites: temporarily add `op.execute("DROP INDEX idx_bookings_slot_seat_unique")` to the migration and watch it red, then remove it. Do this once, at build time. |
| `test_migration_0025_round_trips` | `downgrade()` then `upgrade()` on a table with **no walk-in rows**. | the `DROP COLUMN IF EXISTS source` line in `downgrade()`. |
| `test_the_downgrade_refuses_to_narrow_past_a_walk_in_row` | Seed one `walk_in` row with NULL terms; `downgrade()` **raises**. `test_migrations.py:352`'s idiom. | adding a pre-clean (`DELETE FROM bookings WHERE source='walk_in'`) or a `SET DEFAULT`-then-`UPDATE` to `downgrade()` — i.e. the two lenient forms this plan declined. Deleting the `SET NOT NULL` line makes it red too. |
| `test_every_tenant_id_table_has_forced_rls` | **Unedited.** Staying green is the assertion that no table snuck in. | n/a — it is the *absence* proof. Named here so nobody "helpfully" edits it. |

### Repository — `test_bookings_db.py`, **db**

| Test | Asserts | **Deletion that reds it** |
|---|---|---|
| `test_insert_walk_in_writes_one_instant_across_starts_at_and_checked_in_at` | `starts_at == checked_in_at == at`, exactly. Passing `at` in rather than reading a clock twice is the invariant. **`created_at` is deliberately not compared** — it is a `now()` server default (`models/base.py:21-23`), i.e. transaction-start time, and under the injected `_clock` the two are years apart. | `it[checked_in_at] = at` → any other expression, e.g. re-reading `datetime.now()`. |
| `test_insert_walk_in_writes_source_and_null_terms` | `source == 'walk_in'`, both terms columns NULL, `manage_token_hash` NULL, `seat_index == 1`. | the `source="walk_in"` kwarg (the DB default would make it `'storefront'` and the row would then violate `bookings_terms_evidence_check` — so this one fails **twice over**, which is the constraint doing its job). |
| `test_two_walk_ins_at_a_forced_identical_instant_raise_on_the_slot_index` | Same tenant, **different** customers, `at` forced identical → `IntegrityError` from `idx_bookings_slot_seat_unique`. | the index is 0008's; **structural**. What proves it bites: it is a positive assertion that an exception *is* raised, so a vacuous pass is impossible — either the second insert raises or the test fails. |
| `test_two_walk_ins_for_one_customer_at_a_forced_identical_instant_raise_on_the_customer_index` | Same tenant, **same** customer, `at` forced identical → `IntegrityError` from `idx_bookings_tenant_customer_starts_unique`. Separate test so the two indexes are told apart rather than one covering for the other. | ditto. ⚠ **Force the timestamp explicitly.** Two natural `insert_walk_in` calls are microseconds apart and neither index binds — a test that "passes" by never colliding would be the third instance of this repo's seeded-fixture failure mode. |

### Service — `test_booking_owner_service.py`, **db**

| Test | Asserts | **Deletion that reds it** |
|---|---|---|
| `test_create_walk_in_returns_a_checked_in_confirmed_row` | Happy path; `status == 'confirmed'`, `checked_in_at` set, `manage_token` is `None` on the `OwnerMutation`. | `checked_in_at=at` in `insert_walk_in`'s call. |
| `test_an_unknown_customer_is_a_404` | `BookingNotFoundError`. | the `if customer is None: raise BookingNotFoundError` line. |
| `test_an_erased_customer_is_the_same_404` | Seed a customer with `erased_at` set → `BookingNotFoundError`, and **no `bookings` row was written**. | the `or customer.erased_at is not None` clause. ⚠ The row-count assertion is what makes this bite: without it, an implementation that creates the booking *and then* raises would pass. |
| `test_an_unknown_type_is_the_same_404` | ditto, indistinguishable by design. | the `if type_row is None` line. |
| `test_an_archived_type_is_the_same_404` | Soft-delete the type (= archive, DR-3) → 404. | `AppointmentType.deleted_at.is_(None)` from `by_id` — a shipped line, so this test guards a **dependency** rather than F50's own code. Named as such. |
| `test_the_audit_row_carries_both_ids_and_neither_the_phone_nor_the_name` | One `audit_log` row, `action == 'booking_walk_in_created'`, `actor_id == staff.id`, `entity == str(booking.id)`, `details` keys exactly `{customer_id, appointment_type_id}`. | the `await self._audit.insert(...)` call. The **key-set equality** is what catches a well-meaning later addition of `customer_name`. |
| `test_no_customers_row_is_written_and_an_existing_consent_is_unchanged` | Seed a customer with `marketing_consent_at` set; after the create, `marketing_consent_at` is **byte-identical** and `marketing_consent_withdrawn_at` is still NULL. | adding any `record_marketing_consent` / `withdraw_marketing_consent` call to `create_walk_in`. ⚠ **Seed the consent.** Against a customer with NULL consent, "unchanged" is NULL-to-NULL and the assertion passes on a path that clears it — the vacuity this repo has shipped before. |
| `test_no_scheduled_message_is_created` | Zero `scheduled_messages` rows for the new booking id. | any `upsert_reminder` call. **Structural**; armed by asserting `== 0` against a booking that exists, not against an empty table. |
| `test_manage_token_hash_is_null` | The row's `manage_token_hash` is NULL. | the absence of a `mint_manage_token()` call — structural, same shape. |

### The four disarm assertions — **db**, and the highest-value tests in the feature

Each pins a **shipped** predicate against a walk-in row, so a future edit to any of the four collides with a test instead of with a bride.

| Test | Asserts | **Deletion that reds it** |
|---|---|---|
| `test_the_backfill_feed_does_not_return_a_walk_in` | Create a walk-in, then call `list_confirmed_without_manage_token(after=<a later instant>)` → the walk-in is absent, **and a seeded future storefront booking with a NULL hash IS present**. | `Booking.starts_at > after` from `bookings.py:751`. ⚠ **The second half is what arms it.** Without the present-row, widening the filter adds no rows to an empty result and the test passes on nothing — the exact defect this repo has shipped. |
| `test_resend_link_on_a_walk_in_is_409` | `POST /manage/bookings/{id}/resend-link` → 409 `BOOKING_TRANSITION_INVALID`. | `if booking.starts_at <= now: raise BookingTransitionInvalidError` at `owner.py:1128`. |
| `test_phone_correction_on_a_walk_in_is_409` | `POST /manage/bookings/{id}/phone` → 409. Separate test: the two routes share `_guard_live` today and **must be asserted independently**, or a later feature that gives one its own guard silently loses the other's coverage. | the same line — deliberately. The value is the pair, not the line. |
| `test_cancel_is_409_and_no_show_and_complete_are_200` | Three calls on one walk-in row. Cancel 409 (future-only), `no-show` 200, `complete` 200. | `owner.cancel`'s future-`starts_at` guard. The two 200s are what prove the row is a *usable* booking rather than an inert one. |

### API — `test_booking_owner_api.py`, fast

| Test | Asserts | **Deletion that reds it** |
|---|---|---|
| the route joins `ROUTES` (`:96`) | 401 without a session; the walker covers it. | removing the tuple. |
| `SPEC_ERROR_CODES` (`:117`) **unchanged** | Set equality holds with no new member. | adding a new code to the service — a real result, not laziness. |
| the two full-dict `==` literals | `source` present on the list row; both terms fields nullable on the detail. | the `"source": booking.source` line in `_row_fields`. These literals red-fail on the new field **first**, and updating them is the visible reviewed edit. |
| `test_shift_manager_can_create_a_walk_in` | 200, positively asserted. | adding `dependencies=[Depends(require_role(StaffRole.OWNER))]` to the route. |
| `test_staff_role_gating.py` — **unedited** | The structural walker reads `allowed_roles` off the live route table, so the new route is policy-checked with no edit; the route is **absent** from `OWNER_ONLY`. | n/a — absence proof, same class as the RLS test. Named so nobody adds it to `OWNER_ONLY` "for consistency". |

### **T-P — the privacy regression, `test_privacy_subject_requests_db.py`, db. Written BEFORE the migration.**

| Test | Asserts | **Deletion that reds it** |
|---|---|---|
| `test_the_subject_export_survives_a_walk_in_booking` | A subject with **one storefront booking and one walk-in booking**: `POST /manage/privacy/subject-export` answers **200**, the walk-in's `terms_version_accepted` is `null`, the storefront one carries the real version, and the `terms` array carries **exactly the one version that exists**. | P1's `if row.terms_version_accepted is not None` guard (→ `TypeError` 500 from `sorted()`), **or** P2's `int \| None` (→ `ValidationError` 500 from the explicit `ExportedBooking(...)` construction at `service.py:289-290`). Two independent single-line reds, which is the correct shape for the feature's highest-risk edit. ⚠ **Both bookings are required.** With only a walk-in, the `terms` array is empty and the "exactly one version" assertion passes on nothing. |

### Structural sites with no runtime test, named rather than papered over

**P4 (`manage.py:225`) and P5 (`owner.py:308`) are unreachable at runtime** — a walk-in has no manage token and no `payments` row. They are narrowed with an explicit `is None` branch and their proof is **mypy**, not pytest. A runtime test would require constructing a state the product cannot produce, and faking it would assert the fake. What is asserted instead is that the branch exists and is typed: `mypy` fails on a cast or a `# type: ignore`, which is precisely why neither is used.

### Frontend — vitest

| File | Asserts | **Deletion that reds it** |
|---|---|---|
| `WalkInDialog.test.tsx` (new) | search debounces and renders results; **the empty-state copy is present and names the check-in code**; confirm disabled until both fields chosen; **the create body is exactly two keys** (`Object.keys(body)` equality — catches a later `notes` or `starts_at`); error copy comes from `bookingErrorText`. | the `disabled={customer === null \|\| type === null}` expression; the `walkin.empty` render. |
| `BoardSection.test.tsx` (extended) | the button renders in the **empty** state and in the **populated** state and **not** on the terminal screen; a successful create closes the dialog, fires **exactly one** extra fetch, writes the cue; **a 403 drives the terminal screen and issues NO further fetch** (D9's exception); no poll tick while in flight; exactly one armed after it settles, on success and non-terminal failure. | the `&& !terminated` clause in the `.finally()` — it reds the 403 no-further-fetch assertion specifically. The `rows !== null && terminal === null` render condition reds the three placement assertions. |
| `BookingDetail.test.tsx` (extended) | a walk-in detail renders `booking.termsNone` in the terms Fact and **neither** the version string nor the date. | the `terms_version_accepted !== null ?` ternary. |
| all three + `BookingsSection.test.tsx` | **five factories gain `source`**; `pnpm build` green is the gate. | n/a — this is a compile gate, and TS2739 is the red. |
| `i18n.test.ts` | `HE_F50` declared **and spread into `HE`**; its floor; the resolve check and both register guards reach the `walkin.*` keys; the ar-presence guard at `:1431-1434` covers them. | **the `...HE_F50` line in the `HE` array.** ⚠ This is the one that matters: deleting the *declaration* is a compile error and obvious; deleting the *spread* is silent and green, which is what the file's own comment warns about. The floor assertion (`expect(HE_F50.length).toBeGreaterThanOrEqual(14)`) is what makes the spread's absence visible. |

### E2E — Playwright + axe

Open the board, open the dialog, search an existing customer, create, see the row appear **already checked in**; axe clean on the open dialog; **Esc closes and focus returns to «תור חדש»**.

⚠ **The focus-trap, Esc and focus-return assertions belong to Playwright and NOT to vitest.** `setup.ts` stubs `HTMLDialogElement.showModal()` as `this.open = true` (jsdom has no `<dialog>`, `.memory/jsdom-has-no-dialog`), so a jsdom assertion about any of the three measures the stub and **cannot fail**. Every one of the spec's other dialog assertions is about *state*, not focus, and is valid in vitest.

---

## 5. Build discipline

**Commit shape.** The migration (A1), the ORM (A2) and the five ripple sites (P1–P5) are **one commit**, with T-P written first. Splitting them ships a green suite and a 500 on the §13 export. This is the review's first question.

**Rebase protocol.** Build the migration as `0025` and keep it the **last commit on the branch**. Immediately before the pre-push rebase, re-run `alembic heads` against rebased `main`; if a sibling took 0025, `git commit --amend` the one file. A reserved-but-wrong number breaks alembic outright and reds **every** db test (`.memory/parallel-alembic-numbering`).

**Pathspec.** Git tracks `backend/`/`frontend/` **lowercase** though the dirs are `Backend/`/`Frontend/`. `git add Backend/…` **silently skips modified tracked files**. Lowercase every pathspec and verify with `git show --stat` before pushing (`.memory/git-add-uppercase-pathspec-trap`).

**Merge-conflict hygiene.** A conflict-broken test file reads as one `Tests no tests` line, not N failures (`.memory/silently-unexecuted-test-files`). After any conflict resolution, parse every touched test file's collection count.

**Parallel sessions share this worktree.** Files and commits can change mid-task; a clean `git status` does not mean idle. Sweep with `find … -mmin` before touching a sibling area.

**Frontend build check.** `pnpm build` before staging any `.ts`/`.tsx` — F1 breaks five factories in three files and TS2739 is the whole signal.

---

## 6. Risks the plan discovered that the spec did not

**R-1 — `test_the_terms_evidence_check_refuses_an_undeclared_source` is the only proof of D1's central claim, and it is one line from being vacuous.** D1's constraint direction (`source = 'walk_in' OR …` rather than `source <> 'storefront' OR …`) is the feature's hand-off to its own second half, and the two spellings are **behaviourally identical on every value that exists today**. Only an insert with `source='owner'` — a value the source CHECK itself rejects, so the test must add it to the CHECK inside a savepoint or drop the source CHECK first — can tell them apart. If that test is written lazily (against `'walk_in'` and `'storefront'` only) D1 becomes untested prose and the remote half inherits a silent exemption. **Owner: this plan, task A1. Trigger: code review — read that one test's body, not its name.**

**R-2 — the two partial-unique-index tests can pass by never colliding.** `insert_walk_in` stamps microsecond-precise instants, so two natural calls never share a `starts_at` and neither index binds. A test that constructs its collision "naturally" is green forever and proves nothing. Both tests **must force an identical timestamp**, and the plan says so — but this is the third feature in a row where a seeded fixture would have made a filter test vacuous, and it is worth naming as a class rather than an incident. **Owner: this plan, task B1. Trigger: review of `test_bookings_db.py`.**

**R-3 — `source` on `OwnerBookingRow` is the second D18 exception in three features, and this plan makes it the second one with a comment explaining itself.** F34's `checked_in_at` has a five-line justification; `source` gets the same. The pattern is now "add a field, write a paragraph", which reads as discipline but is how a rule erodes with full ceremony. The spec's Risk 6 says the third addition should retire or restate D18 rather than exception it again; **this plan agrees and adds nothing to that**, but records that the comment-shaped exception is itself becoming the convention. **Owner: team. Trigger: the third addition.**

**R-4 — the frontend type widening has a silent failure mode the compile gate does not catch.** `pnpm build` reds on the required `source` (TS2739) — loud and immediate. But the *nullable terms* half is **assignable in the safe direction**: `number` fits `number | null`, so every existing factory, fixture and assertion compiles unchanged and nothing forces anyone to think about the NULL case. The only thing that surfaces it is `BookingDetail.test.tsx`'s new walk-in case, which is one test in one file. If that test is dropped or weakened, `BookingDetail.tsx` renders «גרסה null» to a staffer and nothing else notices. **Owner: this plan, task F3. Trigger: review — check that the walk-in detail case exists and asserts the absence of the version string, not merely the presence of `termsNone`.**

**R-5 — `insert_walk_in` and `insert` will drift.** Two writers on one table, one of which (`insert`) carries a docstring naming this feature as its next caller and is now wrong about that. D5's argument for the split is sound — a lock-free caller folded into a method whose docstring promises every caller holds the lock is how that promise dies — but the cost is that a future column added to `bookings` must be added in two places, and a `TypeError` on the second is the only signal. **Mitigation, cheap and taken**: `insert`'s docstring sentence *"F15's owner-side reschedule is the next caller; owner-side creation is out of F15 (Interview Q6) and belongs to the owner-created-bookings spec"* (`bookings.py:117-119`) is **updated in the same commit** to point at `insert_walk_in` and say why it is separate. Leaving a shipped docstring pointing at an unbuilt feature that has since been built is exactly the orphan-comment failure `.planning/plans/ppl-compliance.md` R-A records. **Owner: this plan, task B1.**

**R-6 — the E2E test needs a customer who already exists, and nothing in the feature creates one.** The walk-in dialog searches `customers`, and a `customers` row is created **only** inside `create_booking` after an OTP (`models/customer.py:12-15`). So the Playwright walk must either run a full storefront booking first (slow, and couples the F50 E2E to F19's deposit config and F13's OTP) or seed the row out of band. **Reading taken**: seed it, in the E2E fixture, and say in a comment that the seeding is standing in for an OTP flow the walk-in half deliberately does not have. **Owner: this plan, task F8. Trigger: the first E2E run.**
