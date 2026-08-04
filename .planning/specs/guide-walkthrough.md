# Spec: F60 — Per-page guided walkthrough (the «מדריך» button) — cross-cutting, LAST in the floor program

**Spec review**: 27 findings from 2 lenses · **26 applied**, **1 rejected** (see *Rejected findings*). Five findings were duplicates across the two lenses and are resolved once each; where two lenses proposed conflicting fixes for one defect, the adopted fix is named and the other is refuted in place.

**Created**: 2026-08-04 · **Gate 1: standing approval** — `interview-2026-07-30.md` §Standing approvals (Q1's enumerated exceptions are F17, F18, F19, F20, F29, F48; F60 is none of them — no payments, no refunds, no privacy-law text, no billing). **That last clause is now load-bearing and is enforced by D7 + DL15: if the `/checkin` hint ever states a data-handling fact, Gate 1 stops being self-approving and the feature must stop for the user.** · **Design gate: self-approved** — ruling 2026-07-31 named exactly two novel interaction patterns for this run, F34's shift board and F42's capacity matrix. F60 is neither: its overlay is `@boutique/ui`'s shipped `Modal` and its trigger is a button in a shipped header. · **Effort**: **S** — one new lib file, one new console component, one optional prop on `ConsoleShell`, one optional prop on `Modal`, one disclosure on `/checkin`, and 45 strings. **No migration, no endpoint, no dependency.**
**Depends on**: **F30/F31** (`ConsoleShell`, the console's role-filtered `NAV`) · **F37** (`SosProvider`/`useSos`, and `SosOverlay`'s Esc guard — D6 is entirely about this) · **F33** (`CheckinPage`) · and, transitively, every feature that added a `SectionKey`: F52, F34, F53, F57, F41, F33, F17, F51. **LOOP-STATE records `deps: [F34]`, which is stale — see *Codebase conflicts recorded*.**
**Feeds**: nothing. F60 ships no capability. It is deliberately last.

## What F60 does *not* do

No migration. No endpoint. No new row, column, poll loop, rate limiter or audit action. **No new dependency of any kind** — not a tour library, not a focus-trap library, not a popper. The overlay is `@boutique/ui`'s `Modal`, which is a native `<dialog>` opened with `showModal()`; the browser owns the trap, the Esc key and the focus return, and it has owned them in this repo since F5. It does not anchor to, highlight, spotlight or scroll to any element on the page — there is no positioning engine here, which is the single largest reason no dependency is needed. It does not persist "seen" state, does not open itself on first visit, and adds no storage key. It does not touch `usePoll`, `SosOverlay`, `SosProvider`, `FloorPanel`, `BoardSection`, or any section component.

---

## Problem

The console has fourteen sections. A boutique owner configures five of them once and never opens them again; a receptionist hired on a Tuesday sees exactly one; a seamstress sees two. Nothing in the product explains any of them. The screens are Hebrew, self-labelled and reasonably clear, but "reasonably clear" is what every screen's author believes, and the brief's own lowest-priority item exists because the boutique asked for it after using the prototype.

The two things that make this more than copy:

- **The console already has one full-screen overlay that appears unbidden.** F37's SOS page renders app-level, over whatever the staffer is doing, on every section. A second overlay — one that a user opens deliberately and that a browser will put in the *top layer* — can hide the first one and make it unanswerable. That is the only way this feature can hurt anybody, and D6 is where it is settled rather than waved past.
- **A guided overlay is a focus trap by definition, IS 5568 / WCAG 2.0 AA is legally binding here, and this repo has shipped a focus-drops-to-`<body>` defect five times** (`e2e/sos.spec.ts:32-35`, in as many words). axe reports none of that class. Worse, and this is the finding that shapes the whole test plan: **jsdom 29.1.1 ships no `<dialog>` implementation at all.** `node_modules/.pnpm/jsdom@29.1.1/.../HTMLDialogElement-impl.js` is an empty subclass of `HTMLElementImpl`, so the repo stubs `showModal` in all three `src/test/setup.ts` files with a body that is literally `this.open = true`. No focus move, no trap, no top layer, **no `cancel` event on Esc**. Every focus assertion a vitest test could write about this overlay would be measuring that stub. DL17 makes that a rule instead of an accident.

## Goal

A staffer on any console section presses «מדריך» in the header and gets a short, numbered walkthrough of *the section she is looking at* — never of a section her role cannot reach. She moves with «הבא»/«הקודם», and she can leave from **any** step by three routes that all work: «סגירה», Esc, or «סיום» on the last step. She lands back on the button she pressed. A screen reader hears the step she is on when the overlay opens and hears each new step when it changes — once, on change, not on every render. If an emergency page arrives while she is reading, the guide gets out of the way. And a woman standing in the shop doorway on `/checkin` gets one sentence explaining what checking in puts her into, from a disclosure that traps nothing and moves nothing.

## What already exists to build on (verified against code, 2026-08-04)

- **`packages/ui/src/components/Modal.tsx` is the whole trap.** It renders a `<dialog>` unconditionally (`:36-55` — children at `:53` are mounted whether `open` is true or false), drives it with `showModal()`/`close()` from an effect on `open` (`:25-33`), wires `aria-labelledby` to a `useId()` title, and wires **both** `onCancel` (`:38-42`, `preventDefault()` + `onClose()`) **and** `onClose={onClose}` (`:43`) — that pair matters to the E2E mutation table and is why one of the two named deletions there was wrong. Three further facts a builder must not assume otherwise: it sets **no `role` attribute** (the dialog role is implicit), it wires **no backdrop click** (the `:7` comment naming "backdrop" describes what `onClose` *means*, not a behaviour that is bound), and it renders `footer` only when supplied.
- **`Modal` has FIFTEEN production call sites, not four.** `HoursSection:319`, `AtelierSection:1101`, `AtelierSection:1242`, `SosRaiseDialog:190`, `DressEditor:405`, `TypesSection:306`, `BookingDetail:624`, `BookingDetail:655`, `RoomHandoverDialog:53`, `RoomsRegistryDialog:279`, `RoomsRegistryDialog:413`, `MediaGallery:526`, `RoomDressDialog:93`, `StaffSection:411`, `RescheduleDialog:103`. **F60 adds one optional prop to it and nothing else** (D3) — but the blast-radius argument and AC18 are sized against fifteen.
- **Every shipped `Modal` caller supplies an explicit dismiss control in `footer`.** `SosRaiseDialog:196-201` names it — *"The house pattern: ghost dismiss + secondary confirm, and the dismiss reuses F36's shipped «ביטול»"* — and `HoursSection:324-330` is «ביטול» + «הסרה». There is no backdrop route out of a `Modal` in this repo, so a footer without a dismiss is a dialog a pointer-only user cannot leave (D3, DL19).
- **`ConsoleShell` already has the header slot pattern.** `packages/ui/src/components/ConsoleShell.tsx` renders `boutiqueName` and a logout `<button>` in one `flex items-center justify-between` row (`:46-51`), and already takes two optional `ReactNode` props (`banner`, `progress`). A third, in the header, is the same move — but the row has exactly two children today and `justify-between` spreads a third to the middle, so the two right-hand controls get wrapped (DL18).
- **`SosOverlay` is deliberately NOT a `<dialog>` and says so at length** (`:15-21`): *"It is NOT a `<dialog>`, NOT `showModal()` and NOT `inert` on the console — each of those moves focus BY DEFINITION."* It is a `fixed inset-0 z-40` div. **A `showModal()` dialog beats every z-index and makes the rest of the document inert**, which is exactly why D6 exists.
- **`SosOverlay` already stands down for open dialogs.** Its document-level **capture** Esc listener returns early on `document.querySelector("dialog[open]") !== null` (`:298`), with a comment (`:294-297`) naming `Modal`'s `showModal()`/`close()` toggling as the mechanism. **A guide built on `Modal` inherits this for free** — Esc inside the guide means "close the guide", never "route into the SOS card". Note the listener calls `event.preventDefault()` (`:312`) *after* that guard, which is what makes T8's mutation behave the way T8 now says it does.
- **`SosOverlay`'s dismiss key is COMPOSITE, and its comment says why** (`:48-61`): `` `${alert.id}:${alert.escalated}:${alert.stalled}` ``, because *"escalation and the stall each re-rise the card exactly once"*. D6's detector must use the same key or it is blind to both re-rises.
- **`SosProvider` orders alerts oldest-first and appends.** `sos.tsx:129-131` — *"appending keeps the oldest-first order the read establishes"* — so a newly arriving alert lands at the **end** of `alerts`, never at index 0. D6 turns on this.
- **`SosOverlay`'s MOVE A never steals focus.** It moves focus to the first rising card only when `document.activeElement === document.body` (`:203-205`), and it is consumed once per rising run via `hadCardsRef` (`:197-202`). D6 depends on this and does not change it.
- **The console's fourteen sections are one array.** `App.tsx:24-41` declares `SectionKey` (14 members) and `:83-152` declares `NAV` (14 rows) with a `roles` field per row. `activeKey` (`:208-210`) is the single derived truth for "which section is on screen".
- **`CheckinPage` already owns a focus discipline, and a shipped comment on it rules directly against putting anything privacy-shaped behind a disclosure.** `CheckinPage.tsx:299-302`: *"The notice sits ABOVE the box it describes, and is never behind a disclosure: notice at the moment of collection means visible at the moment of collection. Both strings are counsel-gated in he.ts; nothing here may hardcode any part of either."* D7 and DL15 are written to that sentence.
- **`ManageBookingPage`'s inline reveal is the precedent for the SHAPE, and its focus move is the precedent for what NOT to copy.** `:414-418` — *"An inline reveal rather than a Modal: it keeps the whole decision on one surface and spares the focus-trap machinery for a two-button choice."* It has **no Esc handler anywhere in the file**; its close is a ghost «ביטול» at `:469-483`. Its focus move (`:405-406`, `:425`) is the one frontend entry on `LOOP-STATE.md`'s `known_flaky` list, and **two shipped design decks already declined that shape for that reason** (`fitting-rooms/design.md` §5.3, `floor-dispatch/design.md` P-4). D7 takes the shape and refuses the move.
- **`e2e/` is where focus is measured in this repo, and it says so.** `e2e/manage.spec.ts:26-30` and `e2e/sos.spec.ts:28-40` both open with the same paragraph: jsdom is not a browser, every focus assertion is measured in Chromium, and F57 once shipped a focus test that asserted nothing. `installManageApi` and the payload builders live in `e2e/fixtures/manage.ts` — **there is no login helper there.** `manage.spec.ts:37` and `sos.spec.ts:53` each declare `const LOGIN_SUBMIT = "כניסה"` locally and inline the login steps.
- **`i18n.test.ts` is the copy gate.** Each feature declares its own `HE_F##` selector, spreads it into `HE`, asserts a floor count, and adds an `ar` **value**-parity guard (`ar[key] === he[key]`, not merely "present"). The register guards over `HE` ban `!` and `/נשלח|תישלח|בדרך/`. **It has no source-file scanner** — nothing in `apps/manage/src/__tests__/i18n.test.ts` reads a `.tsx` file, so a key present in `he.ts` and never rendered passes every console guard. The storefront's `i18n-keys.test.ts` *does* scan sources, deriving `SECTIONS` from `Object.keys(he.translation)` (`:21`) and filtering dotted literals on the first segment (`:39`).

---

## Design

### D1 — The section inventory, derived from the shipped `App.tsx`

**Fourteen `SectionKey` members** (`App.tsx:24-41`), listed here in `NAV` order (`:83-152`), which is **not** the union's declaration order — see D2. Role sets: `ALL = [owner, shift_manager]`, `FLOOR_ONLY = [reception, sales_assistant, seamstress]`, `ATELIER_ROLES = [owner, shift_manager, seamstress]`.

| # | `SectionKey` | Nav label | Roles | Steps | What the steps cover |
|---|---|---|---|---|---|
| 1 | `dashboard` | סקירה | ALL | 2 | What each number counts and over what window; that a number that looks wrong is answered on the section it came from, not here. |
| 2 | `profile` | פרופיל והגדרות | ALL | 3 | What of this reaches the public storefront; the brides-only switch; the deposits switch and that it does nothing until the gateway is connected. |
| 3 | `hours` | שעות פעילות | ALL | 3 | The weekly rules; a one-off exception (closed day, or different hours); that a change moves future slots and never a booking already taken. |
| 4 | `types` | סוגי תורים | ALL | 3 | What an appointment type fixes (duration, audience); the deposit amount per type; sort order is the order a bride sees. |
| 5 | `terms` | מדיניות ביטולים | ALL | 2 | Policy is **versioned** and a customer is bound to the version she accepted; publishing a new one. ⚠ **`TermsSection` hides the publish form from a shift manager** (`TermsSection.tsx:20-21`, `const isOwner = role === "owner"`), so step 2 must describe versioning without promising the control — otherwise the guide lies on one of the shift manager's eleven rows. |
| 6 | `catalog` | שמלות | ALL | 3 | Adding a dress; variants and sizes; photos, and what the storefront actually shows. |
| 7 | `bookings` | תורים | ALL | 3 | The list and its filters; opening one booking; reschedule and cancel, and what the console **records** (never what was sent — D8). |
| 8 | `customers` | לקוחות | ALL | 2 | What a customer card holds; how to find her. |
| 9 | `board` | לוח היום | ALL | 3 | The day's timeline and the «עכשיו» divider; check-in; **and the floor panel that renders beneath the board on this section for these two roles only** (`App.tsx:258-263`). |
| 10 | `floor` | הצוות בקומה | FLOOR_ONLY | 3 | Who is on the floor and the break toggle; the fitting rooms; the waiting queue and take-next. |
| 11 | `atelier` | תפירה | ATELIER_ROLES | 3 | The five columns intake→delivered; opening a ticket; the seamstress's own view (`AtelierSection.tsx:1344`'s `isSeamstress` branch). |
| 12 | `checkinQr` | קוד סריקה | ALL | 2 | What the poster is and where the code leads; printing and re-printing it. |
| 13 | `staff` | צוות | `["owner"]` | 2 | Adding a staffer and choosing a role; deactivating one. |
| 14 | `gateway` | סליקה ותשלומים | `["owner"]` | 2 | Connecting the gateway; what happens to deposits while it is not connected. |

