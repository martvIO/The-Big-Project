# Spec: F57 — Floor roles (reception / sales_assistant / seamstress) + break status + staff cards (Epic E6, floor program iteration 2)

**Created**: 2026-07-31 · **Status**: **Gate 1 self-approved under Interview Q1** — F57 is not on Q1's enumerated exception list (`.planning/epics/interview-2026-07-30.md` §1: *F17, F18, F19, F20, F29, F48* present and wait; everything else self-approves). No payments, no refunds, no privacy-law text, no billing. **DESIGN GATE SELF-APPROVED** — Interview Q2 named exactly two novel interaction patterns for this run, F34's shift board and F42's capacity matrix (`LOOP-STATE.md:1054`); a staff-cards panel assembled from F34's shipped shell is neither, so no prototype and no `design-critic` pass gate this build. · **Effort**: **L** — one migration widening a shipped CHECK plus one nullable column, a new `/manage` domain module with three routes, two repository writers, a new console panel, **and** the `usePoll` extraction that migrates F34's 744-line `BoardSection.tsx` onto shared code in the same PR (D10).
**Design**: a deck was nevertheless authored the same afternoon and it **is binding** — `.planning/design/screens/floor-staff-roles/design.md` (self-approved, §8 `P-1`…`P-8` resolved, §9 `F-1`…`F-11`) and `copy.md` beside it, which is **the canonical key list** (32 invented, 4 reused) and outranks D13's prose table. Four of the deck's §8 decisions bind the panel's layout directly: **P-1** one `Card` containing a divided `<ul>`, one column at every width, never a grid of cards; **P-2** the role is muted words and the card's single `Badge` is the status; **P-4** no hoisting of her own card, marked instead with F51's shipped «זו את» (`he.ts:209`); **P-5** the 🟢/🟡/🔵 brief ships as **words**, never glyphs.
**Depends on**: **F51** (`auth/staff_router.py`'s four owner-only routes, `StaffService`'s advisory-locked last-owner protocol, `StaffUsersRepository`, `StaffSection.tsx`) · **F34** (`BoardSection.tsx` and D4's six poll mechanisms, `App.tsx`'s `SectionKey`/`NAV` shape, the `{401,403}` terminal rule, D11's live-region rule, D14's SC 2.2.2 control) · **F31** (`require_role`, `RoleGate.allowed_roles`, and `test_staff_role_gating.py`'s default-deny walker) · **Feeds**: **F36** (rooms and occupancy EXTEND this feature's `/manage/floor` payload and add `occupied` to the card status — no second poll loop), **F58** (the waitlist panel joins the same payload), **F37** (SOS centre on the same board), **F41/F42** (the third and fourth callers of `usePoll`).

**What F57 does *not* do.** It does **not** rebuild staff CRUD. F51 shipped add / edit / deactivate as PR #25 and its guards — no self-demote, never remove the last live owner, the namespaced per-tenant advisory lock — are untouched. The only thing this feature does to F51's surface is widen its role `<select>` from two options to five, and fix the ternary that widening breaks (D14).

---

## Problem

The brief's floor screen shows staff cards — name, role, live status. Today the product can render none of the three honestly.

