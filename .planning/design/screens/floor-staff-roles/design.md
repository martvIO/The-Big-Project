# Screen: Floor staff cards + break status (F57 — `FloorPanel`, a panel on F34's board and the `floor` section's whole screen)

**Date**: 2026-07-31 · **Status**: **DESIGN GATE SELF-APPROVED.** Interview **Q2** named exactly two novel interaction patterns for this run — F34's shift board and F42's capacity matrix (`LOOP-STATE.md:1054`, `rulings_2026_07_31`). A staff-cards panel assembled from F34's shipped shell is neither, so there is **no prototype and no `design-critic` pass** at this gate, and every `P-` in §8 carries a resolution rather than a question. **What that costs is stated rather than hidden**: the one thing a human reviewer would have caught here is SC 2.2.2, and §7.4 is where it is discharged.
**Designer**: Claude · **Consumes**: `.planning/specs/floor-staff-roles.md` (**D1–D14**, Gate 1 self-approved under Q1) · `.planning/design/system/tokens.md` (**binding**) · `.planning/design/screens/design-system/manage-restyle.md` (**binding**) · `.planning/design/screens/shift-board/design.md` **Revision 2** (this panel attaches to that board and inherits its rulings whole) · `.planning/design/screens/manage-staff/manage-staff.md` (F51's shipped staff surface — the role words and the self-marker come from there, not from here) · `packages/ui` and `apps/manage` **as shipped**
**Copy**: `copy.md` in this directory — every Hebrew string with its untranslated `ar` value (Interview Q3 / pre-decided #47 / the 2026-07-31 languages ruling).
**Prototype**: **none, deliberately.** The two questions F34's prototype existed to answer — is a five-second beat usable, is one-tap check-in right under a thumb — were answered there and the mechanisms are now shared code (spec **D10**, `usePoll`). This panel introduces no beat, no control shape and no state that F34 did not already put in front of the user.

**What this deck is NOT.** It is not a redesign of F51's «צוות» section. F51 shipped add / edit / deactivate as PR #25 and this feature widens its role `<select>` from two options to five and fixes the ternary that widening breaks (spec **D14**). That is three lines in `StaffSection.tsx`, it has no new screen state, and it is out of this deck's §1–§7 entirely — §8 **P-8** records it so a reader does not go looking.

---

## 0. Scope

The console gains an **eleventh section** — `nav` key `floor`, label «הצוות בקומה» — and **one new component** that renders in two places. (`App.tsx:18-27` is a **ten**-member `SectionKey` union with ten `NAV` rows; `i18n.test.ts` already calls F51's the seventh nav item, F52's the eighth and F17's the ninth, so F57's is the eleventh. An earlier draft of this line said "eighth" and it was a stale count, not a layout claim.)

| Surface | Who sees it | Shape |
|---|---|---|
| A panel **below** F34's board, on the `board` section | owner, shift_manager | `<FloorPanel/>` after `<BoardSection/>` in the same `space-y-6` stack (spec D11) |
| The **whole** `floor` section | reception, sales_assistant, seamstress | the same `<FloorPanel/>`, alone |
| The role `<select>` in «צוות» | owner | three more `<option>`s — **P-8**, not designed here |

**Zero new `packages/ui` components and zero new variants.** Everything is `Card`, `Badge`, `Button`, `EmptyState`, `Skeleton` and the two shipped `lib/` helpers (`isolateLtr` — `lib/booking.tsx:32`; `jerusalemTime` — `lib/jerusalem.ts:35`). Checked against the shipped files rather than assumed: `Badge.tsx` already exports `success` / `warning` / `neutral`, which is exactly the three-value status vocabulary this panel needs today and after F36; `Button.tsx:35-39` gives `md` a `min-h-11` (44px) and applies `focusRing` unconditionally at `:62`. **No new colour pair enters the ledger** (§6).

### Binding inheritances (obeyed, not restated)

From **`manage-restyle.md`**: 720px content cap at every breakpoint; the three-register split (an **outage** is `text-ink-muted`, a thing-she-must-fix is `text-danger`, a nothing-failed **notice** is `text-warning-text`); `EmptyState` over a blank column; inline muted cues over Toasts; **no `role="tab"` anywhere**; **never override a `packages/ui` component's own utility from the call site** (F15 F-6 — `cn()` is a plain join and the consumer loses, which is why the `Card`'s `p-6` is not touched here either).
From **`tokens.md`**: the gold law (`--color-gold-strong` never carries text — **it appears on this screen zero times**); focus ring on every control; ≥44×44 touch targets; no raw px in app code; `prefers-reduced-motion` is already global (`theme.css:155-163`).
From **`shift-board/design.md` Revision 2**: the freshness row is the whole live-ness contract and is **never announced and never `aria-hidden`** (its **F-1**, accepted into the spec's a11y floor); the poll may never write into a live region (D11); a live region is written **only when its value actually changes** (its **F-7**); a tick may not repaint while a pointer is down (its **F-8**); the `{401, 403}` terminal pair are two states, not one; pause/resume is one button whose **name** changes, never `aria-pressed`; resume fetches immediately and at the **base** interval.
From **`manage-staff.md`**: the role word carries the role and the colour never does; `staff.roleOwner` / `staff.roleShiftManager` / `staff.selfMarker` are **shipped keys, reused not re-declared**.

### Explicitly NOT here — with the spec's reasons

| Not shipped | Reason |
|---|---|
| **`occupied` status, room labels, "she's with a client"** | Spec **D9**: `occupied` is F36's `fitting_room_assignments` index, a table that does not exist. `StaffCardStatus` has two inhabitants and a set-equality test pins them. The card grows a third status word and a `neutral` Badge in F36's PR, with **no new colour** (§2.3). |
| **Dispatch, take-next, push-assign, the waitlist** | F58's, on this same payload. |
| **SOS, the full-screen alert** | F37's. |
| **Break history, "who was on a break when", a duration** | No table (spec D2). The two audit rows are the only record and nothing reads them. The card says *since when*, which is the whole of what the shift manager can act on. |
| **A maximum break length or an auto-end sweep** | Spec D7: nothing schedules a break's end, because every automatic end is a guess about a person's shift and there is no roster to guess from (F40's). **F-6**. |
| **On-shift / off-shift marking, a roster** | Pre-decided #33 → F40. "Live status" here means available-or-on-a-break, never rostered. |
| **A staff avatar, a photo, a phone number, an email** | Spec D9: the card is a name, a role and a status. F51's owner-only wire shape carries the email; this payload is read by five roles and deliberately does not. |
| **A second poll interval, a frequency picker, a "live" claim** | The constants come from `usePoll` (spec D10) and this panel introduces no number of its own. §8 **P-7**. |
| **Any highlight, shimmer, pulse or flash when a card changes** | F34's D11, §7.3. |

---

## 1. The panel — mobile 375, loaded (state **F**)

**375 is the primary case.** Pre-decided #27 puts the console on each staffer's own phone, signed in as herself, and for reception / sales_assistant / seamstress this panel is the **entire product**. A reception tablet is one more signed-in device.

⚠ **The diagrams below are drawn LEFT-TO-RIGHT, for legibility in a Markdown file. The rendered panel is RTL.** So in the shipped console every run inverts: **inline-start is the physical RIGHT and inline-end is the physical LEFT.** The name starts at the physical right; §5's "the control aligned to inline-end" and §6's `justify-end` put the control at the physical **left**. This deck ships **no prototype and no `design-critic` pass** (header), so the ASCII block is the sole visual source — a builder implementing the drawn order ships a mirrored panel that passes axe, passes every named vitest assertion, and reads wrong to the only users who will ever see it. The block is not redrawn in RTL because a hand-mirrored ASCII diagram is one more thing to keep true; this sentence is cheaper and says the same.

```
+------------------------------------------------+
|  … <BoardSection/> above, on the board section  |   owner / shift_manager only
+------------------------------------------------+
|  <main #console-main tabIndex=-1, max-w-720>   |
|                                                |
|  צוות בקומה                                     |   h2, tabIndex={-1} (§7.2 focus rescue),
|                                                |     --text-lg font-semibold ink
|                        עודכן 14:07  [ השהיה ]   |   FRESHNESS ROW — one flex line, justify-end,
|                                                |     NOT announced, NOT aria-hidden (§1.1).
|                                                |     time in <bdi dir="ltr">, --text-sm ink-muted.
|                                                |     Pause control at the inline-end: Button
|                                                |     ghost md, 44px, WCAG SC 2.2.2 (§2.4)
|                                                |
|  <p role="status" tabIndex=-1>  (empty at rest) |   the ONE announced region — user-initiated
|                                                |     outcomes only (§7.1)
|  +------ Card (surface, p-6) ---------------+   |
|  | <ul class="divide-y divide-border">      |   |
|  | ┌ <li> ────────────────────────────────  |   |
|  | │ דנה כהן            [ פנויה ]   זו את    |   |   name bare <bdi> font-semibold ink
|  | │ תופרת                                  |   |   role: muted words, NOT a Badge (§2.1)
|  | │                       [  להפסקה  ]     |   |   status Badge: the word carries it (§2.3)
|  | └                                        |   |   control on its own line at ≤767 (§5)
|  | ┌ נועה לוי           [ בהפסקה ]           |   |
|  | │ קבלה                                   |   |
|  | │ מאז 11:20                              |   |   the since-line — --text-sm ink, the card's
|  | │                       [   חזרה   ]     |   |     operative fact, not a caption
|  | └                                        |   |
|  | ┌ שיר אברהם          [ פנויה ]            |   |
|  | │ יועצת מכירות                            |   |   no control: a non-elevated viewer on
|  | └ </ul>                                  |   |     someone else's card (§2.2)
|  +------------------------------------------+   |
+------------------------------------------------+
```

- **Order is the server's and the client never re-sorts.** `StaffUsersRepository.list_live` is `ORDER BY created_at` with the reason already written in the repository — *"so the founding owner is first and the console's rows do not shuffle between page loads"* (`db/repositories/staff_users.py:36-44`). A five-second repaint is exactly the caller that sentence was written for.
- **Her own card is not hoisted to the top.** §8 **P-4**.
- **One `Card`, one `<ul className="divide-y divide-border">` — not a grid of `Card`s.** §8 **P-1**. The payload's type is named `StaffCard` and the brief says "cards"; at 375 a card and a row inside a card are the same rectangle, and nesting `Card` inside `Card` is shadow-on-shadow.
- **The Card's `p-6` is not overridden** (F15 F-6).
- **No day line and no aggregate.** §8 **P-3**.

### 1.1 The freshness row — inherited whole from F34, minus the half this panel does not need

Two things on one line, never announced, never `aria-hidden`:

| Element | Content | Register | Why |
|---|---|---|---|
| inline-end | `floor.updatedAt` → «עודכן 14:07»; `floor.staleAt` when a tick failed; `floor.pausedAt` when the loop is stopped | `--text-sm --color-ink-muted`, escalating to `--color-warning-text font-semibold` in the stale **and** the paused case | The freshness claim. It changes **only on a successful fetch**, so it is a claim the panel can keep. The escalation is F34's **P-6**, ruled and shipped, for the identical reason: correct-looking cards beside a grey notice are what gets scanned past |
| inline-end, after the time | the **pause / resume** control — `floor.pause` «השהיה» ⇄ `floor.resume` «חידוש» | `Button variant="ghost" size="md"` | **WCAG 2.0 SC 2.2.2 (Level A)**, spec **D12**. §2.4 |

**No `floor.summary`.** The board carries «הגיעו 3/12» because counting forty rows by eye does not answer "how many are still outside". A boutique's live staff list is single-digit — `list_live` returns the whole of it and every card is on one screen at 375 — so «פנויות 3/5» would restate what the reader can already see, and it would be a second thing to keep true. §8 **P-3**.

**One slot, three reasons the panel might not be current, and F34's precedence order applies unchanged**: terminal (the panel is gone) > paused/idle («מושהה · עודכן») > stale («אין עדכון מאז») > running («עודכן»). A stopped loop cannot fail a tick, so the stop is the cause in force and the resume control is the remedy — which also keeps «רענון» and «חידוש» off one line.

### 1.2 Placement — below the board, and why two pause controls is the answer rather than a problem

- **The panel renders after `<BoardSection/>`, never before.** Mechanical, not taste: the board scrolls its «עכשיו» divider into view once, on first rows (`BoardSection.tsx:321-333`), and the two panels resolve their first fetch at different moments. A panel *above* the board grows after that scroll and pushes the divider back out of view. Below, it cannot move anything above it. (Spec D11.)
- **Two independently updating regions carry two independent mechanisms.** One control governing both loops would mean lifting pause state into a shared parent, which is precisely the coupling spec D11 forbids — and it is the coupling that would make a floor tick repaint the board's forty rows. Declined.
- **What that costs is that the two controls must be distinguishable to a screen reader.** Their visible labels are identical («השהיה»), which is correct — each sits against its own freshness stamp and reads unambiguously to a sighted user. Their accessible names name their own region: `board.pauseAria` «השהיה — עדכון הלוח» (shipped, `BoardSection.tsx:526`) and `floor.pauseAria` «השהיה — עדכון הצוות». **Both start with the visible label**, so WCAG 2.5.3 label-in-name holds — see **F-2**, which is where the spec's own proposed string failed that test.
- **For the three floor roles there is exactly one control, because there is exactly one region.** That is the case that makes the panel's own control unmissable rather than merely correct: a seamstress has no board to borrow a pause from.

---

## 2. The card — anatomy, and the control matrix

### 2.1 What a card shows

| Slot | Content | Bidi | Notes |
|---|---|---|---|
| Name row | `display_name` + the status `Badge` + `staff.selfMarker` on her own card | **bare `<bdi>`** on the name | `dir="ltr"` on a Hebrew name is itself a bidi defect and it looks deliberate (`owner-bookings.md` §6.3). `font-semibold text-ink`, `break-words`, **no ellipsis ever** — a panel that abbreviates a colleague's name makes two colleagues look like one. «זו את» is F51's **shipped** key, reused (`he.ts:209`) |
| Role line | the role word through `ROLE_LABEL_KEY` | bare `<bdi>` | `--text-sm --color-ink-muted`. **Muted words, not a Badge** — §8 **P-2** |
| Since line | `floor.breakSince` → «מאז 11:20», **only when `break_started_at !== null`** | time in `<bdi dir="ltr">` | `--text-sm --color-ink` — on this panel it is the operative fact, not a caption (F34's arrival-line treatment). Absent entirely when she is available: an empty slot would be five lines of nothing, and its appearance is what §7.2's pointer hold exists for |
| Control | at most one `Button` (§2.2) | — | The **only** interactive element in the card |

**The card is not a button.** One action per card, and the card does not navigate anywhere — there is nowhere to navigate to. F51's «צוות» owns the staff record and is one nav item away for the one role that may edit it.

### 2.2 Which control exists — the two authorization axes, rendered

The panel renders **only the operation the server will accept** (the F15 discipline: *"rendering four buttons where three answer 409 is a trap; a disabled button with no explanation is worse than an absent one"*). Spec **D6** is the rule: **owner and shift_manager may toggle anyone; any staffer may toggle herself.**

| Viewer's role | Whose card | Control | `break_started_at` |
|---|---|---|---|
| owner / shift_manager | her own | **«להפסקה»** `Button secondary md` | `null` |
| owner / shift_manager | her own | **«חזרה»** `Button ghost md` | set |
| owner / shift_manager | a colleague's | same two, same variants | — |
| reception / sales_assistant / seamstress | **her own** | same two, same variants | — |
| reception / sales_assistant / seamstress | a colleague's | **none** | — |

**What a staffer without permission sees on a colleague's card: a name, a role, a status, and nothing else.** No disabled button, no lock glyph, no «אין לך הרשאה» line, no tooltip. Three reasons, and they are the same three every time this question comes up in this codebase: a disabled control with no explanation is worse than an absent one; an explanation would teach the permission model on a screen she opens fifty times a shift, to answer a question she did not ask; and any such affordance would be the client asserting a rule the server owns.

**The absence is COSMETICS and the frontend test asserts it as cosmetics.** The control is spec D6's service check, which compares an id from the request against an id from the **session** and runs **before any read of the target**, so the 403 is not an existence oracle. `App.tsx`'s own NAV comment already says this sentence about the nav array and it is true again here: the filter exists so she is not shown a door that answers 403, and the server is what closes the door.

**«להפסקה» is `secondary` and «חזרה» is `ghost»`, matching F34's check-in / undo pair exactly.** Starting a break is the ordinary forward act and gets the ink boundary that makes a target findable in a scan; ending one is the return to normal and is demoted but never hidden. `size="md"` on both, never `sm` — `Button.tsx:36`'s `sm` is `min-h-9` = 36px, under the 44 floor.

**Which card the control belongs to, for a sighted elevated viewer — answered rather than assumed.** For an owner or a shift manager every card carries an identical «להפסקה» in an identical position, and the person is carried only in the accessible name (§7.4). **The sighted answer is the row, and it is deliberate:** the `divide-y` list gives each control exactly one adjacent name block, the control is the only interactive element in its card (§2.1), and her own card carries the shipped «זו את». The mis-tap this leaves open — starting your own break instead of Noa's — costs one tap to undo and writes one reversible timestamp, and the post-hoc cue names the colleague («נרשמה הפסקה עבור נועה לוי.»). **Declined, and both were considered**: a confirmation step (F34's precedent is one tap for a reversible act, and a confirm on a fifty-times-a-shift screen is a tax on the common case); and rendering the name in the **visible** label on colleagues' cards only («להפסקה — נועה לוי», which would match the aria-label exactly and has room at 375 where the control already owns a full line). The second is the **recorded upgrade path** — one interpolated key, no new component, no new state — and it is the first thing to reach for if a pilot shows a mis-tap. It is not taken now because the design gate self-approved on the basis that this panel introduces no control shape F34 had not already shown a user, and a label that differs per card is one.

**Neither control is ever time-boxed and neither is ever disabled except while its own request is in flight.** The server takes no clock bound in either direction and no maximum break length (spec D7), so a control that vanished after an hour would be a lie the API contradicts — F34's **P-3**, same reasoning, different verb.

### 2.3 Status — the word carries it, the colour never does, and the brief's dots are declined

| `status` | Badge | Variant | Reinforcement |
|---|---|---|---|
| `available` | «פנויה» | `success` (`border-success text-success`, 5.56:1) | — |
| `break` | «בהפסקה» | `warning` (`border-border text-warning-text font-semibold`, 5.20:1) | the since-line «מאז 11:20» **and** the control reading «חזרה» — three text signals, no glyph |
| `occupied` — **F36, not here** | — | `neutral` is the slot it will take | the room label F36 adds |

**The brief's 🟢 / 🟡 / 🔵 are declined as glyphs and delivered as words.** §8 **P-5**. The requirement they encode — a status legible at a glance across a counter — is met by a bordered pill carrying a Hebrew word, which is what `Badge` is and what F51 already ships for the role (`StaffSection.tsx:303-305`, under the comment *"The WORD carries the role; the colour never does"*). Three specific reasons the emoji do not ship: an emoji is **announced** by a screen reader with a name the product did not choose and cannot translate (VoiceOver reads 🟢 as an English colour name inside a Hebrew sentence); the console ships **no icon vocabulary at all**, so the first glyph would be a convention with one member; and a coloured dot beside a coloured pill is the same fact twice, which is how a reader learns to read the colour and stop reading the word.

**F36 needs no new colour**, which is worth stating now because "we will need a blue" is exactly the sentence that gets a token added later: `neutral` (`border-border text-ink`, 13.89:1) is a stronger, more legible treatment than a blue would be, and the word «תפוסה» plus a room label is what will carry it.

### 2.4 The pause / resume control — the SC 2.2.2 mechanism

Identical in every property to the board's, which is the point: one shape, two regions, and `usePoll` owns the mechanism (spec D10) so what this panel owns is the control and its copy.

| Property | Value |
|---|---|
| Element | **one** `<button>` whose label changes — `Button variant="ghost" size="md"`. Not two buttons, and **not `aria-pressed`**: a toggle that changes both its name and its pressed state reads as two contradictory facts. The name is the state |
| Target size | `min-h-11` = **44px**, `px-4` → ≥76px wide |
| Position in the tab order | **first stop inside the panel**, before any card (§7.2) |
| Accessible name | `floor.pauseAria` «השהיה — עדכון הצוות» ⇄ `floor.resumeAria` «חידוש — עדכון הצוות», each starting with the visible label (**F-2**) |
| Announcement | on press, the `role="status"` cue carries `floor.paused` / `floor.idleStopped` / `floor.resumed` — user-initiated, exactly what D11 admits there |
| Focus after press | **stays on the control.** It renames, it does not unmount — moving focus would be the defect |
| Effect of resume | fetches **immediately**, at the **base** interval, never the backed-off one |
| Idle stop | the same control with a timer instead of a tap — `IDLE_STOP_MS` = 10 minutes from `usePoll`, F34's **P-8** resolved and shipped. Any tap, key, focus change or scroll resets the window |

**Declined: a frequency picker.** 2.2.2 is satisfied by any one of pause / stop / hide / control-frequency; a picker is a settings surface plus a persisted preference plus a second constant, and the panel would then have two places answering "how live is this".

---

## 3. The poll, made visible

### 3.1 What the user sees on a tick

| Tick outcome | What changes on screen | Announced |
|---|---|---|
| **Nothing changed** (the common case) | the «עודכן HH:MM» time, and nothing else | nothing |
| A colleague started a break | her Badge flips «פנויה» → «בהפסקה», the since-line appears (**the card grows ≈20px** — §7.2's hold), her control flips to «חזרה» where one is rendered | nothing |
| A colleague ended a break | the reverse | nothing |
| A staffer was added in «צוות» | a card appears at the list's **end** (`created_at` order) | nothing |
| A staffer was deactivated | her card leaves — **unless it holds focus** (§7.2) | nothing |
| A staffer's role was changed in «צוות» | the role word changes in place | nothing |
| The fetch failed | the freshness row flips to **F-stale**, and the next retry is further away than the last | nothing |
| The fetch succeeded after failures | the stale copy clears and the interval resets to the base | nothing |
| The fetch answered **401** | the loop stops; `floor.sessionEnded` replaces the panel | **yes** — `role="alert"` |
| The fetch answered **403** | the loop stops; `floor.accessEnded` replaces the panel | **yes** — `role="alert"` |

**No highlight, no fade, no colour wash on a changed card.** F34's D11, endorsed here on its own footing: a highlight that can fire every five seconds is a strobing screen for a whole shift, and it draws the eye to *what changed* when the question is *who is free*. Reduced-motion falls out of the same rule for free.

### 3.2 The six failure modes are `usePoll`'s, and this panel adds none

Spec **D10** moves all six into the shared hook — the single arming site, the `document.hidden` gate plus the `visibilitychange` immediate refetch, the 5s→60s backoff, the `{401,403}` terminal classification, the idle stop, and the monotonic generation behind `isCurrent`. **F34's `design.md` §3.2 is the description and it is not restated here.** Three consequences that are this panel's and not the hook's:

1. **The pointer hold is the caller's three lines and this panel must carry it** (spec D10: the hook deliberately does not own it). §7.2's last bullet is why it is not optional here — the since-line appearing on an earlier card is exactly F34's **F-8** hazard, at a shorter list.
2. **A break mutation's 403 is terminal, not an in-card error.** §8 **P-6**.
3. **`B-stale`'s copy stays interval-free**, inherited as `copy.md` §0 rule 9: no string names or implies a retry interval, because the backoff falsifies any number the moment it doubles.

---

## 4. States — the single source for this feature

Every state the spec's Frontend-changes list names, plus what is announced and where focus goes. **The list may not shrink.**

| # | State | Trigger | What she sees | Region / focus |
|---|---|---|---|---|
| **F-load** | First load | section opened | heading + `<Skeleton variant="text" lines={3} />`; **no** freshness row and therefore **no pause control** — see the SC 2.2.2 note under this table; the cue region carries `floor.loading` | the cue is `role="status"`, so loading **is** announced |
| **F** | Loaded, cards | 200 | §1 | nothing announced |
| **F-self** | Her own card | always — she is in her own tenant's live staff list | identical, plus the shipped «זו את» marker and a control that is always present whatever her role | — |
| **F-empty** | No live staff | 200, `staff: []` | `<EmptyState title={floor.empty} />` inside the Card — never a blank column. **Impossible in practice**: the caller is herself a live staff row, so this is a one-line guard against a payload that cannot arrive, not a designed screen | freshness row still renders — a panel that has stopped updating must still be able to say so |
| **F-fail** | **First** fetch failed | non-2xx / network on the initial load | `<p role="alert" className="text-sm text-ink-muted">` **`staff.loadFailed`** — the **outage** register, and a **SHIPPED key reused, not a new `floor.outage`** (`he.ts:205`; `copy.md` §5, §9 **F-10**) — plus a «רענון» `Button secondary md`. **The freshness row and its pause control DO render here** (see the note below), so the retry is one of two affordances rather than the only one | alert |
| **F-stale** | A poll failed **with cards on screen** | non-2xx / network on any later tick | **The cards stay.** The freshness inline-end flips to `floor.staleAt` «אין עדכון מאז 14:07» in `--color-warning-text font-semibold`, and a second `--text-sm` line appears under it with `floor.staleBody` + «רענון». The loop keeps trying, each failure pushing the next attempt further out. **Nothing on screen states the interval and nothing may** | **not announced.** Blanking to the outage message would throw away correct data to report a network fault |
| **F-paused** | She pressed «השהיה» | a tap on §2.4's control | The loop stops. **The cards stay and are not dimmed** — they were correct at «עודכן 14:07» and pausing did not make them wrong. Inline-end becomes `floor.pausedAt` «מושהה · עודכן 14:07» in `--color-warning-text font-semibold`; under it, `floor.paused`. The control now reads «חידוש». **No «רענון» in this state** — the resume control is the affordance and two similar Hebrew words on one line is worse than one | **announced once**, `role="status"`, `floor.paused`. **Focus stays on the control** — it renamed, it did not unmount |
| **F-idle** | The idle timer fired | 10 minutes with no interaction (`IDLE_STOP_MS`, F34's P-8) | Mechanically identical to **F-paused**. **One thing differs and it is the reason there are two states**: the body line is `floor.idleStopped`, which **names the cause** — a panel that stopped by itself and does not say why is indistinguishable from a panel that broke. It also ends the unattended-counter-tablet exposure without a kiosk mode or a session change | **announced once**, `role="status"`. Focus is wherever she left it: the timer fires precisely because she was not touching anything, so moving it would be a jump-scare |
| **F-401** | Session ended (deactivation) | any tick, or any toggle, answers 401 | **The loop stops.** The panel is replaced by `<p role="alert">` `floor.sessionEnded` + «רענון הדף». Cards are cleared: a dead session cannot vouch for them | `role="alert"` — assertive, once, and it cannot repeat because the loop stopped |
| **F-403** | Access ended (a mid-shift demotion, **or a refused toggle** — **P-6**) | any tick, or any toggle, answers 403 | Identical shape, **different sentence**: `floor.accessEnded`. Cards cleared for a second reason 401 does not have — the list is precisely what she is no longer permitted to see. **The body is generic by design and may not name a role** (`copy.md` §0 rule 10). **For the three floor roles this is the whole product going dark**, which is spec Risk 6 and is **F-7** here | `role="alert"`, once. The reload's honest limit is F34's **F-10**, inherited verbatim |
| **F-busy** | A toggle in flight | control tapped | **that control only**: `loading` on the shipped `Button` (spinner overlaid, label kept for width, `aria-busy`). Every other card's control stays live — one tap must not freeze the panel. **The poll does not tick while a mutation is in flight**, so the card cannot be repainted under the request | nothing announced yet |
| **F-ok** | A toggle succeeded | 200 | the card is patched **from the response** (spec D7 answers the full card), so the panel cannot disagree with itself. The freshness time updates. The cue carries `floor.breakStartedCue` / `floor.breakEndedCue` **including the colleague's name**. The cue then stays on screen until the next tap replaces it | cue is `role="status"`; **focus is restored to the tapped control** (§7.2) |
| **F-noop** | A repeat toggle | 200, nothing written (another staffer got there first) | **Identical to F-ok**, deliberately. The server keeps the first `break_started_at` and the card renders it; the cue still confirms. The outcome she wanted is the outcome that holds, and telling her she lost a race would be telling her she was wrong when she was right (F34's B-noop, spec D7's middle row) | as F-ok |
| **F-actfail** | A toggle on a vanished colleague | 404 `NOT_FOUND` — deactivated in the gap between the tick and the tap, or another tenant's id, which RLS makes indistinguishable | `<p role="alert" tabIndex={-1} className="text-sm text-danger">` **inside that card**, under the control — the **fix-this** register, and it must be in the card because a panel-level error names no colleague. Copy: `floor.error.notFound`. The next tick removes the card | alert, **focused** (§7.2) — the control it belonged to was `disabled` on tap and may unmount |

**Fourteen states, and the list may not shrink.** Every one of the ten the spec's Frontend-changes section enumerates is here; **F-self**, **F-noop**, **F-busy** and **F-actfail** are the four this deck adds by decomposition, and none of them is optional — F-noop and F-actfail are two different answers to the same tap.

**Where the SC 2.2.2 mechanism is reachable, in the two states that are not obvious.** The pause control lives on the freshness row (§1.1, §6), so "does the freshness row render" is the same question as "is there a 2.2.2 mechanism on screen" — and `usePoll` is **armed and backing off** in both **F-load** and **F-fail**, so content can begin auto-appearing in either.

- **F-load: no row, no control, and that is correct.** Nothing is auto-updating yet — there is no content on screen for a repaint to move, and a pause control over a skeleton pauses a fetch the user has not seen produce anything. 2.2.2 is not engaged until the first payload lands, at which point **F** renders the row. Stated here so a later reader does not reopen it.
- **F-fail: the row renders, and it must.** F-empty already states this rule for its own reason (*"a panel that has stopped updating must still be able to say so"*) and F-fail inherits it: the loop is alive and retrying on a widening backoff, so a viewer who wants it to stop must be able to stop it. The inline-end carries `floor.staleAt`, the control carries `floor.pause`, and «רענון» sits beside the alert as F-fail already says.

**State precedence.** A mutation's response is always the truth for its card (it *is* a `StaffCard`). A poll's response is always the truth for everything else. They cannot fight: the loop does not tick during a mutation and the mutation bumps the generation on settle.

---

## 5. Breakpoints — 375 / 768 / 1440

Mobile-first, and there is exactly **one** breakpoint branch in the whole panel — the same one F34 has, in the same place.

| Width | What is different | Why |
|---|---|---|
| **375** (primary) | The card is a two-part flex column: the text block (name + badge + role + since-line) on top, **the control on its own line, aligned to inline-end** | Arithmetic: 375 − 2×`--space-4` = 343 of shell, − 2×`--space-6` of `Card` padding = **295px** of card. A «יועצת מכירות» role word, a «בהפסקה» pill and a 44-high control on one line leave the name under ~120px, which ribbons «אלכסנדרה בן-דוד הכהן» into four lines. Dropping the control to its own line returns the name the full 295 and makes the target *larger*. The `Card`'s padding cannot be reduced from the call site (F15 F-6), so this is the lever that exists |
| **375, long name** | The name wraps and pushes the status `Badge` to the next line. `overflow-wrap: anywhere` on the name, `flex-wrap` on the name row, **no truncation and no ellipsis anywhere** | The card has vertical room it does not have horizontal room |
| **768** | The control moves to the card's inline-end on the **same** line as the text block (`sm:flex-row sm:items-center`). Still **one column** — no grid | 720 − 48 = 672 of card; a name column of ~500px is more line-length than a Hebrew name needs. **No two-column grid**: §8 **P-1** |
| **1440** | **Identical to 768.** The console never exceeds a 720px content column (`packages/ui/src/components/ConsoleShell.tsx:84` — the shell is in `packages/ui`, not `apps/manage`) and this panel is not the exception | A wall-mounted display board is not this feature (F59's) |

**The freshness row at 375 is not re-measured here and does not need to be.** F34's deck measured that exact row, at that exact width, in its prototype, with these exact strings: «עודכן 14:14» / «אין עדכון מאז 14:14» / «מושהה · עודכן 14:14» all fit **one line** beside a 44px ghost control at 343px, with no wrap and no horizontal overflow (`shift-board/design.md` §5). This panel's row carries **strictly less** — it has no «הגיעו 3/12» half (§1.1) — so it cannot overflow where the board's did not. **`flex-wrap` stays on the row anyway**, for F34's reason: the inline-end is the one slot whose string can grow, and a control squeezed under 44px is an accessibility regression rather than a layout one. No truncation, no icon-only fallback, no `sm:` branch of its own.

---

## 6. Component notes — exact tokens

| Element | Notes |
|---|---|
| Section heading | `<h2 ref={heading} tabIndex={-1} className="text-lg font-semibold text-ink">` — `CatalogSection.tsx:116`'s shape plus F51's focus-target treatment (`StaffSection.tsx:80-92`). `tabIndex={-1}` is the §7.2 rescue target and adds **no** tab stop |
| Freshness row | `<div className="flex flex-wrap items-center justify-end gap-3 text-sm text-ink-muted">` — `justify-end` rather than the board's `justify-between`, because there is no inline-start half. `items-center`, never `items-baseline`, now that the line carries a 44px control |
| Pause / resume | `Button variant="ghost" size="md"`, `aria-label` swapping with the visible label. No new variant, no `aria-pressed`, no icon |
| Paused / idle / stale body line | `<p className="text-sm text-ink-muted">` under the freshness row; «רענון» beside it **only** in the stale case |
| Cue region | `<p role="status" tabIndex={-1} className="text-sm text-ink-muted">`, empty at rest. **Written only when its value changes** (F34's **F-7**). ⚠ **`{{name}}` in the two break cues renders in a BARE `<bdi>`, NOT through `isolateLtr`** — that helper emits `<bdi dir="ltr">` (`lib/booking.tsx:32-46`), which on «נועה לוי» is the §2.1 defect. Needs a two-line `isolateBidi(text, value)` sibling in `lib/booking.tsx`, or `<Trans>`. `{{time}}` and `{{minutes}}` **do** go through `isolateLtr` — a numeric run is exactly what it is for. See **F-11** |
| Break control `aria-label` | `t("floor.breakStartAria", { name })` — a **plain interpolated string** and no bidi treatment at all. An `aria-label` takes no markup, so `<bdi>` cannot appear in one; there is nothing rendered to reorder, and a screen reader reads the name as text. Named here only because §7.4's bidi rule reads as if it covered every `{{name}}` and it does not |
| List | `<Card>` → `<ul className="divide-y divide-border">` — `BookingsSection.tsx:142`'s exact shape |
| Card row | `<li data-staff-id={id} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center">`; text block `min-w-0 grow space-y-1` |
| Name | `<bdi className="font-semibold break-words text-ink">` — bare `<bdi>` |
| Status Badge | `Badge variant={available ? "success" : "warning"}` — the Hebrew word carries the state (§2.3). One Badge per card |
| Role line | `<p className="text-sm text-ink-muted"><bdi>{t(ROLE_LABEL_KEY[role])}</bdi></p>` |
| Since line | `<p className="text-sm text-ink">` with the time in `<bdi dir="ltr">` via `jerusalemTime` — **no new formatter** (spec D13) |
| Self marker | `<span className="text-xs text-ink-muted">{t("staff.selfMarker")}</span>` — F51's shipped key and shipped treatment |
| Break controls | «להפסקה» `Button variant="secondary" size="md"`; «חזרה» `Button variant="ghost" size="md"`. `fullWidthMobile={false}` — a full-width button per card would be a wall |
| Loading | `Skeleton variant="text" lines={3}` — `aria-hidden`, so announcing is the cue region's job |
| Empty | `EmptyState title` only, **no body and no CTA** (§4 F-empty) |
| Retry / reload | `Button variant="secondary" size="md"` |
| In-card error | `<p role="alert" tabIndex={-1} className="text-sm text-danger">` |
| Terminal panel | `<p role="alert" className="text-sm text-ink">` + `Button variant="secondary"` — **the same treatment for 401 and 403**, different string. The shape is identical because the consequence is identical; only the sentence and the remedy differ |

**Contrast, from the tokens ledger — not eyeballed.** ink 13.89 · ink-muted 5.61 · danger 6.18 · warning-text 5.20 · success 5.56 · focus ring 5.57 · border (non-text boundary) ✓. **This feature introduces no new colour pair and no gold at all** — the board's «עכשיו» hairline is the console's only `gold-strong` and this panel has no divider to put it on. The ledger needs no addition at this gate.

---

## 7. The a11y contract — IS 5568 / WCAG 2.0 AA is a legal requirement (pre-decided #38)

### 7.1 Live regions — the three-region split, inherited whole

| Region | ARIA | Carries | Politeness |
|---|---|---|---|
| **The cue** (`<p>` above the list) | `role="status"` | first-load `floor.loading`, then **user-initiated outcomes only**: `floor.breakStartedCue`, `floor.breakEndedCue`, `floor.paused`, `floor.idleStopped`, `floor.resumed`. Empty at rest | **polite** — every string is the consequence of a tap she just made |
| **The list** | **no live attributes at all** | the cards | **off.** `role="log"` is the tempting wrong answer: it is for append-only chat, and this list mutates in place |
| **The freshness row** | **no live attributes**, and deliberately **not `aria-hidden`** | «עודכן 14:07» / the stale / paused copy | **off, but readable.** `aria-hidden` would make the panel's only honesty signal sighted-only — F34's **F-1**, accepted into the spec's own a11y floor and not a reviewer's decision to reopen |

**The poll may never write into any live region** (spec D12, verbatim and non-negotiable): a `role="status"` update every five seconds announces the whole staff list forever. The idle stop is inside the rule and not an exception to it — its trigger is her own inactivity, not the tick.

**And "write" means write, not change.** F34's **F-7** applies unchanged: assigning a non-empty string to a text node runs the DOM's string-replace-all and produces a real `childList` mutation inside `role="status"` even when the two strings are byte-identical. The cue is written **only when its value actually changes**, and the frontend test must drive **several consecutive ticks with the cue already populated** — a single-tick assertion passes against the broken version whenever the cue starts empty.

**The cue names the colleague** («נרשמה הפסקה עבור נועה לוי.»), for F34's reason: a cue that cannot say *which* person is useless exactly when it matters. This is a colleague's display name announced to a colleague, not a customer's — a smaller disclosure than the board's, on a payload every staffer can already read.

**`role="alert"` appears exactly three times**, and each is bounded: **F-401** (once per dead session, the loop has stopped), **F-403** (once per revocation, same), **F-actfail** (once per refused tap, bounded by her own tapping). None can be produced by the poll on its own.

### 7.2 Focus, and content moving underneath it

- **Cards are keyed by `staff.id`.** A repaint mutates text nodes inside a stable element, so focus inside a card survives every tick. One prop, and it is the most important line in this section.
- **After a successful toggle, focus is restored to the tapped control.** This is the bug class that has now shipped **twice** in this repo — F56 on the storefront and F34 on the board — and axe walked past it both times, because axe cannot see a focus move that never happened. `@boutique/ui`'s `Button` is `disabled={disabled || loading}` (`Button.tsx:57`), so the browser blurs the tapped control the instant the request starts. Unlike F34's check-in the control here does **not** unmount — it renames «להפסקה» ⇄ «חזרה» — so the correct destination is the control itself: an effect keyed on that card's busy state falling to `false` calls `ref.current?.focus()` **guarded on `document.activeElement === document.body`**, so it can never steal focus from somewhere she moved it in the meantime. That guard is F34's shipped shape (`BoardSection.tsx:298-306`).
- **After a FAILED toggle, focus moves to the in-card alert**, keyed on the error state rather than raised inside the handler — the alert node does not exist yet when the state is set (`BoardSection.tsx:308-319`, `BookingDetail.tsx`). **The failure path is the one that gets forgotten**: F34's success path compensated and its catch path restored nothing, and that was a Level A defect found in review, not in CI.
- **A card that leaves the list while holding focus hands focus to the panel `h2`.** The only way a card leaves is a deactivation in «צוות». F34 keeps its departing row alive with a «התור הועבר» note because the booking still exists and she might still act on it; a deactivated colleague's card has nothing left to say, so the cheaper shipped pattern applies instead — F51's own removal path already does exactly this (`StaffSection.tsx:80-92`: *"a completed removal falls back to the heading"*). One line, one existing pattern, **no new string and no stranded-card mechanism**.
- **Tab order**: skip link → header logout → nav buttons → `#console-main` → *(on the board section: the board's own stops)* → **the panel's pause / resume control** → **one stop per card that has a control** → the retry button when present. The pause control being the **first stop inside the panel** is a ruling, not DOM luck: a 2.2.2 mechanism placed after the content it governs is reachable only by walking the list that is repainting under the walk.
- **After a pause or a resume, focus does not move at all.** That control renames rather than unmounting.
- **The panel never moves the scroll position.** It has no divider to scroll to and nothing to auto-scroll.
- **A tick may not repaint while a pointer is down on the panel.** This is F34's **F-8** arriving at a shorter list and it is not optional: §2.1's since-line renders only when `break_started_at` is set, so a remote break starting on card 2 grows it by one `--text-sm` line plus a `--space-1` gap — **≈20px** — and slides every control below it down by that much. At 375 the control sits on its own line (§5), so it is exactly the thing that moves. A finger already travelling toward card 4's «להפסקה» during a repaint can land on the card above. **Mitigation**: `pointerdown` on the panel holds the next repaint, `pointerup` / `pointercancel` releases it; the loop keeps its own beat underneath, so a lost `pointerup` costs at most one interval and can never stall the panel. **Spec D10 puts these three lines in the caller's own `run`, not in `usePoll`** — so the hook will not supply it and the build must write it.

### 7.3 Motion

Nothing on this panel animates except the shipped `Button` spinner during a mutation and the `Skeleton` pulse on first load — both already frozen globally by `theme.css:155-163` under `prefers-reduced-motion`. No highlight on a changed card, no fade on an arriving one, no pulse on the freshness line. **This feature adds no motion rule because it adds no motion.**

### 7.4 The rest of the floor

**SC 2.2.2 Pause, Stop, Hide (Level A) — the row no tool will ever add for us, and the one a human reviewer would have caught at a gate this run self-approved.** Content that auto-updates, starts automatically and is presented in parallel with other content must offer **a mechanism for the user** to pause, stop or hide it. A staff panel repainting every five seconds for a whole shift is squarely that. Three things make this row different from every other item here:

1. **It is a legal bar.** Pre-decided #38 makes IS 5568 / WCAG 2.0 AA legally required for these staff screens, and Level A sits inside AA.
2. **`axe` cannot see it.** There is no axe rule for 2.2.2 — the criterion needs a human judgement about what counts as auto-updating. The failure mode is not "CI catches it late"; it is "**CI stays green and the product is non-conformant**".
3. **The only coverage is the named frontend tests plus this deck.** The spec pins them: the pause control stops the loop and resume fetches immediately; the idle stop fires and one interaction resumes. **They may not be dropped as redundant with the axe assertion** — the floor-program review says so about F34 in as many words, and F57 is the feature that adds the second such surface to the same screen.

**SC 2.2.1 Timing Adjustable (Level A) — named, and explicitly not this feature's to close.** `session_ttl_seconds` is 43200 (12h), under 2.2.1's 20-hour exception, unextendable and unwarned. The remedy is a session-model change owned by **F21**. What this panel does is stop the loop and say so honestly (**F-401**).

- **≥44×44 on every target**: both break controls, the pause / resume control, the retry and the reload are `size="md"` → `min-h-11`. At 375 the break control sits on its own line and is *wider* than the floor, not narrower.
- **Visible focus ring** on every interactive element — `focusRing` from `@boutique/ui`, applied unconditionally by `Button.tsx:62`. Nothing here sets `outline: none`.
- **Accessible names carry the visible label plus the person**: «להפסקה — נועה לוי» / «חזרה — נועה לוי». Five buttons all named «להפסקה» is a screen-reader dead end, and the name **starts with the visible string** so WCAG 2.5.3 label-in-name holds.
- **Status is never colour alone** (§2.3), **role is never colour alone** (it is muted words, and F51's Badge already carries the word), and **paused is never colour alone** — the `warning-text` escalation is reinforcement; the state is carried by «מושהה», by the body line and by the control's own label flipping to «חידוש».
- **Bidi**: `<bdi dir="ltr">` on times; **bare `<bdi>`** on display names and role words. `dir="ltr"` on a Hebrew name is the worse defect because it looks deliberate.
- **Headings**: the shell owns the single sr-only `h1`; the panel heading is an `h2` **beside** the board's `h2`, not under it. No `h3`s — the panel has no groups.
- **Content capped at 720px** at every width. **`A11yMenu` / `A11yStatementLink` are storefront-only**, so no fixed-chrome clearance applies.
- **An `axe` pass** runs over the panel in `__tests__/FloorPanel.test.tsx` — **and it is explicitly not sufficient**, per the three points above.

---

## 8. RESOLVED decisions — self-approved with the design gate, 2026-07-31

**All eight carry a resolution and none is an open question.** Each keeps its full reasoning, because the reasoning is what a later feature would have to overturn to reopen it. **The Hebrew remains the user's to edit post-merge** — the F15 P-1/P-5 and F34 precedent: a one-line `he.ts` / `ar.ts` edit after merge, never a rebuild.

| | Resolution |
|---|---|
| **P-1** | **One `Card`, one `<ul>`, one column at every width** — not a grid of `Card`s |
| **P-2** | **The role is muted words; the single Badge is the status** |
| **P-3** | **No aggregate summary line** on the freshness row |
| **P-4** | **Her own card is not hoisted**; server order, marked with the shipped «זו את» |
| **P-5** | **The brief's 🟢/🟡/🔵 ship as words in a `Badge`**, not as glyphs |
| **P-6** | **A toggle's 403 is terminal**, like a tick's |
| **P-7** | **No new numbers**: 5s / 60s cap / 10min idle, all from `usePoll` |
| **P-8** | **F51's staff surface is not redesigned** — three lines, no new state |

- **P-1 — RESOLVED: one `Card` containing a divided list, one column at 375, 768 and 1440.** The payload's type is `StaffCard` and the brief says "cards", but at 375 — the primary case — a card and a row inside a card are the same rectangle, and a `Card` inside a `Card` is a shadow on a shadow that `packages/ui` has no treatment for. At 768+ a two-column grid would buy one screen-line back on a single-digit list, at the cost of replacing `divide-y` with border management and adding the one breakpoint branch this panel does not otherwise have. **The upgrade path is recorded and cheap**: F36 adds a room label per card and F58 adds a dispatch control, and a card that has grown three lines is the moment a grid earns itself — at which point it is a `grid gap-3 sm:grid-cols-2` on the same `<li>`s.
- **P-2 — RESOLVED: the role is `--text-sm --color-ink-muted` words under the name; the card's one `Badge` is the status.** F51's «צוות» renders the role *as* a Badge and is right to — on that screen the role **is** the answer to the question the screen asks. Here the status is the answer and the role is context, and two pills in 295px teaches the reader to scan colours instead of words. F15's rule («exactly one Badge per row region, and the status owns it») is the same ruling arrived at from the other side. **The role word is still never colour-coded anywhere**, which is `manage-staff.md`'s rule and survives.
- **P-3 — RESOLVED: no «פנויות 3/5» summary.** The board's ratio exists because forty rows cannot be eye-counted. A boutique's live staff list is single-digit and fits one 375px screen, so the aggregate would restate what is already visible and become a second fact to keep true through every tick. If a pilot boutique ever runs a staff list long enough to need it, it is one interpolated string and `isolateLtr` unchanged.
- **P-4 — RESOLVED: no hoist.** `list_live`'s `ORDER BY created_at` exists so *"the console's rows do not shuffle between page loads"* (`db/repositories/staff_users.py:36-44`), and a five-second repaint is that comment's ideal caller. Hoisting her own card would give every viewer a different order for the same data — so two staffers standing beside each other could not point at "the third one down" — to save a scroll on a list of five. The shipped «זו את» marker already answers "which one is me" without moving anything.
- **P-5 — RESOLVED: words in a `Badge`, no emoji, no dots.** §2.3 is the full argument. The short version: an emoji is announced with a name the product did not choose and cannot translate; the console ships no icon vocabulary, so the first glyph would be a convention with one member; and a coloured dot beside a coloured pill is the same fact twice, which is how a reader learns to read the colour and stop reading the word. **The requirement the dots encode — legible across a counter — is met by a bordered pill with a Hebrew word in it.**
- **P-6 — RESOLVED: a break toggle that answers 403 puts the whole panel into F-403, exactly as a tick would.** It looks aggressive and it is correct. `usePoll.fail(error)` classifies a mutation's error on the same `{401,403}` rule the ticks use (spec D10's contract), so the alternative — an in-card alert plus a loop that keeps polling with a role the server just refused — would be the panel disagreeing with itself for up to five seconds and then doing the same thing anyway. The realistic cause is a mid-shift demotion between the last tick and the tap, which is the identical revocation the very next tick would have found. **A 404 is NOT terminal** and stays an in-card alert (F-actfail): a colleague vanishing is a fact about her, not about the viewer's access.
- **P-7 — RESOLVED: this panel introduces no constant.** `POLL_INTERVAL_MS` = 5s, `MAX_BACKOFF_MS` = 60s and `IDLE_STOP_MS` = 10 minutes are exported by `usePoll` (spec D10) and were ruled at F34's gate (its **P-1** and **P-8**). Two surfaces with two different beats on one screen would be a thing to explain and nothing to gain. If F29 halves the beat, it halves both.
- **P-8 — RESOLVED: F51's «צוות» is not redesigned and this deck does not cover it.** Spec **D14** is three lines: two `<select>`s gain three `<option>`s each, and `roleWord`'s two-branch ternary (`StaffSection.tsx:99-100`) becomes a lookup in the shared `ROLE_LABEL_KEY` record. **That ternary is a real defect this feature creates if it is missed** — after the migration it silently labels a seamstress «אחראית משמרת» — which is why it is named here rather than left to the build. `Record<StaffRole, string>` makes a missing member a type error; the i18n test makes a missing key a red test. **No new screen state, no new component, no copy beyond the three role words in `copy.md` §3.1.**

## 9. ⚠ FINDINGS

- **F-1 — on a forty-row day the panel is ~4.5 screens below the fold, for the two roles that also have a board.** The three floor roles land straight on it (it is their whole screen), but a shift manager on «לוח היום» scrolls the entire day's bookings to reach «צוות בקומה». The placement is forced: above the board it would push the board's one-shot `scrollIntoView` target out of view (spec D11, §1.2). **Not fixed here and the cheap remedies are both above this feature**: a second in-page skip link past the board (`ConsoleShell` owns skip links, and F34's own **F-4** already files the general version of this), or F36 grouping the floor panels into their own section once there are three of them. *Owner: team. Trigger: F36, which adds the second panel to the same stack.*
- **F-2 — the spec's proposed `floor.pauseAria` breaks WCAG 2.5.3 label-in-name, and this deck revises it.** Spec D12 proposes «השהיית עדכון הצוות». The visible label is «השהיה», and «השהיית» is a different word form — so the accessible name does **not** contain the visible label, and a speech-input user saying "השהיה" matches nothing. Revised to **«השהיה — עדכון הצוות»**, which is the exact shape the shipped `board.pauseAria` uses and which F34's deck justified on the same criterion. **This is a copy correction to the spec, recorded rather than folded in silently**, because a reviewer diffing the deck against D12 will otherwise read it as drift.
- **F-3 — `floor.breakSince` is «מאז {{time}}», not the spec's proposed «בהפסקה מ־{{time}}».** The status `Badge` immediately above already reads «בהפסקה»; repeating the word in the line under it spends 295px saying one thing twice, and it makes the two signals look like two facts. The deck's version keeps the three-text-signal rule intact (Badge word + since-line + the control reading «חזרה») with no duplication. Same class of change as F-2 and recorded for the same reason.
- **F-4 — two idle timers on one screen, and they will always fire together — visually AND audibly.** The board and the panel each own an `IDLE_STOP_MS` window from their own `usePoll` instance, but both are reset by the same global interactions (tap, key, focus, scroll), so in practice they stop within a frame of each other and she sees two «מושהה» stamps and two body lines. **The auditory half is the worse one and an earlier draft of this finding recorded only the visual half**: both body lines are written into a `role="status"` region, and `board.idleStopped` (`he.ts:488`) is **byte-identical** to the panel's proposed string, so a screen-reader user hears the same sentence twice, back to back, from two regions, with nothing in either naming which region stopped. The idle stop is the one 2.2.2 event that fires **without a tap**, so it is the one case where both regions announce automatically and simultaneously — and it is a regression against this panel's own rule that a stopped surface must say which surface stopped, which is the whole reason **F-idle** exists as a state separate from **F-paused**. **Fixed in copy, not in structure**: `floor.idleStopped` names its region — «עדכון הצוות הופסק אחרי {{minutes}} דקות ללא פעילות.» — the same treatment the two `aria-label`s already carry, and the same thing `floor.paused` already does by naming «רשימת הצוות». No new key, no new state, and `board.idleStopped` is untouched (spec D10 forbids editing `BoardSection`'s i18n in this PR). The **timers** are still **not merged**, because merging them means shared state above both panels — the coupling spec D11 forbids and the one that would make a floor tick repaint forty booking rows. *Owner: team. Trigger: F36/F58 adding panels three and four to the same screen — that is the point at which four idle notices become a design problem rather than a footnote.*
- **F-5 — no he/ar parity guard exists in this repo.** F57 adds ~33 keys to both `he.ts` and `ar.ts` by hand. F15's Risk 5, inherited by F34, inherited again. The mitigation is unchanged: `copy.md`'s table is the single source for **both** columns, so it is one file to one file. *Owner: team. Trigger: F45, the feature that makes Arabic selectable.*
- **F-6 — a break that outlives the shift is legible but never corrected.** Nothing ends a break but a tap (spec D7 — no clock bound, no sweep, no worker), so a staffer who taps «להפסקה» and goes home reads as on a break across days. **The since-line is the entire mitigation and it is a real one**: «מאז 11:20» on a card at 09:00 the next morning is obviously wrong to any reader, where a bare «בהפסקה» would not be. Deliberate, and it is why the timestamp is on the wire at all (spec D9). *Owner: user. Trigger: pilot feedback, or F40's roster — the first thing that could end a break honestly.*
- **F-7 — for the three floor roles, F-403 is the whole product going dark.** A seamstress whose floor read answers 403 sees a sentence and a reload button and nothing else — no dashboard, no bookings, no fallback, because those are exactly the surfaces her role is refused. That is correct (spec Risk 6) and it is thin. The copy is what closes the gap: `floor.accessEnded` points at a person rather than implying the button will help — F34's **F-10**, inherited whole, and the reason `copy.md` §0 rule 10 forbids naming a role in that body. *Owner: team. Trigger: the first pilot morning; the cheap remedy if it bites is a role-aware empty state, not a new door.*
- **F-8 — axe cannot see SC 2.2.2, and this run has no human design gate behind it either.** F34 at least had a deck the user could have read; this one is self-approved. So the named frontend tests — pause stops the loop, resume fetches immediately at the base interval, the idle stop fires, one interaction resumes — are the **sole** coverage of a legal requirement, on the second such surface in the product. **They must not be cut as redundant with the axe assertion**, which is exactly what the floor-program review warns about for F34 and applies twice as hard here. *Owner: team. Trigger: the code-review pass, and every later tidy-up of "redundant" a11y tests.*
- **F-9 — ten of this panel's strings are byte-identical to F34's and are still declared twice.** «השהיה», «חידוש», «רענון», «עודכן {{time}}», «אין עדכון מאז {{time}}», «מושהה · עודכן {{time}}», «ייתכן שהמידע אינו עדכני.», «העדכון חודש.», «תוקף החיבור פג…» and «רענון הדף» exist under both `board.*` and `floor.*`, so the day the user edits one she must edit the other or the console spells one fact two ways. **Both cheaper options are closed today**: reading `board.*` keys from `FloorPanel` makes the only screen three of the five roles can open depend on a namespace named for a screen they cannot; and lifting the ten into a shared `poll.*` namespace edits `BoardSection`'s i18n, which spec D10 forbids in this PR — `BoardSection.test.tsx` must pass **unedited**, and that rule is the only thing separating a faithful `usePoll` extraction from a subtly different one. **The upgrade path is the same second-caller logic this feature used for the hook**: F37, F41 and F59 are callers three, four and five, and the PR that adds the third set of duplicates is the one where `poll.*` is worth the rename. *Owner: team. Trigger: F37, the next polling surface.*
- **F-10 — `floor.outage` is NOT declared; the shipped `staff.loadFailed` is reused for F-fail, and the namespace objection that raises is answered here.** An earlier draft of §4's F-fail named a new `floor.outage`, while `copy.md` §5 ships no such key and reuses `staff.loadFailed` «לא הצלחנו לטעון את רשימת הצוות כרגע.» (`he.ts:205`). **`copy.md` is right and §4 is corrected**: it is the same sentence about the same subject, and two byte-identical strings under two keys is how a console ends up spelling one fact two ways the day somebody edits one of them — §0 rule 8, and F-9 already records that this panel carries ten such duplicates against its will. **The objection this raises has to be answered, because F-9 refuses the same move in the other direction**: F-9 declines reusing `board.*` on the grounds that those keys are namespaced to a screen three of the five roles cannot open — and `staff.*` is F51's **owner-only** section, i.e. strictly *more* restricted. The difference is what the namespace names. `board.*` names a **screen**, and ten strings read from a `board.` prefix on a panel with no board is a lie about where the reader is. `staff.loadFailed` names its **subject** — the boutique's staff list, which is precisely this panel's payload and which all five roles read. A key whose namespace matches its subject travels; a key whose namespace matches a screen does not. **This is the third copy correction to spec D13**, alongside F-2 and F-3, and it is the precedent for where F37, F41, F42 and F59 put their shared strings. *Owner: team. Trigger: F37's copy deck.*
- **F-11 — `isolateLtr` must NOT be used on `{{name}}`, and `copy.md` §7's register table said it should.** §2.1 and §7.4 are emphatic that display names take a **bare `<bdi>`**, because *"`dir="ltr"` on a Hebrew name is itself a bidi defect and it looks deliberate"*. But `copy.md` §7 claimed *"every interpolated value (`{{time}}`, `{{minutes}}`, `{{name}}`) is a single run, so `isolateLtr` is reused unchanged and no second helper is invented"* — and `isolateLtr` (`lib/booking.tsx:32-46`) emits **`<bdi dir="ltr">`**, which on «נועה לוי» is exactly the banned defect. It is also the only helper that exists, so "reused unchanged" points a builder straight at it, and §6's component table was silent on how the cue renders a name, so nothing broke the tie. **Resolved per interpolation**: `{{time}}` and `{{minutes}}` → `isolateLtr` (numeric runs; `dir="ltr"` is correct); **`{{name}}` → bare `<bdi>`**, which needs a two-line `isolateBidi(text, value)` sibling in `lib/booking.tsx` or a `<Trans>` — now named in §6 beside the cue region. An `aria-label` takes no markup, so the two `*Aria` keys interpolate plainly and are outside this rule. **Recorded as a deliberate divergence from F34 rather than drift**: the shipped board isolates **nothing** in its cues — `BoardSection.tsx:385-391` interpolates `customer_name` into a plain string and `:138` does the same with `{{minutes}}`. **No test is named for this and axe cannot see it**, unlike the SC 2.2.2 row, and IS 5568 makes it a legal surface. The failure case is a Latin-script display name («Anna Levi») inside a Hebrew sentence ending in a period, where the period jumps. *Owner: team. Trigger: the code-review pass; the cheap check is a rendered-DOM assertion that no `<bdi>` wrapping a name carries `dir`.*