**36 steps total.**

**Role-gating is structural and needs no code of its own.** The guide is keyed on `activeKey`, and `activeKey` is already the role-filtered truth: `App.tsx:208-210` falls back to `reachable[0]?.key ?? section` whenever `section` is not in the role's reachable set. A receptionist can therefore only ever be shown `floor`'s three steps — not because F60 filters anything, but because she can never make any other key active. **F60 must not re-implement the role filter**: the filter has exactly one home and `activeKey` is already it (DL6).

The one gate the *structure* cannot express is the intra-section one — row 5's `TermsSection` and row 11's seamstress branch. Those are handled in the **copy**, by describing what the section is for rather than naming a control the reader may not have. That is a copy-deck rule (D8), and it is the reason the two rows above carry a ⚠.

**The one role the structure gets wrong, stated rather than discovered later.** `App.tsx:200-207` documents an out-of-enum role deliberately: `GET /manage/auth/me` echoes `staff_users.role` verbatim with no allowlist, so `reachable` is empty, `activeKey` stays `"dashboard"`, `DashboardSection` renders and its one fetch 403s. The guide would then offer `dashboard`'s two steps over an outage panel. **Accepted, in one sentence:** the steps describe a screen and not its data (the same argument as *Every state* → Loading), migration 0011's CHECK makes the row impossible in the database, and the cost of the alternative is a second condition. Recorded, not repaired. If a later reviewer disagrees, the fix is one expression in `App.tsx` — `guide={reachable.length > 0 ? <GuideOverlay section={activeKey} /> : undefined}` — and is explicitly **not** a second permission table.

### D2 — The step model: one table, keyed by `SectionKey`, compiler-forced

A new file, `frontend/apps/manage/src/lib/guide.ts`, owns **both** `SectionKey` and the table. `App.tsx` imports `SectionKey` from it.

**Move the union across as it is shipped** — same member order, same three ordinal comments (`// F57's floor — the TWELFTH member…`, `// F33's printable check-in code — the THIRTEENTH.`, `// F41's atelier — the FOURTEENTH.`). The shipped order is `dashboard, profile, hours, types, terms, catalog, bookings, customers, board, staff, gateway, floor, checkinQr, atelier` — **`staff` and `gateway` sit before `floor`**, because F57/F33/F41 appended. Union member order is behaviourally irrelevant; reordering it during the move is a diff a reviewer has to read for nothing, and it costs the three comments that record who added what.

```ts
export type SectionKey =
  | "dashboard" | "profile" | "hours" | "types" | "terms" | "catalog"
  | "bookings" | "customers" | "board" | "staff" | "gateway"
  | "floor" | "checkinQr" | "atelier";   // ← with the three shipped comments kept

// A NON-EMPTY tuple per section. `satisfies` is the whole mechanism: a
// fifteenth SectionKey with no steps is a TYPE ERROR, and a section with zero
// steps is UNREPRESENTABLE — which is how «the button never lies» is enforced
// at the only moment it can be enforced cheaply.
export const GUIDE_STEPS = {
  dashboard: ["guide.dashboard.1", "guide.dashboard.2"],
  // …
  gateway: ["guide.gateway.1", "guide.gateway.2"],
} as const satisfies Record<SectionKey, readonly [string, ...string[]]>;
```

**Why the type and not a runtime guard.** `pnpm --filter manage typecheck` runs in `build` and gates the merge, so "add a section, forget its steps" fails the build. A runtime `if (steps.length === 0) return null` would be a branch no test can reach without an injection seam invented solely to reach it — a seam is more code than the defect it guards. **The direction of the ordering matters and must not be "simplified":** `SectionKey` lives in `guide.ts` and `guide.ts` imports nothing from `App.tsx`. Declaring `SectionKey` in `App.tsx` and importing it here creates the same import cycle `router.tsx:205-215` documents, where `vi.mock`'s live binding silently resolves to the real module.

