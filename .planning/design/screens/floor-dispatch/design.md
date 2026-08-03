# Screen: Floor dispatch — the waitlist panel, the tile's take-next control, and the five verbs (F58 — `WaitlistPanel`, the THIRD child of F57's shipped `FloorPanel`)

**Date**: 2026-08-03 · **Status**: **DESIGN GATE SELF-APPROVED.** Interview **Q2** names exactly two novel interaction patterns for this run — F34's shift board and F42's capacity matrix (`LOOP-STATE.md`, `rulings_2026_07_31`) — and a list of people with four controls per row, assembled from `Card`, `Badge`, `Button`, `Select` and `EmptyState` inside F57's shipped `FloorPanel`, is neither. **No prototype, no `design-critic` pass**, and every `P-` in §12 carries a resolution rather than a question. **The gate goes away; the design work does not** — this deck and `copy.md` are build tasks (spec **D17**, **D18**).
**Designer**: Claude · **Consumes**: `.planning/specs/floor-dispatch.md` (**D1–D19**, Gate 1 standing-approved) · `.planning/design/system/tokens.md` (**binding**) · `.planning/design/screens/design-system/manage-restyle.md` (**binding**) · `.planning/design/screens/fitting-rooms/design.md` (F36 — this panel is that panel's sibling and inherits every ruling in it) · `.planning/design/screens/floor-staff-roles/design.md` (F57 — both are children of that panel) · `.planning/design/screens/shift-board/design.md` **Revision 2** (F34's D11 live-region rule, D14 pause control) · `packages/ui` and `apps/manage` **as shipped**
**Copy**: `copy.md` in this directory — **it is canonical, this deck's inline Hebrew is illustrative.** It carries **fourteen corrections to spec D16**, one of which is a value that **cannot pass a shipped test** (§13 **F-2**).
**Prototype**: **none, deliberately.** The two questions a prototype would answer — is a five-second beat usable, is a one-tap reversible act right under a thumb — were answered at F34's gate and are now shared code (`usePoll`, `FloorPanel.mutate`). This feature introduces no beat, no poll, no pause control and no live region that F34, F57 and F36 have not already put in front of a user.

**What this deck is NOT.** It is not a redesign of the rooms panel: `RoomsPanel` gains **one control and one `describe()` branch** (§3) and nothing else. It is not a redesign of the staff cards: they inherit a walk-in's name through D10's `COALESCE` **for free** and change no markup. It is not a new console section — `App.tsx` is untouched and F58 adds **no nav row** (spec D15), which `i18n.test.ts` asserts rather than omits. It is not F59's wall board: that is a different app, a different poll and a different audience, and the only thing this feature owes it is `called_at` (spec D7).

**⚠ This is the deck for the feature that discharges TWO deployment gates.** `LOOP-STATE.md` `deployment_gates` names F58 as `cleared_by` for both F33 and F59. Three of this deck's surfaces are the discharge, not decoration: the **rows** are the first rendering of `queue_tickets` anywhere in the product; the **remove verb + duplicate line** (§7) are the buyer Ruling 3 has been waiting for; and the **five verbs** are what give `status` its writers, so a woman leaves F59's public board when she leaves the shop.

---

## 0. Scope

Three surfaces. All inside the shipped `<FloorPanel/>`, all reached by the two roles who see it under «לוח היום» and the three roles for whom it is the whole product.

| Surface | Who sees it | Shape |
|---|---|---|
| The **waitlist panel** — one row per waiting walk-in | all five roles | `<WaitlistPanel/>`, rendered by `FloorPanel` **below** `<RoomsPanel/>` and **above** the staff `Card` (spec D15) |
| The **take-next control** on each free, active room tile | all five roles | one `Button` added to `RoomsPanel`'s existing action row (§3) |
| The **row's three inline reveals** — assign, skip-confirm, remove-confirm | assign + call: all five · skip + remove: owner, shift_manager | markup inside the row's own `<li>`. **No `<dialog>` anywhere in this feature** (spec D4, Decision 21) |

**Zero new `packages/ui` components and zero new variants.** Everything is `Card`, `Badge`, `Button`, `Select` and `EmptyState`, plus the two shipped bidi helpers (`isolateLtr`, `isolateBidi` — `lib/booking.tsx`) and the shipped `elapsedMinutes` (`lib/elapsed.ts:23`). Verified against the shipped files rather than assumed: `Badge.tsx:4` exports `neutral | success | danger | muted | warning`; `Button.tsx:36-38` gives `md` a `min-h-11` (44px) and `sm` a `min-h-9` (36px, **under the house floor**); `Button.tsx:57` is `disabled={disabled || loading}`, which is the whole of §11.1 MOVE 2's difficulty; `Select.tsx:6` types `label: string` — so a `Select` label **cannot be bidi-isolated at all**; `EmptyState.tsx:14-16` renders `title` alone when no `body` is passed; `Card.tsx:12` bakes in `p-6`, which the call site may not override (`manage-restyle.md`, F15 F-6).

**One new colour pair enters nothing.** The ledger is unchanged (§10).

### Binding inheritances (obeyed, not restated)

From **`tokens.md`**: the gold law (`--color-gold-strong` never carries text — it appears on this screen **zero** times, and no control here is ever `primary`); focus ring on every control (law 4); ≥44×44 touch targets (law 7); no raw px in app code (law 5); no colour communicates alone (law 2); `prefers-reduced-motion` already global.
From **`manage-restyle.md`**: the 720px content cap at every breakpoint (`ConsoleShell.tsx:84`); the **three-register split** — an outage is `text-ink-muted`, a thing she must fix is `text-danger`, a nothing-failed **notice** is `text-warning-text`; `EmptyState` over a blank column; inline muted cues over Toasts; **never override a `packages/ui` component's own utility from the call site**.
From **`shift-board/design.md` Revision 2**: the poll may never write into a live region (D11); a live region is written **only when its value actually changes** (F-7); a tick may not repaint while a pointer is down (F-8); `{401,403}` is a terminal pair.
From **`floor-staff-roles/design.md`**: **which control EXISTS is the rendered form of the authorization axes** — no disabled button, no lock glyph, no «אין לך הרשאה» line, no tooltip; the WORD carries the state and the colour never does; a display name takes a **bare `<bdi>`** and a numeric run takes `<bdi dir="ltr">` (F-11); every `floor.*` poll string is shipped and reused unchanged.
From **`fitting-rooms/design.md`**: exactly **one `Badge` per row region** and the state owns it (§2.3 there, §2.3 here); "greyed" is a token swap and **never `opacity-*`**; **no truncation and no ellipsis on a person's name, ever**; the tile alert has two registers and **neither is red**; the cue **names the act or the room and never the client**, because the region is persistent.

### Explicitly NOT here — with the spec's reasons

