# Screen: Storefront Booking Flow (F14 — `/book/*`, Epic E3)

**Date**: 2026-07-29 · **Status**: **rev 2** — revised against round 1 of adversarial review (three reviewers: brand/tokens, accessibility, spec-coverage; verdict **NEEDS CHANGES**, all findings resolved below). **GATE APPROVED 2026-07-29.** Both outstanding items were signed off in one session: P1–P8 confirmed (§14.1, all boxes checked) and `copy.md` signed off end to end (rev 3 — 61 of 61 rows APPROVED, §7 answered, two keys added at sign-off). The build is unblocked; see §14.1's gate outcome note for the deltas this design inherits from the copy walk.

**Gate log**: drafted 2026-07-29 by five parallel authors (§2–§3, §4–§5, §6–§7, §8–§14, `copy.md`), assembled and reconciled the same day as **R1–R6**; reviewed the same day by three adversarial reviewers, whose findings are resolved as **R7–R31**. Round detail in §14.2.

> **Read the two reconciliation tables before any section.** The per-screen sections were written in parallel and reviewed after assembly, so a section may still argue a position that R1–R31 has overturned. **The tables win.** Losing arguments are deliberately left in place — several of them are the reason the winning ruling is shaped the way it is — and each is marked ⛔ where it lands.

**Binding sources**: `system/tokens.md` (every token; the three-golds law; the `Price` convention; the nine usage laws) · `system/components.md` (reuse before invent) · `screens/design-system/README.md` + `storefront-catalog.md` + `storefront-dress-detail.md` + `storefront-profile-hours.md` (the storefront dialect this continues) · `screens/manage-catalog/manage-catalog.md` (the document's structural template only — its visual language is the *console* dialect and is not this screen's) · **`specs/storefront-booking-ui.md` (the contract: its State matrix is the single source for states, and its Decisions Log D1–D12 are locked)**.

**What this document is for.** F13 shipped the endpoint that writes a booking and nothing calls it. This is the customer-facing flow: a bride, in Hebrew, right-to-left, usually on a 375px phone reached from an Instagram bio link, who has to pick a time, give her name, accept a cancellation policy and prove her number over SMS — **without a single dead end that leaves her not knowing whether she has an appointment.** That last clause is the feature's whole reason to exist, and §12.4 is where it is checked.

---

## Reconciliations — binding, and they override any section below

The per-screen sections were drafted in parallel and could not see one another. Six genuine conflicts surfaced during assembly. Each is ruled here, once. **Where a section below still reads the other way, this table wins**; the sections are left otherwise intact because their reasoning is worth keeping, including the reasoning on the losing side.

| # | Conflict | Ruling | Why |
|---|---|---|---|
| **R1** | **What is the `h1`?** §2 and §4 say the boutique name, with the step as `h2`. §6 and §8 say the step itself. | **The `h1` is the step** (`booking.stepSlot` / `stepDetails` / `stepTerms` / `stepOtp` / `confirmTitle`). **Plus** a boutique-identity line *above* it, rendered as body text — `--text-sm`, `var(--color-ink-muted)` — never as a heading. | The storefront's law is `h1` = *the page's subject*, and `/dress/{id}` already takes the dress name over the boutique name on exactly that basis. The subject of `/book/terms` is the policy, not the boutique. Decisively: a step-label `h1` is a **static i18n string**, so it survives the D12 boutique-fetch failure *by construction* with no fallback path — whereas a boutique-name `h1` needs `catalog.essenceFallback` and has a state where it is wrong. The identity line answers §2's real point (`competitors.md`: "booking stays inside the boutique's brand"), which matters because **`StorefrontLayout` renders no header at all** — only `<main>` and a footer of links — so without it the boutique's name would appear nowhere in the flow. The line is omitted entirely when `useBoutique()` has nothing; it is decoration, never a load-bearing label. |
| **R2** | **Are completed stepper items links?** §3 says yes; §9.4 says no. | **No. The stepper is inert** — an `<ol>` with `aria-label`, `aria-current="step"` on the current item, no focusable descendants. | §3's own a11y justification survives without links: completed is marked by a `✓` glyph in the dot, current by `aria-current` **and** weight, upcoming by an outline dot — three non-colour signals, none of them needing an anchor. What links would add is a shortcut past the `booking.backStep` control that already walks backwards one step at a time. Against that: a stepper where two of four items are interactive and two are not is a moving target at 375px, and it is more state, more markup and more tests for a convenience. Declined on the smallest-thing-that-holds principle, not on a defect. |
| **R3** | **Does the resend cooldown show a ticking number?** §10 and §12 say the seconds re-render once per second; §6.9 says no number at all. | **No number.** `booking.otpResendWait` is a fixed sentence with **no `{{seconds}}` placeholder**, carried as the disabled button's own visible label, reverting to `booking.otpResend` after 60s. §10's and §12's rows are amended to match: there is no ticking value, so the live-region question they answer does not arise. The cooldown length itself — 60s — is unchanged and confirmed (**P3**). | §6.9 wins on a mechanical argument the other sections did not have: **i18next interpolation cannot carry markup**, so a `<bdi dir="ltr">` seconds run would have to be split at the call site, pinning Hebrew word order in TSX — which is precisely where bidi layouts break. It also removes a 1 Hz repaint and removes the only element in the flow a reviewer could reasonably read as a countdown (usage law 9). What a number buys — the reassurance that time is passing — a disabled button carrying a sentence already gives. **If the gate overrides this**, §6.9 has already fixed the shape so it is not re-guessed: `{t("booking.otpResendWait")}` followed by a plain-text `<bdi dir="ltr">` seconds node at the call site, with the polite region still firing only on enable. |
| **R4** | **What is the forward label on steps 1–3?** §3 rules `booking.submit` must be written step-neutrally; §4 uses a key called `booking.continue`; §14 proposes `booking.continueStep`. | **Two keys: `booking.continue` for steps 1–3, `booking.submit`/`booking.submitting` reserved for the verify step's commit.** The name is `booking.continue`. | One label cannot honestly serve both. "שליחה" on the slot step promises a booking three screens early; a neutral "המשך" on the verify step under-states an irreversible commitment taken on the screen where a cancellation policy has just been accepted. This is one new key against the spec's inventory (**P6**), and it removes §3's constraint on the copy author rather than adding one. |
| **R5** | **Slot-grid columns.** §3 derives 3 @375 and 5 @≥768 from one `auto-fill` rule; §8 asserts 2 and 3. | **§3's rule stands**: `grid-template-columns: repeat(auto-fill, minmax(104px, 1fr))`, one rule, no breakpoints, yielding 3 columns in the 343px content box at 375 and 5 in the 640px column at ≥768. | It is derived from the actual column arithmetic rather than asserted, and one rule with no breakpoints cannot drift from the numbers it is documented with. |
| **R6** | **How does the CTA render as a link?** §2 specifies a new `ButtonLink` in `packages/ui`; §13.2 recommends adding `href` to `Button`. | **`ButtonLink`**, per §2 — a sibling component in `Button.tsx` sharing the private `base`/`variants`/`sizes` constants, carrying **no `loading`, no `disabled`, no `type`, no `ref`**. | Adding `href` to `Button` leaves `disabled`, `type` and `loading` reachable on an anchor branch, where each of them is a lie — and a "disabled anchor" is the commonest way a design system ships an unreachable control. Exporting the class recipe for the three call sites to compose was also declined: three copies of the token strings, none of them linted. |

**Two further reconciliations that are additions rather than conflicts**, both adopted: the slot grid's `<legend>` needs a visible string, so **`booking.pickTime`** is a new key (§3, F-A6); and the item-based path's dress chip needs one, so **`booking.forDress`** is a new key (§3). See R21 for the final count.

---

## Rev 2 — review findings, resolved. Also binding.

Round 1 of adversarial review returned **NEEDS CHANGES** from three independent reviewers. Every finding is resolved below. Where a ruling contradicts a section, **this table wins**; where it contradicts R1–R6, it supersedes them and says so.

Four of these correct things that were **factually unbuildable** — specified against a shipped component that cannot do them. Those are marked **⚙ verified**, meaning the claim was checked against the source, not reasoned about.

### The three that were real defects, not inconsistencies

| # | Ruling | Why it matters |
|---|---|---|
| **R13** | **`POST /storefront/bookings` failing with 429, 5xx or a dropped connection is a designed state, and it was missing.** On any status not in the designed set: the submit button **re-enables**, a step-level `<p role="alert">` in `--color-ink-muted` carries `errors.unknown`, and `ContactPanel` renders beneath it (the 429 face can last an hour). Retry is genuinely safe — §6.12 establishes the verification token survives, because the backend rolls the whole transaction back. **Add the row to the spec's State matrix and to §12.4.** | This was **the flow's real terminal dead end**. A bride who verified her phone, accepted the policy and pressed commit got a `loading` button that stopped spinning, no message, and **no way to learn whether she is booked** — the exact failure D6 and this whole feature exist to remove. §6.15's own F-C2 enumerated three rate-limit faces and then designed only two. |
| **R14** | **The cold confirmation may not assert a booking it has no evidence for.** `booking.confirmTitle` ("התור נקבע") is the **warm branch only**. The cold branch takes a neutral heading and `booking.confirmCold` is rewritten conditionally — *if you completed the booking it exists; we cannot show it from here; call and we will confirm it for you.* | `/book/confirm` is guard-exempt by D8 and never redirects, so a hand-typed URL, a stale bookmark, a browser-forward out of an abandoned flow, or a bride whose booking was later cancelled **all rendered an unconditional "you are booked"** over a phone number. It conflated "you booked and we lost the payload" with "you never booked", and asserted the first in both. The bride could not tell she should worry. |
| **R15** | **`booking.sizeUnavailable` renders as a ≤24-character phrase on a second line inside the unavailable chip's own `<label>`** (§4.5b's ruling, adopted). Not a group-level sentence. `copy.md`'s ~100-character draft is rewritten to fit; the prototype's single `role="status"` below the fieldset is wrong and is re-rendered. | The prototype's version left the chips reading `36 / 38 / 40 / 42 / 44` with **nothing marking which size is unavailable** — a WCAG 1.3.1 and usage-law-2 failure on state-matrix row 8, and invisible to axe because the text was present, just not associated. Inside the label the phrase is part of the radio's accessible name by construction. |

### The four that were specified against code that cannot do them

| # | Ruling | ⚙ Verified against |
|---|---|---|
| **R9** | **Card padding is `var(--space-6)` at every width, including 375.** Strike the `(var(--space-4) @375)` parenthetical from §3.7, §6.5, §7.2 and §8.2. If 16px at 375 is genuinely wanted it is a `packages/ui` change and belongs in §13's queue as a gate condition — **not four table cells the build silently ignores**. | `Card.tsx:13` is `"rounded-md bg-surface p-6 shadow-sm"` with the caller's className **appended** by `cn`, and `lib/styles.ts`'s `cn` is `values.filter(Boolean).join(" ")` — a naive joiner with no tailwind-merge. Both classes ship and stylesheet order decides; `p-6` wins. |
| **R10** | **Slot grid is 2 columns @375 and 5 @≥768. This supersedes R5.** The arithmetic, stated so it cannot drift again: at 375 the content box is `375 − 2×--space-4 (page gutter) − 2×--space-6 (Card, per R9)` = **295px**; `repeat(auto-fill, minmax(104px, 1fr))` with `gap: var(--space-2)` needs `3×104 + 2×8 = 328px` for three columns, so it yields **2**. At ≥768 the column is `640 − 48` = 592px ≥ `5×104 + 4×8 = 552`, so **5** holds. | R5 (and §3.3/§3.6) did the arithmetic on the page content box and forgot the Card padding the grid sits inside. Two columns at 375 is the honest consequence, and the upside is ~140px-wide targets. |
| **R19** | **i18next interpolation cannot carry markup, so every string needing `<bdi dir="ltr">` around an interpolated value is split: the key holds the lead, the call site renders `{t("key")} <bdi dir="ltr">{value}</bdi>`.** This is already the house pattern — §3.5 uses it for `depositByPhone` + `<Price>`. Applies to all seven: `typeDuration`, `refundWindow`, `forfeit`, `confirmWhen`, `confirmWhat`, `confirmDress`, `forDress`. Each `copy.md` row is annotated with its shape, **because the shape constrains Hebrew word order and the copy author has to know before writing.** Declined `<Trans>` (available — `react-i18next@^17` is installed — but heavier, and the split is already shipped practice). | R3 deleted the cooldown's number on exactly this ground and then the doc ignored it for seven other strings. The shipped precedent is worse than silent: `he.ts:61-69` ships interpolated numerics with **no** isolation at all. |
| **R25** | **`TextArea`'s character counter must be wrapped in `<bdi dir="ltr">` — a `packages/ui` change, added to §13.2's queue.** One line, no API change, same PR as the `ref` addition. | §4.6 and §12 both require the counter isolated, but `TextArea` renders it itself with no slot, no render prop and no `ref`, so the storefront cannot do it from the call site. |

### Structural rulings

| # | Ruling |
|---|---|
| **R7** | **The forward button is NEVER `disabled`, on any step** — §4.4d's ruling extends to the slot step, overriding §3.7. Pressing it with no type or no time renders inline `role="alert"` messages and moves focus to the first unfilled group; pressing it on a selected deposit row re-announces the deposit block and does nothing else. **Delete the `aria-describedby` on the disabled button** — §4.4d proves it inert, because `disabled` drops the control from the tab order and a description *from* a disabled control is never read. The prototype ships the broken form (`disabled aria-describedby="dep-2"`) and is corrected. |
| **R8** | **The in-flow back control sits at the block-start of the column on all five steps, and the forward button sits alone on the last row.** Four placements were live across the package; this is the one three of four sections and the only executable artifact agree on. Rewrite §3.7's "Footer nav" and "Footer — back" rows and §8.2's ≥768 line. Rationale beyond consistency: a control that reverses a step must not relocate between screen 1 and screen 2 (WCAG 3.2.3). |
| **R11** | **The heading table, settled.** `h1` = `booking.step*` on all five steps (R1). `h2` = **`booking.typeHeading`** on slot (it is the type picker's `<legend>`, and the `<legend>` *is* the `h2` — it cannot be a separate element) and **`booking.termsHeading`** on terms (a plain `<h2>`; the terms step has no fieldset). On confirm, `confirmWhen`/`confirmWhat` are **labels, not headings** — remove them from §9.1's `h2` list. `copy.md:121`'s claim that `termsHeading` is "the step's `h1`" is corrected. Without this the terms step shipped `<h1>מדיניות ביטולים</h1>` immediately above `<h2>מדיניות ביטולים</h2>`. |
| **R12** | **The two no-step degrade screens (E1 no-terms, E3 no-types) take `document.book` as their `h1`.** Under R1 they would have carried `booking.stepSlot` ("מועד") above copy that says "call us" — a heading for a step that is not on the page. `document.book` ("קביעת תור") is the flow's own name, already exists as a key, and reads correctly above a phone-only block. **Zero new keys.** |
| **R16** | **`booking.otpSent` is the code field's `help` prop and nothing else** (§6.8 wins over §12 region (7) and `copy.md`'s "body copy at the top of the step"). Focus moves to the field, so `aria-describedby` speaks it exactly once; a live region would double-announce. **The verify step therefore has exactly one authored polite region**, written by exactly two discrete events: the cooldown ending, and submit starting. §12.3's regions (7) and (8) collapse into that one. |
| **R17** | **§12.4's dead-end audit is corrected — it credited exits that no screen renders.** `booking.noSlots`'s exit is **change the date**, full stop: §3.8 and the prototype render one centred sentence with no panel and no phone. `TOO_MANY_ATTEMPTS` has **no panel** in either face. Four missing rows are added: the step-level entry load failure, `TERMS_STALE` refetch failure, dress-fetch-failed-not-404, and R13. And it is recorded that **`SMS_*` intersected with D12 is the one state in the flow with neither a way forward nor a contactable exit** — previously undocumented, and the single worst cell in the table. |
| **R20** | **The submit-time `NOT_FOUND` probe gets its own §6 subsection — it was named everywhere and designed nowhere.** In flight: the submit button **stays `loading`** while the probe's one or two GETs run. Probe fails (429/5xx — realistic, since all reads share the per-tenant throttle): render `errors.unknown` in the step-level block and **leave her on `verify` with everything intact**. Dress branch: **drop the binding in memory and re-issue the booking POST once**, landing on `confirm` with `booking.dressGoneGeneric` shown there — never walk her backwards two steps for a decoration she did not choose, against a 600-second token already partly spent. (Three sections gave three different answers; the spec's own words are "drop the binding and **continue**".) |
| **R24** | **One rule for read failures: a failure on a read the flow *needs* (terms, types, slots) is a blocking step-level alert with retry; a failure on a read that only *decorates* (the dress) drops the binding and shows `booking.dressGoneGeneric`.** §4.7 wins over §2.4's "drop silently" — silence leaves her wondering where the dress went. Consequence: `dressGoneGeneric` now serves **four** triggers, not three. **File "An entry read failed (non-404) → step-level load failure · D · unit" as a third State-matrix row recommendation**, alongside FINDING 2's. |

### Consistency rulings (lower stakes, still binding)

| # | Ruling |
|---|---|
| **R18** | `booking.otpResend` is worded for the **first** send as well as the resend (`שליחת קוד אימות`, not `שליחת קוד חדש`). It labels the primary button in sub-state A where nothing has been sent yet; a screen-reader user arriving at an empty form must not hear a button offering to resend something that never happened. |
| **R21** | **The i18n additions are seven, not five**: `contactUnavailable`, `confirmDress`, `continue`, `pickTime`, `forDress`, **`sizeRequired`**, **`errors.otpSendBudget`**. The last two are rendered by the design and had **no row in `copy.md` at all** — `i18n-keys.test.ts` scans `src/` for dotted literals and asserts each resolves to non-empty Hebrew, so they would have been red on day one, not blank. `copy.md`'s arithmetic is corrected to `45 + 1 + 6 + 7 = 59`. |
| **R22** | **§14.1 is renumbered as the single authoritative proposal list, one row per decision.** P7 meant both `booking.continue` and the 640px column; P8 meant both `booking.sizeRequired` and the state-matrix row; P6 asked the user to approve `booking.continueStep`, a name R4 had already replaced. §5.10's P9–P12 appeared in no checklist. Every `**P#**` reference in §3–§13 points at the renumbered list. **A sign-off instrument whose numbers mean two things each cannot be signed off.** |
| **R23** | The gold hairline ornament is the shipped `SectionHeading` geometry — `block-size: 1px; inline-size: var(--space-12)` (48px) — **on every step including details**, which §4.6 had exempted. §2.7's full-width version is struck. Note for the builder: `SectionHeading` hardcodes `text-xl`, so the `--text-2xl` `h1` cannot use that component and must be a bare `<h1>` + `<span>`. |
| **R26** | The e2e pin "browser back walks the steps in reverse" is scoped to **a flow with no mid-flow recovery**. `navigate()` is `pushState`-only, so a `SLOT_UNAVAILABLE` recovery pushes `slot` on top of `verify` and re-advancing pushes the rest again; the stack grows and back no longer walks cleanly out. Accepted consequence of having no `replace`; adding one is deliberately out of scope. |
| **R27** | At ≥768 the forward button is at the **inline-end** of its row on all five steps, including verify. §6.4's inline-start reasoning is overruled for consistency. |
| **R28** | **One selected-chip treatment: the slot chip's** — `--color-gold` fill + weight 600. **Stop citing the border hue as a signal**: `--color-border-input` `#8A7A5E` against `--color-gold-strong` `#9E7B36` is **1.06:1** and carries nothing. The `aria-hidden ✓` glyph specified in §13.1 and §12.1 appears in no wireframe and no prototype — either draw it in §3.6 and §4.6 or drop it; **dropped**, since fill + weight + the native `:checked` announcement are three real channels. |
| **R29** | **Required-field indication (WCAG 3.3.2)** for the two controls that lacked it: `required` goes on each size radio (which makes the group required to AT — one line, no new key), and the consent checkbox relies on its own imperative sentence. §12.3's Labels bullet, which claimed the labelling story was complete, is corrected. |
| **R30** | **The loading state gets one `VisuallyHidden role="status"`** carrying a loading string while the entry fetches are in flight, emptied when they resolve. `aria-busy` on a plain `<div>` — what §3.8 and the prototype ship — is **not announced by VoiceOver or NVDA**, so a bride on a slow connection heard the `h1`, then silence, then content that swapped in unannounced. Reuse an existing `catalog.*` loading key if one exists; otherwise it is an eighth addition. |
| **R31** | **The WCAG 2.5.3 requirement for a slot chip's accessible name to read `"10:30 — <date>"` is dropped.** The `<fieldset>`'s visible `<legend>` and the adjacent date control already scope the group, so the bare time is sufficient and is what §3.6, the prototype and the `RadioGroup` row all build. §12's bullet is corrected rather than the three build specs. |

**Two review findings are accepted as correct and need no change**: the details step can fire three simultaneous `role="alert"` errors (the primitives hardcode the role, so the storefront cannot opt out — F8's arithmetic is corrected from two to three and §12.3's "one region per step" is qualified to "one *authored* region"), and the prototype omits several dead-end states, of which the two `TOO_MANY_ATTEMPTS` faces are the highest-value additions when it is next re-rendered.

### ⚠ `prototype.html` status after rev 2 — five known divergences

The prototype was rendered against rev 1 and **has not been re-rendered**. It remains the best reference for the heading structure (it implements R1 correctly, which the §2/§3 wireframes do not) and for the RTL/token/bidi mechanics, which a mechanical audit confirms: **zero physical direction or sizing properties, zero raw hex outside `:root`, 13 `<fieldset>`s matched by 13 `<legend>`s, 70 labels for 65 inputs, `dir="ltr"` as a real attribute on both LTR inputs.** But it is now wrong in five specific places, and a builder must not copy them:

| Divergence | Correct per rev 2 |
|---|---|
| Renders a ticking cooldown (`בעוד <bdi>42</bdi> שניות`) | **R3** — fixed sentence, no number |
| Slot grid draws 3 columns at 375 | **R10** — 2 columns; and the Card padding it assumes (`--space-4`) is itself wrong per **R9** |
| `booking.sizeUnavailable` as one `role="status"` below the fieldset, with no per-chip signal | **R15** — a ≤24-char phrase inside the unavailable chip's own `<label>` |
| Forward button `disabled aria-describedby="dep-2"` on the deposit branch | **R7** — never disabled, and the `aria-describedby` is inert on a disabled control |
| Card padding `--space-4` at 375 via a `@container` override | **R9** — `--space-6` at every width; `Card` hardcodes `p-6` and `cn` cannot be overridden |

**Re-render it after the user's copy sign-off, not before** — the strings are about to change, and rendering twice against DRAFT Hebrew spends the effort twice.

**What review confirmed as right and must not be re-litigated**: §5.3a's terms step (no inner scroll container, no scroll-to-accept gate — no keyboard trap on the one screen that could have had one); §6.7's single OTP field; **§6.12's "what survives" table**, which reviewers singled out as the best work in the package for inferring from the backend's transaction rollback that `SLOT_UNAVAILABLE` recovery must not route back through OTP; §7.5's refusal of `--color-success`; the bidi model; and `Checkbox` over `Toggle`.

---

## Reading this document

| § | Contents |
|---|---|
| §0–§1 | Scope, the route map, wireframe conventions, the flow map, the three exits |
| §2–§3 | **S0** the entry (CTA, first paint, the two entry-level degrades) · **S1** the slot step |
| §4–§5 | **S2** details (name, notes, size chips) · **S3** terms acceptance |
| §6–§7 | **S4** phone verification and submit · **S5** confirmation, including the cold load |
| §8–§10 | Responsive rules · heading/focus/keyboard model · motion |
| §11 | **The state-matrix coverage map** — every row of the spec's table, and where it is designed |
| §12 | Accessibility, including §12.4's dead-end audit |
| §13 | Rows queued for `components.md` and `qa-checklist.md` |
| §14 | Gate proposals for the user, and the revision log |

Findings raised by the authors are marked **⚠ FINDING** and are kept in place. They are not defects in the design; they are places where the spec, the shipped code or another document needs an amendment, and each says which.

---
## 0. Scope

Six surfaces, one route family, one storefront shell.

| # | Surface | Route | Component (F14) | Owned by |
|---|---|---|---|---|
| **S0** | Booking entry — the «קביעת תור» CTA, plus the first paint of the flow and its two entry-level degrades | `/` · `/dress/{id}` · `/about`, then `/book/slot[/{dressId}]` | `components/BookingCTAButton.tsx` (modify) → `routes/BookPage.tsx` (new) | §2 |
| **S1** | Slot step — appointment type (**D11**), date, time | `/book/slot[/{dressId}]` | `BookPage.tsx`, step `slot` | §3 |
| **S2** | Details step — name, optional `notes`, size chips (**P2**) | `/book/details[/{dressId}]` | `BookPage.tsx`, step `details` | §4 |
| **S3** | Terms step — policy text, the two numbers, the consent checkbox | `/book/terms[/{dressId}]` | `BookPage.tsx`, step `terms` | §5 |
| **S4** | Verify step — phone, OTP, resend cooldown, submit | `/book/verify[/{dressId}]` | `BookPage.tsx`, step `verify` | §6 |
| **S5** | Confirm — terminal, outside the stepper | `/book/confirm[/{dressId}]` | `BookPage.tsx`, step `confirm` | §7 |

**Route map.** `/book/{step}` and `/book/{step}/{dressId}`, `step ∈ {slot, details, terms, verify, confirm}` — a closed set, so a step slug can never be read as a dress id (**D8**). The dress rides in a path segment, never a query string (**D9**). Bare `/book` **renders** the slot step; it never redirects to it, because `navigate()` is `pushState`-only with no `replace` — a mount-time redirect would push a second entry and browser-back would loop `/book → /book/slot → /book`. Nothing in the app ever *links* to bare `/book`; it exists only as a tolerated hand-typed alias.

**Navigation model (one model at every breakpoint): one column, replacement per step.** There is no wizard side-rail and no persistent running-summary panel at 1440. *Declined*: a two-pane 1440 layout with a live summary — the content column is capped at 640px (below), a summary panel would duplicate S5's job, and it doubles the state surface every step has to keep correct.

- **In-app back is a `<Link>` to the previous step's known URL.** The app never calls `history.back()` / `navigate(-1)` / `router.back()`; `qa-greps.sh:34` greps for all three, and `router.tsx` exposes no `back()` to call in the first place. The browser's own back button works, via the shipped `popstate` subscription, and walks the steps in reverse.
- **The Router already owns focus and scroll on every step transition.** `router.tsx:196-211` scroll-resets to top and focuses `<main id="content" tabIndex={-1}>` on every `pathname` change, suppressed on first paint only. **F14 adds no per-step focus move** — a second `focus()` racing the Router's is a defect, not a courtesy. The only additional focus moves F14 is allowed are the two the console model reserves them for: first-invalid-field on a failed validation, and an error block that appears with no navigation. Both belong to §4–§6.
- **One `document.title` for the whole flow** — a single `book: "document.book"` entry in `DOC_TITLE_KEYS`. Every `/book/{step}` matches `RouteName === "book"`, and the Router's title effect re-runs on every step, so a per-step title written from inside `BookPage` would be clobbered on the next step.
- **No `BookingCTA` bar inside `/book`, at any width.** `hasBookingBar(route)` is `catalog || dress` (`StorefrontLayout.tsx:63-65`) and F14 deliberately does **not** add `book` to it — the inverse mistake would put a "book a fitting" CTA inside the booking flow (spec Risk 6). Consequences, both owned here: the shell reserves no bottom padding for `/book`, and `A11yMenu` keeps its resting `[inset-block-end:var(--space-4)]` instead of lifting to `var(--space-a11y-clearance)`.

**Page frame — RULED, `PROPOSED — user confirms at the gate`.**

| Property | Value | Reason |
|---|---|---|
| Content column | `max-inline-size: 640px`, centred (`max-w-[640px]` in class position) | `/book` is a form-and-reading surface, not a lookbook. `/about` is the shipped storefront precedent at 640px (`storefront-profile-hours.md:48`, "editorial page — never goes multi-column"); the 1200px catalog width exists to hold a 4-column grid this screen does not have, and the console's 720px form column is the *console* dialect |
| Page gutters | `padding-inline: var(--space-4)` @375 → `var(--space-6)` @≥768; **no third step** | `/about` exactly. The catalog's third step (`xl:px-12`) fires at Tailwind's `xl` = **1280px**, not 1440 — a column capped at 640px never reaches its own gutters, so the step is dead weight |
| Page bottom reserve | `padding-block-end: var(--space-16)` (64px) **at every width** | The fixed `A11yMenu` trigger is `size-11` (44px) at `inset-block-end: var(--space-4)` (16px) and is **not** reset at ≥768 — it occupies the bottom 60px of the viewport at the inline-end edge. 64px clears it. `/accessibility` (`pb-16`) is the shipped page with the same geometry and is the precedent followed |
| Vertical rhythm | `--space-8` between page-level blocks (h1 / stepper / Card / footer nav); `--space-6` between groups inside a Card | tokens.md: "section rhythm ≥ `--space-6`" |

> **⚠ FINDING F-A1 — `/about` under-reserves for the fixed `A11yMenu` button.** PRE-2 says a page with no CTA bar "uses `--space-4` and the page reserves matching bottom padding". `/about` ships `pb-8` (32px) against a 60px fixed-button footprint, so the button overlaps the last 28px of the page. `/accessibility` ships `pb-16` (64px) and is correct. F14 follows `/accessibility` and does **not** fix `/about` — but the two precedents disagree, and whichever number the gate blesses should be written into `qa-checklist.md` alongside the `/book` row queued in §12.

---

## 1. Reading the wireframes, and the flow map

### 1.1 Reading the wireframes

> **Reading the wireframes.** ASCII below is drawn in **logical order** — inline-**start** on the left of the drawing, inline-**end** on the right. On screen everything is mirrored: the storefront is `lang="he" dir="rtl"`, so inline-start is the **right** edge. Every CSS rule in this document is written in logical properties (`padding-inline-*`, `margin-inline-*`, `border-inline-*`, `inset-inline-*`, `text-align: start/end`, `min-block-size`, `max-inline-size`). Media-query *features* (`@media (max-width:767px)`) are exempt — they are viewport queries, not properties.
>
> **One correction against `manage-catalog.md`'s stricter console note, and it is deliberate.** That document bans physical *sizing* properties too (`max-width`, `min-height`). The storefront does not, and cannot: `qa-greps.sh:40` bans only inline-direction utilities (`ml- mr- pl- pr- left- right- text-left text-right border-l- border-r-`), and every shipped storefront file uses `max-w-[1200px]`, `max-w-[640px]`, `min-h-screen`, `min-w-0`, `max-w-prose`, `min-h-11`. **So: CSS spec tables in this document name logical properties; any Tailwind class quoted in this document is the class the build actually ships.** Mandating `max-inline-size` in class position would produce a document the build cannot follow.

Annotation vocabulary, as used in `manage-catalog.md` and extended here:

| Mark | Meaning |
|---|---|
| `<- comment` | annotation pointing back at the element on that line |
| `(h2, display, --text-xl)` | trailing parenthetical: tag · font · token · a11y attribute |
| `[ ... ]` / `[ label ]` | input field / button |
| `( )` / `(•)` | radio unchecked / checked |
| `[ ]` / `[x]` | checkbox unchecked / checked |
| `(1)———(2)` | stepper dots and their `aria-hidden` connector |
| `(כלות בלבד)` | a `Badge`, drawn as a parenthesised chip |
| `~ hairline ~` | the gold hairline ornament (`aria-hidden`) |
| `▓▓▓ … ▓▓▓` | the gold CTA bar fill |
| `→` | the RTL back-glyph (`aria-hidden`; in RTL the way back points inline-start-to-end, i.e. rightwards) |
| `⌂` | a skeleton block |

Visible strings are written as their **i18n key** (`booking.noSlots`) or as a short English gloss in brackets. The Hebrew itself is `copy.md`'s (§11) — no wireframe in this section invents prose.

### 1.2 The flow map