**`index` needs no clamp, and here is the invariant that makes that true rather than lucky.** `GuideOverlay` holds `index` while `section` arrives as a prop, and sections have 2 or 3 steps — so a section change under an open guide would render `t(undefined)`. It cannot happen: the only writer of `activeKey` is `ConsoleShell`'s `onNavigate`, and `showModal()` has made that nav inert. Stated because a builder cannot otherwise tell a considered omission from a forgotten one. If a later feature ever changes `section` programmatically, `key={section}` on `<GuideOverlay>` in `App.tsx` remounts it and costs one token.

**Ordering** is array order, `0`-based internally and rendered 1-based. **Keying** is the i18n key itself, spelled in full rather than built from a template (DL5).

Each step is **one sentence**. There is no per-step title: the dialog's title is `t("guide.title", { section })` where `section` is the already-translated nav label, so no section name is transcribed twice.

### D3 — The overlay is `Modal`, the one prop it gains, and the footer it must carry

`GuideOverlay` renders `<Modal open={open} onClose={close} title={…} describedById={bodyId} footer={…}>`. `Modal` gains exactly one optional prop:

```ts
describedById?: string;   // → aria-describedby on the <dialog>
```

Rendered as `aria-describedby={describedById}`. When `undefined` React omits the attribute, so all fifteen shipped call sites are byte-identical in behaviour. **This is not cosmetic.** `showModal()` puts focus on the first focusable control, and with `aria-labelledby` alone a screen-reader user hears «מדריך — לוח היום» then a button label and never hears the step. `aria-describedby` pointing at the step paragraph is what makes the first step audible on open, and it is why D5's live region can stay silent on open. **It is therefore the one D3 mechanism with its own test and its own AC** (vitest §7, AC5) — it is a plain IDREF assertion with no focus and no `<dialog>` behaviour in it, so DL17 permits it and it is the cheapest test in the feature. Without it, the whole of D3 could be omitted at build time and every other listed test would stay green.

**The footer carries a persistent dismiss on EVERY step, and this is not optional.** `Modal` wires no backdrop click and there is no close affordance in the chrome, so the footer is the only pointer route out. Without a dismiss, step 1 of a 3-step guide is a top-layer dialog containing exactly one control — «הבא» — and a woman on the boutique tablet or a 375px phone (no Esc key, no backdrop, no X) can only leave by tapping through to «סיום». Footer, in DOM order, following `SosRaiseDialog:196-201`'s house pattern:

1. **«סגירה»** — `variant="ghost"`, present on every step, calls `close()`.
2. **«הקודם»** — `variant="secondary"`, **absent** on step 1 (DL10).
3. **«הבא»** / **«סיום»** on the last step — `variant="primary"`.

**Consequence, stated so nobody "fixes" it:** the first focusable descendant is therefore «סגירה», and that is where `showModal()` puts focus on open. That is fine and is deliberately not overridden — it is a labelled, non-destructive control, and the step itself is announced by `aria-describedby` regardless of which control holds focus. No `autofocus` attribute, no manual `.focus()`: two engines deciding the entry point is exactly the class of defect D4.1 refuses.

**Rejected: a hand-rolled trap.** LOOP-STATE says "a hand-rolled overlay, NOT a tour library". A native `<dialog>` is neither: it is the platform, it is already in this repo, and hand-rolling a Tab/Shift+Tab cycle over a focusable-selector list would be ~60 lines of the exact code this repo has got wrong five times. The scope fence is about **dependencies**, and F60 adds none.

**Rejected: `Modal`'s width.** `Modal` is `w-[min(28rem,calc(100vw-2rem))]`. Correct here unchanged — see *Every state*, narrow viewport.

### D4 — The focus contract

Everything in this block is browser behaviour of `<dialog>` + `showModal()` unless marked **[F60 code]**. Each line is a named test in *Testing*.

1. **Open.** `showModal()` moves focus into the dialog, onto the first focusable descendant — which, per D3, is «סגירה». **Nothing in F60 calls `.focus()` on open** — the trap's entry is the platform's, and adding a manual move on top of it is how two engines disagree.
2. **The trap.** Tab from the last control in the dialog goes to the first; Shift+Tab from the first goes to the last. Focus cannot reach the console behind it, because `showModal()` makes everything outside the dialog inert.
3. **Esc.** From anywhere inside, Esc fires `cancel` → `Modal`'s `onCancel` → `preventDefault()` + `onClose` → `setOpen(false)` → `close()`. `SosOverlay`'s document capture listener returns early while `dialog[open]` matches (`:298`), so Esc can never mean two things at once.
4. **Return.** `close()` returns focus to the element that was focused when `showModal()` ran — the «מדריך» button. This holds for **all four** close routes: Esc, «סגירה», the last step's «סיום», and D6's SOS close.
5. **Never unbidden. [F60 code]** `open` is `useState(false)` and is set `true` in exactly one place: the trigger's `onClick`. There is no effect, no timer, no storage read and no "first visit" branch anywhere in this feature. A guide that opened itself would steal focus from a receptionist mid-phone-number, which is precisely the defect `SosOverlay:15-27` exists to avoid.
6. **Step changes do not move focus. [F60 code]** «הבא»/«הקודם» change `index` and nothing else. Focus stays on the button she pressed, so four steps cost four presses and not four presses plus four Tabs. The step is announced instead — D5.

**One consequence, stated so a builder does not "fix" it:** on the last step «הבא» is replaced by «סיום», so the control under her finger changes identity. That is deliberate — it is the same position, it is labelled, and the alternative (a disabled «הבא» beside a «סיום») puts a dead control inside a trap.

### D5 — The announcement contract

Three mechanisms, each doing exactly one job.

| When | What announces it | Why not the others |
|---|---|---|
| Open | the dialog's `aria-labelledby` (title) + `aria-describedby` (D3) → the step paragraph | A live region freshly inserted with content is announced by some ATs and not others. Unreliable is worse than silent. |
| Step change | an `sr-only` `<p role="status">`, **mounted for the dialog's whole lifetime**, whose text is set from an effect on `index` | `aria-describedby` does not re-fire when the described text changes. Moving focus would announce it but costs D4.6. |
| Close | nothing | Focus returns to a labelled button, which the AT reads. A cue for "the help closed" is noise. |

**"On CHANGE, not on every render"** is enforced by four properties together, and the spec calls all four because each is one line and each has been got wrong elsewhere in this repo:

1. The region is **never conditionally mounted**. `Modal` renders its children unconditionally (`Modal.tsx:53`) — the `<dialog>` and everything in it stay mounted whether `open` is true or false, hidden only by the UA's `display:none` on a closed dialog. Remounting a live region re-announces it, which would fire on every unrelated re-render of the section behind.
2. Its content is **state**, written by `useEffect(…, [index])` — not `t(steps[index])` inline. The mechanism is the one `AtelierSection.tsx:445-449` records: assigning a string to a text node produces a real childList mutation inside `role="status"` **even when the two strings are byte-identical**, and `setState` with an equal value is a React no-op, so **the `setState` itself is the guard**.
3. That effect **skips its first run after open**, via a ref reset in the trigger's `onClick`. Without it, open would announce twice — once through `aria-describedby` and once through the region.
4. **The region's text is CLEARED on open**, by `setAnnounced("")` in the same ordered `onClick` as `setIndex(0)` and the ref reset. Because the region is never unmounted (property 1) and the effect deliberately skips its first run (property 3), without this the region still holds the **last step of the previously visited section**, and it transitions from `display:none` to exposed carrying that stale sentence — which several ATs announce. That is the exact "unreliable is worse than silent" failure this table rejects a live region for on open, and it is invisible on the first open of a session, which is why §5's assertion has a close-navigate-reopen leg.

Going *back* to step 1 does announce, because `index` changed. That is correct and is why the region is not merely "empty on the first step" — it is **empty on every open**, and carries whatever the last `index` change produced thereafter.

The counter «שלב 2 מתוך 4» is part of the visible step chrome and part of the region's text. **Both digits must sit between Hebrew words in the Hebrew string** — neither at a string edge, neither adjacent to a neutral — so no `isolateLtr` wrapper is needed. This is a copy-deck constraint (D8), not a code one.

### D6 — An SOS page arriving while the guide is open: **the emergency wins, and the only way it can win is for the guide to close**

The mechanism, stated plainly because it is counter-intuitive: `showModal()` promotes the dialog to the **top layer**, which paints above every `z-index` — including `SosOverlay`'s `z-40` — and makes every node outside the dialog **inert**. So with the guide open, an arriving emergency page would be both *invisible* and *unanswerable*: not merely covered, but unclickable and unreachable by Tab. There is no z-index, no portal and no stacking context that changes this. Raising `SosOverlay` above a top-layer dialog is not possible.

**Ruling: a rising page closes the guide.** `GuideOverlay` reads `useSos()` and closes on the **edge** — a `for_me` key appearing that was not there before — mirroring `SosOverlay`'s own `risingKey`/ref shape (`:129-136`, `:197-206`):

