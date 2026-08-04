# Plan: Feature 60 — Per-page guided walkthrough (the «מדריך» button), cross-cutting, LAST in the floor program

**Status**: Gate 2 self-approved 2026-08-04 under Interview Q1 (standing approvals; F60 is none of Q1's six enumerated exceptions — no payments, no refunds, no privacy-law text, no billing). **LOOP-STATE governs**: the F60 entry's `note:` and `rulings_2026_07_31` are binding and are not re-litigated here.

**Spec**: `.planning/specs/guide-walkthrough.md` (475 lines · D1–D8 · DL1–DL21 · 27 review findings, 26 applied, 1 rejected)
**Decks**: `.planning/design/screens/guide-walkthrough/design.md` (design gate self-approved, no prototype) · `.../copy.md` (**canonical for every string**)
**Branch**: `feature/guide-walkthrough` · **Worktree**: `.worktrees/guide-walkthrough` · **Created**: 2026-08-04

TDD throughout. Every task states its **failing test first**, then the code that makes it pass, then the exact files, then how to verify, then the commit message. `✚` marks a new file.

**Effort: S.** Two new source files, two two-line prop additions, three lines in `App.tsx`, twelve lines on `/checkin`, 45 strings, two test files. **No migration, no endpoint, no dependency.**

---

## Path and tooling hygiene — read before every task

**Quote every shell path.** The repo path contains a space *and* a `+`.

**Git tracks `frontend/` lowercase while the on-disk directory is `Frontend/`.** `git add Frontend/…` silently skips modified tracked files. Lowercase every pathspec and verify every commit with `git show --stat`. (`.memory/git-add-uppercase-pathspec-trap.md`.)

**One other worktree is live**: `.worktrees/seamstress-capacity` on `feature/seamstress-capacity` (F42). Verified with `git worktree list` on 2026-08-04. **Do not touch it.** F42's blast radius is `AtelierSection.tsx` + `staff_users`; F60's is `App.tsx`, `i18n/{he,ar}.ts`, `packages/ui`, `CheckinPage.tsx`. The one shared file is `i18n/{he,ar}.ts` and both diffs are **append-shaped** — keep it that way.

**`make lint` runs `frontend/scripts/qa-greps.sh`, which greps WHOLE FILES INCLUDING COMMENTS** (`qa-greps.sh:23`, a bare `grep -rnE`). Its seven `check` calls are scoped to `SRC="apps/storefront/src"` (`:17`) — **the console and `packages/ui` are NOT scanned by them**; only the trailing unzoned-date *review* block reads `apps/manage/src` and `packages/ui/src`. So the hazard surface for F60 is exactly **Task 7** (`CheckinPage.tsx` and the storefront bundle), and it is a prose hazard, not a code one:

| Pattern (`qa-greps.sh`) | What trips it in F60's style |
|---|---|
| `:34` `favorit\|localStorage\|heart` | a comment saying "no `localStorage` key" — and DL16 is *about* not having one, so this is the likeliest single failure in the feature |
| `:40` `[^a-zA-Z-](ml-\|mr-\|pl-\|pr-\|left-\|right-\|text-left\|text-right\|border-l-\|border-r-)` | ordinary English prose: "left-hand", "right-hand", "the right place" |
| `:42` `#[0-9a-fA-F]{6}\b` | a hex quoted in a contrast note |
| `:38` `₪` | ⚠ **`guide.types.2` quotes «מקדמה (₪)» — and that lands in `apps/manage/src/i18n/he.ts`, which this check does not read.** Safe as written. It would fail if the same string were ever moved to the storefront bundle. |

**Capture the `make qa-greps` baseline in Task 0 and diff it at Task 7 and Task 9.** A new `FAIL` line from F60 is prose, and the fix is the prose.

**There is no migration and no db-marked test in this feature.** `alembic heads` on this tree prints **`0022 (head)`** (verified 2026-08-04). It must print the same thing, one head, at the end. There is nothing here for the MIGRATION CHAIN rule to resolve.

---

## What moved since the spec was written — every citation re-verified on 2026-08-04

The spec was written **the same day** as this plan and its code reading is unusually accurate: `Modal`'s fifteen call sites, `SosOverlay`'s composite `dismissKey`, `sos.tsx`'s append, `App.tsx`'s fourteen sections, the jsdom stub and `Nav.test.tsx`'s eleven/thirteen all check out exactly. **Seven things do not.** One is a BLOCKER.

### ✅ Verified on this tree — do not re-check

- ✅ `frontend/apps/manage/src/App.tsx` — `SectionKey` **`:24-41`, fourteen members**, in the shipped order `dashboard · profile · hours · types · terms · catalog · bookings · customers · board · staff · gateway · floor · checkinQr · atelier`, with the three ordinal comments (`// F57's floor — the TWELFTH member since F53 added customers.` `:35`, `// F33's printable check-in code — the THIRTEENTH.` `:37`, `// F41's atelier — the FOURTEENTH.` `:39`). `NAV` **`:83-152`, fourteen rows**, in the order `dashboard · profile · hours · types · terms · catalog · bookings · customers · board · floor · atelier · checkinQr · staff · gateway`. **The two orders differ and D1's table follows `NAV`, correctly.** `reachable` `:194`, `activeKey` `:208-210` with `reachable[0]?.key ?? section`, `nav` `:211`, `<SosOverlay />` `:236` **before** `<ConsoleShell` `:237`, the `FloorPanel` beneath the board `:258-263`, `activeKey === "floor"` `:264`. Every `NAV` row's `labelKey` is exactly `` `nav.${key}` `` — used by **P-1**.
- ✅ `frontend/packages/ui/src/components/Modal.tsx` — 57 lines. `ModalProps` `:5-12` (`footer?` `:12`), the `:7` backdrop comment (**describes what `onClose` means; no `onClick` is bound anywhere**), the `[open]` effect `:25-33` with `dlg.showModal()` **`:29`** and `dlg.close()` `:31`, `onCancel` `:38-42`, **`onClose={onClose}` `:43`**, `aria-labelledby` `:44`, **no `role` attribute**, `{children}` rendered unconditionally **`:53`**, footer `mt-6 flex justify-end gap-3` **`:54` with no `flex-wrap`**.
- ✅ **Fifteen production `<Modal` call sites**, enumerated by grep, byte-for-byte the spec's list: `HoursSection:319` · `AtelierSection:1101` · `AtelierSection:1242` · `SosRaiseDialog:190` · `TypesSection:306` · `RoomHandoverDialog:53` · `RoomsRegistryDialog:279` · `RoomsRegistryDialog:413` · `BookingDetail:624` · `BookingDetail:655` · `MediaGallery:526` · `RoomDressDialog:93` · `DressEditor:405` · `StaffSection:411` · `RescheduleDialog:103`.
- ✅ `frontend/packages/ui/src/components/ConsoleShell.tsx` — `banner?` `:19`, `progress?` `:20`, the header row `flex … justify-between px-4 py-3` **`:46`** with **exactly two children** (`:47` the name span, `:48-50` the logout `<button>` carrying `text-sm text-ink-muted hover:text-ink` + `focusRing`), `<nav>` `:56`, `</header>` `:82`, `<main id="console-main" tabIndex={-1}>` `:84`.
- ✅ `frontend/packages/ui/src/index.ts` — `ModalProps` `:31` and `ConsoleShellProps` `:75` are **already exported**. No edit.
- ✅ `frontend/apps/manage/src/components/SosOverlay.tsx` — the "NOT a `<dialog>`, NOT `showModal()`" paragraph `:15-27`; **`dismissKey` `:59-61` = `` `${alert.id}:${alert.escalated}:${alert.stalled}` ``** with its "escalation and the stall each re-rise the card exactly once" rationale `:51-58`; `risingIds` `:129`, **`risingKey = risingIds.join()` `:134`**, `risingIdsRef` `:135-136`; MOVE A's `hadCardsRef` consume `:198-199` and its `document.activeElement === document.body` guard **`:203-205`**; the document **capture** Esc listener's `document.querySelector("dialog[open]") !== null` early return **`:298`** and `event.preventDefault()` **`:312`**; the per-device dismiss `:322-330`; the red field `fixed inset-0 z-40 … bg-danger` **`:451`**.
- ✅ `frontend/apps/manage/src/api.ts` — `SosAlert` `:628`, `escalated` `:646`, `stalled` `:647`, `for_me` `:648`.
- ✅ `frontend/apps/manage/src/lib/sos.tsx` — the merge's append and its "appending keeps the oldest-first order the read establishes" comment `:128-131`; the poll's wholesale `setAlerts(result.alerts)` **`:145`**.
- ✅ **Stronger than the spec's citation, and use this one**: `frontend/apps/manage/src/lib/sos-context.ts:18-19` declares the contract in as many words — `` /** Live alerts visible to this caller, oldest first. */ alerts: SosAlert[]; ``. Backed by the server: `Backend/app/db/repositories/sos_alerts.py:245` is `.order_by(SosAlert.created_at)`, **ascending**. A new page therefore arrives at the **end** of the array on every path — the merge *and* the poll.
- ✅ `frontend/apps/manage/src/components/CheckinQrSection.tsx` is **99 lines**; `FloorPanel` 904 + `RoomsPanel` 1116 + `WaitlistPanel` 901 = **2 921** lines. Deck F-8 stands.
- ✅ `grep -c useTranslation` is **0** for `HoursSection.tsx`, `TypesSection.tsx`, `TermsSection.tsx`, `CatalogSection.tsx`. Deck F-4 stands, and **every Hebrew label `copy.md` quotes from those four is byte-present in its component** — spot-verified for all 22 (`יום`, `פתיחה`, `סגירה`, `קיבולת`, `סגור כל היום`, `הערה`, `תאריך`, `הסרת תאריך חריג`, `משך (דקות)`, `קהל יעד`, `נדרשת מקדמה`, `מקדמה (₪)`, `סדר תצוגה`, `העברה לארכיון`, `כלות בלבד`, `עריכה`, `מחיר בתיאום`, `אזל מהמלאי`, `אין תמונות`, `החזר מלא עד (שעות לפני התור)`, `אחוז חילוט מחוץ לחלון`, `תוכן מדיניות הביטולים`), plus `TermsSection`'s shift-manager line «יש לפנות לבעלת הבוטיק כדי להגדיר מדיניות ביטולים.».
- ✅ **All 32 shipped `he.ts` keys `copy.md` cites exist** (`profile.publicNotice`, `gateway.writeOnlyNotice`, `board.updatedAt`, `waitlist.assign`, `atelier.stage.intake`, `checkinQr.urlHint`, `staff.deactivateCta`, …). R1's failure mode is drift, not absence.
- ✅ `frontend/apps/manage/src/i18n/he.ts` — the nested `nav: { profile, hours, types, terms, catalog }` **`:14-20`** and nine flat `"nav.*"` literals (`:61, 251, 314, 430, 506, 607, 684, 1172, 1214`); the merge-conflict-zone note `:424-429`; 1 799 lines. `ar.ts` 728 lines.
- ✅ `frontend/apps/manage/src/__tests__/i18n.test.ts` — `entries()` `:19-23`; twelve `HE_F##` constants; the **fold** `HE = [...]` `:78-91`; the register guards `describe("the register, mechanically")` `:1027-1037` (`includes("!")`, `/נשלח|תישלח|בדרך/`); `describe("the ar bundle")` `:1039+` with the presence guard and **three value-parity twins** (`HE_F36` `:1054`, `HE_F58` `:1066`, `HE_F37` `:1080`) — the shape D8 copies. **No source-file scanner anywhere in the file.** R7 stands.
- ✅ `frontend/apps/storefront/src/__tests__/i18n-keys.test.ts` — `SRC` `:17`, `SECTIONS = new Set(Object.keys(he.translation))` **`:21`**, `DOTTED_LITERAL` `:22`, the first-segment filter **`:39`**, `resolve(key, bundle)` `:41-51`, `USED_KEYS` `:53-59`, the three `it.each(USED_KEYS)` blocks `:62-100`, `F19_KEYS` `:106-113` and its **presence**-only `ar` guard `:145-150`, the empty-string walk `:152-168`.
- ✅ `frontend/apps/storefront/src/i18n/he.ts:408` `checkin: {` · `ar.ts:77` the same. `checkin.notice` and `checkin.optIn` are the counsel-gated pair, **amended by F59** to name the public queue board («עמוד אינטרנט ציבורי»), pinned by `i18n-keys.test.ts:133-142`. **F60 touches neither.**
- ✅ `frontend/apps/storefront/src/routes/CheckinPage.tsx` — 338 lines. `pageClass` `:22`, the chips' `min-h-11 min-w-11` `:35`, the loading arm `:214`, the no-boutique arm `:234-248` with the retry `Button size="md"` `:242`, the `pointer` offer and its "An OFFER, above the form, never a redirect" comment **`:254-266`**, the first `<Input>` (name) **`:268-276`**, the notice comment and `<p>` **`:296-305`**, the opt-in checkbox `:308-313`, the submit `Button size="md"` `:314-324`.
- ✅ `frontend/e2e/fixtures/manage.ts` — `MANAGE` `:37`, `Reply`/`ok`/`refuse` `:86-128`, `Recorder` `:139`, `staff()` `:155` (**default role `reception`**), `sosAlert()` `:351` (id `"sos-1"`, `for_me: true` by default, `escalated`/`stalled` settable directly), `sosPayload()` `:375`, `installManageApi()` `:404-463`, `sosPath()` `:473`.
- ✅ `frontend/e2e/sos.spec.ts` — the "jsdom cannot answer it" preamble `:23-49`, **"this repo has shipped a focus-drops-to-`<body>` defect five times" `:30-35`**, `retarget()` `:139-147`, `axeViolations()` `:150-158`, `card()`/`row()` `:170-182`.
- ✅ `frontend/packages/ui/src/__tests__/Modal.test.tsx:18-34` — "Esc (cancel) dismisses without firing the confirm action", which fires a bare `new Event("cancel", { cancelable: true })` at `getByRole("dialog")`. This is `onCancel`'s existing pin and **`getByRole("dialog")` resolves in jsdom** (implicit role, no attribute), so the E2E locator rule is also true in vitest.
- ✅ **The jsdom stub, in all three `src/test/setup.ts` files, is byte-identical** and is `this.open = true` for **both `showModal` and `show`**, plus a `close()` that flips `open` and dispatches a `close` event. jsdom is **29.1.1** and `node_modules/.pnpm/jsdom@29.1.1/.../HTMLDialogElement-impl.js` exists as the empty subclass. **No `cancel` event on Esc, no focus move, no top layer, and `show()` and `showModal()` are indistinguishable in vitest** — which is exactly why T1–T5's named deletion is a Chromium-only signal.
- ✅ `frontend/apps/manage/src/__tests__/Nav.test.tsx` — `NAV_LABELS` `:88`, `toHaveLength(13)` **`:219`**, the shift-manager `.slice(0, 11)` at `:152` and `:267`, and `expect(NAV_LABELS).not.toContain("הצוות בקומה")` `:218`. **F60 edits none of it**, and that is an assertion.
- ✅ `frontend/.oxlintrc.json` — `plugins: ["react","oxc"]`, `"react/rules-of-hooks": "error"`. `Makefile` — `lint`, `test`, `fe-test`, `fe-build`, `e2e`, `qa-greps`. Every workspace `test` script is `TZ=America/New_York vitest run`. `axe-core ^4.12.1` is in **both** apps' `package.json`.
- ✅ `frontend/apps/manage/src/lib/booking.tsx:75-87` — `isolateLtr` splits on **`text.indexOf(value)` at `:76`**. Deck F-3's refutation stands (and the helper lives in **`apps/manage`**, not the storefront).
- ✅ `frontend/apps/storefront/src/router.tsx:200-214` — the `handOff` docstring naming the import cycle in which `vi.mock`'s live binding silently resolves to the real function. DL3's citation is sound.
- ✅ `.planning/LOOP-STATE.md` `known_flaky` — the `ManageBookingPage.test.tsx :: the cancel two-step :: moves focus into the revealed block` entry is the **only** frontend one. DL14 / deck §6.3 stand.

### C1 — **BLOCKER. There is no login block to copy, and writing one is dead code.**

The spec's E2E section says: *"There is no shared login helper: `guide.spec.ts` copies `sos.spec.ts`'s local login block (`const LOGIN_SUBMIT = "כניסה"` plus the fill-and-submit steps, about six lines)."*

**No such block exists in either file.** `installManageApi` authenticates by *not* authenticating, and says so at `e2e/fixtures/manage.ts:14-17`: *"`App.tsx` bootstraps on `api.me()` and renders `<LoginForm/>` on a rejection, so fulfilling `GET /manage/auth/me` with a 200 `Staff` body is the whole of «signed in» — no cookie, no login POST, no session table."* `grep -n LOGIN_SUBMIT e2e/*.ts` returns exactly **four** hits and every one is a **negative** assertion — `manage.spec.ts:37`/`:171` and `sos.spec.ts:53`/`:407`, both `expect(page.getByRole("button", { name: LOGIN_SUBMIT })).toHaveCount(0)`, i.e. *"the console did NOT fall back to login"*.

**Resolution:** `guide.spec.ts` opens with `await installManageApi(page, { staff, replies })` then `await page.goto(MANAGE)` and a settle assertion. **No login constant, no fill, no submit.** A builder who follows the spec literally writes six lines that either time out on a form that never renders or pass vacuously. The rest of the spec's E2E paragraph — the `getByRole("dialog")` locator rule, the positive-focus-assertion rule, the "no shared helper to extract" scope note — is correct and stands.

### C2 — `useSos()` **throws** outside `SosProvider`, so the vitest block has a mandatory harness

`lib/sos-context.ts:32-40`: *"Loud rather than inert. A component that reads this outside the provider is one that would render a permanently empty emergency channel."* Four shipped test files carry the same warning comment (`FloorPanel.test.tsx:10-14`, `SosRaiseDialog.test.tsx:32`, `RoomsPanel.test.tsx:24`, `RoomDressDialog.test.tsx:17`).

**Resolution:** `GuideOverlay.test.tsx` copies `SosCentre.test.tsx`'s harness verbatim rather than inventing one — `vi.mock("../api")` with the nine floor/sos fns, `render(<SosProvider>…</SosProvider>)`, `vi.useFakeTimers({ shouldAdvanceTime: true })`, `getSos.mockResolvedValue(sosPayload([...]))`, and an `advance(ms)` helper wrapping `vi.advanceTimersByTimeAsync` in `act()`. **Declined: `vi.mock`ing `../lib/sos-context`.** It is one line shorter and it stubs the exact mechanism §6 exists to measure — the provider's array identity across a poll tick.

**And the import is `from "../lib/sos-context"`, not `from "../lib/sos"`.** All four shipped consumers import it from there (`SosOverlay.tsx:8`, `SosCentre.tsx:8`, `SosRaiseDialog.tsx:6`, `sos.test.tsx:8`); the split exists so `sos.tsx` keeps fast refresh.

### C3 — the spec never says who translates the section name into `guide.title`. **P-1 decides it.**

`D2` says the title is `t("guide.title", { section })` where `section` is "the already-translated nav label"; `GuideOverlayProps` is `{ section: SectionKey }`. Those two cannot both be true without a mechanism.

**Resolution — `GuideOverlay` derives it: `t(`nav.${section}`)`.** Verified sound: every one of the fourteen `NAV` rows has `labelKey === `nav.${key}``, five resolve through the nested `nav:` object (`he.ts:14-20`) and nine through `ignoreJSONStructure`'s flat fallback (`he.ts:61` etc.), and deck F-6 records that both paths work and that **neither may be "fixed" against the other**. Cost: zero props, zero expressions in `App.tsx`, zero new keys.

**Reconciling with DL5** ("steps are declared as full key literals, never built from a template"): DL5's argument is that the console has **no source scanner**, so `HE_F60`'s `startsWith("guide.")` filter is the only thing that can see a step key, and a filter can only count literals. `nav.*` is outside that namespace, is indexed by a **closed, compiler-checked union**, and a miss would already render the raw key in the nav row `ConsoleShell` paints on every section. Named test in Task 2: all fourteen `` `nav.${key}` `` resolve to something other than the key.

### C4 — deck F-1 is right and the spec's *Every state* row is wrong

*Narrow viewport* says three `size="md"` footer buttons *"wrap rather than shrink"*. `Modal.tsx:54` is `flex justify-end gap-3` with **no `flex-wrap`**. The conclusion survives on deck §2.6's arithmetic (≈243px of buttons in a 295px content box at 375). **Amend the spec's mechanism; do not add `flex-wrap` to `Modal`** — that is a fifteen-call-site edit this feature has not earned.

### C5 — four small citation drifts, re-captured

(a) `TermsSection`'s `const isOwner = role === "owner"` is **`:21`**, not `:20`. (b) `AtelierSection`'s `mayWork` is **`:1356`** (the comment runs `:1347-1355`), not `:1344`. (c) `SosOverlay`'s "five times" sentence is **`e2e/sos.spec.ts:30-35`**, not `:32-35`. (d) The nested `nav:` block closes at **`he.ts:20`**; the five labels are `:15-19`.

### C6 — one copy-deck rationale is wrong; the string is not

`copy.md` §3 justifies `checkin.guideHint` avoiding «שליחה» because *"the submit button already owns it"*. The submit is **`checkin.submit` = «הצטרפות לתור»** (`he.ts`), not «שליחה». The *rule* is unaffected — the hint still avoids the banned roots and both approved strings stand unchanged. Recorded so a reviewer diffing the deck against `he.ts` does not think the string drifted.

### C7 — the guide's detector reads **all** `for_me` alerts, including dismissed ones, and it must

`SosContextValue` (`sos-context.ts:22-36`) exposes `alerts`, `serverNow`, `terminal`, `channelDown` and the four verbs. **`dismissed` is `SosOverlay`'s own `useState` and is not on the context**, so `GuideOverlay` *cannot* filter it out — which is the correct behaviour anyway: a dismissed alert whose `escalated` flips re-rises the card, and the guide must close for that. Stated here because a reviewer will ask why the detector does not mirror `SosOverlay`'s `rising` (which *does* subtract `dismissed`). It must not. §6b is the test that a *persisting* dismissed alert still lets her reopen.

---

## Scope fence — read this before every task

**F60 ships an overlay of sentences. It ships no capability, calls no endpoint, and writes no row.**

| Not in F60 | Why |
|---|---|
| **A migration** | There is no state. `alembic heads` is `0022 (head)` before and after. |
| **An endpoint** | Nothing is fetched, stored or sent. |
| **ANY new dependency** — a tour library, a focus-trap library, a popper, a positioner | LOOP-STATE's fence. ⚠ **A builder who reaches for a tour library has misread the feature.** The three things such a library sells are: a focus trap — already in this repo, native `<dialog>` + `showModal()`, trusted by fifteen call sites since F5; a positioning engine — **out of scope, because nothing is anchored** (§2.3 of the deck); and a step state machine — `useState(0)`. Adding one would ship ~200 KB and a second focus authority to replace eleven lines. |
| A hand-rolled Tab/Shift+Tab cycle over a focusable-selector list | ~60 lines of the exact code this repo has got wrong five times. **The fence bans a dependency; the platform is not one** (DL1). LOOP-STATE's "focus trap and Esc-to-close are the real work here" is true about *where the risk is*, not about *what must be written*. |
| Anchoring, highlighting, spotlighting, a cut-out, a scroll-to | Deck §2.3. It is the whole reason no dependency is needed. |
| A first-visit auto-open, a "seen" flag, a storage key, a dot on the trigger | DL16. An overlay that opens itself steals focus from a receptionist mid-phone-number. |
| A `flex-wrap` on `Modal`'s footer; a backdrop-click dismiss; any other `Modal` change beyond `describedById?` | Fifteen call sites. C4. |
| A nav row, a `SectionKey`, a `NAV` edit, a `Nav.test.tsx` edit | `SectionKey` stays **fourteen**. The guide is a header control. |
| Repairing `SosOverlay.tsx:12`'s "thirteen sections", `:612`'s "eleven sections", `App.tsx:230`'s "eleven sections" | Spec *Codebase conflicts* 3. True when F37 merged, overtaken by F41 and F33. **A drive-by comment repair inside an emergency component is the unrelated diff this program's review sends back.** |
| Repairing the «מקדמה»/«פיקדון» split | `copy.md` C-2. F60 uses «מקדמה» throughout and edits neither payments block. |
| A per-section `aria-label` on the trigger (`guide.triggerAria`) | DL20. 2.5.3 is true by construction without it. |
| Widening the storefront's new `ar` value-parity check beyond the two `checkin.guide*` keys | DL21. |
| Extracting a shared Playwright login helper | There is nothing to extract (**C1**). |

If a task's diff grows a fetch, a storage write, a package.json dependency, a nav row or a second focus authority, it has left F60.

---

# The plan — ten tasks

## Task 0 — This plan, the seven spec amendments, and the qa-greps baseline
`.planning/plans/guide-walkthrough.md` (this file ✚), `.planning/specs/guide-walkthrough.md`

No test, no code. Amend the spec so it is the binding statement of every resolution above:

- **Testing → E2E** — delete the "copies `sos.spec.ts`'s local login block" sentence and replace it with **C1**: `installManageApi` *is* the authentication, `grep -n LOGIN_SUBMIT e2e/*.ts` returns four negative assertions and no login flow. Keep the locator rule, the positive-focus rule and the "no shared helper to extract" scope note verbatim.
- **Testing → Frontend** — add **C2**: the vitest block mounts inside `<SosProvider>` because `useSos` throws outside it, copies `SosCentre.test.tsx`'s harness, and imports from `../lib/sos-context`.
- **D2 / Per-component behaviour** — add **C3/P-1**: `GuideOverlay` derives the title's section label as ``t(`nav.${section}`)``, with the DL5 reconciliation and the fourteen-key resolve test.
- **Every state → Narrow viewport** — replace "wrap rather than shrink" with **C4** and point at deck §2.6's arithmetic.
- **Citations** — `TermsSection.tsx:21`, `AtelierSection.tsx:1356`, `e2e/sos.spec.ts:30-35`, `he.ts:14-20` (**C5**).
- **D6 / DL12** — add **C7**: `dismissed` is not on the context, the detector reads every `for_me` alert deliberately, and that is what makes an escalation re-rise of a dismissed page close the guide.
- Record **C6** in the *Codebase conflicts* list (the deck's «שליחה» rationale; the strings stand).

Then, **before any frontend file is touched**:

```
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen" \
  && make qa-greps > "<scratchpad>/qa-greps-baseline.txt" 2>&1; echo "exit=$?"
```

Commit the baseline nowhere; keep the file. Tasks 7 and 9 diff against it.

- **Done when**: C1–C7 are in the spec; `grep -n "LOGIN_SUBMIT\|login block" .planning/specs/guide-walkthrough.md` returns nothing; `grep -n "wrap rather than shrink" .planning/specs/guide-walkthrough.md` returns nothing; the baseline file exists and its `exit=` is recorded here.
- **Commit**: `docs(planning): F60 implementation plan and seven spec amendments — Gate 2 self-approved`

---

## Task 1 — `lib/guide.ts`: the union moves, the table is compiler-forced (D1, D2, DL3, DL4)
`frontend/apps/manage/src/lib/guide.ts` ✚, `frontend/apps/manage/src/__tests__/GuideOverlay.test.tsx` ✚

### The failing test first — `GuideOverlay.test.tsx` §1

Written before `guide.ts` exists, so it fails on the import.

1. **the table covers every section, by SET EQUALITY** — `new Set(Object.keys(GUIDE_STEPS))` equals the fourteen literals, spelled out in the test rather than derived from anything (a test that derives its expectation from the thing under test proves nothing). And `Object.values(GUIDE_STEPS).every(s => s.length > 0)`.

⚠ **No `SosProvider` is needed for §1** — it imports a module, renders nothing.

### The code

```ts
// frontend/apps/manage/src/lib/guide.ts
export type SectionKey = /* App.tsx:24-41 VERBATIM: same fourteen members, SAME
   ORDER, and the three ordinal comments moved with them. Reordering the union
   during the move is a diff a reviewer reads for nothing and costs the record
   of who added what. */;

export const GUIDE_STEPS = {
  dashboard: ["guide.dashboard.1", "guide.dashboard.2"],
  // …the other thirteen, in NAV order (D1's table), full key literals (DL5)
} as const satisfies Record<SectionKey, readonly [string, ...string[]]>;
```

**`guide.ts` imports nothing from `App.tsx`, and the direction is not negotiable.** Declaring `SectionKey` in `App.tsx` and importing it here creates the cycle `router.tsx:200-214` documents, where `vi.mock`'s live binding resolves to the real module inside `importActual` and the test passes while asserting nothing.

**"No steps" is a type error, not a runtime branch** (DL4). `readonly [string, ...string[]]` makes an empty tuple unrepresentable and `pnpm --filter manage typecheck` gates the merge, so **AC1's second half is verified by the build, not by a test**. A runtime `if (steps.length === 0) return null` would need an injection seam invented only to reach it.

**`index` needs no clamp**, and this is a considered omission rather than a forgotten one: `index` is local state, `section` is a prop, and the only writer of `activeKey` is `ConsoleShell`'s `onNavigate`, which `showModal()` has made inert. If a later feature ever changes `section` programmatically, `key={section}` on `<GuideOverlay>` costs one token.

### Mutation-check

| Mechanism | Remove it | Expect |
|---|---|---|
| `satisfies Record<SectionKey, …>` | drop one section from `GUIDE_STEPS` | `pnpm --filter manage typecheck` **RED** — and §1 red too |
| §1's set equality | add a fifteenth key `foo: [...]` | §1 **RED** (the type also complains) |

- **Done when**: `pnpm --filter manage test -- src/__tests__/GuideOverlay.test.tsx` green; `pnpm --filter manage typecheck` clean. **`App.tsx` is untouched in this commit** — its local `type SectionKey` is deleted in Task 6, so the tree stays compiling at every commit.
- **Commit**: `feat(manage): the guide step table, keyed by SectionKey and forced by the compiler`

---

## Task 2 — 45 strings, the `HE_F60` block, and the storefront's first value-parity guard (D8, DL5, DL20, DL21)
`frontend/apps/manage/src/i18n/he.ts`, `.../i18n/ar.ts`, `frontend/apps/manage/src/__tests__/i18n.test.ts`, `frontend/apps/storefront/src/i18n/he.ts`, `.../i18n/ar.ts`, `frontend/apps/storefront/src/__tests__/i18n-keys.test.ts`

**`copy.md` is canonical.** Transcribe from it, not from `design.md`'s diagrams and not from D1's table. **Every step must be read back against its section component before it is committed** (R1) — and for `hours`, `types`, `terms` and `catalog` the component **is the only place the words exist** (deck F-4, verified: `grep -c useTranslation` = 0 for all four). A quoted label is byte-identical to the shipped one or it is not quoted.

### The failing tests first — `i18n.test.ts`

Follow the shipped block-per-feature shape exactly:

```ts
// NO `nav.` term, and that is an assertion rather than an omission: F60 adds no
// nav row — SectionKey stays fourteen, NAV stays fourteen, Nav.test.tsx needs no
// edit — and `guide.trigger` is a header control, not `nav.guide`.
const HE_F60 = entries(he.translation, (key) => key.startsWith("guide."));
```

1. `expect(HE_F60.length).toBeGreaterThanOrEqual(43);`
2. **`...HE_F60` spread into `HE`** (`i18n.test.ts:78-91`), plus the shipped **"is FOLDED into HE, not merely declared"** twin: `expect(HE.map(([k]) => k)).toContain("guide.trigger")`. The file states four times that a declared-and-unspread block silently skips the resolve check, **both** register guards and the `ar` guard.
3. `it("adds no nav row, and that is an assertion rather than an omission")` — `HE_F60.filter(([k]) => k.startsWith("nav."))` is `[]` **and** `"nav.guide" in he.translation` is `false`. (`HE_F37`'s twin at `:906-909`.)
4. **`ar` VALUE parity**, the fourth twin beside `HE_F36`/`HE_F58`/`HE_F37`: `HE_F60.filter(([k, v]) => arTranslation[k] !== v)` is `[]`. Presence alone passes on an English string, a `TODO`, or a *different* Hebrew wording.
5. **P-1's loop** — for each of the fourteen `SectionKey` literals, `` i18n.t(`nav.${key}`) `` is not the key itself. Five resolve through the nested object and nine through the flat fallback; this is the one test that proves the constructed title lookup is total.
6. `it("interpolates the section, step and total placeholders")` — `t("guide.title", { section: "לוח היום" })` is «מדריך — לוח היום»; `t("guide.progress", { step: 2, total: 3 })` is «שלב 2 מתוך 3 במדריך». ⚠ **The trailing «במדריך» is load-bearing twice** (deck F-3 / copy §1): it keeps both digits between Hebrew words, and it names which of the console's `role="status"` regions is speaking. `isolateLtr` is **not** the alternative — it splits on `indexOf` (`lib/booking.tsx:76`), so on «שלב 3 מתוך 3» it isolates the *first* 3.
7. **No 2.5.3 loop** — there is no `*Aria` key in this block (DL20), and that absence is stated in a comment rather than left to be discovered.

**`i18n-keys.test.ts`** gains **one** `it` inside the existing `describe("the ar bundle")`, and it must be written as a **value** check: `resolve("checkin.guideTrigger", ar.translation) === resolve("checkin.guideTrigger", he.translation)`, same for `guideHint`. Say in its comment that the F19 block beside it (`:145-150`) is a **presence** check and that **the storefront has never had a value-parity guard anywhere** — this is the first, deliberately scoped to two keys. No scanner edit: `checkin` is already in `SECTIONS` (`he.ts:408`), so the dotted-literal scan (`:21`, `:39`) picks both keys up the moment `CheckinPage.tsx` renders them in Task 7.

### The code

- **Console**: 43 flat dotted literals appended to `he.ts` — **the nested `nav:` object at `:14-20` stays untouched** (`he.ts:424-429`: it is the file's merge-conflict zone while sibling features land, and F42 is live). 7 chrome keys (`guide.trigger`, `guide.title`, `guide.progress`, `guide.next`, `guide.prev`, `guide.done`, `guide.close`) + 36 steps. Mirrored in `ar.ts` with **the approved Hebrew value**, never `""` (i18next's `returnEmptyString` default renders the empty string rather than falling back, and would blank the dialog).
- **Storefront**: two keys under the **existing** `checkin` section (`he.ts:408`, `ar.ts:77`) — `checkin.guideTrigger`, `checkin.guideHint`. Not a new top-level namespace (DL21).

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| the `...HE_F60` spread | delete it from `HE` | test 2's fold twin **RED** (and the register + `ar` guards silently stop covering 43 strings — which is the point) |
| the `ar` value guard | change one `ar.ts` value to a different Hebrew wording | test 4 **RED**; the shipped presence guard stays **green** |
| the storefront value guard | change `ar.checkin.guideHint` to English | the new `it` **RED**; `F19_KEYS`' presence guard and the empty-string walk stay **green** |
| the `>= 43` floor | delete four step keys from `he.ts` | test 1 **RED** — and §1's set equality (Task 1) **RED**, which is the only thing standing between the deck and a dead key (R7) |

⚠ **The register guards now cover 43 more strings.** `guide.bookings.3` is the one at genuine risk of `/נשלח|תישלח|בדרך/` — "what the customer is told about a reschedule" is a sentence about messaging. `copy.md` resolves it by wording rather than by dodging: the step says what the console **records** and then says it is not evidence of what reached her handset, which is also the true statement (`booking.deliveryNotice` exists because the platform swallows send errors). Zero `!` and zero banned roots across all 45 values — `copy.md` §4's scan, re-run as part of this task.

- **Done when**: `pnpm --filter manage test` and `pnpm --filter storefront test` green; every mutation-check performed and restored; the scan in `copy.md` §4 re-run by hand against the two bundles.
- **Commit**: `feat(i18n): the guide's 43 console keys, its two storefront keys and their he/ar guards`

---

## Task 3 — `packages/ui`: one optional prop each on `Modal` and `ConsoleShell` (D3, DL2, DL18)
`frontend/packages/ui/src/components/Modal.tsx`, `frontend/packages/ui/src/components/ConsoleShell.tsx`

⚠ **`Modal` is gate-passed and has FIFTEEN production call sites** (R2), two of them inside `AtelierSection` (the console's largest component, and the file F42 is live in) and two inside `BookingDetail`. **AC18 is the whole unit suites, not four named files** — fifteen call sites cannot be verified by naming four.

### The failing test first

There is none of F60's own in `packages/ui`. **`describedById`'s test lives in `apps/manage`** (Task 4 §7) because the assertion that matters is *the dialog's `aria-describedby` is the id of the element carrying the current step's Hebrew*, and that is a `GuideOverlay` fact. `packages/ui`'s job here is to stay byte-identical when the prop is omitted, which is what the shipped suites already assert.

### The code — four lines total

```ts
// Modal.tsx — ModalProps gains one line, the <dialog> gains one attribute
describedById?: string;   // → aria-describedby. Omitted → React writes nothing.
```

```tsx
// ConsoleShell.tsx — ConsoleShellProps gains `guide?: ReactNode`, and the header
// row's two children become two GROUPS. The wrapper is not cosmetic (DL18):
// :46 is `flex … justify-between` with exactly TWO children today, so a bare
// third child spreads to the middle and the boutique name, the guide and the
// logout end up evenly distributed — the two chrome controls stop reading as a
// pair.
<div className="flex items-center gap-4">
  {guide}
  <button type="button" onClick={onLogout} …>{logoutLabel}</button>
</div>
```

**`packages/ui/src/index.ts` is NOT edited** — `ModalProps` (`:31`) and `ConsoleShellProps` (`:75`) are already exported and both new fields ride along.

**No `flex-wrap` on the footer** (C4) and **no backdrop `onClick`** (spec *Codebase conflicts* 5 — the `:7` comment describes what `onClose` *means*, and none of the fifteen callers relies on a backdrop route out).

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `aria-describedby={describedById}` | delete the attribute | Task 4 §7 **RED**. ⚠ **Without §7, the whole of D3 could be dropped at build time and every other listed test would stay green** — which is why DL2 gives it its own AC. |
| `describedById?` being optional | make it required | `pnpm --filter ui typecheck` **RED** at all fifteen call sites — the fastest possible proof that omission is the default |
| the `flex items-center gap-4` wrapper | render `{guide}` bare | no test reddens; this is a **visual** claim measured by deck §1.1 and the T1–T6b locators, and it is recorded as such rather than pretended to be tested |

- **Done when**: `pnpm --filter ui test` green (**`Modal.test.tsx` included, unedited**), `pnpm --filter manage test` and `pnpm --filter storefront test` green — **AC18**. `pnpm -r typecheck` clean.
- **Commit**: `feat(ui): Modal gains an optional describedById, ConsoleShell a header guide slot`

---

## Task 4 — `GuideOverlay`: the trigger, the dialog, the step machine, the live region (D3, D4, D5, DL8–DL10, DL19, DL17)
`frontend/apps/manage/src/components/GuideOverlay.tsx` ✚, `frontend/apps/manage/src/__tests__/GuideOverlay.test.tsx`

⚠ **DL17 IS THE RULE FOR THIS WHOLE TASK: no vitest test in this feature may assert `document.activeElement`, `dialog[open]`-driven focus, Tab order, or Esc-through-`cancel`.** Verified above: jsdom 29.1.1 ships no `<dialog>` implementation and all three `setup.ts` stubs are `this.open = true` for **both `show` and `showModal`**, with no `cancel` event. Every such assertion would measure the stub. §7 is the one permitted exception because it is a plain IDREF read with no focus and no `<dialog>` behaviour in it. **Every focus criterion is Task 8's.**

### The failing tests first — `GuideOverlay.test.tsx` §2–§5, §7

Harness per **C2**: `vi.mock("../api")`, `<SosProvider>`, fake timers, `getSos.mockResolvedValue(sosPayload([]))` in `beforeEach`.

2. **the guide shows the active section's steps** — render at `section="floor"`, click «מדריך», assert `guide.floor.1`'s Hebrew is on screen and `guide.dashboard.1`'s Hebrew is **absent** (AC6).
3. **it never opens itself** (AC7) — render with alerts present *and* absent, `advance(POLL_INTERVAL_MS * 3)`, assert `document.querySelector("dialog")?.hasAttribute("open")` is false until the trigger is clicked. ⚠ **An attribute read, not a role query** — a closed `<dialog>` is a jsdom grey area and `getByRole` must not be trusted for it.
4. **the controls** (AC8, AC19) — «סגירה» present on step 1 **and** on the last step; «הקודם» **absent** on step 1 (`queryByRole` → null), present on step 2; the primary reads «הבא» on steps 1..N-1 and **«סיום»** on the last; «סיום» closes. No focus assertion anywhere, so DL17-safe.
5. **the region announces on change, not on open, and never carries a stale sentence** (AC9) — open, assert the `role="status"` node is empty; «הבא», assert step 2's text; «הקודם», assert step 1's text (**going back announces, and that is correct**); then **close, rerender at a different `section`, reopen, assert empty again**. ⚠ **That last leg is the only one that fails if `setAnnounced("")` is missing** — the first leg is true on a session's first open regardless, because the region has never held anything.
7. **`aria-describedby` points at the step** (AC5) — open at `section="floor"`, read `screen.getByRole("dialog").getAttribute("aria-describedby")`, assert it is non-null and is the `id` of the element whose text is `guide.floor.1`'s Hebrew.

### The code

`GuideOverlay.tsx`, ~95 lines. State: `open: boolean`, `index: number`, `announced: string`. `useId()` for the body id.

**The trigger** — a bare `<button type="button">` matching the logout button's register exactly (`ConsoleShell.tsx:48`: `text-sm text-ink-muted hover:text-ink` + `focusRing`), **plus `min-h-11 px-2`** for `tokens.md` law 7. ⚠ **Consequence, deliberate and stated rather than discovered in review (deck F-5): the console header grows from ≈52px to ≈68px on every section.** The background is transparent so the box is invisible; visually it is still two text labels side by side. **Not a `Button variant="ghost"`** — that is `font-semibold text-base` and would outrank the logout beside it. **No icon, no dot, no `aria-label`** (DL20).

**The `onClick`, in this exact order**: `setIndex(0)` → `setAnnounced("")` → reset the skip-first ref → `setOpen(true)`. So the dialog opens on step 1 every time, with an empty live region, and a reopen never resumes mid-walkthrough nor re-announces the previous section's sentence.

**The dialog** — `<Modal open={open} onClose={close} title={t("guide.title", { section: t(\`nav.${section}\`) })} describedById={bodyId} footer={…}>`. Body: the counter `<p>` (`text-sm text-ink-muted`), the step `<p id={bodyId}>` (`text-base text-ink`), then the `sr-only <p role="status">`.

⚠ **`text-ink` on the step paragraph is NOT the F15 F-6 override trap, and the deck says so because a reviewer will reach for it** (§2.2): F-6 is a call-site utility losing a same-property fight **on the same element**; here `Modal.tsx:53` puts `text-ink-muted` on the wrapper `<div>` and the step is a **child `<p>`** carrying its own colour. An element's own declaration beats an inherited value — no specificity contest, no stylesheet-order dependency.

**The footer, in DOM order** (deck §2.5, DL19), following `SosRaiseDialog:196-201`'s house pattern — dismiss first, primary last:

| DOM | Label | Variant | Present on |
|---|---|---|---|
| 1 | «סגירה» | `ghost` | **every step** |
| 2 | «הקודם» | `secondary` | steps 2..N |
| 3 | «הבא» → «סיום» on the last | `primary` | every step |

⚠ **F60 ships this console's FIRST three-control `Modal` footer** (deck F-2, verified: all fifteen call sites render at most two — `SosRaiseDialog:190-215`'s three are two ternary branches, `RescheduleDialog`'s third is in the body). The cited house pattern is a **two**-control shape, which is why deck §2.6 measures the row (≈243px in a 295px content box at 375) instead of inheriting it.

⚠ **«סגירה» is not optional.** `Modal` binds no backdrop click and the chrome has no X, so without it step 1 of a 3-step guide is a top-layer dialog containing exactly one control, and a boutique tablet or a 375px phone — no Esc key — can only leave by tapping through to «סיום».

⚠ **«הקודם» is ABSENT on step 1, not disabled** (DL10). Inside a focus trap every Tab stop is one she must walk past, and `Button.tsx:57` is `disabled={disabled || loading}`, which blurs a tapped control and drops focus. **This is an argument against dead controls, not against controls** — DL19's dismiss and DL10 are not in tension.

⚠ **Nothing in F60 calls `.focus()`.** `showModal()` puts focus on the first focusable descendant, which per the DOM order above is «סגירה» — a labelled, non-destructive control, with the step announced by `aria-describedby` regardless. Adding `autofocus` or a manual move on top of the platform's entry is two engines deciding one thing, which is the class of defect D4.1 refuses.

**The live region — four properties, each one line, each got wrong elsewhere in this repo:**

1. **Never conditionally mounted.** `Modal.tsx:53` renders `{children}` whether `open` is true or false, so the region lives for the dialog's whole lifetime, hidden only by the UA's `display:none`. Remounting a live region re-announces it, on every unrelated re-render of the section behind.
2. **Content is state**, written by `useEffect(…, [index])` — **never `t(steps[index])` inline**. `AtelierSection.tsx:445-449` records the mechanism: assigning a string to a text node is a real childList mutation inside `role="status"` **even when the two strings are byte-identical**, and `setState` with an equal value is a React no-op — **so the `setState` is the guard**.
3. **The effect skips its first run after open**, via the ref reset in the `onClick`. Without it, open announces twice — once through `aria-describedby`, once through the region.
4. **The region is CLEARED on open.** Because of (1) and (3), without this it still holds **the last step of the previously visited section** and transitions from `display:none` to exposed carrying that stale sentence, which several ATs announce. Invisible on a session's first open — which is why §5 has the close-navigate-reopen leg.

**Step changes move no focus** (D4.6, DL8). Four steps cost four presses, not four presses plus four Tabs. ⚠ **On the last step «הבא» becomes «סיום» in the same position** — the control under her finger changes identity, deliberately: same slot, labelled, and the alternative (a disabled «הבא» beside a «סיום») puts a dead control inside a trap.

### Mutation-checks (mandatory)

| Mechanism | Remove it | Expect |
|---|---|---|
| `setAnnounced("")` in the `onClick` | delete it | §5's **close-navigate-reopen leg** RED; every other leg green |
| the skip-first ref | delete the reset | §5's first leg RED (the region carries step 1 on open) |
| `setAnnounced` as state → inline `t(steps[index])` in the JSX | swap it | §5 stays green ⚠ — **this is a real-AT claim, not a jsdom one**, and it is handed to the manual screen-reader pass. Recorded rather than pretended to be tested. |
| «סגירה» from the footer | delete it | §4 RED, **and T6b RED** (Task 8) |
| «הקודם»'s absence on step 1 | render it disabled | §4 RED |
| `aria-describedby={describedById}` (Task 3) | delete the attribute | §7 RED |

- **Done when**: `pnpm --filter manage test` green; every mutation-check performed and restored; `pnpm -r lint` clean (oxlint's `react/rules-of-hooks` is `error` — the `useSos()` call is unconditional and first).
- **Commit**: `feat(manage): the guide overlay, its step machine and its announcement contract`

---

## Task 5 — The SOS-over-guide interaction: **the emergency wins** (D6, DL11, DL12, DL13, C7)
`frontend/apps/manage/src/components/GuideOverlay.tsx`, `frontend/apps/manage/src/__tests__/GuideOverlay.test.tsx`

**This is the only way this feature can hurt anybody, and it is its own task for that reason.**

The mechanism, stated plainly because it is counter-intuitive: `showModal()` promotes the dialog to the browser's **top layer**, which paints above every `z-index` in the document — including `SosOverlay`'s `z-40` (`:451`) — and makes every node outside the dialog **inert**: unclickable, unreachable by Tab, invisible to hit-testing. So with the guide open, an arriving emergency page is not merely covered, it is **unanswerable**. **There is no z-index, no portal and no stacking context that changes this. Raising `SosOverlay` above a top-layer dialog is not possible.** Closing the guide is the only mechanism that exists (DL11).

### The failing tests first — `GuideOverlay.test.tsx` §6, four legs

Driven through the shipped `SosProvider` harness (**C2**): change `getSos.mockResolvedValue(sosPayload([...]))`, then `advance(POLL_INTERVAL_MS)`.

- **(a) zero → one `for_me` alert**: open the guide, deliver one alert, assert the `<dialog>`'s `open` attribute is gone.
- **(b) rerender with the SAME alert list**: the trigger **reopens** it (DL12). ⚠ Without this, a staffer who dismissed a page could never open the guide again — the level-trigger failure.
- **(c) one alert already seen, guide reopened, then a SECOND arrives appended at the end** (`[A]` → `[A, B]`): `open` is gone. ⚠ **Fails against any head-of-list detector**, because `alerts` is oldest-first on both paths (`sos-context.ts:18`'s contract, `sos_alerts.py:245`'s `ORDER BY created_at`, `sos.tsx:128-131`'s append), so a new page lands at the **end** — and that is precisely the case where a top-layer dialog is most dangerous, since the second emergency lands under a dialog the first one already failed to close.
- **(d) the same alert's `escalated` flipping `false` → `true`, no id change**: `open` is gone. ⚠ **Fails against any id-only detector.** `SosOverlay.dismissKey` (`:59-61`) is composite *precisely* because escalation at t=30s and the stall at t=2min each re-rise a dismissed card exactly once — F37's safety net for "the first responder did not come".

### The code

```ts
const { alerts } = useSos();   // from "../lib/sos-context"

// ⚠ THE KEY IS THE COMPOSITE SosOverlay ALREADY USES (`dismissKey`,
// SosOverlay.tsx:59-61), NOT THE BARE ID. Escalation and the stall each RE-RISE
// a dismissed card under the SAME id — that is F37's safety net for «the first
// responder did not come» — so an id-keyed detector is structurally blind to
// exactly the alert this guard exists for. A CHANGE TO ONE KEY IS A CHANGE TO
// BOTH.
//
// ⚠ And it reads EVERY for_me alert, dismissed ones included. `dismissed` is
// SosOverlay's own state and is not on SosContextValue — which is correct as
// well as unavoidable: a dismissed page whose `escalated` flips re-rises the
// card, and the guide has to get out of its way.
const forMe = alerts
  .filter((a) => a.for_me)
  .map((a) => `${a.id}:${a.escalated}:${a.stalled}`);

// SosOverlay:129-136's shape: a joined string is the dependency, a ref carries
// the live list, because the array is rebuilt every render.
const risingKey = forMe.join("|");
const forMeRef = useRef<readonly string[]>(forMe);
forMeRef.current = forMe;
// Seeded with what is ALREADY live at mount (DL12).
const seenRef = useRef<readonly string[]>(forMe);

useEffect(() => {
  const keys = forMeRef.current;
  // ⚠ SET DIFFERENCE, NEVER THE HEAD OF THE LIST. `alerts` is oldest-first
  // (sos-context.ts:18, sos_alerts.py:245), so a NEW page ARRIVES AT THE END:
  // any test on keys[0] never fires while an older page is still live.
  const grew = keys.some((k) => !seenRef.current.includes(k));
  seenRef.current = keys;
  if (grew) setOpen(false);
}, [risingKey]);
```

**Edge and not level, and that is half the decision.** `if (forMe.length > 0) setOpen(false)` would close the guide on **every 5s poll tick** for as long as a live-but-dismissed alert exists, so a staffer who dismissed a page could never open the guide again. Dismissal here is deliberate and per-device (`SosOverlay:322-330`).

**Only a `for_me` page closes it** (deck §5.4). The channel-down strip and the "N hidden" affordance are not full-screen, are not urgent, and closing a walkthrough for them would be noise.

**The «מדריך» button is NEVER disabled or hidden during an emergency** (DL13). Either one ships the sixth focus-drops-to-`<body>` defect: if her focus is on the trigger when the alert lands, `close()` returns focus to a control the same commit has just removed and Chromium drops to `<body>`. It is also what makes T8's setup reachable at all.

**Effect ordering, and what the spec deliberately does NOT assume.** `SosOverlay` is mounted at `App.tsx:236`, before `ConsoleShell` at `:237`, so its effects flush first — in the commit in which the alert arrives, while the guide is still open. The invariant is **not** "focus is on the trigger": `showModal()` moved focus **into the dialog**. Whether `document.activeElement` can degrade to `<body>` after a click on non-focusable dialog content is **engine-dependent and must not be assumed either way** — which is exactly T4's setup. So MOVE A's `document.activeElement === document.body` guard (`:203-205`) may read true, and if it does, `cardRefs.current.get(ids[0])?.focus()` runs against a node `showModal()` has made inert: a no-op, with `hadCardsRef` already set, so MOVE A is **consumed for that alert and will not fire again**.

**That outcome is accepted, not engineered around, and the layout-effect fix is declined in writing** (spec *Rejected findings*). Focus is not lost: `close()` returns it to the labelled «מדריך» button — a better destination than MOVE A's own by F37's reasoning, since MOVE B's fallback is `#console-main` — and Esc from there reaches «אני מגיעה» in one keypress the moment `dialog[open]` stops matching. Converting this effect to `useLayoutEffect` would buy back one focus move whose absence costs nothing, in exchange for an invisible cross-component ordering dependency between two components that share nothing but a context — unpinnable by any test that does not already have to exist, and the first thing broken by an unrelated React bump. **T7 leg (b) measures it in Chromium instead.**

⚠ **One thing the spec does not say out loud and this plan does** (deck F-7): "focus returns to the «מדריך» button" and "the red page is on screen" describe **the same pixels**. `SosOverlay.tsx:451` is `fixed inset-0 z-40 … bg-danger` — opaque and full-screen — so the returned focus sits on a button now underneath the emergency, with an invisible focus ring. **Not a WCAG 2.0 AA failure**: SC 2.4.7 Focus Visible requires a visible indicator *for the focused element*; focus-not-obscured is **SC 2.4.11, WCAG 2.2**, and IS 5568 is 2.0 AA. It lasts one keypress, and every alternative is a worse defect. **Handed to the manual screen-reader pass on this PR** — along with the FRAME 2 sequence, a `role="alert"` mounting in the same commit a `<dialog>` leaves the top layer, which is the one interaction in this feature no automated tool in this repo can observe.

### Mutation-checks (mandatory — R4's three named failure modes)

| Mechanism | Break it | Expect |
|---|---|---|
| edge, not level | `if (forMe.length > 0) setOpen(false)` | §6b **RED** (the trigger can no longer reopen it) |
| set difference, not head-of-list | `keys[0] !== seenRef.current[0]` | §6c **RED**; a, b, d stay green |
| composite key, not bare id | `.map(a => a.id)` | §6d **RED**; a, b, c stay green |
| the effect at all | delete it | §6a **RED**, and **T7 red on the ack CLICK, not merely on a focus assertion** |

⚠ **§6c and §6d are easy to read as redundant and are not.** The effect's comment must say why, in the shape `SosOverlay:51-58` uses for its own composite key, and must name the oldest-first ordering as the reason the detector is a set difference.

- **Done when**: `pnpm --filter manage test` green; all four mutation-checks performed and restored. ⚠ **Then run `GuideOverlay.test.tsx` first-in-worker in isolation, five times** — see Task 8's warning; §6 is a scheduling-sensitive test that depends on when a poll tick lands relative to a React commit.
- **Commit**: `feat(manage): a rising SOS page closes the guide — edge-triggered on the composite key`

---

## Task 6 — Wire it into the console shell (D1, D2, DL3, DL6, DL18)
`frontend/apps/manage/src/App.tsx`

**Three lines, and `NAV`, `reachable` and `activeKey` are untouched.**

```tsx
// delete the local `type SectionKey = …` at :24-41 (it moved in Task 1)
import type { SectionKey } from "./lib/guide";
import { GuideOverlay } from "./components/GuideOverlay";
// …
<ConsoleShell
  …
  guide={<GuideOverlay section={activeKey} />}
>
```

**Role-gating is structural and needs no code of its own** (DL6). `activeKey` (`:208-210`) is **already** the role-filtered truth — it falls back to `reachable[0]?.key ?? section` whenever `section` is not in the role's reachable set — so a receptionist can only ever be shown `floor`'s three steps. **F60 must not re-implement the filter**: it has exactly one home. (`:69-73`'s "this is COSMETICS" comment argues the *opposite* direction — the server's RoleGate is the control — and nobody may simplify the gate away on the strength of it.)

**The out-of-enum role is accepted in one sentence, recorded rather than repaired.** `:200-207` documents it: `GET /manage/auth/me` echoes `staff_users.role` verbatim with no allowlist, so `reachable` is empty, `activeKey` stays `"dashboard"`, and the guide would offer `dashboard`'s two steps over `DashboardSection`'s 403 outage panel. **Accepted**: the steps describe a *screen* and not its data (the same argument as *Every state* → Loading), and migration 0011's CHECK makes the row impossible in the database. If a later reviewer disagrees, the fix is one expression — `guide={reachable.length > 0 ? <GuideOverlay section={activeKey} /> : undefined}` — and is explicitly **not** a second permission table.

- **Done when**: `pnpm --filter manage typecheck` clean (this is the commit where `GUIDE_STEPS`' `satisfies` starts guarding the real union); `pnpm --filter manage test` green with `Nav.test.tsx` **unedited**; `pnpm --filter manage build` clean (no unused import, no unused variable — `tsc --noEmit && vite build`).
- **Commit**: `feat(manage): mount the guide in the console header and move SectionKey to lib/guide`

---

## Task 7 — The `/checkin` hint: a reveal-only disclosure (D7, DL14, DL15, DL21)
`frontend/apps/storefront/src/routes/CheckinPage.tsx`, `frontend/apps/storefront/src/__tests__/CheckinPage.test.tsx`

⚠ **Re-read the qa-greps warning at the top of this file before writing a single comment.** This is the one task whose files `qa-greps.sh`'s seven `check` patterns actually read. **Diff `make qa-greps` against Task 0's baseline before committing** — a new `FAIL` line here is prose, not a code defect, and the fix is the prose.

### The failing tests first — `CheckinPage.test.tsx`

1. the hint's trigger renders with `aria-expanded="false"` and **no `aria-controls`** while collapsed (a dangling IDREF is what axe reports as `aria-valid-attr-value`, per `A11yMenu.tsx:120-122`);
2. clicking it flips `aria-expanded` to `"true"`, sets `aria-controls` to the hint's id, and reveals `checkin.guideHint`'s Hebrew;
3. **it is withheld in BOTH degraded arms with the form** — the `loading` arm (`:214`) and the `boutique === null` arm (`:234-248`). No boutique, no form, nothing to explain;
4. it renders **after** the `pointer` offer link and **before** the name `<Input>`, in both `pointer` arms;
5. **zero axe A/AA violations** with the hint revealed (`axe-core` is already in `apps/storefront/package.json:28`).

### The code — ~12 lines

`Button variant="ghost" size="md"` carrying `aria-expanded={revealed}` and `aria-controls={revealed ? hintId : undefined}`, with `<p id={hintId}>` **immediately after it in DOM order**. That is the APG disclosure in full: `aria-expanded` announces the state, and the reader's very next item *is* the hint.

**Nothing else. No `tabIndex={-1}`, no ref, no effect, no `onKeyDown`, no Esc handler, no focus move.** ⚠ **This is the THIRD deck to decline `ManageBookingPage`'s reveal-focus-move** and the reasons compound: (1) `ManageBookingPage` has **no Esc handler anywhere in the file** — grep it; its close is a ghost «ביטול» at `:469-483` — and an Esc handler is only needed *because* focus moved; (2) that focus move is the **only** frontend entry on `LOOP-STATE.md`'s `known_flaky` list (verified above), a jsdom focus/timing race that has already parked a green PR, and `fitting-rooms/design.md` §5.3 and `floor-dispatch/design.md` P-4 each recorded a deliberate decision to avoid it; (3) **there is nothing to move focus to** — this reveals one sentence with nothing focusable in it, and a `tabIndex={-1}` paragraph is a destination invented so an Esc handler has something to close from.

**Placement**: below the `pointer` offer link when it renders (`:254-266`), above the first `<Input>` (`:268`) in both cases. Putting an orientation hint above a live "resume your existing ticket" link would bury the more useful control. `size="md"` (`min-h-11`), matching the retry (`:242`), the submit (`:314-324`) and the chips' explicit `min-h-11 min-w-11` (`:35`) — this page has a 44px floor on a public phone surface and F60 does not lower it. **A fixed control is impossible here anyway**: `StorefrontLayout.tsx:186-199` puts the statutory `A11yMenu` trigger in the block-end inline-end corner on every route.

⚠ **THE CONTENT FENCE IS POSITIVE, AND IT IS LOAD-BEARING ON GATE 1.** The hint names **the queue and only the queue**: what checking in puts her into, what she gets back, and that a staffer calls her by name. **It states no data-handling fact of any kind.** `CheckinPage.tsx:296-300` rules directly against the alternative — *"The notice sits ABOVE the box it describes, and is never behind a disclosure: notice at the moment of collection means visible at the moment of collection. Both strings are counsel-gated in he.ts; nothing here may hardcode any part of either."* A collapsed «מה קורה עם הפרטים שלי?» beside a legally-mandated always-visible notice would be a **second, unapproved notice at the same collection point**, and it would **void this spec's Gate 1 self-approval** ("no privacy-law text"). `checkin.notice` and `checkin.optIn` are untouched — F60 does not edit a character of either, including F59's public-queue-board clause, which `i18n-keys.test.ts:133-142` pins.

⚠ **If the intended content genuinely is data handling, Gate 1 stops being self-approving and the feature STOPS FOR THE USER** (DL15, Interview Q1).

### Mutation-checks (mandatory)

| Mechanism | Break it | Expect |
|---|---|---|
| `aria-controls={revealed ? hintId : undefined}` | make it unconditional | test 1 **RED**, and axe's `aria-valid-attr-value` fires |
| the hint's placement inside the form gate | render it above the degraded returns | test 3 **RED** |
| the disclosure shape | convert it to a `Modal` | **T9 RED** (Task 8) — focus trapped where nothing should be |

- **Done when**: `pnpm --filter storefront test` green; `make qa-greps` **byte-identical to Task 0's baseline**; the two `test_config.py`-style local false failures do not apply here (this is frontend only).
- **Commit**: `feat(storefront): the check-in queue hint, as a disclosure that traps nothing`

---

## Task 8 — **The focus contract, in Chromium** (D4, AC11–AC17)
`frontend/e2e/guide.spec.ts` ✚

**This is the task the feature exists to get right, and it is the only proof the trap exists.**
`e2e/manage.spec.ts:26-30` and `e2e/sos.spec.ts:23-49` both open with the same paragraph: jsdom is not a browser, every focus assertion in this repo is measured in Chromium, and F57 once shipped a focus test that asserted nothing. **DL17 forbids a single vitest focus assertion in this feature, so if this file is weak, F60 has no safety argument at all.**

### Harness — **C1: no login block**

```ts
await installManageApi(page, { staff: /* staff() → reception, or MANAGER */, replies: { … } });
await page.goto(MANAGE);
```

`installManageApi` *is* the authentication (`fixtures/manage.ts:14-17`). Copy `retarget()` (`sos.spec.ts:139-147`), `axeViolations()` (`:150-158`) and `card()` (`:170-176`) from `sos.spec.ts`; **extracting a shared helper is out of scope for this feature.**

**Default identity `reception` is the right default here**: her only reachable row is `floor`, `activeKey` lands there with no navigation, no other panel mounts, and `floor` has three steps — so step 2 gives a three-control footer for the Tab-cycle tests.

**Locators.** `Modal` sets **no `role` attribute** — a `<dialog>` carries only an implicit ARIA role. Use `page.getByRole("dialog")`, which resolves it through the accessibility tree, or the CSS `dialog[open]`, which is the selector `SosOverlay.tsx:298` itself uses. ⚠ **`page.locator("[role=dialog]")` and `document.querySelector("[role=dialog]")` match NOTHING** and are the vacuity class this section exists to prevent.

**Every focus assertion is POSITIVE** — `expect(<named locator>).toBeFocused()` — and a `not.toBeFocused()` may appear only *in addition to* one.

### One named test per focus rule, and the deletion that must turn it red

| # | Test | Rule | The deletion that must turn it red |
|---|---|---|---|
| **T1** | *the guide opens with focus inside it* — click «מדריך», `expect(page.getByRole("dialog").getByRole("button", { name: "סגירה" })).toBeFocused()` | D4.1 | **`Modal.tsx:29`: `dlg.showModal()` → `dlg.show()`.** A non-modal dialog moves no focus; T1 finds focus still on the trigger. ⚠ Invisible to vitest — both stubs are `this.open = true`. |
| **T2** | *Tab from the last control returns to the first* — focus «הבא», press Tab, assert the dialog's first control is focused | D4.2 | Same one-token deletion. Without modality Tab leaves the dialog into the console header and T2 finds the logout button. |
| **T3** | *Shift+Tab from the first control reaches the last, never the console* — assert the last control **is** focused, and additionally `expect(logout).not.toBeFocused()` | D4.2 | Same. Also red if `<dialog>` is swapped for a `<div>`. |
| **T4** | *Esc from the step body closes it* — **click the step paragraph** (non-focusable dialog content, the exact `activeElement` state D6 refuses to assume anything about), press Esc, `expect(page.getByRole("dialog")).toBeHidden()` | D4.3 | **`Modal.tsx:29`: `showModal()` → `show()`.** A non-modal `<dialog>` has no close watcher, so Esc does not close it at all. ⚠ **Two other deletions were proposed and BOTH come back green — do not use them.** Deleting `onCancel` (`:38-42`) alone leaves **`onClose={onClose}` (`:43`)** wired: Esc closes natively, `close` fires, `onClose()` runs `setOpen(false)`, the `[open]` effect's `!open && !dlg.open` branch is a no-op, and the browser has already returned focus. Deleting **both** is no better: `open` never changes, so the `[open]` effect never re-runs and nothing reopens the dialog. What `onCancel` uniquely buys is already pinned by **`packages/ui/src/__tests__/Modal.test.tsx:18-34`** (a bare `cancel` event calls `onClose` once and does not fire the confirm) — cite that rather than inventing a browser mutation for it. |
| **T5** | *Esc returns focus to the «מדריך» button* | D4.4 | Same deletion as T4; also red if the trigger is unmounted while open. |
| **T6** | *«סיום» on the last step returns focus to the «מדריך» button* | D4.4 | `GuideOverlay`: replace `setOpen(false)` with an unmount of the whole component. Focus drops to `<body>` — **the exact defect class this repo has shipped five times.** |
| **T6b** | *a pointer-only user can leave from step 1* — open the guide, **click «סגירה» without pressing any key**, assert the dialog is gone and `expect(guideTrigger).toBeFocused()` | DL19, AC19 | `GuideOverlay`: remove «סגירה» from the footer. T6b then has nothing to click — the exact state a keyboard-less tablet is left in. |
| **T7** | *an SOS page closes the guide, focus returns to the button, the red page is on screen, and its ack is CLICKABLE* — **three legs**: (a) focus untouched after open; (b) **after clicking the step paragraph first**, the `activeElement` state D6 refuses to assume anything about and the measurement that replaces the rejected layout-effect fix; (c) with one alert already live and **dismissed** and the guide reopened over it, `retarget` a **second** alert and assert the new card's «אני מגיעה» is clickable | D6, DL11 | `GuideOverlay`: delete the D6 effect. The guide stays open in the top layer, the ack is inert, and **T7 fails on the CLICK — not merely on a focus assertion.** Leg (c) additionally reddens if the detector tests only the head of the alert list. |
| **T8** | *Esc means one thing at a time.* ⚠ **Setup, explicitly, because D6 makes the naive setup unreachable**: install a `for_me` alert in the **first** poll response and wait for the red page — the D6 edge is consumed by that arrival — **then** click «מדריך» (DL13 keeps the trigger enabled, DL12 keeps the close edge-triggered, so it opens). Assert the dialog is open. Press Esc: the dialog closes and «אני מגיעה» is **not** focused. Press Esc again: it is. | D4.3, AC15 | **`SosOverlay.tsx:298`: delete the `dialog[open]` guard.** The listener then reaches `event.preventDefault()` (`:312`), which **suppresses the dialog's own close request** — so the first Esc focuses the ack and the guide stays open. T8 goes red on its first assertion. (Any claim that it "fires both" is wrong; the capture listener's `preventDefault` is why.) |
| **T9** | *`/checkin`'s hint traps nothing* — reveal it, Tab, assert focus reaches the name field | D7, AC16 | `CheckinPage`: convert the disclosure to a `Modal`. T9 then finds focus trapped. |

**Plus two axe passes** (`wcag2a`, `wcag2aa`): the console with the guide open, and `/checkin` with the hint revealed. ⚠ **They are the floor, not the proof** — axe reports none of the focus class above and was green all five times this repo shipped a focus-drops-to-`<body>` defect.

### ⚠ jsdom does not blur a disabled element — this is how a vacuous focus test shipped here before

`SosCentre.test.tsx:139-158` ships the helper and the explanation: *"`Button` is `disabled={disabled || loading}`, so Chromium blurs the tapped control the instant the request starts. jsdom does not — and `HTMLElement.blur()` **BAILS OUT** on an element that is not a focusable area, so the `control.blur()` MOVE H's tests use is a **NO-OP** on a disabled control."* A vitest test that "proves" focus moved off a disabled control proves that jsdom left it there. **Every test above is therefore written so it would FAIL if its focus code were deleted, and every one of them runs in Chromium.** The named deletions in the table are the check; perform each, watch it go red, restore it.

### ⚠⚠ Run the focus- and scheduling-sensitive tests BOTH ways, several times each

A sibling feature shipped a full-suite-green test that CI failed, decided by one event-loop turn. Full-suite ordering and first-in-worker ordering are different schedulers.

```
# full suite, three times
for i in 1 2 3; do (cd "…/frontend" && pnpm --filter manage test) || break; done

# first-in-worker, in isolation, five times — the ordering the full suite hides
for i in 1 2 3 4 5; do \
  (cd "…/frontend" && pnpm --filter manage test -- src/__tests__/GuideOverlay.test.tsx) || break; \
done

# the E2E block alone, three times, then inside the whole e2e run
for i in 1 2 3; do (cd "…/frontend" && pnpm e2e -- guide.spec.ts) || break; done
(cd "…/frontend" && make -C "…" e2e)
```

Applies to **`GuideOverlay.test.tsx` §5 and §6** (a live region written from an effect; a detector that fires on a poll tick relative to a React commit) and to **`guide.spec.ts` T7 and T8** (an alert delivered by `retarget` while a top-layer dialog is open). **A test that is green in one ordering and red in the other is a defect in the test or in the feature, and it does not ship** — the rule the `known_flaky` entry states is *fix the wait, do not raise the timeout*.

- **Done when**: `make e2e` green, the existing `manage.spec.ts`, `sos.spec.ts`, `storefront.spec.ts` and `a11y.spec.ts` unchanged and green; every named deletion performed, observed red, and restored; both loops above run clean.
- **Commit**: `test(e2e): the guide's nine focus journeys and the two axe passes jsdom cannot answer`

---

## Task 9 — Gates and the run report
No files.

Run the full verification below, report what ran and what passed, and carry forward:

- **The scope fence held.** `git diff --stat main…HEAD -- '*/package.json' '*/pnpm-lock.yaml'` is **empty**. **No dependency was added**, and the reason is stated positively (spec *Codebase conflicts* 4): the trap is native `<dialog>`, the positioner is out of scope because nothing is anchored, and the state machine is `useState(0)`.
- **No migration.** `cd "…/Backend" && uv run python -m alembic heads` prints **`0022 (head)`**, a single head, **unchanged from main's**. Quote the output in the report.
- **R1 — the copy is 36 sentences describing fourteen screens that changed nine times in one day.** Each was written with its section component open, and for `hours`, `types`, `terms` and `catalog` the component is the only place the words exist. **A quoted label that drifts from its control is this deck's failure mode and no test in this repo can see it.** *Owner: reviewer, and whoever next renames a control on those four screens.*
- **R2 — `describedById` touched a component with FIFTEEN production call sites.** AC18 is the whole unit suites, not four named files. State that `pnpm --filter ui test`, `--filter manage test` and `--filter storefront test` all ran green with `Modal.test.tsx` unedited.
- **R3 — T1–T9 are the only proof the trap exists**, and they run only in the E2E job. **If `Frontend E2E (Playwright + axe)` is ever made `continue-on-error`, this feature silently loses its entire safety argument and every remaining test still passes.** *Owner: whoever next edits the merge gate.*
- **R6 — the fifteenth section.** Whoever adds one gets a type error in `guide.ts` and will be tempted to silence it with a placeholder sentence. **A placeholder is a lie with a compile-time blessing; the type buys a prompt, not a guarantee.** *Owner: reviewer, on the next `SectionKey` PR.*
- **R7 — the console's `i18n.test.ts` has no source scanner**, so a `guide.*` key that exists and is never rendered passes the floor, both register guards and the parity guard. The only things between the deck and a dead key are `GUIDE_STEPS`' literal list and §1's set equality.
- **Deck F-7, handed to the manual screen-reader pass**: focus returns to a «מדריך» button that `SosOverlay.tsx:451`'s opaque full-screen field is covering. Not a WCAG 2.0 AA failure (focus-not-obscured is SC 2.4.11, **WCAG 2.2**), one keypress long, every alternative worse — but unstated in the spec until now. Together with the FRAME 2 sequence (a `role="alert"` mounting in the same commit a `<dialog>` leaves the top layer) and the live region's real-AT behaviour, these are the three claims **no automated tool in this repo can observe**.
- **Deck F-5 — the console header grew ≈16px on every section**, deliberately, for `tokens.md` law 7's 44px floor.
- **`copy.md` C-2 — the shipped «מקדמה»/«פיקדון» split is NOT repaired** by F60 and is recorded for whoever next opens `booking.*`.
- **`copy.md` C-3 — `guide.atelier.3` is the only place in the product where the atelier's permission model is written down.** `AtelierSection.tsx:1347-1355` deliberately renders no explanation on a screen she opens fifty times a shift; the walkthrough she opens deliberately is where the other half of that argument lands. **On a feature that ships no capability, that is its strongest single justification.**
- **Spec *Codebase conflicts* 3 — three shipped comments still under-count the console's sections** (`SosOverlay.tsx:12` "thirteen", `:612` "eleven", `App.tsx:230` "eleven"; it is fourteen). **F60 does not fix them** and edits neither file.
- **LOOP-STATE's `deps: [F34]` for F60 is stale**; what actually constrains this build is F37, F33 and the shipped `ConsoleShell`/`Modal`. Recorded, not repaired — LOOP-STATE is not this plan's to edit.

No push, no PR from this task — the orchestrator owns review and shipping.

---

## Shipping checklist — run in this order

1. `git show --stat` on **every** commit confirms the **lowercase** pathspecs landed. `git add Frontend/…` silently skips modified tracked files.
2. `git diff --stat main…HEAD` touches **only** the files in the manifest below. Nothing in `.worktrees/`, nothing in `Backend/`, nothing in `frontend/apps/manage/src/components/SosOverlay.tsx`, `.../lib/sos.tsx`, `.../lib/usePoll.ts`, `.../__tests__/Nav.test.tsx`, `.../components/BoardSection.tsx`.
3. `git diff main…HEAD -- '*/package.json' '*/pnpm-lock.yaml'` is **empty**.
4. `cd "…/Backend" && uv run python -m alembic heads` → **`0022 (head)`**, single head, unchanged.
5. `make qa-greps` output is **byte-identical to Task 0's baseline**.
6. `grep -rn "localStorage" frontend/apps/storefront/src` returns nothing new.
7. Full local gate (below), all five targets green.
8. Both repeat-run loops from Task 8 clean.
9. Rebase onto `origin/main`, re-run the gate. **There is no migration to renumber.**
10. Open the PR. The three gating jobs are `Backend (lint, types, tests)`, `Frontend (lint, types, build)`, `Frontend E2E (Playwright + axe)`.

---

## Verification — the full local gate sequence

```
make lint      # Backend: ruff check . && ruff format --check . && mypy app tests
               #   + Frontend: pnpm -r lint && pnpm -r typecheck   (oxlint -c ../../.oxlintrc.json src)
               #   + bash frontend/scripts/qa-greps.sh
make test      # Backend: pytest -m "not db" -q      — UNCHANGED by F60
make fe-test   # Frontend: pnpm -r --if-present test  (TZ=America/New_York vitest run, all three packages)
make fe-build  # Frontend: pnpm -r build              (tsc --noEmit && vite build)
make e2e       # Frontend: pnpm -r build && playwright install --with-deps chromium && pnpm e2e
```

**Green looks like:**

- **`make lint`** — ruff and mypy untouched by F60; `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages; `qa-greps.sh` **exit 0 printing exactly Task 0's baseline**.
- **`make test`** — unchanged. F60 touches no backend file. ⚠ **Two `test_config.py` failures are always false locally** (`Backend/.env` leaks `MEDIA_BUCKET`); CI is green. Do not chase them (`.memory/local-env-breaks-config-tests.md`).
- **`make fe-test`** — `GuideOverlay.test.tsx` (§1–§7), `i18n.test.ts` (the `HE_F60` block, its floor, its fold twin, its `ar` value guard, P-1's fourteen-key loop), `CheckinPage.test.tsx`, `i18n-keys.test.ts` (the new value-parity `it`), and `Modal.test.tsx` / `console-composites.test.tsx` **unedited** — all green. **No vitest test in this feature asserts focus** (DL17).
- **`make fe-build`** — both apps build; no unused-import or unused-variable TS error (`App.tsx` loses a type declaration and gains two imports in the same commit).
- **`make e2e`** — `guide.spec.ts`'s nine journeys and two axe passes green; `manage.spec.ts`, `sos.spec.ts`, `storefront.spec.ts`, `a11y.spec.ts` unchanged and green.
- **`make test-db`** — **not run and not needed.** F60 has no db-marked test and no migration.

**There is no local-only harness patch in this feature**, so there is nothing to revert before a commit.

## What a local run cannot prove

| Claim | Proved locally | Not proved anywhere automated |
|---|---|---|
| The trap, Esc, the focus return, the SOS close | **T1–T9 in real Chromium**, each with a named deletion that reddens it | — |
| Zero axe A/AA violations | the two passes | axe reports **none** of the focus class above |
| Step 1 is audible on open | §7's IDREF assertion | that a **real AT** reads `aria-describedby` on a `<dialog>` entering the top layer |
| The region announces once, on change | §5 (the four mechanical properties) | that a **real AT** announces a rewritten `role="status"` inside a `<dialog>` that just left `display:none` — **the manual pass** |
| Focus returns to «מדריך» when an SOS lands | **T7**, all three legs | that the returned focus is *usable* while `bg-danger` covers it (deck F-7 — recorded, one keypress, below the 2.0 AA floor) |
| The copy names controls that exist | nothing | **R1.** No test in this repo can see a step that describes a renamed button. |

---

## Task-by-task file manifest

| Task | New (✚) | Modified |
|---|---|---|
| 0 | `.planning/plans/guide-walkthrough.md` | `.planning/specs/guide-walkthrough.md` |
| 1 | `frontend/apps/manage/src/lib/guide.ts`, `frontend/apps/manage/src/__tests__/GuideOverlay.test.tsx` | — |
| 2 | — | `frontend/apps/manage/src/i18n/he.ts`, `…/i18n/ar.ts`, `…/__tests__/i18n.test.ts`, `frontend/apps/storefront/src/i18n/he.ts`, `…/i18n/ar.ts`, `…/__tests__/i18n-keys.test.ts` |
| 3 | — | `frontend/packages/ui/src/components/Modal.tsx`, `frontend/packages/ui/src/components/ConsoleShell.tsx` |
| 4 | `frontend/apps/manage/src/components/GuideOverlay.tsx` | `frontend/apps/manage/src/__tests__/GuideOverlay.test.tsx` |
| 5 | — | `frontend/apps/manage/src/components/GuideOverlay.tsx`, `…/__tests__/GuideOverlay.test.tsx` |
| 6 | — | `frontend/apps/manage/src/App.tsx` |
| 7 | — | `frontend/apps/storefront/src/routes/CheckinPage.tsx`, `…/__tests__/CheckinPage.test.tsx` |
| 8 | `frontend/e2e/guide.spec.ts` | — |
| 9 | — | — |

**Never modified, and that is an assertion:** `frontend/packages/ui/src/index.ts` (both types already exported) · `frontend/packages/ui/src/__tests__/Modal.test.tsx` · `frontend/packages/ui/src/__tests__/console-composites.test.tsx` · `frontend/apps/manage/src/__tests__/Nav.test.tsx` · `frontend/apps/manage/src/components/SosOverlay.tsx` · `frontend/apps/manage/src/lib/sos.tsx` · `frontend/apps/manage/src/lib/sos-context.ts` · `frontend/apps/manage/src/lib/usePoll.ts` · `frontend/apps/manage/src/components/BoardSection.tsx` · **all fifteen `Modal` call sites** · `frontend/scripts/qa-greps.sh` · `frontend/e2e/fixtures/manage.ts` · `frontend/e2e/{manage,sos,storefront,a11y}.spec.ts` · **the entire `Backend/` tree** · `.planning/LOOP-STATE.md`.

---

## Testing plan → acceptance criteria

| AC | Where |
|---|---|
| AC1 `GUIDE_STEPS` covers all fourteen; a fifteenth without steps fails the build | `pnpm --filter manage typecheck` + `GuideOverlay.test.tsx` §1 |
| AC2 every step key resolves to Hebrew, never the key | `i18n.test.ts` §F60 resolve check (via the fold) |
| AC3 `ar.ts` carries all 43 with the approved Hebrew **value** | `i18n.test.ts` §ar — the fourth value-parity twin |
| AC4 no `!`, no `/נשלח\|תישלח\|בדרך/` in any `guide.*` string | `i18n.test.ts` register guards, **via the `...HE_F60` spread** |
| AC5 `aria-describedby` is the id of the current step | `GuideOverlay.test.tsx` §7 — **the one D3 mechanism jsdom can measure honestly** |
| AC6 the guide shows `activeKey`'s steps and nothing else | `GuideOverlay.test.tsx` §2 (+ structurally, `App.tsx:208-210`) |
| AC7 it never opens itself | `GuideOverlay.test.tsx` §3 |
| AC8 the step controls | `GuideOverlay.test.tsx` §4 |
| AC9 the region is empty on **every** open and speaks on every change, back included | `GuideOverlay.test.tsx` §5 — **the close-navigate-reopen leg is the only non-vacuous one** |
| AC10 a `for_me` alert closes it, incl. a second page and an escalation re-rise; a persisting dismissed one does not lock it shut | `GuideOverlay.test.tsx` §6 a/b/c/d |
| AC11 focus is inside the dialog after open | `guide.spec.ts` **T1** |
| AC12 Tab and Shift+Tab cycle; neither reaches the console | **T2**, **T3** |
| AC13 Esc closes from anywhere inside | **T4** |
| AC14 focus returns to «מדריך» on all four close routes | **T5**, **T6**, **T6b**, **T7** |
| AC15 Esc never means two things at once | **T8** |
| AC16 `/checkin` reveals, flips `aria-expanded`, moves no focus, traps nothing | `CheckinPage.test.tsx` + **T9** |
| AC17 zero axe A/AA violations, guide open and hint revealed | `guide.spec.ts`'s two passes |
| AC18 `describedById` changes no shipped caller's behaviour | **the whole unit suites** — `pnpm --filter ui test`, `--filter manage test`, `--filter storefront test` |
| AC19 every step has a working pointer-only dismiss | `GuideOverlay.test.tsx` §4 + **T6b** |

---

## What could go wrong in review

Every item is a **recorded ruling**. A reviewer who raises one should find the reasoning rather than file a finding.

1. **"LOOP-STATE says the focus trap is the real work, and this wrote none of it."** Spec *Codebase conflicts* 2. `Modal` has provided a native trap, native Esc and native focus-return since F5 and fifteen call sites ride it. The real work is (a) the announcement contract, which no native mechanism covers; (b) the SOS top-layer collision, which nothing in LOOP-STATE anticipates; (c) that **the trap cannot be tested in this repo's unit suite at all**; (d) the pointer-only exit, because a native `<dialog>` gives Esc for free and gives a tablet nothing. **A builder who reads the note literally and hand-rolls a Tab cycle writes ~60 lines of the most defect-prone code in the console for no gain.**
2. **"No tour library? A guided walkthrough is exactly what those are for."** Scope fence, and it is a **positive** finding rather than a grudging one. The three things such a library sells are already answered: the trap is the platform, the positioner is **out of scope because nothing is anchored** (deck §2.3), and the state machine is `useState(0)`. Anchoring was refused on its own merits too — nine features changed these fourteen sections in one day, and an anchor is a selector into somebody else's component that turns silent the first time a wrapper is renamed, with every test green.
3. **"The e2e file has no login step."** **C1.** `installManageApi` authenticates by fulfilling `GET /manage/auth/me`, and says so at `fixtures/manage.ts:14-17`. The spec's "copy `sos.spec.ts`'s login block" is wrong; `grep -n LOGIN_SUBMIT e2e/*.ts` returns four hits, all `toHaveCount(0)` negative assertions.
4. **"The vitest block asserts no focus at all."** **DL17**, and it is the most important line in the Testing section. jsdom 29.1.1 ships no `<dialog>` implementation, and all three `setup.ts` stubs are `this.open = true` for **both `show` and `showModal`**, with no `cancel` event. Every focus assertion would measure the stub — F57's vacuous focus test with a different mechanism. §7 is permitted because it is a plain IDREF read.
5. **"T4's mutation should delete `onCancel`."** Refuted in place. `Modal.tsx:43` wires `onClose={onClose}` **in addition to** `onCancel` at `:38-42`: deleting `onCancel` alone still closes on Esc, and deleting both means `open` never changes so nothing reopens. `showModal()` → `show()` is the one mutation that reddens T1–T5, and `onCancel`'s unique value is already pinned by `Modal.test.tsx:18-34`.
6. **"The detector looks over-specified — §6c and §6d are the same test."** **R4, and they are not.** §6c dies to a head-of-list detector (`alerts` is oldest-first — `sos-context.ts:18`, `sos_alerts.py:245`, `sos.tsx:128-131` — so a new page lands at the **end**); §6d dies to a bare-id detector (`dismissKey` is composite *precisely* because escalation and the stall each re-rise the card once). Both failures end the same way: a full-screen emergency painted under an inert top-layer dialog.
7. **"Why does the detector not subtract dismissed alerts, like `SosOverlay` does?"** **C7.** `dismissed` is `SosOverlay`'s own state and is not on `SosContextValue`, so it cannot — and must not: a dismissed page whose `escalated` flips re-rises the card, and the guide has to get out of its way. §6b is the test that a *persisting* dismissed alert still lets her reopen.
8. **"Close the guide from a `useLayoutEffect` so `SosOverlay` never samples `activeElement` while the dialog is open."** **The spec's one rejected finding**, declined in writing. Its diagnosis was accepted in full and D6 rewritten to it. The fix buys back one focus move whose absence costs nothing — focus still returns to a labelled button and Esc reaches «אני מגיעה» in one keypress — in exchange for an invisible cross-component ordering dependency. **Measured by T7 leg (b) instead.**
9. **"Focus returns to a button hidden under the red field."** **Deck F-7**, now stated. Not a WCAG 2.0 AA failure (focus-not-obscured is SC 2.4.11, **WCAG 2.2**; IS 5568 is 2.0 AA), one keypress long, and every alternative — moving focus ourselves, disabling or hiding the trigger — is a worse defect, the last two being the sixth instance of this repo's most-shipped bug. Handed to the manual pass.
10. **"«הקודם» is absent on step 1 but «סגירה» is always there — pick one."** **DL10 and DL19, and they are not in tension.** Inside a trap every Tab stop is one she must walk past, so a *dead* control earns nothing; a *working* dismiss earns the only pointer exit that exists, because `Modal` binds no backdrop click and the chrome has no X.
11. **"Three buttons will wrap at 375."** **C4 / deck F-1.** They cannot — `Modal.tsx:54` has no `flex-wrap`, so items shrink and a long label wraps inside its own button. The conclusion is unaffected: deck §2.6 measures ≈243px of buttons in a 295px content box. **Adding `flex-wrap` is a fifteen-call-site `Modal` edit this feature has not earned.**
12. **"The counter says «במדריך» — that reads oddly."** **Deck F-3 / copy C-1**, and it corrects D5 twice. «שלב 2 מתוך 4» is unrepresentable (N ∈ {2,3}), and D5's "neither digit at a string edge" is **unsatisfiable** for a two-number Hebrew counter without a trailing noun. `isolateLtr` is not the alternative and would be actively wrong — it splits on `indexOf` (`lib/booking.tsx:76`), so on «שלב 3 מתוך 3» it isolates the *first* 3, on the most-visited step.
13. **"The `/checkin` hint should explain what happens to her details."** **DL15, and it is a Gate 1 matter, not a copy preference.** `CheckinPage.tsx:296-300` rules directly against the placement, and a second notice at the same collection point would void this spec's Gate 1 self-approval ("no privacy-law text"). The hint names the **queue** and nothing else. **If the intended content genuinely is data handling, the feature stops for the user.**
14. **"`/checkin`'s disclosure should move focus into the revealed text, like `ManageBookingPage` does."** **DL14**, and this is the **third** deck to decline it. That file has **no Esc handler at all**; its focus move is `LOOP-STATE`'s only frontend `known_flaky` entry; and there is nothing focusable to move to. APG's disclosure moves no focus.
15. **"The title's section name is built from a template, which DL5 bans."** **P-1 / C3.** DL5's argument is that the console has no source scanner, so `HE_F60`'s literal filter is the only guard on a `guide.*` key. `nav.*` is outside that namespace, indexed by a closed compiler-checked union, already rendered by `ConsoleShell` on every section, and covered by a named fourteen-key resolve test. Every `NAV` row's `labelKey` is exactly `` `nav.${key}` `` — verified.
16. **"axe is green, so the a11y work is done."** axe reports **none** of the focus class and was green all five times this repo dropped focus to `<body>`. **T1–T9 are the a11y work**, and R3 is the standing warning that they live in one job.