```
        ENTRY (S0)                             THE FLOW                          TERMINAL
  ┌──────────────────────┐
  │ /            catalog │──┐
  │ /about               │──┼─ <a href="/book/slot">  ────────┐
  └──────────────────────┘  │                                 │
  ┌──────────────────────┐  │                                 v
  │ /dress/{id}          │──┴─ <a href="/book/slot/{id}"> ──> /book/slot   (S1, §3)
  └──────────────────────┘                                     │  type · date · time
                                                               v
                                                          /book/details    (S2, §4)
                                                               │  name · notes · size
                                                               v
                                                          /book/terms      (S3, §5)
                                                               │  policy · consent
                                                               v
                                                          /book/verify     (S4, §6)
                                                               │  phone · OTP · SUBMIT
                                                               v
                                                          /book/confirm    (S5, §7)

  back:  in-app  = <Link> to the previous step's known URL (never history.back())
         browser = popstate walks the same URLs in reverse
  S1's back link targets `/` (booking.backToCatalog), NOT the bound dress — see §3.7
```

### 1.3 The three exits

Every one of them is a **phone-only block** (§2.5): a sentence, then `ContactPanel`, then — when `useBoutique()` has nothing — a plain-copy degrade instead of the panel (**D12**, **P5**).

| # | Exit | Trigger | Where it lands | Owner |
|---|---|---|---|---|
| E1 | **No published terms** — the flow never opens | `GET /storefront/terms` → `404 NOT_FOUND` (**D5**) | replaces the whole of S1; no stepper, no Card | §2.6, wireframe S0-c |
| E2 | **Deposit-required type** — this service is booked by phone | the selected appointment type has `deposit_required` (**D3**) | inline, **under the selected row only**; siblings stay bookable | §3.2, §3.5 |
| E3 | **No active appointment types** — the boutique cannot take a booking online at all | `GET /storefront/appointment-types` → `[]` | replaces S1's Card | §3.8, wireframe S1-e |

The confirm screen's cold-load `ContactPanel` (**D8**) is a fourth instance of the same block; §7 owns it.

> **⚠ FINDING F-A2 — D12 enumerates three `ContactPanel` branches; there are four.** D12's "all three" names D3's deposit note, D5's no-terms entry and the cold-`confirm` screen. `booking.noTypes` (E3 above) is structurally identical — a boutique that cannot take a booking online, on a screen with no other affordance — and dead-ending it without a phone number is exactly the failure this feature exists to remove. This section rules that it gets the same block **and the same D12 degrade**, making four. D12's count wants amending in the spec.

---

## 2. Screen S0 — the entry

### 2.1 What changes, and what does not

Nothing about the CTA's **appearance** changes. `BookingCTA` keeps its bar geometry below 768 and goes inline from 768; `/about` keeps `inline` (its qa §7 no-bottom-bar-at-any-width requirement is orthogonal to **D1** and survives it). What changes is three things:

1. the CTA is an **anchor**, not a button, and it **navigates** instead of opening a `Modal` (**D1**);
2. it renders on `/` even when the boutique fetch failed, and loses its `boutique` prop (**D12**);
3. `booking.panelTitle` and `booking.close` become dead keys and are deleted in the same pass — `i18n-keys.test.ts` checks used→defined only, never defined→used, so nothing will fail if they are left behind.

### 2.2 The CTA element — RULED

**RULING (P1) — `PROPOSED — user confirms at the gate`.** The CTA is a plain `<a href="/book/slot…">` styled as the primary button, rendered by a new **`ButtonLink`** primitive in `packages/ui`.

*Why an anchor at all.* `router.tsx:180-194` delegates clicks from the document root: any `<a>` whose href is same-origin, http(s), no `target`, no `download`, no `rel="external"` and not a bare hash is `preventDefault()`ed into a client navigation. `shouldIntercept` (`:105-146`) explicitly bails on meta/ctrl/shift/alt and non-primary buttons, so **open-in-new-tab, middle-click and "copy link address" all keep working** — every one of which `onClick` + `navigate()` silently destroys. `DressCard` already ships on exactly this mechanism.

*Why a new primitive rather than a className.* `Button.tsx:53` hardcodes `<button type="button">`; `ButtonProps` has no `as` / `asChild` / `href`, and its `base` / `variants` / `sizes` class constants are module-private — `packages/ui/src/index.ts` exports only `Button`, `cn` and `focusRing`. So P1 is **not free**: it is a `packages/ui` change either way. `ButtonLink` shares those three constants with `Button` in the same file, and deliberately carries **no `loading` and no `disabled`** — a link can be neither, and a "disabled anchor" is the single most common way a design system ships an unreachable control.

*Alternatives declined.* (a) Adding `href?: string` to `Button` — its props extend `ButtonHTMLAttributes`, so `disabled`, `type` and `loading` would all be reachable on the anchor branch and each would be a lie. (b) Exporting the class builder and hand-rolling `<a className={buttonClass(...)}>` at three call sites — three copies of the token strings, none of them linted. (c) Wrapping the storefront's own `Link` component — it works, but it makes `packages/ui` router-aware for no gain, since the delegated listener already catches a bare `<a>`.

```
ButtonLink — packages/ui/src/components/Button.tsx (same file, shared constants)
  props: { href: string; variant?: ButtonVariant; size?: ButtonSize;
           fullWidthMobile?: boolean; className?: string; children: ReactNode }
  renders: <a href={href} className={cn(base, variants[variant], sizes[size], …, focusRing)}>
  no type · no disabled · no loading · no ref
```

*Split-rule check* (spec §Design): a link styled as a button is something a second app would plausibly need, so it belongs in `packages/ui` and inherits its design-gate obligation. Recorded for §12.

> **⚠ FINDING F-A3 — P1 breaks four test queries, and two of them fail *silently*.** Spec Risk 3 names three sites; there are four, and the role changes from `button` to `link`. `AboutPage.test.tsx:282-283` and `:295` and `CatalogPage.test.tsx:152` all hard-fail (loud, safe). But `CatalogPage.test.tsx:183` is `expect(queryByRole("button", …)).toBeNull()` — under P1 that **passes vacuously**, silently un-verifying the exact assertion **D12** inverts. And `DressPage.test.tsx:254`'s `toBeEnabled()` is vacuous on an `<a>` (jest-dom's disabled matchers apply only to `button/input/select/textarea/optgroup/option/fieldset`); it must be replaced by an assertion on the `href` carrying the dress id, which is what the spec's own Risk 3 text asks for anyway.

### 2.3 The hrefs

| Origin | href | Note |
|---|---|---|
| `/` (catalog, bar @375 / inline in header @≥768) | `/book/slot` | generic path |
| `/about` (`inline`, no bar at any width) | `/book/slot` | generic path |
| `/dress/{id}` (bar @375 / inline in the facts column @≥768) | `/book/slot/${encodeURIComponent(dressId)}` | item-based path. Encode exactly as `api.getDress` does; `router.tsx:45-53`'s `decodeId` is the matching decoder and already guards a malformed `%` |

Absolute paths only. The delegated handler pushes `anchor.getAttribute("href")` — the **raw attribute**, not the resolved `.href` — so a relative href would be pushed verbatim and break.

Nothing links to bare `/book` (§0).

### 2.4 First paint of `/book/slot` — what the flow fetches, and when

**RULING — terms are fetched on flow entry, not at the terms step.** `GET /storefront/terms` fires in parallel with `/appointment-types` and `/slots` on the first paint of the flow, because a `404` there is an **entry-level** decision (**D5** — "the entry itself, when a boutique has no published terms"). Fetching it at S3 would let a bride fill two steps before hitting a dead end, which is the failure mode this feature exists to remove.

| Call | Fires | On failure |
|---|---|---|
| `GET /storefront/terms` | flow entry | `404` ⇒ **E1** phone-only block (§2.6). Any other status ⇒ the step-level load-failure state (§3.8) — the `404` is branched on **before** the shared `errorMessageKey` helper ever sees it, because `NOT_FOUND` means something else on every other call in this flow |
| `GET /storefront/appointment-types` | flow entry | `[]` ⇒ **E3** (§3.8). Any error ⇒ step-level load failure |
| `GET /storefront/slots` (no params — server defaults to today..+14d Jerusalem) | flow entry | error ⇒ step-level load failure |
| `GET /storefront/dresses/{id}` | flow entry, **only when a `dressId` is bound** | `404` ⇒ drop the binding, continue generic, `booking.dressGoneGeneric` (§2.6, wireframe S0-b). Any other error ⇒ drop the binding silently; a failed decoration must never block a booking |

All four spend the storefront's per-tenant read throttle (`_throttle`), plus the layout's app-wide `/storefront/boutique`. Five reads for one entry is the honest cost of `/book` being a real route; a `429` on any of them renders one step-level load failure, not five.

**`isNotFound` is never called from this flow.** It folds `400 VALIDATION_ERROR` into "dress not found" (`api.ts:33-36`), scoped by its own comment to the dress-detail route. A booking-path `400` running through it would show "השמלה כבר לא זמינה" for a mistyped phone number — which is the assertion the spec's §Testing names.

### 2.5 The phone-only block — one named pattern, four instances

Defined once here; §3 and §7 reference it rather than redrawing it.

| Part | Spec |
|---|---|
| Sentence | `--font-body`, `--text-base` (line-height 1.6 from the token — never add a `leading-` utility, it overrides the token), `color: var(--color-ink)` (**15.24:1** on cream ✓ / **13.89:1** on paper ✓). Ink, **not** ink-muted: this is an instruction she must act on, not an outage report. `max-inline-size: 60ch` |
| Panel | `ContactPanel` with `phone` / `whatsapp` (`waPhone`) / `wazeUrl` / `mapsUrl` / `instagram` from `useBoutique()`, `labels={contactLabels(t)}`, inside a `Card` (`background: var(--color-surface)`, `border-radius: var(--radius-md)`, `box-shadow: var(--shadow-sm)`, `padding: var(--space-6)` / `var(--space-4)` @375, **no hard border**) |
| Row order | phone first, then WhatsApp, then Waze / Maps, then Instagram — `ContactPanel`'s shipped order, unchanged. See §12: `test-results.md:117` asks the pilot interview to record "whether she reaches for WhatsApp or the phone number first — that ordering should drive the panel's row order", and that interview has not been run |
| **D12 degrade** | When `useBoutique()` has no boutique (loading resolved to `error`, or `boutique === null`), the `Card` + `ContactPanel` are **not rendered at all** and a second `<p>` carries `booking.contactUnavailable` (**P5**) in `--text-base`, `var(--color-ink-muted)` (**6.15:1** on cream ✓). *Precedent:* `AboutPage.tsx:106-130` already withholds the contact card entirely on a failed boutique fetch rather than printing empty rows, and `ContactPanel` with every channel empty renders a literally empty `<div>` — the degrade cannot be a prop on the panel, it has to be a branch at the call site |
| `booking.contactUnavailable` must be **name-free** | The boutique fetch failed by definition, so there is no name to interpolate. `he.ts:184`'s `statement.coordinatorNoChannel` is the shape precedent but it interpolates `{{name}}`; this key must not |

Where the block replaces a whole screen (E1, E3), it is preceded by the `h1` (§2.7) and followed by the `booking.backToCatalog` link — **no stepper**, because there is no flow to be a step of.

### 2.6 Wireframes

**S0-a — first paint of `/book/slot`, everything in flight (375).**

```
+---------------------------------------------+
|  ⌂⌂⌂⌂⌂⌂⌂⌂            <- Skeleton text, 1 line, 60%   (the h1 slot; see §2.7)
|                                             |
|  (1)———(2)———(3)———(4)   <- stepper renders LIVE, not skeletoned
|  שעה   פרטים  מדיניות  אימות                |
|                                             |
|  +-- Card ---------------------------------+|
|  |  ⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂        <- text, 1 line   ||
|  |  ⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂  <- 3 rows, 56px  ||
|  |  ⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂                    ||
|  |  ⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂⌂                    ||
|  |  ⌂⌂⌂⌂⌂  ⌂⌂⌂⌂⌂  ⌂⌂⌂⌂⌂  <- grid, 2 rows   ||
|  |  ⌂⌂⌂⌂⌂  ⌂⌂⌂⌂⌂  ⌂⌂⌂⌂⌂                    ||
|  +-----------------------------------------+|
|                                             |
|  (no footer nav — nothing to advance to yet)|
+---------------------------------------------+
|  footer (layout-owned)                      |
+---------------------------------------------+
    NO CTA bar at any width.  ◑ A11yMenu fixed, end-4, inset-block-end --space-4
```

The **stepper renders live** rather than as a skeleton: it is static chrome whose content is known before any fetch resolves, and skeletoning it would claim uncertainty that does not exist. The **h1 is skeletoned only while `useBoutique()` is loading** — `CatalogPage.tsx:139-141`'s rule verbatim: "a real header with a placeholder name would claim an identity the boutique has not sent yet".

**S0-b — dress archived before the flow (375).** `GET /dresses/{id}` → `404`. The binding is dropped; the flow continues generic.

```
|  בֶּלָה                       (h1, display, --text-2xl)
|                                             |
|  booking.dressGoneGeneric  <- role="status", --text-sm, ink-muted,
|                               no icon, no colour, no border, no dismiss
|  (1)———(2)———(3)———(4)                      |
|  +-- Card: the ordinary S1 body, no binding chip ------+
```

**The URL keeps the dead id; only the in-memory binding is dropped.** Rewriting `/book/slot/{deadId}` → `/book/slot` would require a `pushState` (there is no `replace`), which breaks back. Instead the step machine constructs every **forward** URL without the dress, so the dead id disappears on the first forward move and can never re-enter. Browser-back to `/book/slot/{deadId}` re-fetches, `404`s again and shows the same notice — idempotent. The notice renders on the slot step only; once she moves forward the URL carries no dress and there is nothing left to explain. *Declined*: carrying the notice through all four steps — a `role="status"` that re-announces on every step is noise, and the same string is reused by the submit-time `NOT_FOUND` probe (§6) where it is genuinely new information.

**S0-c — E1, no published terms → phone-only entry (375).**

```
+---------------------------------------------+
|  בֶּלָה                       (h1, display, --text-2xl)
|  ~~~~~~~~ gold hairline ~~~~~~~~  (aria-hidden, h-px bg-gold)
|                                             |
|  booking.noTermsByPhone       (--text-base, ink, max 60ch)
|                                             |
|  +-- Card ---------------------------------+|
|  |  [ ContactPanel ]                       ||
|  |   ☎ call · WhatsApp · Waze · Maps · IG  ||
|  +-----------------------------------------+|
|                                             |
|  → booking.backToCatalog     (gold-text, underlined link)
+---------------------------------------------+
```

No stepper. No Card of form controls. No footer forward button — there is nothing to advance to.

**S0-d — the same screen under D12 (boutique fetch failed).**

```
|  catalog.essenceFallback      (h1 — the shipped fallback, used by all
|  ~~~~~~~~ gold hairline ~~~~~~~~   three storefront routes)
|                                             |
|  booking.noTermsByPhone       (--text-base, ink)
|  booking.contactUnavailable   (--text-base, ink-muted)   <- P5
|                                             |
|  (no Card, no ContactPanel — an empty panel is a literally
|   empty <div>; AboutPage.tsx:106-130 is the precedent)
|                                             |
|  → booking.backToCatalog                    |
```

### 2.7 Component notes — exact tokens

| Element | Spec |
|---|---|
| The CTA (unchanged geometry) | `ButtonLink variant="primary"` inside the shipped `BookingCTA` wrapper (fixed bar below 768, static from 768) on `/` and `/dress`; bare `ButtonLink` with `w-full` on `/about`. **F14 changes the element, not the box** — bar height, padding and the `--cta-bar-height` reservation are all as shipped and are not re-specified here. Colour is `background: var(--color-gold)` + `color: var(--color-ink)` (**6.41:1** ✓ — the only legal way gold touches this control, usage law 1), `border-radius: var(--radius-md)`, weight 700 |
| CTA focus ring | `focusRing` — `var(--color-focus)`, 2px, 2px offset (**5.57:1** on cream ✓). Unchanged; the anchor is focusable natively and needs no `tabindex` |
| **`h1` — every `/book` screen, every degraded branch** | `<h1 className="font-display text-2xl text-ink">` carrying `boutique?.name ?? t("catalog.essenceFallback")`. **RULED, `PROPOSED — user confirms at the gate`** (§2.8 note) |
| Gold hairline ornament | `<div aria-hidden="true" className="h-px bg-gold" />` directly under the `h1`, full column width. The storefront's one decorative motif; nothing else decorates `/book` |
| `booking.dressGoneGeneric` notice | `<p role="status">`, `--text-sm`, `var(--color-ink-muted)` (**6.15:1** on cream ✓), `margin-block: var(--space-2) var(--space-4)`. No icon, no border, no fill — an informational line with nothing to act on. `role="status"` (polite), never `alert`: it appears without a navigation but demands nothing |
| Phone-only sentence / panel / D12 degrade | §2.5 |
| `booking.backToCatalog` link | `<Link to="/">` styled as the storefront's standard link — `cn("text-base text-gold-text underline", focusRing)` (**5.57:1** on cream ✓) — prefixed by an `aria-hidden` `→` glyph, matching `DressPage.tsx:168` ("in RTL the way back points inline-start-to-end, i.e. rightwards"). `min-block-size: 44px` with the padding to match |
| Skeletons | `Skeleton variant="text"` for the `h1` and labels, plain blocks for rows and chips. `--color-surface` fill, 1.5s pulse, **static under `prefers-reduced-motion`** (`--animate-skeleton` is the one sanctioned literal-duration animation) |

> **⛔ STRUCK BY R1 AND R11. Do not build from this block or from §2/§3's wireframes' heading rows.**
>
> This subsection argued for the boutique name as `h1`; three of the four sections, the prototype, and the `/dress/{id}` precedent all say otherwise, and **R1 ruled the `h1` is the step label**. The reasoning below is retained for one reason only: its brand point (`competitors.md` — "booking stays inside the boutique's brand") is *why* R1 keeps a boutique-identity line at all. That line is `--text-sm` `var(--color-ink-muted)` **body text above the `h1`**, never a heading, and it is omitted entirely when `useBoutique()` has nothing.
>
> **Consequently, every wireframe in §2 and §3 that draws `בֶּלָה` or `catalog.essenceFallback` as the `h1` is superseded**: that element is the identity line, and the step label is the `h1` beneath it. Finding F-A4 below is likewise struck — R1 resolves it with zero new keys. **`prototype.html` renders the correct heading structure** and is the reference for it until these wireframes are redrawn — but see the rev-2 note on the prototype's five other divergences before copying anything else from it. On the two no-step degrade screens (E1, E3) the `h1` is `document.book`, per R12.

**Heading law on `/book`, RULED.** The `h1` is the **boutique name**, on every step and every degraded branch; the step's own heading is an `h2` carrying the step label. Three reasons: (1) the storefront law is "exactly one `h1`, on every state including degraded ones" and `catalog.essenceFallback` is the shipped, already-proven fallback for a failed boutique fetch — which is precisely the **D12** branch; (2) `competitors.md:29` records "booking stays inside the boutique's brand" as a binding anti-pattern to avoid, and a booking route whose page subject is not the boutique is the platform-branded booking page that complaint names; (3) it needs no new i18n key, and there is none — see F-A4. *Declined*: the step label as `h1` — it would duplicate the stepper's current item verbatim, and it changes the page's subject four times inside one `document.title`.

**The `h1` is a bare `<h1>`, not `BoutiqueHeader`.** That composite carries the hours-today snippet **and the inline `BookingCTA` at ≥768** — mounting it inside `/book` would put a "book a fitting" CTA inside the booking flow, which is exactly the Risk 6 inverse mistake §0 rules out. Size is `--text-2xl`, not the catalog's `--text-3xl`: this is a working surface, and `--text-2xl` is the shipped identity size on `/dress`'s degraded states.

> **⚠ FINDING F-A4 — the i18n inventory has no heading string for the booking flow.** It carries `document.book` (the `<title>`) and the four `booking.step*` labels, but nothing that could be an `h1`. The ruling above resolves it with zero new keys by reusing the boutique name and `catalog.essenceFallback`. If the gate prefers a dedicated heading, that is one new key and the ruling changes.

### 2.8 States