```ts
const { alerts } = useSos();

// ⚠ THE KEY IS THE COMPOSITE SosOverlay ALREADY USES (`dismissKey`,
// SosOverlay.tsx:59-61), NOT THE BARE ID. Escalation at t=30s and the stall at
// t=2min each RE-RISE a dismissed card under the SAME id — that is F37's safety
// net for «the first responder did not come» — so an id-keyed detector is
// structurally blind to exactly the alert this guard exists for. A change to one
// key is a change to both.
const forMe = alerts
  .filter((a) => a.for_me)
  .map((a) => `${a.id}:${a.escalated}:${a.stalled}`);

// SosOverlay:129-136's shape: a joined string is the dependency, a ref carries
// the live list, because the array is rebuilt every render.
const risingKey = forMe.join("|");
const forMeRef = useRef<readonly string[]>(forMe);
forMeRef.current = forMe;
// Seeded with what is ALREADY live at mount, so a page raised before she opened
// the guide does not slam it shut (DL12).
const seenRef = useRef<readonly string[]>(forMe);

useEffect(() => {
  const keys = forMeRef.current;
  // ⚠ SET DIFFERENCE, NEVER THE HEAD OF THE LIST. `alerts` is oldest-first
  // (sos.tsx:129-131), so a NEW page ARRIVES AT THE END: any test on keys[0]
  // never fires while an older page is still live — which is precisely the case
  // where a top-layer dialog is most dangerous, because the second emergency
  // lands under a dialog the first one already failed to close.
  const grew = keys.some((k) => !seenRef.current.includes(k));
  seenRef.current = keys;
  if (grew) setOpen(false);
}, [risingKey]);
```

**Edge and not level, and this is the whole of that half of the decision.** A level trigger (`if (forMe.length > 0) setOpen(false)`) would close the guide on *every poll tick* for as long as a live-but-dismissed alert exists, so a staffer who dismissed a page could never open the guide again. Dismissal in this product is deliberate and per-device (`SosOverlay:322-330`), and after it the guide is hers to open.

**Set difference and composite key, and this is the other half.** Two sequences, both entirely within shipped behaviour, defeat any simpler detector and both end with an unanswerable emergency:

- *A second page.* Alert A is live and dismissed on this device; she opens the guide; alert B is raised. `alerts` becomes `[A, B]`. A detector that tests only the head of the list sees `A`, which it has already seen, and does nothing.
- *A re-rise.* She dismissed a live page, opened the guide, and at t=30s the alert **escalates**. `SosOverlay` re-raises the card under the same `id`. An id-keyed detector cannot see it at all — and the escalation exists precisely for "the first responder did not come".

**Why not disable or hide the «מדריך» button during an emergency.** Both were considered and both ship the sixth focus-drops-to-`<body>` defect: if her focus is on the trigger when the alert lands, `close()` returns focus to a button that the same commit has just disabled or unmounted, and Chromium drops to `<body>`. The button stays enabled.

**What the user sees.** Guide closes; focus returns to the «מדריך» button; the red page is on screen. From the trigger, Esc routes her into «אני מגיעה» via `SosOverlay`'s listener, which is un-guarded again because `dialog[open]` no longer matches.

**Effect ordering, and the one thing the earlier draft of this spec got wrong.** `SosOverlay` is mounted before `ConsoleShell` (`App.tsx:236-237`), so its effects flush first — in the commit in which the alert arrives, while the guide is still open. The invariant that matters there is **not** "focus is on the trigger": `showModal()` moved focus **into the dialog** (D4.1), and that is the whole point of the trap. Whether `document.activeElement` can degrade to `<body>` after a click on non-focusable dialog content is engine-dependent and **must not be assumed either way** — T4's own setup ("click the step paragraph") is exactly that state.

