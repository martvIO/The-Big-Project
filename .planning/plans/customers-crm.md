# Plan: Feature 53 — Customers CRM (Epic SMC, phase SMC-4)

**Status**: **Gate 2 self-approved** 2026-08-03 under the standing approval recorded in `interview-2026-07-30.md` §Standing approvals — Q1's stop-list is F17, F18, F19, F20, F29 and F48, and F53 is on none of them. **The design gate self-approves under Q2**: the screen is `SectionHeading` / `Card` / `Input` / `TextArea` / `Button` / `Badge` / `Skeleton` / `EmptyState`, every one exported from `packages/ui/src/index.ts` today (verified: `:7`, `:9`, `:11`, `:13`, `:15`, `:24`, `:26`, `:28`), and Q2 names exactly two novel patterns for this run — F34's shift board and F42's capacity matrix. F53 is neither. **No prototype and no `design-critic` pass**, the F19 and F57 precedent; the copy deck stays in the spec (D11) rather than being re-authored under `.planning/design/screens/`.

**Spec**: `.planning/specs/customers-crm.md` (Gate 1 self-approved 2026-08-03, D1–D12 + C1–C8, 1047 lines, adversarially reviewed) · **Branch**: `feature/customers-crm` · **Worktree**: `.worktrees/customers-crm` · **Created**: 2026-08-03

TDD throughout. Local gate per task: `make lint` + `make test` for backend tasks, `make fe-test` + `make fe-build` for frontend ones. **`db`-marked tests are run LOCALLY in this run — a Postgres 16.14 cluster is already up on port 55434 and is F53's to use.** See §"The local Postgres cluster", which is the highest-leverage section in this document.

F53 ships **one migration** — two `ALTER TABLE customers ADD COLUMN` statements, both additive, neither destructive — and **it does not ship last**. See **C1**, which is the only correction in this document that changes what gets committed, and the only one backed by a measurement rather than a `grep`.

**Path hygiene.** The repo path contains a space and a `+`. Quote every shell path. Git tracks `backend/` and `frontend/` **lowercase** while the on-disk directories are `Backend/` and `Frontend/`: `git add Backend/…` silently skips modified tracked files. Lowercase every pathspec and verify with `git show --stat`.

---

## Interview and spec rulings this plan is built on

| Ruling | Effect on the build |
|---|---|
| **Standing approval, `interview-2026-07-30.md` §Standing approvals** | Gate 1 and Gate 2 self-approve. D1–D12 are **positions already taken** and are not re-litigated here. Nothing in F53 is parked. |
| **Interview Q2 / the 2026-07-31 design ruling** — only F34 and F42 are novel | **No prototype, no `design-critic` pass, no user gate, and no `.planning/design/screens/manage-customers/` folder** (D11). The copy deck is §Hebrew copy deck of the spec and is binding from Task 7. |
| **Q3 / pre-decided #47 / the 2026-07-31 LANGUAGES ruling** (`LOOP-STATE.md:1138`) | Every new key lands in **both** `he.ts` and `ar.ts`, the `ar` value being the approved Hebrew verbatim, **never `""`**. `i18n.test.ts`'s `describe("the ar bundle")` (`:251-266`) enforces both halves. |
| **pre-decided #38** | IS 5568 / WCAG 2.0 AA is a **legal** requirement. Axe-clean and the two focus assertions are gates on Task 8, not polish. |
| **pre-decided #5** | Zero exclamation marks, enforced mechanically over `HE` at `i18n.test.ts:242-244`. |
| **The `/manage` real-verb convention** — `dashboard/router.py:38-39`, `auth/staff_router.py:27-30`, `booking/owner_router.py:15-17` | `GET` / `GET /{id}` / `PATCH /{id}`. **`.claude/rules/` is Kotlin/Micronaut boilerplate that does not describe this repo** — a `POST /list` here would be the first in the product. Do not propose one in review. |
| **The epic's Locked feature decisions** (`epics/shift-manager-console.md:32`) | *"CRM with notes + tags (`TEXT[]` on customers)"* — the column type is ruled, not chosen here. |

---

## What moved since the spec was written (2026-08-03 morning → 2026-08-03 afternoon)

The spec is hours old and **every one of its code citations still points at live code**. Two things moved, both in the program around it rather than in the tree it reads:

### The branch base moved, and it is docs-only

`origin/main` is now **`0c71702`**, four commits past the `877587c` the spec's Collision map names. All four are `.planning/` commits:

```
0c71702 docs(planning): F57 pr-open (PR #33) — all three gating jobs green first run
6216f35 docs(planning): loop — F53 started in parallel with F57, F33 and F19
1e4a080 docs(planning): F19 plan, design deck and copy deck — Gate 2 self-approved
295397f docs(planning): loop — F19 started in parallel with F57 and F33
```

`git diff --stat 877587c..origin/main` touches **four files, all under `.planning/`**. **No backend or frontend file moved.** That is why the verified-citations list below is as long as it is.

### F19 started building, and it changed two things F53 cares about

The spec's Collision map records F19 as **0 commits**. It now has **six**, and two of them land on seams F53 uses:

| | Spec said | Actually |
|---|---|---|
| F19 commits | 0 | **6** (`295248b` … `1387b92`) |
| F19 migration | "0017, renumbered" | **`0015_deposit_flow.py`, `revision = "0015"` / `down_revision = "0014"`** — i.e. F19 built against 0015, exactly as F57 did |
| F57 commits | 12 | **13** (`50ebc3d` is a review-round-1 fix commit) |
| F33 commits | 0 | **0** — unchanged, spec only |

Two consequences, and both are build constraints:

1. **`revision = "0015"` is claimed TWICE right now** — `0015_floor_roles.py` on F57 and `0015_deposit_flow.py` on F19. Different filenames, so git merges both cleanly and alembic then reports multiple heads at runtime. F19 shipped the guard for it (`test_exactly_one_migration_head`, `test_migrations.py:29`, **fast, not `db`-marked**). **F53 must not become the third claimant** — see C2.
2. **F19 broke `test_migrations.py`'s terminal-test convention.** On `origin/main` the file is 530 lines: `test_migration_0014_round_trips` at `:476` (its `finally: command.upgrade(cfg, "head")` at `:499`) and the fast `test_running_env_py_does_not_disable_the_app_logger` at `:502`, terminal. On F19's branch that fast test sits at `:564` with **three more `db` tests appended after it** at `:630`, `:670` and `:729`. The spec's instruction to append "between line 499 and line 502" is correct **against `origin/main`** and will not survive a rebase onto a merged F19 — see C3.

### Citations verified against the tree — ✅ do not re-verify

Everything in this list was read at `dece1f0` and says what the spec says it says.