| State | What she sees | Trigger | Test |
|---|---|---|---|
| **CTA, default** | unchanged gold bar @375 / inline button @≥768 on `/`, `/dress`, `/about` | — | unit ×3 |
| **CTA on a failed boutique fetch (`/`)** | the CTA **renders** (D12 inverts F10's guard). The page keeps its one muted `role="alert"` + `catalog.retry`; the CTA is not a second alert | `useBoutique()` error | unit — and see **F-A3**: the assertion must query `role="link"`, or it passes vacuously |
| **CTA on a reserved dress** | unchanged and navigable, carrying the dress id | `reserved: true` | unit — assert the `href`, not `toBeEnabled()` (**F-A3**) |
| **Loading** | wireframe S0-a — live stepper, skeletoned `h1` (only while the boutique is in flight), skeletoned Card body | any of the four entry fetches in flight | unit |
| **Dress archived before the flow** | wireframe S0-b — `booking.dressGoneGeneric` `role="status"`, binding dropped, flow continues generic, URL untouched | `GET /dresses/{id}` → `404` | unit |
| **E1 — no published terms** | wireframe S0-c — the phone-only block replaces the entire flow | `GET /terms` → `404` (**D5**) | unit |
| **E1 under D12** | wireframe S0-d — plain copy, no panel, no Card | `GET /terms` → `404` **and** no boutique | unit |
| **Entry fetch failed (not the terms 404)** | the step-level load-failure state — §3.8 | terms non-404 · types error · slots error · `429` on any | unit |

Item-based and generic happy paths, and every remaining row of the state matrix, are S1's (§3.8) and S2–S5's.

---

## 3. Screen S1 — the slot step

The densest screen in the flow. Structure, top to bottom: `h1` · ornament · [`dressGoneGeneric` notice] · stepper · **Card**{ [binding chip] · type picker · date · slot grid } · footer nav.

### 3.1 Mobile 375 — default, generic path

```
+---------------------------------------------+
|  בֶּלָה                     (h1, display, --text-2xl, ink)
|  ~~~~~~~~ gold hairline ~~~~~~~~  (aria-hidden)
|                                             |
|  (1)———(2)———(3)———(4)      <ol aria-label={booking.stepsLabel}>
|  שעה   פרטים  מדיניות  אימות   (--text-xs, li labels)
|   ^ aria-current="step"                     |
|                                             |
|  +-- Card (paper, radius-md, shadow-sm, --space-4 @375) -----+
|  |                                                          |
|  |  booking.typeHeading         (<legend>, h2-weight, --text-xl display)
|  |  +------------------------------------------------------+|
|  |  | ( )  מדידה ראשונה                     <- name, 600   ||
|  |  |      booking.typeDuration [45]        <- bdi ltr, sm ||
|  |  +------------------------------------------------------+|
|  |  | ( )  מדידה עם מלווים   (booking.audienceBrides)      ||
|  |  |      booking.typeDuration [90]        <- Badge muted ||
|  |  +------------------------------------------------------+|
|  |  | ( )  חבילת כלה                                       ||
|  |  |      booking.typeDuration [120]                      ||
|  |  +------------------------------------------------------+|
|  |                        (44px min per row, hairline between)
|  |                                                          |
|  |  booking.pickDate            (visible <label>)           |
|  |  [ 04/08/2026        ]   <- native <input type="date">,  |
|  |                             dir="ltr", min=today(IL),    |
|  |                             max=today+14d                |
|  |                                                          |
|  |  booking.pickTime            (<legend>)   <- PROPOSED key|
|  |  [10:00] [10:45] [11:30]     <- each <bdi dir="ltr">,    |
|  |  [12:15] [13:00] [13:45]        radio, 44px, radius-full |
|  |  [14:30] [15:15]                                         |
|  |                                                          |
|  +----------------------------------------------------------+
|                                                             |
|  → booking.backToCatalog          [ booking.submit ]        |
|                                                             |
+-------------------------------------------------------------+
|  footer (layout-owned): על הבוטיק · הצהרת נגישות · @ig · tel |
+-------------------------------------------------------------+
     NO CTA bar.  ◑ A11yMenu fixed end-4 / inset-block-end --space-4
     page reserves padding-block-end: var(--space-16)
```

### 3.2 Mobile 375 — item-based, with the D3 deposit branch open

One wireframe, both halves of the assertion the spec names: **the deposit branch is per-row, and a non-deposit sibling in the same picker stays fully bookable.**

```
|  בֶּלָה                                                     |
|  ~~~~~~~~ gold hairline ~~~~~~~~                            |
|  (1)———(2)———(3)———(4)                                      |
|  +-- Card ---------------------------------------------------+
|  |  ( עבור: עלמה )      <- booking.forDress, Badge muted,    |
|  |                         non-interactive, PROPOSED key      |
|  |  booking.typeHeading                                       |
|  |  +--------------------------------------------------------+
|  |  | ( )  מדידה ראשונה · [45]        <- STILL SELECTABLE     |
|  |  +--------------------------------------------------------+
|  |  | (•)  חבילת כלה · [120]          <- SELECTED, deposit    |
|  |  |                                                         |
|  |  |   booking.depositByPhone … 1,500 ₪   <- one <p>, ink,   |
|  |  |                                         Price component |
|  |  |   +-- ContactPanel (inline, no Card — already on paper) |
|  |  |   |  ☎ call · WhatsApp · Waze · Maps · IG              |
|  |  |   +-------------------------------------------------- |
|  |  +--------------------------------------------------------+
|  |  | ( )  מדידה עם מלווים · [90]     <- STILL SELECTABLE     |
|  |  +--------------------------------------------------------+
|  |                                                            |
|  |  booking.pickDate  [ 04/08/2026 ]   <- STILL RENDERED      |
|  |  booking.pickTime  [10:00] [10:45] … <- STILL OPERABLE     |
|  +------------------------------------------------------------+
|                                                               |
|  → booking.backToCatalog     [ booking.submit ]  <- DISABLED  |
|                                 aria-describedby -> the notice|
```

Selecting either sibling row collapses the revealed block and re-enables the forward button; the picked time survives the switch.

### 3.3 768 / 1440 deltas

The content column is capped at 640px, so 768 and 1440 are the **same screen** — only 375 differs. Deltas from §3.1:

| # | Delta | Widths |
|---|---|---|
| 1 | Page gutters `var(--space-4)` → `var(--space-6)` | ≥768 |
| 2 | Card padding `var(--space-4)` → `var(--space-6)` | ≥768 |
| 3 | Slot grid 3 columns → 5 (one `auto-fill` rule, §3.6) | ≥768 |
| 4 | Type-picker rows: name and duration move onto **one line** (`display: flex; justify-content: space-between`) instead of stacking | ≥768 |
| 5 | Stepper labels stop wrapping (four Hebrew labels at `--text-xs` fit 640px on one line each) | ≥768 |

Everything else — one column, one Card, footer nav as one row, no CTA bar, `A11yMenu` at `--space-4` — is identical at all three widths. **Nothing is redrawn**, because nothing else moves.

### 3.4 The stepper — semantics RULED

```html
<ol aria-label={t("booking.stepsLabel")}>
  <li><a href="/book/slot">…</a></li>          <!-- completed: a real link -->
  <li><span aria-current="step">…</span></li>  <!-- current -->
  <li><span>…</span></li>                      <!-- upcoming: inert text -->
  <li><span>…</span></li>
</ol>
```

**It is NOT the ARIA tab pattern, and it is not a `progressbar`.** No `role="tablist"` / `role="tab"` / `role="tabpanel"`, no roving `tabindex`, no `aria-valuenow`. `role="tab"` would promise arrow-key roving focus over one tab stop; these are up to three sequential Tab stops (the completed links). `role="progressbar"` would promise a continuously-changing value; this is a discrete four-item list, and `<ol>` already tells AT "item 2 of 4" for free. `manage-catalog.md` §1.1 rules the same way for the console's tab strip, for the same reason.

> **⛔ OVERRIDDEN BY R2.** Assembly ruled the stepper **fully inert** — no item is a link and none is focusable. The markup block above therefore renders every `<li>` as a `<span>`, with `aria-current="step"` on the current one. The argument below is retained because its "no colour communicates alone" analysis still governs: completed is marked by the `✓` glyph, current by `aria-current` **and** weight, upcoming by an outline dot — three non-colour signals that survive the links being removed.

**Completed steps are `<Link>`s; the current and every later step are inert `<span>`s. RULED.** The prerequisite question the assignment poses resolves cleanly in one direction: **a backward step's prerequisites are satisfied by construction** — the machine only ever advances past a step after validating it, and every step's data lives in `BookPage` state for the life of the flow, so any step *strictly before the current one* is both valid and re-enterable. **Forward** steps are the ones whose prerequisites cannot be assumed, and they are never linked. The definition therefore needs no extra state: *completed ⇔ index < currentIndex*. When a mid-flow conflict resets the machine backwards (`SLOT_UNAVAILABLE` → `slot`, `TERMS_STALE` → `terms`), the current index moves back and the later steps become inert again automatically — their data survives, but they stop being offered.

*Declined*: a display-only stepper with no links (it throws away a free keyboard shortcut and the only non-colour signal that distinguishes done from pending — see below); and linking every step with a guard that silently redirects (a link that does not go where it says is a broken promise, and the guard already exists for cold URL entry where there is no alternative).

**No colour communicates alone.** Three states, three machine-readable signals with **zero new copy**: completed is a **link** (actionable), current carries **`aria-current="step"`**, upcoming is **inert text**. Visually the three are also distinguished by fill, by weight, and by the completed marker replacing the ordinal — never by hue alone.

| Stepper element | Spec |
|---|---|
| `<ol>` | `display: flex; gap: var(--space-2); align-items: flex-start; list-style: none`, `margin-block: var(--space-6)`. Never scrolls horizontally; labels wrap to at most 2 lines at 375 |
| `<li>` | `flex: 1 1 0; text-align: center; min-inline-size: 0` |
| Dot — completed | `inline-size / block-size: 24px`, `border-radius: var(--radius-full)`, `background: var(--color-gold)`, content `✓` in `var(--color-ink)` (**6.41:1** ✓, usage law 1 — gold as background, ink as glyph), `aria-hidden` |
| Dot — current | same box, `background: var(--color-ink)`, ordinal in `var(--color-bg)` (**15.24:1** ✓), `<bdi dir="ltr">2</bdi>` |
| Dot — upcoming | same box, `background: var(--color-surface-raised)`, `border: 1px solid var(--color-border-input)` (**4.18:1** on white ✓, non-text ≥3), ordinal in `var(--color-ink-muted)` (**6.36:1** on white ✓) |
| Connector | `block-size: 1px`, `background: var(--color-border)`, `aria-hidden="true"`, drawn between dots only. Decorative — the `<ol>` carries the ordering |
| Label — current | `--text-xs`, weight 600, `var(--color-ink)` (**15.24:1** on cream ✓) |
| Label — completed / upcoming | `--text-xs`, weight 400, `var(--color-ink-muted)` (**6.15:1** on cream ✓) |
| Completed link | the whole `<li>` content (dot + label) is one `<a>`; `min-block-size: 44px` including the label, `focusRing` on the anchor, no underline (the dot is the affordance and an underlined 12px Hebrew label under a chip reads as noise) |
| Not rendered on `confirm` | S5 is outside the stepper (**D8** — which is why there is no `stepConfirm` label). §7 |

### 3.5 The appointment-type picker — semantics RULED

**Native `<fieldset>` + `<legend>` + `<input type="radio">`, styled as rows. Not `Select`.** The duration, the brides-only badge and the deposit branch all have to be **visible before choosing**; a native `<select>` collapses every one of them into a single line of option text, and `components.md` bans custom dropdowns outright. *Declined*: `Select` (hides the information the choice depends on), and `Toggle`-style chips (`Toggle.tsx:22` hardcodes `role="switch"` on a closed prop list — the wrong semantic, and unreachable anyway).

`Badge` is a non-interactive `<span>` with no pressed state and no focus ring, so it is **exactly right for D10's brides-only label and exactly wrong as a selectable control**. The rows are radios; the badge rides inside one.

**No preselection.** The picker opens with nothing chosen. Preselecting the first type would choose for her, and with a brides-only or deposit-required type first it would choose wrongly.

**RULING — the D3 deposit branch is per-row.** Selecting a `deposit_required` row reveals, **inside that row's group and nowhere else**, `booking.depositByPhone` followed by an inline `ContactPanel`, and disables the footer's forward button. It does **not** touch the picker, the date control or the slot grid: siblings stay selectable, the date and time controls stay rendered and operable, and a time already picked survives a switch back to a bookable type. *Declined*: hiding the date + grid while a deposit row is selected — a mid-screen layout collapse, and it turns a per-row branch into a per-screen one, which is the exact mistake the spec's §Testing assertion is written to catch.

**RULING — the deposit amount (P4) renders inside the revealed block, through `Price`.** `qa-greps.sh:37` bans the `₪` glyph in `apps/storefront/src` unconditionally and `Price.tsx` is out of scan range, so the component is mechanically the only route; note `Price` requires `hiddenLabel` even when `visible` is true. Placement is a single `<p>` whose final run is the `<Price>` element: `{t("booking.depositByPhone")} <Price agorot={…} visible …/>`. **This constrains the copy** — `booking.depositByPhone` must be authored to end in a phrase a money amount completes (see §11 / `copy.md`). *Declined*: a permanent deposit amount or badge on the unselected row — it needs a new i18n key the spec's inventory does not carry, and it would compete visually with D10's badge on rows that carry both. `research/insights.md:34`'s "never hide fees mid-flow" is satisfied: the fee is disclosed at the moment the type is chosen, before any other step, and there is no later reveal. Recorded in §12 so the gate can overrule it with one key.

**The disabled forward button explains itself.** DOM and visual order put the revealed sentence *before* the footer nav, so a screen-reader user reading forward meets the reason before the control; the button additionally carries `aria-describedby` pointing at the revealed block's id.

### 3.6 The date control and the slot grid — RULED

**Date: native `<input type="date">` via `DateField`.** No calendar library, no custom popover — `components.md` already rules `TimeField`/`DateField` as "native inputs styled", the spec's Dependencies say "no new runtime dependency", and the native control gets the OS date picker, the OS locale and the OS accessibility stack for free.

| Attribute | Value |
|---|---|
| Label | `booking.pickDate`, **visible** (usage law 3), `--text-sm`/600, `margin-block-end: var(--space-1)` |
| `min` | today in **Asia/Jerusalem** — the server's `from` default. Computed from the returned slot instants, not from the browser clock (a bride abroad, or a device with a wrong TZ, must not be offered a date the server will reject) |
| `max` | `min` + 14 days — the server's `to` default. The 60-day clamp is the ceiling for an **explicit** `to`, and F14 sends none |
| `dir` | `"ltr"` — a date control is a numeric run |
| Initial value | the **earliest date in the window that has at least one slot**, so the default view is never empty unless the whole window is |
| Geometry | `min-block-size: 44px`, `border: 1px solid var(--color-border-input)` (**3.69:1** on paper ✓), `background: var(--color-surface-raised)`, `border-radius: var(--radius-sm)`, `max-inline-size: 200px` |

**RULING — one slots fetch for the whole window; the date field filters in memory.** `GET /storefront/slots` fires once on flow entry with no parameters and returns today..+14d; changing the date re-renders from the in-memory list. *Declined*: a fetch per date change — fourteen round trips against a throttled per-tenant read budget, and a spinner on every date tap.

> **⚠ FINDING F-A5 — a date control necessarily creates a per-date empty that the state matrix does not have.** The matrix has exactly one empty-slots row ("No bookable times in the window — empty `slots`"), but a native date input cannot disable arbitrary dates, so she can always land on a date inside the window with no times. **Resolution, and it invents no state**: `booking.noSlots` occupies the grid area **whenever the grid would be empty** — whole-window-empty and this-date-empty are the same block and the same string, because if the window is empty then every date is empty. One string, one block, one test.

**Slot grid — app-local (the spec's split rule puts it there), radio semantics, one choice.**

| Element | Spec |
|---|---|
| Group | `<fieldset>` + visible `<legend>` `booking.pickTime` (**PROPOSED new key** — see F-A6). `border: 0; padding: 0` |
| Layout | `display: grid; grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: var(--space-2)`. **One rule, no breakpoints** — the resulting counts are 3 @375 (343px content) and 5 @≥768 (640px column, capped, so 768 and 1440 are identical) |
| Chip | `<label>` wrapping a visually-hidden `<input type="radio" name="slot">`. `min-block-size: 44px`, `padding-inline: var(--space-3)`, `border-radius: var(--radius-full)`, `border: 1px solid var(--color-border-input)` (**3.69:1** on paper ✓), `background: var(--color-surface-raised)`, `color: var(--color-ink)` (**15.75:1** ✓), `--text-base`/400 |
| Chip content | `<bdi dir="ltr">10:45</bdi>` — a Latin/numeric run inside Hebrew, per the shipped bidi precedent |
| Chip — checked | `background: var(--color-gold)`, `color: var(--color-ink)` (**6.41:1** ✓ — gold as background, ink as text), `border-color: var(--color-gold-strong)` (non-text, ≥3 ✓), weight 600 |
| Chip — focus | `focusRing` on `:focus-within` of the label (**5.08–5.76:1** ✓), never `outline: none` |
| No colour-only signal | selection is carried by the native `:checked` state (which is what AT announces), by fill **and** by weight. Three channels, none of them hue alone |
| Never disabled | the grid stays operable while a deposit row is selected (§3.5) |

> **⚠ FINDING F-A6 — the i18n inventory has `booking.pickDate` but no legend string for the slot grid.** A radio group's accessible name is its `<legend>`, and usage law 3 requires it to be **visible**. **PROPOSED: one new key, `booking.pickTime`.**

### 3.7 Component notes — exact tokens

| Element | Spec |
|---|---|
| `h1` · ornament · `dressGoneGeneric` notice | §2.7 — identical on every step |
| Stepper | §3.4 |
| Card (one per step) | `background: var(--color-surface)` · `border-radius: var(--radius-md)` · `box-shadow: var(--shadow-sm)` · `padding: var(--space-6)` (`var(--space-4)` @375) · `max-inline-size: 640px` · **no hard border** — matting + shadow only. Groups inside are separated by `var(--space-6)`. *Declined*: a Card per group (three shadows on one 375 screen is noise) and no Card at all (the white `--color-surface-raised` inputs need paper behind them to read as elevated against cream) |
| Binding chip | `Badge variant="muted"` — `color: var(--color-ink-muted)` on `var(--color-surface-raised)` (**6.36:1** ✓), `border: 1px solid var(--color-border)`, no shadow, `--text-xs`/600, `padding: 2px var(--space-3)`, `border-radius: var(--radius-full)`. Content `booking.forDress` with the dress name interpolated. **Non-interactive** — there is no unbind control (*declined*: an unbind ✕, which duplicates browser-back to the dress page and adds a state the machine does not need). Reused verbatim by §4–§6 |
| Picker `<legend>` | `booking.typeHeading`, `--font-display`, `--text-xl`, weight 500, `var(--color-ink)` (**13.89:1** on paper ✓). It is the step's `h2`-weight heading; the actual `h2` element and its relationship to the `<legend>` is one of the two items in §12 |
| Type row | `<label>` wrapping `<input type="radio" name="appointment_type">`. `min-block-size: 44px`, `padding-block: var(--space-3)`, `border-block-end: 1px solid var(--color-border)`, `:last-child` none. Hover `background: var(--color-surface-raised)`. `focusRing` on `:focus-within` |
| Radio control | native, `inline-size/block-size: 20px`, `accent-color: var(--color-gold-strong)` (non-text boundary, ≥3 ✓), `margin-inline-end: var(--space-3)` |
| Type name | `--font-body`, `--text-base`, weight 600, `var(--color-ink)` (**13.89:1** on paper ✓) |
| Type duration | `booking.typeDuration` with the minutes in `<bdi dir="ltr">`, `--text-sm`, `var(--color-ink-muted)` (**5.61:1** on paper ✓) |
| Brides-only badge (**D10**) | `Badge variant="muted"` carrying `booking.audienceBrides`. It **labels, it does not gate** — the row stays selectable. Same treatment as the dress page's size chips, whose comment is the binding precedent: "Words, not just a dimmed chip: availability signalled by colour alone fails WCAG 1.4.1" |
| Deposit reveal | `<p id="deposit-notice-{typeId}">` — `--text-base`, `var(--color-ink)`, `max-inline-size: 60ch`, `margin-block: var(--space-3)`; final run is `<Price agorot={deposit_amount_agorot} visible hiddenLabel={…} />` (§3.5). Then `ContactPanel` **inline, no Card** — it is already on paper inside the picker Card; its links are `var(--color-gold-text)` underlined (**5.08:1** on paper ✓) |
| Date control | §3.6 |
| Slot grid | §3.6 |
| Footer nav | one row at **every** width: `display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); margin-block-start: var(--space-8)`. **One DOM order at every width**, so focus order can never diverge from visual order. *Declined*: `manage-restyle.md`'s 375 full-width-primary rule — stacking would need the primary first visually and back first in DOM, or a `column-reverse` that breaks focus order |
| Footer — back | `<Link to="/">` with the `aria-hidden` `→` glyph, label `booking.backToCatalog`, styled as the storefront link (`text-gold-text underline`, **5.57:1** ✓), `min-block-size: 44px`. **Step 1's back target is always `/`, never the bound dress** — one target, one string; the dress page is one tap from the catalog, and a label saying "back to the collection" pointing at a dress page would be a lie. Steps 2–5 use `booking.backStep` and the previous step's URL (§4–§6) |
| Footer — forward | `Button variant="primary" size="lg"` (`min-h-12`), label `booking.submit`, busy label `booking.submitting` via the `loading` prop (which forces `disabled` + `aria-busy` and keeps the label in the DOM under `aria-hidden` so the width never jumps). `min-inline-size: 140px`. `background: var(--color-gold)` + `color: var(--color-ink)` (**6.41:1** ✓) |
| Forward — disabled | when no type or no time is chosen, or a deposit row is selected. `aria-describedby` points at the deposit notice in the deposit case; in the plain "nothing chosen yet" case the button is disabled with no extra prose, because the two unfilled controls above it are the explanation and a sentence restating them is noise |

> **⚠ FINDING F-A7 — the inventory has no "next" string; `booking.submit` has to be step-neutral.** The keys are `booking.{submit, submitting, backStep, backToCatalog}` — one forward label for four steps whose last one really does submit a booking. **RULED**: `booking.submit` is the forward label on **every** step and `booking.submitting` its busy state, which means the copy author must write it as a neutral "continue", not "book". Flagged to §11 / `copy.md` as a hard constraint, not a preference.
>
> **⛔ RESOLVED DIFFERENTLY BY R4.** The finding is real and is accepted; the resolution is not. Rather than constrain one string to serve four actions, assembly adds one key: **`booking.continue`** is the forward label on steps 1–3, and `booking.submit` / `booking.submitting` are reserved for the verify step's commit. This *removes* the constraint on the copy author instead of imposing it. Wherever this section's wireframes and tables show `booking.submit` as the forward label on the slot step, read `booking.continue`.

### 3.8 States

Every row here is a row of the spec's state matrix. Ordering follows the matrix.

| State | What she sees | Trigger | Test |
|---|---|---|---|
| **Default, generic** | wireframe §3.1 | types + slots present, no dress bound | unit + e2e |
| **Default, item-based** | wireframe §3.2 minus the deposit reveal — binding chip above the picker | entered from a dress page, dress read OK | unit + e2e |
| **Loading** | wireframe S0-a (§2.6) — live stepper, skeleton Card body, no footer nav | entry fetches in flight | unit |
| **Brides-only badge** (**D10**) | `Badge muted` inside the row; row stays selectable | `audience` = brides-only | unit |
| **Deposit-required type** (**D3**) | wireframe §3.2 — reveal under **that row**, siblings bookable, grid still operable, forward disabled | `deposit_required` on the selected row | unit — **the sibling assertion is the one the spec names** |
| **Deposit reveal under D12** | the same reveal, `ContactPanel` omitted, `booking.contactUnavailable` in its place (§2.5) | `deposit_required` **and** no boutique | unit |
| **E3 — no active appointment types** | wireframe S1-e — the phone-only block replaces the Card; no date, no grid, no forward button | `/appointment-types` → `[]` | unit |
| **No bookable times** | `booking.noSlots` fills the grid area: `--text-base`, `var(--color-ink-muted)`, centred, `padding-block: var(--space-8)`, `max-inline-size: 40ch`. The legend, the date control and the type picker stay. **This is the state every new tenant ships in, so it must read as a fact, not a fault** — no icon, no border, no danger colour, no retry button (there is nothing to retry) | empty `slots`, or a chosen date with none (F-A5) | unit |
| **Load failure (step-level)** | the Card body is replaced by one muted `role="alert"` carrying `booking.slotsError` + `Button variant="secondary"` `catalog.retry` (existing key). **One alert, not three** — a single outage announced three times makes a screen reader read three messages for one problem (`CatalogPage.tsx:167-171`'s rule). The retry re-runs whichever of the entry calls failed | terms non-404 · `/appointment-types` error · `/slots` error · `429` on any | unit |
| **`SLOT_UNAVAILABLE` return** | she arrives back at `/book/slot` from a failed submit. Slots are **re-fetched**, the picked time is **cleared**, and a `role="alert"` block sits directly above the slot-grid legend carrying `errors.slotUnavailable` in `var(--color-danger)` (**6.18:1** on paper ✓). The type and date survive. Wireframe S1-f | `409 SLOT_UNAVAILABLE` from `POST /bookings` (§6) | unit + e2e |
| **`typeGoneRepick` return** | same shape, one level up: the `role="alert"` sits above the **picker** legend carrying `booking.typeGoneRepick`, the type list is the freshly re-fetched one, and the type selection is cleared. Wireframe S1-g | submit-time `NOT_FOUND` probe finds the type gone (§6) | unit |
| **`TOO_MANY_ATTEMPTS`** | the step-level load-failure block, with `errorMessageOr(error, t, "booking.slotsError")` resolving to `errors.tooManyAttempts` (already mapped — **do not add a second case or a second key**) in `var(--color-ink-muted)`, plus the retry button. Muted, not danger: a spent budget is not her mistake | `429` on any entry call | unit |
| **Dress archived before the flow** | §2.6 wireframe S0-b — binding chip replaced by the `role="status"` notice | `GET /dresses/{id}` → `404` | unit |
| **Step entered without prerequisites** | not a visual state — the guard redirects to `slot`, which is this screen's default | direct entry to a later step (**D8**) | unit |

**Two colour categories, RULED, because the storefront has two kinds of bad news.**

| Category | Colour | Applies to |
|---|---|---|
| **A conflict she must act on** | `var(--color-danger)` (**6.78:1** on cream · **6.18:1** on paper ✓), matching the shipped `Input` error treatment | `errors.slotUnavailable` · `errors.termsStale` · `errors.otpInvalid` / `otpExpired` · `booking.typeGoneRepick` · `booking.sizeGoneRepick` · every client-validation message |
| **An outage or a limit, which is not her fault** | `var(--color-ink-muted)` (**6.15:1** on cream ✓) | `booking.slotsError` · `errors.tooManyAttempts` · `errors.unknown` on load · `errors.smsUnavailable` · `booking.dressGoneGeneric` |

`CatalogPage.tsx:181-182`'s rule is the source of the second row ("a backend that is down is not the boutique's fault"); the first row exists because a slot conflict is specific, actionable and hers to resolve, and rendering it in the same muted grey as an outage would make it read as noise. In **both** categories the meaning is carried by a full sentence — never by hue (usage law 2).

**At most one `role="alert"` on the screen at a time.** If a return-reason alert is present, the grid's own empty state renders without a second one.

### 3.9 State wireframes

**S1-e — E3, no active appointment types (375).**

```
|  בֶּלָה                                      |
|  ~~~~~~~~ gold hairline ~~~~~~~~             |
|  (no stepper — there is no flow to be a step of)
|                                              |
|  booking.noTypes         (--text-base, ink, max 60ch)
|                                              |
|  +-- Card ----------------------------------+|
|  |  [ ContactPanel ]                        ||
|  +------------------------------------------+|
|                                              |
|  → booking.backToCatalog                     |
```

Under **D12**: the Card and panel are omitted and `booking.contactUnavailable` follows the sentence in `var(--color-ink-muted)`.

**S1-f — `SLOT_UNAVAILABLE` return (375).**

```
|  +-- Card -----------------------------------------------+
|  |  booking.typeHeading                                  |
|  |  | (•)  מדידה ראשונה · [45]     <- selection SURVIVES |
|  |  | ( )  חבילת כלה · [120]                             |
|  |                                                       |
|  |  booking.pickDate  [ 04/08/2026 ]   <- SURVIVES       |
|  |                                                       |
|  |  errors.slotUnavailable      <- role="alert", --color-danger,
|  |                                 --text-base, above the legend
|  |  booking.pickTime                                     |
|  |  [10:00] [11:30] [13:00]     <- RE-FETCHED, none checked
|  |  [14:30]                                              |
|  +-------------------------------------------------------+
|  → booking.backToCatalog     [ booking.submit ] (disabled — no time)
```

**S1-g — `typeGoneRepick` return (375).** Identical, one level up: the `role="alert"` carrying `booking.typeGoneRepick` sits above `booking.typeHeading`, the picker holds the re-fetched list with nothing selected, and the date and time survive.

> **⚠ FINDING F-A8 — `booking.slotsError` has to carry three failures, not one.** The inventory names one error string for this step, but three different entry calls can fail it (terms non-404, `/appointment-types`, `/slots`) and the flow cannot proceed without any of them. Rather than add two keys, this section rules **one load-failure state with one string**, which means `booking.slotsError` must be authored as a step-level "we could not load the available appointments right now", **not** a slots-only sentence. Flagged to §11 / `copy.md`. *Declined*: per-fetch inline recovery — three alerts and three retry buttons for one outage, against `CatalogPage`'s explicit one-alert law.

### 3.10 Keyboard and focus on this screen

Owned in full by §8; three rulings originate here and are recorded so §8 can absorb them rather than re-derive them.

1. **No per-step focus move.** The Router already focuses `<main id="content" tabIndex={-1}>` and scroll-resets on every step transition (§0). The slot step adds nothing.
2. **Focus destination on a return-path alert.** `SLOT_UNAVAILABLE` and `typeGoneRepick` arrive *with* a navigation, so the Router's focus move to `<main>` already puts a screen-reader user above the alert, and the alert's `role="alert"` announces it regardless. **No additional focus move**, and no `tabindex="-1"` on the alert.
3. **Tab order at 375** is: skip link (layout) → completed stepper links (0–3 of them) → type radios (one stop, arrow keys move within the group — native radio behaviour, not something F14 implements) → date input → slot radios (one stop, arrows within) → back link → forward button → footer → `A11yMenu`. Visual order matches, RTL-aware.
## 4. Screen S2 — Details (`/book/details` · `/book/details/{dressId}`)

> **Reading the wireframes** (restated here for standalone reading; the canonical note belongs at the head of this document). ASCII is drawn in **logical order** — inline-**start** on the left of the drawing, inline-**end** on the right. On screen everything is mirrored: the storefront is `dir="rtl"` and inline-start is the **right** edge. Every rule below is written in logical properties (`padding-inline-*`, `margin-inline-*`, `inset-inline-*`, `text-align: start/end`, `min-block-size`, `max-inline-size`). **Where a Tailwind class is quoted it is the class the build will actually ship** (`max-w-[640px]`, `min-h-11`) — `Frontend/scripts/qa-greps.sh:40` bans physical *inline-direction* utilities (`ml-`, `pl-`, `left-`, `text-left`, `border-l-`) and nothing else, and the shipped storefront uses `max-w-`/`min-h-`/`min-w-0` throughout. Conflating the CSS-spec vocabulary with the Tailwind class vocabulary produces a document the build cannot follow.

The step that collects the two things `POST /storefront/bookings` needs from a
human and cannot infer: **who she is** (`name`, required) and **what she wants the
boutique to know** (`notes`, optional). On the item-based path it also collects
`dress_size`, which — see §4.8 ⚠ F1 — the backend requires whenever `dress_id`
is sent.

Owned elsewhere and cross-referenced, never re-specified here: the step column
width, gutters, page bottom padding and `A11yMenu` clearance (§2 — the flow
shell); the stepper, the single `h1`, `document.title` and the `booking.backStep`
`<Link>` (§2); the appointment-type picker and slot grid (§3 — Screen S1); the
submit call and its `NOT_FOUND` probe (§6 — Screen S4).

### 4.1 Mobile 375 — generic path (no dress bound)

```
+---------------------------------------------------------+
|  → [booking.backStep]              <- Link, §2 owns it   |
|                                                          |
|  [ stepper: 1 — (2) — 3 — 4 ]      <- §2 owns it         |
|                                                          |
|  [booking.stepDetails]     (h2, --font-display, --text-xl)|
|                                                          |
|  +-- Card (paper, --space-6, radius-md, shadow-sm) -----+ |
|  |                                                      | |
|  |  [booking.name]                (label, sm/600, ink)  | |
|  |  [ ................................................] | |
|  |                                                      | |
|  |  [booking.notes]               (label, sm/600, ink)  | |
|  |  [booking.notesHint]           (help, xs, ink-muted) | |
|  |  [ ................................................] | |
|  |  [ ................................................] | |
|  |  [ ................................................] | |
|  |  [ ................................................] | |
|  |                                        0 / 500       | |
|  |                            ^ counter, xs, ink-muted, | |
|  |                              text-align: end,        | |
|  |                              <bdi dir="ltr">         | |
|  +------------------------------------------------------+ |
|                                                          |
|  [            booking.continue            ]  <- lg,      |
|                                                 full-width|
|                                                          |
|  (page reserves padding-block-end for the A11yMenu — §2) |
+---------------------------------------------------------+
```

### 4.2 Mobile 375 — item-based path (`/book/details/{dressId}`)

```
+---------------------------------------------------------+
|  → [booking.backStep]                                    |
|  [ stepper ]                                             |
|  [booking.stepDetails]                            (h2)   |
|                                                          |
|  +-- Card ----------------------------------------------+ |
|  |  +--------+                                          | |
|  |  | 64px   |   <dress.name>   (--font-display,        | |
|  |  | 3:4    |                   --text-lg, ink)        | |
|  |  | cover  |                                          | |
|  |  +--------+   <- alt="", NOT a link (§4.6)           | |
|  |                                                      | |
|  |  ---------------------------------- hairline         | |
|  |                                                      | |
|  |  [booking.name]                                      | |
|  |  [ ................................................] | |
|  |                                                      | |
|  |  +-- fieldset ------------------------------------+  | |
|  |  | <legend> [dress.sizes] </legend>               |  | |
|  |  |                                                |  | |
|  |  | ( 36 )  ( 38 )  (•40 )  ( 42 )   <- radios,    |  | |
|  |  |                                     wrap, 44px |  | |
|  |  | ( 44         )                                 |  | |
|  |  | ( [booking.  )   <- an unavailable size: the   |  | |
|  |  | ( sizeUnavail)      phrase is a SECOND LINE    |  | |
|  |  |                     inside the same chip label |  | |
|  |  +------------------------------------------------+  | |
|  |     ^ • = selected. On screen the marker is a 2px    | |
|  |       gold-strong border + weight 600, not a glyph;  | |
|  |       drawn here only to show which chip is checked. | |
|  |                                                      | |
|  |  [booking.notes] / [booking.notesHint]               | |
|  |  [ ................................................] | |
|  |  [ ................................................] | |
|  |                                        0 / 500       | |
|  +------------------------------------------------------+ |
|                                                          |
|  [            booking.continue            ]              |
+---------------------------------------------------------+
```

**Field order is fixed and is not a taste call.** Name first, then size, then
notes. Size sits *between* the two text fields because it is the only control on
this screen that a mid-flow API answer can invalidate (§4.7 `sizeGoneRepick`,
`dressGoneGeneric`); putting it last would mean a returning bride scrolls past
her own already-typed answers to reach the one thing she is being asked to redo,
and putting it first would open a form for a stranger with a chip grid instead of
her name. Declined: grouping the dress binding and its sizes into a second Card —
two Cards on a 375 screen for one dress is section rhythm spent on nothing.

### 4.3 768 / 1440 deltas

Deltas only; everything not listed is identical to 375.

| Width | Delta |
|---|---|
| **768** | Card padding stays `var(--space-6)` (see §4.6 — the shipped `Card` cannot be talked out of it). The forward `Button` stops being full-width and sits at the **inline-end** of the step (`display:flex; justify-content:flex-end`), matching the console's ≥768 form rule. Size chips wrap into fewer rows; no other change |
| **1440** | Identical to 768. **The form never becomes multi-column at any width** — `/about`'s editorial column is the storefront's precedent for a reading-and-typing surface (`storefront-profile-hours.md:48`, "never goes multi-column"), and a two-column name/notes split would put a 500-character textarea and an 80-character input on the same baseline, which reads as two unrelated forms |

### 4.4 The two bounds — RULED

The spec names this as a testable boundary ("500 submits and 501 is refused
client-side with no request issued, likewise 80 and 81"). It does not say what
she *sees* at the boundary. Ruled here, and the plan implements exactly this.

**Ruling 4.4a — the fields carry native `maxLength`.** `name` gets
`maxLength={MAX_CUSTOMER_NAME_LENGTH}` (80), `notes` gets
`maxLength={MAX_BOOKING_NOTES_LENGTH}` (500), both imported from
`src/validation.ts`, never as literals. This is the console's shipped precedent
(`DressEditor.tsx:268,285`; `VariantMatrix.tsx:203`; `CatalogSection.tsx:125`)
and it is what makes the counter honest. **Consequence, stated because it is
easy to mis-test: 81 and 501 are unreachable through the UI** — the UA refuses
the keystroke and truncates a paste. The `validateName` / `validateNotes` guards
still exist and are still the thing the boundary test drives, because (a) they
are the mirror `test_frontend_constant_parity.py` pins, and (b) the submit path
must be provably incapable of issuing a request for an over-length value
regardless of how the value got there.

**Ruling 4.4b — the length check runs on the RAW value; the blank check runs on
the TRIMMED value.** This mirrors `backend/app/booking/validation.py` line for
line — `if not name.strip()` then `if len(name) > MAX_CUSTOMER_NAME_LENGTH` — and
**the value sent on the wire is the raw one, untrimmed.** Declined: trimming
client-side before validating or before sending. A client that validates a
different string than the server receives is exactly how a `400 VALIDATION_ERROR`
the client believed impossible reaches a bride.

**Ruling 4.4c — errors surface on SUBMIT, never on blur, never on input.**
Blur-time validation on a three-control form fires the moment she tabs out of a
field she fully intends to come back to; input-time validation tells her the name
is required before she has finished typing the first letter. On the forward
press: run all three validators, render every failure inline, move focus to the
first invalid control, issue no request. This is `manage-catalog.md` §3.5
"Validation error (client)" verbatim, and it is the shape the shipped `Input`
already implements (`Input.tsx:31-45` — `aria-invalid`, `aria-describedby`, and
an error `<span role="alert">`).

**Ruling 4.4d — the forward button NEVER disables on validation state.** It is
always enabled and always pressable; it submits and fails visibly. A disabled
forward button on a form is the single worst affordance available: it states no
reason, `disabled` drops it from the tab order so a screen-reader user reaching
it any other way learns nothing, and `aria-describedby` on a disabled control is
inert (`manage-catalog.md` §10.3, "Disabled controls explain themselves").
Declined: disabling until valid, and disabling on an empty required field.

**Ruling 4.4e — the counter appears on `notes` only, never on `name`.**
`TextArea` ships `showCount` (`TextArea.tsx:10,46-50`); `Input` does not, and
adding it would be a `packages/ui` change bought for nothing. Reason beyond the
mechanics: a counter under a name field reads as a rule the boutique might
enforce against her name. 80 characters is not a budget anyone plans against;
500 characters of free prose is. Declined: adding `showCount` to `Input`;
declined also porting the console's near-cap warning colour
(`manage-catalog.md` §3.4 turns the counter `--color-warning-text`/600 within 20
of the cap) — that behaviour exists because a 4,000-character description is a
budget an owner plans against, and here `maxLength` makes overrun impossible, so
a warning colour would warn about nothing. **The counter stays
`--color-ink-muted` at every value, including 500 / 500.**

**Ruling 4.4f — the counter is not a live region, and nothing announces
keystrokes.** `TextArea`'s counter is a plain `<span>` joined into
`aria-describedby` (`TextArea.tsx:17-18`), so it is spoken once when focus
arrives at the field and never again. That is correct and must not be
"improved": `manage-catalog.md` §10.3's rule applies verbatim — *a continuously
changing value is never itself a live region* — and a live counter on a 500-char
field announces once per character, each announcement interrupting the last.

**Ruling 4.4g — an empty `notes` is OMITTED from the payload, not sent as
`""`.** `validate_booking_request` guards `if notes is not None`, so `""` passes
harmlessly — but omitting keeps "she wrote nothing" as one state in the owner's
console instead of two.

### 4.5 Size chips (D4) — RULED

Every entry in `GET /storefront/dresses/{id}`'s `sizes[]` renders as a
selectable chip, **including `available: false`** (D4). The chips are native
`<input type="radio">` inside a `<fieldset>` with a `<legend>`.

**Ruling 4.5a — real radios, visually-hidden input, styled `<label>` chip.**
`components.md`'s stated philosophy is native-first ("native `<select>` styled —
no custom dropdown in v1 (a11y cost not worth it)"). A native radio group gives
single-selection, arrow-key roving and the correct `radiogroup` announcement for
free. The `<input>` is `sr-only` (not `display:none`, which removes it from the
a11y tree); the `<label>` carries the chip visual and the focus ring, drawn via
`:has(:focus-visible)`. Declined: `role="radiogroup"` over `<button>`s — that is
ARIA promising behaviour we would then have to hand-write, the same defect class
`manage-catalog.md` §4.3 rules against for `aria-pressed`.

**Ruling 4.5b — `available: false` gets NO stock styling. None.** The
unavailable chip is visually identical to an available one: same border, same
fill, same weight, same text colour, same size. **The signal is a word, and only
a word.** `booking.sizeUnavailable` renders as a **second line inside the same
`<label>`**, `--text-xs`, `--color-ink-muted`, so it is visible *and* inside the
radio's accessible name by construction — no `sr-only` twin, no `aria-label`
override.

Every alternative is declined, and each for its own reason:

| Declined | Why |
|---|---|
| `Badge variant="warning"` (the console's "אזל מהמלאי") | That is a **stock-warning register**. This is a fitting, not a purchase, and D4's whole point is that the size stays bookable. Borrowing the console's out-of-stock chrome tells the bride the opposite of what the copy says |
| Strikethrough on the size number | Reads as "unavailable / disabled". It is neither |
| Dimming (`opacity`) | Colour-only signalling (usage law 2) *and* `manage-catalog.md` §10.3's flat ban on `opacity` as a way to recess text |
| `Badge variant="muted"` per the shipped `DressPage.tsx:214` | That component is **not selectable** and has no room for a phrase, which is why it needs an `sr-only` word. A chip label has room; use it |
| Any badge, ribbon, countdown or urgency bar | Usage law 9. There is no promo register anywhere in this flow |

**Copy constraint for the copy author (§copy deck):** because
`booking.sizeUnavailable` renders inside **every** unavailable chip, it must be a
**short phrase, ≤ 24 characters** — not the full "may need to be ordered in"
sentence. It carries the whole meaning on its own; there is no second
group-level sentence, because the inventory has no key for one and inventing one
would put the same information in two places.

**Ruling 4.5c — the size is REQUIRED on the item-based path.** See §4.8 ⚠ F1:
the backend rejects `dress_id` without `dress_size`. So the fieldset is a
required control. No option is pre-selected, and there is no "not sure" escape
hatch. Declined: pre-selecting the first available size (putting a size in her
mouth on a fitting booking, and worse if the first entry is `available: false`);
declined a "not sure" member (it cannot exist — the server refuses the payload it
would produce). The missing-selection error needs one new key, **P8**.

**Ruling 4.5d — the legend reuses the shipped `dress.sizes` key** ("מידות",
`he.ts:38`). It is already the storefront's word for this set on the dress page,
and reusing it costs no key. If the copy author wants a form-voice singular
("מידה"), that is a copy-deck call and a new key; flagged there, not decided
here.

**Ruling 4.5e — a bound dress with ZERO active sizes drops the binding.** See
§4.8 ⚠ F2. The dress name and cover stay on screen for orientation, the fieldset
does not render, and `booking.dressGoneGeneric` states the outcome in a
`role="status"`. `dress_id` and `dress_size` are both omitted from the payload
(the two-path model: both or neither).

### 4.6 Component notes — exact tokens

| Element | Spec |
|---|---|
| Step heading | `SectionHeading as="h2"` with **no ornament** — `--font-display`, `--text-xl`, `var(--color-ink)` (**13.89:1** on paper / **15.24:1** on cream). The ornament is `/about`'s identity moment; a form step is not one. The flow's single `h1` is owned by §2 and does not change across steps (one `DOC_TITLE_KEYS` entry, `document.book`). **If §2 rules the step heading itself the `h1`, this row becomes `h1` and nothing else in §4 or §5 changes** |
| Card | `Card` as shipped: `background: var(--color-surface)`, `border-radius: var(--radius-md)`, `box-shadow: var(--shadow-sm)`, `padding: var(--space-6)` **at every width, 375 included**. No hard border — matting + shadow only. **The console's `--space-4`-at-375 reduction is declined and is also unbuildable**: `Card` hardcodes `p-6` and `cn` has no tailwind-merge (spec §What `packages/ui` does not have, constraint 2), so a caller `p-4` loses to `p-6` on stylesheet order. The shipped storefront `HoursCard`/`ContactCard` already pad `--space-6` at 375; `tokens.md` says "cards pad `--space-6`" unconditionally |
| Name field | `Input` — `label={t("booking.name")}`, `type="text"`, `autoComplete="name"`, `enterKeyHint="next"`, `dir="auto"` (a Latin name is ordinary), `maxLength={80}`, `required`. Box: `background: var(--color-surface-raised)`, `border: 1px solid var(--color-border-input)` (**4.18:1** on its own white fill, **3.69:1** against the paper Card — both ≥3:1), `border-radius: var(--radius-sm)`, `padding: var(--space-2) var(--space-3)`, `min-block-size: 44px`. Focus: `2px solid var(--color-focus)` at `2px` offset (`focusRing`, usage law 4). Error state adds `border-color: var(--color-danger)` — colour **plus** the message, never colour alone. **No asterisk** (see the required-marking note below) |
| Notes field | `TextArea` — `label={t("booking.notes")}`, `help={t("booking.notesHint")}`, `showCount`, `maxLength={500}`, `rows={4}`, `dir="auto"`, `className="[resize:block]"` (logical; the default `resize: both` lets a drag widen the field past the column and produce horizontal scroll at 375). Same box tokens as the name field. `notes` deliberately permits tab / LF / CR (D7) — a textarea is the right control and nothing strips them |
| Char counter | Shipped `TextArea` markup: `--text-xs`, `var(--color-ink-muted)` (**5.61:1** on paper), `text-align: end`, joined into `aria-describedby`. Wrap the numeric run: `<bdi dir="ltr">0 / 500</bdi>`. **Plain text, never a live region** (§4.4f) |
| Required marking | **The storefront uses no `*` convention.** The console's asterisk needs an explanatory line and its own key; this form has two required controls and one optional one, so the optional one carries the word instead — `booking.notesHint` states the optionality. Copy constraint, no new key |
| Bound-dress cover | `inline-size: 64px`, `aspect-ratio: 3/4`, `background: var(--color-surface)` (the cream matting), `border-radius: var(--radius-md)`, `box-shadow: var(--shadow-sm)`, `overflow: hidden`. `<img loading="lazy" decoding="async" alt="">` `object-fit: cover` — `alt=""` because the dress name is the adjacent visible text. **No hard border** — matting + shadow only (`tokens.md`). No image ⇒ the box renders empty as matting; the `Monogram` placeholder is the dress page's identity moment and is oversized for a 64px binding chip |
| Bound-dress name | `--font-display`, `--text-lg`, `var(--color-ink)`. **NOT a link.** Declined linking to `/dress/{id}`: the picked slot, the appointment type and the form draft all live in memory, `localStorage` is banned outright (`qa-greps.sh:33`), and there is no draft persistence — a tap that leaves the flow discards everything she has entered. The `booking.backStep` `<Link>` is the only navigation on this screen |
| Binding hairline | `1px solid var(--color-border)`, `margin-block: var(--space-4)`. Decorative (1.22:1) and never the only thing delimiting anything |
| Size fieldset | `<fieldset>` with a visible `<legend>` (`dress.sizes`), `--text-sm`, weight 600, `var(--color-ink)` — the legend **is** the visible label; usage law 3 is satisfied by it and no `aria-label` is added. `border: none; padding: 0; margin: 0` on the fieldset itself (UA defaults are not the design). Chips: `display:flex; flex-wrap:wrap; gap: var(--space-2)` |
| Size chip — resting | `<label>`: `min-block-size: 44px; min-inline-size: 44px`, `display:flex; flex-direction:column; align-items:center; justify-content:center`, `padding-inline: var(--space-3)`, `border: 1px solid var(--color-border-input)` (**3.69:1** on paper), `border-radius: var(--radius-full)` (pill — `manage-catalog.md` §12 item 3e records `tokens.md`'s radius table as the stale side), `background: var(--color-surface-raised)`, `--text-sm`, `var(--color-ink)`. Size label `<bdi dir="ltr">38</bdi>`. `cursor: pointer` |
| Size chip — selected | `border: 2px solid var(--color-gold-strong)` (**3.47:1** against the paper Card, **3.93:1** against the chip's own white fill) **plus label weight 600**. The differentiator is a **border-width** change and a **weight** change, not a hue change — usage law 2 is discharged on the visual side by geometry, and on the AT side by the radio role itself, which announces "selected". The 1px→2px growth is absorbed inside the chip (`padding-inline` drops by 1px when selected, or the resting chip carries a transparent 2px border) so nothing reflows on selection |
| Size chip — unavailable | **Identical** to the resting chip in every token. Adds one second line inside the same `<label>`: `booking.sizeUnavailable`, `--text-xs`, `var(--color-ink-muted)` (**6.36:1** on the chip's white fill), `text-align: center`. Chip grows in block size; `min-block-size: 44px` is a floor, not a height |
| Size chip — focus | The `<input type="radio">` is `sr-only`; the ring is drawn on the `<label>` via `:has(:focus-visible)` → `outline: 2px solid var(--color-focus); outline-offset: 2px` (**5.76:1** on white). `outline` + `outline-offset` and nothing else — the browser traces the pill radius itself |
| Forward button | `Button variant="primary" size="lg"` (`min-block-size: 48px` ✓), label `booking.continue` (**P7** — see §4.8 ⚠ F3), `fullWidthMobile`. `background: var(--color-gold)` + `color: var(--color-ink)` = **6.41:1** ✓ — the only legal way gold touches this button (usage law 1). **Never wrapped in `BookingCTA`**: `hasBookingBar` is `catalog \|\| dress` and excludes `/book` deliberately (spec Risk 6, `StorefrontLayout.tsx:63-65`), so this is an ordinary in-flow button. It navigates with `navigate()` to `/book/terms` or `/book/terms/{dressId}`, preserving the path segment |
| Motion | Chip selection: `transition: border-color var(--motion-fast) var(--ease-out)`. Nothing else on this screen animates. Under `prefers-reduced-motion: reduce` the transition is `none` (theme-level). Collected into the document's §Motion |

### 4.7 States

| State | What she sees | Trigger |
|---|---|---|
| **Default, generic** | Name + notes in one Card, forward button below | no `dressId` in the path |
| **Default, item-based** | Cover + name, hairline, name field, size fieldset, notes | `dressId` present and `GET /dresses/{id}` resolved with `sizes.length > 0` |
| **Loading (binding)** | Name and notes render **immediately and are typeable**; only the binding block is deferred — `Skeleton variant="image"` at 64px in the cover slot and `Skeleton variant="text" lines={1}` for the name, with `Skeleton variant="text" lines={2}` in the fieldset slot. **The form is never blocked on the dress fetch** — she can be typing her name while it lands | `GET /dresses/{id}` in flight |
| **Validation — name empty** | `booking.nameRequired` inline under the field, `--text-sm`, `var(--color-danger)` (**6.18:1** on paper), `role="alert"` + `aria-describedby` (shipped `Input`); `aria-invalid="true"`; border turns `--color-danger`. Focus moves to the name input. **No request issued** | forward pressed, `name.trim() === ""` |
| **Validation — name too long** | `booking.nameTooLong`, same treatment. **Unreachable through the UI** (`maxLength={80}`); it exists because the validator is the mirror the parity test pins, and the submit path must be provably incapable of sending an over-length name | `len(name) > 80` |
| **Validation — notes too long** | `booking.notesTooLong`, same treatment on the textarea. Same unreachability note (`maxLength={500}`) | `len(notes) > 500` |
| **Validation — no size picked** | `booking.sizeRequired` (**P8**) rendered inside the fieldset directly under the chips, `--text-sm`, `var(--color-danger)`, `role="alert"`, tied to the fieldset via `aria-describedby` on the group. Focus moves to the **first radio** in the group. No request issued | forward pressed on the item path with no radio checked |
| **`sizeGoneRepick` return** | She arrives back here **from the submit probe** (§6). `booking.sizeGoneRepick` renders at the top of the fieldset in `role="alert"`, `--text-sm`, `var(--color-warning-text)` (**5.20:1** on paper) — cautionary, not danger: nothing she did failed, the boutique's stock moved. **Her previous size selection is cleared**, the chips repaint from the freshly re-fetched `sizes[]`, and the name and notes she already typed are untouched. This is a navigation (`/book/verify/…` → `/book/details/{dressId}`), so the Router's own effect scroll-resets and moves focus to `<main>` (`router.tsx:196-211`) — **§4 adds no competing focus move**; the `role="alert"` is what speaks | `NOT_FOUND` probe: type present, dress present |
| **`dressGoneGeneric` — mid-flow drop** | The **entire binding block is removed** — cover, name, hairline and fieldset all unmount — and `booking.dressGoneGeneric` takes their place as a `role="alert"` line, `--text-sm`, `var(--color-warning-text)`. Name and notes stay exactly as typed and keep their scroll position; the Card visibly shortens. `dress_id`/`dress_size` are dropped from the payload. **The URL is NOT rewritten** — see ⚠ F4 | `GET /dresses/{id}` → `404 NOT_FOUND`, or the submit probe finds the dress gone |
| **`dressGoneGeneric` — zero sizes** | Same copy, but `role="status"` (polite) and the **cover and name stay on screen**: nothing failed and nothing vanished, the dress simply has no bookable variants. Only the fieldset is absent. §4.8 ⚠ F2 | `sizes.length === 0` |
| **Dress fetch failed (not 404)** | The binding block collapses to the same `dressGoneGeneric` line. **No retry button, no error voice.** A 5xx on the *binding* must not stop a bride booking a fitting; the storefront's one-alert rule (`CatalogPage.tsx:167-171`) applies — the form is the page's voice, not the sidecar | 5xx / network on `GET /dresses/{id}` |
| **Forward pressed, all valid** | `navigate()` to `/book/terms[/{dressId}]`. No spinner, no loading state — **this step issues no request on forward** | — |

**Not a state here.** The dress's *price*, *reserved* flag and *description* are
not rendered on this screen. She has already seen them; the booking screen is
where she gives information, not where the catalog is restated (and `Price`
would drag `--color-gold-text` and a whole second register onto a form).

### 4.8 ⚠ FINDINGS (§4)

**⚠ F1 — `dress_size` is REQUIRED whenever `dress_id` is sent. The spec's
contract table says otherwise.**
The spec's §The contract F14 consumes writes the booking body as
`{… dress_id?, dress_size?, notes?}`, which reads as three independently optional
fields. `backend/app/booking/validation.py` is stricter and says so explicitly:

```python
# The two-path model, enforced at the boundary: item-based carries BOTH
# dress_id and dress_size, generic carries NEITHER.
if dress_id is not None and (dress_size is None or not dress_size.strip()):
    raise BookingValidationError("dress_size is required when dress_id is given")
if dress_id is None and dress_size is not None:
    raise BookingValidationError("dress_size requires dress_id")
```

Consequences, all of which §4 now designs for: the size fieldset is a **required
control**, not an optional nicety; there can be no "not sure" option and no
unselected-and-submit path; a bound dress with no pickable size must **drop the
binding** rather than send a partial pair; and the flow needs one error string
the i18n inventory does not contain (**P8**, `booking.sizeRequired`). *Action: the
spec's contract table should read `dress_id? + dress_size?` as a paired unit.
Nothing else in the spec moves.*

**⚠ F2 — a dress with zero active sizes is unbookable as item-based, and no
state covers it.**
`DressPage.tsx:208` renders the size block only when `dress.sizes.length > 0`,
so a variant-less dress is a shipped, reachable state — indeed the state **every
dress ships in** before the owner opens the variant matrix
(`manage-catalog.md` §4.5, "לא הוגדרו מידות"). Its `BookingCTA` is live and
constructs `/book/…/{dressId}` all the same. With ⚠ F1, that path cannot produce
a valid payload. §4.5e rules it: drop the binding, keep the dress visible, say so
once. *Action: add a row to the spec's §State matrix — "Bound dress has no active
sizes → binding drops, generic booking · D · unit". Design is already here; only
the matrix row is missing.*
**Copy constraint that falls out of this**: `booking.dressGoneGeneric` must be
written **cause-agnostic** — "the dress cannot be attached to this appointment;
continuing as a regular appointment" — because it now serves three triggers (404
at the size fetch, 404 from the submit probe, and zero active sizes). Written as
"the dress was removed" it would be a lie in the third case. Flagged to §copy
deck.

**⚠ F3 — the i18n inventory has no forward-button label for the non-terminal
steps.**
The inventory carries `booking.submit` and `booking.submitting` and nothing else
button-shaped. Reusing `booking.submit` on `slot`, `details` and `terms` produces
a button that says "submit" when nothing is submitted — and, sitting next to a
consent checkbox on the terms step, tells a bride she has booked when she has not
yet verified her phone. That is precisely the dead-end class this feature exists
to remove. Cannot be solved by interpolation: `i18n-keys.test.ts` only sees
literal keys, and one string cannot be three. **P7** adds one key. *Action: add
`booking.continue` to the §Design i18n inventory.*

**⚠ F4 — dropping the dress binding cannot drop the path segment.**
`navigate()` is `pushState`-only (`router.tsx:85-88`); there is no `replace`.
Rewriting `/book/details/{dressId}` → `/book/details` would push a second entry,
and the browser back button — which D8 makes the flow's real back affordance —
would walk straight back into the dead path, re-probe, re-drop and push again.
**Ruling: the URL keeps the dress id; the binding is dead in memory only.** The
step machine treats `dressId` as a *requested* binding and holds resolved-dead
ids in a session-lifetime `Set<string>`, so a back-navigation to the same path
renders the dropped state directly without a second 404 round trip. Declined:
adding a `replace` mode to `navigate()` — that is a router change outside D1's
six mechanical edits, with its own tests and its own popstate semantics, bought
for a cosmetic URL.

**⚠ F5 — `Input` / `TextArea` / `Select` have no `ref`, so focus-to-first-invalid
is unbuildable today.**
`ButtonProps` declares `ref?: Ref<HTMLButtonElement>` explicitly
(`Button.tsx:12`) precisely because React 19's ref-as-prop is not part of
`*HTMLAttributes`. The three field primitives do not, and `id` is `Omit`'d, so
there is **no handle to focus** — not the name input on a failed submit, not the
first radio, not the OTP field on step entry (§6's problem too). This is not in
the spec's §What `packages/ui` does not have. **Queued fix**: add
`ref?: Ref<HTMLInputElement>` / `HTMLTextAreaElement` / `HTMLSelectElement` to the
three prop interfaces and spread it — one line each, three files, no behaviour
change for existing callers. **Fallback if it does not land**: the step still
passes AT, because every error `<span>` is already `role="alert"`
(`Input.tsx:42`, `TextArea.tsx:52`) and speaks without focus; what is lost is
WCAG 2.4.3-quality focus order on failure. Focus-to-first-invalid is the
specified behaviour and the `ref` is how it is built.

**⚠ F6 — `len()` is code points, `.length` is UTF-16 code units.**
`test_frontend_constant_parity.py` pins the *number* 80 and the *number* 500; it
cannot see that Python counts code points and JavaScript counts UTF-16 units. For
Hebrew and Latin (all BMP) the two agree exactly. For astral characters — emoji,
which do appear in customer notes — one code point is two JS units, so the client
refuses at 80/500 what the server would accept. **The divergence is always
client-stricter, never client-looser, so no invalid request can reach the
server** and no fix is required for v1. Recorded so a later reader does not read
it as an oversight, and so nobody "fixes" it by loosening the client bound.

---

## 5. Screen S3 — Terms acceptance (`/book/terms` · `/book/terms/{dressId}`)

This is the screen a bride actually stops and reads — D2 put it before the OTP
for exactly that reason, so that a slow reader is not a failure mode. It is also
the only screen in the flow whose main content is a **string a boutique owner
typed**, of arbitrary length, in arbitrary shape.

§2 (the flow shell / entry) owns the **absent**-terms case — `GET /storefront/terms`
→ `404` at entry, D5, degrade to `ContactPanel` or, under D12, to plain copy.
§5 owns only the present-terms screen and its **mid-session** invalidation.

### 5.1 Mobile 375

```
+---------------------------------------------------------+
|  → [booking.backStep]                       <- §2 owns   |
|  [ stepper: 1 — 2 — (3) — 4 ]               <- §2 owns   |
|                                                          |
|  [booking.termsHeading]    (h2, --font-display, --text-xl)|
|                                                          |
|  +-- Card (paper, --space-6, radius-md, shadow-sm) -----+ |
|  |                                                      | |
|  |  [booking.refundWindow]  ...<bdi dir="ltr">48</bdi>..| |
|  |  [booking.forfeit]       ...<bdi dir="ltr">50</bdi>..| |
|  |          ^ --text-base, weight 600, ink              | |
|  |                                                      | |
|  |  ---------------------------------- hairline         | |
|  |                                                      | |
|  |  <terms_text, verbatim>                              | |
|  |  white-space: pre-line · dir="auto" ·                | |
|  |  overflow-wrap: anywhere · --text-base/1.6 · ink     | |
|  |                                                      | |
|  |  ...flows to whatever length the owner wrote.        | |
|  |  NO inner scroll box. NO expander. NO clamp.         | |
|  |                                                      | |
|  |  ---------------------------------- hairline         | |
|  |                                                      | |
|  |  [x] [booking.acceptTerms]      <- Checkbox (NEW),   | |
|  |                                    24px box, label   | |
|  |                                    row >=44px         | |
|  +------------------------------------------------------+ |
|                                                          |
|  [            booking.continue            ]  <- lg,      |
|                                                 full-width|
+---------------------------------------------------------+
```

**Order is load-bearing.** The two numbers sit **above** the prose because they
are what she is actually agreeing to and a paragraph is where numbers go to hide.
The checkbox sits **below** the prose, last, in normal flow — a consent control
that is reachable before the thing being consented to has been scrolled past is
the pattern that produces unread consent.

### 5.2 768 / 1440 deltas

| Width | Delta |
|---|---|
| **768** | Forward `Button` stops being full-width and sits at the inline-end. Nothing else changes |
| **1440** | Identical to 768. **The policy block adds no `max-inline-size` of its own** — it inherits the step column's measure (§2). Declined `max-w-prose` inside an already-narrow editorial column: double-constraining a 640px column produces a ~440px ribbon of legal text with two dead gutters, which reads as a rendering bug |

### 5.3 The policy text — RULED

**Ruling 5.3a — full flow. No scroll container, at any width.** The policy renders
as one block in the page's normal flow and the page scrolls. Reasons, in order of
weight:

1. **Two scroll contexts on a 375 phone is a trap.** A thumb that lands inside an
   inner scroller scrolls the policy instead of the page, and a thumb that lands
   outside it scrolls past the policy without ever moving it.
2. **A keyboard-scrollable container needs `tabindex="0"` + `role="region"` +
   an accessible name** to satisfy WCAG 2.1.1 — which inserts a tab stop between
   the text and the checkbox, on the one screen where the tab order should be
   read → accept → continue.
3. **WCAG 1.4.10 reflow.** A fixed block size clips at 200% zoom / 320 CSS px.
4. The assignment's own constraint — *the checkbox must not be hidden below the
   fold on 375* — is satisfied by **not** boxing the text: the checkbox simply
   follows it, and page scroll is the one gesture that always works.

Declined: `max-block-size: 40vh; overflow-block: auto` (all four reasons above).
Declined: a "read more" expander — a legal consent may never hide the thing being
consented to behind a disclosure control. Declined: a scroll-to-bottom-before-you-can-accept
gate — it breaks for anyone who reaches the checkbox by keyboard or screen reader
without generating scroll events, and it is dark-pattern-shaped rather than
consent-shaped.

**Ruling 5.3b — long text at 375 behaves by growing the page, and nothing else.**
`terms_text` is capped at `MAX_TERMS_TEXT_BYTES` (50 KB) by the console's own
validator (`apps/manage/src/validation.ts:146`) — long, but page flow handles
long. The two things that must hold at 375 are: **no horizontal scroll ever**
(`overflow-wrap: anywhere` on the policy block, because an owner can paste a
200-character URL or an unbroken string — the same reason `StorefrontLayout`'s
footer links carry `[overflow-wrap:anywhere]`), and **the checkbox and the
forward button remain the last two blocks in flow, never fixed, never sticky**.
Declined: a sticky forward button on this step. `/book` renders no fixed bar by
Risk 6, and a sticky consent button on a policy screen is precisely the affordance
that gets people to accept without reading.

**Ruling 5.3c — `white-space: pre-line`.** `terms_text` is authored in a manage
`TextArea`, so its paragraph structure is literal `\n` characters. `pre-line`
preserves those line breaks and collapses runs of spaces. Declined `pre-wrap`
(preserves leading indentation and trailing spaces the owner left behind, which in
RTL produces ragged, apparently-random indents). Declined splitting on `\n\n` into
`<p>` elements: owner-authored text uses single newlines as often as double, so a
splitter guesses at structure and gets it wrong for half of tenants.

**Ruling 5.3d — rendered as TEXT, never as HTML. This is a hard rule.**
`{termsText}` as a React text child. **No `dangerouslySetInnerHTML`, no markdown
renderer, no sanitiser-then-inject.** React escapes by construction. The boutique
owner is a semi-trusted author, but this is a public, anonymous, multi-tenant
surface: any HTML path here is a stored-XSS vector reachable by every visitor to
that tenant's storefront. The backend already treats it this way
(`booking/validation.py`: "rendered as text there, never HTML").

**Ruling 5.3e — `dir="auto"` on the policy block.** The page is `dir="rtl"` and
the policy is Hebrew, but owners paste English clauses. `dir="auto"` sets the
block's base direction from its first strong character, which is right far more
often than a hard `rtl` and costs nothing. Same treatment `manage-catalog.md`
§10.3 gives every field where Hebrew and Latin both occur.

**Ruling 5.3f — the two numbers are plain paragraphs, not a callout box.**
`booking.refundWindow` and `booking.forfeit`, one `<p>` each, `--text-base`,
weight **600**, `var(--color-ink)`, with `refundable_until_hours_before` and
`forfeit_percent` each wrapped in `<bdi dir="ltr">`. Separated from the prose by a
`1px solid var(--color-border)` hairline and `var(--space-4)`. **The distinction
from the policy body is carried by weight and a divider, not by fill or hue.**
Declined a tinted callout: a block whose job is to read as a distinct block needs
a ≥3:1 boundary (`manage-catalog.md` §10.1 — white-on-paper is 1.13:1 and a
`--color-border` hairline is 1.22:1), so a box here would cost a
`--color-border-input` frame and would read as an *alert*, which two neutral
facts are not.
**Edge values are legal and must render:** `validateTerms` permits
`refundable_until_hours_before = 0` and `forfeit_percent` anywhere in 0–100. "0
hours" and "0%" and "100%" all render as ordinary numbers; there is no special
case and no hidden row. Copy constraint: both strings must read correctly with a
`0` substituted.

### 5.4 `Checkbox` — the one genuinely new `packages/ui` primitive

`Toggle` is a native `<input type="checkbox">` but hardcodes `role="switch"` on
line 22 with a **closed prop list, no rest-spread and no `ref`** — nothing can
opt out. A switch announces on/off and models a setting that takes effect
immediately; a one-shot legal consent announces checked/unchecked and is the
canonical checkbox. The spec already names this gap
("a checkbox-role primitive is genuinely absent").

**`packages/ui/src/components/Checkbox.tsx`**

```ts
export interface CheckboxProps {
  label: string;
  description?: string;
  error?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  ref?: Ref<HTMLInputElement>;   // Button.tsx:12 is the precedent
}
```

Closed prop list, matching `Toggle`'s shape exactly so the two read as siblings —
plus `error` (the house error contract) and `ref` (⚠ F5; this control is a focus
destination). Declined extending `InputHTMLAttributes`: `Toggle` does not, and a
consent control has no legitimate use for arbitrary passthrough.

| Element | Spec |
|---|---|
| Row | `<label htmlFor>` **wraps the box and the label text together** and carries `min-block-size: 44px`, `padding-block: var(--space-2)`, `display:flex; align-items:flex-start; gap: var(--space-3)`, `cursor: pointer`. **The whole row is the hit target** — `manage-catalog.md` §3.4's "Toggle row geometry" ruling verbatim (usage law 7). Label text wraps freely; the row grows |
| Box | Real, visible `<input type="checkbox">` — **not** visually hidden. `inline-size: 24px; block-size: 24px` (`Toggle`'s shipped `size-5` = 20px misses the bar and is queued below), `flex-shrink: 0`, `border: 1px solid var(--color-border-input)` (**4.18:1** on white, **3.69:1** on paper), `border-radius: var(--radius-sm)` (4px — a checkbox is an input, never a pill), `background: var(--color-surface-raised)`, `accent-color: var(--color-gold-strong)`. Declined a visually-hidden input with a CSS-drawn box: `accent-color` is the house pattern already shipped in `Toggle`, and it keeps the UA checkmark, the indeterminate rendering and Windows High Contrast for free |
| Checked | UA-painted white checkmark on the `accent-color` fill: white on `--color-gold-strong` = **3.93:1** ✓ (≥3:1 for a non-text graphical object; WCAG 2.0 AA — the IS 5568 floor — has no non-text SC at all, so this clears our own stricter bar). The checked box's outer boundary against the white Card interior is the same **3.93:1** pair |
| Label | `--text-base`, `var(--color-ink)` (**13.89:1** on paper), inside the `<label>` so it is the accessible name |
| Description (optional; unused on this screen) | **Outside** the `<label>`, tied by `aria-describedby`, `--text-sm`, `var(--color-ink-muted)`, offset `padding-inline-start: calc(24px + var(--space-3))` to align under the label. `manage-catalog.md` §3.4 — folding a description into the accessible name is how a 40-word name happens |
| Error | `<span id role="alert" className="text-sm text-danger">` **below the row**, byte-identical to `Input.tsx:41-45`. Input carries `aria-invalid="true"` and `aria-describedby` pointing at it; the box gains `border-color: var(--color-danger)` (**6.18:1** on paper) — colour **plus** message, never colour alone |
| Focus | `focusRing` on the `<input>` itself: `outline: 2px solid var(--color-focus); outline-offset: 2px` (**5.08:1** on paper). `outline` + `outline-offset` and nothing else |
| Disabled | Not used on this screen. If ever used, the reason goes on the **visible label**, not on `aria-describedby` — a `disabled` control is out of the tab order and the reference is inert (`manage-catalog.md` §10.3) |

### 5.5 Component notes — exact tokens (screen-level)

| Element | Spec |
|---|---|
| Step heading | `SectionHeading as="h2"`, no ornament, `booking.termsHeading`. Same row as §4.6 — including the "if §2 rules it the `h1`" clause |
| Card | Identical to §4.6: shipped `Card`, `--color-surface`, `--radius-md`, `--shadow-sm`, `padding: var(--space-6)` at every width |
| Numbers block | Two `<p>`, `--text-base`/600, `var(--color-ink)`; numeric runs `<bdi dir="ltr">`. §5.3f |
| Policy block | `<div>` (not `<p>` — `pre-line` content contains its own paragraphing): `white-space: pre-line`, `dir="auto"`, `overflow-wrap: anywhere`, `--text-base` (which carries the theme's 1.6 line-height — **never add a `leading-` utility, it overrides the token**, `AboutPage.tsx:63`), `var(--color-ink)`, `max-inline-size` inherited from the step column. §5.3a–e |
| Consent | `Checkbox` (§5.4), `label={t("booking.acceptTerms")}`, `error={acceptError}` |
| Hairlines | `1px solid var(--color-border)`, `margin-block: var(--space-4)`. Decorative (1.22:1), never a load-bearing boundary |
| Forward button | Identical to §4.6's row — `Button primary lg`, `booking.continue` (**P7**), `fullWidthMobile`, `--color-gold` background + `--color-ink` text (**6.41:1**). Navigates to `/book/verify[/{dressId}]` |
| `TERMS_STALE` alert | `<p role="alert">`, `--text-base`, `var(--color-warning-text)` (**5.70:1** on cream, **5.20:1** on paper), rendered **above** the `h2` so it is the first thing in the content region. §5.6 |
| Motion | None specific to this screen. The `TERMS_STALE` skeleton inherits the shared 1.5s pulse (static under reduced motion) and the step transition inherits the shared page fade + 8px rise |

**No summary of her appointment appears on this screen, or on §4's.**
*(PROPOSED — user confirms at the gate.)* The cancellation policy is
version-scoped, not appointment-scoped, and the back `<Link>` is one tap from the
real picked slot. A restated "your appointment: Tuesday 14:00" is a second source
of truth that can drift from the one held in memory, and the confirmation screen
(§7) is where D6 makes the appointment state itself in full. Declined: a
persistent appointment summary rail across the steps.

### 5.6 States

| State | What she sees | Trigger |
|---|---|---|
| **Default** | Numbers, hairline, policy, hairline, unchecked consent, forward button | terms present in the payload §2 fetched at entry |
| **Loading** | **Does not normally occur.** The terms payload is fetched **once at flow entry by §2** and held; this step issues no fetch of its own. Declined re-fetching on step entry: it narrows but cannot close the staleness window (she can still read for three minutes), so it buys nothing and adds a loading state and a failure mode to the one screen that must simply be readable. `TERMS_STALE` is the designed recovery for staleness, not a bug to pre-empt | — |
| **Acceptance missing** | `booking.acceptRequired` renders as the `Checkbox`'s `error` — `--text-sm`, `var(--color-danger)` (**6.18:1** on paper), `role="alert"`, `aria-describedby`-tied, box border `--color-danger`, `aria-invalid="true"`. **Focus moves to the checkbox.** No navigation, no request. The forward button stays enabled throughout (§4.4d — a disabled forward button on a legal-consent screen states no reason and cannot be focused to explain itself) | forward pressed unchecked |
| **`TERMS_STALE` return — refetching** | She arrives here **from the submit** (§6). `errors.termsStale` renders immediately in a `role="alert"` above the `h2`, `var(--color-warning-text)` — cautionary, not danger: nothing failed and nothing is her fault, the boutique republished its policy. **The whole step body below the heading is replaced by `Skeleton variant="text" lines={10}`** while `GET /storefront/terms` re-fetches. Declined leaving the old numbers on screen next to a skeleton: showing superseded figures beside a "the policy changed" alert is the one arrangement guaranteed to mislead | `409 TERMS_STALE` on submit |
| **`TERMS_STALE` return — resolved** | The **new** `terms_text` and the **new** numbers render. **The checkbox resets to unchecked, unconditionally** — her acceptance was of a different version, and carrying it forward would record consent to text she never saw, which is the entire reason `terms_version` is in the payload. The held `terms_version` is replaced by the newly-fetched one. **§5 adds no focus move**: this arrived by navigation (`/book/verify/…` → `/book/terms/…`), so `router.tsx:196-211` has already scroll-reset and focused `<main>`; the `role="alert"` is what speaks, and it is a genuine insertion because `BookPage` is reconciled rather than remounted across `/book/*` steps | refetch resolves 200 |
| **`TERMS_STALE` return — refetch 404** | The boutique deleted its policy outright mid-session. F13 cannot accept a booking without a terms version, so **the flow cannot complete**: this step adopts **§2's D5 degrade shape** (`booking.noTermsByPhone` over `ContactPanel`, or plain copy when `useBoutique()` has nothing — D12), and the forward button and the consent checkbox do not render. This is not a new state: it is the same §State-matrix row ("No published terms → phone-only entry"), reached from a second trigger point | refetch → `404 NOT_FOUND` |
| **`TERMS_STALE` return — refetch failed (5xx / network)** | The storefront's error voice, not a toast: one `<p role="alert">`, `--text-base`, `var(--color-ink-muted)` (**5.61:1** on paper) via `errorMessageOr(error, t, …)`, plus a `Button variant="secondary"` retry calling the same fetch. Ink-muted, not danger — *"a backend that is down is not the boutique's fault"* (`CatalogPage.tsx:181-182`). **One alert, never two** (`CatalogPage.tsx:167-171`): the `errors.termsStale` line is replaced by this one, not stacked above it | refetch fails |
| **Long policy at 375** | The page grows; the Card grows with it; the checkbox and forward button sit at the bottom of the flow and are reached by ordinary page scroll. No inner scroller, no clip, no horizontal scroll (`overflow-wrap: anywhere`). §5.3a–b | any `terms_text` length up to 50 KB |
| **Forward pressed, checked** | `navigate()` to `/book/verify[/{dressId}]`, carrying the accepted `terms_version` in memory. This step issues no request on forward | — |

### 5.7 ⚠ FINDINGS (§5)

**⚠ F7 — `Toggle`'s shipped geometry already fails usage law 7, and `Checkbox`
must not copy it.**
`Toggle.tsx:18` is `<label className="flex items-start gap-3">` with **no
`min-block-size`**, and line 28's box is `size-5` = **20px**. A 20px box beside a
`--text-base` line is roughly a 26px row — under the 44px floor, on the console's
`price_visible` and `reserved` controls. `manage-catalog.md` §3.4 already ruled
the correct geometry (label wraps box + title, `min-block-size: 44px`, box
24×24) and §10.3 lists it as checked; **the shipped component does not implement
it**. Not F14's screen and not F14's fix — but `Checkbox` is being written
alongside it and must ship the ruled geometry, and the divergence is queued below
so the two primitives do not sit next to each other disagreeing about the touch
floor.

**⚠ F8 — two field errors can announce simultaneously, and the storefront
cannot opt out.**
`Input` and `TextArea` hardcode `role="alert"` on their error span. On §4's
details step, `name` and `size` can fail on the same press, producing two
assertive announcements. **Accepted as-is.** The form has at most two
co-failing controls, both messages are one short line, and the alternative — a
form-level error summary — is listed in the spec's §What `packages/ui` does not
have and would be a new primitive built for a two-field form. Recorded as the
escalation path if this flow ever grows a third required field. §5's terms step
has exactly one validatable control and can never fire two.

### 5.8 Contrast rows contributed to the document's §10.1 ledger

Every pair §4 and §5 rely on, computed against **the surface the pair actually
renders on**. Method validated by reproducing `tokens.md`'s published figures:
`--color-gold-strong #9E7B36` on `--color-bg #FDFBF7` recomputes to **3.80:1**
and on `--color-surface #F6F0E6` to **3.47:1**, matching `tokens.md` and
`manage-catalog.md` §10.1 exactly.

| Element | Foreground | Background | Ratio | Note |
|---|---|---|---|---|
| Step headings, field labels, chip size labels, policy text, consent label, bound-dress name | `--color-ink` | `--color-surface` (paper) | **13.89:1** | matches tokens.md |
| Forward button ("booking.continue") | `--color-ink` | `--color-gold` | **6.41:1** | gold as *background* only — usage law 1 |
| Notes help text, char counter, `booking.sizeUnavailable` chip line | `--color-ink-muted` | `--color-surface-raised` (the field / chip's own white fill) | **6.36:1** | |
| Same on paper (help text inside the Card, terms refetch-error line) | `--color-ink-muted` | `--color-surface` | **5.61:1** | matches tokens.md |
| Inline field errors (`nameRequired`, `nameTooLong`, `notesTooLong`, `sizeRequired`, `acceptRequired`) | `--color-danger` | `--color-surface` | **6.18:1** | matches tokens.md |
| `sizeGoneRepick`, `dressGoneGeneric`, `errors.termsStale` | `--color-warning-text` | `--color-surface` | **5.20:1** | cautionary register, never danger — nothing she did failed |
| `errors.termsStale` where it renders above the Card, on the page | `--color-warning-text` | `--color-bg` (cream) | **5.70:1** | matches tokens.md |
| Input / textarea / chip / checkbox borders (non-text) | `--color-border-input` `#8A7A5E` | `--color-surface-raised` / `--color-surface` | **4.18 / 3.69** ✓ | the corrected token, shipped in `theme.css:31` |
| Selected size chip border (non-text) | `--color-gold-strong` | `--color-surface` (paper Card, outside) / `--color-surface-raised` (chip fill, inside) | **3.47 / 3.93** ✓ | selection is **also** a border-*width* and font-*weight* change — never hue alone |
| **Checked-checkbox mark (non-text graphic)** ‡ | UA white checkmark | `--color-gold-strong` (`accent-color` fill) | **3.93:1** ✓ | **new pair, computed here.** Same numbers as gold-strong-on-white, inverted. WCAG 2.0 AA has no non-text SC; this clears our own ≥3:1 bar |
| Focus ring (2px, 2px offset, non-text) | `--color-focus` | `--color-surface` / `--color-surface-raised` / `--color-bg` | **5.08 / 5.76 / 5.57** ✓ | |
| Card hairlines, binding divider, policy divider | `--color-border` | — | 1.22 on paper — decorative | **never a load-bearing boundary**; where a block's edge must be perceivable the fill changes instead (§5.3f declines to need one) |

**Never used in §4 or §5**: raw `--color-gold` on text (2.38:1 — usage law 1);
`--color-gold-strong` on any text (its only two uses are the selected-chip border
and the checkbox `accent-color` fill, both non-text); `opacity` as a way to recess
text (`manage-catalog.md` §3.3); any colour not in `tokens.md`; any promo or
sale register whatsoever (usage law 9 — there are no badges, no urgency, no
countdowns and no scarcity language on either screen, and D4's unavailable size
is specifically designed **not** to borrow one).

### 5.9 Queued — must land before or with the F14 build

Numbered against this document's §Open items; the assembler should merge these
into that section.

1. **`components.md` needs a `Checkbox` row.** Core primitives table, beside
   `Toggle`:
   `| `Checkbox` | one-shot consent (terms acceptance) — native `<input type="checkbox">`, **role NOT overridden** (`Toggle` hardcodes `role="switch"` and is the wrong semantic for consent); label + optional description; `<label>` wraps box + label and carries `min-block-size: 44px`, box 24×24, `accent-color: var(--color-gold-strong)` (white mark **3.93:1** ✓) | error (message `role="alert"`, tied via `aria-describedby`), disabled |`
   **Gate condition: this row must land in `components.md` before or with the
   F14 build that consumes this document** — the same shape and the same
   reasoning as `manage-catalog.md` §12 item 7, which queued the `Badge`
   `muted`/`warning` variants and has since landed (`components.md:16`). A build
   that reads `components.md` as the component contract would otherwise find a
   primitive it is told to render and no definition for it.
2. **`ref` on `Input` / `TextArea` / `Select`** (⚠ F5). Add
   `ref?: Ref<HTMLInputElement>` / `HTMLTextAreaElement` / `HTMLSelectElement`
   to the three prop interfaces and spread it — one line each, three files,
   mirroring `Button.tsx:12`. No behaviour change for existing callers. Without
   it, focus-to-first-invalid-field is unbuildable on §4 and the OTP field's
   entry focus is unbuildable on §6. Same PR as item 1.
3. **`Toggle` geometry correction** (⚠ F7) — box 20px → 24px, `<label>` gains
   `min-block-size: 44px`. `manage-catalog.md` §3.4 already ruled this and §10.3
   already claims it; the shipped component does not implement it. **Not an F14
   blocker** (no `Toggle` appears in the booking flow), but it should ride the
   same PR as item 1 so the two sibling primitives do not disagree about the
   touch floor in the same file.
4. **`qa-checklist.md:141` needs a fourth CTA family.** It enumerates
   catalog / detail / `/about` and asserts "exactly one instance visible at each
   width". F14 adds **`/book/*` — no `BookingCTA` bar at any width, forward
   button in normal flow, `A11yMenu` at `var(--space-4)` and not
   `var(--space-a11y-clearance)`**. Same amendment shape as `manage-catalog.md`
   §12 item 4. *(§2 may already be queuing this; if so, merge, do not duplicate.)*
5. **Spec §State matrix needs one row** (⚠ F2): "Bound dress has no active sizes
   → binding drops, generic booking · D · unit". The design is in §4.5e; only the
   matrix row is missing, and that table is the single source the test suites
   read.
6. **Spec §The contract F14 consumes** should record `dress_id` + `dress_size` as
   a **paired** unit rather than two independent optionals (⚠ F1). One
   table-cell edit; no decision reopens.
7. **§Design i18n inventory gains two keys** — `booking.continue` (**P7**, ⚠ F3)
   and `booking.sizeRequired` (**P8**, ⚠ F1). Both are ordinary `booking.*` keys
   and `i18n-keys.test.ts` picks them up automatically.

### 5.10 PROPOSED decisions in §4 and §5 (user confirms at the gate)

| # | Proposal | Where |
|---|---|---|
| **P2** (confirmed here) | **The size chips live on the details step**, not the slot step. Ruled and designed: D11 already gave the slot step the appointment-type picker, and a third picker there would put *what service*, *when*, and *which size* on one 375 screen. Size is an attribute of the booking's subject, which is what S2 collects | §4.2, §4.5 |
| **P7** | **One new i18n key `booking.continue`**, used as the forward-button label on `slot`, `details` and `terms`. `booking.submit` / `booking.submitting` stay on `verify` only | ⚠ F3, §4.6, §5.5 |
| **P8** | **One new i18n key `booking.sizeRequired`** — the inline error when the item-based path is submitted with no size chosen. Forced by the backend's paired-field rule | ⚠ F1, §4.5c, §4.7 |
| **P9** | **Copy constraint: `booking.sizeUnavailable` is a phrase of ≤ 24 characters**, not a sentence — it renders inside every unavailable chip | §4.5b |
| **P10** | **Copy constraint: `booking.dressGoneGeneric` is written cause-agnostic** — it serves three triggers (404 at the size fetch, 404 from the submit probe, and a dress with zero active sizes) and must be true in all three | ⚠ F2, §4.7 |
| **P11** | **No appointment summary on S2 or S3.** The back `<Link>` is one tap from the real picked slot; §7's confirmation is where D6 makes the appointment state itself in full | §5.5 |
| **P12** | **The bound-dress name is not a link.** Leaving the flow discards the in-memory draft, and `localStorage` is banned (`qa-greps.sh:33`), so there is no draft to come back to | §4.6 |
## 6. Screen S4 — phone verification (`/book/verify`, `/book/verify/{dressId}`)

Wireframes below follow the **reading-the-wireframes** note in the document preamble: ASCII is drawn in **logical** order (inline-**start** on the left of the drawing), and on screen everything mirrors — inline-start is the **right** edge. Every rule is written in logical properties.

This screen is the fourth and last step of the stepper (D2 order; the stepper chrome, the `booking.backStep` control and the flow's content column are specified once in §2 and are not respecified here). It carries **two** POSTs — `/storefront/otp/send` and `/storefront/otp/verify` — and then the one that writes the booking, `POST /storefront/bookings`. Everything the earlier steps collected is submitted from here.

### 6.1 The ruling — one screen that grows, not two sub-screens

**RULED: `verify` is a single route with two sub-states rendered as one growing form. The code field is *appended* below the phone field; the phone field never leaves the DOM.**

| Declined | Why |
|---|---|
| A **swap** (phone form replaced by code form) | The single most common OTP failure is a mistyped number, and it is a failure the bride can *see* only if the number is still on screen. A swap forces her to un-swap, or worse, to spend one of five hourly sends discovering the typo. It also destroys the node focus is on at exactly the moment focus matters most (§6.11) |
| Two step slugs, `/book/verify/phone` + `/book/verify/code` | D8 fixed `step` as a **closed set of five**, and the dress rides in the segment after the step (D9). A sixth slug reopens a locked decision and collides with `/book/verify/{dressId}` — `verify/code` and `verify/{dressId}` are the same shape |
| Holding the sub-state in the URL query | D9's evidence: the hand-rolled navigation store snapshots `pathname` only |

The sub-state is therefore **derived, not stored**: the code field renders iff `codeSentFor === normalizePhone(phoneField)`. One comparison, no extra state, and it produces the correct behaviour for free — **editing the phone number after a send collapses the code field and clears the entered code**, because a code minted for number A cannot verify number B and submitting it would spend a verify budget to learn nothing.

**No recap block on S4.** The i18n inventory carries no key for one, and the flow's full statement of the appointment is S5's whole job (§7). Declined: a slot/type summary above the form — new UI with no string behind it.

### 6.2 Mobile 375 — sub-state A (phone)

```
+--------------------------------------------------------------+
| ->  booking.backStep                    (Link -> /book/terms) |
|                                                               |
| booking.stepsLabel   [stepper, 4 of 4 — §2 owns it]           |
|                                                               |
| booking.stepOtp                     (h1, display, --text-2xl) |
| ~~~~~~ gold hairline ~~~~~~         (aria-hidden ornament)    |
|                                                               |
| +-- Card (paper, --space-4 @375, radius-md, shadow-sm) ------+ |
| |  booking.phone                  (visible <label>, 600)     | |
| |  booking.phoneHint              (help -> aria-describedby) | |
| |  +-------------------------------------------------------+ | |
| |  |050-1234567                                            | | | <- dir="ltr" island.
| |  +-------------------------------------------------------+ | |    Caret + value sit
| |                                                            | |    at the PHYSICAL
| |  [[[[   booking.otpResend   ]]]]  (Button primary, lg,     | |    LEFT of the box;
| |                                    fullWidthMobile)        | |    label stays RTL
| +------------------------------------------------------------+ |
|                                                               |
| (page owns its own padding-block-end — the shell reserves     |
|  none for /book; A11yMenu sits at --space-4. §2 / §8)         |
+--------------------------------------------------------------+
```

### 6.3 Mobile 375 — sub-state B (code sent)

```
+--------------------------------------------------------------+
| ->  booking.backStep                                          |
| booking.stepsLabel   [stepper]                                |
| booking.stepOtp                     (h1 — unchanged)          |
| ~~~~~~ gold hairline ~~~~~~                                   |
|                                                               |
| +-- Card -----------------------------------------------------+
| |  booking.phone                                             | |
| |  booking.phoneHint                                         | |
| |  +-------------------------------------------------------+ | |
| |  |050-1234567                                            | | |
| |  +-------------------------------------------------------+ | |
| |                                                            | |
| |  ---------------------------------- hairline (--color-border)|
| |                                                            | |
| |  booking.otpCode                (visible <label>, 600)     | |
| |  booking.otpSent                (help -> aria-describedby) | |
| |  +--------------------+                                    | |
| |  |123456              |     <- dir="ltr", ONE field,       | |
| |  +--------------------+        max-inline-size: 10ch       | |
| |                                                            | |
| |  [[[[   booking.submit   ]]]]     (Button primary, lg)     | |
| |  [    booking.otpResend    ]      (Button secondary, md)   | |
| +------------------------------------------------------------+ |
+--------------------------------------------------------------+
```

Cooldown variant of the last control, drawn once because it is the row usage law 9 is watching:

```
| |  [  booking.otpResendWait  ]   (Button secondary, disabled;  |
| |                                 no number, no bar, no tick)  |
```

**One primary per sub-state.** In A the forward action *is* the send, so the send button is `primary`. In B the forward action is the submit, so the same control demotes to `secondary` — its role genuinely changed from "the way forward" to "a remedy".

### 6.4 Desktop 768 / 1440 — deltas only

Nothing about this screen is width-dependent beyond the flow's shared column (§2). Three deltas:

| Width | Delta |
|---|---|
| **375** | Card padding `--space-4`; both buttons `fullWidthMobile` (`w-full sm:w-auto`, `Button.tsx:64`) |
| **768** | Card padding `--space-6`; buttons shrink to intrinsic width and sit in a `flex` row with `gap: var(--space-3)`, submit at inline-start of the pair (it is the primary, and inline-start is the first thing read) |
| **1440** | Identical to 768. The column does not widen — a form column that grows past ~640px puts the label and its field on opposite sides of the eye's travel |

**No `BookingCTA` bar at any width** (spec Risk 6): `hasBookingBar` is `catalog || dress` and `/book` falls through to `false` silently. This screen's submit is an ordinary in-flow `Button`, never `BookingCTAButton`.

### 6.5 Component notes — exact tokens

| Element | Spec |
|---|---|
| `h1` `booking.stepOtp` | `font-family: var(--font-display)`, `--text-2xl` (1.75rem/1.25), `color: var(--color-ink)` (**15.24:1** on cream ✓). Matches `DressPage`'s page-subject `h1`, not `BoutiqueHeader`'s `--text-3xl` — the page's subject is a step, not the boutique. **Exactly one `h1`, carried by every state below including the dead ends** (storefront heading law: the `h1` is where the Router's focus move lands, so a state that drops it drops a screen-reader user into an untitled region) |
| Gold hairline under the `h1` | `<span aria-hidden="true">`, `block-size: 1px`, `inline-size: var(--space-12)` (48px — the shipped `SectionHeading ornament` geometry, `h-px w-12 bg-gold`), `background: var(--color-gold)`. The storefront's one decorative motif. Decorative gold is exempt from the text bar (usage law 1) |
| Card | `background: var(--color-surface)` (paper), `border-radius: var(--radius-md)`, `box-shadow: var(--shadow-sm)`, `padding: var(--space-6)` (`var(--space-4)` @375). **No hard border** — matting + shadow only |
| Divider between the two fields | `border-block-start: 1px solid var(--color-border)`, `margin-block: var(--space-4)`. Decorative (1.22:1) and never the only thing delimiting a region — the two visible `<label>`s do that |
| Phone field | `Input` with `label={t("booking.phone")}` `help={t("booking.phoneHint")}` `type="tel"` `dir="ltr"` `inputMode="tel"` `autoComplete="tel"` `error={…}`. **No `placeholder` at all** (usage law 3 — and a Hebrew placeholder inside an `ltr` input anchors to the physical left and reads backwards). Border `1px solid var(--color-border-input)` at the shipped `#8A7A5E` (**3.69:1** on paper ✓), `border-radius: var(--radius-sm)`, `background: var(--color-surface-raised)`, `padding-inline: var(--space-3)`, `padding-block: var(--space-2)`, `--text-base`, `color: var(--color-ink)` (**15.75:1** ✓). Focus: `border-color: var(--color-gold-strong)` + the global 2px `var(--color-focus)` ring at 2px offset |
| Code field | `Input` with `label={t("booking.otpCode")}` `help={t("booking.otpSent")}` `dir="ltr"` `inputMode="numeric"` `autoComplete="one-time-code"` `maxLength={6}` `pattern="[0-9]*"`. `max-inline-size: 10ch` — wide enough for six digits at 200% text, narrow enough that it does not read as a free-text field. Same border/fill/focus tokens as the phone field |
| Send / resend button | `Button variant="primary"` in sub-state A, `variant="secondary"` in B, `size="md"`, `min-block-size: 44px` from `sizes.md` (`min-h-11`). Disabled during cooldown and during either POST. Its **visible label carries its own reason when disabled** (§6.7) |
| Submit button | `Button variant="primary" size="lg"` — `background: var(--color-gold)` + `color: var(--color-ink)` (**6.41:1** ✓, and the only legal way gold touches this button: gold as *background*, ink as text — usage law 1). `border-radius: var(--radius-md)`, `min-block-size: 48px` (`min-h-12`), `font-weight: 700`. `loading` while the booking POST is in flight |
| Field-level error | the `Input` primitive's own: `<span role="alert" id="…-error" class="text-sm text-danger">`, wired to `aria-invalid` + `aria-describedby` by construction (`Input.tsx:31-45`). `--color-danger` on `--color-surface` = **6.18:1** ✓ |
| Step-level alert block | `<p role="alert">`, `--text-base`, **`color: var(--color-ink-muted)`** on cream (**6.15:1** ✓) — the shipped storefront error voice (`CatalogPage.tsx:181-182`: *"a backend that is down is not the boutique's fault"*). Sits above the Card, `margin-block-end: var(--space-4)` |
| Dead-end block | `<div tabIndex={-1}>` (focus destination — §6.11), `--text-base`, `var(--color-ink-muted)`, followed by `ContactPanel` at `margin-block-start: var(--space-4)`. **No `role="alert"`**: it is reached *by* a focus move, and the house rule reserves the assertive region for errors that appear without one |
| `ContactPanel` links | `--text-base`, `var(--color-gold-text)` on cream (**5.57:1** ✓), **always underlined**, `gap: var(--space-3)` between rows, 44px hit area |

**Colour split, ruled.** Field-level errors are `--color-danger`; step-level and dead-end messages are `--color-ink-muted`. The split is not cosmetic: `--color-danger` says *you typed something wrong*, and the phone field is the only thing on this screen she can type wrong. A token that expired, a carrier that lost an SMS and a spent send budget are none of them her mistake, and the storefront has an established muted voice for exactly that. Declined: danger for everything (turns an outage into an accusation), muted for everything (an invalid phone then whispers).

### 6.6 The two LTR islands — ruled

Both fields are LTR islands by the **price-field precedent** (`manage-catalog.md` §3.4) and the shipped `ProfileSection.tsx:115-119` phone input:

- **`dir="ltr"` goes on the `<input>` only**, passed through `Input`'s `...rest` spread (`Input.tsx:30`). The primitive's wrapper (`flex flex-col gap-1`) and its `<label>` stay in the RTL flow, so **the label sits at the inline-start (physical right) edge while the value runs left-to-right at the physical left edge of the box**. That asymmetry is correct and is what every Israeli phone field does.
- **`text-align` is left unset** so it inherits `start` *within the input's own `ltr` direction* — i.e. the caret rests at the physical left of the empty box and the value grows rightwards. Setting `text-align: end` would park the caret against the label and make deletion read backwards.
- **The box keeps its RTL position in the form flow.** Only its content direction flips. `text-align: left` is a review defect and `qa-greps.sh:40` greps for it.
- **No `placeholder`.** The format guidance is `booking.phoneHint`, which `Input` already renders as a `--text-xs` `--color-ink-muted` node **and** joins into `aria-describedby` (`Input.tsx:14-16`). Free, correct, and it survives the field being filled.

⚠ **Do not pass `aria-describedby` at the call site.** `Input` spreads `...rest` at line 29 and then writes its own `aria-describedby` at line 32 — a caller-supplied value is silently overwritten. Any extra description must go through `help`.

**Code field input filtering.** On every `change`, `value.replace(/\D/g, "").slice(0, 6)`. Digits-only makes a short submit a deliberate act rather than a stray space, and it is two lines instead of a validator.

### 6.7 The code field is ONE field — segmented six-box widget ruled OUT

**RULED: a single `<input maxLength={6}>`. No six-box widget, at any width.**

| Reason | Detail |
|---|---|
| **A11y liability** | Six inputs are six tab stops, six labels and six `aria-describedby` targets; AT reads "edit, 1 of 6" six times for one six-digit value. Only one of them can legally carry `label={t("booking.otpCode")}`, so the other five need invented per-box names that say nothing a bride wants to hear |
| **Paste** | The realistic input path is *paste from the SMS notification*. A six-box widget needs bespoke split-on-paste logic; Safari fires `paste` on the focused box only, so five of six digits vanish |
| **iOS/Android autofill** | `autocomplete="one-time-code"` fills a **single** field. Against split fields several browsers drop the whole code into box 1 and stop |
| **Focus** | It requires programmatic focus-forwarding on every keystroke — i.e. focus stolen mid-typing on six occasions, which is the exact thing §6.11 forbids |
| **House** | The spec never asks for one. It is product-y ornament, and `packages/ui` would have to grow a primitive that exists to be worse than an `<input>` |

Declined alternative considered and rejected: one field with a visual six-cell mask via `letter-spacing` + a background image. Tracking is banned outright by `tokens.md` ("Letter-spacing: 0 for Hebrew"), and the digits here sit inside a Hebrew document.

### 6.8 `booking.otpSent` — where it lives, and what it may not claim

**RULED: `booking.otpSent` is the code field's `help` prop.** It renders under the code label at `--text-xs` / `var(--color-ink-muted)` and is joined into the field's `aria-describedby`, so it is spoken exactly when focus arrives at the field it describes (§6.11 sends focus there). Declined: a separate `<p role="status">` — focus is already moving to the described field, so a live region double-announces the same fact.

**Copy constraint, binding on §11's Hebrew.** `POST /storefront/otp/send` **always answers 204** and deliberately reveals nothing — not whether the number exists, not whether an SMS was accepted by the carrier, not whether one is even configured beyond the 503 case. So `booking.otpSent` may **not** be written as a delivery claim:

- ✗ "שלחנו לך קוד" / "הקוד נשלח" — a completed-delivery claim the endpoint cannot support.
- ✓ conditional-arrival shape: *if the number is right, a code is on its way; it is valid for a few minutes.*
- It **may** state the code's own life span in words (see the finding in §6.13 on `OTP_TTL_SECONDS = 300`), because that is a real constraint she is about to hit.

### 6.9 Resend and cooldown — 60 s, and no ticking number

**RULED (confirms gate proposal P3): the resend cooldown is a fixed 60 seconds, starting at each successful `/otp/send`. No escalation.**

| Declined | Why |
|---|---|
| 30 s | Inside the p95 of Israeli SMS delivery. A resend that early is not a remedy, it is an impatience valve that spends one of five hourly sends on an SMS that was already arriving |
| 120 s or more | Eats 40 % of the code's own 300-second life before a remedy is even offered, and is past the point a bride on an Instagram detour stays on the page |
| Escalating backoff (60 → 120 → 300) | Duplicates a server budget in the client and adds state. A bride who genuinely has not received three SMS is not helped by waiting five minutes; the honest exit is the 429 state in §6.12, and that state already exists |

60 s is the number that fits both clocks: it is past the delivery p95, and four resends still fit inside one code's 300-second TTL.

**RULED: the cooldown renders NO seconds.** The disabled resend button's own visible label becomes `booking.otpResendWait` — a fixed sentence with **no `{{seconds}}` placeholder** — and reverts to `booking.otpResend` when the 60 s elapse.

This is not squeamishness about usage law 9's countdown ban; a functional cooldown is not urgency marketing and would be permissible if styled calmly. It is that a rendered number costs four things and buys one:

1. It must be a `<bdi dir="ltr">` numeric run inside Hebrew, and i18next interpolation cannot carry markup — so the string has to be split at the call site, which pins Hebrew word order in TSX.
2. It repaints once a second forever.
3. It creates the live-region problem below for no discrete event.
4. It is the one element on this flow a reviewer would read as a countdown, and usage law 9 is the storefront's single clearest de-luxury guard.

What it buys is the reassurance that time is passing — which a disabled button with a sentence already gives.

**Calm styling, explicit.** `Button variant="secondary"` disabled: `border: 1px solid var(--color-ink)`, `background: transparent`, `color: var(--color-ink)`, plus the primitive's `disabled:opacity-60` and `disabled:cursor-not-allowed` (`Button.tsx:20`). Disabled controls are exempt from WCAG 1.4.3, so the opacity is legal here — and it is the *control* that recesses, never a heading or a hint (the "no opacity on text" rule). **No progress bar. No `--color-warning-text`. No colour change of any kind. No transition or keyframe**, so there is nothing for `prefers-reduced-motion` to switch off — the button simply enables.

**Announcement to AT — ruled.** The house rule applies verbatim: *a continuously-changing value is never itself a live region.* There is no continuously-changing value here, which leaves exactly one discrete event — **the button becoming available** — and it gets exactly one announcement:

- The resend button is **not** `aria-live`, **not** `role="status"`, **not** `role="timer"`.
- A `VisuallyHidden role="status"` sibling of the button emits `booking.otpResend` **once**, on the transition from disabled to enabled. Nothing announces on entry into the cooldown, because entry is a direct consequence of a button the user just pressed.
- The label change alone is insufficient: `disabled` removes the button from the tab order, so no AT is parked on it to notice — which is also why the tick-free label carries no interruption risk.

**If the user overrides at the gate and wants visible seconds**, the shape is fixed here so it is not re-guessed: `{t("booking.otpResendWait")}` followed by a `<bdi dir="ltr">` seconds node at the call site; the seconds node stays plain text; the polite region still fires **only on enable**, never on a coarse interval.

### 6.10 Submit — the in-flight state, and no double submit

The forward control in sub-state B POSTs `/storefront/otp/verify` and, on its `{verification_token}`, immediately POSTs `/storefront/bookings`. Both are one user-visible action.

| Concern | Ruling |
|---|---|
| Button in flight | `<Button variant="primary" size="lg" loading>`. The primitive sets `disabled` and `aria-busy` and overlays a spinner while keeping the label mounted under `aria-hidden` so the width never jumps (`Button.tsx:57-77`) |
| `booking.submitting` | **RULED: it is NOT the button's `children`.** Swapping the children defeats the very width lock the `loading` variant exists to give — the invisible label is what sizes the box. `booking.submitting` is a `VisuallyHidden role="status"` sibling emitted once when the POST starts. `aria-label` is also declined: WCAG 2.5.3 Label in Name requires the accessible name to *begin with* the visible text, and "submitting" does not contain "submit"'s Hebrew verbatim |
| No double submit — layer 1 | `loading` → `disabled` on the button, so the second click has no target |
| No double submit — layer 2 | The handler returns early while `submitting` is true. **Required, not decorative**: React commits `disabled` asynchronously, and a fast double-tap on iOS fires two `click`s inside one frame — the second one lands on a button that is still enabled in the DOM |
| No double submit — layer 3 | The form is a real `<form onSubmit>`; Enter in either field submits it once, and the same guard covers a keyboard repeat |
| Other fields during the POST | **RULED: fields stay enabled.** Only the submit and resend buttons disable. Declined: `<fieldset disabled>` — one attribute, but it removes every control from the tab order *under standing focus*, which is a focus loss (and a WCAG 3.2.2 change-on-input surprise) bought for nothing: the request payload was already captured at submit time, so a later keystroke in the phone field cannot corrupt it |
| Client validation before the POST | Only the phone. **No client length check on the code**, and the submit button is never disabled-until-6-digits — a disabled control must state its reason on its own visible label (house rule), and a label that mutates as she types is worse than a server round trip. The digits-only filter (§6.6) plus `maxLength={6}` makes a short submit deliberate, and the server's `OTP_INVALID` already carries the right sentence. Cost, stated honestly: one of ten verify attempts per five minutes |
| Auto-submit on the sixth digit | **Declined.** It fires on a paste of a *wrong* code, spends a verify budget, and moves focus under a user who is still reading |

### 6.11 States

Every row is drawn or fully specified above; the "Focus lands on" column is normative and §6.12 explains the two rules it follows.

| # | State | Trigger | What she sees | Focus lands on |
|---|---|---|---|---|
| 1 | **Default (phone)** | step entry | §6.2 | `<main id="content">` — the **Router's** move (`router.tsx:196-211`). This screen adds none |
| 2 | **Phone invalid** | client `validatePhone` on send | phone field gains `error={t("booking.phoneInvalid")}` → `aria-invalid` + `role="alert"`; **no request is issued** | the **phone field**, value selected |
| 3 | **Sending** | `/otp/send` in flight | send button `loading` (width locked); phone field stays enabled | unchanged (the button) |
| 4 | **Code sent** | `204` | code field appended (§6.3); `booking.otpSent` under its label; cooldown starts | the **code field** |
| 5 | **Resend before cooldown** | < 60 s since last send | resend button disabled, label is `booking.otpResendWait` (§6.9) | unchanged |
| 6 | **Cooldown ends** | 60 s elapsed | label reverts to `booking.otpResend`; one polite `role="status"` | unchanged |
| 7 | **`OTP_INVALID`** | wrong code on `/otp/verify` | code field `error={t("errors.otpInvalid")}`; **the resend button stays visible and reachable directly below it** (§6.15 F-C3) | the **code field**, value **selected, not cleared** |
| 8 | **`OTP_EXPIRED`** | code older than `OTP_TTL_SECONDS` (300 s) | code field `error={t("errors.otpExpired")}`; same layout as 7, and resend is the actual remedy | the **code field**, value selected |
| 9 | **Submitting** | `/bookings` in flight | submit `loading`; `booking.submitting` announced once | unchanged (the button) |
| 10 | **`PHONE_NOT_VERIFIED`** | 403 on `/bookings` — the 600 s token died or was spent | **collapse to sub-state A**: code field and its value removed; step-level `<p role="alert">` above the Card carrying `errors.phoneNotVerified`; everything else preserved (§6.12) | the **phone field** |
| 11 | **`TOO_MANY_ATTEMPTS` — verify face** | 429 on `/otp/verify` (10 per 5 min) | form intact; step-level `<p role="alert">` with `errors.tooManyAttempts`; both buttons stay enabled — the window is short and self-clearing | unchanged |
| 12 | **`TOO_MANY_ATTEMPTS` — send face** | 429 on `/otp/send` (5 per hour) | **dead-end block replaces the form**: `errors.otpSendBudget` (PROPOSED, §6.15 F-C2) over `ContactPanel` | the **dead-end block** (`tabIndex={-1}`) |
| 13 | **`SMS_NOT_CONFIGURED` / `SMS_UNAVAILABLE`** | 503 on `/otp/send` | **dead-end block replaces the form**: `errors.smsUnavailable` over `ContactPanel`. The `h1` and the ornament stay; the stepper stays; `booking.backStep` stays, so she is not trapped | the **dead-end block** (`tabIndex={-1}`) |
| 13d | **13 or 12 under D12** | `useBoutique()` has nothing | identical block, but `booking.contactUnavailable` (P5) replaces `ContactPanel` — no phone, no WhatsApp, no empty rows | same |
| 14 | **`SLOT_UNAVAILABLE` / `TERMS_STALE` / `NOT_FOUND` on submit** | 409 / 404 on `/bookings` | leaves this screen — §3 (slot re-pick), §5 (terms re-accept), §3/§4 (the `NOT_FOUND` probe). **Her verification token survives** (§6.12) | owned by the destination step |
| 15 | **`201`** | success | `navigate("/book/confirm")` → §7 | the Router's move |

Wireframe of state 13 / 13d, the only one whose layout is not a variant of §6.2 or §6.3:

```
| booking.stepOtp                     (h1 — unchanged)          |
| ~~~~~~ gold hairline ~~~~~~                                   |
|                                                               |
| +-- <div tabindex="-1">  (focus destination, NO role=alert) -+ |
| |  errors.smsUnavailable  |  errors.otpSendBudget            | |
| |     --text-base · var(--color-ink-muted) · NOT danger      | |
| +------------------------------------------------------------+ |
|                                                               |
| +-- ContactPanel --------------------------------------------+ |
| |  contact.call        (gold-text, underlined, 44px row)     | |
| |  contact.whatsapp                                          | |
| |  contact.waze / contact.maps / contact.instagram           | |
| +------------------------------------------------------------+ |
|                                                               |
|            ...  under D12, the whole panel is replaced by:    |
|            booking.contactUnavailable  (--text-base, muted)   |
|                                                               |
| ->  booking.backStep                    (still present)       |
+--------------------------------------------------------------+
```

### 6.12 What survives — ruled explicitly

**RULED: nothing she has entered is ever discarded by a verification failure. Not one field, in any of states 7, 8, 10, 11, 12, 13 or 14.**

| Datum | Survives? | Why it must |
|---|---|---|
| Picked slot (`starts_at`) | ✅ | She chose a time. A restart of *identity* is not a restart of *intent* |
| Appointment type id | ✅ | Same |
| Name, `notes` | ✅ | Re-typing 500 characters of "coming with my mother, wheelchair access" to fix an OTP is the dead end this feature exists to remove |
| Dress id + size | ✅ | And they stay in the URL segment regardless (D9) |
| **Terms acceptance + `terms_version`** | ✅ | **Explicitly ruled.** A consent is a consent to a *version*, and the version did not change — only the phone token expired. Re-prompting is legally no stronger and practically a second read of a cancellation policy for nothing. If the version *did* change the server says `TERMS_STALE`, which is a different state and is §5's |
| Phone number | ✅ | Including in state 10 — she stays on the field, ready to re-send |
| Entered OTP code | ❌ in state 10 (its token is gone), ✅ **selected not cleared** in states 7 and 8 | Clearing destroys the evidence of what she typed, and on `OTP_EXPIRED` the digits were probably correct |
| Cooldown timer | ✅ | It is a property of the last send, not of the failure |

**The backend guarantees the hard half of this.** `create_booking` runs in one transaction, and *"a claim that fails at ANY step — including losing the race — rolls back the token burn too, so the customer's verification survives to retry another slot"* (`Backend/app/booking/service.py:130-135`). So after `SLOT_UNAVAILABLE` or `TERMS_STALE` **her verification token is still live** and state 14's recovery must **not** route back through OTP — it returns to `slot` or `terms` and submits again from there. A design that re-verified after a lost slot race would burn one of five hourly sends to re-prove something the server never un-proved.

`PHONE_NOT_VERIFIED` is checked **first inside the transaction**, before type, terms, dress and slot (`service.py:167-173`), so it never arrives alongside another cause. One error at a time; no discriminator needed.

### 6.13 Focus model — the two rules, then every transition

**Rule 1 — the screen never competes with the Router.** `router.tsx:196-211` scroll-resets and focuses `<main id="content">` on **every** path change, and its dependency array includes `pathname`, so it re-fires on each step. A page-level focus move on mount races it. S4 adds **no** mount-time focus.

**Rule 2 — focus moves only on a *submit*-triggered transition, never on an *input*-triggered one.** No autofocus on the sixth digit, no focus jump on a valid-looking phone number, no auto-submit. The bride is typing; the screen does not.

Everything else follows from the house rules already in force:

- An error that appears **with** a focus move needs only `aria-describedby` — which the `Input` primitive supplies by construction. That covers states 2, 7 and 8.
- An error that appears **without** one must be in an assertive region — which is why the step-level blocks in states 10 and 11 are `<p role="alert">` and the dead-end block in 12/13, which *is* reached by a focus move, is deliberately **not**.
- Every DOM-mutating action names a destination. The two mutations that destroy the node focus was on are state 10 (the code field is removed) and states 12/13 (the whole form is removed) — both name one.

**`Input` cannot do this today.** See F-C5 below; the entire column is a gate condition on `packages/ui`, not a build detail.

### 6.14 Rows for the shared contrast ledger (§10.1)

Recomputed against the surface each pair actually renders on, not transcribed.

| Element | Foreground | Background | Ratio | Note |
|---|---|---|---|---|
| `h1`, field labels | `--color-ink` | `--color-bg` / `--color-surface` | **15.24** / **13.89** | h1 on cream, labels inside the paper Card |
| Field value (typed phone / code) | `--color-ink` | `--color-surface-raised` | **15.75:1** | the input's own white fill |
| `booking.phoneHint`, `booking.otpSent`, `booking.otpResendWait` | `--color-ink-muted` | `--color-surface` | **5.61:1** | inside the Card |
| Step-level alert, dead-end sentence, `booking.contactUnavailable` | `--color-ink-muted` | `--color-bg` | **6.15:1** | outside the Card, on cream |
| Field errors (`phoneInvalid`, `otpInvalid`, `otpExpired`) | `--color-danger` | `--color-surface` | **6.18:1** | the `Input` primitive's `text-danger` span, inside the Card |
| Submit button | `--color-ink` | `--color-gold` | **6.41:1** | gold as background only — usage law 1 |
| `ContactPanel` links, `booking.backStep` | `--color-gold-text` | `--color-bg` | **5.57:1** | always underlined as well |
| Input / button borders (non-text) | `--color-border-input` `#8A7A5E` | `--color-surface` / `--color-surface-raised` | **3.69** / **4.18** ✓ | the corrected token, already shipped at `theme.css:31` |
| Focus ring (non-text) | `--color-focus` | `--color-bg` / `--color-surface` / `--color-surface-raised` | **5.57** / **5.08** / **5.76** ✓ | 2px, 2px offset |
| Card hairline divider | `--color-border` | `--color-surface` | 1.22 — decorative | never a load-bearing boundary; the two visible labels delimit the fields |

**Never used on this screen**: `--color-gold` on text · `--color-gold-strong` on text at any size (its one use here is the focus-state input border, a non-text boundary) · `--color-success` (§7 rules it out flow-wide) · `--color-warning-text` (a cooldown is not a warning) · opacity on any text node.

### 6.15 ⚠ FINDINGS

**⚠ F-C1 — the spec names one clock; there are two, and the tighter one is not in the spec.**
The spec calls the 600-second verification token *"the flow's hard constraint"* and builds D2's ordering on it. But the code itself lives **`OTP_TTL_SECONDS = 300`** (`Backend/app/notifications/validation.py:14`) and starts ticking at `/otp/send` — *before* she types a digit. D2 is untouched (the 600 s window still never spans the policy read), but this screen has a second, shorter clock that produces `OTP_EXPIRED` for a bride who took six minutes to find her phone, and the spec's state matrix folds `OTP_EXPIRED` in with `OTP_INVALID` as "retry inline" when the correct recovery is **resend, not retype**. Designed here as states 7 and 8 with different remedies; **the spec's line should be amended to name the 300 s clock**, and `booking.otpSent` may state it in words.

**⚠ F-C2 — `TOO_MANY_ATTEMPTS` is one code with three call-site faces and three different waits, and the shipped Hebrew is wrong for two of them.**
`errors.tooManyAttempts` already ships as *"יותר מדי בקשות. נסי שוב בעוד רגע."* — "try again in a moment". The three budgets:

| Call | Budget | Real wait |
|---|---|---|
| `/otp/verify` | 10 per 5 min (`otp_verify_max_per_phone_window`) | ≤ 5 minutes — "in a moment" is true |
| `/otp/send` | **5 per hour** (`otp_send_max_per_phone_window`) | up to an hour — "in a moment" is a **lie** that will make her hammer the button into the same 429 |
| `POST /bookings` | 10 per hour per phone | up to an hour — same lie |

The spec's state matrix has **one** "Rate limited" row and its i18n inventory has **one** key, so a builder following the spec literally ships the lie. Like the spec's own two-meaning `NOT_FOUND`, the discriminator is the **call site, never the code** — deterministic, no probe needed. Designed here as states 11 (verify face, form survives) and 12 (send face, dead end). **PROPOSED: one new key, `errors.otpSendBudget`**, beyond the spec's inventory, on the same footing as P5's `booking.contactUnavailable`. Declined zero-key fallback: render `errors.tooManyAttempts` inside the dead-end block above the `ContactPanel` — the recovery would be right and the sentence merely optimistic, but it reads as self-contradictory copy next to a phone number.

**⚠ F-C3 — a burnt code is indistinguishable from a wrong one, so `errors.otpInvalid` must itself point at resend.**
`OTP_MAX_VERIFY_ATTEMPTS = 5` is tracked on the code row, and once it is spent **every further verify answers `OtpInvalidError`** (`Backend/app/notifications/service.py:279-289`) — deliberately, so the lockout is not readable off the response. The client therefore cannot detect the lockout and cannot switch copy. Two consequences, both binding: (a) the **resend control must remain visible and reachable directly below the code field in states 7 and 8** — an error that hides the only working remedy is a dead end; (b) **copy constraint on §11**: `errors.otpInvalid` must name resending as the remedy, not merely say the code is wrong, because on the sixth attempt retyping the *correct* code still fails.

**⚠ F-C4 — the i18n inventory has no label for the FIRST send.**
The inventory carries `otpResend`, `otpResendWait`, `submit`, `submitting` — and nothing for the button that sends the first code. `booking.submit` means "book" and cannot serve. **PROPOSED, no new key: `booking.otpResend` is worded to serve both** — a neutral "send code" shape rather than "send again". Same economy the spec itself applies when it deliberately maps two `SMS_*` codes onto one key. This is a **copy constraint**, not a silent reuse: §11 must not write `otpResend` as "שליחה חוזרת".

**⚠ F-C5 — `Input` has no `ref`, so every focus move in §6.13 is unbuildable today. This is a gate condition on `packages/ui`.**
`InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id">` (`Input.tsx:5`) — `id` is omitted and generated internally by `useId`, and React 19's ref-as-prop is **not** part of `*HTMLAttributes`. `Button` declares `ref?: Ref<HTMLButtonElement>` explicitly for exactly this reason (`Button.tsx:12`); `Input`, `TextArea` and `Select` do not. There is consequently **no way to focus a field programmatically**: not the code field on send success (state 4), not the phone field on client validation (state 2) or on `PHONE_NOT_VERIFIED` (state 10), not the code field on `OTP_INVALID`/`OTP_EXPIRED` (states 7, 8). This is not a booking-flow quirk — it is the "focus moves to the first invalid field on submit" rule the console already claims, unimplementable in the shared primitive. **Remedy: add `ref?: Ref<HTMLInputElement>` to `InputProps` and thread it, one line each in `Input.tsx`, `TextArea.tsx`, `Select.tsx`, copying `Button.tsx:12,55` verbatim.** Queued for `components.md` in the same PR, same reviewer, no new design work. **Gate condition: this must land in `packages/ui` before or with the F14 build that consumes this document.**

**⚠ F-C6 — `Button`'s `loading` variant cannot carry a swapped label, which is where `booking.submitting` naively goes.**
`Button.tsx:68-77` keeps `children` mounted (`invisible`, `aria-hidden`) *specifically* so the box keeps its natural width while the spinner overlays it. Swapping `children` to `booking.submitting` re-sizes the invisible label and the width jumps — defeating the one thing the variant exists to guarantee. Ruled in §6.10: `booking.submitting` is a `VisuallyHidden role="status"` sibling. Flagged because a plan that says "swap the label to `booking.submitting`" is the obvious wrong reading of the inventory, and it produces a defect no test will catch.

---

## 7. Screen S5 — confirmation (`/book/confirm`, `/book/confirm/{dressId}`)

Terminal. **Outside the stepper** — no step indicator, no `booking.backStep`, no step count (which is why D8's label set has no `stepConfirm`). It is the one step exempt from the prerequisite guard: the booking is already written, so this screen **never** redirects to `slot` (D8).

**D6 governs every word on it: it promises no SMS.** F16 has not shipped; a booking created here sends nothing. This screen is her only record.

### 7.1 Mobile 375 — warm (the `201` is in memory)

```
+--------------------------------------------------------------+
| booking.confirmTitle                (h1, display, --text-2xl) |
| ~~~~~~ gold hairline ~~~~~~         (aria-hidden ornament)    |
|                                                               |
| +-- Card (paper, --space-4 @375, radius-md, shadow-sm) ------+ |
| |  booking.confirmWhen               (label, --text-sm muted)| |
| |  יום שלישי, <bdi dir="ltr">4.8.2026</bdi>                  | |
| |            . <bdi dir="ltr">16:30</bdi>   (--text-lg, ink) | |
| |                                                            | |
| |  ---------------------------------- hairline               | |
| |                                                            | |
| |  booking.confirmWhat               (label, --text-sm muted)| |
| |  {appointment_type_name}                  (--text-lg, ink) | |
| |  {dress_name} . מידה <bdi dir="ltr">38</bdi>               | |
| |                          (--text-base, ink — rendered ONLY | |
| |                           when dress_name !== null)        | |
| +------------------------------------------------------------+ |
|                                                               |
| booking.confirmKeepScreen           (--text-base, ink-muted)  |
|                                                               |
| ->  booking.backToCatalog       (Link, gold-text, underlined) |
|                                                               |
| (page owns its own padding-block-end — §2 / §8)               |
+--------------------------------------------------------------+
```

**768 / 1440 deltas**: Card padding `--space-6`; nothing else changes. The column does not widen (§2). No `BookingCTA` bar at any width.

### 7.2 Component notes — exact tokens

| Element | Spec |
|---|---|
| `h1` `booking.confirmTitle` | `var(--font-display)`, `--text-2xl`, `var(--color-ink)` (**15.24:1** on cream ✓). **Identical in every branch below**, including cold and cold-under-D12 — the storefront heading law admits no state without an `h1`, and this page's `h1` must not depend on whether an in-memory payload or a boutique fetch survived |
| Gold hairline | `<span aria-hidden="true">`, `block-size: 1px`, `inline-size: var(--space-12)` (48px), `background: var(--color-gold)`. **The only decoration on the screen** (§7.5) |
| Card | `background: var(--color-surface)`, `border-radius: var(--radius-md)`, `box-shadow: var(--shadow-sm)`, `padding: var(--space-6)` (`var(--space-4)` @375). No hard border |
| `booking.confirmWhen` / `booking.confirmWhat` | **labels, not sentences** — `--text-sm`, `var(--color-ink-muted)` (**5.61:1** on paper ✓), `font-weight: 600`, `margin-block-end: var(--space-1)` |
| The two values | `--text-lg` (1.1875rem/1.5), `var(--color-ink)` (**13.89:1** ✓). Larger than body: this is the screen's payload and a screenshot has to survive being read back at 200 % zoom in a car park |
| Date + time | `יום {weekday}, <bdi dir="ltr">{d.m.yyyy}</bdi> · <bdi dir="ltr">{HH:MM}</bdi>`. The Hebrew weekday word stays in RTL flow; **only the numeric runs are LTR islands** — matching `DressPage.tsx:215` and `StorefrontLayout.tsx:166`. The `·` separator is an `aria-hidden` span |
| Dress line | `{dress_name} · מידה <bdi dir="ltr">{dress_size}</bdi>`, `--text-base`, `var(--color-ink)`. Renders **only** when `dress_name !== null` — the generic path prints no empty row (the shipped precedent: `/about` omits its contact card rather than printing blank lines) |
| Divider | `border-block-start: 1px solid var(--color-border)`, `margin-block: var(--space-4)` |
| `booking.confirmKeepScreen` | **outside** the Card, `margin-block-start: var(--space-4)`, `--text-base`, `var(--color-ink-muted)` on cream (**6.15:1** ✓). Outside because it is instruction *about* the card, not a fact *in* it — and because a screenshot cropped to the Card should contain only facts |
| `booking.backToCatalog` | **a text link, not a Button**: `<Link to="/">` with `cn("text-base text-gold-text underline", focusRing)` (**5.57:1** ✓) and an `aria-hidden` `→` glyph — in RTL the way back points inline-start-to-end, i.e. rightwards (`DressPage.tsx:168`). `min-block-size: 44px` on the link box. **This sidesteps gate proposal P1's cost entirely on this screen**: `Button` is not polymorphic (`Button.tsx:53` hardcodes `<button type="button">`, and its class constants are module-private), so a "button-styled anchor" would need a `packages/ui` change. A link that looks like a link needs none, and matches the shipped `dress.back` treatment |

### 7.3 Formatting the instant — ruled, with the objection pre-answered

`starts_at` arrives from the `201` as a **UTC instant**. It must be rendered in **Asia/Jerusalem**, because a bride in Israel opening the page on a phone whose clock the airline changed must still see the boutique's time.

**RULED: `new Intl.DateTimeFormat("he-IL", { timeZone: JERusalem, … })`**, with `JERusalem` imported from `@boutique/ui` (`packages/ui/src/index.ts:43`). Two formatters — one for the weekday + date, one for `HH:MM`.

Two objections a reviewer will raise, answered here so they are not re-filed:

1. **`hoursText.ts:19` bans locale date formatting.** Its stated reason is *"it reads an implicit timezone, and the wire date is already a Jerusalem calendar date"* — both clauses fail here. The timezone is **explicit**, and the wire carries a UTC instant that *must* be converted. The ban does not reach this case; hand-rolling the conversion would.
2. **`qa-greps.sh`'s advisory check.** Its pattern is `getDay()|getDate()|toLocaleDateString|toLocaleTimeString` — `Intl.DateTimeFormat(...).format()` is not in it, and it is non-blocking regardless. `TermsSection.tsx:9` is the shipped `Intl.DateTimeFormat("he-IL", …)` precedent.

`status` from the `201` is **not rendered**. `Backend/app/models/booking.py:31` server-defaults it to `'confirmed'` and `create_booking` never writes another value, so on this path it is constant. Printing a constant invites the reader to wonder what the other values are, and dressing it as a `Badge success` would be colour + word for a fact with no decision behind it. Declined.

### 7.4 Tone — what the copy must NOT imply

This screen must read **complete and calm**: a fact stated, not a process begun. §11's DRAFT Hebrew and the user's final copy are both bound by the list below, so that neither can drift into promising a message F16 has not shipped.

**Forbidden in `confirmTitle`, `confirmWhen`, `confirmWhat`, `confirmKeepScreen` and `confirmCold`:**

| Forbidden | Why |
|---|---|
| Any future-tense delivery verb — "נשלח", "יישלח", "תקבלי הודעה / מסרון / SMS" | D6. Nothing is sent. This is the dead end the feature exists to remove, reintroduced by a verb tense |
| "אישור בדרך", "בדקי את הטלפון", "we'll be in touch" | Same, in disguise. An outbound-message promise dressed as reassurance |
| Any mention of email | The flow never collects one |
| "נחזור אלייך" | Reads as an outbound call the boutique has not committed to. The *appointment* is the commitment; a phone call is not |
| "מזל טוב", stacked exclamation marks, celebratory framing | Usage law 9. A fitting is a step, not a purchase, and celebration here is the promo register |
| A cancellation/reschedule instruction that names a self-serve control | The manage/cancel link is explicitly out of scope. If cancelling is mentioned at all it points at the boutique |

**Required tense and posture**: the appointment **exists, now**, and here it is. `confirmKeepScreen` is the only sentence that asks her to do anything, and what it asks is to keep the screen — screenshot or save it — because it is the record.

**The one string that changes when F16 lands: `booking.confirmKeepScreen`.** Its premise ("this screen is your only record") is exactly what F16 falsifies. `confirmTitle`, `confirmWhen` and `confirmWhat` remain true afterwards and must not be written in a way that couples them to the no-SMS state. Spec Risk 2's trigger resolves to **one key**.

### 7.5 The success visual — ruled

**RULED: `--color-success` appears nowhere on this screen. Green is not the success signal.**

The signal is three things that are not colour:

1. `booking.confirmTitle` — the words.
2. **The appointment stated in full.** A screen that can print her weekday, her time and her appointment type is a screen on which the booking demonstrably exists. That is a stronger proof than a tick.
3. The gold hairline ornament under the `h1` — the storefront's one existing decorative motif, `aria-hidden`, already carried by every page-subject heading on the site.

| Declined | Why |
|---|---|
| A `--color-success` band, rule or checkmark | Introduces a motif the storefront does not have, on the one screen where the design should feel most like the rest of the site. And green-as-success is precisely "colour communicates alone" (usage law 2) unless paired with a word — and the word is already doing all of the work |
| `Badge variant="success"` | A badge implies a status **among several**. There is only one (§7.3) |
| Confetti, a scale-in, a checkmark draw-on | Usage law 9, and `tokens.md`'s motion language outright: *"Nothing bounces, nothing spins except spinners, nothing autoplays"* |

**Motion**: the shared plan only — page content fade + 8 px rise, `--motion-base` (200 ms), `--ease-out`. Nothing feature-specific. `prefers-reduced-motion: reduce` ⇒ none. Recorded in §9 as a no-op row so a reviewer can see it was considered.

### 7.6 Focus and announcement on arrival — ruled

Arriving here is a **client navigation** (`navigate("/book/confirm")` after the `201`), so `router.tsx:196-211` already scroll-resets to the top and focuses `<main id="content">`. The `h1` is the first node inside `<main>`, so a screen reader reading forward from the focus point reads `booking.confirmTitle` immediately, after the `document.title` change announces the route.

**RULED: this screen adds no focus move and no live region.**

| Declined | Why |
|---|---|
| A `role="status"` announcing success | It would speak the same fact the `h1` is about to be read — a double announcement, on the one screen where the *facts under* the heading are what matter |
| A `role="alert"` announcing success | Wrong on two counts. `alert` is assertive: it **interrupts** the AT's own reading of the newly-focused page, and the thing it would interrupt is the appointment she came for. And `alert` is semantically reserved for something demanding attention or action; a success the user navigated to demands neither. **If a live region is ever added here it is `role="status"`, never `role="alert"`** |
| Focusing the `h1` directly | A second `focus()` racing the Router's. §6.13 Rule 1 |

The one legitimate additional destination is the **cold** branch's, and it needs none either: cold-confirm is reached by a page *load*, not a client navigation, so the browser owns focus and the skip link is the first stop — `router.tsx`'s `handledPath` guard suppresses the move on first paint precisely so it is not stolen.

### 7.7 Cold confirm — reload, or the iOS screenshot round-trip

A reload — or the app-switch a screenshot triggers on iOS — destroys the in-memory `201`, and **there is no public read-a-booking-by-id endpoint** (D8; F14 does not add one). This is not an edge case: D6 tells her to screenshot the screen, and on iOS that is an app-switch. **The state this design most has to get right is the one the previous sentence causes.**

**RULED: cold confirm renders a short, true statement over `ContactPanel`. It never bounces her to step one, and it never claims facts it does not hold.**

```
+--------------------------------------------------------------+
| booking.confirmTitle                (h1 — byte-identical to   |
| ~~~~~~ gold hairline ~~~~~~          the warm branch)         |
|                                                               |
| booking.confirmCold                 (--text-base, ink-muted)  |
|                                                               |
| +-- ContactPanel --------------------------------------------+ |
| |  contact.call        (gold-text, underlined, 44px rows)    | |
| |  contact.whatsapp                                          | |
| |  contact.waze / contact.maps / contact.instagram           | |
| +------------------------------------------------------------+ |
|                                                               |
| ->  booking.backToCatalog                                     |
+--------------------------------------------------------------+
```

Three rulings inside that drawing:

- **No Card.** The Card's job is to hold the appointment's facts; with none in memory it would frame an absence.
- **`booking.confirmKeepScreen` is NOT rendered.** ⚠ see F-C8 — its instruction is to keep a record that this branch does not have, so printing it here is actively wrong.
- **`ContactPanel` row order** follows the shared ruling in §2 (the same ordering question the usability plan raised for all three panel branches). Not re-decided here.

### 7.8 Cold confirm under D12 — no boutique, therefore no channels

D12's honest consequence: on `/book` for a tenant whose boutique fetch failed, the `boutique` object is `null`, so `ContactPanel` has no phone, no WhatsApp, no address and no handle. Rendering it anyway produces `<div class="flex flex-col gap-3">` with **no children** — an empty flex box (`ContactPanel.tsx:37-38`; every row is behind a truthiness guard).

**RULED: branch at the call site and render plain copy instead.** This is exactly what the shipped storefront already does in three places — `CatalogPage.tsx:162` withholds the CTA, `AboutPage.tsx:106-114` renders a `<p>` and omits the contact card outright, and `statement.coordinatorNoChannel` is the same shape as a string.

```
+--------------------------------------------------------------+
| booking.confirmTitle                (h1 — still identical)    |
| ~~~~~~ gold hairline ~~~~~~                                   |
|                                                               |
| booking.confirmCold                 (--text-base, ink-muted)  |
| booking.contactUnavailable          (--text-base, ink-muted)  |
|                                          <- gate proposal P5  |
|                                                               |
| ->  booking.backToCatalog                                     |
+--------------------------------------------------------------+
```

**Copy constraint on P5's key, binding.** `statement.coordinatorNoChannel` interpolates `{{name}}` — and in the D12 case the name is unavailable **by definition**, because the fetch that would have carried it is the one that failed. `booking.contactUnavailable` must therefore be **name-free**, or interpolate `catalog.essenceFallback` ("חנות הכלות") the way `CatalogPage.tsx:150`, `DressPage.tsx:98` and `AboutPage.tsx:92` all do for the `h1`. **RULED: name-free** — one string, no interpolation, no i18next `returnObjects` trap, and nothing that could ever render "לפנות אל undefined".

Note that the `h1` needs no such fallback: it is `booking.confirmTitle`, which is boutique-independent. This screen is the only one in the flow whose heading survives D12 without a fallback at all.

### 7.9 States

| # | State | Trigger | What she sees | Focus |
|---|---|---|---|---|
| 1 | **Warm confirm** | the `201` is in memory | §7.1 — full statement | Router's move to `<main>` |
| 2 | **Warm, generic** | `dress_name === null` | §7.1 minus the dress line entirely; no empty row | same |
| 3 | **Cold confirm** | reload / iOS app-switch | §7.7 — `confirmCold` over `ContactPanel`, no Card, **no `confirmKeepScreen`** | browser-owned (first paint) |
| 4 | **Cold under D12** | cold **and** `useBoutique()` has nothing | §7.8 — `booking.contactUnavailable` replaces the panel | same |
| 5 | **`verify` reached with a spent token but a completed booking** | D8's forward rule | forwards to `confirm` and renders state 1 or 3 — never `slot` | Router's move |

There is deliberately **no loading state**: nothing on this screen is fetched. The warm branch reads memory; the cold branch reads nothing. `useBoutique()`'s `loading` affects only branch 4's choice, and the honest treatment while it resolves is to render **state 3's copy without the panel** rather than a skeleton for a panel that may never come.

### 7.10 Rows for the shared contrast ledger (§10.1)

| Element | Foreground | Background | Ratio | Note |
|---|---|---|---|---|
| `h1` `booking.confirmTitle` | `--color-ink` | `--color-bg` | **15.24:1** | cream, outside the Card |
| `confirmWhen` / `confirmWhat` labels | `--color-ink-muted` | `--color-surface` | **5.61:1** | inside the paper Card |
| Date, time, type, dress values | `--color-ink` | `--color-surface` | **13.89:1** | the payload |
| `confirmKeepScreen`, `confirmCold`, `contactUnavailable` | `--color-ink-muted` | `--color-bg` | **6.15:1** | outside the Card |
| `booking.backToCatalog`, `ContactPanel` links | `--color-gold-text` | `--color-bg` | **5.57:1** | underlined |
| Focus ring | `--color-focus` | `--color-bg` / `--color-surface` | **5.57** / **5.08** ✓ | 2px, 2px offset |
| Gold hairline ornament | `--color-gold` | `--color-bg` | 2.38 — **exempt** | `aria-hidden` decorative art (usage law 1) |
| Card divider | `--color-border` | `--color-surface` | 1.22 — decorative | the two visible labels delimit the halves |

**`--color-success` appears zero times on this screen** (§7.5), which is the one ledger row a reviewer should check by its absence.

### 7.11 ⚠ FINDINGS

**⚠ F-C7 — the confirmation is the only record, and the action D6 asks for is the action that destroys it.**
`booking.confirmKeepScreen` tells her to screenshot. On iOS a screenshot is an app-switch, and returning can reload the tab — which lands her in cold confirm, the branch that **cannot restate her appointment**. D8 anticipated the reload and ruled the branch; nobody has recorded that the instruction and the failure share a cause. Nothing here is unbuildable — the design is §7.7 — but two things follow that the spec does not say: (a) **§11's `confirmKeepScreen` should prefer "save" or "write down" framing over "screenshot"-only**, so the instruction does not exclusively name the risky gesture; and (b) **this is the strongest argument in the epic for a public read-a-booking-by-id endpoint**, which F14 correctly does not add — recorded so F15/F16 inherits it rather than rediscovering it.

**⚠ F-C8 — `booking.confirmKeepScreen` must not render in the cold branch, and the inventory does not say so.**
The spec's inventory lists `confirmCold` and `confirmKeepScreen` side by side with no statement that they are mutually exclusive. They are: "keep this screen" printed above a screen that holds no appointment instructs her to preserve an absence. **Ruled in §7.7: the cold branch renders `confirmCold` and never `confirmKeepScreen`.** Flagged because "render both, they are both confirm-screen strings" is the obvious wrong reading and no test would catch it.

**⚠ F-C9 — `booking.backToCatalog` duplicates shipped Hebrew, and the duplication should be deliberate.**
`dress.backToCatalog` ("חזרה לקולקציה") already ships, as does `dress.back`. The spec's inventory nonetheless names `booking.backToCatalog`, so this document honours it — but §11 should decide **on purpose** whether the two strings say the same words. A post-booking exit plausibly wants different, warmer copy than a 404's escape hatch, and if it does not, the duplication is a copy-deck decision rather than an oversight. `i18n-keys.test.ts` checks used→defined only and will never flag either case.

**⚠ F-C10 — `confirmWhen` / `confirmWhat` are ruled to be LABELS, not sentences, and this constrains §11.**
They could equally have been written as sentences with `{{date}}` / `{{type}}` placeholders. **Ruled as labels**, for two reasons that are not style: (a) i18next interpolation cannot carry markup, and the date, the time and the size all need `<bdi dir="ltr">` isolation — a placeholder sentence forces the numeric runs out of their islands or forces the Hebrew word order into TSX; and (b) a label/value pair survives being read back off a screenshot at 200 % zoom in a way a flowing sentence does not. §11 must write them as short labels.

---

**Cross-references used by these two sections** (for the assembler to resolve): §2 for the flow shell — content column width, the stepper, `booking.backStep`, `/book`'s own bottom padding and the `A11yMenu` at `var(--space-4)`, and the shared `ContactPanel` row order · §3 for the slot + appointment-type step, which owns the `SLOT_UNAVAILABLE` re-pick and the `NOT_FOUND` probe's type branch · §4 for the details step (name, `notes`) and the size chips (gate proposal P2), which own the `NOT_FOUND` probe's dress and size branches · §5 for the terms step, which owns the `TERMS_STALE` re-accept and D5's no-terms degrade · §8 responsive · §9 motion (§7.5 contributes one no-op row) · §10.1 contrast ledger (§6.14 and §7.10 contribute rows) and §10.3 checklist · §11 copy deck (the constraints in §6.8, §6.15 F-C2/F-C3/F-C4, §7.4, §7.11 F-C8/F-C9/F-C10 are binding on it) · §12 open items (F-C5's `packages/ui` `ref` addition is a gate condition and belongs there; so does the `qa-checklist.md:141` amendment adding the `/book/*` family).
## 8. Responsive

One column, three widths, one rule set. The booking flow is a **form-and-reading surface**, not a lookbook — it takes `/about`'s editorial column, not the catalog's 1200px lookbook width. Everything below is a delta against `StorefrontLayout`, which supplies the skip link, `<main id="content" tabIndex={-1}>`, the footer and the `A11yMenu` unchanged.

### 8.1 The column

| Property | Value | Reason |
|---|---|---|
| Column | `max-inline-size: 640px`, centred | Byte-identical to `/about` (`max-w-[640px]`), the storefront's only other reading-and-forms surface. `/accessibility` uses 720px and the console's form column is 720px by `manage-restyle.md` law, but that is the **console** dialect and this screen is the bride's. **PROPOSED — user confirms at the gate (P7).** Declined: 1200px (a form line-length of 1200px is unreadable and the slot grid would stretch to 6 columns of air) and 720px (borrows the console's number for a customer screen with no reason to) |
| Page gutters | `--space-4` @375 · `--space-6` @≥768 · **no third step** | `/about`'s exact ladder (`px-4 md:px-6`). A third step is dead code here: at a 640px cap the gutters stop being the constraint above a ~688px viewport, so `xl:px-12` would change nothing that is visible. **Do not "restore the missing 1440 step"** — Tailwind's default `xl` is **1280px**, not 1440, and `theme.css` overrides no breakpoints, so the catalog's `xl:px-12` in fact steps at 1280. Copying it here would add a breakpoint the design never asked for at a width the design never names |
| Block padding | `padding-block-start: var(--space-8)` · `padding-block-end: var(--space-16)` | Start matches `/about`'s `pt-8`. End is **larger than `/about`'s `pb-8` on purpose** — see §8.4 |
| Vertical rhythm | `gap: var(--space-6)` between the column's blocks (back link · stepper · h1 · step body · forward row) | Section rhythm ≥ `--space-6` (tokens.md); Card internals stay ≤ `--space-4` |

At **1440 the layout is identical to 768.** The column caps at 640px and centres; nothing gains a second pane. There is deliberately no wide two-column "slots beside a summary" variant: a summary rail that exists only ≥768 is a state that only half the users ever see and only half the tests ever cover, and a bride on 375 is the primary case.

### 8.2 What changes at each width

| Width | Behaviour |
|---|---|
| **375** | Page gutters `--space-4`; Card padding `--space-4`. **Forward button full-width** (`Button` `fullWidthMobile`), sitting alone on the last row of the column. Back link on its own row at the block-start, inline-start. Slot grid **2-col**. Appointment-type options stack full-width, one per row. Size chips wrap freely. Stepper: four items on one row, **labels visible** (§8.3). Every interactive target ≥44×44 |
| **768** | Page gutters `--space-6`. **Forward button returns to auto width, inline-end** of the forward row; the back link joins that row at its inline-start where the step body is short enough that a two-control row reads as one decision. Slot grid **3-col**. Everything else unchanged from 375 |
| **1440** | **Identical to 768.** Only the surrounding page margin grows as the 640px column centres in a wider viewport. No gutter step, no column growth, no new panes |

**Standing check, every width: no horizontal scroll at 375 / 768 / 1440.** The three constructions that can break it are named so QA has something to point at: the slot grid (chips must wrap, never `overflow-x`), the terms policy body (`overflow-wrap: anywhere` — a boutique can paste an un-broken URL into `terms_text`), and any `<bdi dir="ltr">` numeric run at the inline edge of a narrow chip. This is the e2e spec's existing standing route check, extended to the six new URLs in §12.

### 8.3 The stepper at 375 — ruled

**The step labels never truncate to numbers at any width. PROPOSED — user confirms at the gate.**

Four short Hebrew words (`booking.stepSlot` · `stepDetails` · `stepTerms` · `stepOtp`) at `--text-xs` fit a 343px content box at 375 with room; if a longer draft string ever does not, the stepper **wraps to two rows** rather than dropping to `1 2 3 4`. Declined: a numeric stepper at 375, on three grounds — (a) a bare ordinal tells a bride nothing about what she is about to be asked for, which is exactly the reassurance a four-step commitment flow exists to give; (b) it would put text in the accessible name that the sighted user cannot see, the inverse of WCAG 2.5.3; (c) with the current item marked only by colour it becomes a colour-only signal (usage law 2) unless the ordinal is *also* re-labelled — at which point the label is back.

The stepper's visual spec belongs to §1 (flow map); its semantics are §9.4 and §12, and its responsive contract is this row.

### 8.4 `/book` has no CTA bar — and what follows from that (spec Risk 6)

`hasBookingBar(route)` is `route.name === "catalog" || route.name === "dress"` (`StorefrontLayout.tsx:63-65`). `book` is neither, so it falls through to `false`. **That is the intended outcome and it must be asserted, not assumed** — the inverse mistake (adding `book` to the list) renders a "קביעת תור" CTA *inside* the booking flow.

Three consequences, all binding:

1. **No fixed bar at any width in `/book/*`.** The step's forward control is an ordinary in-flow `Button` inside the step's `<form>`. It is never `BookingCTA` and never `BookingCTAButton` — those carry a `fixed` footprint that `cn` cannot be talked out of (no tailwind-merge; `BookingCTAButton` documents being bitten by exactly this).
2. **The `A11yMenu` fixed button rests at `var(--space-4)`, not `var(--space-a11y-clearance)`.** It gets that for free from the same `false`. `--space-a11y-clearance` (92px) exists only to clear a bar that is not here; using it would float the button in dead space.
3. **The page reserves its own block-end padding, because the shell reserves none.** The shell's `max-md:[padding-block-end:calc(var(--cta-bar-height)+…)]` is behind the same `hasBookingBar` guard. `/book`'s column therefore carries `padding-block-end: var(--space-16)` (64px), which is **more than `/about`'s `pb-8`** and is chosen against a measurement rather than copied: the `A11yMenu` trigger is `size-11` (44px) at `inset-block-end: var(--space-4)` (16px), so its footprint reaches **60px** up from the viewport's block-end at its inline-end. `--space-16` = 64px clears it; `--space-8` = 32px does not.

**A residual, stated rather than papered over.** The `A11yMenu` button is `fixed`, so mid-scroll it overlays whatever is beneath it at every scroll position — this is true of every storefront route today and PRE-1's resolution addressed only the CTA bar. At 375 the forward button is full-width (~343px) while the trigger covers 44px at its inline-end, so worst-case overlap costs ~13% of the target's inline extent versus PRE-1's 13.8% of the CTA bar; the button remains operable and the bottom padding above guarantees the *resting* end state is clear. **The footer is a different matter and is not this design's to fix** — see ⚠ FINDING 3.

### 8.5 Standing responsive checks for `/book/*` (fold into `qa-checklist.md` §7 — see §13)

- [ ] No horizontal scroll at 375 / 768 / 1440, on all five steps, with a long boutique name and a 500-character `notes` value in the field
- [ ] **Exactly zero `BookingCTA` bars at 375 and at 768** on every `/book/*` URL — the inverse of the catalog/detail/`/about` rows already in §7
- [ ] `A11yMenu` computed `inset-block-end` is `var(--space-4)` at 375, not `var(--space-a11y-clearance)`
- [ ] At 375, scrolled to the page end, zero `getBoundingClientRect()` overlap between the `A11yMenu` trigger and the forward button
- [ ] Text resize to 200% (browser zoom **and** root-32px text-only) at all three widths: stepper wraps rather than clips, slot chips reflow, the forward button does not lose its label

---

## 9. Heading outline, focus and keyboard model

Binding on the build. Everything here is a consequence of two shipped facts: every step change is a **path** change (D8), and the Router already owns title, scroll and focus for path changes (`router.tsx:196-211`).

### 9.1 Heading outline

**`h1` = the step's own heading. `h2` = sections inside the step. There is no `h3` in this flow.**

| URL | `h1` |
|---|---|
| `/book`, `/book/slot`, `/book/slot/{dressId}` | `booking.stepSlot` |
| `/book/details[/{dressId}]` | `booking.stepDetails` |
| `/book/terms[/{dressId}]` | `booking.stepTerms` |
| `/book/verify[/{dressId}]` | `booking.stepOtp` |
| `/book/confirm[/{dressId}]` | `booking.confirmTitle` |

**Ruling, and why this and not the boutique name.** The storefront's law is "`h1` = the page's subject, and there is exactly one, on every state including degraded ones" — `/dress/{id}` already takes the dress name over the boutique name for precisely that reason. The subject of `/book/slot` is *choosing a time*. The decisive property is the degraded case: a step-label `h1` is a **static i18n string, never fetched data**, so it survives the boutique fetch failing (D12), the terms 404 (D5), the empty-types list, the empty-slots list and every error code, **by construction**. No `catalog.essenceFallback` fallback is specified for `/book/*` because none can ever be reached. Declined: the boutique name as `h1` on every step (it vanishes under D12, which is the exact defect `DressPage.tsx:92-95` warns about) and a single constant flow heading with the step name demoted to `h2` (needs a new i18n key for no gain, and duplicates the stepper's current item one level lower instead of one level up).

Where a step shows the boutique's identity for reassurance, it renders as **body text, not a heading** — the outline stays `h1` = step.

`h2` is used for: the type picker (`booking.typeHeading`) on the slot step, the policy block (`booking.termsHeading`) on the terms step, and the confirm screen's two facts blocks (`booking.confirmWhen`, `booking.confirmWhat`). No level is skipped anywhere, and no `h2` renders without its `h1` above it — including in every degraded branch. **A step's sub-heading takes its level from the outline and its size from the type scale independently**: `DressPage.tsx:210` ships `<h2 className="text-sm text-ink-muted">` and that precedent governs. An `h2` here does not have to be `--text-xl`.

### 9.2 Focus on step change — the Router's move is the only move

**Ruling: no booking step calls `focus()` on navigation, and no step heading carries `tabindex="-1"`.**

`router.tsx:196-211` runs on every `pathname` change: it writes the title, scroll-resets to the top and calls `document.getElementById(MAIN_ID)?.focus()`. Every step transition in this flow is a `pushState` to a new path, so that effect fires for all four transitions and for the confirm landing. The `<main id="content" tabIndex={-1}>` target is already the skip link's destination and already the shipped focus destination for `/` → `/dress/{id}`.

Two reasons a per-step focus move is a defect and not a courtesy:

1. **It cannot win, and reads as if it did.** React flushes child passive effects before the parent's. `BookPage`'s effect runs first; the `Router`'s effect runs second and moves focus to `<main>` regardless. The step's `focus()` becomes dead code that a later reader will take for the working mechanism.
2. **It has nothing better to offer.** The `h1` is the first content inside `<main>`, so a screen reader reading forward from the focus point hits the step's own title immediately. Moving focus *to* the heading gains one saved keystroke and costs a competing focus call.

**The only two legitimate focus moves inside a step**, both of which happen without navigation:

| Trigger | Destination |
|---|---|
| Client validation fails on a forward submit | The **first invalid field**, with `aria-invalid="true"` and its message tied by `aria-describedby` |
| `OTP_INVALID` / `OTP_EXPIRED` returns from `/otp/verify` | Focus **stays** in the code field, its value selected. The message is `role="alert"` (§12) because focus never *arrived* at the control |

Both require a `ref` on `Input`, which `packages/ui` does not have — see §13, item 3, where it is a gate condition on the build.

Everything else — mid-flow conflicts (`SLOT_UNAVAILABLE`, `TERMS_STALE`, submit-time `NOT_FOUND`) — resolves by navigating to an earlier step, so the Router moves focus and the recovery message on the destination step is `role="alert"` so it is spoken from above.

### 9.3 One document title for the whole flow

`DOC_TITLE_KEYS` gains **one** entry: `book: "document.book"`, matching `RouteName`'s one new member. All five steps and both path shapes render under it.

**Why a per-step title cannot be written from inside the page.** The Router's effect re-runs on every `pathname` change and unconditionally assigns `document.title = t(DOC_TITLE_KEYS[match.name])`. React flushes child passive effects before the parent's, so a title written in `BookPage`'s effect on the same commit is overwritten milliseconds later by the Router's. `DressPage.tsx:81-83` gets away with the same pattern only because its write happens in a **later** commit, after its fetch resolves — and its own comment says so. A booking step has no fetch to hide behind on `details`, `terms` or `confirm`, so it has no later commit; a title that stuck on `slot` (which does fetch) and not on `details` is worse than one honest title. If per-step titles are ever wanted, **the Router effect must be the thing that reads `match.step`** — one edit, one place, no race. Recorded here so nobody tries it in `BookPage`.

### 9.4 Tab order, and the stepper's place in it

DOM order = visual order on every step (WCAG 1.3.2), at every width:

```
skip link  →  [ back link ]  →  [ stepper — not focusable ]  →  h1  →  step body  →  forward button  →  footer links  →  A11yMenu trigger
```

- The **skip link** is the first Tab stop on every step; it is the layout's, unchanged.
- The **back link** sits above the stepper at the block-start of the column, inline-start, matching `DressPage`'s shipped "חזרה לקולקציה" placement.
- The **stepper is not in the tab order at all**, and neither are any of its items.
- The **footer** and the **`A11yMenu` trigger** are the last stops, in that order — the trigger is rendered outside the page shell, after `<footer>`.

**Ruling: completed steps are NOT focusable links. PROPOSED — user confirms at the gate.**

The stepper is a non-interactive `<ol>` with `aria-label={t("booking.stepsLabel")}`; the current item carries `aria-current="step"`. A list exposes its item count and each item's ordinal to AT natively, so **no "step 3 of 4" string and no extra i18n key is needed** — the semantics do the counting.

Three reasons the items are not links:

1. Backwards navigation already exists and is unambiguous — one `<Link>`, to one known URL, labelled with what it does.
2. A link from `/book/verify` back to `/book/slot` would silently discard a live 600-second verification token, and a link has no way to say so first.
3. Only *completed* steps could be linked; the upcoming ones cannot. A stepper where two of four items are links and two are not is the moving-target defect, and rendering the dead ones as `href="#"` is banned outright by `qa-greps.sh:35`.

Declined: clickable completed steps (the conventional stepper affordance) — declined because every step's prerequisites are stateful, so the guard (D8) would bounce her back anyway and the link would be a lie half the time.

### 9.5 The in-app back control

`booking.backStep` is a **`<Link>` to the previous step's known URL**. Never `history.back()`, never `navigate(-1)`, never `router.back()` — the app has no `back()` primitive at all, `qa-greps.sh:34` greps for all three, and `router.tsx:12-18` records the absence as structural rather than a convention.

| Step | Back control target | Label |
|---|---|---|
| `slot` (first) | `/` — the catalog | `booking.backToCatalog` |
| `details` | `/book/slot[/{dressId}]` | `booking.backStep` |
| `terms` | `/book/details[/{dressId}]` | `booking.backStep` |
| `verify` | `/book/terms[/{dressId}]` | `booking.backStep` |
| `confirm` (terminal) | `/` — the catalog | `booking.backToCatalog` |

**Ruling: the first step's exit goes to `/` in BOTH paths — including the item-based path. PROPOSED — user confirms at the gate.** Declined: linking back to `/dress/{dressId}` on the item path. That URL can 404 — "dress archived before the flow" is a row in the spec's own state matrix — and the storefront has **no 404 route**, so an archived dress renders the catalog silently. The declined option therefore reaches the same destination via a label that lies about it. The chosen option also needs no new i18n key: `booking.backToCatalog` serves both the first step's exit and the confirm screen's, and both links point at `/`.

Where the dress binding must be preserved across a back navigation, it rides in the URL segment the link already carries (D9) — nothing is held in state that a back link can drop.

The glyph is **`→`, `aria-hidden`**, matching `DressPage.tsx:168`: in RTL the way back points inline-start-to-end, i.e. rightwards.

**Browser back is separate and also correct.** `popstate` is subscribed, so the browser's own button walks `confirm → verify → terms → details → slot` and then out of the flow to wherever she came from. Neither behaviour is built; both are asserted (§11, rows 22–23).

### 9.6 Enter and Escape

**Every step is a real `<form onSubmit={…}>` with the forward control as `type="submit"`.** That is the reason it is a form and not a `<div>` — implicit form submission gives Enter-to-advance on every step for free, with no key handler anywhere in the flow.

| Step | Enter |
|---|---|
| `slot` | On a focused slot or type chip, Enter/Space activates the chip (native radio). Anywhere else in the form, Enter submits → advances |
| `details` | Enter in `name` submits → advances. Enter in the `notes` `<textarea>` inserts a newline and does **not** submit — native, and correct: D7 deliberately permits LF in `notes` |
| `terms` | Space toggles the consent checkbox (native). Enter submits → advances; if the box is unchecked the client validation fires and focus moves to it (§9.2) |
| `verify` | Enter in the phone field or the code field submits. The resend control is a `<button type="button">` so Enter in a field never fires it |
| `confirm` | No form. No submit |

**Escape does nothing anywhere in `/book/*`, and that is deliberate: this flow contains no modal, no dialog, no popover, no sheet and no overlay of any kind.** D1 chose a route over a modal specifically so none exists — the shared `Modal` is fixed-width with no scroll handling and does not fit a slot grid or a policy text. Stated explicitly so that a later "just pop the policy in a dialog" is visibly a reversal of a gate decision rather than a small improvement. The only overlay reachable from these screens is the layout's `A11yMenu` disclosure, which is chrome, not flow.

---

## 10. Motion

Inherits the shared motion plan (`design-system/README.md`: page content fade + 8px rise 200ms ease-out; skeleton pulse 1.5s; toast slide from block-start). Booking-specific:

| Element | Animation | Duration / ease |
|---|---|---|
| Step → step transition | fade + 8px rise on the incoming step | `--motion-base` / `--ease-out` — inherited automatically, because a step change is a route change through the same Router |
| Stepper current marker | cross-fade of the current item's treatment | `--motion-fast` / `--ease-out`. **No filling progress bar and no sliding indicator** — a bar that fills toward a goal is the threshold-bar shape usage law 9 bans, and here it would also imply progress the guard can revoke |
| Slot / type / size chip selection | `background-color` + `border-color` transition | `--motion-fast` / `--ease-out`. No scale, no lift, no bounce |
| Forward button, submitting | the shipped `Button loading` — spinner replaces the label, width locked | component default. **This is the flow's only spinner** |
| Slot grid refetch (after `SLOT_UNAVAILABLE`, or a date change) | `Skeleton` pulse, 1.5s loop, in the grid's own box so the column does not reflow | `--animate-skeleton` |
| Terms body load | `Skeleton variant="text"` | `--animate-skeleton` |
| **Inline field error appearing** | **none — instant.** | — |
| **`role="alert"` recovery message appearing** | **none — instant.** | — |
| **OTP resend cooldown** | **none — and nothing re-renders at all.** Per **R3** the label is a fixed sentence with no seconds in it, so the button simply changes label once at 0s and once at 60s | — |

**Why the two "none" rows for errors.** An error that animates in delays the moment it is readable and competes with its own `role="alert"` announcement — the same defect class as manage-catalog's thumbnail-reorder ruling. An error is information the bride needs now, not an entrance.

**Why the cooldown is calm — the usage-law-9 boundary, stated.** A visible countdown is the single most recognisable promo-register device, and law 9 bans it. The OTP resend timer is not that: it is a **functional cooldown** telling her when a control becomes available again, not a scarcity clock manufacturing urgency — so a calmly-styled one *would* have been permissible. **Per R3 it carries no number at all**, which settles the question by removing it: `booking.otpResendWait` is the disabled button's own fixed label, `Button variant="secondary"` disabled, and it has **no progress bar, no ring, no colour change, no colour beyond the primitive's own disabled treatment, and no animation** — so there is nothing for `prefers-reduced-motion` to switch off. When the 60s elapse the label reverts to `booking.otpResend`, the button enables, and the polite region says so once (§12). If a numeral, a bar or a colour ramp is ever added, law 9 has been broken and the flow has acquired the sale-badge register.

`prefers-reduced-motion: reduce` ⇒ every transition above becomes `none`, the skeleton pulse goes static, and the cooldown text (which was never animated) updates unchanged. `theme.css:149-156` enforces this globally with `!important`, and the `A11yMenu`'s "stop animations" toggle applies the same kill via `:root[data-a11y-stop-motion]` — so **the flow must be fully operable and fully legible with zero motion, and it is, because no motion in this table carries meaning.** Nothing bounces, nothing autoplays, and the only spinner is the submit button's.

---

## 11. State-matrix coverage map

**This map is checked mechanically against `specs/storefront-booking-ui.md` §State matrix.** Every row of that table appears below in its original order; every row marked **D** points at a section of this document. Sections referenced: §0 Scope · §1 Wireframe conventions + flow map · §2 S0 entry · §3 S1 slot · §4 S2 details · §5 S3 terms · §6 S4 verify · §7 S5 confirm · §8–§14 as headed here.

| # | State | Spec Design column | Where designed | Notes |
|---|---|---|---|---|
| 1 | Happy path, generic | D | §3 → §4 → §5 → §6 → §7 | The spine. §1 carries the flow map that links the five |
| 2 | Happy path, item-based | D | §2 (CTA carries the dress id) · §3 · **§4 (size chips — P2)** · §7 | Dress rides the path segment (D9) on every step's URL |
| 3 | Loading | D | §3 (types + slots) · §4 (dress detail, item path) · §5 (terms) | Skeletons, never spinners — `CatalogPage.tsx:139-141`'s ruling governs. §10 sets the pulse |
| 4 | No published terms → phone-only entry | D | **§2** (see ⚠ FINDING 1) · §5 for the re-accept variant | `GET /terms` → 404 (D5). Degrades to `ContactPanel` under `booking.noTermsByPhone`; under D12 to plain copy (`booking.contactUnavailable`, P5) |
| 5 | No active appointment types | D | §3 | `booking.noTypes`. The flow cannot start; exit is the contact panel, not a retry |
| 6 | Deposit-required type → phone-only | D | §3 | D3. `booking.depositByPhone` + `ContactPanel`; `deposit_amount_agorot` through `Price` (P4). **A non-deposit sibling in the same picker stays bookable** — the branch is per-option, never per-picker |
| 7 | Brides-only badge | D | §3 | D10. `Badge variant="muted"` + `booking.audienceBrides`. Labels, does not gate |
| 8 | Out-of-stock size selectable | D | **§4** (P2) | D4. `available: false` stays selectable under `booking.sizeUnavailable`. The chip is a radio, not a `Badge` — see §13 item 2 |
| 9 | No bookable times in the window | D | §3 | `booking.noSlots`. The state every new tenant ships in, so it is the *most* likely first render, not an edge case |
| 10 | Slot taken while she typed | D | **raised §6** (submit) → **recovered §3** | `SLOT_UNAVAILABLE` re-fetches slots and returns to the picker. Message `role="alert"` on the destination step (§12) |
| 11 | Terms republished mid-session | D | **raised §6** → **recovered §5** | `TERMS_STALE` re-shows and re-accepts the new version |
| 12 | Something vanished mid-session | D | **raised §6** → probe → **§3** (type) / **§4** (size) / **§2–§3** (dress binding dropped) | One code, three causes; the spec's probe is deterministic. `booking.typeGoneRepick` · `booking.sizeGoneRepick` · `booking.dressGoneGeneric` |
| 13 | Dress archived before the flow | D | §2 (entry read) · §4 | `NOT_FOUND` on `/dresses/{id}` drops the binding and continues generic — never a dead end |
| 14 | Token expired / spent | D | §6 | `PHONE_NOT_VERIFIED` → restart verification in place. `role="alert"` |
| 15 | Wrong or stale code | D | §6 | `OTP_INVALID` / `OTP_EXPIRED` → retry inline; focus stays in the field, value selected (§9.2) |
| 16 | OTP resend before cooldown | D | §6 · **§10** (calm rendering) · **§12** (not a live region) | Cooldown 60s, P3. `/otp/send` always answers 204 and the UI reveals nothing either way |
| 17 | Verification unavailable | D | §6 | `SMS_*` → honest dead end. **The one state with no way forward** — its exit must be the contact panel, never a retry that will fail again (§12) |
| 18 | Rate limited | D | §6 (OTP budget) · §3 (read throttle — the new terms endpoint spends it too) | `TOO_MANY_ATTEMPTS`. Both surfaces need the state; neither may assume the other owns it |
| 19 | Client validation failures | D | §4 (`name` > 80, `notes` > 500) · §5 (terms unchecked) · §6 (bad phone) | **One matrix row, three screens.** Focus-to-first-invalid + `aria-describedby` on all (§9.2, §12) |
| 20 | Confirmation | D | §7 | D6 — states the appointment in full, promises no SMS, `booking.confirmKeepScreen` |
| 21 | Confirmation loaded cold | D | §7 | Reload / iOS screenshot round-trip. Short "booked" state over `ContactPanel`; under D12, plain copy (P5). Never bounces to step one |
| 22 | Step entered without prerequisites | — | **test-only** — behaviour ruled in **§9** | Guard → `slot` (D8); `confirm` is exempt and never redirects. No screen to design: the bride sees the slot step, which row 1 and rows 5/9 already cover |
| 23 | Browser back across steps | — | **test-only** — behaviour ruled in **§9.5** | `popstate` walks the steps; back out of the first step leaves the flow. No screen to design: each destination is a step already designed |

**All 21 D rows have a home. No D row is orphaned.** Two structural notes the critic should read as findings rather than as coverage:

- **Row 4's home depends on how §2 scopes itself** — see ⚠ FINDING 1.
- **The state matrix is missing a row** that D12 makes reachable independently of rows 4, 6 and 21 — see ⚠ FINDING 2.

### ⚠ FINDING 1 — row 4's owner is ambiguous between §2 and §3, and exactly one must take it

The spec says the no-terms 404 degrades "the booking entry point" (D5). But the CTA lives on `/`, `/dress/{id}` and `/about`, and **the CTA cannot know about terms**: making it conditional would mean fetching `/storefront/terms` on every storefront page load to decide whether a button navigates — a fetch on every page for a state that is rare — and D1/D12 have already ruled the CTA unconditional (it navigates always, with no boutique data and no guard).

**Ruling: the terms fetch happens inside the flow, and the no-terms degrade renders at the slot step's URL in place of the whole flow. PROPOSED — user confirms at the gate.** The CTA's behaviour is unchanged in this state. Which section documents it depends on §2's scope: if §2 "S0 entry" covers the on-`/book`-mount orchestration, it is §2's; if §2 scopes itself to the CTA on the storefront pages only, it is §3's. **Assembler: confirm that exactly one of §2 or §3 designs this state, and that this map's cross-reference resolves.** A state owned by neither is how the "phone-only entry" branch ships as a blank screen.

### ⚠ FINDING 2 — the spec's state matrix has no row for "boutique fetch failed"

D12's stated consequence is that **all three** `ContactPanel` branches — the deposit note (row 6), the no-terms entry (row 4) and the cold confirm (row 21) — must degrade to plain copy when `useBoutique()` has nothing. That is a designed visual state with copy of its own (P5's `booking.contactUnavailable`), and it is reachable **independently of all three of those rows**: a tenant whose boutique fetch failed but whose terms *are* published and whose types are *not* deposit-required still hits it on the cold-confirm path.

The matrix is declared "the single source for states … nothing else in this spec re-enumerates them", and the design gate's obligation is defined as "every row marked D". A state that exists only in a decision-log entry is exactly the drift that table was written to prevent.

**Recommendation — amend `specs/storefront-booking-ui.md` §State matrix with one row, in the same PR as this gate:**

| State | Trigger | Design | Test |
|---|---|---|---|
| Boutique fetch failed → no contact fallback | `useBoutique()` error or null (**D12**) | D | unit |

Its design home is §2 / §3 / §7 (wherever each `ContactPanel` branch lives), its copy is P5, and the shipped precedent for the shape is `AboutPage.tsx:106-130`, which renders a `<p role="alert">` and **omits the contact card entirely** rather than printing empty rows. Tracked as **P8**.

---

## 12. Accessibility (IS 5568 = WCAG 2.0 AA — a floor, not a target)

### 12.1 Contrast ledger — every pair this flow relies on

Every figure below is a pair already computed and published, either in `tokens.md` or in `manage-catalog.md` §10.1/§10.2, cited against **the surface the pair actually renders on**. This design introduces **no new colour value and no unpublished pair** — that is a deliberate constraint on it, not a coincidence.

| Element | Foreground | Background | Ratio | Note |
|---|---|---|---|---|
| Step `h1`, back link's own text is gold (below), body copy on the page | `--color-ink` | `--color-bg` (cream) | **15.24:1** | tokens.md |
| Field labels, policy body, chip labels, headings inside a Card | `--color-ink` | `--color-surface` (paper) | **13.89:1** | tokens.md |
| Chip label inside a selected/white chip; confirm facts on a white block | `--color-ink` | `--color-surface-raised` | **15.75:1** | manage-catalog §10.1 |
| Forward button ("continue" / "submit") | `--color-ink` | `--color-gold` | **6.41:1** | gold as *background* only — usage law 1. The flow's only gold fill |
| Stepper **current** item label | `--color-ink` | `--color-bg` | **15.24:1** | weight 600 as well as colour — the current step is never colour-alone |
| Stepper completed + upcoming labels; hints (`phoneHint`, `notesHint`, `typeDuration`); the resend cooldown; `notes` counter | `--color-ink-muted` | `--color-bg` | **6.15:1** | tokens.md |
| Same, inside a Card | `--color-ink-muted` | `--color-surface` | **5.61:1** | tokens.md |
| `Badge variant="muted"` text — brides-only (`booking.audienceBrides`), out-of-stock size word (`booking.sizeUnavailable`) | `--color-ink-muted` | `--color-surface-raised` | **6.36:1** | tokens.md / manage-catalog §10.1 |
| Back link, and every in-flow link | `--color-gold-text` | `--color-bg` (cream) | **5.57:1** | the back link sits in the column *outside* every Card — cream, not paper (manage-catalog rev-4 finding 37) |
| Any link inside a Card (e.g. inside the policy block) | `--color-gold-text` | `--color-surface` | **5.08:1** ‡ | manage-catalog §10.2 |
| Selected-chip `✓` marker (`aria-hidden`, rendered text) | `--color-gold-text` | `--color-surface-raised` | **5.76:1** ‡ | manage-catalog §10.2; identical to the listed-chip `•` precedent |
| Inline field errors (`nameTooLong`, `notesTooLong`, `phoneInvalid`, `acceptRequired`) | `--color-danger` | `--color-surface` | **6.18:1** | tokens.md |
| `role="alert"` recovery messages rendered on the page column (`slotUnavailable`, `termsStale`, `otpInvalid`, `phoneNotVerified`, `tooManyAttempts`, `smsUnavailable`) | `--color-danger` | `--color-bg` | **6.78:1** | tokens.md |
| Deposit note lead (`booking.depositByPhone`), no-terms note (`booking.noTermsByPhone`), `booking.contactUnavailable` | `--color-ink` | `--color-surface` | **13.89:1** | **Ruled: not `--color-warning-text`, not `--color-danger`.** A deposit-required service is the boutique's flagship, not a caution; a boutique with no published policy is not the bride's error. These are explanations, and they render in the page's ordinary voice |
| Chip / input / checkbox / radio resting borders (non-text) | `--color-border-input` `#8A7A5E` | paper / white / cream | **3.69 / 4.18 / 4.04** ✓ | tokens.md line 29, **already carrying manage-catalog §12 item 3a's correction** — see §12.2 |
| **Selected** chip border, 2px (non-text) | `--color-gold-strong` | `--color-surface` / `--color-surface-raised` | **3.47 / 3.93** ✓ | tokens.md + manage-catalog §10.1. Non-text boundary only — it carries no glyph and no label |
| Focus ring (2px, 2px offset, non-text) | `--color-focus` | cream / paper / white | **5.57 / 5.08 / 5.76** ✓ | byte-identical hex to `--color-gold-text` |
| Card hairlines, stepper connector line | `--color-border` | — | decorative, 1.22 on paper | **never a load-bearing boundary.** The stepper connector carries no meaning the labels do not |

**Never used in this flow**: raw `--color-gold` on text (2.38:1, usage law 1) · `--color-gold-strong` on text or on any meaning-bearing glyph at any size — its only two appearances are the selected-chip border and, if §3 uses one, an `aria-hidden` ornament · `opacity` as a way to recess text · `--color-success` **anywhere, including the confirmation screen** (ruled: the confirm reads as a statement of fact in ink, not a transaction receipt in green; a success-green banner is the console's saved-state register and D6 makes this screen a *record*) · any colour not in `tokens.md`.

### 12.2 Three `tokens.md` corrections this flow depends on — all already landed

manage-catalog.md §12 item 3 escalated four `tokens.md` edits as gate conditions. **`tokens.md` at HEAD ships all of them**, and this flow — which is form-dense and depends on `--color-border-input` for the resting boundary of every chip, input, radio and checkbox — inherits the fixed values. Recorded so the critic does not re-file them and the build does not re-open them:

| Item | Status at HEAD |
|---|---|
| 3a — `--color-border-input` `#B9A98F` → `#8A7A5E` | **landed** (`tokens.md:29`, publishing 3.69 / 4.18 / 4.04) |
| 3c — `--color-focus` published ratio 4.86 → 5.57 | **landed** (`tokens.md:33`) |
| 3d — `--color-gold-strong` barred from rendered text including CSS `content:` | **landed** (`tokens.md:16`) |
| 3e — chips/badges move from `--radius-sm` to `--radius-full` | **landed** (`tokens.md:82,84`) |

### 12.3 Checklist

- [x] **Contrast** — every text pair ≥4.5:1 per §12.1, each cited against the surface it actually renders on; every non-text boundary (`border-input` 3.69–4.18, selected-chip `gold-strong` 3.47–3.93, focus ring 5.08–5.76) ≥3:1. **This design introduces no new colour value and no unpublished pair** — every figure is already in `tokens.md` or in manage-catalog's ledger
- [x] **No opacity on text** — recession is carried by `--color-ink-muted` and by the `disabled` attribute (WCAG-exempt), never by an `opacity` value. The `Button` primitive's own `disabled:opacity-60` is the component's shipped affordance on a control, not a way to recess prose
- [x] **No colour communicates alone** (usage law 2) — the stepper's current item is `--color-ink` **and** weight 600 **and** `aria-current="step"`; a selected chip is a checked native radio **and** a 2px border **and** an `aria-hidden ✓` glyph; the brides-only state is the **word** `booking.audienceBrides` in a `Badge`; the out-of-stock size is the **sentence** `booking.sizeUnavailable`, and the chip stays selectable (D4) so nothing is signalled by dimming; the deposit branch is a **sentence** plus a contact panel
- [x] **Labels** — every input in this flow has a **visible** label; placeholder is never the label (usage law 3, and `Input`/`TextArea`/`Select` all make `label` a required prop, so this is enforced by types). The four labelled fields are `booking.name`, `booking.notes`, `booking.phone`, `booking.otpCode`. The consent checkbox's label is the visible accept sentence (`booking.acceptTerms`), not an `aria-label`. Every chip group is a `<fieldset>` with a visible `<legend>` (`booking.typeHeading`, `booking.pickDate`, and the size group's own). **Where a control has visible text, its accessible name begins with that text verbatim**, disambiguator appended after an em-dash (WCAG 2.5.3) — this bites the slot chips, whose visible label is a time and whose name must read `"10:30 — <date>"`, never `"התור בשעה 10:30"`
- [x] **Errors** — `aria-invalid="true"` + `aria-describedby` to the inline message on every field; focus moves to the **first** invalid field on a failed submit (§9.2). `Input`/`TextArea`/`Select` already ship this wiring with `role="alert"` on the message node, so the house contract needs nothing new — but note the primitives **overwrite a caller-supplied `aria-describedby`** (the `{...rest}` spread precedes the computed attribute), so any extra description must go through the `help` prop, never a hand-passed `aria-describedby`
- [x] **`role="alert"` vs `role="status"` — enumerated, one region of each per step at most.** `role="alert"` (assertive) exactly here, and nowhere else: **(1)** the `OTP_INVALID` / `OTP_EXPIRED` message on the verify step, because focus never left the code field so nothing *arrives* at the `aria-describedby`; **(2)** `PHONE_NOT_VERIFIED`; **(3)** `TOO_MANY_ATTEMPTS`; **(4)** `SMS_NOT_CONFIGURED` / `SMS_UNAVAILABLE`; **(5)** the mid-flow conflict messages `SLOT_UNAVAILABLE`, `TERMS_STALE` and the probed submit-`NOT_FOUND`, rendered at the top of the step they navigate back to — the Router puts focus on `<main>` *above* the message, so an alert is what makes it spoken; **(6)** the D12 / `useBoutique()`-failed notice, matching `AboutPage.tsx:106-130`'s shipped `<p role="alert">`. `role="status"` (polite) exactly here: **(7)** `booking.otpSent` after a successful `/otp/send`; **(8)** the resend button becoming available again when the cooldown reaches zero — **the same region as (7)**, so the verify step has exactly one polite region and never two. Errors reached *by* a focus move need only `aria-describedby` and get no region. **Never `aria-live="assertive"` on anything that ticks**
  - **The resend cooldown is never itself a live region.** manage-catalog §10.3's rule applies verbatim: a continuously-changing value is not a discrete event. **Per R3 there is no changing value to begin with** — the label is fixed for the whole 60s — so the only thing left is the **discrete** event, the cooldown ending, and that is what writes region (8). Had the seconds been rendered, binding a region to them would have announced sixty times, each interrupting the last; R3 removes the hazard rather than managing it
- [x] **Heading outline** — `h1` = the step (§9.1), `h2` = sections inside it, no `h3`, no skipped level, **and exactly one `h1` in every state including every degraded branch** — guaranteed by construction, because the `h1` is a static i18n string and never fetched data
- [x] **Keyboard** — every path in §9 is native: `<form>` + `type="submit"` for Enter, native radios for the chips, a native checkbox for consent, real `<a href>`s for back and exit. There is no key handler and no roving-tabindex widget in this flow. The stepper is not focusable and does not need to be (§9.4)
- [x] **Focus never lost** — explicit destination for every focus-moving event: step change → `<main>` (the Router's, the only one); failed validation → first invalid field; `OTP_INVALID` → stays in the code field with the value selected; mid-flow conflict → `<main>` of the destination step. **Nothing in this flow removes a focused node from the DOM** — the guard redirects rather than unmounting under standing focus, and no control disables itself on use except the resend button, which explains itself (below)
- [x] **Focus visible** — the shipped `focusRing` (`focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus`) on every interactive element: back link, exit link, every chip, every field, the checkbox, the resend button, the forward button. `outline: none` without a replacement is a review defect. `outline` + `outline-offset` only — no `border-radius` on the ring; browsers trace the element's own radius, which matters here because the chips are `--radius-full` pills
- [x] **Touch targets ≥44×44 at 375** — slot chips, appointment-type options, size chips, the resend button, the back link's hit area, the forward button (`Button size="md"` is `min-h-11` = 44px), **and the consent checkbox**: the `<label>` wraps the box and the sentence and carries `min-block-size: 44px`; the box itself renders 24×24 inside it (manage-catalog's `Toggle`-row ruling, applied to the new `Checkbox`). **`Button size="sm"` is `min-h-9` = 36px and is banned everywhere in `/book/*`** — it is under the floor and nothing in this flow is small enough to want it
- [x] **Disabled controls explain themselves** — two exist. The **resend button during cooldown** carries its reason on its own visible label (`booking.otpResendWait`, a fixed sentence with no seconds — R3), never on a detached line, because `disabled` removes it from the tab order and an `aria-describedby` *from* a disabled control is inert. A **deposit-required appointment type** is not disabled at all — it is selectable-looking but routes to the phone-only branch with a visible sentence (D3), which is why it needs no disabled treatment
- [x] **`<bdi dir="ltr">` on every Latin/numeric run — enumerated.** Slot times on every chip and in `booking.confirmWhen` · slot dates and the date input's rendered value · `booking.typeDuration`'s minutes · the `notes` character counter · the resend cooldown's seconds · any phone number in `ContactPanel`'s degrade copy · `dress_size` on the size chips and on the confirm screen. Two are **not** `<bdi>` wrappers but element-level `dir`: the **phone input** (`dir="ltr"` + `inputMode="tel"` + `autoComplete="tel"`) and the **OTP code input** (`dir="ltr"` + `inputMode="numeric"` + `autoComplete="one-time-code"`) — an input's own `dir` is the mechanism, and wrapping a field in `<bdi>` does not affect what it types. The **deposit amount is not on this list**: it renders through `Price`, which does `dir="ltr"` + `unicode-bidi: isolate` by construction, and a hand-written `₪` fails `qa-greps.sh:37`
- [x] **`lang` / `dir` inheritance** — `<html lang="he" dir="rtl">` is the document's, from `index.html`. **No booking screen sets `lang` or `dir` on a container**; the only `dir` declarations in the flow are the two inputs and the `<bdi>` runs above. A step that sets its own `dir` is a review defect
- [x] **Reduced motion** — §10; every transition `none`, skeletons static, the cooldown text unchanged (it was never animated). Verified under both `prefers-reduced-motion: reduce` and the `A11yMenu`'s `data-a11y-stop-motion` toggle
- [x] **Navigation semantics** — the stepper is an `<ol>` with `aria-label={t("booking.stepsLabel")}` and `aria-current="step"` on the current item. It is **not** `role="tablist"` / `role="tab"` and it is **not** a `<nav>`: its items are not links and not focusable (§9.4), and a `tab` role would promise arrow-key roving focus and panel switching that this control does not have. Same defect class as manage-catalog's console strip, resolved the same way. The list's native semantics carry the count and the ordinal, so no "step N of 4" string exists
- [x] **No promo/sale language anywhere** (usage law 9) — no discount badge, no countdown, no urgency copy, no threshold bar, no scarcity phrasing on a nearly-full slot list. **The single case that has to be defended is the OTP resend cooldown**, and §10 defends it: functional cooldown, muted text, no bar, no colour, no motion
- [x] **Axe, per new route, `withTags(["wcag2a","wcag2aa"])`** — six passes: `/book/slot`, `/book/details`, `/book/terms`, `/book/verify`, `/book/confirm`, and `/book/slot/{dressId}` (the item path's entry, which is the only shape where the URL carries a segment axe has not otherwise seen). Bare `/book` renders the slot step and is covered by the first
- [x] **Skip link** — the layout's, unchanged, first Tab stop on all six URLs, targeting `<main id="content" tabIndex={-1}>`. Nothing in this flow renders above it

### 12.4 The thing axe cannot catch, and a human must check: **no screen is a dead end**

Automated tooling verifies structure. It cannot verify that a bride who hits a wall has somewhere to go, and that is the one failure this whole feature exists to remove. **Every failure state in §11 must offer either a way forward or an honest, contactable exit.** The human pass walks the list:

| State | Way forward | Or: contactable exit |
|---|---|---|
| No published terms (4) | — | `ContactPanel`, or `booking.contactUnavailable` under D12 |
| No appointment types (5) | — | `ContactPanel` |
| Deposit-required type (6) | pick a non-deposit sibling | `ContactPanel` for this one |
| No bookable times (9) | change the date | `ContactPanel` |
| `SLOT_UNAVAILABLE` (10) | re-pick from a fresh grid | — |
| `TERMS_STALE` (11) | re-accept | — |
| submit `NOT_FOUND` (12) | probe → re-pick type / size, or continue generic | — |
| `PHONE_NOT_VERIFIED` (14) | restart verification | — |
| `OTP_INVALID` / `_EXPIRED` (15) | retype; resend after cooldown | — |
| `TOO_MANY_ATTEMPTS` (18) | wait and retry | `ContactPanel` |
| **`SMS_*` (17)** | **none — and there must not be a retry button that will fail again** | **`ContactPanel` is the whole screen.** The only state in the flow with no forward path; naming it as such is the honesty D6 demands elsewhere |
| Cold confirm (21) | — | short "booked" statement + `ContactPanel` — never a bounce to step one |
| Boutique fetch failed (⚠ FINDING 2) | — | plain copy, `booking.contactUnavailable` — no phone exists to render |

Also human-only, from the same class: **the flow has never been walked end-to-end with a screen reader by anyone.** `test-results.md:242` records "whether a screen reader can complete a booking" as unrecruited, and F14 is the feature that finally makes the question answerable. One VoiceOver/Safari pass and one NVDA/Firefox pass over the happy path plus states 10, 11 and 15, at 375, before this ships.

---

## 13. Queued for `components.md`

Rows to fold into `.planning/design/system/components.md` in the same PR series as the F14 build, per the precedent in manage-catalog.md §1.2 / §12 item 7. Items 1–3 are **new or changed component contracts a build reading `components.md` would otherwise not find**; item 3 is a **gate condition**.

### 13.1 New rows for the "Core primitives" table

| Component | Variants / notes | Extra states |
|---|---|---|
| `Checkbox` | one-shot consent and any future multi-select. Native `<input type="checkbox">` with **no role override** — the near-miss is `Toggle`, which *is* a native checkbox but hardcodes `role="switch"` with a closed prop list and no opt-out, and a switch announces on/off where a legal consent must announce checked/unchecked. Label REQUIRED and **visible**; the `<label>` wraps box + text and carries `min-block-size: 44px` with a 24×24 box (usage law 7); error tied via `aria-describedby` exactly as `Input` does | error, disabled |
| `RadioGroup` | the selectable chip this flow needs three times (appointment type, slot, size) and `Badge` cannot be — `Badge` is a non-interactive `<span>` with no selected state and no focus ring. `<fieldset>` + **visible** `<legend>`; native radios styled as pills at `--radius-full`; resting border `--color-border-input` (≥3:1), **selected** = 2px `--color-gold-strong` + `--color-surface-raised` fill + an `aria-hidden ✓` in `--color-gold-text`; ≥44×44 per option; `focusRing` on each. Per the spec's split rule this is the *primitive*; the slot **grid layout** stays app-local | error, per-option disabled |
| `Stepper` | non-interactive progress indicator. `<ol>` + `aria-label`, `aria-current="step"` on the current item; items are **not** links and **not** focusable (§9.4); labels never truncate to ordinals at any width (§8.3); no filling bar and no sliding indicator (usage law 9). The list's own semantics carry the count — the component ships no "step N of M" string | — |

**Deliberately NOT added: a form-level error summary.** The spec's §What `packages/ui` does not have lists one. With at most three fields per step, focus-to-first-invalid plus per-field `aria-describedby` is the complete WCAG 3.3.1 / 3.3.3 answer, and a summary block is a second copy of every message to keep in sync. Declined, recorded so a later reader can tell a decision from an omission.

### 13.2 Amendments to existing rows

| Row | Amendment |
|---|---|
| `BookingCTA` (Storefront composites) | **Currently reads**: "persistent bottom bar @mobile, inline @desktop; v1 action = contact panel (phone / WhatsApp deep-link) until E3 booking lands". **D1 makes the second clause stale.** Replace with: "persistent bottom bar @mobile, inline @desktop; action = navigate to `/book/slot[/{dressId}]` (E3 F14). Renders unconditionally — it needs no boutique data (D12) — and appears on `catalog` and `dress` only: `/book/*` ships no bar at any width, and its `A11yMenu` rests at `--space-4`" |
| `Input` / `TextArea` / `Select` | **Add `ref` to the prop interface** — `ref?: Ref<HTMLInputElement>` etc., the one-line shape `Button.tsx:12` already uses because React 19's ref-as-prop is not part of `*HTMLAttributes`. **GATE CONDITION on the F14 build**: `id` is `Omit`'d from all three and no `ref` is declared, so today **there is no way to programmatically focus a field** — which makes §9.2's focus-to-first-invalid and the `OTP_INVALID` focus-retention **unbuildable**, and those are the flow's two WCAG 3.3.1 behaviours. One line in three files; must land before or with the build that consumes this document |
| `Button` | **Needs a link path, or P1 does not ship as written** — `Button.tsx:53` hardcodes `<button type="button">`, `ButtonProps` has no `as` / `asChild` / `href`, and the `base` / `variants` / `sizes` class strings are module-private (`index.ts` exports only `Button`, `cn` and `focusRing`). So "an `<a href>` styled as the primary button" means either extending `Button` or hand-copying token-bearing Tailwind into the app. **Recommendation: extend `Button` with an optional `href` that switches the rendered element to `<a>`** and keeps every class string in one place. See §14 P1 |

### 13.3 …and one row queued against `.planning/design/qa-checklist.md`

§7's booking-CTA row currently enumerates three families (catalog+empty · detail · `/about`). **Add a fourth**: *"`/book/*` (all five steps, both path shapes) — **no** `BookingCTA` bar at any width, `A11yMenu` at `--space-4` not `--space-a11y-clearance`, page column reserves `padding-block-end: var(--space-16)`."* Same shape as manage-catalog §12 item 4's amendment against `manage-restyle.md`: until it lands, the checklist describes three CTA families when four exist, and spec Risk 6's "implicit default nobody chose" is exactly what an unchecked fourth family becomes.

### ⚠ FINDING 3 — the `A11yMenu` trigger can overlap the statutory footer on every storefront route, and `/book` inherits it

The `A11yMenu` trigger is `fixed`, 44×44 (`size-11`), at `inset-block-end: var(--space-4)` and `inset-inline-end: var(--space-4)` — a 60×60 footprint at the viewport's **inline-end block-end corner (bottom-left in RTL)**. `<footer>` is a **sibling** of `<main>`, carries `py-6` (24px) and wraps its four items with `flex-wrap`. At 375, scrolled to the end of a page whose footer has wrapped to two rows, the trigger sits over the footer's inline-end content — which includes the statutory **הצהרת נגישות** link. `qa-checklist.md` PRE-2 states the requirement ("the scrollable page reserves bottom padding ≥ the button's footprint") but `/about` ships `pb-8` (32px), under the 60px footprint, and page padding cannot clear the footer anyway because the footer is outside the padded element.

**This is not `/book`'s defect and `/book` must not invent a local fix.** It is `StorefrontLayout`'s, it predates F14, and it applies identically to `/`, `/dress/{id}`, `/about` and `/accessibility`. Recorded here because F14 is the first feature whose primary action is a full-width button at the block-end of the column, so it is the feature most likely to be blamed for it. **Escalated, not fixed**: raise against `StorefrontLayout` + `qa-checklist.md` PRE-2 as its own item, with the likely remedy being block-end padding on the **footer**, derived from the trigger's footprint via `calc()`, never a literal.

---

## 14. Open rulings and revision log

### 14.1 Gate proposals — the decisions the user confirms when approving this gate

- [x] **P1 — The storefront CTA becomes an `<a href="/book/slot[/{dressId}]">` styled as the primary button.**
  *Argument*: the Router's root click delegation (`router.tsx:180-194`) intercepts any same-origin `<a>` into a client navigation while letting modifier-, middle- and target-clicks fall through to the browser (`shouldIntercept`, `:105-146`) — so an anchor preserves open-in-new-tab, which `onClick` + `navigate()` destroys. `DressCard` already relies on exactly this. Absolute `href` required: the delegated handler pushes the raw `getAttribute("href")`.
  *Declined*: `<button onClick={() => navigate(…)}>` — a booking link that cannot be opened in a new tab is a regression on a page a bride reaches from an Instagram deep link.
  *Cost, stated so it is not a surprise*: (a) `Button` cannot render an anchor today — §13.2's amendment; (b) the CTA's implicit role changes `button` → `link`, which breaks **four** test query sites, not the three Risk 3 names — `AboutPage.test.tsx:282-283` and `:295` and `CatalogPage.test.tsx:152` fail loudly (safe), while **`CatalogPage.test.tsx:183` passes vacuously** (`queryByRole("button", …)).toBeNull()` is trivially true once the CTA is a link — the D12 inversion would go silently unverified) and **`DressPage.test.tsx:254`'s `toBeEnabled()` on an `<a>` is also vacuous** (jest-dom's disabled matchers apply only to `button`/`input`/`select`/`textarea`/`optgroup`/`option`/`fieldset`). Those two must be rewritten to assert the `href`, not the role's enabled state.

- [x] **P2 — The size chips live on the details step (§4), not the slot step.**
  *Argument*: the spec never places them, and D11 has already given the slot step the appointment-type picker plus the date control plus the grid. The size is a property of the *dress binding*, which is what the details step already collects around (`name`, `notes`).
  *Declined*: the slot step (three decisions on one screen at 375) and a step of their own (a fifth step that exists only on the item path, doubling the flow's shape).

- [x] **P3 — OTP resend cooldown = 60 seconds.**
  *Argument*: long enough that a real SMS has time to arrive before she assumes failure, short enough that a lost message is not a dead end. `/otp/send` answers `204` unconditionally, so the client owns this number entirely.
  *Declined*: 30s (invites a second send before the first arrives, spending the per-phone budget) and 120s (reads as punishment on the one screen where she is already anxious).
  *Constraint*: it renders per §10 — muted text, no bar, no colour, no motion — and per §12 it is never itself a live region.

- [x] **P4 — `deposit_amount_agorot` is shown, rendered through `Price`.**
  *Argument*: `research/insights.md:34` is explicit — "typed appointment menu w/ duration+deposit shown upfront (**never hide fees mid-flow**)". Showing the number is what makes D3's "book this one by phone" read as information rather than as a wall.
  *Declined*: naming the deposit requirement without the amount (she then has to phone to learn the price of phoning).
  *Constraint*: `Price` only — `qa-greps.sh:37` bans the `₪` glyph in `apps/storefront/src` outright, and `Price` requires a `hiddenLabel` even when `visible` is true.

- [x] **P5 — One new i18n key beyond the spec's inventory: `booking.contactUnavailable`.**
  *Argument*: D12's consequence — all three `ContactPanel` branches degrade to plain copy when `useBoutique()` has nothing — has no key in the spec's list, and `ContactPanel` renders an **empty flex box** when every channel is absent (every child is behind a truthiness guard), so the degrade must be a branch at the call site rendering a `<p>`, not a prop. `AboutPage.tsx:106-130` and `he.ts:184-185`'s `statement.coordinatorNoChannel` are the shipped precedents for both the shape and the string.
  *Constraint*: the string must be **name-free** — `coordinatorNoChannel` interpolates `{{name}}`, which is by definition unavailable here, and the fallback if a name is ever wanted is `catalog.essenceFallback`.

- [x] **P6 — One further new i18n key: `booking.continueStep`, the forward label on steps 1–3.**
  *Argument*: the inventory carries **one** forward label (`booking.submit` / `submitting`) for **four** forward actions. Steps 1–3 advance; step 4 commits an appointment. One string cannot honestly be both — a "שליחה" on the slot step promises a booking three screens early, and a "המשך" on the verify step under-states an irreversible commitment on the screen where a cancellation policy has just been accepted.
  *Declined*: reusing `booking.submit` on all four (as above) and adding four per-step labels (three of them would be identical).
  *Scope*: `booking.submit` / `booking.submitting` are then reserved for the verify step's commit. The gate's copy author owns both strings.

- [x] **P7 — The booking column is `max-inline-size: 640px`, gutters `--space-4` → `--space-6`, no third step.**
  *Argument*: byte-identical to `/about`, the storefront's only other reading-and-forms surface. §8.1 has the reasoning and the Tailwind-`xl`-is-1280 trap.
  *Declined*: 1200px (the catalog's lookbook width; unreadable as a form measure) and 720px (the console's form width, borrowed into a customer screen for no reason).

- [x] **P8 — Add one row to the spec's State matrix: "Boutique fetch failed → no contact fallback".**
  *Argument*: ⚠ FINDING 2. D12 makes it a designed state with its own copy (P5), reachable independently of rows 4, 6 and 21. The matrix is declared the single source and the gate's obligation is defined against it, so a state that lives only in a decision-log entry is exactly the drift the table prevents elsewhere.
  *Scope*: one row, `Design: D`, `Test: unit`, in the same PR as this gate.

**Gate outcome — 2026-07-29, all eight approved.** The copy sign-off walk (same session) added two decisions this design inherits:

1. **`booking.confirmTitleNamed`** — S5's `h1` renders "התור נקבע ב{{name}}" when boutique data is in memory and falls back to `booking.confirmTitle` ("התור נקבע") otherwise (§7 Q4 answered "yes"; two keys because an i18next string cannot be conditional; `{{name}}` precedent: `statement.coordinatorNoChannel`). The cold confirmation (§7.7) uses the fallback only if the boutique fetch has also failed — the boutique read is independent of the lost `201` payload.
2. **`booking.sizeUnavailableNote`** — S2's size-chip group gains one muted sentence below the group, rendered only when at least one chip is unavailable ("מידה שאינה כרגע בבוטיק אפשר להזמין במיוחד לקראת המדידה."). The ≤24-char in-chip phrase (R15) is unchanged and still mandatory; this is the longer warm form the chip cannot carry.

Copy deltas recorded in `copy.md` rev 3 that change no layout: `booking.audienceBrides` → "פגישת כלה"; `booking.noTypes` drops its written phone clause (FINDING 4 approved — the `ContactPanel` below it does that job); `booking.otpSent` softened ("שלחנו קוד בן שש ספרות למספר שהזנת. הוא תקף לחמש דקות."); `booking.confirmCold` reduced to the honest short form. Q5 closed by evidence (forfeit = % of the deposit; `owner-settings.md:23`, `terms_version.py:23`, `TermsSection.tsx:99-100`). Q3 closed by evidence (backend `normalize_israeli_mobile` accepts flexible input and keys the OTP token on the normalized form; `validatePhone` mirrors it).

**Housekeeping this design implies, carried by the build and needing no gate decision**: `booking.panelTitle` and `booking.close` become dead when D1 removes the modal — `i18n-keys.test.ts` checks used→defined and never defined→used, so nothing will fail if they are left behind; delete them in the same pass. And `errors` gains the six new keys of spec Risk 5 (seven `switch` cases, `SMS_NOT_CONFIGURED` and `SMS_UNAVAILABLE` sharing one).

### 14.2 Revision log

| Round | Date | Reviewer | Findings | Resolution |
|---|---|---|---|---|
| Assembly | 2026-07-29 | assembler, against the five parallel drafts | 6 cross-section conflicts on load-bearing structure: the `h1`'s owner, whether stepper items are links, whether the cooldown ticks, the forward label's key, the slot-grid columns, and the CTA's link mechanism | **R1–R6.** All six ruled; losing arguments retained in place and marked ⛔ |
| 1 | 2026-07-29 | `design-critic` (brand / tokens / the nine usage laws) | **NEEDS CHANGES**, AI-generic score 7/10. 6 HIGH, 2 MEDIUM. Verdict capped at 7 explicitly because parallel authorship left the five steps materially disagreeing on structure — "reads as *assembled*, not *designed*" | Structural disagreements resolved by R7–R31. The brand findings — that the gold-hairline identity, the phone-booking-as-legitimate-luxury-path framing, and size-unavailable-as-invitation all read as specific to this brand rather than generic — needed no change |
| 1 | 2026-07-29 | accessibility + dead-end review | 9 HIGH, 11 MEDIUM, 3 LOW. Reviewed the **assembled** doc, so R1–R6 were not re-filed. Found the flow's real terminal dead end (submit failing outside the designed set), the cold confirmation asserting a booking it cannot verify, and an unavailable size chip with no per-chip signal | **R13, R14, R15** (the three real defects) plus R7, R16, R17, R18, R28, R29, R30. Six items it confirmed as correct are recorded above as not-to-be-re-litigated |
| 1 | 2026-07-29 | spec-coverage + buildability | 10 HIGH, 13 MEDIUM. Verified every buildability claim against the shipped tree. Found four specs the shipped components **cannot execute**, seven strings needing bidi isolation that i18next cannot deliver, two rendered keys absent from the copy deck, and a proposal list whose numbers each meant two different things | **R9, R10, R19, R25** (⚙ verified against source), **R21, R22** (the sign-off instrument), plus R8, R11, R12, R20, R23, R24, R26, R27, R31 |
| Gate | 2026-07-29 | the user (product owner), decision session backed by code research | P1–P8 all approved; `copy.md` signed off end to end (61 rows); FINDING 4 ruling approved; §7 Q1–Q6 answered — Q3 and Q5 closed by code evidence rather than judgement; two keys added at sign-off (`confirmTitleNamed`, `sizeUnavailableNote`); four Hebrew cells changed (`audienceBrides`, `noTypes`, `otpSent`, `confirmCold`) | `copy.md` rev 3; this doc's status flipped to GATE APPROVED; build unblocked |

**What round 1 changed about the package's status.** Rev 1 was internally reconciled but not externally checked, and three of its rulings were specified against components that cannot execute them — a class of error no amount of internal consistency would have caught. The two findings that most justify the round are R13 and R14: both are states where a bride is left unable to determine whether she has an appointment, which is the precise failure this feature exists to eliminate, and neither was visible from inside any single section.

**Round 2 is not scheduled and should not be run before the user's sign-off.** The remaining work is the user's — the Hebrew and the §14.1 proposals — and re-reviewing DRAFT copy would spend a round on strings that are about to change.