- **Role.** `StaffRole` has exactly two members, `OWNER` and `SHIFT_MANAGER` (`Backend/app/models/constants.py:9-14`), pinned in the database by `0011_staff_roles.py:22-25`'s `CHECK (role IN ('owner', 'shift_manager'))`. A boutique whose floor is a receptionist, two sales assistants and a seamstress can only describe them as owners or shift managers — and a shift manager is admitted to every `/manage` route except staff management, the payment gateway and `POST /manage/terms` (`OWNER_ONLY`, `test_staff_role_gating.py:69-79` — nine routes, and terms-publishing is the one a prose summary keeps dropping). Recording a seamstress as a shift manager hands her the boutique's whole booking surface.
- **Status.** `staff_users` is `id, tenant_id, created_at, updated_at, deleted_at, email, password_hash, display_name, role` and nothing else (`0003_auth.py:34-41`, `Backend/app/models/staff_user.py:11-20`). There is no column that says a person stepped away, and F34's spec already recorded the consequence for the adjacent question — "`staff_users` has no `on_shift` column… A board cannot list who is on shift" (`shift-board-checkin.md:276`).
- **A place to show them.** F34 shipped the board (`BoardSection.tsx`, merged as PR #32) and it renders the day's bookings only. Its own Out-of-scope hands the rest of the floor forward.

And the roles have never had a consumer, which is the bar `0011_staff_roles.py:20-21` and `constants.py:10-12` both set in writing: *"reception/seamstress/sales join when E6-proper gives them a consumer (the ScheduledMessageKind rule — no speculative kinds)."* The floor program is that consumer. This feature is the moment those comments described.

**Nothing here is dangerous in the way F34's arrival record was.** The floor payload carries **zero customer data** — names and roles of colleagues, and a timestamp saying one of them is on a break. That is what makes admitting three brand-new roles to one read a small decision rather than a large one. The part of this document that gets argued is the other half: three roles that F31's walker default-denies everywhere must be admitted to exactly two things and to nothing else, forever, and "forever" has to be a test rather than a memory.

## Goal

`StaffRole` widens to five and the database CHECK widens with it. `staff_users` gains `break_started_at TIMESTAMPTZ NULL`. A new `GET /manage/floor` answers the tenant's live staff as cards — name, role, derived status — and admits all five roles. Two sibling routes toggle a break: **owner and shift_manager on anyone; any staffer on herself, and "herself" is read off the session cookie and never off the request.** A `FloorPanel` renders those cards on F34's board for the roles that have a board, and is the whole screen for the roles that do not, on its own 5-second poll.

F57 ships **one migration** (one CHECK swap, one nullable column), **one new router**, **two `AuditAction` members**, **no new error code**, **no new handler**, **no new table**, **no new rate limiter**, and — the one structural thing — **`usePoll`, extracted from `BoardSection.tsx` and adopted by it in the same PR**.

## What already exists to build on (verified against code)

- **The role set is pinned in exactly two places and both are named in this spec.** `StaffRole` (`constants.py:9-14`) and `0011_staff_roles.py:22-25`'s named constraint `staff_users_role_check`. `StaffUser.role` is plain `Text` with a `server_default` of `'owner'` (`models/staff_user.py:18-20`) — no SQLAlchemy `Enum`, so the ORM needs no change when the set grows.
- **`RoleGate` fails closed on any role the enum does not know**, and its `allowed_roles` is introspected by the walker (`auth/dependencies.py:40-62`). Widening `StaffRole` therefore widens **nothing**: every shipped gate names its roles positionally (`require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)`), so a new member is refused by every one of them on the day it is added. That is the property this feature is built on, and it is also the property that makes the two new doors have to be opened deliberately.
- **`RoleGate` composes by INTERSECTION, never by union, and that decides where the floor router lives.** The docstring is explicit — *"Applied router-level as the default posture and per-route to tighten (both gates run…)"* (`auth/dependencies.py:44-45`) — and `_gate_role_sets` yields **every** gate in the dependency tree (`test_staff_role_gating.py:129-136`), which is why `test_route_table_matches_the_permission_matrix` asserts `all(... in roles for roles in role_sets)`. A per-route gate on an existing router can only narrow it. There is no way to widen `booking/owner_router.py`'s `require_role(OWNER, SHIFT_MANAGER)` (`owner_router.py:82`) for one route. (D4.)
- **The seven shipped `/manage` gates, in full**, because D5 has to be route-by-route:

  | Router | File:line | Admits |
  |---|---|---|
  | `auth/router.py` — login / logout / me | — | **ungated by contract** (`test_staff_role_gating.py:105-109`) |
  | `boutique/router.py` — settings, hours, types | `boutique/router.py:33` | owner, shift_manager |
  | `boutique/router.py` — `POST /manage/terms` | `boutique/router.py:215` | owner only |
  | `catalog/router.py` | `catalog/router.py:61` | owner, shift_manager |
  | `booking/owner_router.py` (F15 + F34) | `owner_router.py:82` | owner, shift_manager |
  | `auth/staff_router.py` (F51) | `staff_router.py:63` | owner only |
  | `dashboard/router.py` (F52) | `dashboard/router.py:68` | owner, shift_manager |
  | `payments/router.py` (F17) | `payments/router.py:30` | owner only |

- **`app/dashboard/` is the shape for a small read-only `/manage` domain module**, and its router docstring already argues every decision F57's would otherwise have to re-argue: router-level gate so a later route cannot forget it, tenant from `get_current_tenant(request)` and never from `StaffContext.tenant_id` (`dashboard/router.py:17-26`), a fourth local three-line `_no_store` copy rather than a backwards dependency arrow (`:28-30`), no rate limiter (`:32-36`), real HTTP verbs (`:38-39`).
- **`StaffUsersRepository.list_live` is the floor read, already written.** `deleted_at IS NULL`, `ORDER BY created_at` with the reason stated — *"so the founding owner is first and the console's rows do not shuffle between page loads"* (`db/repositories/staff_users.py:36-44`). A 5-second repaint is precisely the caller that reason was written for. `soft_delete` (`:120-135`) is the guarded-`UPDATE`-plus-`.returning()` shape the break writers copy.
- **`NotAuthorizedError` is not a domain error and is already generic.** *"Lives here (not in a domain module) because every /manage router raises it"*, and `create_app` maps it to one body for every unadmitted role *"so a probe cannot learn which roles exist"* (`auth/dependencies.py:17-21`; body pinned by `test_staff_role_gating.py:377-397`). The break toggle's "not on her" refusal reuses it and adds no code. (D6.)
- **`audit_log.action` is plain `TEXT` with no CHECK** (`0003_auth.py:71-79`), which is why `AuditAction` has grown four times without a migration — F15's seven (`constants.py:113-119`), F34's two (`:127-128`), F51's five (`:135-139`), F17's. F57 is the fifth such block.
- **The identity-map trap is documented three times and F34 shipped the fix.** ORM-enabled `update()` stamps the SET values onto the in-memory instance whatever the database matched, and the session factory is `expire_on_commit=False`, so a trailing `by_id` hands the poisoned object back (`db/repositories/bookings.py:287-295`; `booking/owner.py:325-333`; pinned by `test_booking_owner_db.py:747-760`). F34's answer — `.returning()` scalar for "did I write", plus a `select(...).execution_options(populate_existing=True)` re-read for what to render — is the shape D7 copies.
- **`test_migrations.py` already has the exact test shape for a widened CHECK.** `_ADD_ROLE_CHECK` is 0011's `ALTER` verbatim, deliberately not a paraphrase, and `_DROP_ROLE_CHECK` deliberately drops the `IF EXISTS` so the halves cannot pass vacuously (`test_migrations.py:44-53`); `test_adding_the_role_check_validates_existing_rows` (`:154-189`) runs it on a **populated** table in both directions. `test_staff_role_check_pins_the_role_set` (`:73-93`) probes accept/refuse, and `test_the_app_role_can_promote_to_shift_manager_but_not_to_an_unknown_role` (`:96-151`) proves the CHECK against the **app** role and against `UPDATE`.
- **The walker's unknown-role sentinel already anticipated this feature.** `UNKNOWN_ROLE = "no-such-role"` with a tripwire asserting it never becomes a real `StaffRole`, and a comment saying it is *"Deliberately NOT 'reception' (or seamstress/sales): 0011's comment names those three as the next roles to join StaffRole, and the day one of them does, a test using it as the unknown-role probe would silently start asserting the opposite of its own name"* (`test_staff_role_gating.py:81-91`, mirrored at `test_migrations.py:54-56`). Today is that day. The sentinel survives it untouched; the comment moves to the past tense (D5).
- **`App.tsx` is a **ten**-member `SectionKey` union plus a role-filtered `NAV` array** (`dashboard`, `profile`, `hours`, `types`, `terms`, `catalog`, `bookings`, `board`, `staff`, `gateway` — F52 added `dashboard`, F17 `gateway`, F34 `board`). `SectionKey` at `:18-28`, `const ALL = ["owner", "shift_manager"]` at `:30`, `interface NavItem {key, labelKey, roles}` at `:42-46`, `NAV` at `:48-72`, `reachable`/`activeKey`/`nav` derived at render (`:114-131`), one render branch per key (`:145-154`). The file states twice that the array is **cosmetics** and the server's `RoleGate` is the control (`:32-38`, `:62-65`). `activeKey`'s `reachable[0]?.key ?? section` fallback (`:121-130`) is what lands a role that reaches no NAV row without white-screening — and it is what makes a role that reaches exactly one row land on it.
- **`BoardSection.tsx` holds the loop this feature extracts, and its two review bugs are fixed in the shipped source.** Base/backoff/idle constants at `:12-27`; `schedule()` — "THE ONE ARMING SITE" — at `:108-124`; **the unmount fix at `:250-260`** (`runningRef.current = false` in the mount effect's cleanup, with the comment saying why `clearTick()` alone is not enough); `visibilitychange` immediate-fetch at `:263-281`; idle arming at `:283-296`; pause/resume at `:335-355`; `mutate()` with the re-arm in its `.finally()` at `:363-421`; the focus rescue keyed on `rowError` at `:315-319`. `terminalOf` — the `{401,403}` rule — at `:32-47`.
- **`api.ts` already narrows the role to a union.** `export type StaffRole = "owner" | "shift_manager"` (`api.ts:362`) feeds `StaffMember`, `CreateStaffRequest` and `UpdateStaffRequest` (`:364-406`). `Staff.role` is `string` (`:73`), which is why `App.tsx`'s `roles: readonly string[]` comment exists.
- **`StaffSection.tsx` renders the role in three places and two of them are two-valued.** `roleWord` is a ternary — `role === "owner" ? t("staff.roleOwner") : t("staff.roleShiftManager")` (`:99-100`) — and the two `<select>`s hardcode two `<option>`s each (`:242-243`, `:373-374`). The badge is already safe: `variant={row.role === "owner" ? "success" : "neutral"}` under the comment *"The WORD carries the role; the colour never does"* (`:303-305`).
- **`ar.ts` states the rule this feature inherits** — every value is the approved Hebrew standing in untranslated, never an empty string, because i18next's `returnEmptyString` renders `""` rather than falling back (`i18n/ar.ts:1-21`). `lng` stays `"he"`, no switcher, per the 2026-07-31 languages ruling.
- **`Nav.test.tsx` already asserts the role filter by count** — "shows an owner all ten sections", "shows a shift manager eight sections and neither owner-only one", "does not white-screen on a role the enum does not know", and "is cosmetics only" (`Nav.test.tsx:83-126`). Three new roles are three new cases in a file whose shape already exists.

## Design

### D1 — The role set widens by DROP + ADD on 0011's named CHECK, and the migration proves it on a populated table

`StaffRole` gains three members and the DB constraint gains the same three values:

```python
class StaffRole(StrEnum):
    # The DB pins this exact set (0011, widened by F57's migration). The floor
    # program is the consumer 0011's comment demanded before these three could
    # be added — pre-adding speculative roles is the un-lazy thing (the
    # ScheduledMessageKind rule), and this block is the record that the bar was
    # met rather than waived.
    OWNER = "owner"
    SHIFT_MANAGER = "shift_manager"
    RECEPTION = "reception"
    SALES_ASSISTANT = "sales_assistant"   # supersedes pre-decided #24's 'sales'
    SEAMSTRESS = "seamstress"
```

`'sales_assistant'`, not `'sales'` — the user's 2026-07-31 ruling, recorded here because pre-decided #24 says otherwise and a reader will find it.

The DDL is **DROP then ADD**, not `ALTER CONSTRAINT`: Postgres has no way to change a CHECK's expression in place, and `ADD CONSTRAINT` validates every existing row, which is the property 0011's own comment claims and `test_adding_the_role_check_validates_existing_rows` proves (`test_migrations.py:154-189`). Widening a constraint can only ever *admit* rows that were already legal, so the validation cannot fail on live data — but the test is copied for the widened set anyway, because the claim is only worth what proves it, and because the same test shape is what will catch a typo in one of the three new literals.

**Declined: `NOT VALID` + a later `VALIDATE CONSTRAINT`.** That is the right pattern for a *narrowing* constraint on a large table; here the table is a single-digit staff list per tenant and the constraint is a widening, so the two-step buys a lock-avoidance the table does not need and leaves a window where the constraint means nothing.

**Declined: dropping the CHECK and validating in Python only.** The CHECK is what makes `test_me_echoes_an_out_of_enum_role_verbatim` safe — that test records, in writing, that `GET /manage/auth/me` echoes `staff_users.role` to the browser with **no allowlist**, and that *"What makes that safe is the DATABASE, not this code path"* (`test_staff_role_gating.py:470-482`). Removing the CHECK would silently make that comment false.

**The downgrade re-adds the two-value CHECK and will fail loudly if a row already holds a new role.** That is correct and is stated in the migration: a downgrade that quietly left a `seamstress` row sitting past a two-value constraint would leave the database describing a state its own schema forbids. **Consequence for the test suite, and it is a real trap that reaches across files.** `migrated_db` and `app_role_url` are `scope="session"` (`conftest.py:82`), so one container is shared by every db-marked module, and pytest collects files **alphabetically** — `test_floor_db.py` runs **before** `test_migrations.py`. The rule is therefore about commits, not about file order:

> **No F57 test, in any file, may leave a COMMITTED row holding one of the three new roles.** Roll every such probe back, the `test_staff_role_check_pins_the_role_set` shape (`:78-93`: `trans = await conn.begin()` … `await trans.rollback()`).

Three tests go red on a leftover, and the third is the one a plan-phase reading misses:

1. `test_migration_0011_round_trips` (`:192-220`) downgrades to `"0010"` and back, so it unwinds F57's migration and hits the narrowing re-`ADD CONSTRAINT` first.
2. `test_migration_0014_round_trips` — same statement, same reason.
3. **`test_adding_the_role_check_validates_existing_rows` (`:154-189`)**, which has nothing to do with round-trips. It DROPs the constraint, inserts a probe row and re-adds **0011's two-value `_ADD_ROLE_CHECK` verbatim**; its first assertion is `assert asyncio.run(probe(StaffRole.OWNER.value)) is True`. One committed `reception` row anywhere in `staff_users` makes that ADD fail and flips the assertion to `False` — a red in a file that never mentions F57, on a constraint that has nothing to do with breaks.

And `test_the_app_role_can_promote_to_shift_manager_but_not_to_an_unknown_role` deliberately **leaves a row behind**, reasoning at `:106-110` about which later probes still succeed with it present; that leftover may hold **only** `owner` or `shift_manager` after F57, and the comment says so.

**Where the rule and a test's own needs collide, the seed role is the thing that gives.** `test_floor_db.py`'s forced interleave must commit (exiting `tenant_session` **is** the commit, `db/tenant.py:25`) and its RLS probe needs a second tenant's row on disk. Both seed `owner` / `shift_manager` rows instead: break toggling is role-independent at the repository layer, and RLS isolation is about `tenant_id`, not about `role`. Nothing there needs a floor-role row, so nothing there needs rolling back.

### D2 — `staff_users.break_started_at TIMESTAMPTZ NULL` is the break model

One nullable timestamp on the row that already exists. `NULL` means not on a break and is the only sentinel; a non-null value is both the fact and the "since when".

**Declined: a `status TEXT` column with its own CHECK** (`available | break | occupied`). It is the shape that looks like the card, which is exactly what makes it wrong. The card's status is **derived** (D9) and one of its three values — `occupied` — is owned by another table entirely: F36's `fitting_room_assignments`, whose partial unique index `(tenant_id, staff_user_id) WHERE released_at IS NULL AND deleted_at IS NULL` is *what makes "occupied" a fact rather than a guess* (`LOOP-STATE.md`, F36's note). A status column would oblige F36 to write into `staff_users` on every claim and every release, in the same transaction as the assignment insert, and to keep the two in step forever — a second copy of a fact an index already holds, and a write that races the very concurrency F36 exists to make impossible. Same argument as F34's D1: orthogonal facts in one enum is the shape that forces the impossible-tuple conversation later.

**Declined: a `staff_breaks` table** (`staff_user_id, started_at, ended_at`). It would buy break *history*, which nothing in the brief, the epic or the queue asks for, and it would cost a tenant table: an RLS policy, `enable_tenant_rls`, grants, an entry in `test_every_tenant_id_table_has_forced_rls` (`test_tenant_isolation.py:203`), its own `test_*_isolation.py` suite by the house rule, and an F20 retention row. One nullable timestamp needs none of that. The upgrade path is recorded and is cheap: the two audit rows D8 writes already carry the start and end times, so a history table can be back-filled from `audit_log` the day anybody wants one.

**Declined: `break_ended_at` beside it.** Two columns to express one boolean, with a third state (`started_at` set, `ended_at` set) that means the same as `NULL` and has to be excluded from every predicate. Ending a break clears the column; the value it destroys goes into the audit row (D8), which is F34's D8 argument for `previous_checked_in_at` verbatim.

**No index on `break_started_at`.** Nothing filters or sorts on it — `list_live` already returns the tenant's whole staff list and the derivation reads the column off rows it has in hand. A partial index would serve no reader and cost every write. (F34's D1, same sentence, same reason.)

### D3 — One migration, revision id resolved at build time, and what it must prove it did not do

**`alembic heads` reads `0014 (head)` as this spec is written, so the migration is almost certainly `0015` revising `0014` — and this sentence is not the source.** Re-read `alembic heads` at build time and revise whatever HEAD then is. F34's D2 made this rule after the naive reading went stale before the build started, and its shipped note records that it paid off exactly as predicted (0012 and 0013 landed in the window). Every assertion below keys to *"after this feature's migration"*, never to a revision number.

```python
"""floor roles + break status

Revision ID: <next after `alembic heads` at build time>
Revises:     <whatever HEAD is then — NOT hardcoded 0014>
"""

_ROLES = "'owner', 'shift_manager', 'reception', 'sales_assistant', 'seamstress'"

def upgrade() -> None:
    # DROP + ADD: a CHECK's expression cannot be altered in place. ADD CONSTRAINT
    # validates existing rows, and a WIDENING can only admit rows that were
    # already legal — so this cannot fail on live data. Proven on a populated
    # table by test_migrations.py, the shape 0011's own claim is proven with.
    op.execute("ALTER TABLE staff_users DROP CONSTRAINT staff_users_role_check")
    op.execute(f"ALTER TABLE staff_users ADD CONSTRAINT staff_users_role_check "
               f"CHECK (role IN ({_ROLES}))")
    # When this staffer stepped away. NULL = not on a break, and it is the only
    # sentinel. NOT a status column (spec D2): 'occupied' is F36's index, not a
    # value anything here may write.
    op.execute("ALTER TABLE staff_users ADD COLUMN break_started_at TIMESTAMPTZ")

def downgrade() -> None:
    op.execute("ALTER TABLE staff_users DROP COLUMN IF EXISTS break_started_at")
    op.execute("ALTER TABLE staff_users DROP CONSTRAINT IF EXISTS staff_users_role_check")
    # Deliberately NOT `IF EXISTS`-shaped and deliberately able to fail: a row
    # holding one of the three new roles must block the narrowing rather than be
    # left sitting past a constraint its own value violates.
    op.execute("ALTER TABLE staff_users ADD CONSTRAINT staff_users_role_check "
               "CHECK (role IN ('owner', 'shift_manager'))")
```

Deliberately absent, each for a verified reason:

- **No `GRANT`.** `0003_auth.py:83-84` issued table-level `GRANT SELECT, INSERT, UPDATE, DELETE ON staff_users TO app_user`; table grants are column-agnostic and no column-level grant was ever issued on this table. (The `.claude/CLAUDE.md` `ALTER DEFAULT PRIVILEGES` gotcha is about newly *created* tables, not added columns.)
- **No `enable_tenant_rls`.** RLS is a table property, already forced on `staff_users` since 0003; F57 adds no table, so `test_every_tenant_id_table_has_forced_rls` stays green untouched.
- **No `_updated_at_trigger`.** It exists from 0003.
- **No index, no default, no NOT NULL.**

**The ORM model is the second half of this migration and is not optional.** `models/staff_user.py` declares every column explicitly and no model↔migration parity test exists anywhere in `Backend/tests/`, so without

```python
break_started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
```

every backend line D7 and D9 specify is an `AttributeError`. Migration + model are one atomic change, the `0008_bookings.py` / `models/booking.py` pattern F34's D2 already followed.

**What the migration must prove it did not do.** A db-marked test reads `pg_get_constraintdef` for `staff_users_role_check` **after this feature's migration** and pins it byte-identical. **Capture that literal by running it, do not transcribe it** — Postgres deparses `IN (...)` to `= ANY (ARRAY[...])` and F34's shipped note records that transcribing such literals from the migration source *"would have pinned nothing and reddened CI"*. That test is the thing that will still earn its keep when F36 or a later feature reaches for this constraint again.

### D4 — `GET /manage/floor` is a new `app/floor/` module, because `RoleGate` composes by intersection

New package `Backend/app/floor/` with `router.py`, `schemas.py`, `service.py` — the `app/dashboard/` shape F52 established, registered as the **seventh** `/manage` router in `create_app()` with the same include-order shadowing warning the other six carry, and a `ROUTES` table in `tests/test_floor_api.py` to keep it honest.

```python
router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(*StaffRole)),   # all five, explicitly — see below
    ],
)
```

**Why not hang it off an existing router — and this is structural, not stylistic.** `RoleGate` narrows and never widens: both the router gate and any per-route gate run, and `_gate_role_sets` walks the whole dependency tree (`auth/dependencies.py:44-45`; `test_staff_role_gating.py:129-136`). So a `@router.get("/floor", dependencies=[Depends(require_role(*StaffRole))])` on `booking/owner_router.py` would still be refused for a seamstress by the router-level `require_role(OWNER, SHIFT_MANAGER)` at `owner_router.py:82`. There is no per-route widening in this codebase. The alternatives were: relax `owner_router.py`'s router gate to all five and re-tighten all twelve of its routes (twelve new gates to protect one new route, and the first mistake gives a seamstress the day's customer list), or put the floor read on `auth/staff_router.py`, whose gate is `require_role(StaffRole.OWNER)` and whose docstring says *"Owner-only at ROUTER level, not per route… a route added here later cannot forget the gate"* (`staff_router.py:9-14`) — adding a five-role route there deletes that sentence. A new module is the smallest change and the only one where the gate reads as what it is.

**`require_role(*StaffRole)` spelled from the enum, not as five literals.** The set this router admits *is* "every role the product has", and the day F36 or a later feature adds a sixth, the floor read is where it should be admitted by default rather than by an edit somebody has to remember. `test_gates_admit_only_known_roles` (`test_staff_role_gating.py:165-181`) keeps the expansion honest, and D5's new walker assertion is what stops this from becoming a hole — it pins the three floor roles **out** of every other route, so a gate spelled `*StaffRole` anywhere else fails.

**No rate limiter**, for the one leg `dashboard/router.py:32-36` gives: no `/manage` router carries one and F57 does not introduce the first. CSRF fencing applies to the two POSTs by default (`csrf.py:48` gates on `request.method in MUTATING_METHODS`) and not to the GET; the protection on the read is the session cookie and the role gate, alone.

**Tenant from `get_current_tenant(request)`**, never `StaffContext.tenant_id` — `dashboard/router.py:17-26` argues this at length and F57 is the second route with a session already in hand for other reasons, which is exactly where an implementer reaches for the wrong one.

### D5 — Route by route: the three new roles reach exactly six routes, and a walker assertion pins it

`allowed_roles` for every `/manage` route after this feature, in full. **Nothing in the "owner, shift_manager" rows changes** — F31's default-deny means the three new roles are refused there with no edit at all, which is the whole point of the gate and is why this table is a statement of *what stays true*:

| Method | Path | `allowed_roles` after F57 | Change |
|---|---|---|---|
| `POST` | `/manage/auth/login` | — **ungated by contract** | none — anonymous by definition (`test_staff_role_gating.py:95`) |
| `POST` | `/manage/auth/logout` | — **ungated by contract** | none — anonymous too, deliberately (`:96-100`) |
| `GET` | `/manage/auth/me` | — **ungated by contract** | none — any authenticated staff (`:101-103`) |
| `GET`/`PUT` | `/manage/settings`, `/manage/hours`, `/manage/appointment-types*` | owner, shift_manager | none |
| `POST` | `/manage/terms` | owner | none |
| all | `/manage/dresses*`, `/manage/media*` (catalog) | owner, shift_manager | none |
| all | `/manage/bookings*` (F15 + F34, incl. `/check-in`) | owner, shift_manager | none |
| all | `/manage/staff*` (F51) | owner | none |
| `GET` | `/manage/dashboard` (F52) | owner, shift_manager | none |
| all | `/manage/gateway*` (F17) | owner | none |
| **`GET`** | **`/manage/floor`** | **all five** | **NEW** |
| **`POST`** | **`/manage/floor/staff/{staff_id}/break/start`** | **all five** | **NEW** |
| **`POST`** | **`/manage/floor/staff/{staff_id}/break/end`** | **all five** | **NEW** |

**The three ungated auth routes are doors too, and they are load-bearing.** A reception user must reach `POST /manage/auth/login` and `GET /manage/auth/me` or she cannot sign in at all — `App.tsx:85-91` bootstraps on `api.me()` and renders `<LoginForm/>` when it fails. They are in `UNGATED_ALLOWLIST` with reasons already written (`test_staff_role_gating.py:93-109`), and F57 changes neither the allowlist nor the routes. Stated because "exactly two doors" is the queue note's phrasing and it is two *new* doors, not two reachable routes — a reader auditing this feature must not be surprised to find a seamstress reaching `/manage/auth/me`.

**The new walker assertion.** `test_route_table_matches_the_permission_matrix` (`:184-212`) is about `shift_manager` only and the floor routes pass it unchanged (they admit her and are not in `OWNER_ONLY`). The three new roles need their own structural pin, derived from the **live route table** so it covers routes that do not exist yet:

```python
FLOOR_ROLES = frozenset({
    StaffRole.RECEPTION.value,
    StaffRole.SALES_ASSISTANT.value,
    StaffRole.SEAMSTRESS.value,
})

# The ONLY /manage routes the floor roles may reach. UNGATED_ALLOWLIST's three
# auth routes are reachable by every authenticated staffer by contract and are
# not gated, so they are the walker's business and not this test's.
FLOOR_OPEN = {
    ("GET", "/manage/floor"),
    ("POST", "/manage/floor/staff/{staff_id}/break/start"),
    ("POST", "/manage/floor/staff/{staff_id}/break/end"),
}

def test_the_floor_roles_reach_exactly_the_floor_routes() -> None:
    """F31's gate default-denies the three floor roles everywhere; F57 admits
    them to the floor read and their own break toggle and to NOTHING else.
    Derived from the live route table, so a future /manage route that admits a
    floor role fails here on the day it is written — including one spelled
    require_role(*StaffRole), which is legal on the floor router and nowhere
    else."""
    admits_floor: list[tuple[str, str]] = []
    missing: set[tuple[str, str]] = set(FLOOR_OPEN)
    for route in _leaf_routes(create_app(resolver=_null_resolver)):
        ...  # same walk as test_route_table_matches_the_permission_matrix
        role_sets = list(_gate_role_sets(dependant))
        # RoleGate composes by INTERSECTION — every gate in the tree runs, so
        # the set a route actually admits is the intersection of its gates, and
        # "this route admits a floor role" is a property of that intersection,
        # NOT of any single gate. `any(...)` would report a route that is on the
        # floor router and TIGHTENED per-route — exactly what F36 and F58 will
        # add — as admitting the floor roles when the intersection denies them,
        # and this test would red-fail on a correct route. An EMPTY role_sets
        # (an ungated route) counts as not-admitting, so assertion 1 below is
        # what catches a floor route that lost its gate.
        effective = frozenset.intersection(*role_sets) if role_sets else frozenset()
        for method in route.methods:
            if effective & FLOOR_ROLES:
                admits_floor.append((method, path))
            if (method, path) in FLOOR_OPEN:
                missing.discard((method, path))
                assert FLOOR_ROLES <= effective, (method, path)
    assert set(admits_floor) == FLOOR_OPEN, f"floor roles reach: {sorted(admits_floor)}"
    assert not missing, f"FLOOR_OPEN names routes that no longer exist: {sorted(missing)}"
```

**Three** assertions, each failing on a different mistake — and an earlier draft of this paragraph said "four" while listing three, because it double-counted the lost-gate case. That case belongs to assertion 1, and it cannot belong to assertion 2: `all(FLOOR_ROLES <= roles for roles in role_sets)` over an **empty** `role_sets` is vacuously `True`.

| Assertion | Fails when |
|---|---|
| `set(admits_floor) == FLOOR_OPEN` | a floor role is admitted **anywhere else** — and also when a floor route **lost its gate**, because an ungated route has an empty `effective` and drops out of `admits_floor` |
| `FLOOR_ROLES <= effective` | a floor route admits only **some** of the three |
| `assert not missing` | `FLOOR_OPEN` names a path that no longer exists (the anti-vacuity half) |

The `missing` half is what keeps this test from passing vacuously the day somebody renames a path, which is the failure mode `UNGATED_ALLOWLIST`'s own `seen >= UNGATED_ALLOWLIST` assertion exists to catch (`:161`). **The intersection classifier is the load-bearing detail** — a subsequent reviewer facing a red on F36's first narrowed floor route must fix the route, never relax the quantifier, and `any(...)` is precisely the relaxation Risk 1 exists to prevent.

**Two shipped walks gain the floor routes**, so the gate is proven over HTTP and not only structurally: `test_shift_manager_is_admitted_everywhere_except_terms_publishing` and `test_unknown_role_is_403_on_every_gated_route` both iterate `[*ROUTES, *CATALOG_ROUTES, *GATEWAY_ROUTES]` (`:340`, `:371`) and gain `*FLOOR_ROUTES` from `test_floor_api.py`. The second is the important one: it proves the floor router's gate actually **raises** rather than merely carrying an `allowed_roles` attribute — the decoy-gate failure that comment already describes (`:362-367`).

**And the fake is wired ASYMMETRICALLY, which is the half an earlier draft of this section left out.** `_client` (`:292-321`) wires fakes selectively on purpose: `boutique_service` always, `catalog` **only when a test needs a 2xx**, and the comment at `:311-315` says why — `test_unknown_role_is_403_on_every_gated_route` *"depends on the real (ambient-env) service never being reached, so a decoy gate that carries `allowed_roles` without raising blows that test up instead of quietly passing"*. Wiring a floor fake unconditionally would silently delete exactly that proof for the floor router — the one router in the codebase whose gate is spelled `*StaffRole`, i.e. the one where a decoy gate is most consequential. So `_client` gains `floor: FakeFloorService | None = None`, set on `app.state.floor_service` **only when passed**; the shift-manager walk passes one and **the unknown-role walk deliberately does not**, carrying a comment saying so in the catalog's own words.

**Two tables, two spellings, and mixing them is a CI round trip.** `test_staff_role_gating.py:46-49` is explicit that the structural walkers read `route.path`, so their tables must be route templates and never a literal uuid; the HTTP walks issue real requests and need concrete URLs. F57's break routes carry `{staff_id}`, so both spellings exist:

| Table | Lives in | Spelling |
|---|---|---|
| `FLOOR_OPEN` (this section's walker assertion) | `test_staff_role_gating.py` | `("POST", "/manage/floor/staff/{staff_id}/break/start")` — **template** |
| `FLOOR_ROUTES` (wiring + the two HTTP walks) | `test_floor_api.py`, imported by the gating module | `("POST", f"/manage/floor/staff/{STAFF_ID}/break/start", None)` — **concrete** |

A concretely-spelled `FLOOR_OPEN` fails on the `missing` assertion rather than passing silently — so the mistake is caught, but catching it on CI costs a round trip.

**The unknown-role sentinel's comment moves to the past tense.** `test_staff_role_gating.py:81-91` and `test_migrations.py:54-56` both explain that `"no-such-role"` was chosen *because* reception/seamstress/sales were the next roles to join. They did. The `assert UNKNOWN_ROLE not in {role.value for role in StaffRole}` tripwire (`:88-91`) needs no change and stays green — the comment is edited to record that the anticipated day arrived and the sentinel held. A one-line edit that a reviewer would otherwise flag as a stale comment.

### D6 — The break toggle has two authorization axes, and the actor's identity comes from the session only

The rule: **owner and shift_manager may toggle anyone's break; any staffer may toggle her own.** Both routes carry the target's id in the path — `/manage/floor/staff/{staff_id}/break/start` — and the service's first statement is:

```python
# The acting identity is StaffContext, resolved from the session cookie by
# get_current_staff. It is NEVER read from the path, the query or a body: the
# request names only WHOM to toggle, never WHO is asking. A body-supplied
# "staff_user_id" doubling as the caller's identity is the one shape that turns
# "any staffer on herself" into "any staffer on anyone".
if staff_id != actor.id and actor.role not in _ELEVATED:
    raise NotAuthorizedError
```

where `_ELEVATED = {StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value}`.

Three properties of that placement, each deliberate:

1. **The comparison's left operand comes from the request and the right operand comes from the session.** The request is only ever a *target*. There is no code path in which the caller's identity is taken from anything the caller wrote.
2. **It runs before any read of the target**, so the 403 cannot be an existence oracle: a seamstress probing `/manage/floor/staff/<random-uuid>/break/start` gets the same generic body whether or not that row exists, whether or not it is soft-deleted, and whether or not it belongs to another tenant. `NotAuthorizedError` is already the generic one-body-for-every-unadmitted-role error (`auth/dependencies.py:17-21`) and needs no new code, no new handler and no new `SPEC_ERROR_CODES` member.
3. **It compares ids, not emails or names.** `StaffContext.id` is the primary key `resolve_session` returned.

**Declined: a self-only route plus an elevated route** (`POST /manage/floor/break/start` for herself, `POST /manage/floor/staff/{id}/break/start` for others). Four routes instead of two, two more rows in the walker's `FLOOR_OPEN`, and the self route would still have to answer the same question the moment F36's room cards want a "put her on a break" control — while the id comparison above is one line that already answers both.

**Declined: `require_role(OWNER, SHIFT_MANAGER)` on the routes with a separate self-service route.** Same shape, same cost, and it moves an authorization rule out of one readable line and into the route table where it is invisible to the person reading the service.

**Declined: deriving "elevated" from anything but the role.** No "is this person the target's manager" notion exists in the schema and none is invented here.

**A deactivated target is a 404, not a 403.** `StaffUsersRepository.by_id` filters `deleted_at IS NULL` (`db/repositories/staff_users.py:26-34`); an elevated caller toggling a deactivated colleague gets `DomainNotFoundError` → 404 `NOT_FOUND`, the handler F34 rode unchanged (`main.py:757-759` — **not** `:463-465`, which an earlier draft of this document cited twice and which is a different handler). A non-elevated caller never reaches the read at all, by (2).

**Cross-tenant is the same 404, indistinguishable from missing**, because RLS makes another tenant's row invisible to the read. The floor db test asserts it (Testing).

### D7 — Two verbs, idempotent by predicate, and the outcome is read off the database

```
POST /manage/floor/staff/{staff_id}/break/start   -> StaffCard
POST /manage/floor/staff/{staff_id}/break/end     -> StaffCard
```

Both answer the **full card**, so the panel patches its card from the server's own row and cannot disagree with itself — F34's D4.4 contract (`BoardSection.tsx:377-384`), and the reason the panel is not optimistic.

**Declined: one route with a `{"on_break": bool}` body.** Two guards, two audit actions, two `details` shapes and two idempotency predicates collapsed into a body of `if`s — F34's D5 argument against the same collapse, and F15's D7 against a single `PATCH` carrying `status`.

**Idempotent by predicate**, the `confirm_attendance` / `check_in` shape:

```python
async def start_break(self, session, tenant_id, staff_id, *, at) -> tuple[bool, StaffUser | None]:
    #   UPDATE staff_users SET break_started_at = :at
    #     WHERE tenant_id AND id AND break_started_at IS NULL AND deleted_at IS NULL
    #     RETURNING id
    #   -> the scalar is the ONLY honest "did I write?" (cancel's rule,
    #      db/repositories/bookings.py:287-295)
    #   then ONE re-read:
    #     select(StaffUser).where(tenant_id, id, deleted_at IS NULL)
    #       .execution_options(populate_existing=True)
    #   -> overwrites the identity-mapped instance from the row the DB actually
    #      holds, undoing `evaluate` synchronization's stamp. Correct branch AND
    #      correct render, one statement.

async def end_break(self, session, tenant_id, staff_id) -> tuple[bool, StaffUser | None]:
    #   ... WHERE break_started_at IS NOT NULL AND deleted_at IS NULL RETURNING id, same re-read.
```

**A `(bool, StaffUser | None)` tuple rather than F34's four-member `CheckInOutcome`, and the difference is real rather than laziness.** F34 needed a three-valued enum because zero rows there had two *opposite* causes — already checked in (200) versus no longer `confirmed` (409) — and a boolean could not tell them apart. A break has **no status guard**: zero rows with a live row back means "the target state already holds", full stop, and zero rows with `None` back means the row is gone. `(wrote, row)` is total over that:

| `wrote` | `row` | Answer |
|---|---|---|
| `True` | the row | **200**, card rendered from it, **one audit row** |
| `False` | the row | **200 unchanged**, card rendered from it, **no audit row** — the first toggler's `break_started_at` survives |
| `False` | `None` | **404** `NOT_FOUND` |

If a later feature ever gives the break a status guard, that is the day the enum earns its keep; today it would be a four-member enum with one unreachable member.

**The `populate_existing=True` re-read is not optional and is not a judgement call per call site.** `update(StaffUser)` is ORM-enabled DML whose default synchronization stamps the SET value onto any identity-mapped instance *whatever the database matched*, and the factory is `expire_on_commit=False` — pinned by `test_booking_owner_db.py:747-760` with a docstring that is verbatim this bug. Whether a given call site happens to have loaded the row first is exactly the reasoning that has bitten this repo three times; the flag costs one chained method and removes the question.

**Concurrency, stated because two staffers can tap one card.** Two simultaneous `break/start` on the same person: the predicate matches once, the loser writes nothing and **keeps the winner's timestamp**, and both callers get 200 with the same card. `break/start` racing `break/end` on the same person resolves to whichever committed first, and the loser's re-read renders the database's answer rather than its own. **No advisory lock.** F51's namespaced lock exists because the last-owner invariant is *"at least one"*, which no index can express (`LOOP-STATE.md`, F51's note (1)); a break touches one column on one row and has no cross-row invariant to serialise. Adding it would serialise every break in the boutique against every staff edit.

**No clock bound in either direction**, and no maximum break length. A break that outlives the shift is a fact with a timestamp, not a lie, and the remedy for a forgotten toggle is the other toggle — the `/confirm` precedent F34's D5 already took (`owner.py:253-259`).

### D8 — Two `AuditAction` members, no migration, and the end carries the value it destroys

| Member | Value | Written by | `details` |
|---|---|---|---|
| `STAFF_BREAK_STARTED` | `staff_break_started` | a start that actually wrote | `{"target": "<uuid>", "break_started_at": "…Z"}` |
| `STAFF_BREAK_ENDED` | `staff_break_ended` | an end that actually cleared | `{"target": "<uuid>", "previous_break_started_at": "…Z"}` |

No migration — `audit_log.action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`), the fifth block to rely on that fact. `actor_id = actor.id`, `entity = str(staff_id)`, written in the same transaction before commit (F15's D2 shape). **A no-op writes no audit row** (D7's middle row): the second toggler changed nothing, and `{on_break → on_break}` noise in the only trail this area has would be worse than silence — F34's D8 rule.

`previous_break_started_at` is the load-bearing one: ending a break destroys the only copy of when it began and there is no history table (D2). That is F34's `previous_checked_in_at` argument and F15's `old_customer_id` argument, same shape.

**A row is written even when a staffer toggles her own break.** The asymmetric rule — audit only when `actor.id != staff_id` — was considered and declined: it makes "who put Dana on a break" unanswerable exactly when the answer is Dana, it is a condition a future reader of the table has to know about to interpret it, and the volume it saves is single-digit staff × a few breaks a day. The trail is still write-only in v1 (F15's Risk 7, inherited unchanged).

### D9 — The card's status is derived, and `occupied` is not on the wire until F36

One function, one place:

```python
def _status(row: StaffUser) -> StaffCardStatus:
    # 'occupied' is NOT here and is not in StaffCardStatus. It is F36's:
    # occupancy is an active row in fitting_room_assignments, a table that does
    # not exist, and its partial unique index on (tenant_id, staff_user_id) is
    # what will make it a fact rather than a guess. F36 widens this function and
    # the enum together, in the PR that gives 'occupied' a writer.
    return StaffCardStatus.BREAK if row.break_started_at is not None else StaffCardStatus.AVAILABLE
```

`StaffCardStatus` is `available | break` and **nothing else**. A fast test asserts the wire literal set by **set equality**, so an implementation that emits a third value fails.

**Declined: shipping `"occupied"` now as an unreachable literal.** It is the exact thing `constants.py` refuses in four separate comments — `ScheduledMessageKind`'s *"pre-adding speculative kinds is exactly the un-lazy thing"* (`:64-69`), `StaffRole`'s own pre-F57 comment (`:10-12`), `GatewayCredentialStatus`'s *"there is deliberately no 'unvalidated'"* (`:81-88`) — and `PaymentStatus`'s recorded departure from that rule is written up as a **risk** rather than a precedent (`:90-95`). Shipping it would also buy nothing: F36 must add the Hebrew copy, the client union member and the card's room label in its own PR regardless, so the only thing pre-adding saves is a one-line enum edit, and the only thing it costs is a value that renders as nothing for however long F36 takes.

**This is what "structurally impossible until F36" means, precisely.** Not "no code path currently returns it" — the derivation is a **total function of one nullable column**, its output type has two inhabitants, and the set-equality test pins both. There is no input, real or forged, from which `occupied` can be produced.

**`break_started_at` is on the wire** (null unless on a break) because the panel renders «בהפסקה מ־14:20» — a status that says only "on a break" cannot tell a shift manager whether it started two minutes or two hours ago, and the timestamp is the whole difference between a status and a decision. It is also what keeps the status off colour alone (D12).

**The card carries no email.** `StaffMember` (F51's owner-only wire shape) carries it; the floor card is read by five roles and needs a name, a role and a status. Narrowed deliberately.

### D10 — `usePoll` is extracted here, it carries F34's unmount fix, and `BoardSection` is migrated onto it in the same PR

F34's D13 declined the extraction with a stated reopening condition: *"A hook with one caller, no second consumer and no test of its own is an abstraction bought on speculation… the day there is a second caller the extraction is mechanical and reviewed"* (`shift-board-checkin.md:517`). **F57 is that second caller**, and the queue note claims the extraction. It lands in `Frontend/apps/manage/src/lib/usePoll.ts` — `lib/` for the reason `lib/booking.tsx`'s header already gives, that a shared helper hung off either end of an import chain closes it into a cycle.

**Contract, and every member has a named caller:**

```ts
export const POLL_INTERVAL_MS = 5_000;      // F34's P-1 / Q-1 constant, now shared
export const MAX_BACKOFF_MS   = 60_000;     // D4(6)'s cap
export const IDLE_STOP_MS     = 600_000;    // D14's ten minutes

export type PollMode = "running" | "paused" | "idle";
export type PollTerminal = "session" | "access";

export interface Poll {
  mode: PollMode;                    // render the pause/resume control and its copy
  terminal: PollTerminal | null;     // render the session-or-permission-ended panel
  bump(): void;                      // invalidate whatever is in the air (the date roll)
  refresh(): void;                   // user intent: bump + fetch now (the retry control)
  pause(): void;                      // SC 2.2.2
  resume(): void;                     // SC 2.2.2 — resumes at the BASE interval, not the backoff
  fail(error: unknown): boolean;      // classify a MUTATION's error; true if it was terminal
}

// A tick's outcome, returned by `run`. `undefined` (a plain `Promise<void>`)
// means "clean": reset the backoff to the base and re-arm there.
export type TickOutcome = void | "held" | "suppressed";

export function usePoll(opts: {
  run: (isCurrent: () => boolean) => Promise<TickOutcome>;   // may throw; the hook classifies
  onFailure: (error: unknown, isCurrent: () => boolean) => void;  // non-terminal only
}): Poll;
```

**`TickOutcome` is three-valued because the shipped loop has three outcomes, and this is a correction to an earlier draft of this document that claimed otherwise.** That draft said the pointer hold and the mutation guard move into the caller's `run` with *"byte-identical behaviour, zero API"*. Read against the shipped source, both halves of that claim are false:

| Caller's early return | `BoardSection.tsx` as shipped | What a two-valued `run` would do instead |
|---|---|---|
| pointer hold | `schedule(backoffRef.current)` (`:228-232`) — re-arms at the **current, possibly backed-off** gap and does **not** reset the backoff | a clean tick resets the interval to the base, so a held tick during a backoff would fetch at 5 s instead of the backed-off gap |
| mutation in flight | `return` with **no** `schedule()` call (`:219-222`); the single re-arm is `mutate()`'s `.finally()` (`:411-420`) | a clean tick re-arms, so timers get armed **during** a mutation — which the shipped design explicitly avoids |

So `run` returns `"held"` (re-arm at the current gap, do not touch the backoff) or `"suppressed"` (do not re-arm at all; the caller owns the next arming). Two members on a union type is a smaller surface than the `runExclusive`-plus-hold API this deliberately still avoids, and it is the surface both callers actually need — `FloorPanel`'s hold and its own `mutationsRef` are the same two shapes.

**Neither divergence is covered by `BoardSection.test.tsx` as it stands**, which is why the zero-edit gate alone could have gone green over a changed loop. `usePoll.test.tsx` therefore carries two named tests that pin them: *a `"held"` tick during a backoff re-arms at the backed-off gap, not the base one*, and *a `"suppressed"` tick arms no timer at all*.

What the hook owns, i.e. the six mechanisms neither caller may re-derive: the **single arming site** (`schedule-after-settle`, so at most one request in flight per tab by construction); the `document.hidden` gate plus the `visibilitychange` **immediate** refetch; the failure backoff 5s → 60s cap with reset on the first success; the `{401, 403}` terminal classification; the idle stop; and the monotonic generation behind `isCurrent`.

**The unmount fix is the hook's cleanup and it is the reason the hook is worth extracting.** F34's review found that the loop survived unmount — cleanup cancelled the armed timer, but the arming sites are the request's `.finally()`, which runs *after* cleanup when a request was in flight, and nothing in the cycle touched React state so unmount could not break it: one orphan 5-second request loop per nav-away, for the rest of a twelve-hour session. The fixed source is `BoardSection.tsx:250-260` and it is one line — `runningRef.current = false` **before** `clearTick()` in the mount effect's cleanup. **That line moves into `usePoll`'s cleanup verbatim, with its comment**, and gains a named test of its own: *a request unresolved at unmount arms nothing* (advance several intervals after unmount, assert the call count did not grow). Two callers today and four by F42; the alternative is that line being copy-pasted four times by four different builders.

**What the hook deliberately does NOT own**, because both would be surface with one caller:

- **The pointer-hold suppression.** F34 suppresses exactly one tick on `pointerdown` so a repaint cannot slide a control out from under a travelling finger (`BoardSection.tsx:223-232, 476-484`). Under the hook this is four lines at the top of the caller's own `run` — check the ref, clear it, `return "held"` — and the hook re-arms at the current gap. The **policy** stays in the caller; only the arming is the hook's.
- **A `runExclusive` mutation wrapper.** F34's `mutate()` cancels the armed tick, bumps the generation and re-arms in its `.finally()` (`:363-421`). Under the hook the caller keeps its own `mutationsRef`, `run` returns `"suppressed"` while it is non-zero, and `bump()` discards the poll in the air — same observable behaviour (zero requests issued during a mutation, **no timer armed** during one, a tick re-armed by the `.finally()` after a **failed** mutation as well as a successful one) with two union members instead of a three-member wrapper API. `fail(error)` is what the mutation's `catch` needs and is all it needs.
- Anything board-shaped: the date roll, `applyRows`' focus rescue, the stranded-row repair, the divider scroll.

**`BoardSection.tsx` is migrated onto the hook in the same PR, and the acceptance rule is mechanical: `apps/manage/src/__tests__/BoardSection.test.tsx` must pass with ZERO edits.** The 61 `it(` blocks in that file cover every one of D4's six mechanisms plus D14's pause and idle; they are the only thing that can tell a faithful extraction from a subtly different one, and they only mean that if not a single expectation is relaxed to accommodate the hook. **They are necessary and not sufficient** — the two divergences the `TickOutcome` table above names are not among them, which is why `usePoll.test.tsx` pins those two separately. **If any of them needs an edit, the extraction is wrong** — the escape hatch is, in order: grow the hook (a `runExclusive`, a hold) until the tests pass untouched; and failing that, revert `BoardSection.tsx` to its shipped loop, ship `usePoll` with `FloorPanel` as its only caller, and record the divergence for F37 to resolve. That fallback is worse than the goal and is written down so the build takes it deliberately rather than by editing a test.

Declined: extracting after F57 ships, so F57's panel copies the loop a second time. That is what F34's D13 said not to do the moment a second caller exists, and it is how F37, F41, F42 and F59 each end up with a private copy of the unmount fix — or without it.

### D11 — The panel is a sibling in `App.tsx`, two polls not one, and `BoardSection.tsx` gains no board-level state

`FloorPanel.tsx` is a new component owning **all** of its own state and its own `usePoll` instance. `App.tsx` composes:

```tsx
{activeKey === "board" && (
  <div className="space-y-6">
    <BoardSection />
    <FloorPanel selfId={staff.id} role={staff.role} />
  </div>
)}
{activeKey === "floor" && <FloorPanel selfId={staff.id} role={staff.role} />}
```

**Why no second full-board repaint: the floor state never leaves `FloorPanel`.** React re-renders the component whose state changed and its subtree; a floor tick therefore repaints the cards and nothing else, because `BoardSection` is a **sibling**, not a parent and not a consumer. Lifting the floor rows into `BoardSection` (or into `App`) is the one change that would make every floor tick repaint the day's booking list — including the row a finger is travelling toward, which is the hazard F34 built `holdRef` for. Stated as a rule the plan may not relax: **no floor state above `FloorPanel`.**

**`BoardSection.tsx` is not touched by this decision at all** — the composition happens in `App.tsx` where the role is already in hand. That matters more than it looks: the alternative (widen the `board` nav row to five roles and make `BoardSection` render its bookings half conditionally) cannot be done with a conditional, because the hooks must still run — it would mean splitting a **744**-line component that merged four days ago and whose review found two blockers. The only edits `BoardSection.tsx` takes in this PR are D10's mechanical ones.

**Two nav rows, not one widened row.** `SectionKey` gains an **eleventh** member `"floor"` (`App.tsx:18-28` is a ten-member union today — F52 added `dashboard`, F17 `gateway`, F34 `board`), and `NAV` gains an **eleventh** row after `board`. F57's `i18n.test.ts` block therefore says "the eleventh nav item", the way F51's says seventh, F52's eighth and F17's ninth:

```ts
const FLOOR_ONLY = ["reception", "sales_assistant", "seamstress"] as const;
...
{ key: "board", labelKey: "nav.board", roles: ALL },        // unchanged
{ key: "floor", labelKey: "nav.floor", roles: FLOOR_ONLY },  // NEW
```

Declined: widening `board`'s `roles` to all five. A seamstress would land on a section labelled «לוח היום» whose board the server refuses her — and `BoardSection`'s first fetch would 403, which its own `terminalOf` correctly treats as **terminal** (`BoardSection.tsx:32-47`), blanking the screen and telling her her access ended. The label would promise a thing the gate forbids and the component would be right to break. Two rows cost one `SectionKey` member, one `NAV` row and one i18n key, and every role gets a door labelled with what is behind it.

`activeKey`'s existing fallback does the rest with no edit: the three new roles reach exactly one `NAV` row, `section` initialises to `"dashboard"` which is not reachable for them, and `reachable[0]?.key ?? section` (`App.tsx:121-130`) lands them on the floor. F52's landing decision is untouched — `dashboard` is still `NAV` row 0 for the roles that can reach it (F34's Q-5 = NO, satisfied structurally as before).

**The panel renders AFTER the board, not before**, for a mechanical reason rather than taste: `BoardSection` scrolls its "now" divider into view **once**, on first rows (`BoardSection.tsx:321-333`), and the two panels resolve their first fetch at different moments. A panel above the board grows after that scroll and pushes the divider back out of view. Below, it cannot move anything above it.

**One poll or two: TWO, and the reason is a security reason rather than a load one.** The obvious saving is to merge the day's bookings into `/manage/floor` and poll once. That endpoint admits five roles. The board's payload carries `customer_name` (`OwnerBookingRow`), so merging would put customer names behind a gate that admits a seamstress — or would need a per-role projection of one payload, which `dashboard/router.py:9-11` explicitly declined for a far weaker case (*"there is no per-role projection: a shift manager sees the same six answers the owner does"*). Two endpoints with two different admitted sets is the honest shape. The cost is recorded and pre-sanctioned: *"F34's board polling `GET /manage/bookings?date=` while F57 adds a second 5s loop on the same screen — D13-sanctioned, two requests per 5s is not a load problem for one boutique"* (`floor-program-review-2026-07-31.md` §5). F36, F58 and F37 must extend this payload rather than add a third loop — F36's queue note already says so in as many words.

**What the second tick costs**, derived by F34's D3 method (`shift-board-checkin.md:110-120`) and **not measured** — the citations are `tenancy/middleware.py:74`, `db/tenant.py:25-29`, `db/session.py:59`:

| Per floor tick, per device | Count | Where |
|---|---|---|
| Sessions opened | **3** | `tenants.by_slug` (its own session) → `resolve_session` → `list_live` |
| `set_config` + BEGIN/COMMIT | **2** of each | the two tenant-scoped sessions |
| `SELECT 1` on pool checkout | **3** | `pool_pre_ping=True` |
| Business SQL | **4** | session ×2, `list_live` ×1, `tenants.by_slug` ×1 |
| **Total** | **~6 statements, ~11 round trips, 3 pool checkouts** | |

So a board screen open on one phone goes from ~17 round trips per 5 s to **~28**, and the single cheapest lever is still the one F34's Risk 2 already handed to F29: `tenants.by_slug` is uncached *per request*, so it is now paid **twice** per beat instead of once (`tenancy/resolver.py:8-9` — *"Caching is deliberately deferred to E5"*). Risk 2 below hands F29 the updated number rather than letting it discover one.

### D12 — The panel is a second auto-updating surface, so it carries its own SC 2.2.2 control, and D11's live-region rule is inherited whole

Pre-decided #38 makes IS 5568 / WCAG 2.0 AA a **legal** requirement for these staff screens and Level A sits inside AA. **SC 2.2.2 Pause, Stop, Hide** applies to any content that auto-updates, starts automatically and is presented in parallel with other content — a self-repainting staff grid is squarely that, and **axe has no rule for it** (F34's D14 established this and the review file's F34 note warns that the named vitest assertions are now the *sole* coverage of a legal requirement). So:

- **The panel carries its own visible pause / resume toggle**, 44×44 minimum, in the tab order, beside its own freshness line, with the same behaviour F34 shipped: pause stops the loop, resume fetches **immediately** and resets the interval to the base rather than inheriting a backed-off gap (`BoardSection.tsx:343-355`). Free, in the sense that `usePoll` owns the mechanism (D10) — what F57 owns is the control and its copy.
- **Its own idle stop** at the same `IDLE_STOP_MS`, from the same hook.
- **Two pause controls exist on the board screen for owner and shift_manager, and that is the answer rather than a problem.** Two independently updating regions with two independent loops need two mechanisms; one control governing both would mean lifting pause state into a shared parent, which is exactly the coupling D11 forbids. What it costs is that the two controls must be **distinguishable to a screen reader**: `board.pauseAria` already exists and is distinct from the button's visible text (`BoardSection.tsx:526`), and `floor.pauseAria` names its own region — **«השהיה — עדכון הצוות»**, the shipped `board.pauseAria` shape (`he.ts:481`), not the «השהיית עדכון הצוות» this document first proposed (D13, and the deck's F-2 says why). Declined: one control for both loops (couples the panels); declined: no control on the panel, relying on the board's (the three floor roles have no board at all — that is the case that makes it unmissable rather than merely wrong).
- **A break toggle that answers 403 is TERMINAL** — deck §8 **P-6**. The panel goes into the same session-or-permission-ended state a failed tick would, because `usePoll.fail(error)` classifies a mutation's error on the same `{401,403}` rule the ticks use (D10's contract). The alternative — an in-card alert plus a loop that keeps polling with a role the server just refused — is the panel disagreeing with itself for up to five seconds and then doing the same thing anyway. The realistic cause is a mid-shift demotion between the last tick and the tap.
- **And its converse: a 404 is NOT terminal.** It stays an in-card alert — *"a colleague vanishing is a fact about her, not about the viewer's access"* — which needs a key this document's first D13 list did not have: **`floor.error.notFound`**, in the `text-danger` fix-this register, **inside the card**, because a panel-level error names no colleague.
- **The poll never writes into an aria-live region** (F34's D11, verbatim and non-negotiable): a `role="status"` update every five seconds announces the whole staff list to a screen-reader user forever. The panel's announced region carries **only user-initiated outcomes** — the break cue, the pause, the idle stop (whose trigger is her own inactivity), the terminal alert. A poll that changes cards repaints them silently, and the freshness line is visible, readable and **not** `aria-hidden` (F34's accepted F-1 ruling — the board's only honesty signal must not be sighted-only).
- **Status never by colour alone.** Each card's status is a word — «פנויה» / «בהפסקה» — and where it is on a break, the time it started. A 🟢/🟡 dot may accompany the word and may never replace it. The role likewise: F51's badge already carries the word and never the colour (`StaffSection.tsx:303-305`) and the card copies that.
- **No shimmer, no pulse, no flash on refresh** — the same rule that serves `prefers-reduced-motion`, F34's D11.
- `<bdi dir="ltr">` around every numeric run (times), bare `<bdi>` around Hebrew free text (display names), one `h1` (the shell's) with the panel heading an `h2`, visible focus ring on every control, and **focus never dropped to `<body>`** when a card repaints under a tapped button. That last one is not boilerplate: it is the bug class that has now shipped **twice** in this repo (F56 on the storefront, F34 on the board), both times because `@boutique/ui`'s `Button` is `disabled={disabled || loading}` so the browser blurs the tapped control the instant a request starts, and both times axe walked straight past it. The break control is exactly that shape. **The failure path is the one that gets forgotten** — F34's success path compensated and its catch path did not — so the panel moves focus on **both** outcomes, keyed on the state that renders the message rather than raised inside the handler (`BoardSection.tsx:308-319` is the shape).

### D13 — i18n: the role word becomes a table, and every key ships in both files

New `floor.*` namespace plus `nav.floor` and three `staff.role*` keys, in `apps/manage/src/i18n/he.ts` **and** `ar.ts`, with the Hebrew standing in untranslated in `ar.ts` — Interview Q3, pre-decided #47, the 2026-07-31 languages ruling, and `ar.ts:14-21`'s own mechanics (never empty strings; `lng` and `fallbackLng` stay `"he"`; no switcher). Proposed copy for the load-bearing keys:

| Key | Hebrew |
|---|---|
| `nav.floor` | «הצוות בקומה» |
| `floor.heading` | «צוות בקומה» |
| `staff.roleReception` | «קבלה» |
| `staff.roleSalesAssistant` | «יועצת מכירות» |
| `staff.roleSeamstress` | «תופרת» |
| `floor.statusAvailable` | «פנויה» |
| `floor.statusBreak` | «בהפסקה» |
| `floor.breakSince` | **«מאז {{time}}»** — corrected from «בהפסקה מ־{{time}}» (deck F-3): the `Badge` directly above already reads «בהפסקה», and repeating it spends 295px of a 375px screen saying one thing twice and makes two signals look like two facts |
| `floor.pauseAria` / `floor.resumeAria` | **«השהיה — עדכון הצוות» / «חידוש — עדכון הצוות»** — corrected from «השהיית עדכון הצוות» (deck F-2): the visible label is «השהיה» and «השהיית» is a different word form, so the accessible name would not **contain** the visible label — **WCAG 2.5.3 label-in-name** — and a speech-input user saying "השהיה" would match nothing. `board.pauseAria` «השהיה — עדכון הלוח» (`he.ts:481`) is the shipped shape |
| `floor.breakStart` / `floor.breakEnd` | «להפסקה» / «חזרה» |

plus `floor.pause` / `floor.resume` / `floor.pauseAria` / `floor.resumeAria` / `floor.pausedAt` / `floor.paused` / `floor.idleStopped` / `floor.resumed` / `floor.loading` / `floor.updatedAt` / `floor.staleAt` / `floor.staleBody` / `floor.refresh` / `floor.empty` / `floor.sessionEnded` / `floor.accessEnded` / `floor.reload` / `floor.breakStartAria` / `floor.breakEndAria` / `floor.breakStartedCue` / `floor.breakEndedCue` / `floor.error.notFound` — the board's own state set, which is the set a second polling surface needs and a reason not to re-derive it.

**`floor.outage` was proposed here and is NOT shipped.** The copy deck (`copy.md` §5, `design.md` §9 **F-10**) reuses the shipped `staff.loadFailed` «לא הצלחנו לטעון את רשימת הצוות כרגע.» (`he.ts:205`) for the first-fetch failure instead: it is the same sentence about the same subject — the boutique's staff list failing to load — and two byte-identical strings under two keys is how a console ends up spelling one fact two ways the day somebody edits one of them. **This is a third copy correction to this table**, alongside C8's two, and it is the one place where reusing a key from a **more** restricted namespace (`staff.*` is F51's owner-only section) is right where reusing `board.*` was wrong; F-10 carries that argument. **The canonical key list is `copy.md`'s table — 32 invented, 4 reused — not this paragraph.**

**The role word stops being a ternary.** `StaffSection.tsx:99-100` reads `role === "owner" ? t("staff.roleOwner") : t("staff.roleShiftManager")`, which after this migration **silently labels a seamstress "אחראית משמרת"**. That is the "widening the enum silently widens nothing" trap in its frontend form, and it is a real defect this feature creates if the plan does not name it. It becomes one record, exported from `lib/` so `StaffSection` and `FloorPanel` share it:

```ts
export const ROLE_LABEL_KEY: Record<StaffRole, string> = {
  owner: "staff.roleOwner",
  shift_manager: "staff.roleShiftManager",
  reception: "staff.roleReception",
  sales_assistant: "staff.roleSalesAssistant",
  seamstress: "staff.roleSeamstress",
};
```

`Record<StaffRole, string>` is the point: adding a sixth member to the union without a key is a **type error**, not a wrong label. A vitest assertion resolves every value through i18n so a key that exists in the map but not in `he.ts` is caught too.

**No new formatter.** `lib/jerusalem.ts`'s `jerusalemTime` renders the break-start time with `timeZone: Jerusalem` already (`jerusalem.ts:35`), so `scripts/qa-greps.sh`'s unzoned-formatter grep gains nothing to find. **No he/ar parity guard is invented** — F15's Risk 5, inherited unchanged by F34 and inherited again here.

### D14 — F51's staff CRUD is not rebuilt; only its role select widens

Three edits to `StaffSection.tsx` and one to `api.ts`, and nothing else on that surface:

- `api.ts:362` — `export type StaffRole = "owner" | "shift_manager"` gains the three members. `StaffMember`, `CreateStaffRequest` and `UpdateStaffRequest` inherit it with no edit.
- `StaffSection.tsx:242-243` and `:373-374` — three `<option>`s each, labels from `ROLE_LABEL_KEY`.
- `StaffSection.tsx:99-100` — `roleWord` reads the record (D13).

**No backend change to F51.** `CreateStaffRequest.role: StaffRole` and `UpdateStaffRequest.role: StaffRole | None` are typed as the enum precisely so *"an unknown value is a house 422→400 at the boundary and can never reach 0011's CHECK"* (`auth/schemas.py:65-67`) — widening the enum widens both requests with zero edits. `StaffService`'s guards keep working on their own terms and are worth stating because a reader will ask:

- **The last-owner guard still fires**, because it keys on the target *leaving* `owner` and not on where it is going: `role_moves and target.role == StaffRole.OWNER.value and count_live_owners(...) <= 1` (`auth/staff.py:187-193`). Demoting the last owner to `seamstress` is refused exactly as demoting her to `shift_manager` is.
- **The self-demote guard still fires** — `role_moves and is_self` (`:187-188`).
- **`STAFF_ROLE_CHANGED`'s `details={"from": …, "to": …}`** (`:251`) carries the new values with no edit, because they are strings.

`test_staff_service.py` and `test_staff_api.py` gain cases for the new values against those three facts; nothing in F51 is redesigned.

## API surface

| Method | Path | Body | Answers | Admits |
|---|---|---|---|---|
| `GET` | `/manage/floor` | — | `FloorResponse` | all five roles |
| `POST` | `/manage/floor/staff/{staff_id}/break/start` | — | `StaffCard` | all five (self, or elevated on anyone — D6) |
| `POST` | `/manage/floor/staff/{staff_id}/break/end` | — | `StaffCard` | same |

Neither POST takes a body, so neither needs a `ForbidExtraModel`. Both are `cache-control: no-store` by the router-level dependency, and both are CSRF-fenced by `CsrfOriginMiddleware` because they are mutating methods (`csrf.py:48`).

```jsonc
// GET /manage/floor
{
  // An ENVELOPE, not a bare array — F51's /manage/staff returns a bare list and
  // that was right for a list. This payload is the floor's, and F36 adds rooms
  // + occupancy to it, F58 adds the waitlist. An envelope makes those additive;
  // a bare array makes the first of them a breaking shape change.
  "staff": [
    {
      "id": "0f5f…",
      "display_name": "דנה",
      "role": "seamstress",
      "status": "available",          // "available" | "break" — and NOTHING else (D9)
      "break_started_at": null
    },
    {
      "id": "9c21…",
      "display_name": "נועה",
      "role": "reception",
      "status": "break",
      "break_started_at": "2026-08-02T11:20:00Z"
    }
  ]
}
```

```jsonc
// POST /manage/floor/staff/9c21…/break/end  -> the card, patched in place
{ "id": "9c21…", "display_name": "נועה", "role": "reception",
  "status": "available", "break_started_at": null }
```

**Errors — zero new codes, zero new handlers.** `SPEC_ERROR_CODES`-style set equality in `test_floor_api.py` asserts F57 introduces none.

| Condition | Status | Code | New? |
|---|---|---|---|
| No session / expired | 401 | `NOT_AUTHENTICATED` | no — app-wide |
| A role outside all five (a hand-edited row) | 403 | `NOT_AUTHORIZED` | no — F31's, generic body |
| Non-elevated caller targeting someone else | 403 | `NOT_AUTHORIZED` | no — the same generic body, raised in the service (D6). **On the panel this is TERMINAL** (deck P-6, D12) |
| Unknown / deactivated / another tenant's `staff_id` | 404 | `NOT_FOUND` | no — `DomainNotFoundError`, `main.py:757-759`. **On the panel this is an in-card alert, NOT terminal** (`floor.error.notFound`) |
| Repeat start, repeat end | **200** | — | not errors, by D7 |
| Mutating request from a foreign origin | 403 | `CSRF_ORIGIN_MISMATCH` | no — `csrf.py:15-16,48` |
| Backend down / 5xx | — | — | no — backoff, not terminal (D10) |

## Frontend changes

| File | Change |
|---|---|
| `apps/manage/src/lib/usePoll.ts` | **new** — the extracted loop: single arming site, `document.hidden` + `visibilitychange` immediate, `{401,403}` terminal, 5s→60s backoff, idle stop, generation, **and F34's unmount fix (`runningRef.current = false` in cleanup) with its comment** (D10) |
| `apps/manage/src/lib/roles.ts` | **new** — `ROLE_LABEL_KEY: Record<StaffRole, string>` (D13). In `lib/` so `StaffSection` and `FloorPanel` share it without an import cycle |
| `…/components/FloorPanel.tsx` | **new** — the cards, their own `usePoll`, the break control, the pause/resume + idle control, the freshness line, the announced region, the terminal panel. The **empty** state is `<EmptyState title={floor.empty} />` inside the `Card` with **no body and no CTA** (deck F-empty; `BoardSection.tsx:4` already imports the component), and the freshness row still renders beneath it — *a panel that has stopped updating must still be able to say so*. No test beyond "it does not crash on `[]`" |
| `…/components/BoardSection.tsx` | **migrated onto `usePoll`** — the loop deleted, the constants imported, the hold check moved to the top of `run`, `mutate`'s catch calling `poll.fail(error)`. **No behavioural change: `BoardSection.test.tsx` must pass with zero edits** (D10) |
| `…/components/StaffSection.tsx` | three `<option>`s per select ×2; `roleWord` reads `ROLE_LABEL_KEY` (D13/D14) |
| `apps/manage/src/App.tsx` | `SectionKey` gains an **eleventh** member `"floor"`; `FLOOR_ONLY`; an **eleventh** `NAV` row after `board`; the `board` branch wraps `<BoardSection/>` + `<FloorPanel/>`; a `"floor"` branch rendering `<FloorPanel/>` alone (D11) |
| `apps/manage/src/api.ts` | `StaffRole` union gains three members; `StaffCard` / `FloorResponse` interfaces; `getFloor`, `startStaffBreak`, `endStaffBreak` on the exported `api` object |
| `…/i18n/he.ts`, `…/i18n/ar.ts` | `nav.floor`, the `floor.*` namespace, three `staff.role*` keys — **both files**, Hebrew untranslated in `ar` (D13). **Transcribed from `copy.md`'s table** (32 invented, 4 reused), which is the single source for both columns and the whole of F-5's parity mitigation. **No `floor.outage`** — `staff.loadFailed` is reused |
| `…/__tests__/FloorPanel.test.tsx` | **new** |
| `…/__tests__/usePoll.test.tsx` | **new** — the unmount test above all (D10) |
| `…/__tests__/BoardSection.test.tsx` | **no change — and that is the acceptance rule for D10** |
| `…/__tests__/Nav.test.tsx` | three new role cases; the owner/shift-manager counts unchanged |
| `…/__tests__/StaffSection.test.tsx` | the five-option selects; a seamstress row renders «תופרת» |
| `…/__tests__/i18n.test.ts` | an `F57 floor keys resolve` block, the shape F15/F51/F52/F17 each have |
| `vite.config.ts` | **no change** — `/manage/floor*` is under `/manage`, already proxied |
| `scripts/qa-greps.sh` | **no change** (D13) |
| `test_frontend_constant_parity.py` | **no change** — `POLL_INTERVAL_MS` and friends mirror no server bound |

**States `FloorPanel` must render:** initial load · loaded with cards · **empty** (impossible in practice — the caller is herself a live staff row — so it is a one-line `EmptyState`, not a designed screen) · first-fetch failure (outage register) · **a failed poll with cards on screen** (keep them, mark stale) · session-or-permission ended (401/403, loop stopped, reload affordance, copy that does not name a role) · paused · idle-stopped · break in flight on a card · a break mutation failure.

## Testing

**Fast suite (no marker, no Docker):**

- `tests/test_floor_api.py` (**new**, the `test_dashboard_api.py` shape): a `ROUTES` table for the three routes, which gives the 401 walk, the wiring walk and the `cache-control: no-store` parametrization; a `FakeFloorService`; each route reaching its own service method with the right arguments; the error-code set asserted **set-equal and empty of new members**; the payload literal for a two-card floor; `StaffCardStatus`'s wire literals asserted **set-equal to `{"available", "break"}`** (D9 — the test that fails if `occupied` is pre-added).
- `tests/test_floor_service.py` (**new**): the authorization matrix as a pure branch against fakes, **which is where D6 is actually proven** — owner on another → allowed; shift_manager on another → allowed; reception/sales_assistant/seamstress on **herself** → allowed; each of those three on **another** → `NotAuthorizedError` **and the target repository is never called** (the assertion that proves the check runs before the read, i.e. that the 403 is not an existence oracle); the `(wrote, row)` mapping onto 200 / 200-unchanged / 404; an audit row on a write and **none** on a no-op; the end's `details` carrying `previous_break_started_at`.
- `tests/test_staff_role_gating.py` (**extended**): `test_the_floor_roles_reach_exactly_the_floor_routes` (D5, derived from the live route table, classifying on the **intersection**); `FLOOR_ROUTES` added to the two HTTP walks at `:340` and `:371` with the `_client(floor=…)` asymmetry D5 describes; the `UNKNOWN_ROLE` comment moved to the past tense.
  - ⚠ **`test_gate_admits_listed_roles` gains a NEW CASE, not three roles.** That test (`:243-247`) is a **RoleGate unit test** that builds `require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)` and asserts it admits `("owner", "shift_manager")`. Adding `"reception"` to that loop would assert something **false and dangerous** — that a two-role gate admits a floor role. The existing case is untouched; a **second** case asserts that `require_role(*StaffRole)` — the shape D4 puts on the floor router and nowhere else — admits all five. Declined: widening the existing assertion (it inverts the meaning of the shipped gate); deleting it (it is the only unit-level proof that a narrow gate stays narrow).
  - **`test_gates_admit_only_known_roles` (`:165-181`) needs ZERO edits, and that is coverage rather than a gap.** It derives `known = {role.value for role in StaffRole}` from the **live enum** and asserts every discovered gate's `allowed_roles <= known`, so widening the enum widens `known` in the same breath and the floor router's `require_role(*StaffRole)` passes by construction. Recorded so nobody "adds the three roles" to it — a no-op edit that would make a derived test look hand-maintained. Same class as `test_the_not_authorized_contract_is_pinned_by_literal` (`:396-397`), which already iterates `StaffRole`, so the three new values join its no-role-leak scan **with no edit** too.
- `tests/test_staff_service.py`, `tests/test_staff_api.py` (**extended**): creating and patching to each new role; the last-owner guard refusing `owner → seamstress`; the self-demote guard refusing it too; `STAFF_ROLE_CHANGED`'s `details` carrying the new value (D14).

**db-marked (CI only — no Docker locally, per the run's standing constraint. F34's shipped note is the standard to meet: stand up a throwaway Postgres 16 cluster outside the repo, run every migration and execute these before pushing, and CAPTURE the deparsed constraint literal rather than transcribing it):**

- `tests/test_migrations.py` (**extended**):
  - `test_staff_role_check_pins_the_role_set` (`:73-93`) — **rewritten to iterate `StaffRole`** rather than list values, so the day a sixth role is added the test covers it or fails; `UNKNOWN_ROLE` still refused. Every probe rolls back (D1's trap).
  - a sibling of `test_adding_the_role_check_validates_existing_rows` (`:154-189`) for the widened set, using the migration's **verbatim** `ALTER` (`_ADD_WIDE_ROLE_CHECK`) and a `_DROP` without `IF EXISTS`, both halves: rows holding `owner` + `shift_manager` + `reception` present ⇒ the constraint is added; an unknown-role row present ⇒ **refused**, asserting the constraint name is in the error.
  - the constraint definition **pinned byte-identical after this feature's migration** — `pg_get_constraintdef` for `staff_users_role_check` (D3).
  - `break_started_at` is a **nullable** `TIMESTAMPTZ` on `staff_users`; this feature's migration up and down.
  - the **downgrade's honest failure**: with a `reception` row present, the narrowing re-`ADD CONSTRAINT` is refused. Rolled back.
  - `test_the_app_role_can_promote_to_shift_manager_but_not_to_an_unknown_role` (`:96-151`) extended to promote to a floor role under the app role, under forced RLS, with only its GRANTs — the F51-style pre-flight for the widened set. **Its seeded row must not be left holding a new role** (D1's trap, and `:106-110` is the comment that explains why).
- `tests/test_floor_db.py` (**new**): a start writes the timestamp and an end clears it; a **second** start keeps the **first** timestamp and reports no write (the idempotency predicate); a start racing an end on one row leaves whichever committed first and the loser renders the **database's** value, not its own — the assertion that fails if the `populate_existing=True` re-read is dropped (D7); the floor read returns every live staff row and **no soft-deleted one**; **RLS isolation — tenant B's staff row can neither read tenant A's staff nor toggle tenant A's break (404, indistinguishable from missing)**. ⚠ **Every row this module commits holds `owner` or `shift_manager`, never a floor role** (D1's trap): the interleave commits by construction and the isolation probe needs a persisted second-tenant row, and neither assertion depends on the actor's role — the role gate is `test_floor_service.py`'s and `test_staff_role_gating.py`'s, not this module's.

**Frontend (vitest):**

- `__tests__/usePoll.test.tsx` (**new**): **a request unresolved at unmount arms nothing** — resolve it after unmount, advance several intervals, assert the call count did not grow (D10, F34's shipped bug); exactly one request per tick and never two in flight; `document.hidden` pauses and `visibilitychange` fetches immediately; 401 and 403 each stop the loop (**two tests, not one** — F34's reasoning: they arrive by different code paths); consecutive failures back the interval off and cap, one success resets it; `pause` stops and `resume` fetches **before** the interval elapses and at the **base** gap not the backed-off one; the idle stop fires and one interaction resumes; **a `run` returning `"held"` during a backoff re-arms at the backed-off gap and does not reset it**; **a `run` returning `"suppressed"` arms no timer at all** — the two `TickOutcome` divergences `BoardSection.test.tsx` cannot see (D10).
- `__tests__/BoardSection.test.tsx` — **unchanged, and its passing unedited is the acceptance gate for the migration** (D10).
- `__tests__/FloorPanel.test.tsx` (**new**): cards render name, role **word** and status **word**; a card on a break shows the start time; the break control patches the card **from the response** and is disabled while in flight, and a double-tap fires one request; **after a FAILED break toggle the loop keeps polling** (the re-arm, F34's D4.4 — the test that would still pass if it were dropped, and every other test here would too); a failed toggle **moves focus to the alert** (the twice-shipped `<body>` bug — the failure path specifically); **the announced region does not change on a poll tick** and does change on a toggle and on a pause (D12); the pause control stops the loop and resume fetches immediately; the idle stop fires; a failed poll with cards on screen keeps them and marks stale; a first-fetch failure shows the outage register; a 401 and a 403 each show the terminal panel and stop; **the break control is absent on other people's cards for a non-elevated role and present on her own** (cosmetics, asserted as cosmetics — the server is the control); an **axe pass, explicitly not sufficient** — axe has no SC 2.2.2 rule, so the pause and idle assertions are the only automated coverage of a legal requirement and must not be cut as redundant with the axe row.
- `__tests__/Nav.test.tsx` (**extended**): a reception / sales_assistant / seamstress user sees **exactly one** nav row and lands on the floor section (the `reachable[0]` fallback, `App.tsx:121-130`); the owner's ten and the shift manager's eight are **unchanged** by this feature — a count assertion that fails if `board` was widened instead of `floor` added (D11).
- `__tests__/i18n.test.ts` (**extended**): the whole `floor.*` deck resolves; every value of `ROLE_LABEL_KEY` resolves to its own Hebrew (the `Record<StaffRole, …>` type catches a missing member, this catches a missing key); `nav.floor` resolves beside the nested `nav` object.

**No E2E**, and the reason is F34's verbatim: the console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend (`e2e/a11y.spec.ts:10-13`). **F58 owns the `/manage/**` interception harness** — the floor-program review budgets it there as real work. Recorded rather than silently skipped.

## Out of scope

- **Fitting rooms, occupancy and the `occupied` status** — F36's, which extends this payload and widens `StaffCardStatus` in the PR that gives it a writer (D9).
- **Dispatch, take-next, push-assign, the waitlist panel** — F58's, on this same payload.
- **SOS, the full-screen alert, the escalation** — F37's.
- **Queue tickets, the public check-in form, the wall board** — F33's and F59's.
- **Break history, break duration reporting, "who was on a break when"** — no table (D2). The two audit rows are the only record and nothing reads them (F15's Risk 7).
- **A maximum break length, an auto-end-of-break sweep, a worker tick** — nothing schedules a break's end (D7).
- **On-shift / off-shift marking and a published roster** — pre-decided #33 gives that to F40, and F34's D9 already recorded that `staff_users` has no `on_shift` column. "Live status" in this feature means available-or-on-a-break, not rostered.
- **Any per-role narrowing of an existing route.** F57 widens the role set and opens two doors; it does not re-scope what a shift manager may reach (`OWNER_ONLY` is untouched).
- **A staff avatar, a photo, a phone number on the card** — the card is a name, a role and a status.
- **Rebuilding F51's staff CRUD** (D14).
- **The tri-lingual top bar / a language switcher** — deferred by the 2026-07-31 languages ruling; `ar` keys keep shipping untranslated.

## Codebase conflicts recorded

1. **Pre-decided #24 names the slug `'sales'`; this feature ships `'sales_assistant'`.** Overridden by the user's 2026-07-31 roles ruling (`LOOP-STATE.md`, `rulings_2026_07_31`). Flagged so a reader who finds #24 finds the ruling too.
2. **`constants.py:10-12` and `0011_staff_roles.py:20-21` both say the three roles join "when E6-proper gives them their first consumer".** The floor program is not E6-proper — it is a re-prioritised block drawn from E6 and E7. Read as the bar being *met* rather than waived: the roles arrive **with** a consumer in the same PR, which is what those comments were protecting against. Both comments are rewritten to record that the consumer arrived; neither is deleted.
3. **`test_staff_role_gating.py:81-91` and `test_migrations.py:54-56` choose their unknown-role sentinel *because* reception/seamstress/sales were unclaimed.** That premise expires today. The sentinel `"no-such-role"` and its tripwire hold unchanged (D5); only the comments move to the past tense. Named because a reviewer reading the comment against the new enum would otherwise think the test had rotted.
4. **F34's D13 declined the `usePoll` extraction and the floor-program review told F34 explicitly not to pre-extract it** (*"do not pre-extract `usePoll`… pre-empting it makes F57 unreviewable"*). F57 is the reopening condition D13 itself named. Doing it here is compliance with both documents, not a reversal of either — and D10's zero-edit rule on `BoardSection.test.tsx` is what makes it reviewable rather than merely done.
5. **F34's spec Out-of-scope says what F35/F37/F44 inherit is *"D4's six mechanisms as a documented pattern and one interval constant — nothing executable"*.** After F57 it is executable, and the floor-program review already reassigned that inheritance to F57/F37/F41/F59. F37, F41, F42 and F59 import `usePoll` rather than copying a loop. Stated so those four features are not scheduled against the older sentence.
6. **F34's Risk 2 gave F29 a per-tick cost derived for one loop on the board screen.** F57 adds a second loop to the same screen, so the number F29 inherits changes: ~28 round trips per 5 s per device on that screen, and `tenants.by_slug` — the lever `tenancy/resolver.py:8-9` already assigns to F29 — is now paid twice per beat. Restated in Risk 2 rather than left for F29 to rediscover.
7. **The floor read admits five roles to a `/manage` surface for the first time.** Every prior `/manage` route admits at most owner + shift_manager. Nothing in the codebase contradicts it — it is simply new — and D5's walker assertion is what keeps "first" from becoming "first of many by accident".

## Risks & open items

1. **The three new roles are one walker assertion away from reaching everything.** F31's gate default-denies by construction, so the risk is not that a floor role leaks today — it is that a future `/manage` router spelled `require_role(*StaffRole)` (which D4 makes legal and correct **on the floor router**) is copy-pasted onto a router that answers customer data. `test_the_floor_roles_reach_exactly_the_floor_routes` is the only thing between that copy-paste and a seamstress reading the day's brides. It must never be relaxed to a subset check, and `FLOOR_OPEN` must never gain a route without the reviewer asking why. *Owner: team. Trigger: every feature in the floor block — F36, F58 and F37 all add `/manage` routes, and F36 and F58 will both want to extend the floor router.*
2. **The board screen now polls twice per beat, and the cost is derived rather than measured.** ~28 round trips and 7 pool checkouts per 5 s per device on that screen (D11's table, F34's D3 method, citations at `tenancy/middleware.py:74`, `db/tenant.py:25-29`, `db/session.py:59`). Ten phones on one tenant is now ~150 statements/s of polling. Nothing throttles it server-side (F34's D3 declines a read limiter and that reasoning holds — there is no attacker, only loyal clients), the client backoff and the idle stop are the only ceilings, and `tenants.by_slug` is uncached **per request** and therefore paid twice per beat. **F29 must be handed this number, not left to discover it.** *Owner: team. Trigger: F29's k6 pass, whose targets pre-decided #22 derives from staging metrics.*
3. **The `usePoll` migration could regress F34's two shipped bug fixes, on the one component in the console that has already had both.** The focus rescue (WCAG 2.4.3, legal here) and the unmount fix are one line each and both live in code this PR rewrites. D10's mitigation is mechanical — `BoardSection.test.tsx` passes unedited or the extraction is wrong — and `usePoll.test.tsx` gets its own named unmount test so the fix is proven at the layer it now lives in. *Owner: team. Trigger: the code-review pass; a reviewer seeing any edit to `BoardSection.test.tsx` should stop and read D10.*
4. **A break has no upper bound and nothing ends it but a tap.** A staffer who taps «להפסקה» and goes home reads as on-a-break until somebody clears her, across days. Deliberate (D7 — no clock bound, no sweep, no worker), because every automatic end is a guess about a person's shift and the product has no roster to guess from (F40's, pre-decided #33). The visible mitigation is that the card shows *since when*, so a stale break is legible rather than silent. *Owner: user. Trigger: pilot feedback, or F40's roster, which is the first thing that could end a break honestly.*
5. **The break control is authorized by role and by identity, and only the identity half has a structural proof.** The elevated half is a set membership on `StaffContext.role` (one line, one fast test); the self half is an id comparison whose safety depends on nothing downstream ever reading a target id as an actor id. Nothing in the codebase does today and D6 forbids it in writing — but F58's push-assign and F37's SOS targeting are both "act on a named colleague" surfaces arriving within four features, and both will be tempted by the same shape. *Owner: team. Trigger: F37's spec, which is the first one to take a target staff id in a body.*
6. **The three floor roles have exactly one screen, and if `/manage/floor` is down they have none.** A seamstress whose floor read 401s or 403s sees the terminal panel and a reload button and nothing else — no dashboard, no bookings, no fallback, because those are the surfaces her role is refused. That is correct behaviour and a thin one. *Owner: team. Trigger: the first pilot morning; the cheap remedy if it bites is a role-aware empty state rather than a new door.*
7. **`ar.ts` still has no parity guard.** F57 adds ~20 keys to both files by hand. F15's Risk 5, inherited by F34, inherited again. *Owner: team. Trigger: the feature that makes Arabic selectable (F45).*
8. **The audit rows are still write-only.** Two more actions nothing renders, and `previous_break_started_at` is the only surviving copy of a destroyed break-start with no way to read it without `psql` (F15's Risk 7, F34's Risk 7). *Owner: user. Trigger: pilot feedback, or F53's activity log.*
9. **No E2E covers either poll loop, and now there are two on one screen.** Both are unit-tested with fake timers against a mocked `api`; neither is exercised against a real backend, and the interaction most likely to differ in reality — two concurrent polls on boutique wifi with one of them slow — is exactly what fake timers model least faithfully. F34's Risk 8, widened. *Owner: team. Trigger: F58, which builds the `/manage/**` interception harness.*
10. **`break_started_at` is a record of a named employee's working pattern, and no privacy notice covers it.** It is a smaller delta than F34's arrival record — it is about staff, not customers, and every staffer can see every colleague's status by design — but it is a new processing purpose over employee data with a 7-year retention inherited from the row it sits on. **F20 (`spec_gate: user`, owner of the collection notice and the processing-activities record) must carry a staff-break entry: purpose = floor operations, retention = with the staff record.** No build work here, no change to F57's scope. F34's Risk 9, same hand-off, different subject. *Owner: team, discharged by F20. Trigger: F20's spec, which stops for the user anyway.*

## Review findings raised and REJECTED

Two adversarial critics reviewed the F57 artifacts on 2026-07-31. **All thirteen findings were factually correct and all thirteen are applied** — across this spec, `.planning/plans/floor-staff-roles.md`, `design.md` and `copy.md`. What is recorded below is the sub-proposals inside those findings that were **not** taken, because a later reader will find the finding text and should find the reason too.

**REJECTED — "keep D10's pointer-hold claim and just add two `usePoll.test.tsx` tests for it."** Offered as option (ii) alongside growing `run`'s contract. Declined: the claim *"byte-identical behaviour with zero API"* is false against the shipped source in two places (`BoardSection.tsx:228-232` re-arms a held tick at the backed-off gap; `:219-222` arms nothing at all during a mutation), and two tests pinning behaviour the contract does not describe would leave the next builder implementing the contract and failing the tests. The contract is the thing that was wrong, so the contract is what changed — `TickOutcome` is two union members, which is still less surface than the `runExclusive` wrapper D10 declines. The two tests ship **as well**, not instead.

**REJECTED — "render the colleague's name in the VISIBLE break-control label on other people's cards"** («להפסקה — נועה לוי»), and **REJECTED — "give the self card a `Badge variant='muted'` instead of the muted «זו את» span."** Both were offered as remedies for the sighted-viewer ambiguity an elevated staffer faces on five near-identical cards. Declined at this gate for one reason: they are **design changes**, and the design gate self-approved on the explicit basis that this panel introduces no shape F34 had not already put in front of a user (`design.md` header). A visible label that differs per card is a new control shape and a new copy row; a Badge on the self card is a second Badge on a card whose single-Badge rule is deck **P-2**. What the finding was right about is that the deck answered the screen-reader case at length and never answered the sighted one — so §2.2 now **answers it as a decision** with the upgrade path recorded, rather than leaving a gap a reviewer cannot argue with. If the pilot shows a mis-tap, the visible-label variant is the first thing to reach for and it costs one interpolated key.

**REJECTED — "declare `floor.outage` and drop the `staff.loadFailed` reuse"** (the other half of the design.md ⇄ copy.md disagreement). Declined: the two strings would be byte-identical and about the same subject, and F-9 already records that this feature carries ten such duplicates against its will. The namespace objection is real and is answered rather than waved past — see `design.md` §9 **F-10**.

**REJECTED — "redraw §1's wireframes in RTL."** Declined as cost with no buyer: a one-line note above the block saying the diagrams are LTR-drawn and that inline-start is the physical right disambiguates §5's "aligned to inline-end" and §6's `justify-end` for the same effect, and a hand-mirrored ASCII block in a Markdown file is a new thing to keep true.

## Decisions Log

- **D1 — `StaffRole` gains `RECEPTION`, `SALES_ASSISTANT`, `SEAMSTRESS`; the DB CHECK widens by DROP + ADD on the named `staff_users_role_check`.** `ALTER CONSTRAINT` cannot change a CHECK expression; `ADD CONSTRAINT` validates existing rows and a widening can only admit rows already legal, proven on a populated table by the shape `test_migrations.py:154-189` already carries. Declined: `NOT VALID` + `VALIDATE` (lock avoidance a single-digit staff table does not need, and a window where the constraint means nothing); dropping the CHECK for Python-only validation (`test_me_echoes_an_out_of_enum_role_verbatim:470-482` says in writing that the database is what makes the un-allowlisted `/manage/auth/me` echo safe). The downgrade re-adds the two-value CHECK and **fails loudly** if a new-role row exists — and every F57 db test must roll its probe rows back, because `test_migration_0011_round_trips` unwinds this migration and `test_migrations.py:106-110` deliberately leaves a row behind.
- **D2 — `staff_users.break_started_at TIMESTAMPTZ NULL` is the whole break model.** Declined a `status` column: `occupied` is F36's `(tenant_id, staff_user_id) WHERE released_at IS NULL` index, so a status column would oblige F36 to double-write into `staff_users` on every claim and release, racing the concurrency it exists to prevent — F34's D1 argument for orthogonal facts. Declined a `staff_breaks` table: history nothing asks for, at the cost of an RLS policy, grants, an isolation suite and an F20 retention row; the two audit rows are the recorded back-fill path. Declined `break_ended_at` (two columns for one boolean, plus a third state meaning the same as NULL). No index — nothing filters or sorts on it.
- **D3 — One migration, revision id read from `alembic heads` at build time, never from this document** (F34's D2 rule, whose payoff is recorded in F34's shipped note). No GRANT (table grants are column-agnostic), no `enable_tenant_rls` (a table property, already forced), no trigger, no index, no default. **The ORM column is not optional** — no model↔migration parity test exists, so without it every backend line in D7 and D9 is an `AttributeError`. The widened constraint definition is pinned byte-identical **after this feature's migration** by a db-marked test whose literal is **captured by running it**, because Postgres deparses `IN (...)` to `= ANY (ARRAY[...])`.
- **D4 — `GET /manage/floor` is a new `app/floor/` module on the `app/dashboard/` pattern, gated `require_role(*StaffRole)` at router level.** The decisive reason is structural: `RoleGate` composes by **intersection** (`auth/dependencies.py:44-45`; `test_staff_role_gating.py:129-136`), so a route on an existing router can only be *narrowed*, never widened — there is no per-route way to admit a seamstress to `booking/owner_router.py`. Declined: relaxing that router's gate and re-tightening twelve routes (twelve gates to protect one route, first mistake exposes the day's customer list); hanging it off `auth/staff_router.py` (whose docstring's owner-only-at-router-level guarantee it would delete). Spelled `*StaffRole` rather than five literals so a sixth role is admitted here by default — safe only because D5 pins the floor roles out of everywhere else.
- **D5 — The three new roles reach exactly six routes: three ungated auth routes they already reached, plus `GET /manage/floor` and the two break toggles.** Everything else is refused with **no code change**, because every shipped gate names its roles positionally. `test_the_floor_roles_reach_exactly_the_floor_routes` derives from the live route table with **three** assertions — no floor role outside `FLOOR_OPEN` (which also catches a floor route that LOST its gate, because an ungated route's `effective` is empty and it drops out of `admits_floor`); all three roles admitted on each `FLOOR_OPEN` route; no stale `FLOOR_OPEN` entry — so a future route that admits one of them fails on the day it is written. **It classifies on the INTERSECTION of a route's gates, never with `any(...)` over them**, because that is how `RoleGate` composes and because `any(...)` would red-fail on the first per-route-tightened floor route F36 adds — the shape most likely to get the test "fixed" by the relaxation Risk 1 forbids. `FLOOR_ROUTES` joins the two shipped HTTP walks (`:340`, `:371`) so the gate is proven to *raise* and not merely to carry an attribute. The `UNKNOWN_ROLE` sentinel and its tripwire survive untouched; only their comments move to the past tense.
- **D6 — The break toggle authorizes on two axes and the actor is read from the session only.** `if staff_id != actor.id and actor.role not in {owner, shift_manager}: raise NotAuthorizedError`, evaluated **before any read of the target**, so the generic 403 is not an existence oracle and a body- or query-supplied id can never stand in for "who is asking". `NotAuthorizedError` is reused (`auth/dependencies.py:17-21`) — no new code, no new handler, no new error code. A deactivated or cross-tenant target is a 404 for an elevated caller and unreachable for anyone else. Declined: separate self and elevated routes (four routes and two more walker rows for a one-line comparison); moving the rule into the route table where it is invisible to the service.
- **D7 — Two verbs, `break/start` and `break/end`, both answering the full card, both idempotent by predicate, both classified off the database.** Guarded `UPDATE … RETURNING id` for "did I write" plus one `select(...).execution_options(populate_existing=True)` re-read for what to render — the identity-map trap documented three times and pinned by `test_booking_owner_db.py:747-760`, applied unconditionally so no call site has to reason about whether the row was already in the session. Returns `(bool, StaffUser | None)` rather than F34's four-member `CheckInOutcome`, because a break has no status guard and zero-rows-with-a-live-row has exactly one meaning: F34 needed three values, this needs two, and a fourth member with no reachable cause is not an abstraction. No advisory lock (one column on one row, no cross-row invariant; F51's lock expressed "at least one", which is a different problem). No clock bound and no maximum break. Declined one route with a boolean body.
- **D8 — Two `AuditAction` members, no migration, and the end carries `previous_break_started_at`.** `audit_log.action` is plain TEXT with no CHECK (`0003_auth.py:71-79`) — the fifth block to rely on it. No-ops write no row (F34's D8). A row is written even for a self-toggle: the asymmetric rule saves single-digit volume and costs a condition every future reader of the table must know to interpret it.
- **D9 — Status is a derived function of one nullable column and `occupied` is not on the wire until F36.** `StaffCardStatus` is `{available, break}`, pinned by set equality, so the derivation is total and no input can produce a third value — that is what "structurally impossible" means here, not merely "unreached". Declined pre-adding the literal: it is exactly what `ScheduledMessageKind`, `GatewayCredentialStatus` and `StaffRole`'s own pre-F57 comment refuse, `PaymentStatus`'s departure is written up as a risk rather than a precedent, and F36 must ship the copy, the client union member and the room label regardless — so pre-adding saves one enum line and costs a value that renders as nothing until F36 lands. `break_started_at` **is** on the wire, because a status without a since-when cannot be acted on. Email is not.
- **D10 — `usePoll` is extracted to `apps/manage/src/lib/`, carries F34's unmount fix with its comment, and `BoardSection` is migrated onto it in the same PR — with `BoardSection.test.tsx` passing UNEDITED as the acceptance rule.** F34's D13 named this exact reopening condition and the floor-program review told F34 not to pre-empt it. The hook owns the six mechanisms and the shared constants; it deliberately does **not** own the pointer-hold policy or a `runExclusive` wrapper — but `run` returns a three-valued `TickOutcome` (`void` / `"held"` / `"suppressed"`) rather than the two-valued one an earlier draft claimed, because the shipped loop re-arms a held tick at the **backed-off** gap and arms **nothing** during a mutation, and neither is what a "clean tick" does. Both divergences get their own `usePoll.test.tsx` assertion, because `BoardSection.test.tsx` covers neither and the zero-edit gate alone would have gone green over them. Escape hatch, in order: grow the hook until all 61 of that file's `it(` blocks pass untouched; failing that, revert `BoardSection` to its shipped loop and ship the hook with one caller, recorded for F37. Declined: extracting after F57, which is how four later features each get a private copy of the unmount fix — or none.
- **D11 — `FloorPanel` is a sibling of `BoardSection` composed in `App.tsx`, owning all its own state, on its own poll; a second `NAV` row `"floor"` serves the three roles that have no board.** No floor state above `FloorPanel`, which is what makes a floor tick repaint the cards and nothing else. `BoardSection.tsx` is untouched by the composition — the alternative (widen `board` to five roles, render its bookings half conditionally) cannot be a conditional because the hooks must run, so it would mean splitting a **744**-line component that merged four days ago. Declined widening `board`'s roles: the label «לוח היום» would promise a screen the server refuses, and `BoardSection`'s first fetch would 403 into its terminal state — correctly. The panel renders **after** the board so it cannot push the board's first-load `scrollIntoView` target out of view. **Two polls, not one, for a security reason**: merging the day's bookings into `/manage/floor` would put `customer_name` behind a gate admitting a seamstress, or would need the per-role projection `dashboard/router.py:9-11` already declined. F36/F58/F37 extend this payload rather than add a third loop.
- **D12 — The panel is a second auto-updating surface, so it carries its own SC 2.2.2 pause/resume and idle stop, and D11's live-region rule is inherited whole.** Level A inside a legally binding AA (pre-decided #38) and **axe has no rule for it**, so the named vitest assertions are the sole automated coverage and may not be cut as redundant with the axe row. Two pause controls on the board screen is the answer, not a defect — one control would couple the panels — provided their accessible names distinguish the regions. Declined: no control on the panel relying on the board's (the three floor roles have no board). Status and role carry **words**, never colour alone. The poll never writes into the announced region; the freshness line is visible and not `aria-hidden` (F34's F-1). Focus moves on the **failure** path of the break toggle as well as the success path — the `disabled={disabled || loading}` blur that has now shipped as a bug twice, and that axe walked past both times.
- **D13 — New `floor.*`, `nav.floor` and three `staff.role*` keys in both `he.ts` and `ar.ts` (Hebrew standing in untranslated), and the role word becomes `Record<StaffRole, string>` in `lib/`.** `StaffSection.tsx:99-100`'s ternary would silently label a seamstress «אחראית משמרת» — the frontend form of "widening the enum widens nothing" — and the `Record` type makes a missing member a compile error while an i18n test makes a missing key a red test. No new formatter (`jerusalem.ts:35` already answers the break time with `timeZone: Jerusalem`), no he/ar parity guard invented (F15's Risk 5, inherited).
- **D14 — F51's staff CRUD is not rebuilt; the role `<select>` widens and the ternary is fixed.** `CreateStaffRequest.role: StaffRole` and `UpdateStaffRequest.role: StaffRole | None` are typed as the enum precisely so an unknown value is a 422→400 at the boundary (`auth/schemas.py:65-67`), so both widen with zero backend edits. The last-owner guard keys on the target *leaving* `owner` (`auth/staff.py:187-193`), so demoting the last owner to `seamstress` is refused exactly as demoting her to `shift_manager` is; the self-demote guard and `STAFF_ROLE_CHANGED`'s `details` need no change either. Three frontend edits, four new tests, nothing redesigned.
