# Plan: Feature 57 — Floor roles (reception / sales_assistant / seamstress) + break status + staff cards (Epic E6, floor program iteration 2)

**Status**: **Gate 2 self-approved** 2026-07-31 under Interview Q1 — F57 is not on the enumerated stop-list (`F17, F18, F19, F20, F29, F48`). **The design gate is self-approved too** by the 2026-07-31 ruling: Interview Q2 named exactly two novel interaction patterns for this run — F34's shift board and F42's capacity matrix — and a staff-cards panel assembled from F34's shipped shell is neither. **A design deck nevertheless exists and is binding** (see C8–C11); there is **no prototype and no `design-critic` pass**, deliberately. The corrections C1–C11 below are amended into the spec in Task 0; the spec text is the binding statement of each resolution, this file the reasoning.

**Spec**: `.planning/specs/floor-staff-roles.md` (Gate 1 self-approved 2026-07-31, D1–D14) · **Design**: `.planning/design/screens/floor-staff-roles/design.md` (**self-approved**, §8 P-1…P-8 all resolved, §9 **F-1…F-11**, of which F-10 and F-11 were added by the review) · **Copy**: `copy.md` in that directory — **it EXISTS, is fully authored, and is the authority for every string**: one table per section, **32 keys invented and 4 reused**, `§0`'s ten rules, and three corrections to spec D12/D13. It was written at 17:57, a minute before `design.md`. **Task 1 RECONCILES it; Task 1 does not author it** (**C9**) · **Branch**: `feature/floor-staff-roles` · **Created**: 2026-07-31 · **Revised**: 2026-07-31 (adversarial review, thirteen findings, **all thirteen applied** — two blockers, five major; the sub-proposals not taken are in the spec's *Review findings raised and REJECTED*)

TDD throughout. Local gate per task: `make lint` + `make test` for backend tasks; `make fe-test` + `make fe-build` for frontend ones. **`db`-marked tests are written here and normally execute only on CI** — but see §"Run the db suite locally anyway", which is the single highest-leverage instruction in this document and is what made F34 green on its first CI run.

F57 ships **one migration** (one CHECK swap, one nullable column), **one new router module**, **two `AuditAction` members**, **no new error code**, **no new handler**, **no new table**, **no new rate limiter**, and one structural change: **`usePoll`, extracted from `BoardSection.tsx` and adopted by it in the same PR** (D10).

**Path hygiene.** The repo path contains a space and a `+`. Quote every shell path. And git tracks `backend/` / `frontend/` **lowercase** while the on-disk directories are `Backend/` / `Frontend/`: `git add Backend/…` silently skips modified tracked files. Lowercase every pathspec and verify with `git show --stat`.

---

## Interview and spec rulings this plan is built on

| Ruling | Effect on the build |
|---|---|
| **Q1** — the stop-list is F17/F18/F19/F20/F29/F48; F57 is not on it | Gate 1 and Gate 2 self-approve. The privacy hand-off (spec Risk 10) is discharged to F20 and **re-nagged in the run report**; it does not stop the build. |
| **Q2 / the 2026-07-31 design ruling** — only F34 and F42 are novel | **No prototype, no `design-critic` pass, no user gate.** But a deck was authored anyway and it is **binding**: every `P-` in its §8 carries a resolution, and its §9 raises **three revisions to the spec's own copy and one new behavioural decision** (C8, C10). The deck's own §7.4 states what self-approval costs — SC 2.2.2 is the one thing a human reviewer would have caught here — and discharges it into named frontend tests. |
| **ROLES ruling, 2026-07-31** | `StaffRole` widens to five. **`'sales_assistant'` supersedes pre-decided #24's `'sales'`.** F51's staff CRUD is NOT rebuilt — only its role `<select>` widens. F31's walker default-denies all three new roles everywhere; F57 admits them to its own surface and nothing else. |
| **LANGUAGES ruling, 2026-07-31 / Q3 / pre-decided #47** | Hebrew only. Every new key lands in **both** `he.ts` and `ar.ts`, Arabic values = the approved Hebrew standing in untranslated, **never `""`**. `lng` and `fallbackLng` stay `"he"`. No switcher. |
| **pre-decided #38** | IS 5568 / WCAG 2.0 AA is **legally binding**. D12's pause/idle control on `FloorPanel` and the live-region rule are not polish, and **axe has no SC 2.2.2 rule** — the named vitest assertions are the only automated coverage of a Level A criterion. The deck's **F-8** says this twice as hard, because this gate had no human behind it. |
| **F34's D13 + the floor-program review** (*"do not pre-extract `usePoll` — pre-empting it makes F57 unreviewable"*) | F57 **is** the second caller and **does** extract it. Doing so here is compliance with both documents, not a reversal. D10's zero-edit rule on `BoardSection.test.tsx` is what makes it reviewable. |
| **The floor-program review's F57 section** (four named items) | All four are folded in: the DROP+ADD shape and the `test_migrations.py:154-189` sibling (Task 2), the route-by-route walker assertion (Task 6), the `App.tsx` role-filter test (Task 10), and the "on herself" leak (Task 4). |

---

## What moved since the spec was written

The spec was written today against this tree, so **almost nothing moved in the code** — the opposite of F34's situation. What did move is that **a design deck landed after the spec, the same afternoon**, and it revises three of the spec's own strings.

### Migrations — `alembic heads` reads **`0014 (head)`**, exactly as the spec predicted

```
$ cd "<repo>/Backend" && uv run python -m alembic heads
0014 (head)
```

`Backend/migrations/versions/` holds `0001`…`0014`; `0014_booking_check_in.py` is F34's, merged as PR #32. **So today F57's migration is `0015` revising `0014`.** D3's build-time rule stands and is exactly why this is safe: **re-read `alembic heads` at build time and revise whatever HEAD then is.** Do not hardcode `0015`/`0014` off this paragraph either if another migration lands first. Every assertion in this plan keys to *"after this feature's migration"*, never to a revision number.

### The design deck postdates the spec and supersedes parts of D13

`.planning/design/screens/floor-staff-roles/design.md`, written 2026-07-31 17:54, after the spec. It is untracked and lands in this PR. It obeys the spec's D1–D14 and restates none of them — but its §9 raises four things a plan cannot ignore, all folded in below as **C8**, **C9**, **C10**, **C11**. Its §8 resolves eight `P-` decisions, of which four bind the build directly: **P-1** one `Card` containing a divided `<ul>`, one column at every width, never a grid of cards; **P-2** the role is muted words and the card's single `Badge` is the status; **P-4** no hoisting of her own card, marked instead with F51's shipped «זו את» (`he.ts:209`); **P-5** the brief's 🟢/🟡/🔵 ship as **words**, never glyphs.

### Citations that still hold exactly — ✅ do not re-verify