So MOVE A's guard may read true, and if it does, `cardRefs.current.get(ids[0])?.focus()` runs against a node `showModal()` has made inert: the call is a no-op, but `hadCardsRef.current` was already set, so **MOVE A is consumed for that alert and will not fire again**. That outcome is **accepted, not engineered around**, for one reason: focus is not lost. `close()` returns it to the labelled «מדריך» button, which is a valid destination in F37's own vocabulary (MOVE B's fallback is `#console-main`, which is less specific than a named button), and the Esc route-in reaches «אני מגיעה» in one keypress the moment the dialog closes. The alternative — closing the guide from a `useLayoutEffect` so the dialog is gone before `SosOverlay` samples `activeElement` — buys back one focus move at the cost of a layout-effect ordering dependency between two components that otherwise know nothing about each other. Not worth it. **T7 exercises the click-first path explicitly** so this is measured in Chromium rather than reasoned about here.

**Scope.** Only a `for_me` page closes the guide. The channel-down strip and the "N hidden" affordance are not full-screen, are not urgent, and closing a guide for them would be noise.

### D7 — The storefront `/checkin` hint is a **reveal-only disclosure** — no dialog, no focus move, no Esc

Different surface, different shell, different user, and the codebase has already ruled on this trade twice. `/checkin` has no `ConsoleShell`, no `SosProvider`, and a **fixed `A11yMenu` trigger in the block-end inline-end corner on every route** (`StorefrontLayout.tsx:186-199`) — a second fixed control would collide with the statutory one.

**Shape:** a plain `Button variant="ghost" size="md"` in the page flow, carrying `aria-expanded={revealed}` and `aria-controls={revealed ? hintId : undefined}`, with `<p id={hintId}>` **immediately after it in DOM order**. That is the APG disclosure pattern in full: `aria-expanded` announces the state, and the reader's very next item *is* the hint. **Nothing else.** No `tabIndex={-1}`, no ref, no effect, no `onKeyDown`.

**Why the focus move is refused, given that `ManageBookingPage` ships one.** Three reasons, and the third is decisive:

1. `ManageBookingPage` has **no Esc handler** — grep the file. Its close is a ghost button (`:469-483`). The earlier draft attributed an Esc handler to it that does not exist, and an Esc handler is only needed *because* focus moved.
2. That focus move is the one frontend entry on `LOOP-STATE.md`'s `known_flaky` list — *"the cancel two-step :: moves focus into the revealed block, onto the question itself"*, a jsdom focus/timing race that has already parked a green PR — and **two shipped design decks recorded a deliberate decision to avoid the shape for exactly that reason** (`fitting-rooms/design.md` §5.3, `floor-dispatch/design.md` P-4: *"A11y coverage is a reason to pick the simpler element"*). Adopting it here would be the third feature to inherit a known flake onto a merge gate, on the lowest-priority item in the program.
3. There is nothing to move focus *to*. `ManageBookingPage` reveals a decision with two buttons; this reveals one sentence with nothing focusable in it. A `tabIndex={-1}` paragraph is a focus destination invented so that an Esc handler has something to close from — and that Esc handler half-works anyway, since one Tab out of a childless `<p>` leaves Esc doing nothing.

Deleting the move deletes the ref, the effect, the `onKeyDown`, the Esc contract and R5, and roughly half of D7's code. **T9 is unchanged** — reveal, Tab, focus reaches the name field — because "nothing is trapped" is the only claim on this surface that matters.

**Placement:** below the `pointer` offer link when it renders (`CheckinPage.tsx:254-266`, *"An OFFER, above the form, never a redirect"*), above the first `<Input>` in both cases. Putting an orientation hint above a live "resume your existing ticket" link would bury the more useful control. `size="md"` (`min-h-11`), matching the retry (`:242`) and submit (`:316-324`) buttons and the visit-type chips' explicit `min-h-11 min-w-11` (`:35`) — this page has a 44px floor on a public phone surface and F60 does not lower it. WCAG 2.0 AA has no target-size SC, so this is convention rather than compliance, and it is cheaper to follow than to justify.

**Content — and this changed after review.** The hint is about **the queue, and only the queue**: what checking in puts her into (the walk-in line for this boutique), what she gets back (a ticket page she can keep open on her phone), and that a member of staff calls her. It states **no data-handling fact of any kind**. See DL15 for why the earlier framing ("what the form does with her details") was not merely redundant but unwritable and out of gate.

The disclosure is withheld in both degraded arms, exactly like the form (`CheckinPage.tsx:229-248`): no boutique, no form, nothing to explain.

### D8 — i18n: one flat `guide.*` namespace in the console, two keys under the storefront's existing `checkin`

**Console** (`frontend/apps/manage/src/i18n/he.ts`), flat dotted literals like every feature since F15: 36 step keys `guide.<section>.<n>`, plus 7 chrome keys — `guide.trigger` («מדריך»), `guide.title`, `guide.progress`, `guide.next`, `guide.prev`, `guide.done`, `guide.close` («סגירה»). **43 keys.** `ar.ts` carries all 43 with the **approved Hebrew value**, per the standing Q3 ruling and the ruling of 2026-07-31 ("Hebrew only for now… every feature keeps shipping `ar` keys untranslated").

**No `guide.triggerAria`.** The trigger's accessible name is its visible text «מדריך», full stop. A per-section `aria-label` would duplicate what `guide.title` already announces the instant the dialog opens, and an `aria-label` on a button with visible text is the single shape WCAG 2.5.3 can fail — so it would buy a duplicate announcement in exchange for one extra key, one extra test loop and one legal risk, on a feature that ships no capability. With it gone, 2.5.3 is true by construction here and `i18n.test.ts` needs no 2.5.3 loop for this block. If a per-section name is ever genuinely wanted, it is one key away.

**`guide.close` is a new key rather than a reuse of `rooms.cancel`.** `SosRaiseDialog` reuses «ביטול» because it is dismissing an action in progress. This dialog has no action in progress — «ביטול» on a walkthrough reads as "cancel *what*?" — so it gets «סגירה». One key, and it keeps the register honest.

`i18n.test.ts` gains, following the shipped block-per-feature shape exactly:
- `const HE_F60 = entries(he.translation, (key) => key.startsWith("guide."));` — **no `nav.` term**, deliberately: the guide is a header control and adds no nav row, and `guide.trigger` is not `nav.guide`.
- `...HE_F60` spread into `HE`. **A block declared and not spread is skipped silently and greenly** by the resolve check, both register guards and the `ar` parity guard — the file says so four times.
- `expect(HE_F60.length).toBeGreaterThanOrEqual(43);`
- An `ar` **value**-parity guard of its own, in the shape of the three shipped twins (`HE_F36`, `HE_F58`, `HE_F37`): `HE_F60.filter(([k, v]) => arTranslation[k] !== v)` must be `[]`. Presence alone passes on an English string, a `TODO`, or a different Hebrew wording.

The register guards over `HE` (no `!`, no `/נשלח|תישלח|בדרך/`) now cover 43 more strings. Instructional copy has no reason to reach for any of them; **`guide.bookings.3` is the one at risk**, since "what the customer is told" is a sentence about messaging. Write it as what the console *records*, never as a promise that something was sent.

**Storefront** (`frontend/apps/storefront/src/i18n/he.ts`): **two keys under the existing `checkin` section** (`he.ts:408`) — `checkin.guideTrigger` and `checkin.guideHint` — not a new top-level `guide` section. Both strings render on that page and nowhere else, and `checkin` is already in `SECTIONS`, so `i18n-keys.test.ts`'s dotted-literal source scan (`:21`, `:39`) covers them with no edit. Mirrored in `ar.ts`, and `i18n-keys.test.ts` gains **one new `it` that is a real value-parity check** — `ar.checkin.guideTrigger === he.checkin.guideTrigger` and the same for `guideHint`. Say this plainly in the plan, because the F19 block it sits beside (`:145-155`) is a **presence** check (`typeof resolve(key, ar.translation) === "string"`) and the storefront has never had a value-parity guard anywhere. This adds the first one, scoped to these two keys; widening it is a different feature's decision to take.

---

## Frontend changes

### New files

| File | What |
|---|---|
| `frontend/apps/manage/src/lib/guide.ts` | `SectionKey` (moved from `App.tsx`, member order and comments preserved) + `GUIDE_STEPS` (D2). ~30 lines, no imports from `App.tsx`. |
| `frontend/apps/manage/src/components/GuideOverlay.tsx` | The trigger button + the `Modal` + the live region + the SOS close effect. ~95 lines. |
| `frontend/apps/manage/src/__tests__/GuideOverlay.test.tsx` | The vitest block. |
| `frontend/e2e/guide.spec.ts` | The Chromium block — the focus contract. |

### Changed files

| File | Change |
|---|---|
| `frontend/packages/ui/src/components/Modal.tsx` | `describedById?: string` on `ModalProps`; `aria-describedby={describedById}` on the `<dialog>`. Two lines. |
| `frontend/packages/ui/src/components/ConsoleShell.tsx` | `guide?: ReactNode` on `ConsoleShellProps`; the two right-hand header controls wrapped in one `<div className="flex items-center gap-4">{guide}<button …logout/></div>` so `justify-between` keeps two groups (DL18). Three lines. |
| `frontend/packages/ui/src/index.ts` | Nothing — both types are already exported via `ModalProps`/`ConsoleShellProps`. |
| `frontend/apps/manage/src/App.tsx` | Delete the local `type SectionKey`; `import type { SectionKey } from "./lib/guide"`; pass `guide={<GuideOverlay section={activeKey} />}` to `ConsoleShell`. Three lines; **`NAV`, `reachable` and `activeKey` are untouched.** |
| `frontend/apps/manage/src/i18n/he.ts`, `ar.ts` | +43 keys each (D8). |
| `frontend/apps/manage/src/__tests__/i18n.test.ts` | `HE_F60`, the spread, the floor, the `ar` value-parity guard (D8). **No 2.5.3 loop** — there is no `*Aria` key in this block. |
| `frontend/apps/storefront/src/routes/CheckinPage.tsx` | The disclosure (D7): one `Button`, one `<p>`, one `useState`. ~12 lines. No ref, no effect, no `onKeyDown`. |
| `frontend/apps/storefront/src/i18n/he.ts`, `ar.ts` | +2 keys each, under the existing `checkin` section. |
| `frontend/apps/storefront/src/__tests__/CheckinPage.test.tsx` | The disclosure's states. |
| `frontend/apps/storefront/src/__tests__/i18n-keys.test.ts` | One `it`: `ar` **value** parity for the two `checkin.guide*` keys (D8). |

### Types

```ts
// lib/guide.ts
export type SectionKey = /* the 14, in App.tsx:24-41's SHIPPED member order, comments kept */;
export const GUIDE_STEPS: /* as const satisfies Record<SectionKey, readonly [string, ...string[]]> */;

// GuideOverlay.tsx
interface GuideOverlayProps { section: SectionKey }

// packages/ui — ModalProps gains:
describedById?: string;
// packages/ui — ConsoleShellProps gains:
guide?: ReactNode;
```

### Per-component behaviour

**`GuideOverlay`** — state is `open: boolean`, `index: number`, `announced: string`. `useId()` for the body id (a console may mount one guide, but `useId` is the repo's standing rule and costs nothing). Reads `useSos()` for D6 only. On the trigger's `onClick`, **in this order**: `setIndex(0)`, `setAnnounced("")`, reset the skip-first ref, `setOpen(true)` — so the dialog opens on step 1 every time, with an empty live region, and a reopen never resumes mid-walkthrough nor re-announces a previous section's sentence (D5.4). Footer per D3: «סגירה» (ghost, every step), «הקודם» (secondary, absent on step 1), «הבא»/«סיום» (primary). The counter renders above the footer.

**`ConsoleShell`** — renders `{guide}` inside a new `flex items-center gap-4` wrapper beside the logout button, inside the existing header row. No logic, no default, no knowledge of sections.

**`CheckinPage`** — one `revealed` boolean; the button carries `aria-expanded={revealed}` and `aria-controls` only while revealed (a dangling IDREF is what axe reports as `aria-valid-attr-value`, per `A11yMenu.tsx:120-122`). The revealed `<p>` sits immediately after the button and takes no focus.

---

## Every state

| State | Console | `/checkin` |
|---|---|---|
| **Closed** | Only the «מדריך» button in the header. `<dialog>` is in the DOM (Modal renders it unconditionally) with no `open` attribute, so `SosOverlay`'s guard does not match and Esc keeps its SOS meaning. | Only the button. `aria-expanded="false"`, no `aria-controls`. |
| **First step** | Counter «שלב 1 מתוך N». Footer is «סגירה» + «הבא» (or «סיום» when N = 1). **«הקודם» is absent, not disabled** — a dead control inside a trap is a Tab stop she must walk past for nothing. **A pointer-only user leaves here in one tap, via «סגירה»** — there is no backdrop dismiss in this repo's `Modal` and a tablet has no Esc key. Live region **empty**; the step was announced by `aria-describedby`. | n/a — the hint is one paragraph, no steps. |
| **Middle step** | «סגירה» + «הקודם» + «הבא». Live region carries the step. | n/a |
| **Last step** | «סגירה» + «הקודם» + **«סיום»**, which closes and returns focus to the trigger. | n/a |
| **Reopened after a section change** | Step 1, counter reset, **live region empty again** (D5.4). The sentence from the previously visited section is gone rather than un-hidden. | n/a |
| **Section with no steps** | **Unrepresentable.** `satisfies Record<SectionKey, readonly [string, ...string[]]>` makes it a compile error, so the button can never offer help that is not there. Verified by the typecheck gate, not a runtime test (D2). | n/a |
| **Out-of-enum role** | `reachable` is empty, `activeKey` stays `dashboard`, and the guide offers `dashboard`'s two steps over `DashboardSection`'s 403 outage panel. **Accepted** — the steps describe a screen, not its data; 0011's CHECK makes the row impossible in the database (D1). | n/a |
| **SOS arrives while open** | Guide closes; focus returns to the trigger; the red page is on screen and reachable (D6). Holds for a **second** page arriving over a first, and for an escalation/stall **re-rise** of an already-seen one. | n/a — no SOS on the storefront. |
| **Narrow viewport (375px)** | `Modal`'s `w-[min(28rem,calc(100vw-2rem))]` gives 16px gutters at 375; the panel covers most of the screen and that is correct — this is a modal and there is nothing behind it to read. Steps are one sentence, so no scroll. Three footer buttons at `size="md"` wrap rather than shrink. | Inline, in normal page flow. Nothing is covered; the form below simply moves down. |
| **`pointer` present + hint revealed** | n/a | Both render: the «התור האחרון מהמכשיר הזה» link first, then the hint's trigger, then the revealed paragraph, then the name field. Reading order is DOM order; nothing is repositioned. |
| **Degraded `/checkin`** | n/a | Withheld in both arms with the form (`CheckinPage.tsx:229-248`) — no boutique, nothing to explain. |
| **Loading** | The guide button renders as soon as the shell does; the sections behind it own their own skeletons. Steps describe a screen, not its data, so they are correct before the data lands. | Withheld with the form during `loading`. |

---

## Acceptance criteria

| # | Criterion | Verified by |
|---|---|---|
| AC1 | `GUIDE_STEPS` covers all fourteen `SectionKey` members; a fifteenth without steps fails the build. | `pnpm --filter manage typecheck` (D2) + `GuideOverlay.test.tsx` §1 |
| AC2 | Every key in `GUIDE_STEPS` resolves to Hebrew — never to the key itself. | `i18n.test.ts` §F60 |
| AC3 | `ar.ts` carries all 43 `guide.*` keys with the approved Hebrew **value**. | `i18n.test.ts` §ar |
| AC4 | No `guide.*` string contains `!` or matches `/נשלח|תישלח|בדרך/`. | `i18n.test.ts` register guards (via the `HE` spread) |
| AC5 | The open dialog's `aria-describedby` is the `id` of the element carrying the current step's Hebrew — the mechanism that makes step 1 audible on open. | `GuideOverlay.test.tsx` §7 |
| AC6 | The guide shows the steps of `activeKey` and of nothing else; a receptionist sees only `floor`'s. | `GuideOverlay.test.tsx` §2 |
| AC7 | The guide **never** opens itself: no effect, timer or storage sets `open`. | `GuideOverlay.test.tsx` §3 |
| AC8 | «הבא»/«הקודם» move one step; «הקודם» is absent on step 1; the primary control is «סיום» on the last step. | `GuideOverlay.test.tsx` §4 |
| AC9 | The live region is empty on **every** open — including a reopen after visiting another section — and carries the new step's text on each change, including a change **back**. | `GuideOverlay.test.tsx` §5 |
| AC10 | A `for_me` alert appearing closes the guide — including a **second** alert arriving beside a live one, and an **escalation re-rise** of an already-seen one; a *persisting* dismissed alert does not stop it reopening. | `GuideOverlay.test.tsx` §6 |
| AC11 | Focus is inside the dialog after open. | `guide.spec.ts` **T1** |
| AC12 | Tab from the last control reaches the first; Shift+Tab from the first reaches the last; neither reaches the console. | `guide.spec.ts` **T2**, **T3** |
| AC13 | Esc from anywhere inside closes it. | `guide.spec.ts` **T4** |
| AC14 | Focus returns to the «מדריך» button on all four close routes. | `guide.spec.ts` **T5**, **T6**, **T6b**, **T7** |
| AC15 | Esc inside the guide never routes into an SOS card; the SOS Esc route-in works again once it closes. | `guide.spec.ts` **T8** |
| AC16 | `/checkin`'s hint reveals, flips `aria-expanded`, **moves no focus**, and traps nothing. | `CheckinPage.test.tsx` + `guide.spec.ts` **T9** |
| AC17 | Zero axe A/AA violations with the guide open (console) and revealed (`/checkin`). | `guide.spec.ts` axe passes |
| AC18 | `describedById` changes no shipped `Modal` caller's behaviour. **Fifteen call sites cannot be verified by naming four**, so the criterion is the whole suites: `pnpm --filter manage test` and `pnpm --filter ui test` stay green, `Modal.test.tsx` included. | full frontend unit suites |
| AC19 | Every step of the guide contains a working dismiss control reachable by pointer alone. | `GuideOverlay.test.tsx` §4 + `guide.spec.ts` **T6b** |

---

## Testing

### Frontend (vitest, jsdom)

**Rule, and it is the most important line in this section: no vitest test in this feature may assert `document.activeElement`, `dialog[open]`-driven focus, Tab order, or Esc-through-`cancel`.** jsdom 29.1.1 has no `<dialog>` implementation (the impl file is an empty subclass) and the repo's `setup.ts` stub is `this.open = true` and nothing more. Any such assertion measures the stub. This is the same class of defect as F57's vacuous focus test, and it is why every focus criterion above points at `guide.spec.ts`.

`GuideOverlay.test.tsx`:
1. **the table covers every section** — `Object.keys(GUIDE_STEPS)` equals the fourteen keys, by set equality, and every entry is non-empty.
2. **the guide shows the active section's steps** — render at `section="floor"`, open, assert step 1's Hebrew; assert `dashboard`'s step 1 is *absent*.
3. **it never opens itself** — render with alerts present and absent, advance timers, assert the dialog has no `open` attribute until the trigger is clicked.
4. **the controls** — «סגירה» present on step 1 **and** on the last step (AC19; no focus assertion, so DL17-safe); «הקודם» absent on step 1, present on step 2; primary reads «סיום» on the last step and calls close.
5. **the region announces on change, not on open, and never carries a stale sentence** — open, assert empty; «הבא», assert step 2; «הקודם», assert step 1; **close, rerender at a different `section`, reopen, assert empty again.** That last leg is the only one that fails if `setAnnounced("")` is missing from the trigger's `onClick`; the first leg is true on a session's first open regardless.
6. **an SOS page closes it — in all three shapes — and a dismissed one does not lock it shut.** Four cases:
   a. zero → one `for_me` alert: the dialog's `open` attribute is gone;
   b. rerender with the *same* alert list: the trigger reopens it (DL12);
   c. **one live alert already seen, guide reopened, then a SECOND arrives appended at the end** (`[A]` → `[A, B]`): `open` is gone. Fails against any head-of-list detector;
   d. **the same alert's `escalated` flipping `false` → `true`** with no id change: `open` is gone. Fails against any id-only detector.
7. **`aria-describedby` points at the step** (AC5) — open at `section="floor"`, read `screen.getByRole("dialog").getAttribute("aria-describedby")`, assert it is non-null and is the `id` of the element whose text is `guide.floor.1`'s Hebrew. The deletion that must redden it: drop `aria-describedby={describedById}` from `Modal.tsx`.

`CheckinPage.test.tsx`: the hint reveals, `aria-expanded` flips, `aria-controls` is absent while closed, and the hint is withheld in both degraded arms.

`i18n.test.ts` / `i18n-keys.test.ts`: as D8.

### E2E (Playwright, Chromium) — `frontend/e2e/guide.spec.ts`

On `installManageApi`, following `manage.spec.ts`'s harness. **There is no shared login helper**: `guide.spec.ts` copies `sos.spec.ts`'s local login block (`const LOGIN_SUBMIT = "כניסה"` plus the fill-and-submit steps, about six lines). Extracting a shared helper is out of scope for this feature; say so rather than sending a builder hunting for a function that does not exist.

**Locators.** `Modal` sets **no `role` attribute** — `<dialog>` carries only an implicit ARIA role. Use `page.getByRole("dialog")`, which resolves it through the accessibility tree, or the CSS `dialog[open]`, which is the same selector `SosOverlay.tsx:298` uses. **`page.locator("[role=dialog]")` and `document.querySelector("[role=dialog]")` match nothing** and are the vacuity class this section exists to prevent. Every focus assertion is **positive** — `expect(<named locator>).toBeFocused()` — and a `not.toBeFocused()` may only ever appear *in addition to* one.

**For each test, the deletion that must turn it red:**

| # | Test | Deletion that must turn it red |
|---|---|---|
| **T1** | *the guide opens with focus inside it* — after clicking «מדריך», `expect(page.getByRole("dialog").getByRole("button", { name: "סגירה" })).toBeFocused()`. | `Modal.tsx:29`: `dlg.showModal()` → `dlg.show()`. A non-modal dialog moves no focus; T1 finds focus still on the trigger. |
| **T2** | *Tab from the last control returns to the first* — focus «הבא»/«סיום», press Tab, `expect(<the dialog's first control>).toBeFocused()`. | Same one-token deletion. Without modality Tab leaves the dialog into the console header and T2 finds the logout button. |
| **T3** | *Shift+Tab from the first control reaches the last, never the console* — assert the last control **is** focused, and additionally `expect(logout).not.toBeFocused()`. | Same. Also red if `<dialog>` is swapped for a `<div>`. |
| **T4** | *Esc from the step body closes it* — click the step paragraph, press Esc, `expect(page.getByRole("dialog")).toBeHidden()`. | **`Modal.tsx:29`: `dlg.showModal()` → `dlg.show()`.** A non-modal `<dialog>` has no close watcher, so Esc does not close it at all and T4 finds it still open. ⚠ **Two other deletions were proposed and BOTH come back green — do not use them.** Deleting `onCancel` alone leaves `onClose={onClose}` (`:43`) wired: Esc closes the dialog natively, `close` fires, `onClose()` runs `setOpen(false)`, the effect's `!open && !dlg.open` branch is a no-op, and the browser has already returned focus to the trigger. Deleting **both** is no better: `open` never changes, so the effect on `[open]` never re-runs and nothing reopens the dialog. What `onCancel` uniquely buys is already pinned by the shipped unit test at `packages/ui/src/__tests__/Modal.test.tsx:18-34` (a bare `cancel` event calls `onClose` once and does not fire the confirm) — cite that rather than inventing a browser mutation for it. |
| **T5** | *Esc returns focus to the «מדריך» button.* | Same deletion as T4, and also red if the trigger is unmounted while open. |
| **T6** | *«סיום» on the last step returns focus to the «מדריך» button.* | `GuideOverlay`: replace `setOpen(false)` with an unmount of the whole component. Focus drops to `<body>` and T6 goes red — which is the exact defect class this repo has shipped five times. |
| **T6b** | *a pointer-only user can leave from step 1* — open the guide, click «סגירה» **without pressing any key**, assert the dialog is gone and `expect(guideTrigger).toBeFocused()`. | `GuideOverlay`: remove «סגירה» from the footer. T6b then has nothing to click — the exact state a keyboard-less tablet is left in. |
| **T7** | *an SOS page closes the guide and returns focus to the button, the red page is on screen, and its ack is clickable* — **and this runs twice**: (a) with focus untouched after open; (b) after clicking the step paragraph first, which is the `activeElement` state D6 refuses to assume anything about. Then a **third** leg: with one alert already live and dismissed and the guide reopened over it, raise a **second** alert and assert the new card's «אני מגיעה» is clickable. | `GuideOverlay`: delete the D6 effect. The guide stays open in the top layer, the ack is inert, and T7 fails on the click — not merely on a focus assertion. Leg (c) additionally reddens if the detector tests only the head of the alert list. |
| **T8** | *Esc means one thing at a time.* **Setup, explicitly, because D6 makes the naive setup unreachable:** install a `for_me` alert in the **first** poll response and wait for the red page — the D6 edge is consumed by that arrival — **then** click «מדריך» (DL13 keeps the trigger enabled, DL12 keeps the close edge-triggered, so it opens). Assert the dialog is open. Press Esc: the dialog closes and «אני מגיעה» is **not** focused. Press Esc again: it is. | `SosOverlay.tsx:298`: delete the `dialog[open]` guard. The listener then reaches `event.preventDefault()` (`:312`), which **suppresses the dialog's own close request** — so the first Esc focuses the ack and the guide stays open. T8 goes red on its first assertion. (The earlier claim that it "fires both" was wrong; the capture listener's `preventDefault` is why.) |
| **T9** | *`/checkin`'s hint traps nothing* — reveal it, Tab, and assert focus reaches the name field. | `CheckinPage`: convert the disclosure to a `Modal`. T9 then finds focus trapped and goes red. |

Plus two axe passes (`wcag2a`, `wcag2aa`): the console with the guide open, `/checkin` with the hint revealed.

**What none of this proves.** The e2e harness stubs the API (`manage.spec.ts:32-34`'s Risk 6), so these prove the console, not a contract. F60 has no contract to prove — it calls no endpoint.

---

## Out of scope

Anchoring, highlighting or spotlighting a real element. Any positioning engine. Persisting "seen"/"dismissed" per staffer. Auto-opening on first login. A guide on any storefront route other than `/checkin`. A guide on the login screen. Video, images or links inside a step. An `en` bundle (Hebrew only, ruling 2026-07-31). A guide for the public queue board `/queue` — it is a wall display with no reader standing at it. Extracting a shared Playwright login helper out of `manage.spec.ts` / `sos.spec.ts`. Widening the storefront's new `ar` value-parity check beyond the two `checkin.guide*` keys.

---

## Codebase conflicts recorded

1. **`LOOP-STATE.md` F60 `deps: [F34]` is incomplete and, on the one dependency that matters, wrong.** F34 (the shift board) is one of fourteen sections and F60 touches none of its code. The dependencies that actually constrain this build are **F37** (`SosProvider`/`useSos` and `SosOverlay`'s `dialog[open]` Esc guard — D6 exists only because F37 shipped), **F33** (`CheckinPage`), and the shipped `ConsoleShell`/`Modal`. Recorded, not repaired: LOOP-STATE is not this spec's to edit.
2. **`LOOP-STATE.md` says "Focus trap and Esc-to-close are the real work here." As shipped, they are already done.** `Modal` has provided a native trap, native Esc and native focus-return since F5, and fifteen call sites ride it. The real work that remains is (a) the announcement contract, which no native mechanism covers (D5), (b) the SOS top-layer collision, which is a genuine hazard nothing in LOOP-STATE anticipates (D6), (c) the fact that **the trap cannot be tested in this repo's unit suite at all** (DL17), and (d) — added at review — **the pointer-only exit**, because a native `<dialog>` gives Esc for free and gives a tablet nothing (D3, DL19). A builder who reads the note literally and hand-rolls a Tab cycle will write ~60 lines of the most defect-prone code in the console for no gain.
3. **Three shipped comments now under-count the console's sections.** `SosOverlay.tsx:12` says "on all thirteen sections"; `:230` and `:620-621` say "the eleven sections with no `SosCentre`"; `App.tsx:230` says "eleven sections that poll nothing else". The shipped `SectionKey` has **fourteen** members and `NAV` has **fourteen** rows (owner sees thirteen, shift manager eleven — `Nav.test.tsx:152`'s `.slice(0, 11)`). The numbers were true when F37 merged and were overtaken by F41's `atelier` and F33's `checkinQr`. **F60 does not fix them** — it edits neither file, and a drive-by comment repair inside an emergency component is exactly the kind of unrelated diff this program's review would send back. Recorded for whoever next opens `SosOverlay.tsx`.
4. **No dependency is needed, and this is stated as a positive finding** because the brief invited a challenge. The three things a tour library sells — a focus trap, a positioning engine and a step state machine — are respectively already in the repo (native `<dialog>`), not in scope (nothing is anchored), and eleven lines of `useState`.
5. **`Modal` has no backdrop-click dismissal, and its `:7` comment reads as though it does.** *"Dismiss (Esc, backdrop, cancel button)"* describes what `onClose` **means**; no `onClick` is bound to the `<dialog>` and none of the fifteen callers relies on one. Every one of them supplies an explicit dismiss in `footer`. Recorded because the comment is the reason a reviewer might wave through a footer with no dismiss.

---

## Risks & open items

| # | Risk | Owner |
|---|---|---|
| R1 | **The copy is 36 sentences describing fourteen screens that changed nine times today.** A step that names a control which has moved is worse than no guide — it is a screen that is authoritative and wrong. The copy deck is a build task and each sentence must be written with the section component open, not from D1's table. | Builder, at the copy-deck task |
| R2 | **`describedById` on `Modal` touches a component with FIFTEEN production call sites.** The prop is optional and omitted renders no attribute, so the actual risk stays low — but `Modal` is gate-passed, any change to it re-opens it for review, and two of the fifteen are inside `AtelierSection` (the console's largest component) and two more inside `BookingDetail`. AC18 is the whole unit suites, not four named files. | Reviewer |
| R3 | **T1–T9 are the only proof the trap exists**, and they run only in the E2E job. If that job is ever made `continue-on-error`, this feature silently loses its entire safety argument and every remaining test still passes. | Whoever next edits `merge-gate.sh` |
| R4 | **D6's edge detector is the one piece of non-obvious logic in the feature, and it has two independent ways to be wrong** — a level trigger (reopens "she can never open the guide again") and a key that is not `SosOverlay`'s composite (goes blind to a second page and to every escalation re-rise). The tests that catch them are §6c and §6d, and both are easy to read as redundant. The comment on the effect must say why, in the shape `SosOverlay:48-58` uses for its own composite key, and must name `sos.tsx:129-131`'s oldest-first ordering as the reason the detector is a set difference. | Builder |
| R5 | *Withdrawn at review.* The `/checkin` hint no longer moves focus (D7), so it does not inherit `known_flaky`'s jsdom focus race. The rule it was quoting still applies to whoever eventually fixes that entry: fix the wait, do not raise the timeout. | — |
| R6 | **Fifteenth section.** Whoever adds it gets a type error in `guide.ts` and will be tempted to satisfy it with a placeholder sentence. A placeholder is a lie with a compile-time blessing; the type buys a prompt, not a guarantee. | Reviewer, on the next `SectionKey` PR |
| R7 | **The console's `i18n.test.ts` has no source scanner**, so a `guide.*` key that exists in `he.ts` and is never rendered passes every console guard — the floor count and the parity guard both count it. The only thing standing between the copy deck and a dead key is `GUIDE_STEPS`'s literal list and §1's set equality. | Builder, at the copy-deck task |

---

## Decisions Log

| # | Decision | Why |
|---|---|---|
| DL1 | The overlay is `@boutique/ui`'s `Modal` (native `<dialog>` + `showModal()`), not a hand-rolled trap. | The scope fence bans a **dependency**, not the platform. A native dialog is already in this repo, already trusted by fifteen call sites, and gives the trap, Esc and focus-return for zero lines. Hand-rolling them is ~60 lines of the code this repo has got wrong five times. |
| DL2 | `Modal` gains one optional prop, `describedById`. | Without it a screen-reader user hears the dialog's name and the focused button but never the step. Optional and omitted → attribute absent → all fifteen shipped callers unchanged. It gets its own test (§7/AC5) because it is the only D3 mechanism jsdom can measure honestly, and without one the whole of D3 could be dropped at build time unnoticed. |
| DL3 | `SectionKey` moves to `lib/guide.ts` in its shipped member order; `App.tsx` imports it. | Keeps `guide.ts` free of any import from `App.tsx`, so no import cycle — the failure `router.tsx:205-215` documents, where `vi.mock`'s live binding silently resolves to the real function inside `importActual` and the test passes while asserting nothing. Preserving member order preserves the three ordinal comments and keeps the move a pure cut-and-paste in review. |
| DL4 | "No steps" is a **type error**, not a runtime branch. | `readonly [string, ...string[]]` makes it unrepresentable, and `typecheck` gates the merge. A runtime guard would need an injection seam invented only to test it — more code than the defect. |
| DL5 | Steps are declared as full i18n key literals, never built from a template. | A constructed key renders the literal key into a Hebrew console on a typo. **The console has no source-file scanner** (that is the storefront's `i18n-keys.test.ts`), so the mechanism that actually guards these 36 keys is `HE_F60`'s `startsWith("guide.")` filter and its `>= 43` floor — and a filter can only count keys that exist in `he.ts` as literals. |
| DL6 | Role-gating is inherited from `activeKey`, never re-implemented. | The role filter has exactly one home and `activeKey` (`App.tsx:208-210`) is already it — a second copy would drift the day a `roles` field changes. (`App.tsx:69-73`'s comment is about the opposite direction: the array is cosmetics and the server's RoleGate is the control, so nobody may simplify the gate away on the strength of it.) |
| DL7 | Intra-section role gates (`TermsSection`'s owner-only publish form, the atelier's seamstress branch) are handled in **copy**, not in code. | Two more branches on a cosmetic surface to avoid two sentences being slightly general is a bad trade. The copy describes the section, not a control the reader may not have. |
| DL8 | Step changes do **not** move focus; a live region announces instead. | Moving focus to the step text would cost one Tab back to «הבא» per step — four steps, four extra Tabs. This is the APG pattern for changing content with persistent controls. |
| DL9 | The live region skips its first run after open, is **cleared** on open, and `aria-describedby` covers the open announcement. | Two mechanisms would otherwise both fire on open and announce step 1 twice. And because `Modal` never unmounts its children (`:53`), a region that is not cleared keeps the *previous* section's last sentence and un-hides it on reopen — announced by several ATs, on a screen it does not describe. |
| DL10 | «הקודם» is **absent** on step 1, not disabled — but that is an argument against **dead** controls, not against controls. | Inside a focus trap every Tab stop is one the user must walk past, so a disabled control earns nothing. A working dismiss earns the only pointer exit that exists (DL19); the two are not in tension and the earlier draft read as though they were. |
| DL19 | The footer carries a **persistent ghost «סגירה» on every step**. | `Modal` wires no backdrop click and the chrome has no X. Without it, step 1 of a 3-step guide is a top-layer dialog with exactly one control, and a boutique tablet or a 375px phone — no Esc key — can only leave by tapping through to the end. Every one of the fifteen shipped callers supplies an explicit dismiss (`SosRaiseDialog:196-201` names it "the house pattern"); F60 keeps the pattern. Consequence accepted: `showModal()` focuses it first. |
| DL11 | A rising SOS page **closes** the guide. | `showModal()` promotes to the top layer and inerts the rest of the document. There is no z-index, portal or stacking context that lets `SosOverlay` win, so closing is the only mechanism that exists. The emergency must win. |
| DL12 | The close is **edge**-triggered, and the edge is a **set difference over `SosOverlay`'s composite key**, not the head of the id list and not the bare id. | Level-triggered, a live-but-dismissed alert would slam the guide shut on every 5s poll tick and she could never open it again (dismissal is deliberate and per-device, `SosOverlay:322-330`). Head-of-list, a **second** page is invisible to the detector, because `sos.tsx:129-131` appends oldest-first. Id-only, an **escalation or stall re-rise** is invisible, because `dismissKey` (`SosOverlay:59-61`) is composite for exactly that reason. All three failures end the same way: a full-screen emergency painted under an inert top-layer dialog. |
| DL13 | The «מדריך» button is **never** disabled or hidden during an emergency. | Either one drops focus to `<body>` when `close()` returns focus to a control the same commit removed — the sixth instance of this repo's most-shipped defect. It is also what makes T8's setup reachable at all. |
| DL14 | `/checkin` gets a **reveal-only disclosure** — the shape of `ManageBookingPage`'s inline reveal, explicitly **without** its focus move and without an Esc handler. | The shape is this repo's ruling (`ManageBookingPage.tsx:414-418`). The focus move is not: that file has no Esc handler at all, its focus move is `LOOP-STATE`'s one frontend `known_flaky` entry, and **two shipped design decks already declined the shape on that evidence** (`fitting-rooms/design.md` §5.3, `floor-dispatch/design.md` P-4). APG's disclosure moves no focus — `aria-expanded` announces the state and the reader's next item is the hint — so the move buys nothing and costs a known flake on a merge gate. The fixed `A11yMenu` trigger also owns the only corner a floating control could take. |
| DL15 | The `/checkin` hint states **no data-handling fact of any kind**; it is about the queue. | The earlier framing — "what the form does with her details" *and* "must not restate or paraphrase `checkin.notice`" — has no intersection: the notice **is** the statement of what the form does with her details, so no copywriter could satisfy both. Worse, `CheckinPage.tsx:299-302` rules directly against the placement — *"never behind a disclosure: notice at the moment of collection means visible at the moment of collection"* — so a collapsed «מה קורה עם הפרטים שלי?» beside a legally-mandated always-visible notice is a second, unapproved notice on the same collection point, and it would void this spec's Gate 1 self-approval ("no privacy-law text"). The fence is now positive: the hint names the queue, the ticket page and the staffer call; `:303-305`'s notice remains the only data-handling text on the page. **If the intended content genuinely is data handling, Gate 1 is not self-approving and the feature stops for the user, per Q1.** |
| DL16 | The guide does not persist "seen" and never auto-opens. | Auto-opening steals focus from a receptionist mid-phone-number — the defect `SosOverlay:15-27` exists to avoid — and persistence needs a storage key, which is scope this feature has not earned. |
| DL17 | No vitest test in this feature asserts focus. | jsdom 29.1.1 has no `<dialog>` implementation and the repo's stub is `this.open = true`. Every such assertion would measure the stub. This is F57's vacuous focus test with a different mechanism. §7's `aria-describedby` check is a plain IDREF read and is therefore permitted. |
| DL18 | The trigger goes in `ConsoleShell`'s header beside the logout button, inside a `flex items-center gap-4` wrapper. | It is chrome, not content: one control, on every section, in the one row that is already the console's chrome. The wrapper is needed because the row is `justify-between` with exactly two children today (`:46-51`) and a bare third child spreads to the middle. **No Shift+Tab argument** — the earlier draft claimed the trigger would be "one Shift+Tab from `<main>`", which is false: the `<nav>` of up to thirteen buttons (`:56-81`) sits between the header row and `<main id="console-main">` (`:84`), so Shift+Tab from `<main>` reaches «סליקה ותשלומים». The placement stands on "it is chrome, in the chrome row" alone. |
| DL20 | No `guide.triggerAria`. The trigger's accessible name is its visible «מדריך». | `guide.title` already interpolates the section name and is announced the instant the dialog opens, so a per-section `aria-label` is a duplicate — and an `aria-label` on a button with visible text is the one shape WCAG 2.5.3 can fail. Dropping it removes a key, a 2.5.3 test loop and a legal risk from a feature that ships no capability, and makes 2.5.3 true by construction here. |
| DL21 | The storefront's two strings live under the existing `checkin` section, not a new top-level `guide` one. | Both render on that page and nowhere else, `checkin` (`he.ts:408`) is already in `i18n-keys.test.ts`'s `SECTIONS`, and a section per feature is how a flat namespace becomes fourteen one-key sections. The new `ar` guard is a **value**-parity check (`ar === he`) and is stated as such: the F19 block beside it is a **presence** check, and the storefront has never had a value-parity guard — this is the first, deliberately scoped to two keys. |

---

## Rejected findings

**"D6's MOVE A analysis — close the guide from a layout effect so `SosOverlay` never samples `activeElement` while the dialog is open."** *(the remedy offered as option (b) in the effect-ordering finding; the finding's diagnosis is accepted in full and D6 is rewritten to it — only this remedy is declined.)*

The diagnosis is right and was applied: D6's old sentence — *"MOVE A does not move focus, because MOVE A only fires when `document.activeElement === document.body` and it is on the trigger"* — is simply false. `showModal()` moved focus **into the dialog**; it is not on the trigger; and T4's own setup puts focus on non-focusable dialog content, which is exactly the ambiguous state. D6 now says so.

The **fix** is declined. Converting `GuideOverlay`'s SOS effect to `useLayoutEffect` to win the ordering race creates a cross-component layout-effect ordering dependency between `GuideOverlay` and `SosOverlay` — two components that today share nothing but a context — to buy back one focus move whose absence costs nothing measurable. What actually happens without it: MOVE A is consumed with no effect, native `close()` returns focus to the labelled «מדריך» button, and Esc from there reaches «אני מגיעה» in one keypress. That is a *better* destination than MOVE A's own (`ids[0]`'s card container) by F37's own reasoning, and it is one the Esc route-in already serves. The ordering coupling would be invisible in both components' source, unpinnable by any test that does not already have to exist, and would be the first thing broken by an unrelated React version bump. **Accepted and stated in D6 instead, with T7 leg (b) measuring it in Chromium** — which is the only place this repo believes a focus claim anyway.