- ✅ **`booking/validation.py:69` and `:70`, verbatim, and the split at `:62-68`.** `_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")` at **`:69`**; `_CONTROL_CHARS_EXCEPT_WS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")` at **`:70`**. Correction C1 of the spec is right: **tags import 69, notes imports 70.** ✅ `:40 MAX_CUSTOMER_NAME_LENGTH = 80`, ✅ `:45 MAX_BOOKING_NOTES_LENGTH = 500`.
- ✅ **`main.py`'s ordinal chain, every line.** `auth_router` `:1018`, `:1024` *"The fourth /manage router"*, `:1029` *"The fifth"*, `:1034` *"The sixth"*, `:1039` *"The SEVENTH"*, `gateway_router` `:1043`, `storefront_router` `:1046`, `:1055-1056` *"LAST, after every router"*, `_register_spas(app)` `:1057`. **F53 is the EIGHTH on `origin/main`.** File is 1061 lines.
- ✅ `main.py:143-144` (*"naming the required role would tell a probe which roles exist"*), `:145-148` (the two-key bodies), `:562` (`DashboardService` on `app.state`), `:738-745` with the comment *"House shape + 400 platform-wide … (no default 422s anywhere)"* at `:740-741`. **Correction C2 of the spec is right: there are no 422s.**
- ✅ `models/customer.py` — **19 lines total**, docstring `:11-13`, the three domain columns `:17-19`. `models/message_log.py:11-13` (Spam-Law), `:23-24` (*"never reaches a response body"*), `:26` (`booking_id` nullable). `models/booking.py:19-22` (the snapshot ruling; the column itself is at `:50`), `:54` (`notes`). `models/base.py:21-23` (`created_at server_default=text("now()")`).
- ✅ `models/constants.py:32-44` (`MessageKind` / `MessageStatus`), `:105`, `:109-112`, **`:129-134` the split criterion**, `:171 GATEWAY_LATE_SETTLEMENT`, `:174 PlatformAuditAction`. D8's seam is real and unoccupied.
- ✅ `db/repositories/customers.py` — 97 lines, `by_phone :14`, `by_id :24`, `by_ids :34`, `set_phone :49`, `upsert :77`; the UPDATE shape at `:63-75`.
- ✅ `db/repositories/message_log.py:10-11` (*"redundant defense-in-depth (house pattern — see StaffUsersRepository)"*), `list_by_phone :55-67` with its three predicates at `:60-64`.
- ✅ `db/repositories/bookings.py` — **761 lines, 20 methods**; `list_day`'s *"Every status, cancelled included"* at **`:578-581`**, the count shape at `:596-598`, `list_live_for_customer` at `:601-619`.
- ✅ `boutique/validation.py:1-6`, `:30 MAX_PROFILE_DESCRIPTION_LENGTH = 2000`, `:110` (*"Empty string = cleared field"*).
- ✅ `auth/staff.py:87-91` (`StaffNotFoundError`, bare-class raise) and all five `entity=str(...)` call sites (`:150`, `:241`, `:250`, `:271`, `:307`).
- ✅ `auth/staff_router.py:27-30` (real verbs, verbatim), `:62`, `:104-127`. ✅ `auth/router.py:13` `APIRouter(prefix="/manage/auth")`. ✅ `booking/owner_router.py:79`, **`:168-169` the query-bounds line verbatim**. ✅ `booking/owner.py:52-58` (`MAX_LIST_OFFSET = 1_000_000` restated + the asyncpg `int8_encode` reason), `:191-199` (the raise **outside** the `async with`). ✅ `booking/schemas.py:107-114` (D18's no-phone-on-row ruling). ✅ `dashboard/router.py:65`, `dashboard/schemas.py:3-5`, `dashboard/service.py:344-349`.
- ✅ `boutique/router.py:32`, `catalog/router.py:58`, `payments/router.py:29` — the exact string `prefix="/manage"`.
- ✅ `notifications/validation.py:43-45` (the `05…` → `972…` rewrite) and `:61-65` (`mask_otp_body`). ✅ `notifications/router.py:1,45,50-53`. ✅ `notifications/service.py:242-248` (the OTP write carries no `booking_id`).
- ✅ `core/config.py:7`, `:76-77` (`otp_send_max_per_phone_window`, `otp_send_phone_window_seconds`), `:250` (the `DEV_DATABASE_URL` fallback). ✅ `db/tenant.py:16-30`. ✅ `csrf.py:48` — the file really is `Backend/app/csrf.py`, `MUTATING_METHODS` frozenset at `:15`. ✅ `schemas.py:13-18` (`ForbidExtraModel`, `extra="forbid"`).
- ✅ `0008_bookings.py:46-50` (unique index + trigger), `:101-104` (**`idx_bookings_tenant_customer`**), `:107-110` (the GRANT/RLS loop). ✅ `0014_booking_check_in.py:22-36` — the "deliberately absent" block is a four-bullet `#   *` list, exactly the style D1 copies.
- ✅ **`grep -rn "ARRAY" Backend/app/models/` returns zero hits and `TEXT[]` appears in no migration.** `tags` really is the first array column in this codebase.
- ✅ `pyproject.toml`: `line-length = 100` `:47`, `select = ["E","F","W","I","UP","B","SIM"]` `:51`, `disallow_untyped_defs = true` `:55`, `warn_unused_ignores = true` `:56`, `asyncio_mode = "auto"` `:74`, markers `db` / `s3` `:75-78`. ✅ `uv.lock` resolves **SQLAlchemy 2.0.51**, so `icontains(..., autoescape=True)` exists.
- ✅ `test_tenant_isolation.py:203-230` keys on the **`tenant_id` column**, not a table list — its staying green unedited really is the assertion.
- ✅ **`test_spa_serving.py:372-400`**, verbatim, including `re.search(r'"\^/manage/\(([a-z|-]+)\)"', source)` and `assert set(match.group(1).split("|")) == expected`. ✅ And `test_spa_serving.py:312-321`'s docstring **names F53 by name**: *"F17, F52 and F53 each append an `include_router` to that function, and one added a line too far down would ship a storefront shell where an API used to be."*
- ✅ `test_staff_role_gating.py` — `OWNER_ONLY` at `:69-79` (nine constants), both walkers derive from `create_app(...)` + `_leaf_routes`, and the **`unenforced_owner_only`** label is real (declared `:192`, asserted `:210-211`). **The spec is right that this file needs no edit.**
- ✅ `test_dashboard_api.py:107-115` `_all_keys`; `test_staff_management_db.py:604-606` the `repr(...)` + `not in` value walk.
- ✅ `test_migrations.py` hardcoded downgrade targets: `:215 "0010"`, `:341 "0011"`, `:372 "0012"`, `:494 "0013"`. **Spec correction C4 is right — all four shipped round-trips hardcode.** `_check_in_column` at `:416-426`.
- ✅ Frontend: `App.tsx` **158 lines**, `NAV` `:48-72` with `board` at **index 7** (`:66`) and `staff` at **index 8** (`:67`, `roles: ["owner"]`), `gateway` index 9 (`:71`); the landing-section comment at `:59-65`; `SectionKey` `:18-28`; the flat `&&` render list `:145-154`. **Index 8 is the right insertion point and the two owner-only rows stay last.**
- ✅ `api.ts` — 697 lines, `:1-5` (no case conversion), `:308-312` / `:311` (`OwnerBookingDetail`), `:411-413` (`staffPath`), `:417-419`, `:549-559` (`listDresses`'s conditional-`q`), and **`listManageSlots` closes at `:656`**. `export const api = {` at `:493`; no method is `async`.
- ✅ `BookingsSection.tsx:27-49` (the `cancelled` effect), `:53-55` + `:53-82` (the in-panel swap and its ruling comment), `:72-78` (*"the row is patched from the response"*), `:86` (the `h2`), `:120` (`isolateLtr`).
- ✅ `BookingDetail.tsx:6`, `:11-15`, `:22-38` (`Fact` / `Instant` local helpers), `:76-82` (`NOT_FOUND` map), `:91-93` (heading focus), **`:103-115` the WCAG 2.4.3 scar**, `:423-427` (`role="alert"` + `tabIndex={-1}` + `ref`).
- ✅ `StaffSection.tsx:9-22` (`MAPPED_CODES`), `:139-148` (`validateStaffDraft` first), `:149-151` (*"Only what actually moved"*), `:209-211` (the raw `h2`). ✅ `ProfileSection.tsx:94` — `toast({...})` as a plain function.
- ✅ `lib/booking.tsx:1-5` (the cycle), `:10-14` (colour is never the only signal), `:22` `statusBadge` with its documented raw-value fallback at `:25`, `:32` `isolateLtr`.
- ✅ `he.ts` — **539 lines**, `:456-457` the «בוטל» comment, `:537` the last key, `:538` the closing `},`. **Append after `:537`.** ✅ `ar.ts` — **305 lines**, `:303` the last key, `:304` the closing `},`. **Append after `:303`.**
- ✅ `vite.config.ts` — 43 lines; the alternation at **`:18-19`** carries exactly **eleven** segments (`appointment-types|auth|availability|bookings|dashboard|dresses|gateway|settings|slots|staff|terms`); the prose at `:13` says *"The eleven names"* and `:16` *"a twelfth router"*. Both must be bumped.
- ✅ `Nav.test.tsx` — 191 lines; `NAV_LABELS` `:52-69` with `"לוח היום"` at `:64` and `"צוות"` at `:67`; **`.slice(0, 8)` at `:95` and `:148`**; the test names at `:84` (*"all ten sections"*) and `:91` (*"eight sections"*); the describe template at `:160-172`.
- ✅ `i18n.test.ts` — 266 lines; **`:247` is the copy guard `/נשלח|תישלח|בדרך/`**, `:242-244` the exclamation guard, `:39` `const HE = [...HE_F15, ...HE_F51, ...HE_F52, ...HE_F17, ...HE_F34];`, `:221-230` the WCAG-2.5.3 aria template, `:258` the `ar` empty-string reject, `:262` the `ar` key parity.
- ✅ `apps/storefront/src/validation.ts` — `:19` / `:20` exported numerics, **`:32` and `:34` bare `const` regexes**, both unexported. The two-declaration-forms warning in the spec is exactly right.
- ✅ `packages/ui`: `Skeleton`'s variants are `"text" | "image" | "block"` with **default `"block"`** — the spec's insistence on `variant="text"` is load-bearing. `SectionHeading` takes no `ref`. `tsconfig.base.json:10` `"isolatedModules": true`. `apps/manage/package.json:11` `"test": "TZ=America/New_York vitest run"`. `Frontend/e2e/` holds exactly two specs and no manage harness.
- ✅ **Nothing named `customers` exists yet**: no `Backend/app/customers/`, no `Backend/tests/test_customers_*.py`, no `CustomersSection.tsx`, no `CustomerDetail.tsx`.

---

## Nine corrections — resolved here, amended into the spec in Task 0

D1–D12 are **not** re-litigated. These are places where the document disagrees with the tree, or with itself. Every resolution is the smaller edit.

### C1 — the migration CANNOT be the last commit, and this is measured rather than argued

The spec's D1 says *"the migration is the LAST commit on the branch"* and its §Commit order puts it at **9**, with `models/customer.py`'s two `Mapped` lines at **3**. **Those two instructions are incompatible, and the cost is not theoretical.**

The moment `Customer.notes` and `Customer.tags` are mapped, every `select(Customer)` SQLAlchemy emits names both columns. Against a database that does not have them, every read of a customer raises `UndefinedColumn`. `customers` is read by the booking create path, the owner booking path and the OTP path, so this is not confined to F53's own tests.

**Measured, in this worktree, against the live cluster** — the two `Mapped` lines applied to `models/customer.py` with no migration, then `pytest -m "db and not s3"`:

```
114 failed, 239 passed, 1235 deselected            # ORM columns, no migration
353 passed, 1235 deselected                        # baseline, unmodified tree
```

**114 pre-existing `db` tests go red**, across `test_booking_service.py`, `test_booking_owner_db.py`, `test_booking_comms_db.py` and more — none of them F53's. Under the spec's ordering the branch would carry that from commit 3 to commit 9, and **the local cluster would be useless for exactly the tasks that need it most.**

**Resolution: the migration and the two ORM columns ship as ONE commit, and it is Task 2 — near the front, not last.** This is the `0008_bookings.py` / `models/booking.py` pattern, F34's Task 2 shape and F19's Task 2 rule verbatim (*"The halves ship together and this is not a preference"*).

**What the spec was actually protecting is preserved.** D1's stated reason for "last" is that *"any rebase costs one `git commit --amend` touching one file that nothing else references"*. The migration is still **one self-contained file that nothing imports**, so the rebase edit is still one file — it is reached with `git rebase -i` (or a `fix(migrations):` commit at the tip) instead of `--amend`. Thirty seconds, against 114 red tests and a dead local cluster for six tasks. **Task 9 keeps the renumber as an explicit, named step so it cannot be forgotten**, which is the other half of what "last" was buying.

### C2 — `revision = "0015"` is claimed twice already; F53 claims **0018** from the first commit

F57 ships `0015_floor_roles.py` (`revision = "0015"`, `down_revision = "0014"`) and F19 ships `0015_deposit_flow.py` (**the same `revision`**). Neither can see the other. F19 added the guard — `test_exactly_one_migration_head` at `test_migrations.py:29`, fast, filesystem-only.

F53 must not be the third. **Build the file as `0018_customer_crm_columns.py` with `revision = "0018"` / `down_revision = "0014"`.**

**A non-contiguous revision id is fine, and this was verified rather than assumed** — alembic follows the linked list, not the sequence:

```
$ uv run alembic heads      →  0018 (head)
$ uv run alembic history    →  0014 -> 0018 (head), …
                               0013 -> 0014, booking check-in: …
```

One head, no complaint. So the branch is coherent today, collides with nobody in flight, and **at rebase only `down_revision` changes** — one literal, exactly the promise D1 made. If a fourth feature has taken 0018 by then, `revision` and the filename move too. **Never hardcode either from this document: `cd Backend && uv run alembic heads` on the REBASED branch is the only source.**

### C3 — `test_migrations.py`'s seam moved on F19's branch, and the file has no module-level marker

Two things, both mechanical:

1. The spec says to append **"between line 499 and line 502"**. That is correct against `origin/main` (`:499` is `command.upgrade(cfg, "head")` closing `test_migration_0014_round_trips`; `:502` is the terminal fast test). **It is wrong the moment F19 merges** — F19 appended three `db` tests *after* that fast test, at `:630`, `:670`, `:729`. **Resolution: append after the last `*_round_trips` test and before `test_running_env_py_does_not_disable_the_app_logger` if that test is still terminal; otherwise append at the end of the file.** Do not chase a line number across a rebase.
2. **`test_migrations.py` carries no module-level `pytestmark`** — every `db` test in it declares its own `@pytest.mark.db` (`:22, 73, 96, 154, 192, 273, 293, 326, 352, 452, 475`), and `test_running_env_py_…` is deliberately unmarked. F53's appended tests each take their own decorator. (`test_customers_db.py` is a **new** module and does take `pytestmark = pytest.mark.db` at module level, as the spec says.)

### C4 — `postgres_url` is `:82-95`, not `:80-93`

The fixture the local-cluster edit targets is at **`Backend/tests/conftest.py:82-95`** (decorator `:82`, `def` `:83`, `yield` `:95`). It is `scope="session"`, and it **fails** rather than skips: `pytest.fail(DOCKER_HELP, pytrace=False)` at `:87`. `migrated_db` (`:97-125`) and `app_role_url` (`:128-131`) both derive from it, and `app_role_url` splits the URL on `@`, so the substituted URL **must contain a `user:password@host` form**. There is no `engine` fixture. Exact edit in §"The local Postgres cluster".

### C5 — three `test_frontend_constant_parity.py` line numbers are off

| Spec says | Actually |
|---|---|
| `_CONST_RE` at `:93` | ✅ correct — `^export const (?P<name>[A-Z][A-Z0-9_]*)\s*=\s*(?P<value>[0-9_]+);` |
| `_TS_REGEX_RE` at `:130` | **`:129`** — `^const (?P<name>[A-Z][A-Z0-9_]*)\s*=\s*/(?P<body>.+)/;`, i.e. `const`, **not** `export const` |
| the hardcoded assertion message at `:148` | **`:149`** — `assert ts_name in declared, f"storefront validation.ts does not declare {ts_name}"` (`:148` is the `for` header) |

Also: `MIRRORS` (`:53-91`) has **three** params today, **two of which already use `MANAGE_VALIDATION_TS`** (`id="manage"` with 11 catalog names, `id="manage-staff"` with 3 auth names, `id="storefront"` with 2 booking names). So `Frontend/apps/manage/src/validation.ts` **already exists** (363 lines) and F53 appends to it — the spec's *"the manage console mirrors no regex today"* is true of **regexes only** (`_MIRRORED_PATTERNS` at `:137-140` is storefront-only) and is not a claim that the file is new. F53's is the **fourth** `MIRRORS` param, as the spec says.

### C6 — `BookingDetail` has NO early null branch; the shape F53 copies is inline conditionals

The spec's §`CustomerDetail.tsx` item 0 cites *"`BookingDetail.tsx:219-242`'s shape"* for a "null branch". **There is no early return in that file.** The heading is at `:219-221`, the `role="status"` region at `:231-239`, the `loadError` alert at `:241-245`, and the `detail === null` handling is **inline**: `:197` (`const badge = detail === null ? null : statusBadge(detail.status);`), `:238` (the loading string), `:247` (`{detail === null && loadError === null && <Skeleton variant="text" lines={4} />}`).

**The spec's design intent is unaffected and is what `BookingDetail` actually does** — the back control, the heading, the announced region and the outage alert render unconditionally; only the data panels are suppressed. **Resolution: implement `CustomerDetail`'s null handling as inline conditionals in one return, not as an early `return`.** An early return would have to duplicate the heading and the back button, which is how the two builders the spec worries about end up with different screens.

### C7 — assorted citation drift, none of it changing a ruling

Corrected addresses only. A builder who greps for the quoted text will find it; a reviewer who opens the cited line will not.

| Spec cites | Actually |
|---|---|
| `customers.py:40-41` for *"`IN ()` is a syntax error in Postgres"* | the sentence is the docstring at **`:38-39`**; `:40-41` is the `if not customer_ids: return []` guard it justifies |
| `message_log.py:66` for the ASC order | `.order_by(MessageLog.created_at)` is at **`:65`**; `:66` is the closing paren. `insert` opens at **`:13`**, not `:14` |
| `auth/staff_router.py:22-27` for the `_no_store` decision of record | **`:21-25`** |
| `booking/owner_router.py:16-18` for the real-verb docstring | **`:15-17`** |
| `dashboard/router.py:15-16` for *"a both-roles route there reports as `unenforced_owner_only`"* | **`:14-15`**; `:16` is blank |
| `dashboard/router.py:38-40` for "real verbs **+ `_no_store`**" | `:38-39` is the real-verb sentence; **`_no_store` is not there** — the docstring note is `:28`, the `def` is `:55`, the wiring is `:67` |
| `app/errors.py:1-9` for the base classes | `:1-9` is the module docstring; **`DomainNotFoundError` is `:12`, `DomainValidationError` is `:18`** |
| `db/rls.py:14-18` for "a superuser bypasses FORCE RLS" | `:14-18` is the DDL list and says nothing about superusers. **FORCE RLS covers the table *owner*; the superuser guard lives in `app/db/session.py::ensure_safe_database_role`.** D3's conclusion is unchanged — the `DEV_DATABASE_URL` fallback at `config.py:250` is still a superuser connection and still bypasses RLS — but cite the right file |
| `notifications/validation.py:25` for `normalize_israeli_mobile` | `:25` is `_NORMALIZED_MOBILE`; the `def` is **`:31`**. The `05→972` rewrite at `:43-45` ✅ |
| `booking/owner.py:641-695` for F15's collision branch | the collision check + `CustomerAlreadyBookedError` is **`:615-623`**; `:639-648` is "7. The move", `:690-698` the audit row. The phone-path collision is `:777-780` |
| `booking/owner.py:802` as a `normalize_israeli_mobile` call site | `:802-804` is `set_phone(..., phone=normalized)` — a **consumer**. The only `normalize_israeli_mobile(` call in the file is `:756` ✅ |
| `0008_bookings.py:41-44` for the same-phone-two-tenants comment | **`:42-45`** |
| `0008_bookings.py:50` for the literal name `trg_customers_updated_at` | `:50` is `op.execute(_updated_at_trigger("customers"))`; the `trg_{table}_updated_at` name is templated in the helper at **`:25-27`** |
| `BookingsSection.tsx:157-158` for the `dir` ruling | the date field's `dir="ltr"` and its comment are **`:91-92`** |
| `BookingsSection.tsx:163` for `customer_name` | **`:161`** (`<bdi className="font-semibold text-ink">{booking.customer_name}</bdi>`), bare-`bdi` comment `:159-160` |
| `StaffSection.tsx:152-167` for the diff body | **`:152-164`**; `:165` is `try {` |
| `Nav.test.tsx:20-33` for the `vi.mock` factory | the factory is **`:10-35`**; `:20-33` is only the inner `api: {…}` member list. The `getDashboard` comment is `:27-30` ✅ |
| `main.py:72ff` for the router imports | they start at **`:15`**; `:72` is only `dashboard_router` |

### C8 — `InputProps.help` is `help?: string` (optional), not `string`

D11's argument is unchanged and still correct — an optional `string` is still a `string` and still cannot hold a `ReactNode`, so `isolateLtr` still cannot be used in a `help` slot. Recorded only so a reviewer checking the type finds the `?`.

### C9 — the local cluster exists, and the spec's Test-plan preamble is stale about it

The spec opens its Test plan with *"there is no Docker locally, so both `db` modules below are first exercised on the CI runner"* and Risk 6 budgets a red CI round for it. **A Postgres 16.14 cluster is already running on `127.0.0.1:55434` and both `db` modules can be run locally before the push.** Risk 6 shrinks from "budget one red round" to "budget one red round only if §The local Postgres cluster is skipped". Amended in Task 0.

---

## Scope fence — read this before every task

**F53 ships one screen that answers four questions about one person, and refuses a fifth.** It touches no money, no billing and no privacy-law text. It adds no table, no error code, no exception handler and no npm dependency.

### Four features, four worktrees, one tree

| Surface | Owner | Rule |
|---|---|---|
| `app/auth/`, `models/staff_user.py`, `db/repositories/staff_users.py`, `app/floor/`, `lib/roles.ts`, **`lib/usePoll.ts`**, `0015_floor_roles.py` | **F57** (`.worktrees/floor-staff-roles`, 13 commits, **PR #33 open**) | **DO NOT TOUCH.** Not one line, not a formatter pass, not an import re-sort. F53's debounce is six lines of `setTimeout`; it does **not** import `usePoll` (D10). |
| `app/payments/`, `app/storefront/`, `models/payment.py`, `db/repositories/payments.py`, `0015_deposit_flow.py`, `BookingStatus`, `PaymentStatus` | **F19** (`.worktrees/deposit-booking-flow`, 6 commits) | **DO NOT TOUCH.** F53 reads `bookings.status` as an opaque string and renders it through the shipped `statusBadge`; it must not learn about `pending_payment`. |
| `queue_tickets`, any `/checkin` route, `customers.marketing_opt_in_at` | **F33** (`.worktrees/qr-walkin-queue`, 0 commits, spec only) | **DO NOT TOUCH.** F33 appends to `models/customer.py` at the same anchor — see Risk 5 of the spec. Union, not overwrite. |
| `app/models/constants.py`, `app/main.py`, `test_migrations.py`, both apps' `i18n/{he,ar}.ts`, `App.tsx`, `api.ts`, `vite.config.ts`, `Nav.test.tsx`, `i18n.test.ts`, `validation.ts` | **SHARED** | **Append only.** Never reorder, never reformat, never re-wrap another feature's lines. Rebase on `main` before every push. |
| Migration revision id | **contested three ways** | Claimed at Task 2 as **`0018` / `down_revision = "0014"`** (C2). **Re-resolved from `alembic heads` at Task 9.** |

### Not in F53

| Not in F53 | Whose |
|---|---|
| Creating, renaming, merging or deleting a customer; editing `name` or `phone` | out of scope — a customer row is minted by the OTP flow only (`models/customer.py:11-13`), and `set_phone`'s one caller re-mints manage tokens (`booking/owner.py`) |
| `message_log.customer_id`, any rewrite of the log's write path | D3's residual, **Risk 1**, blocked on a backfill that cannot be correct |
| Any mutation of a message row — resend, delete, edit, mark-read | never; a mutable evidence trail is not evidence |
| The SMS log on the **booking** detail | recorded as a reduction against the epic; belongs to whichever feature next touches `booking/owner_router.py` |
| A controlled tag vocabulary, a tag-management screen, `GET /manage/customers/tags`, autocomplete | **D5**, three upgrade paths recorded |
| Filtering or sorting the list by tag; any index on `tags` | **D5** — no reader, no request |
| `pg_trgm`, any search index, any `message_log` index | **D2 / D3** — upgrade paths (and the BitmapOr *pair* rule) recorded in the migration comment |
| Reading `audit_log` | F15's D2, F51's D8, F52's D9 — written, not rendered |
| A customer count on the dashboard, or reconciling `total` with `dashboard.customers.total` | **different questions**; F52's Risk 9 asked F53 to define its own number, and D6 does |
| An e2e spec and a manage-console Playwright harness | **F58's** — there is no manage harness at all today (`Frontend/e2e/` holds two storefront specs) |
| Any edit to `test_staff_role_gating.py` or `test_tenant_isolation.py` | both staying green **unedited** is the assertion |

If a task's diff grows a staff role, a payment status, a queue ticket or a second poll target, it has left F53.

---

## The local Postgres cluster — the highest-leverage section in this plan

The run's standing constraint has been "no Docker locally", and `tests/conftest.py:87` **fails** (not skips) the whole `db` suite when the daemon is down. **F34's builder refused that and got all three gating jobs green on the first CI run; F57's builder followed it and did the same (PR #33, three green jobs, first run).** F53 has two `db` modules debuting at once and a query whose correctness is the entire feature. This is the run where the instruction pays.

**A throwaway cluster is ALREADY RUNNING and is F53's.** Nothing to install, nothing to initdb.

```
host      127.0.0.1
port      55434
user      postgres            (trust auth — any password is accepted)
database  boutique            (already created)
data dir  <scratchpad>/f53-pg
socket    -k /tmp             <- REQUIRED: the scratchpad path is longer than
                                 Postgres's 103-byte sun_path limit, so the
                                 default socket dir inside the data directory
                                 cannot be created. This is why the cluster was
                                 started with `-k /tmp`, and why you must connect
                                 over TCP (-h 127.0.0.1) rather than by socket.
binaries  /opt/homebrew/opt/postgresql@16/bin
version   PostgreSQL 16.14 (Homebrew)   <- matches postgres:16-alpine's major
```

Confirm it before Task 2:

```bash
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
psql -h 127.0.0.1 -p 55434 -U postgres -d boutique -c "select version();"
```

If it is not up, restart it — **never inside the repo**, or the data directory lands in `git status`:

```bash
PGDIR="<scratchpad>/f53-pg"
pg_ctl -D "$PGDIR" -o "-p 55434 -k /tmp" -l "$PGDIR/log" start
```

### The conftest escape hatch — LOCAL, UNCOMMITTED, and it is not for commit

`postgres_url` is **session-scoped and lives in a conftest**, so no plugin, fixture override or `-p` hook can replace it. The only way in is an edit to the file. **Five lines, every one carrying `# NOT FOR COMMIT`:**

```python
@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Real Postgres 16 via Testcontainers, connected as the container superuser.
    RLS behavior must be tested against the real engine — SQLite would lie to us."""
    import os  # NOT FOR COMMIT

    local = os.environ.get("LOCAL_TEST_PG_URL")  # NOT FOR COMMIT
    if local:  # NOT FOR COMMIT
        yield local  # NOT FOR COMMIT
        return  # NOT FOR COMMIT

    if not _docker_running():
        pytest.fail(DOCKER_HELP, pytrace=False)
    ...
```

`import os` is function-local deliberately — the file's own style (`from testcontainers.postgres import PostgresContainer` is function-local too) and it keeps the diff to one contiguous block that is trivial to delete.

Then:

```bash
export LOCAL_TEST_PG_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:55434/boutique"
cd Backend && uv run pytest -m "db and not s3" -q
```

**The `user:password@host` form is required, not cosmetic**: `app_role_url` (`conftest.py:128-131`) derives the non-owner URL by splitting `migrated_db` on `@`. A URL without one raises `ValueError` inside the fixture. Trust auth ignores the password, so `postgres:postgres` is fine, and the derived `boutique_app` login works the same way.

**`-m "db and not s3"` deliberately.** The `s3` marker (`pyproject.toml:77`) additionally needs the MinIO Testcontainer and **still requires Docker**. Those tests are not F53's and must be left to CI.

**Proven, not proposed.** This exact recipe was run in this worktree before this plan was written:

```
353 passed, 1235 deselected, 1 warning in 15.58s     # -m "db and not s3", local cluster
```

That is the **baseline** the branch must still show, plus F53's own.

### The cluster is PERSISTENT, and Testcontainers is not — two consequences

Testcontainers throws its database away between sessions. This one does not, and both differences can waste an hour:

1. ⚠ **`alembic_version` survives.** Once Task 2's migration has been applied, the cluster records `0018`. If you then run the suite from a checkout where `0018_customer_crm_columns.py` does not exist — a `git stash`, a bisect, a rebase mid-flight — `migrated_db`'s `command.upgrade(cfg, "head")` fails with *"Can't locate revision identified by '0018'"*. **It is not a bug in your migration.** Recover with `psql -h 127.0.0.1 -p 55434 -U postgres -d boutique -c "UPDATE alembic_version SET version_num = '0014'"`, or just `dropdb`/`createdb boutique` — it holds nothing but test rows.
2. ⚠ **Test rows accumulate across runs.** Every test must mint its own tenant id (the spec already requires this) and **every probe row must be rolled back**. A committed row that violates a later downgrade's constraint reddens a *different* feature's round-trip test in the same session — the F57 rule, and the reason `test_migrations.py`'s existing probes roll back.

### Before any commit

```bash
git diff --stat backend/tests/conftest.py     # MUST print nothing
```

**`git add -A` is BANNED in this worktree for the whole run.** Stage by explicit lowercase pathspec, always, and verify with `git show --stat` after every commit. One `git add -A` with the escape hatch in place ships a test-suite backdoor to `main`.

### Capture deparsed literals; never transcribe them

**F53 adds no CHECK, so there is no `pg_get_constraintdef` hazard — but it DOES assert column types and defaults through `information_schema.columns`, and `tags TEXT[] NOT NULL DEFAULT '{}'` does not come back looking like what you typed.** Run the query, paste the answer.

```sql
SELECT column_name, data_type, is_nullable, column_default, udt_name
  FROM information_schema.columns
 WHERE table_name = 'customers' AND column_name IN ('notes', 'tags')
 ORDER BY column_name;
```

Captured against the real cluster while this plan was written:

```
column_name | data_type | is_nullable | column_default  | udt_name
------------+-----------+-------------+-----------------+----------
notes       | text      | YES         | NULL            | text
tags        | ARRAY     | NO          | '{}'::text[]    | _text
```

`data_type` is the bare string **`ARRAY`** for *any* array column, which is why `udt_name == '_text'` is not padding — without it `text[]` and `int[]` are indistinguishable. Nobody would have typed `'{}'::text[]` or `_text` from the migration source. **Re-run it on your own cluster and paste what it prints.**

The same query also settles D1's no-rewrite claim empirically, and it is worth running once so the argument is a fact rather than a citation:

```
attname | atthasmissing | attmissingval
--------+---------------+---------------
notes   | f             |
tags    | t             | {"{}"}
```

`atthasmissing = t` with `attmissingval = {"{}"}` is exactly the PG 11+ mechanism D1 describes: the default is stored in the catalog and materialized lazily on read. **No table scan happened.**

### One mutation check, and it is on the claim that is the feature

Everything else in F53 is a screen. **D3's `AND booking_id IS NULL` is the part that can render one bride's name and appointment time on another bride's page.** A test that stays green when its mechanism is removed proves nothing, so prove it:

1. With `test_customers_db.py` green, **delete `MessageLog.booking_id.is_(None)` from the phone leg** of `MessageLogRepository.list_for_customer` — leaving `or_(booking_id.in_(...), phone == ...)`.
2. Re-run `pytest -m "db and not s3" -q`.
3. **The recycled-phone test MUST turn red, and nothing else may.** The expected failure is B's detail containing A's two lifecycle rows.
4. Restore the predicate. Confirm green.

If step 3 shows the recycled-phone test still passing, the fixture does not actually reproduce the recycle (most likely: A's phone was never moved with `set_phone`, or B was created before the correction). **Fix the fixture, not the assertion.** If step 3 shows *other* tests failing too, the phone leg is over-matching somewhere else and that is a second finding.

Record the result in the Task 10 run report. This is the one place in F53 where "the test passed" and "the code is right" are different sentences.

---

## Task 0 — This plan, and the nine spec amendments
`.planning/plans/customers-crm.md` (this file), `.planning/specs/customers-crm.md`

- Amend **D1** and **§Commit order**: the migration ships in the **same commit as the ORM columns**, at position 2, with C1's measurement (`114 failed` vs `353 passed`) stated in one line so the reversal reads as evidence rather than preference. Keep D1's *reason* — one self-contained file, one rebase edit — and point it at Task 9.
- Amend **D1** and the **Collision map**: the revision id is **`0018` / `down_revision = "0014"` from the first commit** (C2), with the note that `"0015"` is already claimed by both F57 and F19 and that a non-contiguous id is valid (`alembic history` → `0014 -> 0018 (head)`).
- Amend the **Collision map**: F19 has **6 commits**, F57 **13**, `origin/main` is **`0c71702`** and the four commits since `877587c` are docs-only.
- Amend the **Test plan**'s `test_migrations.py` paragraph with C3 — the seam is "after the last round-trip test", not a line number, and each appended test takes **its own** `@pytest.mark.db`.
- Amend the **Test plan** preamble and **Risk 6** with C9 — a local Postgres 16.14 cluster is available on 55434 and both `db` modules run before the push.
- Amend **§`CustomerDetail.tsx` item 0** with C6 — `BookingDetail` has no early null return; the shape is inline conditionals in one return.
- Correct the citations in **C7**'s table throughout the spec, and `postgres_url`'s range (C4) and the parity-test line numbers (C5).
- Add one sentence to **D11** recording that `InputProps.help` is `help?: string` (C8) — optional, still not a `ReactNode`.
- **Done when**: all nine are in the spec and this file is committed. No code, no tests.
- Commit: `docs(planning): F53 implementation plan — Gate 2 self-approved`

---

# Part I — the backend

## Task 1 — `app/customers/validation.py`, the pure module (TDD, fast) — D2, D5
`Backend/app/customers/__init__.py` (**new**), `Backend/app/customers/validation.py` (**new**), `Backend/tests/test_customers_validation.py` (**new**)

**First because it is the most independent thing in the feature** — no SQLAlchemy, no session, no app, no schema. It is also where the two corrections most likely to ship silently wrong live (C1's regex choice and D2's phone normalization), so it gets the first red test.

### RED — `test_customers_validation.py`, and what each case pins

`normalize_tags`:
- whitespace trimmed; empty elements dropped;
- **first occurrence wins and keeps its casing** — `["VIP", "vip", " Vip "]` → `["VIP"]`;
- **order preserved, never sorted** — asserted against an input whose sorted order differs, so an `sorted()` slipped in fails;
- **cap applied AFTER dedup** — eleven inputs of which two are duplicates yield **ten**, and the eleventh distinct tag is **present**. This red-fails if the cap runs first;
- over-length rejected at `MAX_TAG_LENGTH + 1`;
- **each of `\x00`, `\x0b`, `\t`, `\n`, `\r` rejected.** ⚠ **The `\t \n \r` cases are the whole point** — they are the three characters `_CONTROL_CHARS_EXCEPT_WS` permits, so they are the only assertions that fail if `booking/validation.py:70` was imported instead of `:69` (spec C1).

`validate_notes`:
- at `MAX_CUSTOMER_NOTES_LENGTH` passes, one over fails;
- **`\n` and `\t` PASS** (`_CONTROL_CHARS_EXCEPT_WS`, `:70`); `\x0b` fails;
- `""` passes and means cleared.

`phone_search_term` (D2) — the table, exactly:
`"0501234567" → "972501234567"`, `"050-123-4567" → "972501234567"`, `"050" → "97250"`, `"972501234567" → "972501234567"`, `"מיכל" → None`, `"" → None`. **The two `None` cases are what keep the phone leg off a pure-Hebrew term.**

`q` handling: `"  "` normalizes to absent, `" מיכל "` to `"מיכל"`.

Every raised error `isinstance` of both `CustomerValidationError` and `DomainValidationError`; message text lowercase, field-name first, no trailing period.

### GREEN — the module

`class CustomerValidationError(DomainValidationError)` with the spec's docstring. Constants with their why-comments: `MAX_TAG_LENGTH = 24`, `MAX_TAGS = 10`, `MAX_CUSTOMER_NOTES_LENGTH = 2000` (the **profile-description** peer at `boutique/validation.py:30`, not booking-notes' 500), `MAX_SEARCH_TERM_LENGTH = 80`, and the three restated bounds `MAX_LIST_OFFSET = 1_000_000`, `CUSTOMER_LIST_DEFAULT_LIMIT = 50`, `CUSTOMER_LIST_MAX_LIMIT = 200` — restated per `booking/owner.py:52-58`, carrying the asyncpg `int8_encode` reason with them.

`normalize_tags` in the spec's exact seven steps. `validate_notes`. `phone_search_term`, six pure lines.

**The cross-module import carries one line of comment at the import site**, naming which class and why — both `_CONTROL_CHARS` (`:69`, tags) and `_CONTROL_CHARS_EXCEPT_WS` (`:70`, notes) are underscore-private and nothing in the repo imports either across modules today.

⚠ **Ruff `select` includes `SIM`** (`pyproject.toml:51`). Write `normalize_tags`'s guards as combined conditions, not nested `if`s, or the linter rewrites them for you. `line-length = 100`. Every test function needs `-> None` (`disallow_untyped_defs = true`).

- **Done when**: `make lint` + `make test` green.
- **Discharges**: D2 (the helper), D5 (all of it).
- Commit: `feat(customers): the pure validation module — tags, notes and the phone search term`

## Task 2 — The migration and the two ORM columns, as ONE atomic change (C1, C2) — D1
`Backend/migrations/versions/0018_customer_crm_columns.py` (**new**), `Backend/app/models/customer.py`, `Backend/tests/test_migrations.py`

**The halves ship together and this is not a preference — it is C1's measurement.** Without the migration, the two `Mapped` lines redden 114 pre-existing `db` tests. Without the ORM lines, nothing downstream compiles. Migration + model in one commit is the `0008_bookings.py` / `models/booking.py` pattern.

**Resolve the id, do not copy it from here.** `cd Backend && uv run alembic heads` → `0014 (head)` as of 2026-08-03. Write `revision = "0018"` / `down_revision = "0014"` per C2, and **re-resolve at Task 9**.

### The migration — two statements and a complete absence list

```sql
ALTER TABLE customers ADD COLUMN notes TEXT;
ALTER TABLE customers ADD COLUMN tags TEXT[] NOT NULL DEFAULT '{}';
```

`downgrade()` drops both, `tags` first.

**Deliberately absent, as a `#   *` bullet block in `0014_booking_check_in.py:22-36`'s style** — written so a reviewer can check the list is *complete* rather than merely short:

- **No `GRANT`.** `0008_bookings.py:107-110` issued table-level `GRANT SELECT, INSERT, UPDATE, DELETE ON customers TO app_user`. Table grants are column-agnostic and no column-level grant was ever issued here. (The `ALTER DEFAULT PRIVILEGES` gotcha in `.claude/CLAUDE.md` is about newly **created** tables.)
- **No `enable_tenant_rls`.** RLS is a table property, forced on `customers` since `0008_bookings.py:109-110`. **F53 adds no table — `test_every_tenant_id_table_has_forced_rls` staying green *unedited* is the assertion that none snuck in.**
- **No `_updated_at_trigger`.** `trg_customers_updated_at` exists from `0008_bookings.py:50` (the name is templated in the helper at `:25-27`).
- **No index, no CHECK, no backfill.** `NOT NULL DEFAULT '{}'` is the backfill.

**Two upgrade paths recorded in the comment**, both with their thresholds, because these are the two places a reader will ask "why no index":

```
-- Search (D2), at ~50k live customer rows per tenant:
--   CREATE EXTENSION pg_trgm;
--   CREATE INDEX idx_customers_name_trgm  ON customers USING gin (name  gin_trgm_ops) WHERE deleted_at IS NULL;
--   CREATE INDEX idx_customers_phone_trgm ON customers USING gin (phone gin_trgm_ops) WHERE deleted_at IS NULL;
-- SMS log (D3), at ~100k message_log rows per tenant — a PAIR or nothing, because
-- an OR across two columns needs a BitmapOr and one index alone buys nothing:
--   CREATE INDEX idx_message_log_tenant_phone   ON message_log (tenant_id, phone)      WHERE deleted_at IS NULL;
--   CREATE INDEX idx_message_log_tenant_booking ON message_log (tenant_id, booking_id) WHERE deleted_at IS NULL;
-- Tag filtering (D5), when a reader exists:
--   CREATE INDEX idx_customers_tags ON customers USING gin (tags) WHERE deleted_at IS NULL;
```

### The ORM columns, same commit

```python
from sqlalchemy.dialects.postgresql import ARRAY

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
```

Appended after `name` (`models/customer.py:19`) — **the same anchor F33 will use**, so the merge is a union. `warn_unused_ignores = true`, so a speculative `# type: ignore` on the `ARRAY` line is itself a mypy error. **`tags` is the first array column in this codebase** — `grep -rn "ARRAY" Backend/app/models/` returns zero, verified — so there is nothing to copy and this is spelled out rather than guessed.

### RED — `test_migrations.py`, appended per C3

Each test takes **its own** `@pytest.mark.db` (the file has no module-level marker). Banner `# --- NNNN: the customer CRM columns ---`.

1. **`_customer_crm_columns(url)`** — `_check_in_column`'s shape (`:416-426`), returning `(data_type, is_nullable, column_default, udt_name)` per column. Asserted against the **captured** table in §The local Postgres cluster: `notes` → `("text", "YES", None, "text")`, `tags` → `("ARRAY", "NO", "'{}'::text[]", "_text")`. ⚠ **`udt_name` is not padding** — `data_type` says `ARRAY` for every array type.
2. **`test_migration_00NN_round_trips`** — `0014`'s verbatim, with **`command.downgrade(cfg, "-1")`** instead of a hardcoded target, and the mandatory `try/finally: command.upgrade(cfg, "head")`.

**`"-1"` is a stated departure, not a correction of anyone.** All four shipped round-trips hardcode (`:215 "0010"`, `:341 "0011"`, `:372 "0012"`, `:494 "0013"` — verified). F53 departs for one reason: three unmerged migrations are racing, and `"-1"` means "one step back from head", which survives renumbering, which makes F53's block order-independent, which makes the merge with F57's and F19's a plain concatenation instead of a hand edit. **The `finally` is not decoration either** — `0014`'s own comment says why: leaving the schema down drops columns the ORM still maps, and every later `db` test in the shared session container then fails with `UndefinedColumn` somewhere unrelated to itself. C1's 114 failures are that failure mode, measured.

**Run it against the local cluster before committing.** `make test-db` here is the first proof the two `ALTER`s are what you think.

- **Done when**: `make lint` + `make test` green; `pytest -m "db and not s3"` green **locally** at **353 + 2 = 355** passed; the captured `information_schema` row pasted into the test rather than typed.
- **Discharges**: D1 entirely.
- Commit: `feat(customers): the notes and tags columns, their ORM mapping and the migration probe`

## Task 3 — The three repository appends (TDD, `db`-marked) — D2, D3, D4
`Backend/app/db/repositories/customers.py`, `Backend/app/db/repositories/message_log.py`, `Backend/app/db/repositories/bookings.py`, `Backend/tests/test_customers_db.py` (**new**)

**This is the subtlest backend part and the only one where a bug is a disclosure rather than a defect.** Everything else in Part I is orchestration over these four statements. **No new repository file** — three appends (spec correction C8).

### The invariants every append copies, without exception

Signature order is always `(self, session, tenant_id, <positional id>, *, <kwargs>)`. **Every `select` carries all three predicates** — `tenant_id ==`, the narrowing one, `deleted_at.is_(None)`. Reads end `scalar_one_or_none()` or `list(... .scalars())`. **No repository method opens its own transaction.** `updated_at` is never assigned — the trigger owns it.

### `CustomersRepository.search` + `count_search` (D2)

The spec's statement verbatim. Three things are load-bearing and each has its own assertion below:

- **the phone leg runs on `phone_search_term(term)`, never the raw term.** `customers.phone` only ever holds strict E.164 (`normalize_israeli_mobile`, `notifications/validation.py:43-45`), so `'+972501234567' ILIKE '%0501234567%'` is **false** and `%050%` matches nothing at all. Both the natural desk inputs would answer «אין תוצאות» for a customer who exists.
- **`autoescape=True` on BOTH legs.** Without it a typed `_` or `%` returns the whole tenant. Hand-rolling `f"%{term}%"` ships exactly that bug. SQLAlchemy resolves 2.0.51, verified — the kwarg exists.
- **`ORDER BY name, id`.** The `id` tiebreak is what makes OFFSET paging stable when two customers share a name.
- A blank or whitespace-only `q` **drops the predicate**, it does not search for `""`.

`count_search` is a second `select(func.count())` over the **identical** `where` — the `bookings.py:596-598` shape.

### `CustomersRepository.set_notes_and_tags` (D5, D8)

`set_phone`'s UPDATE shape (`:63-75`): `.returning(Customer.id)`, `None` for "no live row", then a re-read through `by_id`. Takes `notes: str | None` and `tags: list[str] | None` as **keyword-only sentinels** — `None` means *not supplied*, and the method builds `.values()` from only what was supplied. `""` and `[]` are values, not absence (`boutique/validation.py:110`).

### `MessageLogRepository.list_for_customer` + `count_for_customer` (D3) — the one that matters

The spec's statement verbatim, and **do not simplify any of these four things**:

- **`MessageLog.tenant_id == tenant_id` on the predicate.** The repository's own docstring calls it *"redundant defense-in-depth (house pattern — see StaffUsersRepository)"* (`:10-11`) and `list_by_phone` carries it (`:60-64`). This is the **only** query in the feature keyed on a phone rather than a customer id, on a column where `0008_bookings.py:42-45` designs the collision in — *"The SAME phone under two tenants is two customers, deliberately."* RLS is not a substitute: `config.py:250` falls back to `DEV_DATABASE_URL`, a superuser connection, whenever `DATABASE_URL` is unset. ⚠ **Cite `app/db/session.py::ensure_safe_database_role` for the superuser fact, not `db/rls.py:14-18`** (C7).
- **`AND booking_id IS NULL` on the phone leg.** This is the correctness of the feature. Without it the phone leg re-admits every lifecycle row the booking leg already attributed correctly — which is exactly the set that can belong to someone else.
- **`or_`, not `UNION` and not `UNION ALL`.** A lifecycle SMS to the customer's *current* phone matches both legs: `UNION ALL` double-renders it, `UNION` sorts the whole result to dedupe. `or_` needs neither.
- **`ORDER BY created_at DESC, id DESC`, `LIMIT 50`.** The `id` tiebreak is mandatory, not tidy: `created_at` is `server_default=text("now()")` (`models/base.py:21-23`) and Postgres `now()` is `transaction_timestamp()`, constant across one transaction.

`count_for_customer` is `select(func.count())` over the identical `where` — this is `messages_total`, and it is what keeps the evidence question answerable when the fifty-row window truncates (Risk 15).

### `BookingsRepository.list_recent_for_customer` (D4, spec correction C8)

```python
async def list_recent_for_customer(
    self, session: AsyncSession, tenant_id: UUID, *, customer_id: UUID, limit: int
) -> list[Booking]:
```

`tenant_id ==`, `customer_id ==`, `deleted_at.is_(None)`, `.order_by(Booking.starts_at.desc()).limit(limit)` — riding `idx_bookings_tenant_customer` (`0008_bookings.py:101-104`). **Every status, cancelled included**, `list_day`'s argument (`:578-581`). Do **not** reuse `list_live_for_customer` (`:601-619`): it pins `status = 'confirmed'` and `starts_at > after` and is F15's re-mint feed.

### RED — `test_customers_db.py`, and every assertion it must carry

`pytestmark = pytest.mark.db` at module level. **`app_role_url`, never the superuser** — the container superuser bypasses RLS unconditionally and would make every isolation assertion vacuously pass. `create_async_engine(url, poolclass=NullPool)` inside `try/finally: await engine.dispose()`. **Every test mints its own tenant id** — the session is shared and nothing truncates.

**Search:** name match on a literal term · **`q="0501234567"`, `q="050-123-4567"` and `q="050"` each find a customer stored as `+972501234567`** (the rows that red-fail if the phone leg runs raw) · a Hebrew term matches a Hebrew name (catches an accidental `lower()`/collation assumption) · **a literal `%` and a literal `_` each match only the rows actually containing them** (the `autoescape=True` assertion) · a soft-deleted customer never appears, in the page or in `total` · `total` is the count under the **search** predicate, not the tenant total · **order stable under OFFSET**: two identically-named customers, paged one at a time, yield two distinct ids.

⚠ **Pick the name term deliberately.** An author who picks a term that happens to be a substring of the stored E.164 keeps the digit-normalization bug green. Use a Hebrew name and a digit string that share nothing.

**SMS log:** a lifecycle row with `booking_id` set surfaces on its customer's detail **after her phone has been corrected** · the phone leg matches **only** rows with `booking_id IS NULL` · **the recycled-phone case, the headline** — A holds phone X with two lifecycle rows, A's phone is corrected to Y via `set_phone`, B is created on phone X, **B's detail contains none of A's rows and A's still contains both** · an OTP row (no `booking_id`, phone match) **is** included · **the under-report characterised**, with a one-line comment saying this is Risk 1's second direction and is accepted · **51 rows in, 50 out, newest first, `messages_total == 51`** — the rows constructed as `MessageLog(...)` with **explicit, distinct `created_at`**, never through `MessageLogRepository.insert`, which exposes no `created_at` and would give all 51 one `transaction_timestamp()` · a soft-deleted log row excluded from both the window and the count · **the non-disclosure value walk, here and only here** — a row written with sentinel `provider_message_id` and `error` strings yields an `SmsLogRow` whose `model_dump()` contains neither. This is the one place a real row crosses the mapping boundary.

**Tenant isolation, two assertions and the second is the one no other test can make:**
- tenant B reading tenant A's `customer_id` raises `CustomerNotFoundError`, **asserted in the same test as tenant A's own read returning non-empty panels** — an all-empty pass is exactly what a missing `tenant_session` produces and would otherwise read green;
- **two tenants, one shared phone**, each with `booking_id IS NULL` rows: B's detail contains none of A's and `messages_total` counts only B's — **paired with a compiled-statement assertion** (`str(stmt.compile())` contains `message_log.tenant_id`). Without that second half the explicit filter can be deleted and every suite stays green: the fast modules issue no SQL and this module runs where RLS masks the omission.

**Notes and tags:** `tags` round-trips as `list[str]`; the default on an untouched row reads `[]`, **never `None`**; `[]` and `""` write `'{}'` and `''` and read back as such.

⚠ **Run the mutation check from §The local Postgres cluster at the end of this task, not at the end of the run.** It is cheapest here, where the only thing that can move is the predicate you just wrote.

- **Done when**: `make lint` + `make test` green; `pytest -m "db and not s3"` green locally; **the mutation check performed and its result recorded** — recycled-phone red, everything else green.
- **Discharges**: D2 (the query), D3 (all of it), D4 (the third append).
- Commit: `feat(customers): search, the fenced SMS-log join and the booking-history read`

## Task 4 — `schemas.py` and `service.py` (TDD, fast, fakes) — D4, D6, D7, D8
`Backend/app/customers/schemas.py` (**new**), `Backend/app/customers/service.py` (**new**), `Backend/tests/test_customers_service.py` (**new**)

New package `app/customers/` — `app/notifications/` is the in-repo precedent for the `service.py` / `router.py` / `schemas.py` trio in a package that owns no table of its own. Not two files in `app/booking/`: F53 reads across `customers`, `bookings` **and** `message_log` and writes to `customers`, so it belongs to no existing domain.

### GREEN — `schemas.py`

Plain `BaseModel`s used as **return-type annotations**; **no `response_model=` anywhere** (`dashboard/schemas.py:3-5`, and there is none in this repo). `CustomerRow` `{id, name, phone, tags}` · `CustomerListResponse` `{items, total, offset, limit}` · `CustomerBookingRow` `{id, starts_at, status, appointment_type_name}` · **`SmsLogRow` `{id, created_at, kind, status, body}` and nothing else** · `CustomerDetail` `{id, name, phone, notes, tags, bookings, messages, messages_total}` · `UpdateCustomerRequest(ForbidExtraModel)` with `notes: str | None = None`, `tags: list[str] | None = None` and the docstring stating `None` = not supplied, `""`/`[]` = clear.

**`created_at` is on neither `CustomerRow` nor `CustomerDetail`, deliberately** (D4) — F52's D7 established that `customers.created_at` is meaningless as "first seen" after F15's collision branch, so shipping it would put a plausible, wrong "customer since" date on the one screen an owner would quote from.

### GREEN — `service.py`

`CustomersService(session_factory)`. **No clock** — nothing here is time-derived.

**One private `_build_detail(session, tenant_id, customer_id)` that both the `GET` and the `PATCH` go through**: `by_id` → the customer or `CustomerNotFoundError` → the booking-history read → the D3 message read → the `messages_total` count. One `tenant_session` per request, so `session.begin()` makes the whole handler body one transaction and the reads see one snapshot — which matters: a booking created between the customer read and the message read would otherwise produce a log row whose `booking_id` matches nothing in the history panel beside it.

`CustomerNotFoundError(DomainNotFoundError)`, raised as a **bare class** (`auth/staff.py:87-91`), with the `raise` **outside** the `async with` (`booking/owner.py:191-199`).

**`update()`**: normalize tags **before** the diff · compare against stored · **if neither moved, write no `UPDATE` and no audit row** and return `_build_detail` alone · otherwise the `UPDATE` and the audit row **first**, then `_build_detail`, all inside the one transaction.

**No advisory lock** (D7). F51's D3 took one for an *at-least-one* invariant; a notes/tags edit is a single-row `UPDATE` and concurrent edits are last-write-wins, which is the answer every text field in this product already gives.

### RED — `test_customers_service.py`, duck-typed fakes, no DB and no app

- **The no-op rule**: `notes` and `tags` both matching what is stored ⇒ **no `UPDATE`, no audit row**, 200 with the unchanged detail. Tags normalization applied before the diff, so `["vip"]` against a stored `["VIP"]` is a **no-op**, not a write.
- `tags` only ⇒ one row, `details == {"fields": ["tags"]}`. Both ⇒ one row, `{"fields": ["notes", "tags"]}` — **sorted**.
- `entity == str(customer_id)`; `actor_id == actor.id`; `action == AuditAction.CUSTOMER_UPDATED`.
- **The value walk**: with `notes = "מגיעה עם אמא"` and `tags = ["VIP-סודי"]`, `repr([row.details for row in audit_rows])` contains **neither** string, and contains neither the customer's `name` nor her `phone`. The shape is `test_staff_management_db.py:604-606`'s — noted because that precedent lives in a **`db`** module and no value walk exists in any fast module today, so this is a new act rather than a borrowed one.
- **The `PATCH` returns a FULLY-BUILT detail** (D6): a patch that moves `tags` answers a `CustomerDetail` whose `bookings` and `messages` are the same **non-empty** lists the fakes hold and whose `messages_total` is the fake's count — **and the same on the no-op path**. ⚠ **This is the assertion that fails if `update()` builds its response from the `customers` row alone**, which would blank the booking-history and SMS-log panels the instant the owner pressed «שמירה».
- An unknown / soft-deleted / foreign `customer_id` raises `CustomerNotFoundError`, and the update stub is asserted **never called**.

- **Done when**: `make lint` + `make test` green.
- **Discharges**: D4 (`SmsLogRow`'s five fields), D6 (the models, `_build_detail`, the PATCH-returns-detail rule), D7, D8 (the no-op rule and the details shape).
- Commit: `feat(customers): the detail builder, the no-op patch rule and the response models`

## Task 5 — One `AuditAction` member (D8)
`Backend/app/models/constants.py`

```python
# --- F53: the customer CRM ---
# audit_log.action is plain TEXT with no CHECK (0003), so a new member needs
# no migration.
CUSTOMER_UPDATED = "customer_updated"
```

Its own block, appended **after `GATEWAY_LATE_SETTLEMENT` (`:171`) and before `PlatformAuditAction` (`:174`)** — the least-contended seam in a file F57 also edits (at `StaffRole`, `:9-15`, ~160 lines away) and F19 edits (four enums, elsewhere). ⚠ **Append only. Never reorder, never reformat, never re-wrap another feature's lines** — different enums in one file is the easiest possible three-way merge unless somebody runs a formatter across it.

**One value, not `CUSTOMER_NOTES_UPDATED` + `CUSTOMER_TAGS_UPDATED`.** The split criterion this repo applies is recorded at `:129-134` and it is not "is this a distinct field" — it is *"is this a distinct question a security audit actually asks of this table"*. Nobody will ask "who edited tags but not notes".

- **Done when**: `make lint` + `make test` green (no new test — Task 4 already asserts the member by name).
- **Discharges**: D8's enum half.
- Commit: `feat(customers): the customer_updated audit action`

## Task 6 — The router, the wiring and the API suite (TDD, fast) — D6, D9
`Backend/app/customers/router.py` (**new**), `Backend/app/main.py`, `Backend/tests/test_customers_api.py` (**new**)

### GREEN — the router

```python
router = APIRouter(
    prefix="/manage",
    dependencies=[Depends(_no_store), Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))],
)
```

Both roles at **router** level. `_no_store` is a **local three-line copy** whose docstring cites `auth/staff_router.py:21-25` (the decision of record — *"the alternative points the dependency arrow backwards"*) and **states no ordinal**, because every ordinal written into this codebase so far has gone stale (spec correction C5).

Three handlers, `auth/staff_router.py:104-127`'s shapes exactly: bare `customer_id: UUID` (**no `Path(...)`**), bare `body: UpdateCustomerRequest`, tenant from `get_current_tenant(request).id` and **never** from `staff.tenant_id`, the router unpacking the request model into keyword arguments, **no try/except and no error mapping anywhere in the router**.

Bounds copied from `booking/owner_router.py:168-169`: `offset: Annotated[int, Query(ge=0, le=MAX_LIST_OFFSET)] = 0`, `limit: Annotated[int, Query(ge=1, le=CUSTOMER_LIST_MAX_LIMIT)] = CUSTOMER_LIST_DEFAULT_LIMIT`, plus `q: Annotated[str | None, Query(max_length=MAX_SEARCH_TERM_LENGTH)] = None`.

**The two GETs declare no `staff` parameter; the `PATCH` does.** The `RoleGate` runs router-level and needs no binding, so the only reason to inject `StaffContext` is a use for the acting identity — and the `PATCH` has exactly one, `actor_id` on its audit row. Declaring it on the GETs would be a parameter with no reader, and would put the session-derived `tenant_id` in reach on two routes that have no other reason to want it.

### GREEN — `main.py`, two lines and an import

`app.state.customers_service = CustomersService(get_session_factory())` beside the `DashboardService` line (`:562`), reached through `get_customers_service(request)` behind a `Service = Annotated[…]` alias — the pattern that lets the fast API test swap in a duck-typed fake.

`app.include_router(customers_router)` **after `gateway_router` (`:1043`) and before `storefront_router` (`:1046`)**, carrying the shadowing comment every `/manage` include after the first carries and naming `test_customers_api.py`'s `ROUTES` table as its guard.

⚠ **The ordinal.** F53 is **the EIGHTH `/manage` router on `origin/main`** — seven exist today, six declaring the exact string `prefix="/manage"` plus `auth/router.py:13`'s `"/manage/auth"`, which `main.py`'s own chain counts (`:1039` labels the gateway router *"The SEVENTH"*). **Renumber to NINTH if F57 lands first**, and to tenth if F19's sibling router also counts — re-read the chain at Task 9 rather than trusting this sentence.

⚠ **`_register_spas(app)` stays at `:1057`, last.** `test_spa_serving.py:312-321` names F53 by name for exactly this: *"one added a line too far down would ship a storefront shell where an API used to be, with nothing else going red."*

### RED — `test_customers_api.py`, the `test_dashboard_api.py` template

Duck-typed `FakeCustomersService` on `app.state.customers_service` (**not** a dependency override — `test_dashboard_api.py:212-214` records why), `FakeAuthService` whose `StaffContext.tenant_id` **deliberately disagrees** with the host-resolved `TENANT.id`, `dependency_overrides[get_auth_service]` **only**, `TestClient(app, base_url="http://bella.localtest.me")` with the `boutique_session` cookie set on that domain. **Every test is a sync `def`** — `asyncio_mode = "auto"` (`pyproject.toml:74`) would give an async test its own loop and `TestClient` starts a second inside it.

```python
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/manage/customers", None),
    ("GET", f"/manage/customers/{CUSTOMER_ID}", None),
    ("PATCH", f"/manage/customers/{CUSTOMER_ID}", {"notes": "x"}),
]
```

- `test_every_route_requires_authentication` — 401 `NOT_AUTHENTICATED` on all three, and the fake records **zero** calls.
- `test_every_route_is_wired_and_reaches_the_service` — 200 on all three. **This table is the shadowing guard for the eighth `/manage` router**; a 404 here is what catches a duplicated `(method, path)`. The ordinal lives in `main.py`'s include comment and in this docstring only, and the two must agree.
- Both roles get 200 on all three, parametrized over `OWNER` / `SHIFT_MANAGER`.
- An out-of-enum role gets **exactly** `NOT_AUTHORIZED_BODY` with 403, and the fake records zero calls (the gate raises during dependency solving).
- `cache-control: no-store` on all three, parametrized over `ROUTES`.
- **The tenant comes from the HOST** — the fake records the `tenant_id` it was called with; assert `== TENANT.id`. This is the only place the trust path is observable.
- **400, never 422** (spec C2): `limit=0`, `limit=201`, `offset=-1`, `offset=1_000_001`, a 200-character `q`, an unknown body key and a non-UUID path segment each answer **400** with `{"error": {"code": "VALIDATION_ERROR", "message": …}}`.
- ⚠ **`CSRF_ORIGIN_MISMATCH`** — a `PATCH` with a mismatched `Origin` is 403 with that code. `csrf.py:48` fences `MUTATING_METHODS` and the `PATCH` is one. **Do NOT copy `test_dashboard_api.py:343-351`'s inverse** (`test_a_dashboard_read_with_a_mismatched_origin_is_allowed`) — that module's route is a GET and F52's assertion is the opposite of F53's.
- `SPEC_ERROR_CODES = {"NOT_AUTHENTICATED", "NOT_AUTHORIZED", "VALIDATION_ERROR", "NOT_FOUND", "CSRF_ORIGIN_MISMATCH"}`, re-derived from live responses.
- ⚠ **`set(SmsLogRow.model_fields) == {"id", "created_at", "kind", "status", "body"}`** — an **equality**, never a subset. This is the assertion that fails when someone adds `provider_message_id` or `error` "for debugging", and it is what catches a rename that a value-based sentinel cannot.
- **The disclosure walk, keys only, against a fully populated fake.** `_all_keys` reused verbatim (`test_dashboard_api.py:107-115`). F53's own forbidden set, because F52's contains `phone`, `notes`, `customer_name` and `customer_id`, all four of which F53 legitimately ships:

  ```python
  CUSTOMER_FORBIDDEN_KEYS = frozenset(
      {"provider_message_id", "error", "manage_token_hash", "password_hash",
       "tenant_id", "booking_id", "deleted_at", "dress_name", "dress_size",
       "seat_index", "email"}
  )
  ```

  **The fake response must be fully populated** — non-empty `items`, `tags`, `bookings`, `messages` — with the anti-vacuity assertion beside the walk, because a key that never appears cannot leak. **There is no value half in this module**: a sentinel is unreachable through a duck-typed fake behind `-> CustomerDetail`, because FastAPI serializes against the annotation and `SmsLogRow` has no slot for either field. The value walk lives in `test_customers_db.py` (Task 3), where a real row crosses the mapping boundary.

- **Done when**: `make lint` + `make test` green.
- **Discharges**: D6 (the routes, the wiring, the ordinal), D9 (the whole error table).
- Commit: `feat(customers): the /manage/customers router, its wiring and the route table`

---

# Part II — the frontend

## Task 7 — Types, API client, `validation.ts`, both components and the copy (TDD) — D10, D11, D12
`Frontend/apps/manage/src/api.ts`, `…/src/validation.ts`, `…/src/lib/booking.tsx`, `…/src/components/CustomersSection.tsx` (**new**), `…/src/components/CustomerDetail.tsx` (**new**), `…/src/i18n/he.ts`, `…/src/i18n/ar.ts`, `Backend/tests/test_frontend_constant_parity.py`

### `api.ts` — types before `// --- endpoints ---`, methods after `listManageSlots` (`:656`)

All **snake_case**, mirrored field-for-field. There is no case-conversion layer (`api.ts:1-5`); a camelCase interface compiles fine and reads `undefined` at runtime on every field.

⚠ **The wire type is `CustomerDetailResponse`, not `CustomerDetail`** — that name belongs to the component. The shipped pair avoids exactly this (`OwnerBookingDetail` at `api.ts:311` vs `BookingDetail` the component), and under `isolatedModules: true` (`tsconfig.base.json:10`) a colliding value import is a hard **TS2865**. The **backend** model stays `CustomerDetail`; there is no component in Python to collide with.

`customerPath` beside `staffPath` (`:411-413`). Three methods, object-literal shorthand, **not `async`**, one line each — `listCustomers` carrying `listDresses`'s conditional-`q` branch (`:549-559`).

⚠ **Insert after `:656`, NOT at the object end.** F57 appends at the end; deliberately different anchors is what keeps this a union.

### `validation.ts` — and getting the two declaration forms backwards is a red CI round for nothing

`test_frontend_constant_parity.py` scrapes the two kinds with **mutually exclusive** regexes: `_CONST_RE` (`:93`) requires `^export const NAME = <digits>;`, `_TS_REGEX_RE` (**`:129`**, C5) requires a line-start bare **`const NAME = /…/;`** with **no `export`**.

- **`export const`**: `MAX_TAG_LENGTH`, `MAX_TAGS`, `MAX_CUSTOMER_NOTES_LENGTH`, `MAX_SEARCH_TERM_LENGTH`.
- **bare `const`**: `CONTROL_CHARS`, `CONTROL_CHARS_EXCEPT_WS`, copied **byte-for-byte** from `booking/validation.py:69-70`. The shipped mirror does exactly this (`apps/storefront/src/validation.ts:19-20` exported, `:32`/`:34` bare).
- `validateTag`, `validateCustomerNotes`.

### `test_frontend_constant_parity.py` — the fourth `MIRRORS` param and one parametrize

`(MANAGE_VALIDATION_TS, customers_validation, ("MAX_TAG_LENGTH", "MAX_TAGS", "MAX_CUSTOMER_NOTES_LENGTH", "MAX_SEARCH_TERM_LENGTH"))` — **four names, not three.** The search bound is the one the client can hit by paste and the only server bound the mirror-everything claim would otherwise leave unmirrored.

Then parametrize `test_control_character_classes_match_the_backend` (`:143-150`) over `(STOREFRONT_VALIDATION_TS, MANAGE_VALIDATION_TS)`. ⚠ **The hardcoded assertion message at `:149` must stop naming the storefront** — `f"storefront validation.ts does not declare {ts_name}"` sends a manage failure to the wrong file. Make it name the file under test. (Both tests read the TS as **text**, so they stay in the fast no-Node suite.)

### `lib/booking.tsx` — one addition, and it goes there for a stated reason

`customerErrorText(error, t)` lives here, **not in either component**: `CustomersSection` imports `CustomerDetail` and both need the map, which is exactly the cycle `lib/booking.tsx:1-5` was created to avoid. It maps `NOT_FOUND` and `NOT_AUTHORIZED` to Hebrew and falls through to `errorMessage(error)` for everything else. The map is kept **by hand** and nothing pins it; the comment beside it says so and names the failure mode.

`statusBadge` (`:22`) and `isolateLtr` (`:32`) are **reused verbatim, never re-declared** — `he.ts:456-457` records why: *"a second spelling of «בוטל» in one console is a defect."*

### The two components

`CustomersSection.tsx` and `CustomerDetail.tsx`, exactly as the spec's two layout sections specify. The four things most likely to be got wrong:

1. ⚠ **`Skeleton variant="text"`, never the default.** `Skeleton`'s default is `"block"` (verified, `Skeleton.tsx:16`), which renders `h-full w-full` and collapses to zero height in a parent with no intrinsic height.
2. ⚠ **`CustomerDetail`'s null handling is INLINE conditionals in one return, not an early return** (C6). The back `Button` and the `<h2>` render **unconditionally**; only items 3-6 are suppressed while `detail === null`. `BookingDetail` does it inline at `:197` / `:238` / `:247` — copy that, not an early return that would duplicate the heading.
3. ⚠ **`tabIndex={-1}` on both `role="alert"` / `role="status"` focus destinations.** A `<p>` is not focusable, so `ref.current?.focus()` on a plain paragraph is a **silent no-op** that drops focus to `<body>` — `BookingDetail.tsx:103-115` records what that cost (*"the next Tab restarted at the skip link (WCAG 2.4.3)"*) and `:423-427` is the shipped alert that carries it.
4. ⚠ **The `Card`'s baked-in `p-6` is not overridden.** `cn()` is a plain join with no conflict resolution, so a consumer `p-0` and `p-6` are same-specificity rules and `.p-0` is emitted first, making the override **silently inert** (`BookingsSection.tsx:134-137`).

Plus: `<bdi>` bare on names, tags and message bodies; `<bdi dir="ltr">` on phones, dates and times; **no `dir="ltr"` on the search input** (the term is usually Hebrew, and `dir="ltr"` on Hebrew free text is itself a bidi defect); **all tags rendered, no `+N` token** (D11 — it would be user-visible text with no copy-deck key, and a digit run adjacent to a `+` between Hebrew chips is the exact bidi hazard); the save handler is **validate-then-diff** (`validateCustomerNotes` first and `return` without a request, then the diff body); `toast({...})` called as a **function**, not `toast.success(...)` (`ProfileSection.tsx:94`).

### The copy — 51 keys, `he.ts` then `ar.ts`

`// --- F53, customers CRM ---` block appended **after `he.ts:537`, before the closing `},` at `:538`** (file is 539 lines). The same key set appended after **`ar.ts:303`** (file is 305 lines) with **the Hebrew standing in verbatim and never `""`**.

⚠ **«יומן הודעות», never «הודעות שנשלחו».** `i18n.test.ts:247` rejects any `HE` value matching `/נשלח|תישלח|בדרך/`, so the natural heading red-fails the build the moment `HE_F53` is folded into `HE` — and the honest reason is bigger than the mechanical one: **the log renders `status = 'failed'` rows**, and a heading claiming they were sent is exactly the lie that guard exists to prevent. Same for the status word: `sent` means the provider accepted the message, so it is **«הועברה לספק»**, not «נשלחה». **The guard is not widened.**

- **Done when**: `make fe-test` + `make fe-build` green; `pnpm -r lint && pnpm -r typecheck` clean; `make test` still green (the parity test is Python and runs in the fast suite).
- **Discharges**: D10 (the components and the patch-from-response rule), D11 (the deck and the copy guard), D12 (the fetch shape).
- Commit: `feat(manage): the customers section, its detail panels and the F53 copy deck`

## Task 8 — Routing, the nav row and the four coupled test files (TDD) — D10
`Frontend/apps/manage/src/App.tsx`, `…/vite.config.ts`, `…/src/__tests__/Nav.test.tsx`, `…/src/__tests__/i18n.test.ts`, `…/src/__tests__/CustomersSection.test.tsx` (**new**)

**All five ship in ONE commit.** Three of them carry coupled numbers and a half-done rebase leaves a test whose *name* contradicts its assertions.

### `App.tsx` — four one-line inserts at four anchors

Import after `CatalogSection`; `| "customers"` in `SectionKey` (`:18-28`) after `"bookings"`; the `NAV` row **after `board` (`:66`) and before `staff` (`:67`)** — index 8; the render line in the flat `&&` list (`:145-154`) after the `board` line.

**Index 8 is fixed by two shipped comments, both verified.** Not row 0 — `:59-65` says row 0 is the landing section and *"nothing inserted below it can displace either the initial `section` or the `reachable[0]` fallback."* And above the two owner-only rows — `Nav.test.tsx:65-66` says the owner-only rows are last and that is *"what keeps the shift_manager assertions below a `.slice(0, 8)`."* `roles: ALL`.

### `vite.config.ts` — TWO hunks, and the second is prose

⚠ **`customers` into the alternation at `:18-19`** (alphabetically, between `bookings` and `dashboard`) **AND the prose at `:13` and `:16`** — *"The eleven names"* → twelve, *"a twelfth router"* → thirteenth.

**This is not a dev-machine convenience.** `test_spa_serving.py:372-400` derives the expected set from the **live FastAPI route table** and asserts **set equality**, so a missing `customers` fails a **Python** test in the fast suite. **F52 shipped exactly this gap** and had to fix it in `6c232cc`, whose own message is the warning:

> *"F52 is the tenth such router, so the rebase applied with no textual conflict and still broke: without this line `/manage/dashboard` is served the SPA shell instead of being proxied to the API — a 200 with the wrong body, in dev and in `vite preview` (which inherits `server.proxy`), which no status assertion would catch."*

⚠ Note the regex char class is `[a-z|-]` — a segment with a digit or an underscore would not match at all.

### `Nav.test.tsx` — five coupled edits

1. `listCustomers: pending` into the `vi.mock` factory's `api: {…}` member list (`:20-33`, inside the factory at `:10-35` — C7). ⚠ **Without it every nav test red-fails on mount** with `TypeError: api.listCustomers is not a function`, an error that names the nav rather than the customers section. The comment at `:27-30` records exactly this failure for `getDashboard`.
2. `"לקוחות"` into `NAV_LABELS` at index 8, **between `"לוח היום"` (`:64`) and `"צוות"` (`:67`)**.
3. Both `NAV_LABELS.slice(0, 8)` (**`:95`** and **`:148`**) → `slice(0, 9)`.
4. Both test names — `:84` *"all ten sections"* → eleven, `:91` *"eight sections"* → nine.
5. The `:65-66` comment's `.slice(0, 8)` reference.

Plus one new describe on the `:160-172` template: click «לקוחות», assert the heading and the `role="status"` loading text.

### `i18n.test.ts`

`const HE_F53 = entries(he.translation, (key) => key === "nav.customers" || key.startsWith("customers."));` **folded into the `HE` spread at `:39`**. ⚠ **Without the fold, the resolve check, both register guards AND the `ar` parity guard silently skip every F53 key** — the file's own comment at `:32-36` records that failure.

Own describe: the `>= 48` floor · `nav.customers` resolves to «לקוחות» · `customers.messagesHeading` is **exactly** «יומן הודעות» · every `customers.messageKind*` and `customers.messageStatus*` resolves · `customers.tagRemoveAria` matches `new RegExp('^' + i18n.t("customers.tagRemove"))` (the `:221-230` template) · `customers.error.NOT_AUTHORIZED` contains «כרגע» and none of `["אחראית משמרת", "תפקיד", "בוטלו", "הוסרה", "שונה"]`.

### RED — `CustomersSection.test.tsx`

`vi.mock("../api", …)` with `vi.importActual` re-exporting the **real** `ApiError` and `errorMessage` so `instanceof` works in the component. Runs under `TZ=America/New_York` (`package.json:11`), which is what gives every Jerusalem assertion bite. `globals: false`, so every `describe`/`it`/`expect`/`vi` is imported explicitly.

Loading skeleton + the announced loading string · the outage alert with **no stacked empty state** · a populated list · **the two distinct empty states** (no customers vs no results) · **a five-keystroke burst fires exactly one `listCustomers`** (fake timers, then `toHaveBeenCalledTimes(1)` with the final term) · list → detail → back · the notes round-trip patching from the response · tag add / remove / duplicate / over-length / client cap each rendering their own Hebrew **in the right slot** · a `status = 'failed'` row reads «נכשלה» with a `danger` badge · the `NOT_FOUND` and `NOT_AUTHORIZED` maps · bare `<bdi>` on the name and `<bdi dir="ltr">` on the phone · exactly one `H2`, no skipped levels · **axe-core through `renderInShell`** with the 20 000 ms per-test timeout the shipped suites use.

Plus the five the spec's own review added, each pinning something nothing else reaches:

1. **The detail's null branch**: while pending, `customers.detailLoading` is announced **and the back `Button` is already present**; on `NOT_FOUND`, `customers.notFound` renders in the muted alert and the back `Button` is **still** present — the only way out of a 404.
2. **`document.activeElement` is the save alert after a failed save.** ⚠ Red-fails if `tabIndex={-1}` is missing from the `<p>`, which is why it is asserted rather than trusted.
3. **`document.activeElement` is `[data-testid="customers-count"]` after «חזרה לרשימה».** Pins the explicit back-focus effect; without it focus is on `<body>`.
4. **A pasted control character in notes** renders `customers.notesInvalid` in the `TextArea`'s `error` slot and fires **zero** `updateCustomer` calls.
5. **A pasted over-80-character search term** is truncated by `maxLength` and never produces a request the server would 400.

- **Done when**: `make fe-test` + `make fe-build` green; **`make test` green** (`test_spa_serving.py` is the vite guard and it is a Python test); `pnpm -r lint && pnpm -r typecheck` clean.
- **Discharges**: D10 (the nav position and the swap), D11 (the guards), D12 (the debounce and no poll).
- Commit: `feat(manage): the customers nav row, the dev-proxy segment and the section suite`

---

# Part III — the migration's number

## Task 9 — Rebase, re-resolve the revision id, re-count the ordinal
`Backend/migrations/versions/0018_customer_crm_columns.py`, `Backend/app/main.py`, `Frontend/apps/manage/vite.config.ts`, `Frontend/apps/manage/src/__tests__/Nav.test.tsx`

**The migration's *content* shipped at Task 2 (C1). What is last — and what D1's "last commit" was really protecting — is its *number*.** This task exists so that is a named step rather than a rediscovery.

```bash
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen/.worktrees/customers-crm"
git fetch origin && git rebase origin/main
```

Then, in this order:

1. **`cd Backend && uv run alembic heads`.** ⚠ **The only source of `down_revision`.** Never the number in this document, never the number in the spec. Set `down_revision` to what it prints. If `revision = "0018"` is now taken, bump `revision` **and** rename the file to match. `git rebase -i` (or `git commit --fixup` + `--autosquash`) onto the Task 2 commit — **one file, one literal, usually.**
2. **`uv run alembic heads` again** — it must print **exactly one head**. If F19 has merged, `test_migrations.py::test_exactly_one_migration_head` asserts this in `make test` too; if it has not, this command is the only check that exists.
3. **Re-count `main.py`'s ordinal chain** and renumber F53's include comment — **EIGHTH** on `origin/main`, **NINTH** post-F57. The comment and `test_customers_api.py`'s `ROUTES` docstring must agree. Verify `_register_spas(app)` is still the last statement of `create_app()`.
4. **`vite.config.ts` — two guaranteed conflicts** with F57 (which adds `floor`). Resolution is the **union of both segments, alphabetically**, and the count words bumped **twice** (eleven → thirteen, twelfth → fourteenth). `make test` catches a bad resolution.
5. **`Nav.test.tsx` — three coupled numbers and two test names.** F57 bumps the same ones. Whoever rebases second fixes them by hand; the failure is loud, not silent.
6. **`i18n.test.ts:39`** — the `HE` spread is one conflict with F57; the resolution is **both names**.
7. **`test_migrations.py`** — per C3, append after the last round-trip test if the fast test is still terminal, otherwise at the end. `"-1"` is what makes F53's block order-independent, so the resolution is plain concatenation.
8. **`models/customer.py`** — union with F33's `marketing_opt_in_at` if F33 has landed; both are appends after `name`.

⚠ **Do not copy F57's two blemishes when resolving.**

- Its `main.py` registration comment carries a **duplicated sentence** — verbatim on its branch: `# The next one, after the floor. Same hazard again. Same hazard again, and the ROUTES`. F53's include lands immediately around it, so this is the line most likely to be copied by accident.
- Its `test_migrations.py` round-trip **hardcodes `command.downgrade(cfg, "0014")`** — its own `down_revision` spelled as a literal. It is *functionally* what `"-1"` means and F57 reasoned about it in the docstring, but it is a literal that has to be hand-updated if F57's `down_revision` ever moves. **F53 uses `"-1"` (D12) and does not follow this.**

Take F57's *lines*, not its *defects* — and do not "fix" them either; editing another feature's evidence is not F53's to do.

Then the full verification below, then:

```bash
git diff --stat backend/tests/conftest.py        # MUST print nothing
git status --porcelain                            # no cluster data dir, no stray files
```

- **Done when**: one alembic head; the ordinal renumbered; every conflict resolved as a union; the full gate green.
- Commit (if the rebase produced changes beyond the fixup): `fix(customers): renumber onto the rebased head and re-count the /manage ordinal`

---

# Part IV — gates

## Task 10 — The run report
No files.

Run the full verification below and report what ran and what passed. **State explicitly** that the `db` suites were executed **locally against the 55434 cluster** — and if for any reason they were not, say so, because Risk 6's budget depends on the answer.

Carry forward:

- ⚠ **The mutation check's result.** Deleting `AND booking_id IS NULL` turned the recycled-phone test **red and nothing else**. If anything else moved, say what.
- ⚠ **C1 — the migration is NOT the last commit**, against D1's text, and the reason is a measurement: 114 pre-existing `db` tests fail with the ORM columns and no migration. **The most likely finding in review.**
- ⚠ **`revision = "0018"` was chosen to avoid a third claim on `"0015"`** (F57 and F19 both hold it today). If both merged before F53, confirm the final number and that `alembic heads` prints one head.
- **The manual check no test can make** (spec §): run the manage app against a seeded tenant, open a customer whose phone was corrected, and confirm her SMS log shows **her own** lifecycle messages and not the previous holder's. The `db` test proves it in SQL; this proves it through the screen the owner reads.
- **Risk 1 — non-lifecycle rows are mis-attributed in BOTH directions after a phone changes hands.** Over-report (a masked OTP row surfacing on the new holder's log) and **under-report** (every non-lifecycle row sent to her previous number stops matching the moment `set_phone` runs). One root cause — `message_log` has no `customer_id` — and one blocked upgrade path, because a backfill cannot be correct for historical rows. **F20 / F21 inherit it explicitly.**
- **Risk 10 — free-text notes about a named third party, with no retention policy, no export and no erasure path.** Israel's Amendment 13 gives a data subject rights this column cannot yet serve. Mitigated by D8 (field names only in the audit row) and the copy («ההערות נשמרות בכרטיס ונראות לצוות הבוטיק בלבד»). **Owner: user, to overturn rather than to authorise. F20's surface.**
- **Risk 15 — the fifty-row SMS window can be filled entirely by OTP rows** written through an anonymous endpoint at 5/hour/phone/process, evicting every lifecycle row permanently. `messages_total` keeps the volume question answerable; the recorded upgrade is a **separate bound on the OTP contribution**, not a higher shared cap.
- **The epic's SMC-4 row is not fully closed.** The Locked decision reads *"read-only per customer/booking"* and F53 ships only the customer half; the booking half is `MessageLog.booking_id == booking_id`, the same `SmsLogRow`, rows appended to the existing `BookingDetail` response — **no new route, no new copy beyond the four `customers.messages*` keys**. It belongs to whichever feature next touches `booking/owner_router.py`. **F53 being the last unbuilt SMC entry is exactly why saying so here matters.**
- **`audit_log` is still write-only.** F53 adds a ninth action nothing renders. Unchanged from F15's Risk 7.

No push, no PR — the orchestrator owns review and shipping. ⚠ **Do not open the PR while another branch holds an unmerged migration at F53's number.** `main` is unprotected; `bash .claude/scripts/merge-gate.sh <n>` is the only gate.

---

## Do not do this

The traps specific to F53, each one drawn from the spec's Risks or from a scar this repo already carries.

1. ⚠ **Never `git add -A` in this worktree.** The conftest escape hatch is uncommitted and live for most of the run. One `git add -A` ships a test-suite backdoor to `main`. Stage by explicit **lowercase** pathspec (`backend/…`, `frontend/…`) and verify with `git show --stat`. `git diff --stat backend/tests/conftest.py` must print nothing before every commit.
2. ⚠ **Never transcribe a deparsed literal.** `tags TEXT[] NOT NULL DEFAULT '{}'` comes back from `information_schema` as `data_type = 'ARRAY'`, `column_default = '{}'::text[]`, `udt_name = '_text'`. Nobody types that from the migration source. Capture it by querying the real cluster.
3. ⚠ **Never hardcode the migration revision id from this document or the spec.** `alembic heads` on the **rebased** branch is the only source. `"0015"` is already claimed twice; the numbers in these documents are expectations, not facts.
4. ⚠ **Never use «הודעות שנשלחו» or «נשלחה».** Both trip `i18n.test.ts:247`, and the guard is right: the log renders `status = 'failed'` rows, so a heading saying "messages that were sent" is a lie about the rows underneath it. «יומן הודעות» and «הועברה לספק». **Do not widen the guard.**
5. ⚠ **Never omit `customers` from `Frontend/apps/manage/vite.config.ts`'s alternation** — and never omit the two prose words above it either. `test_spa_serving.py:372-400` asserts **set equality** against the live route table. **F52 shipped exactly this gap** (fixed in `6c232cc`): a 200 with the wrong body in dev and in `vite preview`, which no status assertion catches.
6. ⚠ **Never add F53's routes to `test_staff_role_gating.py`'s `OWNER_ONLY`.** Both walkers derive from the live route table; a both-roles route in that set reports as **`unenforced_owner_only`** and goes red. `dashboard/router.py:14-15` states it in as many words. **The file needs no edit at all.**
7. ⚠ **Never copy F57's two blemishes when resolving conflicts** — the duplicated `Same hazard again. Same hazard again,` in its `main.py` registration comment, and the hardcoded `command.downgrade(cfg, "0014")` in its `test_migrations.py` round-trip. Take its lines, not its defects. Equally: **do not edit them** — another feature's evidence is not F53's to rewrite.
8. ⚠ **Never copy `test_dashboard_api.py:343-351`.** That test asserts a mismatched-origin **GET is allowed**. F53's mutation is a `PATCH`, `csrf.py:48` fences it, and F53's assertion is the **opposite**.
9. ⚠ **Never relax `set(SmsLogRow.model_fields) == {…}` to a subset.** The equality is the only thing that catches `provider_message_id` being added back, or renamed to `sid`. A value-based sentinel through a duck-typed fake passes vacuously and would keep passing after the rename.
10. ⚠ **Never drop `MessageLog.tenant_id ==` or `deleted_at.is_(None)` from the D3 join because "RLS covers it".** RLS is not universally in force — `config.py:250` falls back to a superuser URL — and this is the one query keyed on a phone, where the same phone under two tenants is a designed-in collision. The compiled-statement assertion in `test_customers_db.py` is what makes the predicate un-deletable.
11. ⚠ **Never import `_CONTROL_CHARS_EXCEPT_WS` for tags.** Line 70 permits `\t \n \r`; a newline inside a `TEXT[]` element renders as a two-line chip and copies wrong. Tags import **`:69`**, notes imports **`:70`**.
12. ⚠ **Never `export` the two regexes in `validation.ts`.** `_TS_REGEX_RE` (`:129`) matches a line-start **bare** `const`; `_CONST_RE` (`:93`) matches `export const NAME = <digits>;`. They are mutually exclusive, and getting it backwards is a red round for nothing.
13. ⚠ **Never refetch the list after a save.** `name` and `phone` cannot move through this endpoint, so neither list membership nor the `ORDER BY name, id` order is affected. Patch the row from the response. (The *next* mutation added here — a name edit — **would** need the refetch. That is why it is written down.)
14. ⚠ **Never import F57's `lib/usePoll.ts`.** It is on an unmerged branch and it is a different concern. F53's debounce is `setTimeout` + a cleanup that clears it — six lines, no dependency.
15. ⚠ **Never build the SMS-log fixture rows through `MessageLogRepository.insert`.** It exposes no `created_at`, so all fifty-one rows get one `transaction_timestamp()` and both the "newest fifty" and "which row was dropped" assertions become coin flips. Construct `MessageLog(...)` with explicit, distinct values.
16. ⚠ **Never add a `POST /list` route, a `@QueryValue`-style query param for an id, or a `response_model=`.** Three shipped router docstrings rule real verbs and path parameters; `.claude/rules/` describes a Kotlin/Micronaut codebase that is not this one.

---

## Definition of Done

```
make lint      # Backend: ruff check . && ruff format --check . && mypy app tests
               #   + Frontend: pnpm -r lint && pnpm -r typecheck
               #   + bash Frontend/scripts/qa-greps.sh
make test      # cd Backend && uv run pytest -m "not db" -q
make test-db   # cd Backend && uv run pytest -m db -q      <- see below; run the
               #                                              "db and not s3" subset locally
make fe-test   # cd Frontend && pnpm -r --if-present test
make fe-build  # cd Frontend && pnpm -r build
make e2e       # cd Frontend && pnpm -r build && playwright install --with-deps chromium && pnpm e2e
```

**Baselines measured in this worktree at `dece1f0`, before any F53 code:**

| Suite | Baseline | Expected after F53 |
|---|---|---|
| `make test` (backend fast) | **1226 passed, 362 deselected** | **1226 + F53's fast tests**, deselected count grows by F53's `db` tests |
| `pytest -m "db and not s3"` (local cluster) | **353 passed, 1235 deselected** | **353 + F53's** (2 from `test_migrations.py`, ~20 from `test_customers_db.py`) |
| `apps/manage` vitest | **407 passed, 16 files** | **407 + `CustomersSection.test.tsx`'s**, 17 files |
| `apps/storefront` vitest | **733 passed, 16 files** | **733, unchanged** — F53 touches no storefront file |
| `packages/ui` vitest | **104 passed, 17 files** | **104, unchanged** — nothing is added to `packages/ui`, which is the Q2 self-approval hinge |

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`** (`disallow_untyped_defs = true`, so every test function needs `-> None` and every fake needs full annotations including `__init__`), `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, `qa-greps.sh` exit 0 printing **exactly the pre-existing baseline, measured in this worktree**: seven `ok` lines (no nav component / no favorites / no history-based back / no empty fragment hrefs / no hand-formatted shekels / no physical direction props / no raw hex colours), then `review  date reads` listing **`apps/manage/src/components/HoursSection.tsx:15` and `apps/manage/src/components/TermsSection.tsx:9` and nothing else**. F53 adds no formatter, so **any third line under `date reads` is F53's regression** — the one way to earn it is writing a new `Intl.DateTimeFormat` inside `CustomerDetail.tsx`. Don't: the local `Instant` helper delegates to `jerusalemDate` / `jerusalemTime` from `lib/jerusalem.ts` (`:30`, `:35`), exactly as `BookingDetail.tsx:8,31-37` does. Copy the **helper**, import the **formatters**.
- **`make test`** — 1226 + F53's, with `test_customers_validation.py`, `test_customers_service.py` and `test_customers_api.py` green; **`test_spa_serving.py` green** (this is the vite-config guard); **`test_staff_role_gating.py`, `test_tenant_isolation.py` and `test_frontend_constant_parity.py` green** — the first two **unedited**, which is the assertion. ⚠ **There is no `Backend/.env` in this worktree**, so the two known-false `test_config.py` failures (`.memory/local-env-breaks-config-tests.md`) **do not occur here.** If they appear, something added a `.env`.
- **`pytest -m "db and not s3"` against 55434** — 353 + F53's, including the captured `information_schema` row, the round trip both ways, all three digit-normalized phone searches, the two `autoescape` literals, the 51→50 + `messages_total == 51` window, the compiled-statement tenant assertion and **the recycled-phone test**. ⚠ `-m db` alone additionally pulls the `s3` tests, which need Docker for MinIO and are **not F53's** — leave those to CI.
- **`make fe-test`** — manage at 407 + F53's; **axe at zero violations**; the two `document.activeElement` assertions passing (they are the ones that fail if `tabIndex={-1}` was dropped); the five-keystroke burst firing exactly one request.
- **`make fe-build`** — both apps build with **no unused-import or unused-variable TS error**.
- **`make e2e`** — the two existing storefront specs green **and unchanged**. **F53 adds no e2e spec** — there is no manage-console harness at all (F58 builds it) — so an unchanged e2e count is the expected result, not a gap.
- **Working tree clean of the pre-run**: `git diff --stat backend/tests/conftest.py` prints nothing; `git status` shows no cluster data directory and no `.env`.
- **Before the PR opens**: `alembic heads` prints **exactly one head** after the rebase, and the renumbering edits are in the diff.

---

## What could go wrong in review

Every item here is a **recorded ruling**. A reviewer who raises one should find the reasoning rather than file a finding.

1. **"The spec says the migration is the last commit and it is the second."** **C1**, and it is the only correction in this plan backed by a measurement: 114 pre-existing `db` tests fail with the ORM columns and no migration, in this worktree, against the live cluster. D1's stated *reason* — one self-contained file, one rebase edit — is preserved and Task 9 keeps the renumber as a named step. **The most likely finding in the review.**
2. **"`revision = 0018` skips three numbers."** **C2.** `"0015"` is claimed by both F57 and F19 right now, with different filenames, which git merges cleanly and alembic then reports as multiple heads. A non-contiguous id is valid — verified: `alembic history` prints `0014 -> 0018 (head)` and `alembic heads` prints one head. The number is re-resolved at Task 9.
3. **"`command.downgrade(cfg, "-1")` contradicts four shipped round-trips."** **D12, and it is a stated departure rather than a correction.** All four hardcode (`:215`, `:341`, `:372`, `:494`) and that was right for them. F53 departs for one reason: three unmerged migrations are racing, and `"-1"` makes F53's block order-independent so the merge with F57's and F19's is plain concatenation. **F57's hardcoded `"0013"` is left exactly as it is.**
4. **"The list response ships `phone` — `OwnerBookingRow` deliberately does not."** **D6, argued rather than inherited.** A day list is a schedule; a customer directory is an index of people. The phone is the disambiguator for the shared-name case `ORDER BY name, id` already exists for, the search label promises search by phone, and **`notes` — the half D18's force actually lands on — stays detail-only.**
5. **"OTP rows should be filtered out of the log."** **D3, four independent reasons.** The masking ruling already made them safe to store *and read*; `message_log` is the Spam-Law evidence trail and understating send volume is the one thing it must not do; for a customer with no bookings they are the **only** evidence anything was sent; and excluding them costs a filter plus a rule to remember.
6. **"The phone leg's `AND booking_id IS NULL` looks redundant — the booking leg already covers those rows."** **It is the correctness of the feature.** Without it the phone leg re-admits every lifecycle row the booking leg attributed correctly — which is exactly the set that can belong to someone else after a correction or a carrier recycle. **The mutation check in §The local Postgres cluster is what proves the test actually catches its removal.**
7. **"Use `UNION` instead of `or_`."** A lifecycle SMS to the current phone matches **both** legs: `UNION ALL` renders it twice, `UNION` sorts the whole result to dedupe. `or_` needs neither and lets the planner do one scan.
8. **"Search has no index."** **D2.** A btree cannot serve an unanchored `%term%` **at all**; only a `pg_trgm` GIN index can, and that needs a `CREATE EXTENSION` this migration does not have the privilege for and nothing else in the product needs. The upgrade path and its threshold are in the migration comment.
9. **"`autoescape=True` is noise."** Without it a typed `_` or `%` returns the **whole tenant**. Two `db` assertions pin it.
10. **"Just search the raw term — why normalize digits?"** Because `customers.phone` only ever holds E.164, so `'+972501234567' ILIKE '%0501234567%'` is false and `%050%` matches nothing. The two most natural desk inputs would answer «אין תוצאות» for a customer who demonstrably exists.
11. **"One audit action is too coarse — split notes and tags."** **D8.** The split criterion this repo applies (`constants.py:129-134`) is *"is this a distinct question a security audit asks of this table"*, not *"is this a distinct field"*.
12. **"F51's `STAFF_UPDATED` ships `{from,to}` — why doesn't this?"** **D8, and F51 is correct there.** A display name is a label a staffer chose for herself; customer notes are free text about a **third party who never sees them**, `audit_log` has **no retention policy**, and platform operators read across tenants.
13. **"`tags` should be `JSONB` — that is the shape already in this repo."** **D1.** JSONB gives no element type (`["vip", 3, null]` is storable), containment needs a GIN index to be usable, and the future query is `unnest(tags)`, which `TEXT[]` answers natively. The epic already ruled the type.
14. **"`ADD COLUMN … NOT NULL DEFAULT` rewrites the table."** False on PG 11+, and measured here: `atthasmissing = t`, `attmissingval = {"{}"}`. Catalog-only.
15. **"A `POST /manage/customers/list` would match the house rules."** **It would be the first in the product.** Three shipped router docstrings rule real verbs and path parameters; `.claude/rules/` is Kotlin/Micronaut boilerplate for another codebase.
16. **"`test_staff_role_gating.py` should list the new routes."** **It must not.** Both walkers derive from the live route table, and a both-roles route in `OWNER_ONLY` reports as `unenforced_owner_only` and goes red.
17. **"No advisory lock on a concurrent edit."** **D7.** F51's lock protected an *at-least-one* invariant. A notes/tags edit is a single-row `UPDATE`; last-write-wins is what every text field in this product already gives, and an `updated_at` precondition would turn a rare recoverable overwrite into a frequent confusing 409.
18. **"`created_at` is missing from both models."** **D4 / F52's D7.** `customers.created_at` is meaningless as "first seen" after F15's collision branch, so it would be a plausible **wrong** "customer since" date on the one screen an owner would quote from.
19. **"`ar.ts` gained hand-copied Hebrew with nothing checking the translation."** Inherited from F15 through F34, F51, F52 and F57. **No parity guard is invented here**; `i18n.test.ts:258` catches an empty value and `:262` catches a missing key. **F45 owns the real fix.**
20. **"The audit rows are write-only."** Unchanged from F15's Risk 7. F53 adds one more action nothing renders. F19's plan named F53 as the first read surface; **F53 does not build it** (Out of scope), because a read surface for `audit_log` is a feature, not a side effect of a CRM screen.