| Not shipped | Reason |
|---|---|
| A second poll loop, a second freshness row, a second pause control, a second `role="status"` | Spec **D15** and the LOOP-STATE ruling in as many words. `WaitlistPanel` is a **child**. `lib/usePoll.ts` gets a **zero-line diff** |
| A thirteenth nav section, a «תור» row, any `App.tsx` change | Spec D15. The queue is content of the floor, not a destination — and `i18n.test.ts` asserts the absence (`copy.md` §0.1) |
| A row-level «סיימתי» / done control | Spec **D5**, and §6 here. FINISH is the shipped room-tile release, extended. A second finish path would leave the shipped release able to strand a ticket `in_service` forever — the defect this feature exists to remove |
| A wait-time colour, an SLA threshold, anything that fires on elapsed minutes | The number is displayed; **nothing watches it**. Spec Out-of-scope (pre-decided #28), and F36's identical absence |
| Bride-priority ordering, any sort control, any filter | Spec Out-of-scope. FIFO by arrival; `visit_type` is rendered and **nothing sorts on it** |
| Auto-merge, auto-hide or reordering of duplicate entries | Spec **D8/D9** and §7. The panel flags; a human decides |
| A restore / undo for a removed entry | Spec D8. Recorded as the upgrade path; the two-step confirm is the guard |
| Virtualisation, pagination or a collapse at forty rows | §9. A boutique queue is 0–12 people; the bound is 100 and it exists for a griefing flood |
| A link from a row to `/q/{id}` | Spec **A29**. The row carries F33's position-page capability and **must never render it as an href** |
| A wall-mounted layout | F59's, shipped, and gated on this one |

---

## 1. Three panels on one screen — and they never sit side by side

⚠ **The diagrams in this deck are drawn LEFT-TO-RIGHT, for legibility in a Markdown file. The rendered pages are RTL** (`lang="he" dir="rtl"`). In the shipped console every run inverts: **inline-start is the physical RIGHT and inline-end is the physical LEFT.** The position number starts at the physical right; the `Badge` sits to its physical left; every `justify-end` action row puts its controls at the physical **left**. This deck ships **no prototype and no `design-critic` pass**, so these ASCII blocks are the sole visual source — a builder implementing the drawn order ships a mirrored panel that passes axe, passes every named vitest assertion, and reads wrong to the only users who will ever see it. **It is F36's §1 warning, repeated because this screen is now three panels deep.**

**375 is the primary case.** Pre-decided #27 puts the console on each staffer's own phone. For reception / sales_assistant / seamstress this screen **is** the product, and this is the panel they open it for.

```
+--------------------------------------------------+
|  <main #console-main tabIndex=-1, max-w-720>      |
|                                                   |
|  צוות בקומה                                        |   h2 — F57's, UNCHANGED, tabIndex={-1}
|  <p role="status">  (empty at rest)               |   the ONE announced region — F57's.
|                         עודכן 14:07  [ השהיה ]     |   FRESHNESS ROW — F57's, UNCHANGED.
|                                                   |     first tab stop inside the panel.
|  חדרי מדידה                    [ ניהול חדרים ]     |   h3 — F36's, UNCHANGED
|  +------ Card (surface, p-6) -----------------+   |
|  | ┌ חדר 1                        [ פנוי ]    |   |   FREE + a queue: TWO acts, and
|  | │ לקוחה — חדר 1                            |   |     take-next is FIRST (§3.1)
|  | │ [ ללא לקוחה                        ▾ ]   |   |
|  | │       [ קחי את הבאה ] [ תפיסת החדר ]     |   |   secondary · secondary
|  | ┌ חדר 2                        [ תפוס ]    |   |
|  | │ דנה כהן · תופרת                          |   |
|  | │ לקוחה  נועה לוי                          |   |   ← A WALK-IN's name, via D10's
|  | │ כבר 4 דק'                                |   |     COALESCE. New in F58, free.
|  | │      [ הוספת שמלה ] [ העברה ] [ שחרור ]  |   |   «שחרור» IS «סיימתי» (§6)
|  | └                                          |   |
|  +--------------------------------------------+   |
|                                                   |
|  ממתינות בתור                                      |   h3 — NEW, tabIndex={-1},
|  אין חדר פנוי כרגע.                                |     the focus-rescue target.
|  +------ Card (surface, p-6) -----------------+   |   panel-level line, ONCE (§4.2)
|  | <ul class="divide-y divide-border">        |   |
|  | ┌ <li data-entry-id> ──────────────────    |   |
|  | │ 1   מיכל אברהם              [ נקראה ]    |   |   position · name · ONE Badge
|  | │     מדידת כלה · ממתינה 23 דק'            |   |   muted meta line
|  | │       [ קראי ] [ שבצי לחדר ] [ דלגי ]    |   |   ghost · secondary · ghost
|  | │                            [ הסרה ]      |   |   ghost — elevated only, wraps at 375
|  | ┌ 2   נועה בר                              |   |
|  | │     שמלת ערב · ממתינה 8 דק'              |   |
|  | │     יש עוד כניסה פעילה היום עם            |   |   DUPLICATE — a notice-register
|  | │     אותו מספר טלפון.                     |   |     LINE, never a second Badge
|  | │       [ קראי ] [ שבצי לחדר ] [ דלגי ]    |   |
|  | ┌ 3   נועה בר                              |   |   her twin — flagged identically,
|  | │     שמלת ערב · הגיעה זה עתה              |   |     NOT hidden, NOT reordered
|  | │     יש עוד כניסה פעילה היום עם            |   |
|  | │     אותו מספר טלפון.                     |   |
|  | └ </ul>                                    |   |
|  +--------------------------------------------+   |
|                                                   |
|  +------ Card (the SHIPPED staff list) --------+  |   UNCHANGED markup. «תפוסה» + the
|  | ┌ דנה כהן                    [ תפוסה ]      |  |   occupancy line now names a
|  | │ תופרת                                     |  |   WALK-IN when D10 resolved one.
|  | │ חדר 2 · נועה לוי · כבר 4 דק'              |  |
|  +---------------------------------------------+  |
+--------------------------------------------------+
```

### 1.1 The order is FORCED, not conventional

Spec D15 rules the placement — rooms, then waitlist, then staff — and gives the reason as *"the rooms are what she acts on, the queue is what she acts from"*. That reason is true and it is not the load-bearing one. **The load-bearing one is that take-next lives on a room tile** (spec Decision 3, §3.1 here): put a queue of forty above the tiles and the feature's headline control is two screens below the fold at 375, on the surface the brief calls the phone in the shop. The panel order and the take-next placement are **one decision taken twice**, and a builder who reorders the panels for "the queue is more important" silently relocates the control the queue exists to feed.

The staff cards stay last. They are reference — who is on the floor, who is free, who forgot to end a break — and they are the only one of the three a staffer does not act on to serve the woman in front of her.

### 1.2 One tick, one pause, one announced region — now governing THREE regions

`WaitlistPanel` receives `waitlist`, `rooms`, `serverNow`, `fetchCount`, `selfId`, `role`, `paused`, `mutate`, `onWaitlist`, `onRooms`, `onCue` as props (spec D15). It owns no timer, no `usePoll` instance and no pause state. `RoomsPanel`'s contract, applied a second time — which is what makes the pattern reviewable rather than a one-off.

Three things fall out and each is an a11y win rather than an architectural convenience:

1. **One SC 2.2.2 mechanism for three repainting regions.** F57's D12 ruled two pause controls on the board screen acceptable *provided their accessible names distinguish the regions*, and F36 recorded that **three would start to be a defect**. F58 adds none: the shipped «השהיה — עדכון הצוות» now stops the staff cards, the room tiles and the queue, which is honest, because it stops the one tick that repaints all three. **§11.4 is why its shipped tests may not be cut.**
2. **One `role="status"`, so a room cue and a dispatch cue cannot talk over each other.** Three polite regions on one screen queue unpredictably across AT.
3. **One freshness claim.** «עודכן 14:07» is true of the staff, the rooms and the queue simultaneously, because they arrive in one response (spec D2 — the waitlist is two more statements on the tick's existing session, not a second fetch).

**`onWaitlist` is an UPDATER, never a finished list** — `applyRooms`'s shape (`FloorPanel.tsx:325-328`) and its review history. Two rows can be in flight at once (`busy` is per entry, `mutate` **counts rather than latches** — `FloorPanel.tsx:363-384`), so a handler that rebuilt the list from the `waitlist` prop it closed over erases the other handler's patch. This was F36's sharper MAJOR and it is **pre-paid**, not re-discovered.

**Every mutation patches from the SERVER's response, never optimistically.** That is what makes an idempotent second call render the *first* timestamp rather than this request's intent (§5.1), and it is what makes a lost race render the truth rather than the hope (§3.3).

---

## 2. The queue row — anatomy, and every fact it carries

### 2.1 What a row shows

| Slot | Content | Bidi | Notes |
|---|---|---|---|
| Position | `position` (1-based, **the server's `index + 1`**, never re-derived) | `<bdi dir="ltr">` | `text-ink-muted tabular-nums`. Fixed-width digits so a name column stays flush from row 9 to row 10 |
| Name | `entry.name` | **bare `<bdi>`** | `font-semibold text-ink break-words`. **No truncation and no ellipsis, ever** — this is the panel where two abbreviated «נועה»s decide who gets removed |
| Badge | «נקראה» when `called` | — | **At most one, ever** (§2.3) |
| Meta line | visit type «·» wait time | minutes in `<bdi dir="ltr">` | `text-sm text-ink-muted`. §2.4 |
| Duplicate line | the D9 flag, when `duplicate` | — | `text-sm font-semibold text-warning-text` — the **notice** register, §7 |
| Skip line | «דילגו עליה פעם אחת» when `skip_count >= 1` | — | `text-sm text-ink-muted`. Context for §5.2's confirm, not an alarm |
| Reveal | at most one on the whole panel (§2.5) | — | assign · skip-confirm · remove-confirm |
| Alert | at most one, `role="alert" tabIndex={-1}` | — | §3.4's two registers, unchanged |
| Action row | one to four `Button`s (§2.2) | — | `justify-end`, own line at ≤767 |

**The row is not a button and navigates nowhere.** There is nowhere to go: the entry *is* the record, and the one URL that would render it is the customer's own `/q/{id}` — a bearer capability this payload carries and the console **must never link** (spec A29, D10's rewritten privacy sentence).

**No phone anywhere.** `phone` is selected by D2's statement for D9's grouping and is not on the wire. The row cannot render it, and a fast test asserts no E.164-shaped string appears in the payload at all (spec A4).

### 2.2 Which control exists — the authorization axis, rendered

⚠ **A 403 is TERMINAL for the whole floor screen** — `usePoll.terminalOf` returns `"access"` for any 403 (`usePoll.ts:100`), `FloorPanel` returns the terminal `<section>` and clears every card (`FloorPanel.tsx:441-459`), and for the three floor roles that is the entire product going dark. So a control the server will refuse is not an in-row alert; it is a blank screen and a reload button.

| Control | Rendered for | Variant |
|---|---|---|
| «קראי» call | **all five roles** | `ghost md` |
| «שבצי לחדר» assign | all five — **and only when at least one room is free and active** (§4.2) | `secondary md` |
| «דלגי» skip | `ELEVATED.has(role)` — owner, shift_manager | `ghost md` |
| «הסרה» remove | `ELEVATED.has(role)` | `ghost md` |
| «קחי את הבאה» take-next (on the **tile**) | all five, on a free + active tile, **only while `waitlist.entries.length > 0`** | `secondary md` |

**No disabled buttons, no lock glyphs, no explanatory line — absence.** F57's three reasons hold unchanged, and the product cost is real and recorded rather than engineered around: **a reception staffer cannot skip a no-show or remove a duplicate; she asks a shift manager.** That is spec D11 and Conflict 8 — a three-role gate is *structurally forbidden* by `test_staff_role_gating.py:313-329`'s intersection classifier, whose docstring forbids relaxing it. This deck does not soften that into a tooltip.

**`size="md"` on every control, without exception.** `min-h-11` is 44px; `sm` is `min-h-9` = 36px and is under the house floor (`tokens.md` law 7). At four controls per row the temptation to reach for `sm` is at its highest in the codebase, which is why this is a rule and not a preference. `BoardSection.test.tsx:507-512` writes the trap out.

### 2.3 Exactly one `Badge` per row, and it is «נקראה»

| Fact | How it renders | Why |
|---|---|---|
| `called === true` | `Badge variant="warning"` «נקראה» | It is the row's **queue state** — she has been summoned and is still waiting. `warning` at 5.20:1 on paper, and the variant already ships `font-semibold` |
| `duplicate === true` | a **notice-register line** (§7) | A second `Badge` would be a second pill in 295px, which teaches the reader to scan colours instead of words — F15's rule, F36's **P-2**, arrived at from two directions |
| `skip_count >= 1` | a **muted line** | Context for the confirm that is about to appear, not an alarm. The confirm is the guard |

**Spec D17 proposes «at most two `Badge`s»; this deck ships one, and the divergence is F36's §2.3 precedence rule applied one surface over.** There the resolution was *occupancy wins the Badge and the out-of-service flag takes a word line*; here the queue state wins and the record-integrity flag takes a line. And the line is **strictly more useful than the chip it replaces**: «כניסה כפולה» names a category, while the manager's actual question is *which of these two Noas do I remove* — whose answer is «יש עוד כניסה פעילה היום עם אותו מספר טלפון», a fact she can verify by asking the woman in front of her. A two-word chip also cannot say **live**, and the twin being already `in_service` is the case spec D9 calls *"the most valuable thing on this panel to remove"*. ⚠ **CORRECTS D17 and D16**; `copy.md` §2 carries the value.

**No emoji, no dots, no glyphs.** F57's **P-5** and F36's, unchanged: an emoji is announced with a name the product did not choose and cannot translate, and this console ships **no icon vocabulary at all**, so the first glyph would be a convention with one member.

### 2.4 Wait time — anchored on the server, and NOT through `elapsedLine`

The row computes `elapsedMinutes(serverNow, entry.arrived_at)` — the shipped helper at `lib/elapsed.ts:23`, which carries the two load-bearing properties: the **clamp at zero** (the DB clock and the Python clock are two clocks) and the **anchor to the envelope's `server_now`**, so the number freezes exactly when the panel freezes. Nothing sets an interval to advance it.

⚠ **`elapsedLine` is NOT called, and this is a real trap rather than a preference.** Verified at `lib/elapsed.ts:31-37`: it returns `t("rooms.elapsedJustNow")` and `isolateLtr(t("rooms.elapsed", { minutes }), …)` — **hard-coded `rooms.*` keys**. Calling it here renders the ROOM's copy — «כבר 42 דק'», *already 42 min*, about a woman who has not been in a room — and leaves this feature's two keys **dead, green and unused**, because `i18n.test.ts` counts entries and never checks that a key is reached. So `WaitlistPanel` calls `elapsedMinutes` and does its own two-branch key selection in three lines. **No new mechanism, no date library** (F36's D17 forbids one) and **no edit to a shipped `lib/` helper with two shipped callers** — adding a key-prefix parameter buys nothing and puts `RoomsPanel.test.tsx` and `FloorPanel.test.tsx` at risk for a rename.

Two renderings:

- **≥ 1 minute** → «ממתינה {{minutes}} דק'». «ממתינה» and not «כבר»: the room's word says *this has been going on inside a room*; the queue's says *she is still standing there*, which is the fact a manager acts on.
- **< 1 minute (including the clamped negative)** → «הגיעה זה עתה». Two reasons, and the second is the schema's: «ממתינה 0 דק'» is bad Hebrew and it is what **every arrival reads for its first minute**; and `arrived_at` is `created_at`, which `0018_queue_tickets.py:29` gives `DEFAULT now()` — the **database** host's clock — while `server_now` comes from the service's Python one, so `arrived_at > serverNow` is representable.

⚠ **`arrived_at` is `created_at` and NEVER the sort key.** Spec D2 renamed the field and the rename *is* the fix: `COALESCE(requeued_at, created_at)` is rewritten on every skip, so anchoring the clock to it would reset a skipped woman's rendered wait to zero and the panel would read «הגיעה זה עתה» about someone who has been standing there forty minutes — on the number this panel exists to show, and the number §7's remove decision is partly a judgement about. Two facts, two columns.

**No hours branch, no pluralisation, no date library.** «ממתינה 95 דק'» is exactly the alarm a shift manager wants, and «ממתינה שעה ו-35 דק'» is a second key and an arithmetic branch to say the same thing less usefully. «דק'» is invariant in Hebrew, which is why one key covers 1 and 95 — **stated so nobody "fixes" it into an i18next plural rule**, which would be the console's first.

### 2.5 One reveal on the whole panel at a time

`openReveal` is a single `{ entryId, kind: "assign" | "skip" | "remove" } | null`, exactly as `RoomsPanel`'s `openDialog` is a single value. **Not one boolean per row.** With up to a hundred rows, per-row state is a hundred chances for two open confirms to be co-visible, and two questions on one screen is a screen that has asked the user which of two irreversible acts she meant.

The reveal renders **inside the row's `<li>`**, after the alert slot and before the action row, structurally identical to the shipped storefront two-step (`ManageBookingPage.tsx:414-460`): a `<p tabIndex={-1}>` carrying the **question**, then a `flex flex-col gap-3 sm:flex-row` pair of buttons.

---

## 3. TAKE-NEXT — the headline action, and its three outcomes

### 3.1 It lives on the room tile, and the tile now carries two `secondary` controls

Spec Decision 3: take-next needs a room, and a server-chosen "first free room" would derive a value from a count of existing rows — F13's read-then-write shape, needing a lock that F36's D3 argues at length is not this feature's shape. A tile-mounted control inserts three values the caller already holds.

**The consequence for the tile's hierarchy is real and is resolved rather than absorbed.** F36 ruled *one `secondary` per tile, and it is the act that ENDS the tile's current state*. A free tile with a non-empty queue now offers **two** acts that end it, serving two different populations: «תפיסת החדר» seats a **booked bride** picked from the client `Select` (the arrivals list, `GET /manage/floor/clients`), and «קחי את הבאה» seats **the first walk-in in the queue**. Neither is the lesser one, and demoting either to `ghost` would say it is.

**So both are `secondary`, and ORDER carries the hierarchy: «קחי את הבאה» is FIRST in the tile's action row** — at every width the one a thumb reaches first, and at 375 the first on the wrapped line. The rule that survives F36's, restated so a fourth panel can apply it: **at most one `secondary` per act-type, never `primary` anywhere on this screen, and never more than two `secondary`s on one region.** ⚠ **CORRECTS F36's §2.2 as an absolute**, and the criterion is unchanged — `primary` is gold, the storefront's CTA colour, reserved for save actions, and six gold buttons on one panel would be a wall.

**Rendered only while `waitlist.entries.length > 0`.** An empty queue removes the control rather than refusing the tap. §3.3's `QUEUE_EMPTY` therefore fires **only on a stale tile** — the last woman left between the render and the tap, which spec D3 calls *"an ordinary five-second race"* — and the next tick removes the control entirely.

### 3.2 Outcome 1 — a customer and a room

The response is `DispatchResult { room, waitlist }` (spec D15) and **both panels patch from the server's own rows in one paint**:

- The tile becomes occupied: `Badge` «תפוס», the acting staffer's name and role, **«לקוחה  נועה לוי» — the walk-in's name, resolved through D10's `COALESCE(Customer.name, QueueTicket.name)`** — and «זה עתה» on the elapsed line. Without D10's fifth join every dispatched walk-in would render as `rooms.anonymous` on the surface whose entire purpose is to say who is in the room.
- The row leaves the waitlist and every row below it moves up one position.
- **The staff card inherits it for free**: `occupancy_by_staff_id` is derived from the same `room_rows` (`floor/service.py:216-219`), so the acting staffer's card reads «תפוסה» with «חדר 2 · נועה לוי · זה עתה». No markup changes; the name arrives through the same `COALESCE`. It is also the third place a walk-in's name lands on this payload, which is why D10's privacy sentence is rewritten for the third time and not patched.
- **The cue**: «הלקוחה שובצה: {{room}}.» — the **room**, never her name (§11.2).
- **Focus**: back to the tile's current primary control, which is now «שחרור». `RoomsPanel`'s shipped `controlRefs` `Map` is keyed by **room id** and always resolves to whatever the tile's primary control currently is, which is why F36 built it that way — the free and occupied action rows have different shapes and React may or may not reuse the node.

**No highlight, no fade, no "dispatched" flash** anywhere on either panel. F34's D11 governs: a highlight that can fire every five seconds is a strobing screen for a whole shift, and it draws the eye to *what changed* when the question is *which room is free*.

### 3.3 Outcome 2 — «אין ממתינות בתור», and outcome 3 — a lost race, which is NOT an error

⚠ **A lost take-next race is a NORMAL outcome of this screen and the design says so in three places at once.** Two managers tapping «קחי את הבאה» on the same free tile inside one 5s tick is the **most likely collision in the entire feature** (spec D3, step 2b). It is not a fault, not an outage and not her mistake, and the screen must never frame it as one.

| Outcome | Wire | What she reads, where | Register | Focus |
|---|---|---|---|---|
| **The queue emptied** | 409 `QUEUE_EMPTY` | «אין ממתינות בתור.» in the **tile's** alert | **notice** — `text-warning-text font-semibold`. `outage: false` | into the tile alert (`RoomsPanel` MOVE 1) |
| **A colleague took the room** | 409 `ROOM_OCCUPIED` + `details.staff_display_name` | «דנה כבר בחדר הזה.» — **the shipped F36 sentence, reused, not re-keyed** | notice | as above |
| **…and released before the read** | 409 `ROOM_OCCUPIED`, **no `details`** | «החדר נתפס זה עתה. נסי שוב.» — shipped | notice | as above |
| **Her target already holds a room** | 409 `STAFF_OCCUPIED` | «היא כבר בחדר אחר: חדר 5.» / «היא כבר בחדר אחר.» — shipped | notice | as above |
| **Anything unmapped** | 5xx, dropped | `staff.loadFailed`, shipped | **outage** — `text-ink-muted`, no `font-semibold` | as above |

**Four things make the lost race read as *reporting* rather than *failing*, and every one of them is visible on the screen:**

1. **No cue is written.** `RoomsPanel.act()` sets `tileError` on failure and calls `onCue` only on success. The persistent region says nothing, because nothing was achieved.
2. **THE QUEUE IS UNCHANGED, and that is the rendered proof of spec D3a's rollback.** The woman at position 1 is still at position 1, with her wait clock unbroken, and the manager's next tap is a different tile. If this panel ever shows her gone after a refused take-next, the transaction design failed — and it is a state a manager would notice before any test would. **This is the single most important thing on this screen and the only one the customer can feel.**
3. **The tile keeps its own promise inside five seconds.** The next unforced tick repaints the refused tile as occupied by exactly the person the sentence named.
4. **Neither register is red.** `manage-restyle.md`'s split, F36's F-7: on this surface **nothing that can go wrong is her fault** — a 409 is two staffers reaching for one curtain and a 404 is a screen one tick behind. `--color-danger` appears on this screen in exactly one place, §5.3's confirm button, and it is a **choice** rather than a report.

**«אין ממתינות בתור.» is the empty state's title plus a full stop, deliberately.** The alert answers her tap; the `EmptyState` one panel below answers the screen. One fact, one vocabulary, two registers — rather than inventing a second sentence for a state she can already see.

### 3.4 The one shipped function this feature edits: `RoomsPanel.describe()`

Verified at `RoomsPanel.tsx:352-388`: `describe()` maps `ROOM_OCCUPIED`, `STAFF_OCCUPIED` and three 404 targets, then falls through to `{ text: t("staff.loadFailed"), outage: true }`. **A 409 `QUEUE_EMPTY` would take that fallback** and render «לא הצלחנו לטעון את רשימת הצוות כרגע.» in the muted **outage** register to a manager whose queue is simply empty — the exact failure spec D3 buys the error code to avoid, delivered in the wrong colour on top. One branch, `outage: false`, keyed `rooms.error.QUEUE_EMPTY` beside the four F36 sentences it renders alongside. Everything else in that file stays green with no edit.

---

## 4. PUSH-ASSIGN — the inline room reveal

### 4.1 The reveal

«שבצי לחדר» does not act. It reveals, inside the row:

```
┌ 2   נועה בר                                    ┐
│     שמלת ערב · ממתינה 8 דק'                    │
│                                                │
│     שיבוץ לחדר — נועה בר                       │   Select LABEL carries her name,
│     [ חדר 1                            ▾ ]     │     value LAST (Select.label is typed
│                                                │     `string` — isolation impossible)
│              [ שיבוץ ]  [ ביטול ]              │   secondary · ghost
└                                                ┘
```

- **The options are the free, active rooms from the `rooms` prop the panel already has.** No second fetch, no picker endpoint — `RoomsPanel` makes the identical argument for building its handover list from `staff` (`RoomsPanel.tsx:88-92`). One less thing that can be a tick out of date.
- **No placeholder option.** A room is required, so the first free room is preselected and visible. `rooms.clientPick` ships an explicit «ללא לקוחה» default because an anonymous claim is a real choice; there is no "no room" here.
- **The `Select` carries `className="min-h-11"`** — §13 **F-10**.
- **Focus on open goes to the `Select`** (MOVE 5); on dismiss back to «שבצי לחדר», falling back to the panel `h3` when that trigger has gone (MOVE 4).

⚠ **It is an inline reveal and NOT a `<dialog>`, and that is an a11y decision rather than an economy** (spec D4, Decision 21). A `<dialog>` needs **three** focus mechanisms `RoomsPanel` has already had to ship, none of which axe can see: open-capture with the trigger in a ref; close-return resolved explicitly so the native `<dialog>`'s own return does not win (`RoomsPanel.tsx:309-330`); and a tick that drops the OPEN dialog's row (`RoomsPanel.tsx:292-307`, whose comment reads *"a colleague releasing the room unmounts the tile and the dialog under the user's hands with focus inside — F57's own shipped MAJOR reproduced one level deeper, and axe sees none of it"*). F58 would reproduce it one level deeper again: another manager takes Noa by take-next from her own device, the 5s tick drops her row, and row and dialog unmount together with focus inside. **A row-scoped reveal is covered by MOVES 3, 4 and 5 as they stand** (§11.1), so the move count is six and not nine. **A11y coverage is a reason to pick the simpler element, not only a cost of picking the harder one.**

### 4.2 When no room is free

`«שבצי לחדר» is not rendered on any row`, «קחי את הבאה» is on no tile (there is no free tile), and **one muted line renders ONCE, under the panel heading**:

> אין חדר פנוי כרגע.

⚠ **Panel-level, not per-row — CORRECTS spec D17**, which says *"the row carries one line saying so"*. With forty rows that is forty identical sentences, and the fact is not about any one of them. F36's R-full declines a panel-level banner for the rooms because *"the tiles already say it"* — here the opposite holds: the **absence** of a control says nothing at all, and this line is the only surface that explains why «שבצי לחדר» vanished from every row and «קחי את הבאה» from every tile. **Never a disabled button** — a control that refuses is a 403's cousin on a screen where 403 is terminal.

**If the last free room goes while a reveal is open**, the reveal closes and focus goes to its trigger — which is itself now gone, so `isConnected` fails and the fallback lands on the panel `h3`. **That is MOVE 4, unchanged, reached by a tick instead of a tap** (§11.1). No seventh mechanism, and the alternative — keeping an option-less `Select` mounted, or disabling it — is a dead control that looks live on a screen whose whole rule is that absence carries the state.

---

## 5. Call, skip, remove — the three row verbs

### 5.1 «קראי» — one tap, no confirm, and a second tap is a 200

A summons is not destructive and has no target staffer, which is why all five roles have it (spec D11). It stamps `called_at` and **leaves `status = 'waiting'`** — the contract F59's board cannot enforce for itself and this deck's one obligation to another feature.

- **Success**: the «נקראה» `Badge` appears, `«קראי»` **stays** (she did not come the first time and a re-call is what a manager does next), the cue reads «הקריאה נרשמה.», and focus returns to «קראי» (MOVE 2).
- **A second call** is a **200 that writes nothing** — `called_at IS NULL` in the predicate keeps the FIRST timestamp (spec D7's third branch). The screen is **identical to the first success**, deliberately: F57's F-ok/F-noop argument, *"telling her she lost a race would be telling her she was wrong when she was right"*. The row already reads «נקראה», so nothing moves and the cue confirms the tap registered.
- **⚠ The cue says «הקריאה נרשמה.» and never anything about a message.** Nothing is sent. §13 **F-2** is the deck's largest correction and it is exactly here.

### 5.2 «דלגי» — one tap the first time, a confirm the second

`skip_count` is on the wire so **the second press's meaning is legible before it is pressed** (spec D2). Two presses, two screens:

| Rendered `skip_count` | Tap | What she sees |
|---|---|---|
| `0` | acts immediately | the row moves to the END of the list, its «נקראה» badge **clears** (spec D6 nulls `called_at`), the «דילגו עליה פעם אחת» line appears, and the cue reads «הועברה לסוף התור.» |
| `>= 1` | **reveals a confirm** | «דילוג נוסף יסיר את {{name}} מהתור. להמשיך?» with «אישור ההסרה» (`danger`) / «השארה בתור» (`ghost`). On confirm the row **leaves**, and the cue is `waitlist.removedCue` «הוסרה מהתור.» and not the skip cue |

⚠ **Two cues for one control, chosen by what the CLIENT sent** — the removing press sent `seen_skip_count >= 1`, so it knows which happened without reading the response for an entry that is no longer in it. **CORRECTS D16**, which names one `skippedCue` and does not say which press fires it; a row that vanishes under «הועברה לסוף התור» would be the screen reporting the opposite of what it did.

⚠ **The confirm cannot be bypassed by a stale tile, and that is a server property rather than a client one.** Spec D6's `AND skip_count = :seen_skip_count` is what makes it enforceable: two managers who each tap «דלגי» **once** on a woman at `skip_count == 0` would otherwise remove her — B's predicate re-check passes on A's committed row and B's `CASE` reads 1 — **with the confirm never shown on either device**. The refusal she gets instead is §5.4.

### 5.3 «הסרה» — the one destructive act on this screen

Two-step, the shipped `ManageBookingPage` cancel-reveal shape (`ManageBookingPage.tsx:414-460`):

```
┌ 3   נועה בר                                    ┐
│     שמלת ערב · הגיעה זה עתה                    │
│     יש עוד כניסה פעילה היום עם אותו מספר טלפון.│
│                                                │
│     להסיר את נועה בר מהתור?                    │   ← focus lands HERE (MOVE 5)
│     אם הטלפון שלה מציג את הכניסה הזו, המסך      │   ← rendered ONLY when duplicate
│     שלה יראה שהביקור הסתיים. אפשר לומר לה       │
│     שהמקום שלה נשמר.                           │
│                                                │
│         [ אישור ההסרה ]  [ השארה בתור ]        │   danger · ghost
└                                                ┘
```

- **The trigger is `ghost`, not `danger`.** `manage-restyle.md`'s destructive pattern is *"`danger` trigger → `Modal` with a ghost dismiss and a `danger` confirm"*, and this diverges on the trigger for the reason the shipped storefront two-step already diverges: **the trigger does not remove, it asks.** A permanently red control on every row of a list of waiting customers, on a screen a staffer opens fifty times a shift, reads as a threat; the red belongs on the press that is actually irreversible. The **confirm pair keeps the shipped pairing exactly** — `danger` confirm, `ghost` dismiss.
- **Both buttons name the act**, following the shipped storefront pair («אישור הביטול» / «השארת התור») rather than «אישור» / «ביטול». ⚠ **CORRECTS D16.** A bare «אישור» in a two-step is the button a hurried reader presses without having read the question, and it is the one press with no undo.
- **The reveal, not a `Modal`.** F36's **P-7** chose a nested `Modal` for the registry's delete confirm and gave good reasons; the criterion is the same here and it points the other way. F36's confirm lives inside an already-open `Modal` **that the poll does not repaint**; this one lives in a **row a tick can unmount underneath it** (another manager dispatching her from her own device), which is exactly the three-mechanism cost §4.1 declines. Same rule — *take the shape with fewer focus mechanisms axe cannot see* — applied to two different contexts.
- **Focus after a successful removal**: the row is gone, so the panel `h3` (MOVE 3).
- **No restore verb.** Spec D8: one more route, one more gate, one more audit value and one more control, to undo an act that already has a confirm in front of it and an audit row behind it. Risk 3 names the mis-tap consequence; the upgrade path is recorded.

### 5.4 The refusals — what each verb's 409 and 404 look like

All four render in the **row's own alert**, `role="alert" tabIndex={-1}`, in the **notice** register, with focus moved into it (MOVE 1) and cleared by the next successful tick (MOVE 6).

| Wire | Sentence | Note |
|---|---|---|
| 404 | «הכניסה הזו כבר לא קיימת. הרשימה תתוקן בעדכון הבא.» | While `paused`, the twin ending «…עם חידוש העדכון.» — a stopped panel has no next update to promise (F36's DC-8), and it points at the control that IS on screen |
| 409 `QUEUE_TICKET_NOT_WAITING`, `details.status = "in_service"` | «היא כבר בטיפול.» | Different remedy: find her in a fitting room |
| …`"done"` / `"removed"` | «הכניסה הזו נסגרה.» | Different remedy: nothing to do; the tick will drop the row |
| …no `details` | «הכניסה הזו כבר לא ממתינה.» | F36's `*Unknown` precedent: `details` is typed `Record<string, string> \| undefined` and a sentence that admits it does not know beats one that guesses |
| 409 `QUEUE_TICKET_CHANGED` | «מצב הכניסה השתנה. הרשימה תתוקן בעדכון הבא.» + its paused twin | §5.2's refusal. **She is NOT removed** — and the same tick that clears this alert raises the rendered `skip_count` to 1, so her next press correctly opens the confirm |
| 409 `ROOM_OCCUPIED` / `STAFF_OCCUPIED` (push-assign) | **F36's four shipped sentences, reused unchanged** | §13 **F-4** |
| 5xx / dropped | `staff.loadFailed`, **outage** register | shipped |

---

## 6. FINISH is the shipped room-tile release — the row has four controls and «done» is not one of them

The brief's mental model puts four controls on the row: call, assign, skip, **done**. This deck ships call, assign, skip, **remove**, and the fourth substitution is spec **D5** and Conflict 2, taken deliberately.

`POST /manage/floor/assignments/{id}/release` is shipped, on the room tile, labelled «שחרור», reachable by every role that may release, and it is already what a staffer taps when a fitting ends. **If FINISH were a second control on the waitlist row, then releasing from the room tile — the control that is already there, already documented, already tested — would free the room and leave the ticket `in_service` forever.** That is precisely the defect this feature exists to eliminate, re-introduced by the feature that eliminates it.

So: **no new control, no new label, no state-dependent label.** ⚠ An earlier reading had the shipped label become state-dependent («שחרור» vs «סיימתי עם הלקוחה»); spec Conflict 2 declines it in writing and this deck agrees — a label that changes with the assignment's provenance is a second thing that can disagree with the tile it sits on, for a wording gain, and «סיימתי עם הלקוחה» is what the shipped control already means. `copy.md` §9 lists «שחרור» among the reused rows for exactly this reason.

**What changes behind it**: releasing an assignment that carries a `queue_ticket_id` closes the ticket to `done` **in the same transaction** — the worker frees and the entry closes together, or neither does. Nothing on the screen renders differently. **Her own phone is where the change is visible**, and it is the third of F33's three deployment-gate consequences: `QueuePositionPage.tsx:319` finally reaches «הביקור הזה הסתיים.» and stops the loop, on a page that until this merge polls until the tab is closed.

**Handover needs no change at all** (spec D5): it mutates `staff_user_id` alone, so the ticket pointer, the created_at and the dress bindings all survive. A walk-in handed to a colleague keeps her ticket, her elapsed clock and F37's future alert pointer.

---

## 7. The duplicate remedy surface

Ruling 3 traded server-side dedup for duplicates and its stated price was *"a duplicate ticket is now a real, expected outcome, and F58 merges or removes it"*. **This is where that is paid.**

**What the panel does:** it flags **both** rows of the pair, in the notice register, with a sentence that names the fact rather than a category:

> יש עוד כניסה פעילה היום עם אותו מספר טלפון.

**What the panel does NOT do, and each absence is a decision:**

- **It does not merge.** Spec D8 and Decision 5: a merge must choose which capability survives and whose arrival time wins, and both answers are bad. Keeping the later ticket costs her place; keeping the earlier one — her true arrival, and the right answer for the queue — terminates the page her *current* tab is polling.
- **It does not hide, dim or reorder either row.** Two rows, both live, both actionable. A panel that auto-selected one would be deciding, on a name match, which of two women loses her place.
- **It does not recommend which to remove.** The **position numbers already say which arrived first**, and a screen that says "remove this one" is the product overruling a manager who can see both women.
- **It does not flag across the truncation bound.** Spec D9's honest limit: the waiting read is capped at 100, so a pair straddling it is not flagged, and `truncated: true` means the flag is best-effort on that payload. **The truncation line does not say so** — a clause explaining a flag's limits in the one case that means somebody is attacking the queue is a sentence for a case a boutique will never see, and it would make the ordinary line unreadable. The limit is recorded in the spec, where a reviewer reads it.

**The flag is a boolean and never a group index** (spec D9): a woman's twin can be **`in_service`** — she re-scanned, was dispatched on the first ticket, and the second is still waiting — and that ghost is the most valuable thing on this panel to remove. A group *number* would render a group of one visible row, which reads as a bug. The boolean says the true thing in both cases.

**Grouping is by phone and by nothing else**, normalised to E.164 at insert, and **the phone never reaches the wire**. `name` is free text she typed and collides legitimately — two women called נועה in a bridal boutique is not a rare event, and this is the panel where a collision decides who gets removed.

**One line the spec's Risk 2 has no other mitigation for.** Whichever ticket is removed, if it is the one her current tab polls, her page renders «הביקור הזה הסתיים.» and stops — while she is still in the queue on the other ticket. The manager is the only person who can repair that, and she can only repair it if she knows. So the remove confirm carries a **second line, rendered only when `entry.duplicate`**, telling her exactly that and what to say (§5.3, and `copy.md` §5). ⚠ **This is an addition to D16 rather than a correction**, and it is the cheapest possible discharge of a risk whose listed mitigations were *"she is three metres from the counter"* and *"the confirm names her"*.

---

## 8. States — the single source for this feature

**The list may not shrink.** States inherited from `FloorPanel`'s poll (F-load, F-fail, F-stale, F-paused, F-idle, F-401, F-403) are **F57's, unchanged**, and are not restated — they now govern three regions, which is §11.4's point. States belonging to the room tile (R-*) are **F36's, unchanged**, except where §3 names an addition.

| # | State | Trigger | What she sees | Region / focus |
|---|---|---|---|---|
| **W-load** | `waitlist === null`, first tick in flight | section opened | **Nothing** — `WaitlistPanel` returns `null`, exactly as `RoomsPanel` does (`RoomsPanel.tsx:588-592`). `FloorPanel`'s existing skeleton covers the screen. No second skeleton, no second pause control over a fetch nothing has seen produce anything | the shipped `floor.loading` cue |
| **W-empty** | `entries.length === 0` — **the common case** | 200 | `EmptyState title={t("waitlist.empty")}`, **no body and no action for any role**. A bridal boutique's queue is empty most of the day and the panel must read as *quiet*, never as *broken* or as *unconfigured* | nothing announced |
| W-list | 1–100 entries | 200 | Rows in server order (§2) | nothing |
| **W-40** | Forty waiting | 200 | The list scrolls with the page. **No virtualisation, no pagination, no collapse.** «קחי את הבאה» is one tap regardless of length, which is the control that matters at forty; the position numbers are what keep a scrolled list legible | nothing |
| W-truncated | `truncated: true` (>100 — a griefing flood inside F33's 200/hour tenant ceiling) | 200 | One muted line naming **no number and no limit**, and naming what falls off (the later arrivals) | nothing |
| **W-noroom** | Entries exist, every room occupied or inactive | derived from `rooms` | **One** panel-level muted line; no «שבצי לחדר» on any row; no «קחי את הבאה» on any tile. **Never a disabled button** (§4.2) | nothing |
| W-noroom-open | The last free room goes **while an assign reveal is open** | tick | The reveal closes | MOVE 4 → trigger (gone) → `h3` |
| **W-busy** | A row action in flight | tap | **That control only**: `loading` on the shipped `Button` (spinner overlaid, label kept for width, `aria-busy`). Every other row stays live. The poll returns `"suppressed"`, so no row can repaint under the request | nothing yet |
| **W-ok** | Call / assign / skip / remove succeeded | 200 | The panel patches **from the response's whole `Waitlist`** — skip reorders it and remove shortens it, and a per-entry patch cannot express either (spec Decision 11). The freshness stamp updates | `role="status"`; focus per §11.1 |
| **W-vanished** | She was dispatched, skipped or removed from another device between the render and the tap | 404 | «הכניסה הזו כבר לא קיימת…» in the row's alert; the `…Paused` twin while stopped | `role="alert"`, **focused** (MOVE 1); cleared by the next tick (MOVE 6) |
| **W-stalecount** | A colleague skipped her between this render and this tap | 409 `QUEUE_TICKET_CHANGED` | «מצב הכניסה השתנה…». **She is NOT removed** — the whole point of the conjunct | as W-vanished |
| W-notwaiting | She is already in a room, or her entry closed | 409 `QUEUE_TICKET_NOT_WAITING` | One of §5.4's three sentences, chosen on `details.status` | as W-vanished |
| **W-duplicate** | Two rows, same phone | `duplicate: true` on both | Both carry the notice-register line. Neither is merged, hidden or reordered. Removing one is two taps, names her, **and carries the Risk 2 line** (§7) | as W-ok on success |
| W-called | `called: true` | | «נקראה» `Badge`; «קראי» **stays** (a re-call is a 200 no-op) | |
| W-lastskip | `skip_count >= 1` | | The muted skip line, and «דלגי» **opens the confirm instead of acting** | |
| **W-emptyqueue** | Take-next tapped on a tile after the last entry left | 409 `QUEUE_EMPTY` | «אין ממתינות בתור.» in the **tile's** alert, non-outage register. The waitlist below is already empty and says the same words | `role="alert"` on the TILE, focused |
| W-lostrace | Take-next or assign lost the room | 409 `ROOM_OCCUPIED` / `STAFF_OCCUPIED` | §3.3 — the shipped sentence in the tile's (take-next) or the row's (assign) alert, **and the queue unchanged** | focused |
| W-outage | 5xx or a dropped request | | `staff.loadFailed` in the **outage** register (`text-ink-muted`), **never `text-danger`** | focused |
| W-terminal | 401 / 403 from a tick **or a mutation** | | `FloorPanel`'s existing terminal takes the whole screen. This panel adds no second terminal — `mutate()` already routes it, and §2.2 makes the 403 unreachable by design | `role="alert"`, once |
| W-paused | `mode !== "running"` | | Rows keep rendering; wait times **frozen** with the stamp; **every control still live** — pausing is a repaint control, not a read-only mode. The two paused twins replace their sentences | |

**State precedence.** A mutation's response is the truth for the whole waitlist (it *is* a `Waitlist`). A poll's response is the truth for everything else. They cannot fight: the loop issues no tick while a mutation is in flight, and the mutation bumps the generation on settle.

---

## 9. Breakpoints — 375 / 768 / 1440

Mobile-first, and there is exactly **one** breakpoint branch in the panel — the same one F34, F57 and F36 have, in the same place.

| Width | What is different | Why |
|---|---|---|
| **375** (primary) | The row is a flex **column**: the text block on top, **the action row on its own line, `flex flex-wrap justify-end gap-3`** | Arithmetic: 375 − 2×`--space-4` = 343 of shell, − 2×`--space-6` of `Card` padding = **295px** of row. Four `min-h-11 px-4` controls plus three `gap-3` runs measure ≈320px, so they **wrap to a second line rather than shrinking** — `fullWidthMobile={false}` on every one, because four full-width buttons per row would be a wall. `Card`'s `p-6` cannot be reduced from the call site (F15 F-6) |
| **375, long name** | The name wraps and pushes the `Badge` to the next line. `break-words` on the name, `flex-wrap` on the label row, **no truncation and no ellipsis anywhere** | The row has vertical room it does not have horizontal room, and abbreviating on *this* panel makes two women look like one |
| **375, the reveal** | The reveal's two buttons are `flex flex-col gap-3 sm:flex-row` — stacked, full width, the `ManageBookingPage` shape | A destructive confirm is the one place a large target is worth the vertical cost |
| **768** | The action row moves to the row's inline-end on the **same** line (`sm:flex-row sm:items-start`). Still **one column** — no grid, no two-up | 720 − 48 = 672 of row. §12 **P-1** |
| **1440** | **Identical to 768.** The console never exceeds a 720px content column (`ConsoleShell.tsx:84`) | A wall-mounted display is F59's, it is shipped, and it is gated on this feature |
| **Every width** | **The three panels stack in one column, in a fixed order.** They never sit side by side, at any width | The 720px cap forbids it, and §1.1 shows the order is forced by take-next's placement rather than chosen |

**`items-start`, not `items-center`, at 768.** A row with a duplicate line, a skip line and an alert is five to seven lines tall while its action row is one; centring the controls against that block floats them into the middle of the text. F57's staff card uses `items-center` because it is three lines — the divergence is a height difference, not a taste difference, and F36 made the identical call.

**The consequence of stacking, stated:** at 375 with four rooms and twelve waiting, the staff cards are roughly two screens down. That is correct and it is the ordering argument (§1.1) — the staff cards are the only one of the three panels a staffer does not act on to serve the woman in front of her.

---

## 10. Component notes — exact tokens

| Element | Notes |
|---|---|
| Waitlist heading | `<h3 ref={headingRef} tabIndex={-1} className="text-base font-semibold text-ink">` — **`h3`, matching `rooms.heading`; see §13 F-1.** `tabIndex={-1}` is MOVES 3/4/6's rescue target and adds **no** tab stop. Renders in **every** state including W-empty |
| No-free-room line | `<p className="text-sm text-ink-muted">` directly under the heading, outside the `Card` |
| List | `<Card>` → `<ul className="divide-y divide-border">` — `RoomsPanel.tsx:638`'s exact shape. The `Card`'s `p-6` is **not** overridden |
| Row | `<li data-entry-id={id} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start">`; text block `min-w-0 grow space-y-1` |
| Position | `<bdi dir="ltr" className="text-sm text-ink-muted tabular-nums">` — `tabular-nums` is a Tailwind `font-variant-numeric` utility, **not a raw px value**, and it is what keeps the name column flush from row 9 to row 10 |
| Name | `<bdi className="font-semibold break-words text-ink">` — bare `<bdi>`, **never `dir="ltr"`**: forcing LTR on a Hebrew name reverses its words, and it is the bidi defect that *looks deliberate* (F57 F-11) |
| Called Badge | `<Badge variant="warning">{t("waitlist.called")}</Badge>` — **one per row, at most** |
| Meta line | `<p className="text-sm text-ink-muted">` — `{t(visitKey)} · {waitLine}`, where `waitLine` is `isolateLtr(t("waitlist.waiting", { minutes }), String(minutes))` or the plain `waitlist.waitingJustNow`. **`elapsedMinutes`, never `elapsedLine`** (§2.4) |
| Duplicate line | `<p className="text-sm font-semibold text-warning-text">` — the **notice** register |
| Skip line | `<p className="text-sm text-ink-muted">` |
| Row alert | `<p role="alert" tabIndex={-1} className="text-sm font-semibold text-warning-text">` for every mapped code; `text-sm text-ink-muted` (no `font-semibold`) for the unmapped outage fallback. **Never `text-danger`** (§3.3) |
| Reveal question | `<p ref={revealRef} tabIndex={-1} className="text-base text-ink">` — MOVE 5's destination is **the question itself**, so a screen reader hears what is being asked rather than an anonymous container (`ManageBookingPage.tsx:421-424`) |
| Reveal buttons | `<div className="flex flex-col gap-3 sm:flex-row">` — confirm then dismiss |
| Call / skip / remove | `Button variant="ghost" size="md" fullWidthMobile={false}` + its `aria-label` |
| Assign trigger | `Button variant="secondary" size="md" fullWidthMobile={false}` + `waitlist.assignAria` |
| Assign `Select` | `Select label={t("waitlist.assignRoom", { name })} className="min-h-11"` — see §13 **F-10** for why the class is at the call site and why that is not an F15 F-6 violation |
| Assign confirm / dismiss | `secondary md` / `ghost md` |
| Remove + removing-skip confirm | **`danger md`** confirm, `ghost md` dismiss — `manage-restyle.md`'s shipped destructive pairing. The ledger's `white on --color-danger` row (≈7.0:1) is the pairing `Button danger` ships |
| Take-next (on the tile) | `Button variant="secondary" size="md" fullWidthMobile={false}` + `aria-label={t("rooms.takeNextAria", { room })}`, **first** in the tile's action row |
| Empty state | `<EmptyState title={t("waitlist.empty")} />` — **no `body`, no `action`, for any role** |
| Truncation line | `<p className="text-sm text-ink-muted">` under the list |

**Contrast, from the tokens ledger — not eyeballed.** ink 13.89 · ink-muted 5.61 · warning-text 5.20 · danger 6.18 · white-on-danger ≈7.0 · success 5.56 · focus ring 5.57 · border (non-text boundary) ✓. **This feature introduces no new colour pair and no gold at all** — the board's «עכשיו» hairline remains the console's only `gold-strong`, and nothing here is `primary`. The ledger needs no addition at this gate.

---

## 11. The a11y contract — IS 5568 / WCAG 2.0 AA is a legal requirement (pre-decided #38)

axe must return **zero** violations, and **axe is not the coverage**. Three whole classes below are invisible to it.

### 11.1 Focus — six moves, each with a named, non-vacuous test

⚠ **axe cannot see a focus move that never happened.** This repo has shipped that exact bug class **four times** — F56 on the storefront, F34 on the board, F57 on the floor panel, F36 on the room dialogs — and axe walked past every one. `@boutique/ui`'s `Button` is `disabled={disabled || loading}` (`Button.tsx:57`), so **a real browser blurs the tapped control the instant a request starts, and every verb on this panel is that shape.**

Following `RoomsPanel`'s numbering, so the two panels are diffable:

| # | Move | Destination | Mutation that must turn it red |
|---|---|---|---|
| **1** | **A refused verb** (409, 404, outage) | the **row's** alert — keyed on the error state, **not raised in the handler**, because the alert node does not exist when `setRowError` runs | delete the `[rowError]` effect |
| **2** | **A verb that succeeds and leaves the row in place** — call, first skip's *increment*, and every take-next on the tile | the row's (or tile's) current primary control, via a `Map` keyed by **entry id** (room id on the tile), **guarded on `document.activeElement === document.body`** so it can never steal focus from wherever she moved it | delete the restore effect |
| **3** | **A row that LEAVES the list, OR leaves its place, while holding focus** | the panel `h3` | delete the departing-row check — **and run the deletion twice: once for a removal, once for a skip** (below) |
| **4** | **A reveal is dismissed** — by her, **or because a tick removed what it was for** (W-noroom-open, or the row itself) | back to its trigger; `isConnected` then the `h3` (F51's shipped shape, `StaffSection.tsx:80-92`) | delete the `isConnected` fallback → focus lands on a detached node and silently does nothing |
| **5** | **A reveal opens** | onto the **question** (assign: onto the room `Select`) | delete the open-capture |
| **6** | **A tick CLEARS a focused alert** | back to that row's control | delete the render-time capture — ~5s after the refusal, with no user action, the promise «הרשימה תתוקן בעדכון הבא» is kept by the tick and focus must not fall to `<body>` with it |

⚠ **MOVE 3 HAS TWO TRIGGERS AND THE SECOND IS THIS FEATURE'S OWN.** A row leaves the list on a removal, a second skip, **or a poll tick** — another manager dispatching her from her own device drops the row under this user's hands with no action by her. **And a successful FIRST skip does not remove the row; it moves it to the end.** React keys the `<li>` by `entry.id`, so the browser keeps focus on the same control — now forty rows below the fold, where a focus ring is indistinguishable from lost focus for exactly the user who most needs it. So a successful skip sets the same heading flag a departure does. *Declined the alternative* — re-calling `.focus()` on the moved control, which does scroll it into view: a forty-row scroll jump with no user action is the repaint F34's F-8 exists to prevent, and the cue «הועברה לסוף התור.» already says what happened. **The mutation for MOVE 3 must be run for both triggers, and with a reveal open**, or it tests half of what it claims.

**Both render-time captures are copied from `RoomsPanel.tsx:167-192`**, and the reason is not style: by the time an effect runs the departing row is gone, `document.activeElement` has already dropped to `<body>`, and the question cannot be asked any more.

⚠ **jsdom is the trap, and it has already produced one shipped vacuous test.** F57's success-path focus test was **vacuous** because jsdom does not blur a disabled element, so `activeElement` never became `<body>` and the guard never passed — the whole restore effect could be deleted with the suite green. **A test for MOVE 2 must explicitly blur the tapped control before the promise resolves.** `LOOP-STATE.md`'s `known_flaky` also names a jsdom focus race in `ManageBookingPage.test.tsx` — the very component this panel's reveals copy — and the rule there is **fix the wait, never raise the timeout**, and do not copy the flaky shape.

**MUTATION for the whole class:** delete each move's effect body in turn; each must red **exactly one** named test and nothing else. **A move whose test stays green when its mechanism is deleted is a vacuous test and must be respecified before the gate.**

**Tab order** inside the floor screen: skip link → header logout → nav → `#console-main` → *(board section, for the two roles that see it)* → **the pause / resume control** → the registry trigger → per tile: the client `Select`, «קחי את הבאה», «תפיסת החדר» · or the dress / handover / release controls → the waitlist `h3` is not a stop → per row: «קראי», «שבצי לחדר», «דלגי», «הסרה», and the open reveal's controls in place → the staff cards' controls. **The pause control staying the first stop inside the panel is F57's ruling and is now more load-bearing, not less: it governs three repainting regions.**

**Every action is keyboard-reachable and none needs a pointer.** The only interaction primitives are `<button>` and a native `<select>`. **There is no drag, no long-press, no swipe, no hover-only affordance and no custom widget anywhere in this feature.**

**Rows are keyed by `entry.id`**, so a repaint mutates text nodes inside a stable element and focus inside a row survives every tick.

**A tick may not repaint while a pointer is down.** `FloorPanel`'s `holdRef` already covers this and its comment already names the rooms case. **The waitlist makes it worse in a new way**: a remote skip moves a row from position 1 to position 12, so every row between them shifts up — directly under a finger travelling toward «הסרה» on the row below. The mechanism is unchanged; its comment gains the waitlist case.

### 11.2 Live regions — announce on MEANINGFUL CHANGE only, never per tick

**The poll never writes into `role="status"`** (F34's D11, verbatim and non-negotiable). A status update every five seconds announces the whole queue forever and makes a screen reader unusable for a whole shift. The region carries **user-initiated outcomes only**: the dispatch cue, the call cue, the two skip cues and the remove cue, plus F36's five room cues and F57's shipped pause / idle / resume / break cues.

**A row that appears, moves or vanishes because a colleague acted, or because a woman scanned the QR at the door, repaints silently.** So does every position renumbering. That is not a gap: the queue changes continuously and by design, and a region that narrated it would be narrating a shop floor.

⚠ **"Write" means write, not change.** Assigning a byte-identical string to a text node still runs the DOM's string-replace-all and produces a real `childList` mutation inside `role="status"` (F34's **F-7**; `FloorPanel.tsx:236-243` carries the warning). The cue is written **only when its value actually changes**, and the test must drive **several consecutive ticks with the cue already populated** — a single-tick assertion passes against the broken version whenever the cue starts empty.

⚠ **NO CUE ON THIS SCREEN NAMES A CUSTOMER, and this is the deck's sharpest privacy line.** `RoomsPanel.tsx:464-469` states the shipped rule verbatim:

> The cue names the ROOM and never the client. The region is **PERSISTENT** — nothing clears it on a timer — so a bride's name in it would sit on a five-role screen for an arbitrary length of time, in a room she is standing in. The tile one line away carries her name for exactly as long as the fitting lasts.

**The rule is about persistence, not about refusals**, and `FloorPanel.tsx:510-521` confirms it: the cue is a plain `<p role="status">` overwritten only by the next cue and cleared by **nothing** — no timer, no tick, no unmount. F58's cues would have been **strictly worse than the case F36 declined**: «נועה הוסרה מהתור.» sits in the DOM of a five-role screen **after her row has left the payload and after she has left the shop**, so the cue becomes the only place her name survives — falsifying D10's own rewritten promise that *"every name leaves the payload the moment she does"*, on the surface Risk 4 calls the most legally sensitive line in the spec. **So the cues name the ACT**, and the row (or the tile) one line away carries her name for exactly as long as she is on the floor. Only the dispatch cue interpolates, and it interpolates a **room label**.

`role="alert"` appears on this panel **once per refused verb, bounded by her own tapping**, plus F57's shipped terminal 401/403 (once per dead session, with the loop already stopped). **Neither can be produced by the poll on its own.**

### 11.3 Status is never colour alone

«נקראה» is a word. The duplicate flag is a sentence. The skip count is a sentence. The wait time is a number with a word. **Nothing on this panel is expressible only by its colour**, and the notice register (`--color-warning-text`) always accompanies text that says the same thing. `tokens.md` law 2, F51's shipped rule (*"the WORD carries the role; the colour never does"*) and `FloorPanel.tsx:40` (*"the WORD carries the state; the colour never does"*).

**No `opacity-*` anywhere**, on any row, in any state. Opacity multiplies every contrast ratio inside the element, and **axe computes contrast against declared colours rather than composited pixels**, so it walks past the whole class. Muted is a token swap.

### 11.4 SC 2.2.2 — inherited, and its tests may not be cut

`FloorPanel`'s pause / resume control and its idle stop now govern **three** repainting regions. **axe has no rule for SC 2.2.2**, so the shipped frontend assertions — pause stops the loop, resume fetches immediately at the base interval, the idle stop fires, one interaction resumes — are the **sole** coverage of a Level A requirement inside a legally binding AA bar. **F58 adds no control and no constant** (§12 **P-6**), and the shipped tests must not be cut as redundant with the axe pass. F36 said this about the second region; this is the third.

### 11.5 The rest

- **≥44×44 on every target.** Every `Button` is `size="md"` → `min-h-11`; the assign `Select` carries `min-h-11` explicitly (§13 **F-10**). **jsdom has no layout engine, so a measured assertion would be vacuous** — the test asserts the class, which is the trap `BoardSection.test.tsx:507-512` writes out.
- **Visible focus ring** on every interactive element — `focusRing`, applied unconditionally by `Button.tsx:62` and `Select.tsx:31`. Nothing here sets `outline: none`. **axe sees a missing label; it does not see a missing focus ring.**
- **Accessible names carry the visible label plus the customer**, and each **starts with** the visible string so WCAG **2.5.3 label-in-name** holds — «קראי — נועה בר», «שבצי לחדר — נועה בר», «דלגי — נועה בר», «הסרה — נועה בר», «קחי את הבאה בתור — חדר 2». Forty rows all offering a button named «דלגי» is a screen-reader dead end. ⚠ **Four of spec D16's five proposals fail this** and are corrected in `copy.md` (§13 **F-3**). An `aria-label` takes no markup, so an interpolated value in one needs **no bidi treatment at all** (F57 F-11).
- **The position number carries no label, and that is a decision.** «מקומך בתור» beside every one of forty numbers is exactly the repetition every other rule in this deck exists to prevent; the panel heading «ממתינות בתור» plus arrival order supplies the context, and the number is neither `aria-hidden` (it is real information) nor labelled.
- **Bidi**: `<bdi dir="ltr">` on every numeric run (position, minutes); **bare `<bdi>`** on every Hebrew free-text run (customer names, room labels).
- **No truncation and no ellipsis on a customer name, ever.**
- **Headings**: the shell owns the single `h1`; `FloorPanel`'s `h2` is unchanged; this panel's is an **`h3`**, a peer of «חדרי מדידה» (§13 **F-1** records the honest cost and why the remedy is not payable here). **No `Modal` and therefore no second `h2` inside a top layer** — this feature ships no dialog at all.
- **Motion**: nothing new animates except the shipped `Button` spinner, already frozen globally by `theme.css:155-163` under `prefers-reduced-motion`. **No highlight, no fade, no colour wash on a changed row. This feature adds no motion rule because it adds no motion.**
- **No `aria-live` on the list itself.** `role="log"` is the tempting wrong answer — it is for append-only chat and this list mutates in place and **reorders** — and a status region rewritten every five seconds announces the whole queue forever (F34's D12).
- **Content capped at 720px** at every width. `A11yMenu` / `A11yStatementLink` are storefront-only, so no fixed-chrome clearance applies.
- **An axe pass runs over the floor screen with a populated waitlist** — the console's **first axe assertion behind the login screen** (spec D19, A30) — and it is **explicitly not sufficient**, per §11.1, §11.2 and §11.4.

---

## 12. RESOLVED decisions — self-approved with the design gate, 2026-08-03

**All ten carry a resolution and none is an open question.** Each keeps its reasoning, because the reasoning is what a later feature would have to overturn to reopen it. **The Hebrew remains the user's to edit post-merge** — the F15 P-1/P-5, F34, F57 and F36 precedent: a one-line `he.ts` / `ar.ts` edit after merge, never a rebuild.

| | Resolution |
|---|---|
| **P-1** | **Three panels stack in one 720px column at every width** — no grid, no side-by-side, no tabs, and the order is forced (§1.1) |
| **P-2** | **Exactly one `Badge` per row, and it is «נקראה»** — every other flag is a word line |
| **P-3** | **Take-next lives on the room tile and is the tile's SECOND `secondary`**, ordered first |
| **P-4** | **All three reveals are inline; this feature ships no `<dialog>`** |
| **P-5** | **The destructive trigger is `ghost`; the confirm is `danger`** — and both buttons name the act |
| **P-6** | **No new poll, no new pause control, no new announced region, no new constant** |
| **P-7** | **A refused verb is a NOTICE, never `danger`**, and a lost take-next race is not an error at all |
| **P-8** | **No auto-merge, no auto-hide, no reordering of duplicates** — the panel flags and a human decides |
| **P-9** | **The no-free-room line is panel-level and renders once** |
| **P-10** | **Nothing on this screen watches the clock** — no wait colour, no SLA, no threshold |

- **P-1 — RESOLVED.** `ConsoleShell.tsx:84` caps content at 720px at every breakpoint, so a side-by-side layout is not available to be chosen; and even at a hypothetical wider column it would be wrong here, because the three panels answer three different questions in sequence (*is a room free* → *who is next* → *who is on the floor*) rather than three views of one thing. F59's board is the wall-mounted layout and it is a different app. **The order is not a preference**: §1.1 shows it is forced by take-next living on a tile, so a builder who reorders the panels relocates the feature's headline control below the fold.
- **P-2 — RESOLVED.** F36 §2.3's precedence rule, one surface over: the state wins the `Badge`, the flag takes a word line. And the line is more useful than the chip — «כניסה כפולה» names a category, while «יש עוד כניסה פעילה היום עם אותו מספר טלפון» is a fact the manager can check by asking the woman in front of her, and it is the only shape that can say **live** (the twin may already be in a room, which spec D9 calls the most valuable case to remove).
- **P-3 — RESOLVED.** Both acts end the tile's state and both are time-critical, so demoting either to `ghost` would assert a hierarchy that is false. Order carries it instead. **Declined a merged control** ("seat someone here", opening a picker of *both* the arrivals list and the queue): it is one more picker, one more mode, and it would make the one-tap dispatch — the whole ergonomic the ruling protects — two taps.
- **P-4 — RESOLVED.** A `<dialog>` needs three focus mechanisms `RoomsPanel` has already had to ship, none of which axe can see; a row-scoped reveal is covered by MOVES 3, 4 and 5 as they stand. **A11y coverage is a reason to pick the simpler element.** The two-step's shape is the shipped storefront one, which is also the one `known_flaky` names — so the rule travels with it: **fix the wait, never raise the timeout.**
- **P-5 — RESOLVED.** `manage-restyle.md`'s destructive pattern is a `danger` trigger → `Modal`; this diverges on the trigger and keeps the confirm pairing. The reason: the trigger asks rather than removes, and a permanently red control on every row of a list of waiting customers reads as a threat on a screen opened fifty times a shift. The shipped storefront two-step is the precedent (`secondary` trigger, `danger` confirm). **Both buttons name the act** — a bare «אישור» is the button a hurried reader presses without reading the question, on the one press with no undo.
- **P-6 — RESOLVED.** `POLL_INTERVAL_MS` = 5s, `MAX_BACKOFF_MS` = 60s and `IDLE_STOP_MS` = 10 minutes are exported by `usePoll` and were ruled at F34's gate. **`lib/usePoll.ts` gets a zero-line diff.** The wait counter is computed at render and sets no interval of its own.
- **P-7 — RESOLVED.** Nothing that can go wrong on this surface is her fault. `--color-danger` appears once on this screen, on the confirm button of an act she chose. **Declined a `danger` register for the 409s** — red would frame two managers reaching for one customer as her mistake, which is F36's F-7 argument and is sharper here because the "resource" is a person.
- **P-8 — RESOLVED.** §7. Auto-merging would have to choose which of two capabilities survives and whose arrival time wins, and both answers cost a real customer something. Flag both, name her in the confirm, tell the manager the one consequence she can repair (Risk 2's line), and let her decide.
- **P-9 — RESOLVED.** Forty identical lines is not a design. **Declined saying nothing**: the absence of a control carries no information, and this is the one line that explains why «שבצי לחדר» vanished from every row at once.
- **P-10 — RESOLVED.** The number is displayed and nothing watches it (spec Out-of-scope, pre-decided #28 — F36 has the identical absence for its elapsed line). **Declined a colour threshold on long waits**: a colour that fires at *n* minutes is a service-level promise no one has made, it would be the first thing on this screen that communicates by colour, and `created_at → called_at` becomes computable the day this merges — which is the analytics ruling's whole subject.

---

## 13. ⚠ FINDINGS

- **F-1 — F36's F-1 named F58 as the PR where renaming `floor.heading` "earns the edit". It does not, and the cost was mis-estimated by a whole category.** F36 recorded that `FloorPanel`'s `h2` «צוות בקומה» (*staff on the floor*) names only part of its own content and predicted F58 — the PR that makes it panel three — would pay for a floor-level word. **Verified against the tree and the estimate is wrong**: `nav.floor` is «הצוות בקומה» (`he.ts:607`) and `Nav.test.tsx:162-165` asserts the nav label and the heading **together**, so renaming the heading is a **nav-row rename** — the "five coordinated edits" trap that file's own comment (`:149-154`) writes out — landing on the PR that clears two deployment gates. Reusing the shipped value as a new `h3` over the staff list is also dead: `getByRole("heading", { name: "צוות בקומה" })` would then match two elements and throw. **Resolution: F58 does NOT rename.** The waitlist ships an `h3` peer of «חדרי מדידה», the honest cost is the one F36 already recorded and accepted (a heading-walking user falls out of the last named subsection into unnamed staff cards), one panel wider. *Owner: team. **Trigger re-set**: any PR already renaming a `nav.*` label, or F37 — whose overlay makes it four.*
- **F-2 — ⚠ SPEC D16 SHIPS A VALUE THAT CANNOT PASS A SHIPPED TEST.** `waitlist.calledCue` is «**נשלחה** קריאה.», and `i18n.test.ts:560` filters every value in `HE` for `/נשלח|תישלח|בדרך/`. The same spec (D16) requires `HE_F58` to be **folded into `HE`**, which is precisely what makes the guard reach it — so the deck as written is red on its own gate. It is also **substantively false**: `call` stamps a timestamp; nothing is sent to anybody, there is no `scheduled_messages` row and no sender ID, and F58's own Out-of-scope says so in as many words. **Corrected to «הקריאה נרשמה.»** (`copy.md` §7). Recorded rather than folded in silently because this is the guard's second real catch in this program and the pattern is identical both times: a cue about a *summons* reaching for a *sending* verb. *Owner: the builder. Trigger: this PR.*
- **F-3 — four of D16's five `*Aria` values fail the shipped WCAG 2.5.3 pattern, and two also break F36's F-3 rule.** `i18n.test.ts:456-468` asserts each `*Aria` **starts with** its visible label. «הסרת {{name}} מהתור» is a *different word form* from «הסרה», so a speech-input user saying what she can see matches nothing; «שבצי את {{name}} לחדר» does not open with «שבצי לחדר». And «קחי את הבאה בתור **לחדר** {{room}}» places a Hebrew preposition against a user-typed room label, so the boutique's own «חדר 2» renders «לחדר חדר 2» — F36's F-3, established as a general rule and violated again the first time a new deck interpolated a room. **Corrected as a class in `copy.md` §3: every `*Aria` is `<visible label> — {{value}}`.** *Owner: the builder. Trigger: this PR.*
- **F-4 — D16 re-keys four shipped `rooms.error.*` sentences into `waitlist.*`, which is F36's F-10 duplication hazard with four new copies one panel apart on the same screen.** «{{name}} כבר בחדר הזה.» and its three siblings would exist twice, in two namespaces, with two floors and two `ar` parity guards, drifting the first time anyone edits one. **Resolution: the row's `describe()` calls the shipped `rooms.error.*` keys unchanged — four fewer keys, zero duplicates**, and the rule stated so a fifth panel can apply it: **no value is declared twice; a string reused across panels keeps its original key.** `rooms.error.QUEUE_EMPTY` is a *new* string, so its namespace is free and D16's tile-vocabulary argument decides it. *Owner: the builder. Trigger: this PR.*
- **F-5 — D12 gives one error code two Hebrew sentences and D16 declares one key for it.** `QUEUE_TICKET_NOT_WAITING` carries «היא כבר בטיפול.» *or* «הכניסה הזו נסגרה.», chosen on `details.status` — two different remedies (find her in a fitting room / nothing to do). And `details` is typed `Record<string, string> | undefined`, so F36's `*Unknown` precedent applies. **Three keys, `copy.md` §6.** *Owner: the builder. Trigger: this PR.*
- **F-6 — `rooms.*` gains THREE keys, not the one D16 names, and `HE_F36`'s floor moves by three.** D16 exempts `rooms.error.QUEUE_EMPTY` from the `waitlist.` namespace because take-next's refusals render in the tile's alert. **The same argument reaches the tile's BUTTON**: `waitlist.takeNext` / `waitlist.takeNextAria` would be the only `waitlist.`-keyed strings in a component that renders eighteen `rooms.` ones. Moving them also has a mechanical payoff — `i18n.test.ts:461`'s 2.5.3 loop is `["claim","release","handover","addDress"]`, so adding `"takeNext"` puts the new accessible name under a **shipped** guard instead of F58 writing a parallel one. **`HE_F36`'s floor goes `>= 70` → `>= 73`, not the `>= 71` the spec's Frontend-changes table states.** The dispatch cue stays `waitlist.*`: it renders in `FloorPanel`'s region, not in the tile's alert, so the "only foreigner" argument does not reach it. *Owner: the builder. Trigger: this PR.*
- **F-7 — D17's no-free-room line cannot be per-row.** «אין חדר פנוי כרגע.» forty times is not a design, and the fact is about the rooms rather than about any entry. **Panel-level, once, under the heading** (§4.2). *Owner: the builder. Trigger: this PR.*
- **F-8 — a successful first skip MOVES the row, and D18's six moves do not cover a row that stays mounted and travels.** Rows are keyed by `entry.id`, so the browser keeps focus on the same control — now at position 40, below the fold, where a focus ring is indistinguishable from lost focus. **MOVE 3 gains a second trigger** (§11.1) and its deletion mutation must be run twice. Named because it is the fifth instance of this repo's most-shipped bug class and the first one where the element did not unmount, so the departing-row check would have looked correct and covered nothing. *Owner: the builder. Trigger: this PR.*
- **F-9 — the assign reveal must survive the last free room vanishing under it, and D17's inline-reveal ruling does not say what happens.** An option-less `Select` is a dead control that looks live; a disabled one is banned outright. **MOVE 4 gains a second trigger** — the reveal closes and focus falls through `isConnected` to the `h3` — so it costs no seventh mechanism (§4.2, W-noroom-open). *Owner: the builder. Trigger: this PR.*
- **F-10 — F36's F-4 named F58 as the second occurrence that earns fixing `Select`'s height in the component, and F58 declines with a reason.** `Select.tsx:28` is `px-3 py-2 text-base` + 1px border ≈ **43.6px**, under the house 44 floor (`tokens.md` law 7 — WCAG 2.0 AA has no target-size criterion, so this is a house rule and not the legal bar). This deck passes `className="min-h-11"` at the call site, which is **not** an F15 F-6 violation because `Select` declares no `min-h-*` at all, so `cn()`'s plain join has no fight to lose. **The one-line component fix is declined here** because `Select` is consumed by eight screens and F58's acceptance gate is that every shipped suite passes with **no edit** — a shared-component height change is a separate PR with its own eight-file blast radius, not a rider on the feature that clears two deployment gates. *Owner: team. **Trigger re-set**: any PR whose diff is already in `packages/ui`.*
- **F-11 — Risk 2's only listed mitigations are "she is three metres from the counter" and "the confirm names her", and neither tells the manager the consequence.** Removing a duplicate terminates the position page of whichever tab is polling that ticket, and the manager is the only person who can repair it — by saying one sentence to a woman standing in front of her. **One string, rendered inside the remove confirm only when `entry.duplicate`** (§7, `copy.md` §5). An addition to D16 rather than a correction. *Owner: the builder. Trigger: this PR.*
- **F-12 — `HE_F58` must be FOLDED into `HE`, and it needs its own `ar`-value parity test, which the shipped one cannot give it.** `i18n.test.ts:33-34` says it about itself — *"without this the resolve check, BOTH register guards and the `ar` parity guard silently skip every key"* — and F58 is the feature where the fold is load-bearing twice, because **F-2's send-ban catch only fires through it.** Separately, the shipped `ar[key] === he[key]` assertion (`:585-591`) is scoped to `HE_F36` **by name**, so thirty-seven hand-transcribed `waitlist.*` strings would ship with only a presence check — which passes on an English string, a `TODO`, or a different Hebrew wording. **F58 declares the `HE_F58`-scoped twin.** *Owner: the builder. Trigger: this PR.*
- **F-13 — this deck's key count is 40, not D16's ~25, and the `ar` transcription risk scales with it.** Thirty-seven `waitlist.*` plus three `rooms.*`, against a D16 table of roughly twenty-five rows. The delta is the three-key 409 (F-5), the two-key destructive confirm pair, the paused twins the shipped DC-8 pattern requires, the assign reveal's two strings and the Risk 2 line — minus the four re-keyed duplicates F-4 removes. There is still **no he/ar parity guard** in this repo (F15's Risk 5, inherited by F34, F51, F57, F36 and now F58), so the mitigation is unchanged and is why `copy.md` is canonical: **it is one file to one file**, and F-12's assertion is the mechanical half. *Owner: team. Trigger: F45.*

**Parked question, carried forward from the spec and not reopened here:** *should a booking and a queue ticket for the same woman be reconciled?* They are not (spec Out-of-scope). Both surfaces render her honestly — a room tile from her booking, a row from her ticket — and the manager reconciles them by removing one. A pilot day is what decides whether that is worth automating, and D10's `COALESCE` already resolves her to the `customers` name if she is dispatched on both.