- ✅ `models/constants.py:9-14` — `StaffRole` with its two members and the *"Reception/seamstress/sales join when E6-proper gives them their first consumer"* comment, verbatim.
- ✅ `0011_staff_roles.py:15-25` — the `ADD CONSTRAINT staff_users_role_check CHECK (role IN ('owner', 'shift_manager'))` and the comment claiming ADD validates existing rows; `:28` the `IF EXISTS` downgrade.
- ✅ `auth/dependencies.py:17-21` (`NotAuthorizedError`, *"one body for every unadmitted role, so a probe cannot learn which roles exist"*), `:40-52` (`RoleGate`'s docstring, including *"Applied router-level as the default posture and per-route to tighten (both gates run…)"* and the walker sentence), `:54-55` (`allowed_roles` built from `.value`), `:57-62` (the raise), `:65-66` (`require_role(*allowed)` — **already varargs, so `require_role(*StaffRole)` needs no change to this file**).
- ✅ `auth/staff_router.py:1-31` — the owner-only-at-router-level docstring; `:61-64` the router with `require_role(StaffRole.OWNER)`.
- ✅ `dashboard/router.py:1-40` — every decision F57's module docstring copies: router-level gate, tenant from `get_current_tenant(request)` never `StaffContext.tenant_id` (`:17-26`), the fourth local `_no_store` copy (`:28-30`), no rate limiter (`:32-36`), real HTTP verbs (`:38-39`). `:52-56` `_no_store`; `:59-61` the service getter; `:64-70` the router; `:75-80` the one route. **80 lines total — that is the size of `app/floor/router.py`.**
- ✅ `db/repositories/staff_users.py:9-13` (the redundant-`tenant_id` defence-in-depth docstring), `:26-33` `by_id` filtering `deleted_at`, `:35-43` `list_live` with the *"so the founding owner is first"* reason (which is also the deck's **P-4** citation).
- ✅ `models/staff_user.py:11-20` — nine columns, every one declared as `mapped_column`, `role` a plain `Text` with a `server_default` of `'owner'`. **No SQLAlchemy `Enum`, so widening `StaffRole` needs no ORM change** — but the new column does (Task 2).
- ✅ `test_migrations.py:43-57` — `_ROLE_CHECK`, `_ADD_ROLE_CHECK` (0011's ALTER verbatim, with the comment saying why it is not a paraphrase), `_DROP_ROLE_CHECK` (deliberately no `IF EXISTS`), `UNKNOWN_ROLE`. `:73-93` `test_staff_role_check_pins_the_role_set` with both probes rolled back. `:96-151` the app-role promote test. `:154-189` `test_adding_the_role_check_validates_existing_rows` — the shape Task 2 copies, `probe(seeded_role) -> bool`, `DBAPIError` with `assert _ROLE_CHECK in str(exc)`. `:192-220` `test_migration_0011_round_trips`, which downgrades to `"0010"` (see **C6**).
- ✅ `test_staff_role_gating.py:44-53` (route-table **templates**, with the comment saying why a literal `/manage/staff/<uuid>` would never match), `:69-79` `OWNER_ONLY`, `:81-91` the `UNKNOWN_ROLE` sentinel + tripwire, `:93-109` `UNGATED_ALLOWLIST` with its three reasons, `:117-126` `_leaf_routes`, `:129-136` `_gate_role_sets`, `:142-162` the default-deny walker, `:165-181` `test_gates_admit_only_known_roles`, `:184-212` `test_route_table_matches_the_permission_matrix`, `:243-247` `test_gate_admits_listed_roles`, `:292-321` `_client`, `:324-351` the shift-manager HTTP walk, `:362-374` the unknown-role walk, `:377-397` the literal contract test whose role-name scan **iterates `StaffRole`**.
- ✅ `App.tsx` — `SectionKey` is a **ten**-member union at `:18-28` (F34 added `"board"`); `const ALL = ["owner", "shift_manager"]` at `:30`; the cosmetics comment `:32-41`; `interface NavItem {key, labelKey, roles}` at `:42-46`; `NAV` at `:48-72` with the board row at `:66`; `useState<SectionKey>("dashboard")` at `:83`; `reachable` at `:114`; `activeKey`'s `reachable[0]?.key ?? section` at `:128-130`; the ten render branches at `:145-154`. **`Staff` carries `id`** (`api.ts:69-74`), so `<FloorPanel selfId={staff.id} role={staff.role} />` compiles.
- ✅ `BoardSection.tsx` — every line citation in spec D10 and in the deck holds: constants `:10-27`, `terminalOf` `:32-47`, `schedule` — "THE ONE ARMING SITE" — `:108-124`, `armIdle` `:126-135`, the pointer hold in `tick` `:219-242`, **the unmount fix `:248-261`**, `visibilitychange` `:263-281`, idle listeners `:283-296`, the `activeElement`-guarded stranded-row focus rescue `:298-306`, the `rowError` focus rescue `:308-319`, the first-load `scrollIntoView` `:321-333`, `pause`/`resume` `:335-355`, `retry` `:357-361`, `mutate` `:363-421` with the `.finally()` re-arm at `:411-420`.
- ✅ `StaffSection.tsx:99-100` the two-valued `roleWord` ternary; `:242-243` and `:373-374` the two hardcoded `<option>` pairs; `:304-305` the badge under *"The WORD carries the role; the colour never does"*; `:80-92` the heading-fallback focus pattern the deck's §7.2 reuses.
- ✅ `api.ts:362` `export type StaffRole = "owner" | "shift_manager"`; `:368` / `:395` / `:406` its three consumers; `:73` `Staff.role: string`; `:629-634` `checkInBooking` / `undoBookingCheckIn`, the wrapper shape Task 10 copies.
- ✅ `lib/` holds exactly `booking.tsx` and `jerusalem.ts`; `jerusalemTime` at `jerusalem.ts:35`. `__tests__/` holds sixteen files including `Nav.test.tsx` and `i18n.test.ts`.
- ✅ `Nav.test.tsx:71-77` `navItems()` uses `queryAllByRole` (so an empty nav is an assertion, not a throw); `:84-89` the owner's **ten**; `:91-101` the shift manager's **eight**; `:103-114` the out-of-enum role's zero.
- ✅ `i18n.test.ts` — one `describe` block per feature (`F15`, `F51 staff`, `F52 dashboard`, `F17 gateway`), each with a "carries the whole copy deck" case and an "nth nav item beside the nested nav object" case. F57's block is the fifth.
- ✅ `he.ts` is 539 lines, `ar.ts` 305, both flat dotted literals per feature block. `staff.roleOwner` «בעלת הבוטיק» `:207`, `staff.roleShiftManager` «אחראית משמרת» `:208`, **`staff.selfMarker` «זו את» `:209`** (the deck's P-4 key, reused not re-declared). F34's `board.*` block runs **`:459-537`** (`board.reload` `:529`, `board.error.transitionInvalid` `:537`), and **`board.pauseAria` = «השהיה — עדכון הלוח» (`:481`)** — the exact shape the deck's F-2 requires of `floor.pauseAria`. **`board.idleStopped` (`:488`) is byte-identical to `copy.md`'s proposed `floor.idleStopped`** — see the design-deck reconciliation in Task 1.

### Numbers and citations in the source documents that are off — none changes a decision, all are amended in Task 0

⚠ **The ✅ list above says "do not re-verify". These are the ones that did not survive verification** — an adversarial review found five the earlier audit missed. Fixed in Task 0; listed here so a reader who trusts the ✅ list knows exactly where its edge is.

- **`main.py:463-465`** for the `DomainNotFoundError` → 404 handler, cited **twice** in the spec (D6 and the API-surface error table). The handler is at **`main.py:757-759`**. Task 4 below silently used `757-758` while the spec kept the wrong number, so the spec would have shipped wrong.
- **spec `:14`** — *"a shift manager is admitted to every `/manage` route except staff management and the payment gateway"*. `OWNER_ONLY` (`test_staff_role_gating.py:69-79`) also contains **`TERMS_PUBLISH`** (`POST /manage/terms`). Nine routes, not eight.
- **spec `:53`** — *"`App.tsx` is a **nine**-member `SectionKey` union"*. It is **ten** (`App.tsx:18-27`), which is the same number C11 corrects in the deck.
- **`board.*` in `he.ts` runs `459-537`, not `458-529`.** `board.reload` is at `:529` but `board.error.transitionInvalid` is at `:537`.
- **"F34's 59 assertions" in `BoardSection.test.tsx`** — the file has **61 `it(` blocks** and **162 `expect(` calls**. 59 is the number of **tests F34 added** per its LOOP-STATE shipped note, not an assertion count. The zero-edit gate does not depend on the number, but a builder counting to 59 to check the gate held would get a false red.

### Three further numbers, from the original audit

- The spec calls `BoardSection.tsx` **710 lines**; it is **744**. Every line citation into it still resolves exactly, so this is cosmetic. It matters only in that D11's argument — *"splitting a 710-line component that merged four days ago"* — is if anything stronger.
- Six routers carry `prefix="/manage"` exactly today (`boutique`, `catalog`, `booking/owner_router`, `auth/staff_router`, `dashboard`, `payments`), so **the floor router is the seventh** and spec D4 is right. `test_dashboard_api.py:49-51`'s comment *"SIX routers now mount prefix=/manage"* becomes stale on merge; it is a historical note in another feature's file and F57 does not chase it.
- The deck's §0 called floor **"an eighth section"**, and `copy.md:29` called `nav.floor` the **eighth** nav item. `App.tsx` already carries **ten** `NAV` rows — see **C11**. Both corrected.

---

## Eleven corrections — recorded, resolved, amended into the spec in Task 0

The spec is binding and D1–D14 are **not** re-litigated. These are places where the documents are under-specified against the tree, or disagree with each other, in a way a builder cannot proceed through without picking a side. Every resolution is the smaller edit.

### C1 — `test_gate_admits_listed_roles` must gain a **new case**, not three roles

The spec's Testing section says *"`test_gate_admits_listed_roles` gains the three roles"*. That test (`test_staff_role_gating.py:243-247`) is a **RoleGate unit test** that builds `require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)` and asserts it admits `("owner", "shift_manager")`. Adding `"reception"` to that loop would assert something **false and dangerous** — that the two-role gate admits a floor role.

**Resolution:** the existing case is untouched. A **second** case asserts that `require_role(*StaffRole)` — the shape D4 puts on the floor router and nowhere else — admits all five. Declined: widening the existing assertion (it inverts the meaning of the shipped gate); deleting it (it is the only unit-level proof that a narrow gate stays narrow).

### C2 — `test_gates_admit_only_known_roles` needs **zero** edits, and that is coverage, not a gap

`:165-181` derives `known = {role.value for role in StaffRole}` from the **live enum** and asserts every discovered gate's `allowed_roles <= known`. Widening the enum widens `known` in the same breath, and the floor router's `require_role(*StaffRole)` passes by construction.

**Resolution:** recorded as free coverage so nobody "adds the three roles" to it — a no-op edit that would make a derived test look hand-maintained. Same class as `test_the_not_authorized_contract_is_pinned_by_literal` (`:396-397`), which already iterates `StaffRole`.

### C3 — the two HTTP walks need a **`floor=` kwarg on `_client`, wired asymmetrically**

The spec says *"`FLOOR_ROUTES` added to the two HTTP walks at `:340` and `:371`"* and stops there. But `_client` (`:292-321`) wires fakes **selectively and on purpose**: `boutique_service` always, `catalog` **only when a test needs a 2xx**, and the comment at `:311-315` says why — `test_unknown_role_is_403_on_every_gated_route` *"depends on the real (ambient-env) service never being reached, so a decoy gate that carries `allowed_roles` without raising blows that test up instead of quietly passing"*. Wiring a floor fake unconditionally would silently delete exactly that proof for the floor router — the one router in the codebase whose gate is spelled `*StaffRole`, i.e. the one where a decoy gate is most consequential.

**Resolution:** `_client` gains `floor: FakeFloorService | None = None`, set on `app.state.floor_service` only when passed. The shift-manager walk passes one; **the unknown-role walk deliberately does not**, and carries a comment saying so in the catalog's own words.

### C4 — `FLOOR_OPEN` uses route **templates**; `FLOOR_ROUTES` uses **concrete URLs**

`test_staff_role_gating.py:46-49` is explicit: the structural walkers read `route.path`, so their tables must be templates — never a literal uuid. The HTTP walks issue real requests and need concrete URLs. F57's break routes carry `{staff_id}`, so both spellings exist.

| Table | Lives in | Spelling |
|---|---|---|
| `FLOOR_OPEN` (D5's walker assertion) | `test_staff_role_gating.py` | `("POST", "/manage/floor/staff/{staff_id}/break/start")` — **template** |
| `FLOOR_ROUTES` (wiring + HTTP walks) | `test_floor_api.py`, imported by the gating module | `("POST", f"/manage/floor/staff/{STAFF_ID}/break/start", None)` — **concrete** |

A concretely-spelled `FLOOR_OPEN` fails on the `missing` assertion, so the mistake is caught rather than silent — but catching it on CI costs a round trip.

### C5 — the "seventh router" claim is verified; the stale sixth-router comment is not F57's to fix

Six routers carry `prefix="/manage"` exactly. `app/floor/router.py`'s docstring says *seventh*; `test_dashboard_api.py:49-51` is left alone and the staleness is pre-empted in §"What could go wrong in review".

### C6 — a leftover floor-role row reddens **three** tests, in **two** files, and the rule is about commits rather than about order

**The rule, and it is the whole of C6:**

> **No F57 test, in any file, may leave a COMMITTED row holding `reception`, `sales_assistant` or `seamstress`.** Roll every such probe back, the `:78-93` shape (`trans = await conn.begin()` … `await trans.rollback()`).

**It is cross-file, not within-file.** `migrated_db` and `app_role_url` are `scope="session"` (`conftest.py:82`), so one container is shared by every db module — `test_migration_0011_round_trips`'s own docstring says so — and pytest collects files **alphabetically**, which puts **`test_floor_db.py` before `test_migrations.py`**. An earlier draft of this correction reasoned only about definition order inside `test_migrations.py` and therefore named only two victims. There are three:

| Red | Why |
|---|---|
| `test_migration_0011_round_trips` (`:192-220`) | `downgrade(cfg, "0010")` unwinds F57's migration first, and its `downgrade()` re-adds the **two-value** CHECK, deliberately able to fail (D1) |
| `test_migration_0014_round_trips` (`:475-499`) | same statement, same reason |
| ⚠ **`test_adding_the_role_check_validates_existing_rows` (`:154-189`)** — **the one the earlier draft missed** | nothing to do with round-trips. It DROPs the constraint, inserts a probe row and re-adds **0011's two-value `_ADD_ROLE_CHECK` verbatim** (`:49-52`); its first assertion is `assert asyncio.run(probe(StaffRole.OWNER.value)) is True`. One committed `reception` row anywhere in `staff_users` makes that ADD fail and flips it to `False` — a red about a constraint that has nothing to do with breaks, in a file that never mentions F57 |

**And where the rule collides with a test's own needs, the SEED ROLE gives — not the rule.** Task 8 requires a **forced interleave** (holding the loser's `tenant_session` open across the winner's whole transaction, *because exiting `tenant_session` is the commit*, `db/tenant.py:25`) and an **RLS probe** needing a persisted second-tenant row. Both commit by construction, so neither can roll back. **Resolution: seed those rows as `owner` / `shift_manager`.** Break toggling is role-independent at the repository layer and RLS isolation is about `tenant_id`, not `role` — the role gate is `test_floor_service.py`'s and `test_staff_role_gating.py`'s job, and nothing in Task 8 asserts anything about it. Then nothing in `test_floor_db.py` needs rolling back at all.

Task 2's probes (the widened-CHECK sibling, the downgrade's honest failure, the app-role promote extension) **do** hold floor roles and **do** roll back; a one-line comment at `:106-110` records that the deliberate leftover row may hold **only** `owner` or `shift_manager` after F57.

Declined: moving the round-trips (last-in-file by their own documented rule); adding leniency to F57's downgrade (D1 says the loud failure is the point); a per-module truncate fixture (a new fixture on a shared session container, to solve a problem choosing a seed value solves for free).

### C7 — `FloorPanel`'s empty state is unreachable, and the plan says what ships anyway

The spec (`:589`) calls the empty floor *"impossible in practice"*. The deck's **F-empty** row resolves it: `<EmptyState title={floor.empty} />` inside the `Card`, **no body and no CTA**, and the freshness row still renders — *"a panel that has stopped updating must still be able to say so"*. One line, one existing component (`BoardSection.tsx:4` already imports `EmptyState`), no test beyond "it does not crash on `[]`".

### C8 — the deck revises two of the spec's proposed Hebrew strings, and both revisions are correct

The deck's §9 **F-2** and **F-3** are copy corrections to spec D13, raised there explicitly *"rather than folded in silently, because a reviewer diffing the deck against D12 will otherwise read it as drift"*:

| Key | Spec D13 proposed | **Deck ships** | Why |
|---|---|---|---|
| `floor.pauseAria` | «השהיית עדכון הצוות» | **«השהיה — עדכון הצוות»** | The visible label is «השהיה»; «השהיית» is a different word form, so the accessible name does **not contain** the visible label — **WCAG 2.5.3 label-in-name**, and a speech-input user saying "השהיה" matches nothing. The shipped `board.pauseAria` is «השהיה — עדכון הלוח» (`he.ts:481`), i.e. the deck's version is the shipped shape. |
| `floor.breakSince` | «בהפסקה מ־{{time}}» | **«מאז {{time}}»** | The `Badge` directly above already reads «בהפסקה». Repeating it spends 295px of a 375px screen saying one thing twice and makes two signals look like two facts. |

**Resolution: the deck wins on both, and the spec's D13 table is amended to match.** These are the only two places the deck contradicts the spec's text, and in both the deck is applying a criterion the spec did not check. `floor.resumeAria` follows F-2's shape symmetrically: «חידוש — עדכון הצוות».

### C9 — **`copy.md` EXISTS and is authoritative** — an earlier draft of this plan said it did not, and Task 1 would have overwritten it

⚠ **This correction replaces the opposite claim.** The directory holds two files:

```
-rw-r--r--  27782  Jul 31 17:57  copy.md
-rw-r--r--  58594  Jul 31 17:58  design.md
```

`copy.md` **predates** `design.md` by a minute and is a finished deck: ten numbered §0 rules, one table per section, a §7 register check, **"32 keys invented, 4 reused"**, and every one of the corrections an earlier draft of this plan credited to itself — `floor.pauseAria` «השהיה — עדכון הצוות» (`:51`), `floor.resumeAria` (`:53`), `floor.breakSince` «מאז {{time}}» (`:69`), `floor.error.notFound` (`:120`). **The whole directory is untracked (`git status` → `??`), so there is no git copy to recover from an overwrite.**

Three concrete consequences of the wrong claim, each fixed:

1. **The key lists disagreed on one key.** An earlier Task 1 and spec D13 both named `floor.outage`. `copy.md:108` deliberately **drops** it and reuses the shipped `staff.loadFailed` (`he.ts:205`) under §0 rule 8 — a **third** copy correction to D13, where C8 records only two. A builder following the old Task 1 would have shipped a duplicate key the deck rejects by name. **Resolved by the deck**, and `design.md` §4 F-fail is corrected to match (see the design-deck reconciliation in Task 1).
2. **Task 1's own acceptance grep failed against the real file.** It required `grep -n "השהיית\|בהפסקה מ־" copy.md` to return nothing; the shipped file returns **2** — at `:51` and `:69`, in the ⚠ prose that **quotes the rejected spec strings in order to explain why they were rejected**. The gate is scoped to the `he` column, or dropped.
3. **C11's fix was half done.** `design.md:14` is not the only stale count: `copy.md:29` also calls `nav.floor` *"The eighth console nav item"*.

**Resolution: Task 1 becomes a RECONCILIATION, not an authoring pass.** Verify `copy.md`'s 36 rows against spec D13, correct the two decks where they disagree with each other and with the tree, and correct the two "eighth" counts. **`copy.md`'s table is the canonical key list** — the plan's prose is not. Declined: re-authoring it "to be sure" (it destroys 27 KB of self-approved copy that is already better than a transcription, and it is a second spelling of a deck that already exists — the exact defect §0 rule 8 forbids inside the console).

### C10 — the deck adds one behavioural decision and one error string the spec does not have

**§8 P-6 — a break toggle that answers 403 is TERMINAL**, putting the whole panel into the F-403 state exactly as a failed tick would. The spec's D7 error table lists the 403 without saying what the panel does with it. The deck's reasoning: `usePoll.fail(error)` classifies a mutation's error on the same `{401,403}` rule the ticks use (spec D10's contract), so the alternative — an in-card alert plus a loop that keeps polling with a role the server just refused — is the panel disagreeing with itself for up to five seconds and then doing the same thing anyway. The realistic cause is a mid-shift demotion between the last tick and the tap.

**And its converse: a 404 is NOT terminal** and stays an in-card alert (state **F-actfail**) — *"a colleague vanishing is a fact about her, not about the viewer's access."* That needs a key the spec's D13 list does not have: **`floor.error.notFound`**, in the `text-danger` fix-this register, **inside the card** because a panel-level error names no colleague.

**Resolution: both ship, and both go into the spec's D12/D13 and the API-surface error table.** `floor.error.notFound` joins `copy.md` and both i18n files.

### C11 — the deck calls floor "an eighth section"; it is the **eleventh**

`App.tsx:18-28` is a ten-member `SectionKey` union and `NAV` (`:48-72`) has ten rows — F52 added `dashboard`, F17 added `gateway`, F34 added `board`. `i18n.test.ts` already has blocks calling F51's the "seventh nav item", F52's the "eighth" and F17's the "ninth".

**Resolution:** `SectionKey` gains an **eleventh** member and `NAV` an **eleventh** row; F57's `i18n.test.ts` block says "the eleventh nav item". **Two** stale counts are corrected in Task 1, not one: `design.md:14` ("an **eighth** section") **and `copy.md:29`** ("The **eighth** console nav item"). The spec's own *"nine-member `SectionKey`"* is a third, corrected in Task 0. **Nothing about the deck's design changes** — it is a count, not a layout.

All eleven are amended into the spec in **Task 0**, in the same PR — the F15 / F34 Task-0 precedent for a plan-phase spec amendment.

---

## Scope fence — read this before every task

**F57 ships three roles, one nullable timestamp, one read, two toggles, one panel and one hook.** It is the second thing to attach to F34's board and it attaches nothing else.

| Not in F57 | Whose |
|---|---|
| Fitting rooms, occupancy, the `occupied` status, room labels | **F36** — extends this payload and widens `StaffCardStatus` in the PR that gives `occupied` a writer (D9). The deck's §2.3 pre-books it the `neutral` variant so **no new colour** is added then either |
| Dispatch, take-next, push-assign, the waitlist panel | **F58** — on this same payload, no third loop |
| SOS, the full-screen overlay, the 30s escalation | **F37** |
| Queue tickets, QR self-check-in, live position, the public wall board | **F33**, **F59** |
| Break history, break duration reporting, "who was on a break when" | nobody — no table (D2); the two audit rows are the only record and nothing reads them |
| A maximum break length, an auto-end sweep, a worker tick | nobody — nothing schedules a break's end (D7) |
| On-shift / off-shift marking, a published roster | **F40** (pre-decided #33). "Live status" here means available-or-on-a-break, never rostered |
| **Rebuilding F51's staff CRUD** | nobody — three frontend edits and four test cases, and that is the whole of D14 / deck P-8 |
| Any per-role narrowing of an existing route | nobody — `OWNER_ONLY` is untouched |
| A staff avatar, photo, phone number or **email** on the card | nobody — the card is a name, a role and a status |
| A two-column card grid, a summary line, a hoisted self-card, emoji status dots | nobody — deck **P-1**, **P-3**, **P-4**, **P-5**, each resolved with its upgrade path recorded |
| A frequency picker, a second poll interval, any new constant | nobody — deck **P-7**; the three constants come from `usePoll` |
| A he/ar parity guard | Risk 7 / deck F-5, inherited from F15 |
| The `/manage/**` Playwright interception harness | **F58** |
| The privacy-notice entry for `break_started_at` | **F20** (`spec_gate: user`) — Risk 10 |

If a task's diff grows a room, a ticket, an alert, a roster row, a colour token or a third poll target, it has left F57.

---

## Run the db suite locally anyway — this is the highest-leverage instruction in this plan

The run's standing constraint is "no Docker locally", and `tests/conftest.py:81-94` fails the whole db suite with `DOCKER_HELP` when the daemon is down. F34's builder did not accept that, and its shipped note records what it bought: **all three gating jobs green on the first CI run**, three pinned literals **captured rather than guessed**, one real test bug found and fixed locally, and two mutation checks proving the concurrency tests were not vacuous.

**F57 has exactly the same deparse hazard, on its headline assertion.** D3 requires `pg_get_constraintdef('staff_users_role_check')` pinned byte-identical after this feature's migration. Postgres does **not** store the text you wrote: it deparses `CHECK (role IN ('a','b','c'))` into `CHECK ((role = ANY (ARRAY['a'::text, 'b'::text, 'c'::text])))`. Transcribing the migration's own SQL into that assertion pins **nothing** and reddens CI on the first run — verbatim what F34's note says happened to the naive reading there.

**Verified on this machine, 2026-07-31:**

```
$ postgres --version   →  postgres (PostgreSQL) 16.14 (Homebrew)     # same major as postgres:16-alpine
$ command -v initdb pg_ctl psql   →  all three on PATH
$ command -v docker   →  /opt/homebrew/bin/docker                    # CLI present; the DAEMON is the question
```

**Do this, in order:**

1. **Try Docker first.** `make test-db`. If the daemon happens to be up, testcontainers just works and nothing below is needed.
2. **Otherwise stand up a throwaway cluster OUTSIDE the repo** — never inside it, or the data directory lands in `git status`:
   ```
   PGDIR="$TMPDIR/f57-pg"            # or the session scratchpad; NOT the repo
   initdb -D "$PGDIR" -U postgres
   pg_ctl -D "$PGDIR" -o "-p 55432 -k $PGDIR" -l "$PGDIR/log" start
   createdb -h "$PGDIR" -p 55432 -U postgres boutique
   ```
3. **Point the session fixture at it with a LOCAL, UNCOMMITTED edit** to `tests/conftest.py:81-94` — `postgres_url` is session-scoped in a conftest, so a plugin cannot override it. Yield `postgresql+asyncpg://postgres@127.0.0.1:55432/boutique` and skip the `_docker_running()` gate.
4. `make test-db`. Read every failure. **Capture the deparsed literal** by running `SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'staff_users_role_check'` against the migrated database and pasting the result into the test — do not type what you think it says.
5. **Revert the conftest edit and tear the cluster down before committing.** `git diff --stat backend/tests/conftest.py` must print nothing, and `pg_ctl -D "$PGDIR" stop && rm -rf "$PGDIR"`.

Also worth the ten minutes, the other F34 precedent: **one mutation check per concurrency claim** — delete `populate_existing=True` from the re-read and confirm the racing test in Task 8 turns red **and nothing else does**. A concurrency test that stays green with its mechanism removed proves nothing.

⚠ If step 3 is skipped, expect a first CI red on a test bug and budget for it (`.memory/boutique-ci-first-run-surprises.md`). Check `continue-on-error` on the job before believing a red.

---

## Task 0 — This plan, and the eleven spec amendments
`.planning/plans/floor-staff-roles.md` (this file), `.planning/specs/floor-staff-roles.md`

- Amend the **Testing** section's `test_gate_admits_listed_roles` bullet: a **new** five-role case, the existing two-role assertion untouched (**C1**); and record that `test_gates_admit_only_known_roles` and `test_the_not_authorized_contract_is_pinned_by_literal` need **zero** edits and why (**C2**).
- Amend **D5** with the `_client(floor=…)` asymmetry (**C3**) and the templates-vs-concrete table (**C4**).
- Amend **D3** with the observed HEAD: *"`alembic heads` reads **0014** as of 2026-07-31, so the next number is 0015 — and this sentence is not the source either; re-read `alembic heads` at build time."*
- Amend **D1**'s trap paragraph with the collection-order mechanism: which two round-trip tests go red, why F57's `downgrade()` is the first statement they run, and that the promote-test extension must roll back (**C6**).
- Amend the **Frontend changes** table's `FloorPanel` row with C7's `EmptyState` ruling.
- Amend **D13**'s copy table: `floor.pauseAria` → «השהיה — עדכון הצוות», `floor.resumeAria` → «חידוש — עדכון הצוות», `floor.breakSince` → «מאז {{time}}» (**C8**), and add **`floor.error.notFound`** (**C10**).
- Amend **D12** and the **API surface** error table with **P-6**: a break toggle's 403 is terminal; a 404 is an in-card alert (**C10**).
- Amend **D11** and the **Frontend changes** table: `SectionKey` gains an **eleventh** member, `NAV` an eleventh row (**C11**).
- Add a **Design** line to the spec header pointing at the deck, and record that its §8 P-1/P-2/P-4/P-5 bind the panel's layout.
- Amend **D5**'s walker snippet: the classifier is the **intersection** of a route's gates, never `any(...)` over them (see the assertion table in Task 6). Amend **D10**'s hook contract: `run` returns a three-valued `TickOutcome`, and the *"byte-identical, zero API"* claim is deleted as false.
- Amend **D1**'s trap to the cross-file, commit-based rule and its **third** victim (**C6**), and the **Testing** section's `test_floor_db.py` bullet to seed `owner` / `shift_manager`.
- Amend **D13**: `floor.outage` is **not shipped**; `staff.loadFailed` is reused, and `copy.md`'s table — not the spec's prose — is the canonical key list.
- Correct the stale numbers and citations: `BoardSection.tsx` is **744** lines; the floor router is the **seventh** with `prefix="/manage"` exactly; `main.py:463-465` → **`757-759`** in **both** spec locations; `POST /manage/terms` joins the `OWNER_ONLY` list at `:14`; "nine-member `SectionKey`" → **ten**; "59 assertions" → the **61 `it(` blocks**.
- **Done when**: all eleven corrections plus the review's amendments are in the spec, the spec carries a *Review findings raised and REJECTED* section, and this file is committed. No code, no tests.
- Commit: `docs(planning): F57 implementation plan — Gate 2 self-approved`.

## Task 1 — Reconcile the two decks with each other and with the tree
`.planning/design/screens/floor-staff-roles/design.md`, `.planning/design/screens/floor-staff-roles/copy.md`

⚠ **`copy.md` EXISTS and is fully authored** (**C9**). **Do not re-author it.** It is untracked, so an overwrite is unrecoverable, and it is already the canonical key list — **32 invented, 4 reused**, with C8's two corrections and C10's `floor.error.notFound` already in it. This task is a reconciliation pass: the two decks disagree with each other in three places, and each disagreement is one a builder cannot proceed through.

**1 — The outage key.** `design.md` §4 F-fail names `floor.outage`; `copy.md` §5 ships **no such key** and reuses the shipped `staff.loadFailed` (`he.ts:205`, «לא הצלחנו לטעון את רשימת הצוות כרגע.»). One deck declares a key the other never writes into `he.ts` / `ar.ts` — an orphan key or a red `i18n.test.ts` block, and neither deck is internally inconsistent so review-by-reading catches neither. **`copy.md` wins**: it is the same sentence about the same subject, and F-9 already records that this panel carries ten duplicates against its will.
  - Edit `design.md` §4 F-fail to name **`staff.loadFailed`**.
  - Add a numbered **§9 F-10** recording the substitution — and **answer the namespace objection it raises**, because F-9 refuses to reuse `board.*` on the grounds that those keys are *"namespaced to a screen three of the five roles cannot open"*, while `staff.*` is F51's **owner-only** section and is therefore strictly more restricted. The two decisions are the same principle pointed in opposite directions unless the difference is stated: `board.*`'s ten strings would have been read **from a `board.` prefix on a screen with no board**, whereas `staff.loadFailed` is one string whose **subject is the staff list itself** — the namespace names the payload, not the screen, and every one of the five roles reads that payload. This is the PR that sets the precedent for where F37, F41, F42 and F59 put their shared strings, so the reasoning has to be on the page.
  - Spec D13 and the Frontend-changes table are corrected in Task 0.

**2 — The `{{name}}` bidi rule, which three places state three ways.** `design.md` §2.1 and §7.4 are emphatic: **bare `<bdi>`** on display names, because *"`dir="ltr"` on a Hebrew name is itself a bidi defect and it looks deliberate"*. `copy.md:101` agrees. But `copy.md` §7's register table claims *"every interpolated value (`{{time}}`, `{{minutes}}`, `{{name}}`) is a single run, so `isolateLtr` is reused unchanged"* — and `isolateLtr` (`lib/booking.tsx:32-46`) emits **`<bdi dir="ltr">`**, which on «נועה לוי» is exactly the banned defect. It is also the only helper that exists, so "reused unchanged" points a builder straight at it. Resolve **per interpolation**:
  - `{{time}}`, `{{minutes}}` → `isolateLtr` (a numeric run; `<bdi dir="ltr">` is correct).
  - **`{{name}}` → bare `<bdi>`**, which needs either a two-line `isolateBidi(text, value)` sibling in `lib/booking.tsx` or a `<Trans>`. Name whichever in `design.md` §6's component table beside the cue region, which is currently silent on how the cue renders a name.
  - Record in §9 that **F34's shipped cues isolate nothing at all** — `BoardSection.tsx:385-391` interpolates `customer_name` into a plain string and `:138` does the same with `{{minutes}}` — so F57's isolation is a deliberate divergence from the board, not drift. There is **no test named for this**, unlike the SC 2.2.2 row, and IS 5568 makes it a legal surface.

**3 — Two stale "eighth" counts, not one** (**C11**): `design.md:14` and **`copy.md:29`**. Both → **eleventh**.

**Also in this task, each one line:**

- `design.md` §1: a note above the ASCII block that **the diagrams are drawn LTR for legibility in a Markdown file** and the rendered panel is RTL, so **inline-start is the physical right and inline-end is the physical left**. There is no prototype and no `design-critic` pass, so that block is the sole visual source; a builder implementing the drawn order ships a mirrored panel that passes axe and every named assertion and reads wrong to the only users who will see it.
- `design.md` §2.2: **answer the sighted-viewer case**, which the deck argues at length for a screen reader and never argues for eyes — for an elevated viewer every card carries an identical «להפסקה» and the person is carried only in the accessible name.
- `design.md` §4: **say whether the freshness row (and therefore the pause control) renders in F-load and F-fail.** F-empty states it explicitly precisely because it is not obvious; F-load says "no freshness row" and F-fail is silent, while `usePoll` is armed and backing off in both.
- `copy.md` §5 `floor.idleStopped`: **name the region**, the way the aria-labels already do. `board.idleStopped` (`he.ts:488`) is **byte-identical**, both go into a `role="status"` region, and both windows are reset by the same global interactions (F-4), so a screen-reader user hears one sentence twice with nothing saying which surface stopped. `floor.paused` already names «רשימת הצוות»; only `idleStopped` changes. Widen **F-4** to record the auditory half.
- `copy.md:7` and `:51`: the rejected `floor.pauseAria` string is spec **D12**'s (`:457`), not D13's — `design.md` F-2 cites it correctly. (`:69`'s D13 citation for `floor.breakSince` **is** right; D13's table carries that one.)
- `copy.md:7`: it claims all three of its corrections are recorded in `design.md` §9. Two are (F-2, F-3); the `staff.loadFailed` substitution becomes the third once F-10 exists.
- `design.md` §9: the findings run F-1…F-7, **F-9, F-8** — reorder.
- `design.md` §5: `ConsoleShell.tsx:83` → **`packages/ui/src/components/ConsoleShell.tsx:84`** (the file is not in `apps/manage`).

**No other design content changes.** The decks are self-approved; rewriting them is rewriting evidence. Everything above is a contradiction, a stale count, a wrong citation, or a decision the deck left as a gap.

- **Done when**: no key is named in one deck and absent from the other; both "eighth" counts are gone; §9's findings are in order and F-10 exists; `copy.md`'s row count still reads **32 invented / 4 reused** (F-10 removes no key and adds none).
- Commit: `docs(design): reconcile F57's design and copy decks`.

---

# Part I — the backend

## Task 2 — The role set widens: `StaffRole`, the CHECK, and `break_started_at`, as one atomic change (D1, D2, D3)
`Backend/app/models/constants.py`, `Backend/migrations/versions/00NN_floor_roles.py` (**new**), `Backend/app/models/staff_user.py`, `Backend/tests/test_migrations.py`

**The four halves ship together and this is not a preference.** `models/staff_user.py` declares every column explicitly and **no model↔migration parity test exists anywhere in `Backend/tests/`**, so without the ORM column every line in Tasks 3, 4 and 5 is an `AttributeError`. And without the enum members, `require_role(*StaffRole)` admits two roles and D5's walker assertion cannot be written.

**Resolve the revision id at build time. Do not read it off this document.**

```
cd "<repo>/Backend" && uv run python -m alembic heads
```

Take the next integer; set `down_revision` to whatever that command printed. **As of 2026-07-31 it prints `0014 (head)`**, so today the file is `0015_floor_roles.py` with `revision = "0015"`, `down_revision = "0014"` — but if any other entry lands a migration first, that is wrong and `alembic heads` is right.

**`StaffRole` gains three members**, and the comment at `constants.py:10-12` is **rewritten, not deleted** — it records that the bar it set was met rather than waived (spec conflict 2):

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

The migration is spec D3's block verbatim: **DROP then ADD** on the named `staff_users_role_check` (a CHECK's expression cannot be altered in place; `ADD CONSTRAINT` validates existing rows and a **widening** can only admit rows that were already legal, so it cannot fail on live data), then `ADD COLUMN break_started_at TIMESTAMPTZ`. The `downgrade()` drops the column, drops the constraint `IF EXISTS`, and re-adds the **two-value** CHECK **without** `IF EXISTS` and **deliberately able to fail** — a row holding `seamstress` must block the narrowing rather than sit past a constraint its own value violates. `0011_staff_roles.py:20-21`'s comment is likewise rewritten to the past tense.

Deliberately absent, each stated as a comment so a reviewer can check the list is complete rather than short:

- **No `GRANT`.** `0003_auth.py:83-84` issued table-level `GRANT SELECT, INSERT, UPDATE, DELETE ON staff_users TO app_user`; table grants are column-agnostic and no column-level grant was ever issued here. (The `ALTER DEFAULT PRIVILEGES` gotcha in `.claude/CLAUDE.md` is about newly *created* tables.)
- **No `enable_tenant_rls`.** RLS is a table property, forced on `staff_users` since 0003. F57 adds no table — **`test_every_tenant_id_table_has_forced_rls` staying green unedited is the assertion that none snuck in.**
- **No `_updated_at_trigger`.** It exists from 0003.
- **No index, no default, no NOT NULL, no backfill.** Nothing filters or sorts on `break_started_at`; a partial index would serve no reader and cost every write.

**The ORM column**, beside the other `mapped_column` declarations in `models/staff_user.py`. ⚠ **Two imports come with it** — the file's imports are `uuid`, `Text`, `text`, `PG_UUID`, `Mapped`, `mapped_column`, `Base`, `StandardColumns`, `StaffRole` (`:1-8`), and **neither `datetime` nor `TIMESTAMP` is among them**. That matters here more than it looks: this task's *Done when* says mypy resolving `StaffUser.break_started_at` is the whole local signal, so a `NameError`-shaped omission in a copy-paste block is the entire proof surface.

```python
from datetime import datetime

from sqlalchemy import TIMESTAMP, Text, text   # TIMESTAMP joins the existing sqlalchemy import

break_started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
```

Match whichever `TIMESTAMPTZ` spelling `models/booking.py` already uses rather than introducing a second one.

**Tests (`db`-marked, appended to `test_migrations.py`)** — follow that file's conventions: the round-trip goes **last among the schema-mutating tests**, owns no fixtures, and wraps the downgrade in `try/finally: command.upgrade(cfg, "head")`.

1. `test_staff_role_check_pins_the_role_set` (`:73-93`) **rewritten to iterate `StaffRole`** rather than list literals, so a sixth role is covered the day it is added or the test fails. `UNKNOWN_ROLE` still refused. **Every probe rolls back** (C6).
2. A sibling of `test_adding_the_role_check_validates_existing_rows` (`:154-189`) for the widened set, using the migration's **verbatim** `ALTER` as `_ADD_WIDE_ROLE_CHECK` and a `_DROP` without `IF EXISTS`, **both halves**: rows holding `owner` + `shift_manager` + `reception` present ⇒ the constraint is added; an unknown-role row present ⇒ **refused**, with `assert _ROLE_CHECK in str(exc)` on a `DBAPIError` (the `:176-181` shape and its comment).
3. **The highest-value test in the feature.** `pg_get_constraintdef` for `staff_users_role_check` pinned byte-identical **after this feature's migration** (keyed to `head`, never to a revision id — `test_the_booking_check_in_migration_leaves_…`'s docstring at `:456-468` is the shape and says why). ⚠ **Capture the literal by running it.**
4. `break_started_at` is a **nullable `timestamp with time zone`** on `staff_users`, read from `information_schema.columns` (the `_check_in_column` helper's shape).
5. `test_migration_00NN_round_trips` — upgrade applies, downgrade removes **both** halves, upgrade re-applies. **Both directions**, 0013's own rule: a downgrade that silently no-ops stays green while shipping an irreversible migration.
6. **The downgrade's honest failure**: with a `reception` row present, the narrowing re-`ADD CONSTRAINT` is refused. Rolled back.
7. `test_the_app_role_can_promote_to_shift_manager_but_not_to_an_unknown_role` (`:96-151`) extended to promote to a floor role under the **app** role, under forced RLS, with only its GRANTs. ⚠ **Its probe rolls back** (C6, and `:106-110` is the comment that explains why).

- **Done when**: `make lint` clean (ruff + `mypy app tests`), `make test` green (the new tests are `db`-marked → collected and deselected). ⚠ The real proof runs on CI, or locally per the § above; without it, mypy resolving `StaffUser.break_started_at` is the whole local signal.
- Commit: `feat(auth): widen StaffRole to the three floor roles and add break_started_at`.

## Task 3 — The two break writers, guarded by predicate and read back through the identity map (TDD, `db`-marked)
`Backend/app/db/repositories/staff_users.py`, `Backend/tests/test_staff_repositories.py`

**This is the subtlest backend part and it gets its own task.**

The identity-map trap is documented three times in this repo and F34 shipped the fix: `update(StaffUser)` is **ORM-enabled DML** whose default `evaluate` synchronization stamps the SET values onto any identity-mapped instance **whatever the database matched**, and the session factory is `expire_on_commit=False` (`db/session.py:66`) — so a trailing `by_id` hands the poisoned object back. Cite `bookings.py:328-336` (`cancel`'s docstring, the governing precedent), `booking/owner.py:326-333`, and `test_booking_owner_db.py:747-760` in the code comment so the next reader does not rediscover it.

Both writers are **one guarded UPDATE + one identity-map-defeating re-read**, returning `tuple[bool, StaffUser | None]`:

```python
async def start_break(
    self, session: AsyncSession, tenant_id: UUID, staff_id: UUID, *, at: datetime
) -> tuple[bool, StaffUser | None]:
    #  UPDATE staff_users SET break_started_at = :at
    #    WHERE tenant_id AND id AND break_started_at IS NULL AND deleted_at IS NULL
    #    RETURNING id                       <- the ONLY honest "did I write?"
    #  then ONE re-read:
    #    select(StaffUser).where(tenant_id, id, deleted_at IS NULL)
    #      .execution_options(populate_existing=True)
    #  -> overwrites the identity-mapped instance from the row the DB actually
    #     holds. Correct branch AND correct render, one statement.

async def end_break(self, session, tenant_id, staff_id) -> tuple[bool, StaffUser | None]:
    #  ... WHERE break_started_at IS NOT NULL AND deleted_at IS NULL RETURNING id, same re-read.
```

**`(bool, StaffUser | None)` and not F34's four-member `CheckInOutcome`, and the difference is real.** F34 needed three values because zero rows there had two **opposite** causes — already checked in (200) vs no longer `confirmed` (409). A break has **no status guard**: zero rows with a live row back means the target state already holds, full stop. A fourth member with no reachable cause is not an abstraction.

**`populate_existing=True` is applied unconditionally**, not per call site. Whether a caller happened to load the row first is exactly the reasoning that has bitten this repo three times; the flag costs one chained method and removes the question.

Every predicate keeps `deleted_at IS NULL` and the **redundant** `tenant_id` — the defence-in-depth this class's own docstring states (`staff_users.py:9-13`).

**Declined:** `pg_advisory_xact_lock`. F51's namespaced lock exists because the last-owner invariant is *"at least one"*, which no index can express; a break touches one column on one row and has no cross-row invariant to serialise. Adding one would serialise every break in the boutique against every staff edit.

**Tests written first** (`db`-marked): a start writes the timestamp and returns `(True, row)`; a **second** start returns `(False, row)` **keeping the first timestamp**; an end clears it and returns `(True, row)`; a second end returns `(False, row)`; a soft-deleted target returns `(False, None)`; an unknown id returns `(False, None)`; `list_live` returns the column and **no soft-deleted row**.

- **Done when**: `make lint` clean, `make test` green (deselected locally), `make test-db` green on CI or locally per the §.
- Commit: `feat(auth): break start/end writers on StaffUsersRepository`.

## Task 4 — `FloorService`, the two `AuditAction` members, and the authorization matrix (TDD, fast)
`Backend/app/floor/__init__.py`, `Backend/app/floor/service.py`, `Backend/app/models/constants.py`, `Backend/tests/test_floor_service.py` (**new**)

**This is where D6 is actually proven**, and it is a pure branch against fakes — no Postgres.

**`AuditAction` gains two members** — **no migration**: `audit_log.action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`), the same basis on which F15 added seven, F34 two and F51 five. `STAFF_BREAK_STARTED = "staff_break_started"` · `STAFF_BREAK_ENDED = "staff_break_ended"`.

**The authorization statement is the service's first statement and it runs before any read of the target:**

```python
_ELEVATED = frozenset({StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value})

# The acting identity is StaffContext, resolved from the session cookie by
# get_current_staff. It is NEVER read from the path, the query or a body: the
# request names only WHOM to toggle, never WHO is asking. A body-supplied
# "staff_user_id" doubling as the caller's identity is the one shape that turns
# "any staffer on herself" into "any staffer on anyone".
if staff_id != actor.id and actor.role not in _ELEVATED:
    raise NotAuthorizedError
```

Three properties, each deliberate and each with its own assertion: the left operand comes from the **request** and the right from the **session**; it runs **before any read**, so the generic 403 is not an existence oracle; it compares **ids**, never emails or names.

`NotAuthorizedError` is reused (`auth/dependencies.py:17-21`) — **no new code, no new handler, no new `SPEC_ERROR_CODES` member.** A deactivated or cross-tenant target is a **404** (`DomainNotFoundError` → `main.py:757-758`) for an elevated caller and unreachable for anyone else.

The `(wrote, row)` mapping, and the audit rule:

| `wrote` | `row` | Answer |
|---|---|---|
| `True` | the row | **200**, card rendered from it, **one audit row** |
| `False` | the row | **200 unchanged**, card rendered from it, **no audit row** — the first toggler's timestamp survives |
| `False` | `None` | **404** `NOT_FOUND` |

`details` = `{"target": str(staff_id), "break_started_at": …}` on the start, `{"target": …, "previous_break_started_at": …}` on the end. **`previous_break_started_at` is load-bearing**: ending a break destroys the only copy of when it began and there is no history table (D2) — F34's `previous_checked_in_at` argument, same shape, and it must be captured **before** the write. **A row is written even for a self-toggle** (the asymmetric rule was considered and declined in D8).

**Tests first** (fakes, no Postgres — the `test_dashboard_api.py` scaffold where a statement escaping to a real session raises rather than passing silently):

- owner on another ⇒ allowed · shift_manager on another ⇒ allowed · reception / sales_assistant / seamstress **on herself** ⇒ allowed.
- each of those three **on another** ⇒ `NotAuthorizedError` **and the target repository was never called** — the assertion that proves the check runs before the read, i.e. that the 403 is not an existence oracle. **This is the floor-program review's fourth F57 item and it must not be folded into the previous row.**
- the `(wrote, row)` mapping onto 200 / 200-unchanged / 404, all three.
- an audit row on a write with `actor_id=actor.id`, `entity=str(staff_id)`; **none** on a no-op.
- the end's `details` carries `previous_break_started_at`, captured before the write.
- `_status(row)` returns `BREAK` iff `break_started_at is not None`, `AVAILABLE` otherwise, and `StaffCardStatus`'s wire literals are asserted **set-equal to `{"available", "break"}`** — the test that fails if `occupied` is pre-added (D9). ⚠ **`StaffCardStatus` is declared in `app/models/constants.py`**, beside the two new `AuditAction` members this task already adds there, matching every other enum in this codebase (`DressMediaStatus`, `GatewayCredentialStatus`, `StaffRole`). **Not** in `app/floor/schemas.py`, which Task 5 creates — this task's tests import it and cannot import from a file that does not exist yet. Task 5's schemas import it from `constants`.

- **Done when**: `make lint` + `make test` green, **locally and on CI**.
- Commit: `feat(floor): break toggle service with its two-axis authorization and audit rows`.

## Task 5 — `app/floor/` — the router, the schemas, the wiring, and the milestone API module (TDD, fast)
`Backend/app/floor/router.py`, `Backend/app/floor/schemas.py`, `Backend/app/main.py`, `Backend/tests/test_floor_api.py` (**new**)

**Tests first**, on the `test_dashboard_api.py` template (351 lines; F57's is the same shape — a duck-typed `FakeFloorService` on `app.state.floor_service`, a hardcoded `TenantContext` resolver, no database).

The router is `dashboard/router.py`'s 80 lines with a different gate, and its module docstring re-states — not re-argues — the four decisions that file already carries: router-level gate so a later route cannot forget it, tenant from `get_current_tenant(request)` and **never** `StaffContext.tenant_id`, a **fifth** local three-line `_no_store` copy rather than a backwards dependency arrow, no rate limiter. Plus the one decision that is F57's own:

```python
router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(*StaffRole)),   # all five, spelled from the enum
    ],
)
```

**Why a new module and not a route on an existing router — structural, not stylistic.** `RoleGate` composes by **intersection**: the docstring says so (`auth/dependencies.py:44-45`) and `_gate_role_sets` yields **every** gate in the dependency tree (`test_staff_role_gating.py:129-136`). A per-route `require_role(*StaffRole)` on `booking/owner_router.py` would still be refused for a seamstress by that router's `require_role(OWNER, SHIFT_MANAGER)` at `:82`. **There is no per-route widening in this codebase.** The alternatives were relaxing the owner router's gate and re-tightening all twelve of its routes (twelve gates to protect one, and the first mistake gives a seamstress the day's customer list), or hanging it on `auth/staff_router.py`, whose docstring's *"a route added here later cannot forget the gate"* guarantee it would delete.

**`require_role(*StaffRole)` spelled from the enum, not five literals**, so a sixth role is admitted here by default — safe **only** because Task 6's walker assertion pins the floor roles out of everywhere else. `require_role` is already varargs; no change to `dependencies.py`.

Three routes:

```
GET  /manage/floor                                  -> FloorResponse
POST /manage/floor/staff/{staff_id}/break/start     -> StaffCard
POST /manage/floor/staff/{staff_id}/break/end       -> StaffCard
```

Neither POST takes a body, so neither needs a `ForbidExtraModel`. Both are `no-store` by the router dependency and both are CSRF-fenced by `CsrfOriginMiddleware` (`csrf.py:48` gates on `request.method in MUTATING_METHODS`); the GET is not, and its protection is the session cookie and the role gate, alone.

**The payload is an ENVELOPE, not a bare array** — `{"staff": [...]}`. F51's `/manage/staff` returns a bare list and that was right for a list; this one is the floor's, and F36 adds rooms + occupancy while F58 adds the waitlist. An envelope makes those additive; a bare array makes the first of them a breaking shape change.

**Wiring in `main.py`**, three edits mirroring F52's: `app.state.floor_service = FloorService(get_session_factory())` beside `:562`, `app.include_router(floor_router)` after `:1038`, and the include carries the same shadowing warning the other six carry.

**Tests in `test_floor_api.py`:** a `ROUTES` table for the three routes (**concrete URLs** — C4), which gives the 401 walk, the wiring walk and the `cache-control: no-store` parametrization for free; a `FakeFloorService`; each route reaching its own service method with the right arguments; the payload literal for a two-card floor; `SPEC_ERROR_CODES` asserted **set-equal** and **empty of new members**; `StaffCardStatus`'s literals set-equal to `{"available", "break"}`. Export `FLOOR_ROUTES` for Task 6 (the `test_catalog_api` / `test_payments_api` precedent).

- **Done when**: `make lint` + `make test` green, **locally and on CI**. **This is the backend milestone**: the route, the role gate, the tenant trust path and the wire shape are exercised end to end with no Postgres.
- Commit: `feat(floor): GET /manage/floor and the two break toggle routes`.

## Task 6 — The walker assertion that pins the three roles out of everything else (TDD, fast)
`Backend/tests/test_staff_role_gating.py`

**This is the test the whole feature's safety rests on** (spec Risk 1), and the floor-program review's second F57 item asks for it by name.

Add `FLOOR_ROLES`, `FLOOR_OPEN` (**templates** — C4) and `test_the_floor_roles_reach_exactly_the_floor_routes`, derived from the **live route table** so it covers routes that do not exist yet. Spec D5 has the code.

⚠ **Classify on the INTERSECTION of a route's gates, never with `any(...)` over them.** An earlier draft of D5 wrote `if any(roles & FLOOR_ROLES for roles in role_sets)`, which contradicts the premise the whole feature rests on: `RoleGate` composes by intersection (`auth/dependencies.py:44-45`) and `_gate_role_sets` yields **every** gate in the tree (`:129-136`) — which is why the shipped `test_route_table_matches_the_permission_matrix` uses `all(...)` (`:205`). With `any(...)`, a route added to the floor router and **tightened per-route** — `@router.post("/floor/rooms/assign", dependencies=[Depends(require_role(OWNER, SHIFT_MANAGER))])`, i.e. exactly what F36 and F58 will add — lands in `admits_floor` even though the intersection denies the floor roles, and `set(admits_floor) == FLOOR_OPEN` red-fails on a correct route. **A reviewer facing that red on a test declared untouchable is most likely to "fix" it by relaxing the assertion — which is precisely the outcome spec Risk 1 exists to prevent.** Use `effective = frozenset.intersection(*role_sets) if role_sets else frozenset()`, with the empty case counting as **not** admitting.

**Three assertions, each failing on a different mistake:**

| Assertion | Fails when |
|---|---|
| `set(admits_floor) == FLOOR_OPEN` | a floor role is admitted anywhere else — including a future router copy-pasting `require_role(*StaffRole)` — **and** when a floor route quietly lost its gate, because an ungated route's `effective` is empty and it drops out of `admits_floor` |
| `FLOOR_ROLES <= effective` | a floor route admits only *some* of the three |
| `assert not missing` | `FLOOR_OPEN` names a path that no longer exists (the anti-vacuity half, the `seen >= UNGATED_ALLOWLIST` shape at `:161`) |

⚠ **An earlier draft of this table credited the lost-gate case to assertion 2.** It cannot be: `all(FLOOR_ROLES <= roles for roles in role_sets)` over an **empty** `role_sets` is vacuously `True`. Assertion 1 is what catches it, and only if the classifier treats an empty `effective` as not-admitting.

**It must never be relaxed to a subset check and the `any(...)` spelling must never come back**, and `FLOOR_OPEN` must never gain a route without the reviewer asking why. Both sentences belong in the test's docstring, with the intersection reasoning in a comment beside the classifier.

Also in this task:

- **`FLOOR_ROUTES` joins the two shipped HTTP walks** (`:340`, `:371`), with the `_client(floor=…)` asymmetry from **C3**: the shift-manager walk gets a fake so the routes answer 2xx; **the unknown-role walk deliberately does not**, so the floor gate is proven to actually **raise** rather than merely carry an `allowed_roles` attribute. That is the decoy-gate proof `:362-367` already describes, and the floor router — the one gate spelled `*StaffRole` — is where it matters most.
- **`test_gate_admits_listed_roles` gains a second case** for `require_role(*StaffRole)` admitting all five; the existing two-role assertion is untouched (**C1**).
- **The `UNKNOWN_ROLE` sentinel's comment moves to the past tense** in both `test_staff_role_gating.py:81-91` and `test_migrations.py:54-56`. Both explain that `"no-such-role"` was chosen *because* reception/seamstress/sales were the next roles to join. They did. The `assert UNKNOWN_ROLE not in {role.value for role in StaffRole}` tripwire (`:88-91`) needs no change and stays green — the comment records that the anticipated day arrived and the sentinel held. **A one-line edit a reviewer would otherwise flag as a stale comment.**
- **`test_route_table_matches_the_permission_matrix` is untouched** and the floor routes pass it unchanged: they admit `shift_manager` and are not in `OWNER_ONLY`. **`OWNER_ONLY` is not edited at all** — F57 narrows nothing.
- **`test_gates_admit_only_known_roles` and `test_the_not_authorized_contract_is_pinned_by_literal` are untouched** and both gain the three roles for free (**C2**).
- **`test_every_manage_route_is_role_gated` and `test_no_route_is_registered_twice_across_routers` stay green unedited** — the first proves the floor router carries a gate at all; the second catches a `/manage` path collision now that seven routers mount the prefix.

- **Done when**: `make lint` + `make test` green. Sanity-check the new test is not vacuous by temporarily adding `StaffRole.RECEPTION` to `dashboard/router.py`'s gate and confirming it goes red — then revert.
- Commit: `test(auth): pin the three floor roles to exactly the floor routes`.

## Task 7 — F51's staff CRUD absorbs the new roles with no redesign (TDD, fast)
`Backend/tests/test_staff_service.py`, `Backend/tests/test_staff_api.py`

**No production code changes in this task.** `CreateStaffRequest.role: StaffRole` and `UpdateStaffRequest.role: StaffRole | None` are typed as the enum precisely so *"an unknown value is a house 422→400 at the boundary and can never reach 0011's CHECK"* (`auth/schemas.py:65-67`) — widening the enum widens both requests with **zero edits**. What this task adds is the proof, because "widening the enum widens nothing" cuts both ways and a reviewer will ask.

- Creating and patching to each of the three new roles succeeds, end to end over HTTP.
- **The last-owner guard still fires** on `owner → seamstress`, because it keys on the target *leaving* `owner` and not on where it is going: `role_moves and target.role == StaffRole.OWNER.value and count_live_owners(...) <= 1` (`auth/staff.py:187-193`).
- **The self-demote guard still fires** on the same move (`:187-188`).
- **`STAFF_ROLE_CHANGED`'s `details={"from": …, "to": …}`** (`:251`) carries the new values with no edit, because they are strings — asserted.

- **Done when**: `make lint` + `make test` green with **no diff under `Backend/app/auth/`** in this commit.
- Commit: `test(auth): F51's staff CRUD accepts the three floor roles unchanged`.

## Task 8 — `test_floor_db.py` — the race, the soft delete and RLS isolation (written here, executed on CI or per the §)
`Backend/tests/test_floor_db.py` (**new**)

NullPool engines in `try/finally`, the `app_role_url` fixture (never the superuser), frozen module-constant clocks injected as `clock=lambda: NOW` — the idioms `test_booking_owner_db.py` already uses.

- A start writes the timestamp; an end clears it.
- **A second start keeps the FIRST timestamp and reports no write** — the idempotency predicate, asserted on both halves of the tuple.
- **A start racing an end on one row** leaves whichever committed first, and **the loser renders the DATABASE's value, not its own**. This is the assertion that fails if `populate_existing=True` is dropped, and the one to run the mutation check against. Use the **forced interleave** F34's C7 established — hold the loser's `tenant_session` open across the winner's entire transaction, since exiting `tenant_session` is the commit (`db/tenant.py:25`) — **not `asyncio.gather`**, which orders nothing and would let the test pass by coin flip.
- The floor read returns every live staff row and **no soft-deleted one**.
- **RLS isolation**: tenant B's staff row can neither read tenant A's staff nor toggle tenant A's break — **404, indistinguishable from missing**. The `test_booking_isolation.py:1274` pattern. Every tenant table in this repo has an isolation probe and `staff_users` is no exception just because F57 adds no table.
- ⚠ **Every row this module COMMITS holds `owner` or `shift_manager`, never a floor role** (**C6**). This module cannot roll back — the interleave holds a `tenant_session` open across the winner's whole transaction *because exiting it is the commit* (`db/tenant.py:25`), and the isolation probe needs a persisted second-tenant row — so the **seed role** is what gives instead of the rule. Nothing here asserts anything about the actor's role: break toggling is role-independent at the repository layer and RLS isolation is about `tenant_id`. A committed `reception` row reddens **three** tests in `test_migrations.py`, a file that never mentions F57, and `test_floor_db.py` sorts **before** it (session-scoped container, alphabetical file collection) — including `test_adding_the_role_check_validates_existing_rows`, whose failure names 0011's constraint and has nothing to do with breaks.

- **Done when**: `make test-db` green on CI, or locally per the §.
- Commit: `test(floor): break concurrency, soft delete and RLS isolation`.

---

# Part II — the frontend

## Task 9 — Extract `usePoll`, carry F34's unmount fix, and migrate `BoardSection` onto it (D10)
`Frontend/apps/manage/src/lib/usePoll.ts` (**new**), `…/__tests__/usePoll.test.tsx` (**new**), `…/components/BoardSection.tsx`

**Tests first** in `usePoll.test.tsx`, the `CatalogSection.test.tsx` pattern plus `vi.useFakeTimers()`.

**The acceptance rule is mechanical and it is the whole reason this is reviewable: `apps/manage/src/__tests__/BoardSection.test.tsx` must pass with ZERO edits.** Its **61 `it(` blocks** cover every one of D4's six mechanisms plus D14's pause and idle; they are the only thing that can tell a faithful extraction from a subtly different one on those, and they only mean that if **not a single expectation is relaxed to accommodate the hook**. If any needs an edit, the extraction is wrong. ⚠ **They are necessary and not sufficient** — neither of the two `TickOutcome` divergences below is among them, which is why `usePoll.test.tsx` pins those two by name. Escape hatch, in order: (1) grow the hook — a `runExclusive`, a hold — until the tests pass untouched; (2) failing that, revert `BoardSection.tsx` to its shipped loop, ship `usePoll` with `FloorPanel` as its only caller, and record the divergence for F37. **That fallback is worse than the goal and is written down so the build takes it deliberately rather than by editing a test.**

The hook lands in `lib/` (`lib/booking.tsx`'s header gives the reason: a shared helper hung off either end of an import chain closes it into a cycle) with spec D10's contract — three exported constants, `PollMode`, `PollTerminal`, and a `Poll` whose every member has a named caller: `mode`, `terminal`, `bump()`, `refresh()`, `pause()`, `resume()`, `fail(error)`.

**What the hook owns** — the six mechanisms neither caller may re-derive: the single arming site (`schedule-after-settle`, so at most one request in flight per tab **by construction**); the `document.hidden` gate plus the `visibilitychange` **immediate** refetch; the 5s → 60s backoff with reset on the first success; the `{401, 403}` terminal classification; the idle stop; the monotonic generation behind `isCurrent`.

**⚠ THE UNMOUNT FIX MOVES INTO THE HOOK'S CLEANUP VERBATIM, WITH ITS COMMENT.** `BoardSection.tsx:248-261`:

```ts
return () => {
  // clearTick() alone cancels only the timer armed RIGHT NOW. A request in
  // flight at unmount still reaches its .finally() and arms a fresh one, and
  // nothing in tick -> load -> finally -> schedule touches React state, so
  // the loop would outlive the component forever — one orphan per nav-away.
  // This is also what makes "at most one poll in flight per tab by
  // construction" true rather than merely intended.
  runningRef.current = false;   // <- THIS LINE, FIRST
  clearTick();
  clearIdle();
};
```

This was one of F34's **two review blockers**: switching nav sections mid-request leaked a permanent 5-second request loop, one per nav-away, for the rest of a twelve-hour session. It is one line. **Two callers today and four by F42 — the alternative is that line being copy-pasted four times by four different builders, or dropped by one of them.** It gets its own named test: *a request unresolved at unmount arms nothing* — resolve it after unmount, advance several intervals, assert the call count did not grow.

**What the hook deliberately does NOT own**, because both would be surface with one caller:

⚠ **`run` returns a three-valued `TickOutcome` (`void` / `"held"` / `"suppressed"`), and an earlier draft of D10 got this wrong.** That draft said both early returns move into the caller's `run` with *"byte-identical behaviour, zero API"*. The shipped source contradicts it in two places, and **`BoardSection.test.tsx` covers neither**, so the zero-edit gate alone could go green over a changed loop — on the one component in the console that has already shipped two loop bugs:

| Caller's early return | Shipped `BoardSection.tsx` | A two-valued `run` |
|---|---|---|
| pointer hold | `schedule(backoffRef.current)` (`:228-232`) — re-arms at the **current, possibly backed-off** gap, backoff untouched | a clean tick resets to base, so a held tick during a backoff would fetch at 5 s |
| mutation in flight | `return` with **no** `schedule()` (`:219-222`); the single re-arm is `mutate()`'s `.finally()` (`:411-420`) | a clean tick re-arms, so timers get armed **during** a mutation |

- **The pointer-hold POLICY** (`BoardSection.tsx:223-232`) stays in the caller: check the ref, clear it, `return "held"`; the hook re-arms at the current gap and leaves the backoff alone. ⚠ **`FloorPanel` must write its own** (deck §3.2(1), §7.2).
- **A `runExclusive` mutation wrapper** (`:363-421`) is still declined. The caller keeps its own `mutationsRef`, `run` returns `"suppressed"` while it is non-zero — the hook arms **nothing** — and `bump()` discards the poll in the air. Same observable behaviour (zero requests during a mutation, **no timer armed** during one, a tick re-armed by the `.finally()` after a **failed** mutation as well as a successful one) with two union members instead of a three-member wrapper API. `fail(error)` is what the mutation's `catch` needs and is all it needs, and it is also what makes the deck's **P-6** (a toggle's 403 is terminal) one line rather than a second classifier.
- Anything board-shaped: the date roll, the focus rescues, the stranded-row repair, the divider scroll. **`BoardSection`'s two shipped bug fixes — the `rowError` focus rescue at `:308-319` (WCAG 2.4.3, legal here) and the unmount fix — must both still be present after the migration**, the first in the component and the second in the hook.

**Named tests in `usePoll.test.tsx`:** the unmount test above all; exactly one request per tick and never two in flight; `document.hidden` pauses and `visibilitychange` fetches **immediately**; **401 and 403 each stop the loop — two tests, not one** (different code paths: `resolve_session` returning `None` vs `RoleGate` raising); consecutive failures back the interval off and **cap**, one success resets it; `pause` stops and `resume` fetches **before** the interval elapses and at the **base** gap; the idle stop fires and one interaction resumes; **`fail(error)` classifies a mutation's 401 and 403 as terminal and anything else as not** (P-6's mechanism); ⚠ **a `"held"` tick during a backoff re-arms at the backed-off gap and does not reset it**; ⚠ **a `"suppressed"` tick arms no timer at all** — the two divergences the zero-edit gate cannot see.

- **Done when**: `make fe-test` + `make fe-build` green; **`git diff --stat` shows `BoardSection.test.tsx` unchanged**; `pnpm -r lint && pnpm -r typecheck` clean. ⚠ **The zero-edit gate is necessary, not sufficient** — it is what proves the extraction faithful on the six mechanisms, and the two `TickOutcome` tests are what prove it faithful on the two early returns.
- Commit: `refactor(manage): extract usePoll from BoardSection, unmount fix included`.

## Task 10 — i18n, the role-label record, the API client, and the eleventh nav row (TDD)
`Frontend/apps/manage/src/i18n/he.ts`, `…/i18n/ar.ts`, `…/lib/roles.ts` (**new**), `…/api.ts`, `…/App.tsx`, `…/__tests__/i18n.test.ts`, `…/__tests__/api.test.ts`

⚠ **This task does NOT render `<FloorPanel/>`, and its file list no longer includes `Nav.test.tsx`.** An earlier draft had it wiring both render branches and adding the floor `Nav.test.tsx` case — while `FloorPanel.tsx` is created in **Task 11**. The import would not resolve, so `make fe-build` and every `Nav.test.tsx` case would fail, and the task's own green gate was unreachable. **The two render branches and the floor nav case moved to Task 11**, which is the task that creates the component. Everything here is component-independent: `SectionKey` gains a member and `NAV` gains a row, but no test mounts a floor role until Task 11, and the shipped `activeKey === "floor" && …` branches are conditionals rather than an exhaustive switch, so the build is clean with the branch absent.

**Tests first** in `api.test.ts` (the shipped fetch-mock pattern) and `i18n.test.ts` (a fifth `describe` block).

- **`he.ts`** — a new block appended as **flat dotted literals** (the F15 `:61+` / F52 / F17 / F34 `:458+` shape, **not** the pre-F15 nested `nav: {}` object): `nav.floor`, the whole `floor.*` namespace and the three `staff.role*` keys, **transcribed from Task 1's `copy.md` verbatim** — the table, not the prose. **`staff.selfMarker`, `staff.roleOwner` and `staff.roleShiftManager` are shipped keys and are NOT re-declared** (`he.ts:207-209`). Mechanical checks that ride along, from `copy.md` §0: **no string names or implies a retry interval** (rule 9 — the backoff falsifies any number the moment it doubles), and **`floor.accessEnded` names no role** (rule 10).
- **`ar.ts`** — the **same keys**, values = the approved Hebrew standing in untranslated, **never `""`** (i18next's `returnEmptyString` renders `""` rather than falling back, so a premature switch would blank the page). `lng` and `fallbackLng` stay `"he"`; `i18n/index.ts` unchanged. ⚠ **Nothing keeps the two files in sync** — no parity guard exists and F57 does not invent one (Risk 7 / deck F-5, whose whole mitigation is that both columns come from **one** `copy.md` table).
- **`lib/roles.ts`** — `ROLE_LABEL_KEY: Record<StaffRole, string>`, spec D13's block. **The `Record<StaffRole, …>` type is the point**: adding a sixth member to the union without a key is a **compile error**, not a wrong label. In `lib/` so `StaffSection` and `FloorPanel` share it without an import cycle.
- **`api.ts`** — `StaffRole` (`:362`) gains the three members (`StaffMember`, `CreateStaffRequest`, `UpdateStaffRequest` inherit with no edit); new `StaffCard` and `FloorResponse` interfaces; `getFloor()`, `startStaffBreak(staffId)`, `endStaffBreak(staffId)` on the exported `api` object, in the `checkInBooking` shape (`:629-634`). **No case conversion** — this app speaks the backend's snake_case verbatim (`api.ts:1-5`).
- **`App.tsx`**, four edits against the shipped shapes:
  - `SectionKey` (`:18-28`) gains `| "floor"` — the **eleventh** member (**C11**);
  - `const FLOOR_ONLY = ["reception", "sales_assistant", "seamstress"] as const;` beside `ALL` (`:30`);
  - `NAV` gains `{ key: "floor", labelKey: "nav.floor", roles: FLOOR_ONLY }` **immediately after the `board` row (`:66`)**;
  - **the two render branches are Task 11's**, because they import a component that does not exist until then;
  - **`useState<SectionKey>("dashboard")` at `:83` is NOT touched.** The three floor roles reach exactly one `NAV` row, `dashboard` is unreachable for them, and `reachable[0]?.key ?? section` (`:128-130`) lands them on the floor with no edit.
  - **Declined: widening `board`'s `roles` to all five.** A seamstress would land on a section labelled «לוח היום» whose board the server refuses her, and `BoardSection`'s first fetch would 403 — which its own `terminalOf` correctly treats as **terminal**, blanking the screen. The label would promise a thing the gate forbids and the component would be right to break. **`Nav.test.tsx`'s count assertion is what makes this a test rather than a preference.**
- **No `vite.config.ts` change** — `/manage/floor*` is under `/manage`, already proxied.
- **No `test_frontend_constant_parity.py` change** — `POLL_INTERVAL_MS` and friends mirror no server bound.
- **No `scripts/qa-greps.sh` change** — `jerusalemTime` already renders the break time with `timeZone: Jerusalem` (`lib/jerusalem.ts:35`), so F57 adds no formatter for the unzoned-formatter grep to find.

**Named tests:** `i18n.test.ts` — the whole `floor.*` deck resolves; **every value of `ROLE_LABEL_KEY` resolves to its own Hebrew** (the `Record` type catches a missing member, this catches a missing key); `nav.floor` resolves beside the nested `nav` object, as the **eleventh** nav item. `api.test.ts` — `getFloor` / `startStaffBreak` / `endStaffBreak` hit the right URLs. **`Nav.test.tsx` is Task 11's.**

- **Done when**: `make fe-test` + `make fe-build` green; every key in `copy.md`'s table is in both i18n files and no key is in one only (**32 invented, 4 reused — the 4 are NOT re-declared**).
- Commit: `feat(manage): floor i18n, the role-label record, the floor API client and its nav row`.

## Task 11 — `FloorPanel` — fourteen states, the break control, its own SC 2.2.2 loop, and the two render branches (TDD)
`Frontend/apps/manage/src/components/FloorPanel.tsx` (**new**), `…/__tests__/FloorPanel.test.tsx` (**new**), `…/App.tsx`, `…/__tests__/Nav.test.tsx`

**The `App.tsx` wiring lands HERE, not in Task 10**, because it imports this component:

- the `board` branch (`App.tsx:152`) wraps `<BoardSection />` + `<FloorPanel …/>` in a `space-y-6` div — **the panel AFTER the board, never before** (deck §1.2: above it, the panel grows after the board's one-shot `scrollIntoView` and pushes the «עכשיו» divider back out of view);
- a new `floor` branch renders `<FloorPanel …/>` alone.

⚠ **`Nav.test.tsx`'s API mock is an explicit ALLOWLIST and `getFloor` must be added to it** (`Nav.test.tsx:10-34`). Its shipped comment says why in F52's words: *"Without this every one of the nav tests below red-fails on mount with `TypeError: api.getDashboard is not a function` — an error that names the nav rather than the dashboard, because the console now LANDS on DashboardSection."* The new case — a reception / sales_assistant / seamstress user sees **exactly one** nav row and **lands on the floor section** — mounts `<App/>`, which renders `FloorPanel`, which calls `api.getFloor()`. **Add `getFloor: pending,` beside `getDashboard: pending,`** or the failure reads as a `FloorPanel` bug rather than a mock-allowlist gap, which is exactly the trap that file documents.

**`Nav.test.tsx`'s named cases:** the three floor roles each see **exactly one** nav row and land on the floor section (the `reachable[0]` fallback, `App.tsx:128-130`); **the owner's ten and the shift manager's eight are unchanged** — the count assertion that fails if `board` was widened instead of `floor` added.

**Tests first**, the `CatalogSection.test.tsx` + fake-timers pattern. **The design deck's §4 is the state list, §6 is the token list, and §7 is the a11y contract — build from those three tables rather than from prose.**

`FloorPanel` owns **all** of its own state and its own `usePoll` instance. **No floor state above `FloorPanel`** — that is what makes a floor tick repaint the cards and nothing else, because `BoardSection` is a **sibling**, not a parent. Lifting the rows into `BoardSection` or `App` would make every floor tick repaint the day's booking list. **A rule the plan may not relax.**

**Layout, from the deck's resolved `P-`s** — one `Card` containing `<ul className="divide-y divide-border">`, **one column at 375, 768 and 1440** (**P-1**, never a grid of `Card`s); the role is `text-sm text-ink-muted` **words**, not a Badge, so the card's **single** `Badge` is the status (**P-2**); **no aggregate summary line** (**P-3**); **no hoisting of her own card** — server order, marked with F51's shipped «זו את» (**P-4**); the brief's 🟢/🟡/🔵 ship as **words** (**P-5**). One breakpoint branch in the whole panel: at 375 the control drops to its own line (`flex-col`), at 768+ it sits inline (`sm:flex-row sm:items-center`). **No truncation and no ellipsis on a display name, ever** — a panel that abbreviates a colleague's name makes two colleagues look like one.

**Fourteen states, and the list may not shrink** (deck §4): `F-load` · `F` · `F-self` · `F-empty` · `F-fail` · `F-stale` · `F-paused` · `F-idle` · `F-401` · `F-403` · `F-busy` · `F-ok` · `F-noop` · `F-actfail`. The four the deck adds by decomposition are not optional: **F-noop and F-actfail are two different answers to the same tap**, and F-noop is deliberately **identical to F-ok** — telling her she lost a race would be telling her she was wrong when she was right.

**Which control exists** (deck §2.2): the panel renders **only the operation the server will accept**. On a colleague's card, a non-elevated staffer sees **a name, a role, a status and nothing else** — no disabled button, no lock glyph, no «אין לך הרשאה» line, no tooltip. **The absence is cosmetics and the test asserts it as cosmetics**; the control is D6's service check.

**The a11y floor, and pre-decided #38 makes it legally binding:**

- **Its own visible pause / resume toggle** — **one** `<button>` whose label changes, **never `aria-pressed`** (a toggle that changes both its name and its pressed state reads as two contradictory facts). `Button variant="ghost" size="md"` → `min-h-11` = 44px. **First stop inside the panel, before any card** — a 2.2.2 mechanism placed after the content it governs is reachable only by walking the list that is repainting under the walk. Accessible name `floor.pauseAria` «השהיה — עדכון הצוות» ⇄ `floor.resumeAria` — **each starting with the visible label**, WCAG 2.5.3 (**C8**). Resume fetches **immediately** at the **base** interval. **Focus stays on the control** — it renames, it does not unmount.
- **Its own idle stop** at `IDLE_STOP_MS`, mechanically identical to paused with **one** difference that is the reason there are two states: the body line **names the cause**, because a panel that stopped by itself and does not say why is indistinguishable from a panel that broke.
- **Two pause controls exist on the board screen for owner and shift_manager, and that is the answer rather than a problem.** One control governing both loops means lifting pause state into a shared parent — the coupling D11 forbids. What it costs is distinguishable accessible names, which `board.pauseAria` (`he.ts:481`) and `floor.pauseAria` provide. For the three floor roles there is **one** control because there is one region, and that is the case that makes it unmissable rather than merely correct.
- **The three-region split** (deck §7.1): the **cue** is `role="status"` and carries **only user-initiated outcomes**; **the list carries no live attributes at all** (`role="log"` is the tempting wrong answer — it is for append-only chat and this list mutates in place); the **freshness row** carries no live attributes and is deliberately **not `aria-hidden`**, or the panel's only honesty signal becomes sighted-only.
- ⚠ **"Write" means write, not change.** Assigning a non-empty string to a text node runs the DOM's string-replace-all and produces a real `childList` mutation inside `role="status"` **even when the two strings are byte-identical**. The cue is written **only when its value actually changes**, and **the test must drive several consecutive ticks with the cue already populated** — a single-tick assertion passes against the broken version whenever the cue starts empty (F34's F-7, inherited).
- **`role="alert"` appears exactly three times and each is bounded**: F-401 (once per dead session, the loop has stopped), F-403 (once per revocation), F-actfail (once per refused tap). **None can be produced by the poll on its own.**
- **Status never by colour alone** — «פנויה» / «בהפסקה» plus, on a break, the since-line and the control reading «חזרה»: three text signals, no glyph. **Role never by colour alone.** **Paused never by colour alone.**
- **≥44×44 on every target**; visible focus ring everywhere; `<bdi dir="ltr">` on times, **bare `<bdi>`** on Hebrew names and role words; one `h1` (the shell's) with the panel heading an `h2` **beside** the board's, no `h3`s.
- **Accessible names carry the visible label plus the person** — «להפסקה — נועה לוי». Five buttons all named «להפסקה» is a screen-reader dead end.
- **No motion at all** beyond the shipped `Button` spinner and the `Skeleton` pulse, both already frozen under `prefers-reduced-motion` globally.
- ⚠ **Focus, and this is the bug class that has shipped TWICE in this repo** (F56 on the storefront, F34 on the board) with **axe walking past it both times**. `@boutique/ui`'s `Button` is `disabled={disabled || loading}`, so the browser blurs the tapped control the instant a request starts. **Three rules, from deck §7.2:**
  1. **Cards are keyed by `staff.id`**, so a repaint mutates text nodes inside a stable element and focus inside a card survives every tick. One prop, and it is the most important line in the component.
  2. **After a SUCCESSFUL toggle, focus returns to the tapped control** — unlike F34's check-in it does **not** unmount, it renames «להפסקה» ⇄ «חזרה». An effect keyed on that card's busy state falling to `false` calls `ref.current?.focus()` **guarded on `document.activeElement === document.body`**, so it can never steal focus from wherever she moved it. That guard is F34's shipped shape (`BoardSection.tsx:298-306`).
  3. **After a FAILED toggle, focus moves to the in-card alert**, keyed on the error state rather than raised inside the handler — the alert node does not exist yet when the state is set (`BoardSection.tsx:308-319`). **The failure path is the one that gets forgotten.**
  4. A card that leaves the list while holding focus hands focus to the panel `h2` — F51's shipped pattern (`StaffSection.tsx:80-92`), **no new string and no stranded-card mechanism**.
- ⚠ **A tick may not repaint while a pointer is down on the panel**, and `usePoll` deliberately does not supply this (Task 9) so **this component must write it**: the since-line renders only when `break_started_at` is set, so a remote break starting on card 2 grows it ≈20px and slides every control below it — and at 375 the control is on its own line, i.e. exactly the thing that moves. `pointerdown` holds the next repaint; `pointerup`/`pointercancel` releases it; the loop keeps its beat underneath, so a lost `pointerup` costs at most one interval and can never stall the panel. **Mechanically: `run` returns `"held"`**, so the hook re-arms at the current gap without resetting the backoff (Task 9).
- ⚠ **Bidi, per interpolation and not per string**: `{{time}}` and `{{minutes}}` go through `isolateLtr` (`lib/booking.tsx:32-46`, which emits `<bdi dir="ltr">` — correct for a numeric run). **`{{name}}` does NOT** — `isolateLtr` on «נועה לוי» puts `dir="ltr"` on a Hebrew name, which deck §2.1 calls out as *"itself a bidi defect, and it looks deliberate"*. The two break `aria-label`s and both cues carry `{{name}}`, so they need a bare-`<bdi>` interpolation: a two-line `isolateBidi(text, value)` sibling in `lib/booking.tsx`, or `<Trans>`. **There is no test named for this** and axe cannot see it, unlike the SC 2.2.2 row.
- **P-6: a break toggle answering 403 is TERMINAL** — the whole panel goes to F-403, via `poll.fail(error)` on the same `{401,403}` rule the ticks use. **A 404 is NOT** and stays an in-card `floor.error.notFound` alert (**C10**).

**Named tests:** cards render name, role **word** and status **word**; a card on a break shows the since-line; the break control patches the card **from the response**, is disabled while in flight, and a double-tap fires one request; **after a FAILED toggle the loop keeps polling** (the re-arm — the test that would still pass if it were dropped, and so would every other test here); **a successful toggle returns focus to the tapped control**; **a failed toggle moves focus to the in-card alert**; **the announced region does not change across several consecutive ticks with the cue already populated** and does change on a toggle and on a pause; the pause control stops the loop and resume fetches immediately at the base gap; the idle stop fires and names its cause; a failed poll with cards on screen keeps them and marks stale; a first-fetch failure shows the outage register; **a 401 and a 403 each show the terminal panel and stop — two tests**; **a toggle's 403 is terminal and a toggle's 404 is an in-card alert — two tests**; **the break control is absent on other people's cards for a non-elevated role and present on her own** (asserted **as cosmetics**); an **axe pass at zero violations**.

⚠ **The axe pass is explicitly NOT sufficient. axe has no SC 2.2.2 rule**, so the pause and idle assertions are the only automated coverage of a legally binding Level A criterion. The floor-program review warns about this for F34; **the deck's F-8 says it applies twice as hard here, because F34 at least had a deck a user could have read and this gate had nobody behind it.** These tests must not be cut as redundant with the axe row, now or in any later tidy-up.

- **Done when**: `make fe-test` + `make fe-build` green; every state in the deck's §4 has a named `it(...)`; axe at zero violations; **`Nav.test.tsx` green with `getFloor` in its mock**; both render branches wired with the panel after the board.
- Commit: `feat(manage): the floor staff-cards panel, its 5s loop, its pause control and its nav row`.

## Task 12 — F51's role select widens, and the ternary that would mislabel a seamstress is fixed (D14 / deck P-8)
`Frontend/apps/manage/src/components/StaffSection.tsx`, `…/__tests__/StaffSection.test.tsx`

Three edits and nothing else on that surface:

- `:99-100` — `roleWord` stops being `role === "owner" ? t("staff.roleOwner") : t("staff.roleShiftManager")` and reads `ROLE_LABEL_KEY`. **Left as it is, this migration silently labels a seamstress «אחראית משמרת»** — the frontend form of "widening the enum silently widens nothing", and a real defect this feature creates if the plan does not name it. Both the spec's D14 and the deck's P-8 name it for that reason.
- `:242-243` and `:373-374` — five `<option>`s each, labels from `ROLE_LABEL_KEY`.
- `:304-305` — the badge is **already safe** and is not touched: the word carries the role and the colour never does.

**No backend change** — Task 7 already proved the request schemas widen with zero edits. **No new screen state, no new component, no new copy** beyond the three role words.

**Tests:** both selects offer five options; **a seamstress row renders «תופרת»** (the assertion that fails against the un-fixed ternary).

- **Done when**: `make fe-test` + `make fe-build` green with no assertion edits in `StaffSection.test.tsx` beyond the new cases.
- Commit: `feat(manage): widen F51's role select to the five staff roles`.

## Task 13 — Gates and the run report
No files.

Run the full verification below, report what ran and what passed, and state **explicitly** whether the `db`-marked suites were executed locally against a throwaway cluster or are debuting on CI. Carry forward in the run report:

- **Risk 10 — the privacy hand-off, re-nagged.** `break_started_at` is a record of a named employee's working pattern and no privacy notice covers it. **F20 (`spec_gate: user`) must carry a staff-break entry: purpose = floor operations, retention = with the staff record.** No build work here.
- **Risk 2 — hand F29 the number rather than let it discover one.** The board screen now polls **twice** per beat. Per floor tick, per device: **3 sessions, ~6 statements, ~11 round trips, 3 pool checkouts**, so the board screen goes from ~17 round trips per 5 s to **~28**. Ten phones on one tenant is ~150 statements/s. `tenants.by_slug` is uncached **per request** (`tenancy/resolver.py:8-9`) and is now paid **twice per beat** — still the cheapest lever, and still F29's.
- **Risk 1 — the walker assertion is load-bearing for the next three features.** F36, F58 and F37 all add `/manage` routes and the first two will want to extend the floor router. `test_the_floor_roles_reach_exactly_the_floor_routes` must never be relaxed to a subset check.
- **Risk 3 — `usePoll` now carries two of F34's shipped fixes for four future callers.** A reviewer seeing **any** edit to `BoardSection.test.tsx` should stop and read D10.
- **Deck F-1 — on a forty-row day the panel sits ~4.5 screens below the fold** for the two roles that also have a board. The placement is forced (above the board it would push the board's one-shot `scrollIntoView` target out of view). **Handed to F36**, which adds the second panel to the same stack; the cheap remedies are a second in-page skip link or a grouped floor section.
- **Deck F-4 — two idle timers on one screen will always fire together**, because both are reset by the same global interactions. Correct, slightly redundant, and **not merged** because merging means shared state above both panels. Handed to F36/F58, at which point four idle notices become a design problem rather than a footnote. **The auditory half is fixed in copy here**: `floor.idleStopped` names its region («עדכון הצוות הופסק אחרי…»), because the shipped `board.idleStopped` is byte-identical and both write into a `role="status"` region — one sentence heard twice. A copy change, one line, the user's to edit post-merge.
- **Deck F-10 — `floor.outage` is not shipped; F51's `staff.loadFailed` is reused.** A copy decision made by the decks, not the user, and it sets the precedent for where F37/F41/F42/F59 put shared strings: reuse a key whose **namespace names its subject**, never one whose namespace names a screen. One `he.ts` line to overturn.
- **Deck F-11 — `{{name}}` needs a bare-`<bdi>` interpolation helper that does not exist yet**, because the shipped `isolateLtr` emits `dir="ltr"` and that is a bidi defect on a Hebrew name. Two lines in `lib/booking.tsx`. **No test is named for it and axe cannot see it** — the same shape as the SC 2.2.2 row, and on a legally binding surface.
- **C8 — two of the spec's Hebrew strings were revised by the deck** on a WCAG 2.5.3 finding and a duplication finding. The Hebrew remains the user's to edit post-merge — a one-line `he.ts`/`ar.ts` edit, never a rebuild.
- **C10 — P-6 (a toggle's 403 is terminal) was decided by the deck, not the user.** One `poll.fail(error)` call to overturn.

No push, no PR — the orchestrator owns review and shipping.

---

## What a local run cannot prove

Without Docker or the throwaway cluster, `pytest -m db` collects and skips.

| Task | Proof that is CI-only (or cluster-only) | What the local run still gives |
|---|---|---|
| **2** (roles + migration + column) | the round trip, the nullable `TIMESTAMPTZ` type, the widened-CHECK validation on a populated table, **the deparsed constraint literal**, the downgrade's honest failure | `ruff` + `mypy app tests` resolving `StaffRole.SEAMSTRESS` and `StaffUser.break_started_at` at every call site |
| **3** (the break writers) | **every assertion** — `populate_existing` against a real identity map is not reproducible with a fake | `mypy` over the new signatures |
| **8** (the whole db module) | all of it, including the forced interleave and the RLS probes | `mypy` over `tests` |

Everything in Tasks 0, 1, 4, 5, 6, 7 and 9–12 verifies locally. **Task 5 is the backend milestone**: the first point at which the route, the gate, the tenant trust path and the wire shape are exercised end to end with no Postgres. **Task 9 is the frontend milestone**: the first point at which the extraction is proven faithful, by 61 `it(` blocks nobody edited **plus the two `TickOutcome` tests those blocks cannot cover**.

⚠ **Two backend test failures are always false locally** — `test_config.py` picks up `Backend/.env` leaking `MEDIA_BUCKET` (`.memory/local-env-breaks-config-tests.md`). CI is green. Do not chase them.

---

## Testing plan → spec criteria

| Spec / deck criterion | Where |
|---|---|
| `StaffRole` widens to five; `'sales_assistant'` not `'sales'` | `test_migrations.py` (`db`, iterating the enum) + `test_staff_api.py` (fast) |
| The CHECK widens by DROP + ADD and validates a **populated** table, both halves | `test_migrations.py` (`db`) — the `:154-189` sibling |
| The widened constraint definition **pinned byte-identical after this feature's migration** | `test_migrations.py` (`db`) — ⚠ **capture the deparsed literal, do not transcribe it** |
| The downgrade **fails loudly** on a floor-role row | `test_migrations.py` (`db`) |
| `break_started_at` is a nullable `TIMESTAMPTZ`; the migration round-trips both ways | `test_migrations.py` (`db`) |
| No table snuck in | `test_every_tenant_id_table_has_forced_rls` (`db`, **unedited**) |
| Idempotent by predicate off a `.returning()` scalar + a `populate_existing` re-read | `test_staff_repositories.py` (`db`) |
| **A start racing an end renders the DATABASE's value, not its own** | `test_floor_db.py` (`db`, **forced interleave**) — the mutation-check target |
| **A second start keeps the FIRST timestamp and reports no write** | `test_floor_db.py` (`db`) |
| owner/shift_manager on anyone; any staffer **on herself** | `test_floor_service.py` (fast) |
| **A non-elevated caller on another is refused AND the target repository is never called** | `test_floor_service.py` (fast) — the 403-is-not-an-existence-oracle assertion |
| `(wrote, row)` → 200 / 200-unchanged / 404; an audit row on a write and **none** on a no-op; `previous_break_started_at` | `test_floor_service.py` (fast) |
| `StaffCardStatus` is `{available, break}` and **nothing else** | `test_floor_api.py` (fast, **set equality**) — fails if `occupied` is pre-added |
| Three routes wired, authenticated, `no-store`, no `/manage` shadow | `test_floor_api.py` `ROUTES` (fast) + `test_no_route_is_registered_twice_across_routers` (**unedited**) |
| `SPEC_ERROR_CODES` gains **no member** | `test_floor_api.py` (fast, set equality) |
| **The three floor roles reach exactly the three floor routes and nothing else** | `test_staff_role_gating.py::test_the_floor_roles_reach_exactly_the_floor_routes` (fast, **four assertions, live route table**) |
| The floor gate actually **raises**, not merely carries `allowed_roles` | `test_staff_role_gating.py:371` (fast, **no floor fake wired** — C3) |
| Nothing in the owner/shift_manager matrix changed | `test_route_table_matches_the_permission_matrix` + `OWNER_ONLY` (fast, **unedited**) |
| The 403 body still names no role, now over five | `test_the_not_authorized_contract_is_pinned_by_literal` (fast, **unedited**) |
| RLS isolation — tenant B ⇒ 404, indistinguishable from missing | `test_floor_db.py` (`db`) |
| F51's guards survive the widening: last-owner, self-demote, `STAFF_ROLE_CHANGED` details | `test_staff_service.py` + `test_staff_api.py` (fast, **no `app/auth/` diff**) |
| **A request unresolved at unmount arms nothing** | `usePoll.test.tsx` — **F34's shipped blocker, proven at the layer it now lives in** |
| The six poll mechanisms, 401 and 403 **separate**, backoff caps and resets, `fail()` classifies a mutation error | `usePoll.test.tsx` |
| **The extraction is faithful on the six mechanisms** | `BoardSection.test.tsx` — **passing UNEDITED is the acceptance gate**, and it is **necessary, not sufficient** |
| **The extraction is faithful on the two early returns** — `"held"` re-arms at the backed-off gap, `"suppressed"` arms nothing | `usePoll.test.tsx` — the two divergences `BoardSection.test.tsx` does not cover |
| **The floor roles are classified on the INTERSECTION of a route's gates, never `any(...)`** | `test_staff_role_gating.py::test_the_floor_roles_reach_exactly_the_floor_routes` — sanity-checked by adding `RECEPTION` to `dashboard/router.py`'s gate and confirming red |
| **SC 2.2.2** — pause stops, resume fetches immediately at the base gap, the idle stop fires and names its cause | `FloorPanel.test.tsx` — **the only automated coverage; axe has no rule for it** (deck F-8) |
| The announced region does not change **across several consecutive ticks with the cue already populated** | `FloorPanel.test.tsx` — the F-7 shape; a single-tick assertion passes against the broken version |
| **A successful toggle returns focus to the tapped control; a failed one moves it to the in-card alert** | `FloorPanel.test.tsx` — the bug class that shipped **twice** and that axe missed **twice** |
| **A toggle's 403 is terminal; a toggle's 404 is an in-card alert** | `FloorPanel.test.tsx` (deck P-6 / C10) |
| Status, role and paused all carry words, never colour alone | `FloorPanel.test.tsx` + `StaffSection.test.tsx` |
| The break control is absent on colleagues' cards for a non-elevated role — **asserted as cosmetics** | `FloorPanel.test.tsx` |
| Zero axe violations on the panel | `FloorPanel.test.tsx` (`axe-core`, **already a devDependency**) |
| The three roles see exactly one nav row and land on it; owner ten / shift manager eight **unchanged** | `Nav.test.tsx` — fails if `board` was widened instead of `floor` added |
| Every `floor.*` key and every `ROLE_LABEL_KEY` value resolves, in both files | `i18n.test.ts` |
| A seamstress renders «תופרת» in F51's table | `StaffSection.test.tsx` — fails against the un-fixed ternary |
| Every new formatter is zoned | **nothing new to check** — F57 adds no formatter; `qa-greps.sh` output must be **byte-identical to the baseline** |

**No E2E is promised**, and the reason is F34's verbatim: the console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend (`e2e/a11y.spec.ts:10-13`). **F58 owns the `/manage/**` interception harness.** Recorded rather than silently skipped — and it is Risk 9: two concurrent polls on boutique wifi with one of them slow is exactly what fake timers model least faithfully.

---

## What could go wrong in review

Every item here is a **recorded ruling**, not an open question. A reviewer who raises one should find the reasoning rather than file a finding.

1. **"F34's spec and the floor-program review both say `usePoll` must NOT be extracted."** They say F34 must not pre-extract it, *because F57's queue entry claims it* — and F34's D13 named this exact reopening condition: *"the day there is a second caller the extraction is mechanical and reviewed."* F57 is that caller. **Compliance with both documents, not a reversal**, and D10's zero-edit rule is what makes it reviewable. The most likely finding in the review.
2. **"A 744-line component that merged four days ago was rewritten."** Only its loop moved. The acceptance rule is mechanical and visible in the diff: **`BoardSection.test.tsx` is unchanged.** If it is not, the extraction is wrong and D10's escape hatch applies.
3. **"The floor router admits five roles — every other `/manage` route admits at most two."** True, new, and deliberate (spec conflict 7). The floor payload carries **zero customer data**. `test_the_floor_roles_reach_exactly_the_floor_routes` is what keeps "first" from becoming "first of many by accident".
4. **"`require_role(*StaffRole)` is a hole — a sixth role gets in for free."** It is, on **this** router, deliberately: the set it admits *is* "every role the product has". It is safe **only** because D5's assertion pins the floor roles out of everywhere else. Both halves ship in this PR or neither should.
5. **"The deck contradicts the spec's Hebrew."** **Three times**, and all three times the deck is right (**C8** + Task 1): «השהיית עדכון הצוות» fails WCAG 2.5.3 label-in-name against a visible «השהיה» (§9 **F-2**); «בהפסקה מ־14:20» repeats the Badge directly above it (**F-3**); and `floor.outage` is dropped for the shipped `staff.loadFailed` (**F-10**). Each is raised in the deck's own §9 *specifically so this would not read as drift*.
6. **"A break toggle's 403 blanks the whole panel — that's aggressive."** Deck **P-6** (**C10**). The alternative is an in-card alert plus a loop that keeps polling with a role the server just refused: the panel disagreeing with itself for up to five seconds and then doing the same thing anyway. The realistic cause is a mid-shift demotion the next tick would have found. **A 404 is not terminal**, and that asymmetry is the point.
7. **"There is a design deck but the spec says the design gate self-approves."** Both are true. Q2 removed the *gate* — the prototype, the `design-critic` pass, the user's pause — not the design work. The deck's own header states what self-approval costs and discharges it into §7.4.
8. **"`copy.md` is new in this PR and the deck references it as if it existed."** It **did** exist — written a minute before `design.md`, fully authored, 32 keys invented and 4 reused, C8's corrections already in it. An earlier draft of this plan claimed otherwise and had Task 1 author it; that would have **overwritten** 27 KB of untracked, unrecoverable copy. **C9** carries the correction, and Task 1 is now a reconciliation pass. **A reviewer seeing `copy.md` as an untracked new file in the diff is seeing it added to git, not written in this task.**
9. **"Pre-decided #24 names the slug `'sales'`."** Overridden by the user's 2026-07-31 roles ruling (spec conflict 1).
10. **"`constants.py` and `0011` both say these roles wait for E6-proper."** Spec conflict 2. Read as the bar being **met** rather than waived: the roles arrive **with** a consumer in the same PR. Both comments are rewritten to record that; neither is deleted.
11. **"The `UNKNOWN_ROLE` comment is now stale."** Spec conflict 3, and it is edited to the past tense in both files. **The sentinel and its tripwire are untouched and stay green**; the day it anticipated arrived and it held.
12. **"Two pause controls on one screen is a defect."** D12 / deck §1.2: two independently updating regions with two independent loops need two mechanisms, and one control would mean lifting pause state into a shared parent — the exact coupling D11 forbids. The requirement is distinguishable accessible names, which is a test.
13. **"Why two polls on one screen instead of one merged endpoint?"** D11, and the reason is **security**, not load: merging would put `customer_name` behind a gate that admits a seamstress, or would need the per-role projection `dashboard/router.py:9-11` already declined for a weaker case. The floor-program review pre-sanctioned the cost.
14. **"`occupied` is obviously coming — why not ship the literal now?"** D9. It is exactly what `ScheduledMessageKind`, `GatewayCredentialStatus` and `StaffRole`'s own pre-F57 comment refuse; `PaymentStatus`'s departure is written up as a **risk**, not a precedent. The set-equality test is what makes "structurally impossible" mean more than "currently unreached". The deck's §2.3 even pre-books `neutral` for it, so F36 adds **no new colour** either.
15. **"A staffer without permission sees no control at all — shouldn't it be disabled with an explanation?"** Deck §2.2: a disabled control with no explanation is worse than an absent one; an explanation would teach the permission model on a screen she opens fifty times a shift, to answer a question she did not ask; and any such affordance would be the client asserting a rule the server owns. **The absence is asserted as cosmetics.**
16. **"A break has no upper bound."** Risk 4 / deck F-6, deliberate (D7). Every automatic end is a guess about a shift and there is no roster to guess from. The since-line is the mitigation and it is a real one: «מאז 11:20» on a card at 09:00 the next morning is obviously wrong to any reader, where a bare «בהפסקה» would not be.
17. **"The break toggle's 403 could be an existence oracle."** It cannot, and a test proves it: the check runs **before any read of the target**, and `test_floor_service.py` asserts the target repository was **never called**.
18. **"`test_dashboard_api.py` says six routers mount `/manage`."** True today, false after this merge (**C5**). A historical note in another feature's test module; the floor module's own docstring carries the new count.
19. **"`test_gate_admits_listed_roles` should have gained the three roles."** No — that would assert a two-role gate admits a floor role, which is false and dangerous (**C1**). It gained a **new** case instead.
20. **"The audit rows are write-only."** Risk 8, F15's Risk 7 and F34's Risk 7 unchanged. F53's activity log is the first read surface.
21. **"`ar.ts` gained ~33 hand-copied Hebrew values with nothing checking them."** Risk 7 / deck F-5, inherited from F15 through F34. No parity guard is invented here; the mitigation is that both columns come from one `copy.md` table. F45 owns the real fix.

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
make test-db   # cd Backend && pytest -m db -q   <- CI, or locally per the § above
```

**Green looks like:**

- **`make lint`** — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`**, `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` **exit 0** printing **exactly the pre-existing baseline** (seven `ok` lines, then `review  date reads` listing `HoursSection.tsx:15` and `TermsSection.tsx:9` **and nothing else**). F57 adds no formatter, so **any third line is F57's regression**.
- **`make test`** — all fast tests pass; `test_floor_api.py`, `test_floor_service.py`, `test_staff_role_gating.py`, `test_staff_service.py` and `test_staff_api.py` green; the `db`-marked modules **collected and deselected**. `test_route_table_matches_the_permission_matrix`, `test_gates_admit_only_known_roles`, `test_the_not_authorized_contract_is_pinned_by_literal`, `test_no_route_is_registered_twice_across_routers` and `test_frontend_constant_parity.py` pass **unedited**. ⚠ Two `test_config.py` failures are the known local `.env` leak.
- **`make fe-test`** — **`BoardSection.test.tsx` green with a zero-line diff**; `usePoll.test.tsx`, `FloorPanel.test.tsx`, `Nav.test.tsx`, `StaffSection.test.tsx` and `i18n.test.ts` green; axe at **zero** violations on the panel.
- **`make fe-build`** — both apps build; no unused-import or unused-variable TS error (the most common local red after a refactor — the loop's constants and refs leaving `BoardSection.tsx` is exactly that shape).
- **`make e2e`** — the existing storefront and console specs stay green. **F57 adds no e2e spec**, so an unchanged e2e count is the expected result, not a gap.
- **CI additionally**: `make test-db` green, including the widened-CHECK validation on a populated table, the pinned deparsed constraint literal, the migration round trip both ways, the downgrade's honest failure, the forced-interleave race and the RLS isolation probes. **A first red on a test bug here is budgeted** if the local cluster was skipped.
- **Working tree clean of the pre-run**: `git status` shows no `tests/conftest.py` diff and no cluster data directory.

---

## Out of scope (unchanged from the spec and the deck)

Fitting rooms, occupancy and the `occupied` status (F36) · dispatch, take-next, push-assign, the waitlist (F58) · SOS, the overlay, the escalation (F37) · queue tickets, the public check-in form, the wall board (F33, F59) · break history, break duration reporting, "who was on a break when" (no table — D2) · a maximum break length, an auto-end sweep, a worker tick (D7) · on-shift/off-shift marking and a published roster (F40, pre-decided #33) · **any per-role narrowing of an existing route** (`OWNER_ONLY` untouched) · a staff avatar, photo, phone number or email on the card · **a two-column card grid, an aggregate summary line, a hoisted self-card, emoji status dots** (deck P-1/P-3/P-4/P-5, each with its upgrade path recorded) · **a frequency picker, a second interval or any new constant** (deck P-7) · **any new colour token** (deck §6 — F36's `occupied` takes the shipped `neutral`) · **rebuilding F51's staff CRUD** (D14 / deck P-8) · the tri-lingual top bar and any language switcher (2026-07-31 languages ruling) · a he/ar parity guard (Risk 7 / deck F-5) · the `/manage/**` Playwright interception harness (F58) · **the privacy notice and processing-activities entry for `break_started_at`** (F20, `spec_gate: user` — Risk 10) · a skip link past the board or a grouped floor section (deck F-1, handed to F36).
