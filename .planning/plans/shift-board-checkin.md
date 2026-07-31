# Plan: Feature 34 — Live shift board + check-in (5s poll) (Epic SMC, phase SMC-5)

**Status**: Gate 2 self-approved 2026-07-31 under Interview Q1. **The design gate is SELF-APPROVED** by the user's 2026-07-31 ruling (`LOOP-STATE.md:1054`) — this entry no longer parks, and the spec's "Design gate — this one does not self-approve" section is **stale as written**; Task 0 amends it. The corrections C1–C7 below are amended into the spec in Task 0; the spec text is the binding statement of each resolution, this file the reasoning.

**Spec**: `.planning/specs/shift-board-checkin.md` (Gate 1 self-approved 2026-07-30, D1–D14, 499 lines, 12 of 13 adversarial findings folded in) · **Design**: `.planning/design/screens/shift-board/design.md` (**already at Revision 2** — see C1) · **Copy**: `.planning/design/screens/shift-board/copy.md` (34 keys, 10 rows still marked `PROPOSED`) · **Prototype**: `.planning/design/screens/shift-board/prototype.html` (clickable, fakes the tick, pause is pressable) · **Branch**: `feature/shift-board-checkin` · **Created**: 2026-07-31

TDD throughout. Local gate per task: `make lint` + `make test` for backend tasks; `make fe-test` + `make fe-build` for frontend ones; `make e2e` from Task 9 onward (this feature touches the console's built output). **`db`-marked tests are written here and executed only on CI** — there is no Docker locally. The tasks a local run cannot verify are listed in §"What a local run cannot prove".

F34 ships **one migration** — a single nullable `TIMESTAMPTZ` — and its ORM column in the same atomic task (D2).

**Path hygiene.** The repo path contains a space and a `+`. Quote every shell path. And git tracks `backend/` / `frontend/` **lowercase** while the on-disk directories are `Backend/` / `Frontend/`: `git add Backend/…` silently skips modified tracked files. Lowercase every pathspec and verify with `git show --stat`.

---

## Interview and spec rulings this plan is built on

| Ruling | Effect on the build |
|---|---|
| **Q1** — enumerated stop-list is F17/F18/F19/F20/F29/F48; F34 is not on it | Gate 2 self-approves. The privacy hand-off (spec Risk 9) is discharged to F20 and **re-nagged in the run report**; it does not stop the build. |
| **Design gate SELF-APPROVED, 2026-07-31** (`LOOP-STATE.md:1054`, F34 queue note `:56-65`) | No park. The spec's three "deck must be revised first" artifacts become **build tasks** — but see **C1**: two of the three revisions already landed on 2026-07-30. Task 1 is what actually remains. |
| **Q-1 = 5 seconds** · **Q-2 = a row does not navigate** · **Q-3 = undo always visible** · **Q-4 = one chronological list** | The spec's own stated defaults ship. Deck P-1…P-4 flip from `PROPOSED` to resolved in Task 1; no design work changes. |
| **Q-5 = NO** — the board does **not** become the landing section | F52 shipped and owns it. **The deck's P-5 recommends the opposite and must be flipped** (C2). `App.tsx`'s landing constant is untouched by this feature. |
| **Q3 / pre-decided #47** | `board.*` + `nav.board` land in **both** `he.ts` and `ar.ts`, Arabic values = the approved Hebrew, never `""`. `lng` stays `"he"`. |
| **pre-decided #38** | IS 5568 / WCAG 2.0 AA is a **legal** requirement. D14's pause/idle control and the D11 live-region rule in Task 8 are not optional polish, and **axe has no SC 2.2.2 rule** — the named vitest assertions are the only automated coverage of that criterion. |
| **D13 / F57's queue note** (`LOOP-STATE.md:88-91`) | The poll loop stays inside `BoardSection.tsx`. **F57 is the second caller and extracts the shared `usePoll` hook** — that is written into F57's queue entry, so F34 must not pre-extract it. |

---

## What moved since the spec was written (2026-07-30 → 2026-07-31)

F51 / F52 / F55 / F56 / F54 / F17 / F18 merged during what the spec expected to be a park. **Everything below is verified against the tree at this commit.** Where a spec citation still holds it is marked ✅ so the builder does not re-check it.

### Migrations — HEAD is **0013**, not 0011

`alembic heads` → **`0013 (head)`**. `Backend/migrations/versions/` now holds `0001`…`0013`; the two new ones are `0012_payments.py` (`down_revision = "0011"`) and `0013_lemonsqueezy_provider.py` (`down_revision = "0012"`).

**So today F34's migration is `0014`, revising `0013`.** D2's build-time rule stands unchanged and is exactly why this is not a problem: read `alembic heads`, take the next number, revise whatever HEAD then is. **Do not hardcode 0012/0011** — the spec's own naive reading — and do not hardcode 0014/0013 off this paragraph either if another migration lands first.

### `Backend/app/db/repositories/bookings.py` — shifted ≈ **+42 lines**. Every spec citation into this file is stale.

| Spec says | Actually | What it is |
|---|---|---|
| `:38-43` | **`:56`** | `insert` (the advisory-lock obligation docstring) |
| `:74-106` | **`:116` / `:135`** | `active_at` / `active_seats_at` |
| `:129-131` | **`:168`** | `set_manage_token_hash` |
| `:204-224` | **`:245-265`** | `confirm_attendance` — the predicate shape F34 copies |
| `:211-222` | **`:252-263`** | its `IS NULL AND status = 'confirmed'` guard |
| — | **`:267-307`** | `set_status` |
| **`:287-295`** | **`:328-336`** | **`cancel`'s identity-map docstring — the governing precedent for D4(5).** Verbatim: *"reading it off the `.returning()` scalar is the ONLY way to know that. The re-read cannot tell: `update(Booking)` … is ORM-enabled DML whose default `evaluate` synchronization stamps the SET values onto the identity-mapped instance whatever the database matched, and `by_id` hands that same instance back."* |
| `:302-307` | **`:343-348`** | `cancel`'s predicate |
| `:343-354` | **`:361-398`** | `reschedule` |
| `:403-414` | **`:437`** | `list_live_for_customer` |
| `:416+` | **`:457`** | `list_confirmed_without_manage_token` |

### `Backend/app/main.py` — the two handlers F34 rides moved

| Spec says | Actually | What |
|---|---|---|
| `:463-465` | **`:757-758`** | `@app.exception_handler(DomainNotFoundError)` — F34's 404 rides it |
| `:604-608` | **`:898-900`** | `@app.exception_handler(BookingTransitionInvalidError)` — F34's 409 rides it |
| — | `:734-735` | `NotAuthorizedError` → 403 (F31's) |
| — | `:668` | `app.state.owner_booking_service = OwnerBookingService(...)` |
| — | `:1028` | `app.include_router(owner_booking_router)` |

### `Frontend/apps/manage/src/App.tsx` — **restructured by F51/F52/F17. D10's implementation instructions no longer describe this file.**

The spec says «`SectionKey` gains `"board"`; `nav` gains `{ key: "board", label: t("nav.board") }`; `App.tsx:14, 50-56, 74-80`». None of those line numbers or shapes survive:

- `SectionKey` is a **nine-member** union at **`:17-26`** (`dashboard | profile | hours | types | terms | catalog | bookings | staff | gateway`). **The board is the TENTH section, not the seventh** — the spec's "seventh" is a stale count, not a design statement.
- There is no `nav` array. There is `const NAV: readonly NavItem[]` at **`:46-62`**, whose rows are `{ key, labelKey, roles }` — **`labelKey: string`, not a resolved `label`** (`interface NavItem` at `:40-44`). `nav` is derived at render: `reachable.map(item => ({ key: item.key, label: t(item.labelKey) }))` (`:121`).
- Every row carries a `roles` allowlist. `const ALL = ["owner", "shift_manager"] as const` (`:28`). The board takes `roles: ALL` — a board a shift manager cannot open is not a shift manager's board (spec D5), and this array is **cosmetics only**: the control is the server's `RoleGate` (the file says so at `:30-39`).
- **The landing constant is `useState<SectionKey>("dashboard")` at `:73`** — F52 changed it from `"profile"`. D10's sentence "The default landing section stays `profile`" is stale prose; **the ruling (Q-5 = NO) is satisfied by touching nothing**, because `dashboard` is NAV row 0 (`:50`) and `reachable[0]?.key` (`:118-120`) falls back there. Inserting the board after `bookings` cannot displace it.
- The render branch is `{activeKey === "x" && <XSection />}` at **`:135-143`**.

### Frontend infrastructure the spec assumed had to be added — **already shipped**

- **`axe-core` is already a devDependency of `apps/manage`** (`^4.12.1`), imported as `import { run } from "axe-core"` in `BookingsSection.test.tsx:4` and `GatewaySection.test.tsx:2`. F15's Task 14 added it. No package change.
- **`"test": "TZ=America/New_York vitest run"` is already pinned** in `apps/manage/package.json`. No package change.
- **`vi.useFakeTimers()` precedents exist** in `apps/manage/src/__tests__/CatalogSection.test.tsx` and `BookingsSection.test.tsx`.
- **`he.ts` and `ar.ts` grew by flat dotted-literal blocks per feature**, not nested objects: F15's at `he.ts:61+`, F51's at `ar.ts:113+`, F52's at `he.ts:243+` / `ar.ts:146+`, F17's at `ar.ts:193+`. The nested `nav: { profile, hours, types, terms, catalog }` at `he.ts:14-20` is pre-F15 and is **not** the pattern to follow. `he.ts` is 432 lines, `ar.ts` 255.

### Citations that still hold exactly — ✅ do not re-verify

- ✅ `owner_router.py:78-84` router construction; `:82` `Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))`; `:69-70` `_no_store`; `:99-110` `_row_fields`; `:113-114` `_row`; `:117-133` `_detail`; `:154-181` `GET /bookings`; `:168` the `Query(ge=1, le=BOOKING_LIST_MAX_LIMIT)` bound.
- ✅ `models/booking.py:26-53` declares every column as `mapped_column`; `attendance_confirmed_at` at **`:33-35`** is the exact shape to copy.
- ✅ `booking/owner.py`: error classes `:61-86`; `OwnerMutation` **`:95-112`** (spec said `:95-113`); `list_day` `:147-189`; the three `allowed_from` tuples `:250-293`; `_transition` **`:295-356`** (spec said `:234-356` — only the start moved); the identity-map comment **`:326-333`**; `_record` `:867`.
- ✅ `auth/dependencies.py:17-21` (generic 403 body), `:40-62` (`RoleGate`), `:46-48` (the "bites on the very next request" docstring), `:57-62` (the raise).
- ✅ `auth/service.py:87-95` `resolve_session` — reads, never writes. ✅ `core/config.py:24` `session_ttl_seconds = 60 * 60 * 12`.
- ✅ `db/repositories/staff_users.py:26-34` `by_id` filters `deleted_at.is_(None)` (spec said `:25-33`).
- ✅ `db/tenant.py:25-29` — `async with session_factory() as session, session.begin()` then the `set_config`. ✅ `db/session.py:59` `pool_pre_ping=True`, `:66` `expire_on_commit=False`.
- ✅ `tenancy/resolver.py:8-9` — "Caching is deliberately deferred to E5". ✅ `tenancy/middleware.py:72` calls it per request; `EXEMPT_PATHS` at `:28` is `/health` + docs.
- ✅ **`test_booking_owner_api.py:502`** — the detail literal, `attendance_confirmed_at` at `:506`. ✅ **`:422-432`** — the list-row literal inside `test_the_list_applies_the_documented_defaults` (`:409`), `attendance_confirmed_at` at `:427`. ✅ **`:649-664`** is `test_the_owner_slot_grid_carries_capacity_and_remaining` and its literal is `{"slots": [{starts_at, capacity, remaining}]}` — **no booking fields, not affected**. The spec's D6 correction is right on all three.
- ✅ `test_booking_owner_db.py:747-760` — the identity-map trap pinned in a docstring; `:786-800` the deliberately outcome-agnostic `gather` assertion.
- ✅ `test_booking_comms_db.py:788-812` — the two-clock sequential idempotency pattern (spec said `:788-811`).
- ✅ `BookingsSection.tsx:74-78` — the patch-in-place shape; `:110-121` the single `role="status"` region. ✅ `BookingDetail.tsx:365-369` — the `cancelled_at` `<Fact>`; `:232` the `role="status"`; `Fact` defined at `:22`.
- ✅ `api.ts:9-19` `ApiError {status, code, message}`; `:21-23` `errorMessage`; `:286-294` `OwnerBookingRow`; `:306-320` `OwnerBookingDetail`; `:343-345` the private `bookingPath()`.
- ✅ `lib/booking.tsx` exports `statusBadge` (`:22`), `isolateLtr` (`:32`), `bookingErrorText` (`:63`). ✅ `lib/jerusalem.ts` exports `jerusalemTime` (`:35`), `jerusalemIsoDate` (`:43`), `todayJerusalem` (`:74`).
- ✅ `e2e/a11y.spec.ts:10-19` — nothing intercepts the API; the console's e2e surface cannot log in. No E2E is promised.

---

## Seven corrections — recorded, resolved, amended into the spec in Task 0

The spec is binding and D1–D14 are **not** re-litigated. These are places where the document disagrees with the tree or with a post-dating ruling, and a plan cannot proceed without picking one side. Every resolution is the smaller edit.

### C1 — the deck revision the spec demands **already happened**; the spec's design-gate section is stale

The spec (`:331-336`) says `design.md`, `copy.md` and `prototype.html` "were authored against the first draft of this spec and now need a matching revision before the gate", listing three items. Verified against the files:

- `design.md` is at **"Revision 2 — 2026-07-30, to the spec's post-adversarial-review revision"** (`design.md:10`), with an explicit change table at `:12-17` covering **all three** items: D14's pause/idle (row 1), the `{401,403}` widening (row 2), D4(6)'s backoff (row 3), plus F-1's acceptance (row 4).
- `B-paused` (`design.md:276`), `B-idle` (`:277`) and a **sibling `B-403`** (`:279`) are in the state table — seventeen states, "and the list still may not shrink" (`:291`). §2.4 specs the control; §7.4 carries 2.2.2 as an explicit a11y-floor row; F-10 (`:439`) records that the 403's reload is honestly not a remedy.
- `copy.md:3` is **"Revised: 2026-07-30 (to the spec's post-adversarial-review revision — D14, D4.3's `{401,403}`, D4(6)'s backoff)"**, 34 keys (`:30`). `board.pause` / `board.pauseAria` / `board.resume` / `board.resumeAria` / `board.pausedAt` / `board.paused` / `board.idleStopped` / `board.resumed` at `:63-70`; **`board.accessEnded`** at `:111` (the 403's own sentence, generic by design, naming no role — §0 rule 10 at `:28`); `board.staleAt` / `board.staleBody` at `:51-52` revised for the stretching retry.
- `prototype.html` makes the pause pressable — the click handler at `:1021-1045` flips `S.paused`, the checklist at `:65` says *"Press «השהיה» inside the board. The beat meter stops"*, and `:1041`/`:1061` log the backoff and its reset.

**Resolution:** the spec's design-gate paragraph is amended to record that revision 2 discharged it, and **Task 1 is only what remains** — the status flips and the P-decisions the self-approval now has to resolve. Declined: re-doing the revision (it is done, and re-authoring 87KB of deck to reach the same content is the most expensive possible no-op).

### C2 — the deck's **P-5 recommends the opposite of the user's Q-5 ruling**

`design.md:424` — *"**P-5 — The board becomes the console's landing section, and F52 implements it.**"* The 2026-07-31 ruling is **Q-5 = NO**: F52 shipped, the dashboard stays (`LOOP-STATE.md:1054`).

**Resolution:** P-5 is flipped to **RESOLVED — NO** in Task 1, carrying the ruling's reason (F52 owns the landing decision and has already shipped it as a single constant, `App.tsx:73`). The *recommendation's* reasoning is kept as recorded history — it is the argument a later feature would reopen with — but it may no longer read as an open ask. **No code change follows**: satisfying Q-5 = NO means touching `App.tsx:73` not at all.

### C3 — **P-8 (the idle window) is a genuinely open user question that the self-approval leaves unanswered**

`design.md:426` — the idle window "is the only genuinely open question D14 leaves". The ruling resolves Q-1…Q-5 and says nothing about P-8. Without a value, Task 8 cannot be written.

**Resolution:** take the deck's own recommendation — **10 minutes**, `IDLE_STOP_MS = 10 * 60 * 1000`, one constant in `BoardSection.tsx`. The deck's reasoning is why it is safe to take rather than escalate: recovery is one press and the state says exactly why it stopped, so an over-eager window costs a tap, not a mystery. Recorded as a run-report line the user can overturn with a one-line follow-up. **The prototype's 45-second window is a review aid and must not be ported** — `design.md:426` says so explicitly, and shipping 45s would read as a bug.

### C4 — the board is the **tenth** section and `App.tsx` has no `nav` array

See §"What moved". The spec's D10 gives implementation instructions against a file that F51/F52/F17 rewrote.

**Resolution:** D10's *decision* is untouched — the board is its own section, «תורים» keeps its screen, the landing default is not F34's to change. Only its *mechanics* are re-pointed at the shipped shapes: a tenth `SectionKey` member, a `NAV` row `{ key: "board", labelKey: "nav.board", roles: ALL }` inserted **after `bookings`** (`:56`) and **before `staff`** (`:57`), and one render branch at `:135-143`. Inserting after `bookings` rather than at the top is what keeps Q-5 = NO true structurally.

### C5 — `CheckInOutcome` has no stated home, and `constants.py` is the wrong one

The spec shows the enum beside the repository writers but names no module. The reflex is `app/models/constants.py`, where `BookingStatus` / `AuditAction` / `StaffRole` live — but **every enum in that file is a persisted value**, and `CheckInOutcome` is never written anywhere.

**Resolution:** it lives in **`app/db/repositories/bookings.py`**, beside the writers that return it, following that file's own precedent for non-persisted return contracts: `BookingFact` (`:14`) and `CustomerHistory` (`:43`) are both declared there. `app/booking/owner.py` already imports `BookingsRepository` from this module, so the service gains no new dependency edge. Declined: `constants.py` (it would be the first non-persisted member and would invite a future migration author to widen a CHECK for it).

### C6 — `CheckInOutcome.ALREADY_CHECKED_IN` is read as "already clear" by the undo, and that reads wrong

The spec is explicit (`:222-223`): the undo "only ever answers WROTE / ALREADY_CHECKED_IN (read as 'already clear') / MISSING". A reviewer will read `undo_check_in` returning `ALREADY_CHECKED_IN` for a row that is **not** checked in and file it as a bug.

**Resolution:** keep the member — renaming it would be re-deciding a spec shape — and close the gap with the enum's own docstring, which states the two readings side by side: *"zero rows and the predicate's target state already holds — for `check_in` that is 'she is already checked in', for `undo_check_in` it is 'it is already clear'. Both are 200-unchanged."* Recorded in "What could go wrong in review" so the reviewer finds a ruling instead of raising a finding. Declined: a second enum (four members duplicated to rename one), and `NO_OP` (it would lose the fact that the *predicate's target state holds*, which is exactly what makes 200 the honest answer rather than 409).

### C7 — the forced-interleave tests must drive the **repository**, not the service

The spec's Testing section requires the two headline concurrency tests to reach the zero-row branch deterministically, and correctly rejects `asyncio.gather`. But it does not say at which layer, and at the **service** layer the interleave is unreachable by construction: `check_in`'s step 2 (`checked_in_at is not None ⇒ 200 unchanged`) and step 3 (`status != 'confirmed' ⇒ 409`) both short-circuit in Python **before** the guarded UPDATE, exactly as `_transition` does today (`owner.py:320-325`). A service-level "forced interleave" would assert the Python pre-check, not the zero-row branch — the same silent vacuity the spec calls out about `gather`.

**Resolution:** the two forced-interleave tests call `BookingsRepository.check_in` **directly**, with the loser's `tenant_session` held open across the winner's transaction (mechanics spelled out in Task 6). The service's mapping of the three outcomes onto 200 / 409 / 404 is proven separately at Task 4 against fakes, where it is a pure branch and needs no Postgres. Stated so nobody writes a test that cannot fail.

All seven are amended into the spec in **Task 0**, in the same PR — the `booking-comms.md` / F15 Task-0 precedent for a plan-phase spec amendment.

---

## Scope fence — read this before every task

**F34 ships the day's BOOKINGS on a board, and the board itself.** It is the shell the rest of the floor program attaches to, and it attaches nothing yet.

| Not in F34 | Whose |
|---|---|
| Staff cards, floor roles, break status, `GET /manage/floor` | **F57** (`LOOP-STATE.md:70-94`) — and F57, as the **second** poll caller, is where the shared `usePoll` hook gets extracted (D13) |
| Fitting rooms, room assignment, the rooms panel | **F36** |
| Queue tickets, QR self-check-in, live position, the public wall board | **F33** |
| Dispatch — assigning a ticket to a named staffer | **E6-proper** (needs F57's roles and F35's bell) |
| SOS paging, the escalation timer, the full-screen overlay | **F37** |
| Waitlist | **F58** |
| Wait-time analytics — `checked_in_at − starts_at` becomes computable here and **nothing computes it** | pre-decided #28 |
| Walk-in create from the board | **F50/SMC-6** |
| A realtime vendor, a version field, an event table, sockets | SMC ruling 3 — **F32 is subsumed and must never be built** |
| A polling abstraction, hook or module for F35/F37/F44 to import | **D13** — they inherit six documented mechanisms and one interval constant, nothing executable |

If a task's diff grows a staff row, a room, a ticket or a second poll target, it has left F34.

---

## Task 0 — This plan, and the seven spec amendments
`.planning/plans/shift-board-checkin.md` (this file), `.planning/specs/shift-board-checkin.md`

- Amend the header `Status:` line: **DESIGN GATE SELF-APPROVED 2026-07-31**, Q-1…Q-4 resolve to the spec's stated defaults, Q-5 = NO. Drop "DESIGN GATE PENDING" and the "the prototype gate parks the queue entry" clause from the Effort sentence.
- Amend §"Design gate — this one does not self-approve" (`:323-336`): retitle, record that **revision 2 of the deck discharged all three listed revisions on 2026-07-30** (C1), and re-point deliverable 3 ("the queue entry parks") at the ruling.
- Amend §"Questions the prototype must put to the user" (`:471-481`): Q-1…Q-4 marked **RESOLVED to the stated default**; the Q-5 section marked **RESOLVED — NO**.
- Amend **D2** with the observed HEAD: "`alembic heads` reads **0013** as of 2026-07-31, so the next number is 0014 — *and this sentence is not the source either*; re-read `alembic heads` at build time."
- Amend **D5**'s repository block with `CheckInOutcome`'s module (C5) and the dual-reading docstring for `ALREADY_CHECKED_IN` (C6).
- Amend **D10**'s implementation sentence with the shipped `App.tsx` shapes (C4) — tenth section, `NAV` row with `labelKey` + `roles: ALL`, landing constant untouched.
- Amend the **Testing** section's two forced-interleave bullets to say **repository-level** (C7).
- Add **P-8 = 10 minutes** to D14 as a plan-resolved value (C3).
- **Done when**: all seven are in the spec and this file is committed. No code, no tests.
- Commit: `docs(planning): F34 implementation plan — Gate 2 self-approved`.

---

## Task 1 — Reconcile the design deck with the 2026-07-31 ruling
`.planning/design/screens/shift-board/design.md`, `.planning/design/screens/shift-board/copy.md`

**First, because §8's resolutions and `copy.md`'s statuses are what Tasks 7 and 8 consume.** This is a status-and-decision pass, not a re-design: revision 2 already carries the content (C1).

- `design.md:3` — `Status` flips from "**DESIGN GATE — the user's, not the designer's**… does not self-approve" to **SELF-APPROVED under the 2026-07-31 ruling**, naming `LOOP-STATE.md:1054`. The Q2 reasoning stays as recorded history: it is why the prototype exists and why it is clickable.
- `design.md:418-427` §8 — every `P-` resolved, none deleted:
  - **P-1 → 5 seconds.** `POLL_INTERVAL_MS = 5000`.
  - **P-2 → a row does not navigate.**
  - **P-3 → undo always visible.**
  - **P-4 → one chronological list**, no bands.
  - **P-5 → NO** (C2) — the board is not the landing section; F52's dashboard stays. Reason recorded, recommendation superseded.
  - **P-6 → the `--color-warning-text` escalation ships.** Spec Risk 4 names this as the user's call; the self-approval takes the deck's recommendation, and the reasoning survives verbatim (plausible-looking rows beside a muted grey notice are what gets scanned past).
  - **P-7 → «הגיעה» ships** as the check-in verb, «נרשמה הגעה · HH:MM» as the recorded fact.
  - **P-8 → 10 minutes** (C3), with the prototype's 45s explicitly marked a review aid that must not be ported.
- `copy.md:3` — `Status` flips from "**awaiting the user at the design gate**" to **APPROVED under the 2026-07-31 self-approval; the Hebrew remains the user's to edit post-merge** (the F15 P-1/P-5 precedent — a one-line `he.ts`/`ar.ts` edit after merge, never a rebuild).
- The **ten `PROPOSED` rows** in `copy.md` flip to `APPROVED`: `board.staleAt` (`:51`), `board.pause` / `board.pauseAria` / `board.resume` / `board.resumeAria` / `board.pausedAt` / `board.paused` / `board.idleStopped` / `board.resumed` (`:63-70`), `board.accessEnded` (`:111`). Values unchanged — this is a status column edit, not a copy edit.
- **Nothing in `prototype.html` changes.** It already demonstrates the pause, the backoff and the terminal states; a prototype is a review artifact and editing it after the review it served would be rewriting evidence.
- **Done when**: no `PROPOSED` remains in `copy.md`; §8 carries a resolution for P-1…P-8 with P-5 = NO; both `Status` lines name the ruling; `grep -n "does not self-approve\|awaiting the user" .planning/design/screens/shift-board/` returns nothing.
- Commit: `docs(design): resolve the shift board's design gate under the 2026-07-31 ruling`.

---

# Part I — the backend

## Task 2 — The migration **and** the ORM column, as one atomic change (D2)
`Backend/migrations/versions/00NN_booking_check_in.py` (**new**), `Backend/app/models/booking.py`, `Backend/tests/test_migrations.py`

**The two halves ship together and this is not a preference.** `models/booking.py:26-53` declares every column explicitly as `mapped_column` and **no model↔migration parity test exists anywhere in `Backend/tests/`**. Without the ORM column, `update(Booking).values(checked_in_at=…)`, `Booking.checked_in_at.is_(None)` and `booking.checked_in_at` in `_row_fields` are each an `AttributeError` or a compile failure — i.e. **every backend line Tasks 3–5 specify fails to import**. Migration + model are the two-halves pattern `0008_bookings.py` / `models/booking.py` already follow.

**Resolve the revision id at build time. Do not read it off this document.**

```
cd "<repo>/Backend" && ./.venv/bin/python -m alembic heads
```

Take the next integer; set `down_revision` to whatever that command printed. **As of 2026-07-31 it prints `0013 (head)`**, so today the file is `0014_booking_check_in.py` with `revision = "0014"`, `down_revision = "0013"` — but if F19/F53 or any other entry lands a migration first, that is wrong and `alembic heads` is right. Everything below keyed to "this feature's migration" means exactly that and never a literal.

The whole DDL, and the docstring above `upgrade` is the D1 argument in three sentences (spec `:69-79` has the text):

```python
def upgrade() -> None:
    op.execute("ALTER TABLE bookings ADD COLUMN checked_in_at TIMESTAMPTZ")

def downgrade() -> None:
    op.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS checked_in_at")
```

Deliberately absent, each for a verified reason — state each as a comment so a reviewer can check the list is complete rather than short:

- **No `GRANT`.** `0008_bookings.py:107-110` issued table-level `GRANT SELECT, INSERT, UPDATE, DELETE ON bookings TO app_user`; table grants are column-agnostic and no column-level grant was ever issued here. (The `ALTER DEFAULT PRIVILEGES` gotcha in `.claude/CLAUDE.md` is about newly *created* tables.)
- **No `enable_tenant_rls`.** RLS is a table property, already forced by 0008. `test_every_tenant_id_table_has_forced_rls` stays green because F34 adds no table — **that test staying green unedited is the assertion that no table snuck in.**
- **No `_updated_at_trigger`.** `trg_bookings_updated_at` exists from `0008:105`.
- **No index, no CHECK, no default, no backfill.** Nothing filters or sorts on `checked_in_at` (the board reads the day and renders the value), so a partial index would serve no reader and cost every write. `NULL` is the only sentinel.

**The ORM column**, beside `attendance_confirmed_at` (`models/booking.py:33-35`, the exact shape to copy), carrying the D1 comment:

```python
checked_in_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
```

**Tests (`db`-marked, appended to `test_migrations.py`)** — follow that file's own convention: the round-trip test goes **last in the file**, after `test_migration_0013_round_trips` (`:353-380`), owns no fixtures, and wraps the downgrade in `try/finally: command.upgrade(cfg, "head")` because it mutates the live session-scoped schema.

1. `test_migration_00NN_round_trips` — upgrade applies, `checked_in_at` is a **nullable `timestamp with time zone`** on `bookings` (read from `information_schema.columns`), downgrade drops it, upgrade re-applies. Probe **both directions**, the `0013` docstring's rule (`:364-366`): a downgrade that silently no-ops would otherwise stay green while shipping an irreversible migration.
2. **The highest-value test in the feature — what the migration must prove it did *not* do.** After **this feature's migration** (i.e. at `head`, never at a hardcoded revision), pin all three byte-identically:
   - `pg_get_constraintdef` for the `status` CHECK — still `CHECK (status IN ('confirmed','cancelled','no_show','completed'))`;
   - `pg_indexes.indexdef` for `idx_bookings_slot_seat_unique` (`0008:88-92`);
   - `pg_indexes.indexdef` for `idx_bookings_tenant_customer_starts_unique` (`0009:32-36`).

   This is D1's promise made mechanical, and it earns its keep against a **future** edit: when E4 widens the CHECK for `pending_payment`, it collides with a pinned literal and a deliberate review, instead of colliding with nothing.
- **Done when**: `make lint` clean (ruff + `mypy app tests`), `make test` green (the new tests are `db`-marked → collected and deselected locally). ⚠ **The real proof runs on CI**; locally, mypy resolving `Booking.checked_in_at` is the whole signal.
- Commit: `feat(booking): bookings.checked_in_at — the arrival timestamp the board writes`.

## Task 3 — The `CheckInOutcome` writers and the re-read that defeats the identity map (TDD, `db`-marked)
`Backend/app/db/repositories/bookings.py`, `Backend/tests/test_booking_repositories.py`

**This is the subtlest part of the feature and it gets its own task.** Everything else in F34 is an `ALTER TABLE`, two thin routes and a `setTimeout`.

### Why an ORM re-read alone is wrong — the argument, not the assertion

`update(Booking)` on an `AsyncSession` is **ORM-enabled DML**. Its default `synchronize_session="evaluate"` stamps the SET values onto the identity-mapped instance **whatever the database matched**. The session factory is built `expire_on_commit=False` (`db/session.py:66`) and the whole operation runs inside one `tenant_session` transaction (`db/tenant.py:25`), so a trailing `by_id` hands back **that same in-memory object** without overwriting its already-loaded attributes.

So `if booking.checked_in_at is not None` after the write is decided by **the value this request just wrote in memory, never by the database**. It fires for *both* zero-row causes, and both failures are silent:

- the **409 branch becomes unreachable** — a check-in that lost to a concurrent cancel answers a false 200 "she is checked in" while the row is `cancelled` with `checked_in_at IS NULL`, i.e. **a check-mark on a cancelled booking with no audit row behind it**;
- the **render is poisoned too** — the losing writer's in-memory row carries *its own* timestamp, so a 200-unchanged built from it shows the **second** staffer's time, contradicting the exact guarantee this case exists to make.

The repo has been bitten by this once and has documented it four times. Cite all four in the code comment so the next reader does not have to rediscover it:

- `bookings.py:328-336` — `cancel`'s docstring, **the governing precedent**: *"`None` means the predicate matched nothing, and reading it off the `.returning()` scalar is the ONLY way to know that."*
- `owner.py:326-333` — `_transition` captures `from_status` **before** the write for the same reason.
- `test_booking_owner_db.py:747-760` — the trap pinned in a test docstring, verbatim: *"Reading the re-fetched row therefore cannot answer 'did I do this?'"*
- `bookings.py:245-265` — `confirm_attendance`, cited **only for the predicate shape**. It never returns `None` for zero rows (it unconditionally `return await self.by_id(...)`) and `ManageBookingService.confirm_attendance` renders whatever comes back, because a bride re-tapping her own link has exactly one possible meaning. It **deliberately declines** the discrimination check-in needs. It is not the precedent here.

### The mechanism

**Tests first**, appended to the existing `db`-marked module (`pytestmark = pytest.mark.db`), using its `_factory` / `_insert_booking` / `tenant_session` idioms.

`CheckInOutcome`, in `bookings.py` beside `BookingFact` (`:14`) and `CustomerHistory` (`:43`) — C5:

```python
class CheckInOutcome(StrEnum):
    WROTE              = "wrote"               # the predicate matched; THIS request wrote it
    ALREADY_CHECKED_IN = "already_checked_in"  # zero rows, target state already holds -> 200 unchanged
    NOT_CONFIRMED      = "not_confirmed"       # zero rows, status != confirmed        -> 409
    MISSING            = "missing"             # the row is gone / soft-deleted        -> 404
```

with C6's dual-reading docstring on `ALREADY_CHECKED_IN`.

Both writers are **one guarded UPDATE + one identity-map-defeating re-read**, and both return `tuple[CheckInOutcome, Booking | None]` — a bare `Booking | None` cannot express three answers:

```python
async def check_in(
    self, session: AsyncSession, tenant_id: UUID, booking_id: UUID, *, at: datetime
) -> tuple[CheckInOutcome, Booking | None]:
```

1. `update(Booking).where(tenant_id, id, checked_in_at IS NULL, status == 'confirmed', deleted_at IS NULL).values(checked_in_at=at).returning(Booking.id)` — the scalar is the only honest "did I write?".
2. **The re-read**: `select(Booking).where(tenant_id, id, deleted_at IS NULL).execution_options(populate_existing=True)`. `populate_existing` overwrites the identity-mapped instance's attributes from the row the database actually holds, undoing `evaluate` synchronization's stamp; under READ COMMITTED that statement sees the other transaction's commit. **One statement, one documented flag, and it fixes the discrimination and the rendering together.**
3. Classify from `(scalar, refreshed row)` and **never** from the caller's loaded object:
   - scalar not `None` → `(WROTE, refreshed)`
   - refreshed `None` → `(MISSING, None)`
   - `refreshed.checked_in_at is not None` → `(ALREADY_CHECKED_IN, refreshed)`
   - else → `(NOT_CONFIRMED, refreshed)`

`undo_check_in(self, session, tenant_id, booking_id)` — same shape, predicate `tenant_id AND id AND checked_in_at IS NOT NULL AND deleted_at IS NULL`, **no status guard at all** (D5's `/confirm` precedent, `owner.py:250-259`: a mis-tap is correctable whenever it is noticed). It therefore only ever answers `WROTE` / `ALREADY_CHECKED_IN` / `MISSING` — but it uses **the same refreshed read**, so a concurrent undo renders the database's `NULL` and not its own.

**Declined**, and each for a verified reason:
- A column-only Core `select(Booking.status, Booking.checked_in_at)`. It answers the discrimination equally well but **leaves the entity poisoned for rendering**, so it needs a second re-read anyway.
- `pg_advisory_xact_lock`. F15 takes it for the reschedule because that *picks a seat from a count* (`bookings.py:56`); check-in reads and writes one column on one row and has no cross-row invariant to serialise. Adding it would serialise every check-in in the boutique against every public booking create, for nothing.
- `session.refresh()`. It expires and reloads the whole instance and is the same statement with more surface; `populate_existing` on the select we already need is the smaller diff.

**Tests written first** (all `db`-marked): `check_in` on a `confirmed` row → `WROTE` + the timestamp; on an already-checked-in row → `ALREADY_CHECKED_IN` + **the first timestamp**; on a `cancelled` / `no_show` / `completed` row → `NOT_CONFIRMED`, nothing written; on a soft-deleted row → `MISSING`; on an unknown id → `MISSING`. `undo_check_in` on a checked-in row → `WROTE` + `NULL`; on a never-checked-in row → `ALREADY_CHECKED_IN`; on a **cancelled but checked-in** row → `WROTE` (the no-status-guard ruling, asserted); soft-deleted → `MISSING`. Every predicate keeps `deleted_at IS NULL` and the redundant `tenant_id` — the house defence-in-depth `BookingsRepository`'s own class docstring states.

- **Done when**: `make lint` clean, `make test` green (`db`-marked → deselected locally), `make test-db` green **on CI**.
- Commit: `feat(booking): check-in writers returning a three-valued outcome off a refreshed read`.

## Task 4 — Two `AuditAction` members and the two service methods (TDD, fast)
`Backend/app/models/constants.py`, `Backend/app/booking/owner.py`, `Backend/tests/test_booking_owner_service.py`

**`AuditAction` gains two members** — **no migration**: `audit_log.action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`), which is the same basis on which F15 added seven (`constants.py:113-119`) and F51 added its block:

`BOOKING_CHECKED_IN = "booking_checked_in"` · `BOOKING_CHECK_IN_UNDONE = "booking_check_in_undone"`

**Tests first**, appended to the existing fast module (fakes, no Postgres — `test_booking_owner_service.py`'s fake session factory is the `test_storefront_validation.py` scaffold, and a statement escaping to a real session raises rather than passing silently).

Two methods on the existing `OwnerBookingService`, one `tenant_session` each, the `_transition` five-step shape (`owner.py:295-356`):

```python
async def check_in(self, tenant_id, booking_id, *, staff) -> OwnerMutation
async def undo_check_in(self, tenant_id, booking_id, *, staff) -> OwnerMutation
```

`check_in`: load (missing ⇒ `BookingNotFoundError` → 404) → `checked_in_at is not None` ⇒ **200 unchanged, `changed=False`, no audit row** → `status != 'confirmed'` ⇒ `BookingTransitionInvalidError` → 409 → guarded write → **branch on the repository's outcome, never on the loaded object** → audit row **only on `WROTE`** → commit.

The two Python pre-checks are steps 2 and 3 of the shipped shape and they **stay** — they are what makes the answer honest in the uncontended case (`owner.py:320-325`). What is new is step 4's aftermath: it is the **repository**, not the service, that says which of the three things happened, because only the repository holds the `.returning()` scalar and the refreshed row at the same moment. Map:

| Outcome | Answer |
|---|---|
| `WROTE` | `OwnerMutation(booking=refreshed)`, audit `BOOKING_CHECKED_IN` with `details={"checked_in_at": "…Z"}` |
| `ALREADY_CHECKED_IN` | `OwnerMutation(booking=refreshed, changed=False)`, **no audit row** — the outcome the caller wanted is the outcome that holds, the audit row belongs to the staffer who actually wrote it, and a 409 here would be a lie told to the person who was right |
| `NOT_CONFIRMED` | `raise BookingTransitionInvalidError(...)` — rolls the transaction back **before** the audit row |
| `MISSING` | `raise BookingNotFoundError` |

`undo_check_in`: load (missing ⇒ 404) → `checked_in_at is None` ⇒ 200 unchanged, no audit row → clear → `WROTE` ⇒ audit `BOOKING_CHECK_IN_UNDONE` with `details={"previous_checked_in_at": "…Z"}`; anything else ⇒ 200 unchanged, no audit row, rendering the **refreshed** row. **No status guard, so its only failure is 404.**

**`previous_checked_in_at` is load-bearing**: clearing the column destroys the only copy of the arrival time and `bookings` has no history table — the same argument D2 made for carrying `old_customer_id` on a phone correction. The timestamp must be captured **before** the write, for exactly the reason `_transition` captures `from_status` before the write (`owner.py:326-333`).

**No clock bound on check-in, in either direction.** A bride arriving twenty minutes early is the ordinary case the board exists for; a `starts_at <= now` guard would refuse it. An early arrival is not a lie, it is a fact with a timestamp.

**A status transition never touches `checked_in_at`.** `set_status` is not edited and `cancel` is not edited. Marking a checked-in bride `no_show` looks contradictory and the temptation is to clear the timestamp inside `set_status`; declined, because it would make F15's one status writer do two things, destroy the only record of an arrival as a side effect of an unrelated verb, and presume the owner meant the arrival was wrong when she may have meant the bride left. The explicit undo is the remedy. **Asserted by a db-marked test in Task 6**, so the absence is a decision rather than an oversight.

**Tests here** (fakes, run locally): `confirmed` ⇒ written + exactly one audit row with `actor_id=staff.id`, `entity=str(booking.id)`; repeat ⇒ 200, `changed=False`, **zero** audit rows; `cancelled` / `no_show` / `completed` ⇒ 409, nothing written, no audit row; **no clock bound** — a booking two hours in the future checks in; undo of a checked-in row ⇒ cleared + one audit row carrying `previous_checked_in_at`; undo of a never-checked-in row ⇒ 200, no audit row; undo of a **cancelled** checked-in row ⇒ succeeds (D5's ruling, asserted); a repository `NOT_CONFIRMED` raises **and** `audit.record` was never called (the rollback assertion); the service branches on the outcome enum and **never** reads `booking.checked_in_at` after the write (assert by feeding the fake repository an outcome that disagrees with the row it hands back — this is the test that fails if anybody re-introduces the poisoned read).

- **Done when**: `make lint` + `make test` green, **locally and on CI**.
- Commit: `feat(booking): check-in and undo-check-in service methods with their audit rows`.

## Task 5 — `checked_in_at` on the wire, the two routes, and the two shipped literals (TDD, fast)
`Backend/app/booking/schemas.py`, `Backend/app/booking/owner_router.py`, `Backend/tests/test_booking_owner_api.py`

**Tests first**, in the existing module on the `test_catalog_api.py` template it already follows.

**Schema (D6).** `OwnerBookingRow` gains `checked_in_at: datetime.datetime | None` (`schemas.py:107-123`, beside `attendance_confirmed_at` at `:119`), which `OwnerBookingDetail` inherits by subclassing (`:133`). `_row_fields` (`owner_router.py:99-110`) gains one line. **The board only ever reads the list, so the field must be on the row.**

**Two routes**, same router, same verb-sub-path convention as the shipped `/no-show`, `/complete`, `/resend-link` (D7's ruling: path parameters and real HTTP verbs are the `/manage` convention here; the `.claude/rules` RPC/`@QueryValue` guidance is Kotlin boilerplate for another codebase and does not apply):

```
POST /manage/bookings/{booking_id}/check-in       -> OwnerBookingDetail
POST /manage/bookings/{booking_id}/undo-check-in  -> OwnerBookingDetail
```

Both are `_detail_of(...)` handlers in the `confirm_booking` / `mark_no_show` shape (`owner_router.py:200-238`), both inherit `_no_store` and the router-level `RoleGate` by construction (`:78-84`). **No new request body** — the booking id is in the path and nothing else, so neither needs a `ForbidExtraModel`. **No post-commit send**: check-in texts nobody, the `no-show`/`complete`/`confirm` row of F15's post-commit table (D13).

**Declined:** one `POST .../check-in` with a `{"checked_in": bool}` body. Two verbs, two guards (check-in requires `status = 'confirmed'`; the undo requires nothing), two audit actions, two `details` shapes — one handler would collapse all of that into a body of `if`s, which is the argument D7 already made against a single `PATCH` carrying `status`.

**Zero new error codes, zero new handlers**, and this is a real result rather than an accident of laziness:

| Condition | Status | Code | Rides |
|---|---|---|---|
| Unknown booking id (incl. another tenant's, indistinguishable under RLS) | 404 | `NOT_FOUND` | `BookingNotFoundError` ⊂ `DomainNotFoundError`, handler at **`main.py:757-758`** |
| Check-in on a booking that is not `confirmed` | 409 | `BOOKING_TRANSITION_INVALID` | F15's, handler at **`main.py:898-900`**; its docstring already scopes itself to this class of refusal (`owner.py:61-69`) |
| Repeat check-in, repeat undo, undo of a never-checked-in booking | **200** | — | not errors, by D4(5)/D5 |
| No session / expired | 401 | `NOT_AUTHENTICATED` | app-wide |
| A role outside `{owner, shift_manager}` | 403 | `NOT_AUTHORIZED` | F31's, `main.py:734-735`, generic body |

**`SPEC_ERROR_CODES` (`test_booking_owner_api.py:108-120`) is asserted by set equality and F34 adds no member to it.** Declined `BOOKING_ALREADY_CHECKED_IN`: a repeat check-in is a 200, so the code would name a condition that never answers an error — and `main.py` has no error registry, so every invented code is a handler somebody has to remember or the typed error ships a bare 500.

**Test edits, and the two literal updates are the visible, reviewed part of this task:**

- **Two rows added to `ROUTES` (`:92-107`)**, which automatically extends three shipped walks with no new test written: `test_every_route_requires_authentication` (`:330`), `test_both_staff_roles_are_admitted_on_every_route` (`:340`), `test_an_unadmitted_role_is_403_on_every_route` (`:360`), `test_every_route_is_wired_and_reaches_the_service` (`:378`) and the `cache-control: no-store` parametrization (`:393`).
- `FakeOwnerBookingService` gains `check_in` / `undo_check_in`; each route reaches its own service method with the right arguments (the `test_each_transition_verb_has_its_own_handler` shape at `:564`); a service `BookingTransitionInvalidError` leaves as 409 and `BookingNotFoundError` as 404; `test_every_mutation_answers_the_same_detail_shape` (`:579`) covers both new verbs.
- ⚠ **`test_booking_owner_api.py:502`** — the detail literal in `test_the_detail_carries_the_phone_the_notes_and_the_terms_evidence` (`:497-521`) gains `"checked_in_at": None` beside `"attendance_confirmed_at": None` (`:506`). **Verified: this citation still holds exactly.**
- ⚠ **`test_booking_owner_api.py:422-432`** — the list-row literal inside `test_the_list_applies_the_documented_defaults` (`:409`) gains the same key beside `:427`. **Verified: still holds exactly.**
- ✅ **`:649-664` is NOT touched.** `test_the_owner_slot_grid_carries_capacity_and_remaining`'s literal is `{"slots": [{starts_at, capacity, remaining}]}` — no booking fields, so `checked_in_at` cannot reach it. The spec's D6 correction of an earlier draft that named `:657` is right, and **there is no third literal**: `grep -n "attendance_confirmed_at" tests/test_booking_owner_api.py` returns exactly `:427` and `:506`.

  **These two edits are deliberate, reviewed, and are the point of pinning a whole-payload literal.** They red-fail the moment the schema field lands, which is why the schema, the router and the two literals ship in **one commit**: a wire-shape change that does not break a pinned literal would mean the literal was not pinning the wire shape.
- **`tests/test_staff_role_gating.py` — no edit, and the coverage is real rather than absent.** Its walker reads `allowed_roles` off the **live** route table (`:131-140`), so the two new routes are policy-checked for free by `test_every_manage_route_is_role_gated` (`:142`) and — the one that matters — `test_route_table_matches_the_permission_matrix` (`:184-211`), which **asserts every `/manage` route admits `shift_manager` unless `OWNER_ONLY` pins it**. Neither new route joins `OWNER_ONLY` (`:69-79`, nine rows: terms publish, four staff, four gateway), so shift-manager admission is **asserted**, not merely inherited. `test_shift_manager_is_admitted_everywhere_except_terms_publishing` (`:324`) walks it end to end for a real 403/200. Named here so the reviewer can see the coverage rather than look for a missing test.
- `test_no_route_is_registered_twice_across_routers` stays green untouched — four routers mount `/manage` and a duplicated `(method, path)` would silently shadow.

- **Done when**: `make lint` + `make test` green, **locally and on CI**. This is the milestone task: the full route table, both new verbs and the wire shape are exercised end to end with no Postgres.
- Commit: `feat(booking): check-in routes and checked_in_at on the owner booking row`.

## Task 6 — The `db`-marked concurrency suite, with a **forced interleave** (written here, executed on CI)
`Backend/tests/test_booking_owner_db.py`, `Backend/tests/test_booking_isolation.py`

NullPool engines in `try/finally`, the `app_role_url` fixture (never the superuser), frozen module-constant clocks injected as `clock=lambda: NOW` — the `test_booking_service.py:51-93` idioms this module already uses.

### The two headline tests must NOT use `asyncio.gather`, and here is the mechanism that replaces it

`gather` does not order two transactions, so there is no defined "first writer" and no forced interleave. **The repo's own analogue of this race says so in its own comment**: `test_a_customer_cancel_landing_first_is_a_409_and_writes_no_owner_audit_row` (`:747`) uses `gather` and then asserts deliberately outcome-agnostically — *"The only claim that matters, and it holds whichever writer won"* (`:786-790`) — precisely because of this.

Worse for F34 specifically: under `gather` the loser most often loads **after** the winner commits, takes the service's Python pre-check and **never reaches the guarded UPDATE at all** — so the zero-row branch D4(5) exists for would be green without ever executing. Per **C7**, that also means these two tests drive the **repository** directly, never the service.

**The interleave, concretely.** `tenant_session` is `async with session_factory() as session, session.begin()` (`db/tenant.py:25`), so **exiting the context manager is the commit**, and two nested `tenant_session`s on the same factory take two separate pool connections. Under READ COMMITTED, each statement sees data committed as of statement start — which is what makes the loser's UPDATE see the winner's write:

```python
# The LOSER's session, held open across the winner's entire transaction.
async with tenant_session(factory, tenant_id) as loser:
    booking = await repo.by_id(loser, tenant_id, booking_id)      # the read
    assert booking is not None and booking.checked_in_at is None  # the pre-check WOULD pass

    # The WINNER commits in a SECOND session while the loser holds its read.
    async with tenant_session(factory, tenant_id) as winner:
        await repo.cancel(winner, tenant_id, booking_id, at=NOW, by=BookingCancelledBy.CUSTOMER.value)
    # ^ exiting this block is the commit.

    # Only now does the loser's guarded UPDATE run. It matches ZERO rows.
    outcome, refreshed = await repo.check_in(loser, tenant_id, booking_id, at=LOSER_AT)
```

**Test A — "a cancel landing between the read and the write ⇒ 409".** The interleave above. Assert `outcome is CheckInOutcome.NOT_CONFIRMED`; **and assert `refreshed.checked_in_at is None`** — *that* is the assertion that fails if the discrimination is read off the poisoned in-memory object, because `evaluate` synchronization has already stamped `LOSER_AT` onto it. Then, at the service level in the same test, assert 409, **no** audit row, and the transaction rolled back.

**Test B — "a concurrent check-in landing in the gap ⇒ 200 unchanged carrying the FIRST writer's timestamp".** Same forced interleave, the *other* cause of zero rows: the winner's second session calls `check_in(..., at=FIRST_AT)`. Assert `outcome is CheckInOutcome.ALREADY_CHECKED_IN` and **`refreshed.checked_in_at == FIRST_AT`, explicitly `!= LOSER_AT`**. **This pair is what proves the discrimination is real — either one alone can be passed by a coin flip.**

**Test C — "the first timestamp survives", the sequential two-clock service test.** The `test_booking_comms_db.py:788-812` pattern **verbatim**: two `OwnerBookingService` instances, `clock=lambda: NOW` and `clock=lambda: NOW + 2h`; `first_tap.check_in(...)` then `later_tap.check_in(...)`; assert **both answer 200**, both read back `NOW`, and exactly **one** `audit_log` row of `BOOKING_CHECKED_IN`.

**If a `gather` test is kept as well**, its assertions must be set-shaped like `:786-800` and it must **not** claim to prove the 409.

**Also in this task:**

- Check-in then `/complete`, and check-in then `/no-show`: `checked_in_at` **intact** in both. D5's declined auto-clear, asserted as a decision rather than left as an oversight.
- Undo of a **cancelled but checked-in** booking succeeds and writes its audit row (the no-status-guard ruling).
- `list_day` returns `checked_in_at` on the row (extend `test_the_day_list_returns_cancelled_rows_ordered_by_start_then_seat` at `:1198` or add a sibling — do not rewrite its ordering assertions).
- Exactly one audit row per write with `actor_id=staff.id`, `entity=str(booking.id)`, `details` carrying `checked_in_at` / `previous_checked_in_at`; **a no-op writes none**.
- **RLS isolation** (`test_booking_isolation.py`): tenant B's staff can neither read nor check in tenant A's booking — **404, indistinguishable from missing**. The `:1274` pattern.
- **Done when**: `make test-db` green **on CI**. Locally these collect and skip; `make lint` (mypy over `tests`) is the only local signal.
- Commit: `test(booking): forced-interleave check-in concurrency and RLS isolation`.

⚠ **A first CI run failing on a test bug here is expected and budgeted** (`.memory/boutique-ci-first-run-surprises.md`): these assertions debut on CI, and a forced interleave is exactly the shape that bites on first execution. Before believing a red, check `continue-on-error` on the job.

---

# Part II — the frontend

## Task 7 — i18n, the API client, and the tenth nav item
`Frontend/apps/manage/src/i18n/he.ts`, `…/i18n/ar.ts`, `…/api.ts`, `…/App.tsx`, `…/__tests__/api.test.ts`

**Tests first** in `api.test.ts`, the shipped fetch-mock pattern.

- **`he.ts`** — a new block appended as **flat dotted literals** (the F15 `:61+` / F52 `:243+` / F17 shape, **not** the pre-F15 nested `nav: {}` object at `:14-20`): `"nav.board"` plus the 33 `board.*` keys, **every row of `copy.md` verbatim**. Transcribe the tables, not the header's count. Mechanical checks that ride along, from `copy.md` §0: zero exclamation marks in the added block; no string naming a **role** on the 403 path (`board.accessEnded` says only that there is no permission and who to ask — §0 rule 10).
- **`ar.ts`** — the **same keys**, values = the approved Hebrew standing in untranslated, **never `""`** (i18next's `returnEmptyString` renders `""` rather than falling back, so a premature switch would blank the page). Appended as its own commented block, the `:113` / `:146` / `:193` shape. `lng` and `fallbackLng` stay `"he"`; no switcher; `i18n/index.ts` **unchanged**.
  ⚠ **Nothing keeps `ar.ts` in sync with `he.ts`** — no parity guard exists and F34 does not invent one (spec Risk 6, inherited from F15's Risk 5).
- **`api.ts`** — `checked_in_at: string | null` on the `OwnerBookingRow` interface (`:286-294`, beside `attendance_confirmed_at` at `:290`; `OwnerBookingDetail` inherits it by `extends`), plus **two** wrappers on the exported `api` object using the existing private `bookingPath()` (`:343-345`), in the `confirmBooking` / `noShowBooking` shape (`:606-616`):
  ```ts
  checkInBooking(bookingId: string): Promise<OwnerBookingDetail>
  undoBookingCheckIn(bookingId: string): Promise<OwnerBookingDetail>
  ```
  No case conversion — this app speaks the backend's snake_case verbatim (`api.ts:1-5`).
- **`App.tsx`**, three edits against the **shipped** shapes (C4):
  - `SectionKey` (`:17-26`) gains `| "board"` — the **tenth** member;
  - `NAV` (`:46-62`) gains `{ key: "board", labelKey: "nav.board", roles: ALL }` **after the `bookings` row (`:56`) and before `staff` (`:57`)**;
  - one render branch beside `:141`: `{activeKey === "board" && <BoardSection />}`.
  - **`const [section, setSection] = useState<SectionKey>("dashboard")` at `:73` is NOT touched.** Q-5 = NO, and satisfying it means changing nothing: `dashboard` is NAV row 0, so both the initial state and the `reachable[0]?.key` fallback (`:118-120`) still land there.
- **No `vite.config.ts` change** — every endpoint is under `/manage`, already proxied.
- **No `test_frontend_constant_parity.py` change** — `POLL_INTERVAL_MS`, `IDLE_STOP_MS` and the board's page limit mirror **no server bound** (D3). The board asks for 50 and does **not** hardcode `BOOKING_LIST_MAX_LIMIT`: the router declares `Query(ge=1, le=BOOKING_LIST_MAX_LIMIT)` (`owner_router.py:168`), so a client pinned to today's ceiling would start 422-ing the day the ceiling drops — and that constant is unguarded, since `MIRRORS` covers `validation.ts` files only.
- **No `lib/booking.tsx` change and no `lib/jerusalem.ts` change** — `statusBadge`, `isolateLtr`, `bookingErrorText`, `jerusalemTime`, `jerusalemIsoDate` and `todayJerusalem` are imported as they are. F34 therefore adds nothing for `qa-greps.sh`'s unzoned-formatter grep to find (D12).
- **Done when**: `make fe-test` + `make fe-build` green; the console renders a tenth nav item that swaps to an empty panel; `pnpm -r lint && pnpm -r typecheck` clean.
- Commit: `feat(manage): board i18n, check-in API wrappers and the tenth nav item`.

## Task 8 — `BoardSection` — the poll loop, the six D4 mechanisms and D14's pause
`Frontend/apps/manage/src/components/BoardSection.tsx` (**new**), `…/__tests__/BoardSection.test.tsx` (**new**)

**Tests first**, the `CatalogSection.test.tsx` pattern (`vi.mock("../api")` with `importActual` for `ApiError` / `errorMessage`, fixture builders, `vi.mocked`) **plus `vi.useFakeTimers()`**.

**Three constants, at the top of the file, each with its "why this number" comment:**

```ts
const POLL_INTERVAL_MS = 5_000;   // P-1 / spec Q-1. One constant; the pilot or F29 may lower it.
const MAX_BACKOFF_MS   = 60_000;  // D4(6)'s cap. Doubling from POLL_INTERVAL_MS.
const IDLE_STOP_MS     = 600_000; // P-8, 10 minutes (plan C3). NOT the prototype's 45s.
const PAGE_LIMIT       = 50;      // BOOKING_LIST_DEFAULT_LIMIT. Not parity-guarded — see Task 7.
```

**The loop is `schedule-after-settle`, not `setInterval`.** The next tick is armed from the previous request's `.finally()`, so **at most one poll is in flight per tab by construction** — there is nothing to abort and no in-flight flag to get wrong. Declined: `setInterval` + `AbortController` (two mechanisms and a cancellation path to test, to reproduce a property one `setTimeout` gives free) and any `useSWR` / `react-query` dependency (a data-fetching library for one polled endpoint in an app whose other nine sections are hand-written `fetch`).

**One monotonic `generationRef`.** Every poll captures the generation at issue time and applies its result only if it is unchanged. The mutation settle, the date roll, the manual retry and resume all bump it — so a poll issued for yesterday can never paint today's board, and the one poll that could still be in the air when a staffer taps is discarded.

### The six D4 mechanisms → the named assertions. **None of these may be folded away as "covered by another."**

| # | D4 mechanism | The test that proves it |
|---|---|---|
| 1 | **No overlap** — arm-on-settle | *exactly one request per tick, and never two in flight*: advance timers while a fetch is unresolved, assert the call count did **not** grow |
| 2 | **No stale apply** — one generation | *a poll response issued before a check-in is discarded and the row keeps the mutation's value* |
| 3a | **Hidden tab** | *`document.hidden` pauses the loop*; *a `visibilitychange` back to visible fetches **immediately** rather than after the interval* |
| 3b | **401 terminal** | *a 401 stops the loop* — advance several intervals, assert **no further calls** — and renders `board.sessionEnded` |
| 3c | **403 terminal** | *a 403 stops the loop the same way* and renders `board.accessEnded`. **A SEPARATE test from the 401** — the two arrive by different code paths (`resolve_session` returning `None` vs `RoleGate` raising, `auth/dependencies.py:57-62`), carry different copy, and the first draft's terminal set omitted 403 entirely. Without this rule a demoted tab hammers `/manage/bookings` at 0.2 req/s forever while the demotion has **no visible effect**, silently defeating F31's "demotion bites on the very next request" on the one screen in the product that keeps making requests after a revocation — and F51, which makes demotion possible, has now merged. Nothing catches it above the component: `grep -rn "status === 401\|status === 403\|NOT_AUTHORIZED" Frontend/apps/manage/src` is empty. |
| 4a | **Not optimistic** | *check-in patches the row from the response* (the `BookingsSection.tsx:74-78` shape), *the control is disabled while in flight*, *a double-tap fires one request* |
| 4b | **The suppressed tick is re-armed** | *after a **successful** check-in, advancing the interval issues another poll* — **and its own separate test** — *after a **FAILED** check-in too*. The arming lives in the mutation's `.finally()`, **never in its success path**. Without these two the board silently stops converging the first time a staffer acts, **and every other test on this list still passes** |
| 5 | **Idempotent by predicate** | server-side (Tasks 3, 4, 6). Client-side the only assertion is 4a's double-tap |
| 6 | **Failure backoff** | *consecutive failed ticks back the interval off and a success resets it*: fail N ticks, assert the gap between calls **grows and caps** at `MAX_BACKOFF_MS`; then answer one 200 and assert the next gap is back to `POLL_INTERVAL_MS`. A 401/403 is **not** a "failure" for this purpose — those are terminal by 3b/3c and stop the loop outright. Three lines in the same `.finally()` that already arms the tick |

### D14, D11, D12 — the rest of the named assertions

- **the pause control stops the loop and resume fetches immediately**: tap «השהיה», advance several intervals, assert **no calls**; tap «חידוש», assert a call **before** the interval elapses.
- **the idle stop fires** after `IDLE_STOP_MS` with no interaction, and **one tap resumes**.
- **the announced region does not change on a poll tick** and **does** change on a check-in and on a pause (D11 + D14). A `role="status"` update every five seconds is an AA failure in practice however green the automated check comes back, and pre-decided #38 makes AA a **legal** requirement. Announced output is user-initiated only; a poll that changes rows repaints them **silently**; no shimmer, no pulse, no flash on refresh — which serves `prefers-reduced-motion` from the same rule.
- **a Jerusalem date roll refetches for the new day** — `todayJerusalem()` is recomputed **every tick**, not captured at mount, because a counter tablet crosses midnight (pre-decided #27's own device). The tick compares the current Jerusalem date to the one it is showing and, when it rolls, bumps the generation and refetches.
- **a failed poll with rows on screen keeps the rows and marks stale**; **a failed *first* fetch shows the outage register**. Two different states, and the stale copy must stay true as the backoff stretches the retry toward 60s (`copy.md:51-52` is already written for it).
- **the truncation line appears only when `total > items.length`**, pointing at «תורים». A hidden bride is the one failure a board may not have, so the truncation is stated rather than absorbed.
- **an axe pass at zero violations** — `import { run } from "axe-core"`, the `BookingsSection.test.tsx:241` shape. ⚠ **Explicitly not sufficient**: **axe has no SC 2.2.2 rule**, so the pause and idle assertions above are the only automated coverage of a Level A criterion and **must not be dropped as redundant with the axe row**.

### Structure and the a11y floor (the deck's §1–§7; this list may not shrink)

- `<h2>` board heading (one `h1`, the shell's); content capped at 720px; visible focus ring on every control; **focus never dropped to `<body>` when a row repaints under a tapped button**.
- The freshness row: «עודכן 14:07» → «אין עדכון מאז 14:07» (stale) → «מושהה · עודכן 14:07» (paused/idle), the deck's precedence rule at `design.md:289`. **Readable, reachable and NOT `aria-hidden`** — the deck's F-1, accepted into the spec's a11y floor: the literal reading of D11's parenthetical would make the board's only honesty signal sighted-only, so a screen-reader user could never learn the board stopped updating.
- **44×44 minimum on the check-in control AND on the pause control**, which on a phone in a boutique is the whole ergonomic argument.
- Check-in state **never signalled by colour alone**, and no second `Badge` competing with the status chip for meaning in one region (`lib/booking.tsx`'s stated rule). «נרשמה הגעה · 09:24» is words. Paused state likewise carries text, not just an icon.
- `<bdi dir="ltr">` around every numeric run (times, counts); **bare `<bdi>`** around Hebrew free text — customer name, type name, dress name — because `dir="ltr"` on Hebrew is itself a bidi defect.
- **A row does not navigate** (P-2 / Q-2). One row, one action. Deep-linking would make the row a button containing a button — an HTML defect, not a style call — and would give `BookingDetail` a second entry point with a different lifecycle.
- **Undo is always visible** (P-3 / Q-3): the server takes no clock bound on it, so a time-boxed control would be a lie the API contradicts.
- **One chronological list**, `(starts_at, seat_index)` as the server returned it, **no expected/here/done bands** (P-4 / Q-4): checking a bride in would move her row into another band, teleporting the thing you just touched on the one screen whose entire design budget goes on not moving under you.

**The loop lives in this file and is not extracted** (D13). A hook with one caller, no second consumer and no test of its own is an abstraction bought on speculation — and **F57's queue entry already assigns the `usePoll` extraction to itself as the second caller** (`LOOP-STATE.md:88-91`), which is what makes it reviewable then rather than speculative now.

- **Done when**: `make fe-test` + `make fe-build` green; every assertion in the two tables above is a named `it(...)`; axe at zero violations.
- Commit: `feat(manage): the live shift board — 5s poll, check-in and the 2.2.2 pause control`.

## Task 9 — `BookingDetail` states the fact, and the two shipped fixture files
`Frontend/apps/manage/src/components/BookingDetail.tsx`, `…/__tests__/BookingDetail.test.tsx`, `…/__tests__/BookingsSection.test.tsx`

- One `<Fact>` when `checked_in_at !== null`, the **exact three-line `cancelled_at` treatment at `BookingDetail.tsx:365-369`** (`<Fact label={t("booking.checkedInAt")}><Instant value={detail.checked_in_at} /></Fact>`).
- **The check-in control does NOT appear here** (D6). The action lives on the board, one place; the detail states the fact. Any change to the control's placement in F15's detail screen is out of scope.
- `BookingDetail.test.tsx` — the new `Fact` row asserted (present when set, absent when `null`); fixtures gain `checked_in_at`.
- `BookingsSection.test.tsx` — fixtures gain `checked_in_at`. **No assertion changes**: the list row does not render it, and the section is otherwise untouched.
- **Done when**: `make fe-test` + `make fe-build` green with **no assertion edits** in `BookingsSection.test.tsx` beyond the fixture key.
- Commit: `feat(manage): render the arrival timestamp on the booking detail`.

## Task 10 — Gates and the run report
No files.

Run the full verification below, report what ran and what passed, and state **explicitly** that the `db`-marked suites execute only on CI. Carry forward in the run report:

- **Spec Risk 9 — the privacy hand-off, re-nagged.** `checked_in_at` starts collecting a new class of personal data (a named person's physical presence at a place and time) and no privacy notice exists in the product to cover it. **F20 (`spec_gate: user`) must carry an arrival/check-in entry in both the collection notice and the processing-activities record — purpose = floor operations, retention = with the booking (7 years, pre-decided #10).** No build work here.
- **Spec Risk 2 — hand F29 the number rather than let it discover one.** Per tick, per device: **4 sessions, ~9 SQL statements, ~17 round trips, 4 pool checkouts** (the count includes one uncached `tenants.by_slug` in its own session, three `set_config` + BEGIN/COMMIT pairs, and four `pool_pre_ping` `SELECT 1`s). Ten devices on one tenant is ~90 statements/s; 50 tenants × 3 devices is ~270 statements/s. The cheapest lever is already assigned — caching `tenants.by_slug`, which `tenancy/resolver.py:8-9` defers to E5 in its own docstring. D14's idle stop removes the quiet hours.
- **Spec Risk 3 — WCAG 2.0 SC 2.2.1 Timing Adjustable is a Level A item handed to F21, not an ops annoyance.** The 12-hour TTL is **under** 2.2.1's 20-hour exception and is both unextendable and unwarned. F34 cannot close it; it stops the loop and says so honestly.
- **P-8 = 10 minutes** was resolved by this plan (C3), not by the user. One constant, one line to overturn.
- **Deck P-5 was flipped** against the designer's recommendation by the user's Q-5 = NO (C2).

No push, no PR — the orchestrator owns review and shipping.

---

## What a local run cannot prove

No Docker locally, so `pytest -m db` collects and skips.

| Task | Proof that is CI-only | What the local run still gives |
|---|---|---|
| **2** (migration + ORM) | the round trip, the nullable `TIMESTAMPTZ` type, and **the three pinned definitions** (status CHECK + both partial unique indexes) | `ruff` + `mypy app tests` resolving `Booking.checked_in_at` at every new call site |
| **3** (the writers) | **every assertion in the task** — `populate_existing` against a real identity map is not reproducible with a fake | `mypy` over the new signatures and the `CheckInOutcome` enum |
| **6** (the whole concurrency module) | all of it, including both forced interleaves | `mypy` over `tests` |

Everything in Tasks 0, 1, 4, 5 and 7–9 verifies locally. **Task 5 is the milestone**: it is the first point at which the full route table, both new verbs and the changed wire shape are exercised end to end with no Postgres.

⚠ **Two backend test failures are always false locally** — `test_config.py` picks up `Backend/.env` leaking `MEDIA_BUCKET` (`.memory/local-env-breaks-config-tests.md`). CI is green. Do not chase them.

---

## Testing plan → spec criteria

| Spec criterion | Where |
|---|---|
| The migration is one nullable `TIMESTAMPTZ`, up and down | `test_migrations.py` (`db`) |
| The status CHECK and both partial unique indexes are byte-identical **after this feature's migration** | `test_migrations.py` (`db`) — **the test that will still be earning its keep when E4 widens the CHECK** |
| No table snuck in | `test_every_tenant_id_table_has_forced_rls` (`db`, **unedited**) |
| The three-valued outcome off a `.returning()` scalar + `populate_existing` re-read | `test_booking_repositories.py` (`db`) |
| The service branches on the outcome, never on the loaded object | `test_booking_owner_service.py` (fast — fake repository returns an outcome that disagrees with its row) |
| Check-in table: `confirmed` ⇒ written + one audit row; repeat ⇒ 200 + **no** audit row; `cancelled`/`no_show`/`completed` ⇒ 409; no clock bound | `test_booking_owner_service.py` (fast) + `test_booking_owner_api.py` (fast) |
| Undo: clears + audit row with `previous_checked_in_at`; never-checked-in ⇒ 200 no row; **cancelled checked-in ⇒ succeeds** | `test_booking_owner_service.py` (fast) + `test_booking_owner_db.py` (`db`) |
| **The first timestamp survives two taps** | `test_booking_owner_db.py` (`db`, sequential two-clock — `test_booking_comms_db.py:788-812` verbatim) |
| **A cancel in the gap ⇒ 409, nothing written, `checked_in_at` still NULL** | `test_booking_owner_db.py` (`db`, **forced interleave**, repository-level per C7) |
| **A check-in in the gap ⇒ 200 unchanged carrying the FIRST writer's timestamp** | `test_booking_owner_db.py` (`db`, **forced interleave**) — the pair that proves the discrimination is real |
| A status transition never clears `checked_in_at` | `test_booking_owner_db.py` (`db`) — asserted as a decision |
| Both routes wired, authenticated, `no-store`, no `/manage` shadow | `test_booking_owner_api.py` `ROUTES` (fast) |
| `SPEC_ERROR_CODES` **unchanged** and still set-equal | `test_booking_owner_api.py` (fast) |
| Both routes admit owner **and** shift_manager; neither joins `OWNER_ONLY` | `test_staff_role_gating.py:184` + `:324` (fast, **unedited** — live route table walker) |
| `checked_in_at` on the list row and the detail; the two pinned literals updated; `:649-664` untouched | `test_booking_owner_api.py:422-432` + `:502` (fast) |
| RLS isolation — tenant B ⇒ 404, indistinguishable from missing | `test_booking_isolation.py` (`db`) |
| **D4's six mechanisms**, each as its own named assertion, 401 and 403 **separate**, re-arm on success **and** failure | `BoardSection.test.tsx` (vitest, fake timers) |
| **SC 2.2.2** — pause stops, resume fetches immediately, idle stop fires, one tap resumes | `BoardSection.test.tsx` — **the only automated coverage; axe has no rule for it** |
| D11 — the announced region does not change on a tick, does on a check-in and a pause | `BoardSection.test.tsx` |
| Jerusalem date roll refetches; stale-with-rows vs first-fetch outage; truncation line | `BoardSection.test.tsx` |
| Zero axe violations on the board | `BoardSection.test.tsx` (`axe-core`, **already a devDependency**) |
| The arrival timestamp on the detail; fixtures updated | `BookingDetail.test.tsx`, `BookingsSection.test.tsx` |
| Every new formatter is zoned | **nothing new to check** — F34 adds no formatter (D12); `qa-greps.sh` output must be **byte-identical to the baseline** |

**No E2E is promised**, and the reason is F15's verbatim: the console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend and nothing can log in (`e2e/a11y.spec.ts:10-19`). A board e2e needs `/manage/**` route interception that no spec has built. Recorded rather than silently skipped — and it is spec Risk 8: the mode most likely to differ in reality (a genuinely slow response on boutique wifi) is the one fake timers model least faithfully.

---

## What could go wrong in review

Every item here is a **recorded ruling**, not an open question. A reviewer who raises one of these should find the reasoning rather than file a finding.

1. **"The SMC epic says the bookings section is F15's, untouched — but D6 adds `checked_in_at` to its wire shape and a `Fact` to its detail."** (Spec conflict 4, `shift-manager-console.md:34`.) **Read narrowly and deliberately**: "untouched" scopes re-design and re-scoping, **not the byte-level immutability of a shared wire shape**. A new column the console cannot see anywhere would be the stranger choice. The board only ever reads the list, so the field must be on the **row**; and the control does **not** appear on the detail — the action lives on the board, one place, and the detail states the fact. **This is the most likely finding in the review and the ruling is D6.**
2. **"Two shipped test literals were edited."** `test_booking_owner_api.py:502` and `:422-432`. **Deliberate and visible.** That is what a pinned whole-payload literal is *for*: a wire-shape change that broke no literal would mean the literal was not pinning the wire shape. `:649-664` is the slot grid and is untouched; there is no third.
3. **"Why is `CheckInOutcome.ALREADY_CHECKED_IN` returned for a row that is not checked in?"** The undo reads it as "already clear" — spec `:222-223`. Recorded as **C6**, closed with the enum's dual-reading docstring. Renaming would be re-deciding a spec shape.
4. **"The spec says seventh section / landing stays `profile` / `nav` is an array — none of that matches `App.tsx`."** Recorded as **C4**. F51/F52/F17 rewrote the file; D10's *decisions* are intact and only its mechanics were re-pointed. **Q-5 = NO is satisfied by touching `App.tsx:73` not at all.**
5. **"The spec says the deck must be revised before the gate."** Recorded as **C1** — revision 2 landed 2026-07-30 and discharged all three items. Task 1 is only the status flips and the P-resolutions.
6. **"P-8 (10 minutes) was decided by the plan, not the user."** Recorded as **C3**, with the deck's own reasoning and a run-report line. One constant to overturn.
7. **"Every `bookings.py` line number in the spec is wrong."** The file shifted ≈+42 lines. The §"What moved" table has every new location; the *content* the spec cites is all still there, `cancel`'s identity-map docstring included (now `:328-336`).
8. **"F15 declined a limiter on this router; a 5s poll makes that wrong."** (Spec conflict 5.) The conclusion holds and the reasoning is **restated rather than inherited**: a poll makes the traffic real but it does not make an attacker. The caller holds a live session for this tenant, is CSRF-fenced, and can already spend more by holding the tab open than by abusing anything. A budget here would mean a board that stops updating mid-shift because too many staffers were looking at it — a limiter whose only reachable victim is the feature it protects. **What does not survive unchanged is the silence on the client side**, and D4(6)'s backoff is that gap closed.
9. **"`LOOP-STATE.md:411` says F35/F37/F44 ride F34's 5s poll, and this ships no substrate."** (Spec conflict 6.) Inherited when F32 was subsumed and every dep list naming it was rewritten. **D13 ships nothing to ride, and `GET /manage/bookings?date=` structurally cannot carry a bell item or an SOS page.** What those three inherit is D4's six mechanisms as a **documented pattern plus one interval constant — nothing executable**. F57's queue note already assigns the hook extraction to itself as the second caller, which is the intended shape.
10. **"E6's F34 brief lists dispatch, on-shift staff and a queue as IN."** (Spec conflict 1, `e6-instore-realtime.md:77`.) None has data: `staff_users` has no `on_shift` column (`0003_auth.py:34-41`), no queue-ticket table exists, and the only staff rows before F51 were provisioned owners. The SMC epic's user-answered phase table scopes SMC-5 to `checked_in_at` + endpoints + the poll (`shift-manager-console.md:47`). **Codebase-consistent reading taken.** See the scope fence.
11. **"Pre-decided #25 and `architecture.md:12` describe versioned event hints."** (Spec conflict 2.) SMC ruling 3 drops the version; there is no event substrate to version, so the mechanism has no subject. The principle it protects — server is truth, client holds no derived state — is satisfied **more** completely by a permanent full refetch, because there is no gap to miss.
12. **"`checked_in_at` makes wait-time measurable."** (Spec Risk 5.) It does, and **pre-decided #28 forbids measuring it**. The first person to notice will propose a chart. The ruling stands until an epic reopens it.
13. **"The audit rows are write-only."** (Spec Risk 7, F15's Risk 7 unchanged.) F34 adds two more actions nothing renders, and the undo's `previous_checked_in_at` is the only surviving copy of a destroyed arrival time with no way to read it without `psql`. Recorded; F53's activity log is the first read surface.

---

## Verification

```
make lint      # cd Backend && ruff check . && ruff format --check . && mypy app tests
               #   + cd Frontend && pnpm -r lint && pnpm -r typecheck
               #   + bash Frontend/scripts/qa-greps.sh
make test      # cd Backend && pytest -m "not db" -q
make fe-test   # cd Frontend && pnpm -r --if-present test
make fe-build  # cd Frontend && pnpm -r build
make e2e       # cd Frontend && pnpm -r build && playwright install --with-deps chromium && pnpm e2e
```

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`**, `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` **exit 0** printing **exactly the pre-existing baseline**: seven `ok` lines, then `review  date reads` listing `apps/manage/src/components/HoursSection.tsx:15` and `apps/manage/src/components/TermsSection.tsx:9` **and nothing else**. F34 adds no formatter, so **any third line is F34's regression.** (Captured on this tree at 2026-07-31.)
- **`make test`** — all fast tests pass; `test_booking_owner_api.py` and `test_booking_owner_service.py` green; the `db`-marked modules **collected and deselected** with the summary line saying so. `test_staff_role_gating.py`, `test_no_route_is_registered_twice_across_routers` and `test_frontend_constant_parity.py` pass **unedited**. ⚠ Two `test_config.py` failures are the known local `.env` leak — CI is green.
- **`make fe-test`** — `BoardSection.test.tsx` green with every named assertion from Task 8 present and its axe pass at **zero** violations; `BookingDetail.test.tsx` and `BookingsSection.test.tsx` green with fixture-only edits.
- **`make fe-build`** — both apps build; no unused-import or unused-variable TS error.
- **`make e2e`** — the existing storefront and console specs stay green. **F34 adds no e2e spec**, so an unchanged e2e count is the expected result, not a gap.
- **CI additionally**: `make test-db` green, including the migration round trip, the three pinned definitions, both forced interleaves, the sequential two-clock proof and the RLS isolation case. **A first red on a test bug here is budgeted** — check `continue-on-error` before believing it.

---

## Out of scope (unchanged from the spec)

Dispatch and the staff↔client assignment record (D9, E6-proper) · on-shift staff with role badges (D9; no `on_shift` column exists — F57) · queue tickets (F33) · fitting rooms (F36) · SOS (F37) · waitlist (F58) · wait-time analytics and any owner reporting (pre-decided #28 — `checked_in_at − starts_at` becomes computable here and nothing computes it) · a realtime vendor, a version field, an event table, sockets (SMC ruling 3; **F32 stays subsumed and must never be built**) · a read-only kiosk / display mode (pre-decided #27) · walk-in creation from the board (F50/SMC-6) · a board detail view or drag-to-reorder · **any change to the check-in control's placement in F15's detail screen** (D6 — the detail states the fact, the board owns the action) · **a polling abstraction, hook or module for F35/F37/F44** (D13 — F57 extracts it as the second caller) · a he/ar parity guard (Risk 6, inherited) · retrofitting the four hardcoded-Hebrew console sections · **the privacy notice and the processing-activities entry for the arrival record** (F20, `spec_gate: user` — Risk 9) · a warning-and-extend on the 12-hour session TTL (SC 2.2.1, F21 — Risk 3) · a frequency picker for the poll interval (D14: 2.2.2 is satisfied by any *one* of pause/stop/hide/frequency, and one button closes it).
