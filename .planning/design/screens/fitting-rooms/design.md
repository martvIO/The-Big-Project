# Screen: Fitting rooms — the rooms panel, its four dialogs, and the staff card's third status (F36 — `RoomsPanel`, a CHILD of F57's shipped `FloorPanel`)

**Date**: 2026-08-03 · **Status**: **DESIGN GATE SELF-APPROVED.** Interview **Q2** named exactly two novel interaction patterns for this run — F34's shift board and F42's capacity matrix (`LOOP-STATE.md`, `rulings_2026_07_31`) — and E7's screens assemble from F34's board shell and F57's shipped `FloorPanel`. So there is **no prototype and no `design-critic` pass**, and every `P-` in §11 carries a resolution rather than a question. **The gate goes away; the design work does not** — this deck and `copy.md` are build tasks (spec D17, D18), not review preconditions.
**Designer**: Claude · **Consumes**: `.planning/specs/fitting-rooms.md` (**D1–D18**, Gate 1 standing-approved) · `.planning/design/system/tokens.md` (**binding**) · `.planning/design/screens/design-system/manage-restyle.md` (**binding**) · `.planning/design/screens/floor-staff-roles/design.md` (F57 — this panel is a child of that one and inherits every ruling in it) · `.planning/design/screens/shift-board/design.md` **Revision 2** (F34's board shell, whose D11 live-region rule and D14 pause control govern here unchanged) · `packages/ui` and `apps/manage` **as shipped**
**Copy**: `copy.md` in this directory — **it is canonical, this deck's inline Hebrew is illustrative.** Spec D17 says so in as many words, and the F57 precedent is that three corrections landed in `copy.md` first.
**Prototype**: **none, deliberately.** The two questions a prototype would answer here — is a five-second beat usable, is a one-tap reversible act right under a thumb — were answered at F34's gate and the mechanisms are now shared code (`usePoll`, `FloorPanel.toggle`). This feature introduces no beat, no poll, no pause control and no live region that F34 and F57 have not already put in front of a user.

**What this deck is NOT.** It is not a redesign of F57's staff cards. F57 shipped `FloorPanel` as PR #33 and this feature adds **one status value, one occupancy line and one corrected boolean** to it (§6). It is not a redesign of F34's board — `BoardSection` is untouched. It is not a new console section: **`App.tsx` is untouched** (spec D15), and `Nav.test.tsx`'s counts are an assertion that nothing was added, not an omission.

⚠ **Re-verified 2026-08-03 against the tree, and the numbers spec D15 and AC15 quote have MOVED — the rule survives, the arithmetic does not.** F53 (PR #35, `18127e7`) merged after that spec was written and added the `customers` section. `App.tsx:20-33` now carries **twelve** `SectionKey` members, not eleven, and `Nav.test.tsx` now asserts **owner eleven** (`:103`), **shift manager nine** (`:110`, a `.slice(0, 9)`), **floor roles one**, and `NAV_LABELS` **11** (`:156`). That file's own comment records why this is a trap rather than a detail — *"the three numbers in this file's assertions move TOGETHER every time a `roles: ALL` row is added … F53 moved four of the five and left this one at ten, which is why it is spelled out here: a nav row is five coordinated edits, not one"* (`:149-154`). **F36 adds no row, so all of them stay where F53 left them and `Nav.test.tsx` needs no edit** — which is exactly what spec AC15 means and is unaffected by the restated figures. A builder checking AC15 against the spec's literal "owner ten / shift-manager eight" would read a green test as a red one. *Reported as a spec gap; the spec is not edited from here.*

---

## 0. Scope

Five surfaces, all inside the shipped `<FloorPanel/>`, all reached by the two roles that see it under «לוח היום» and the three roles for whom it is the whole product.

| Surface | Who sees it | Shape |
|---|---|---|
| The **rooms panel** — one tile per room | all five roles | `<RoomsPanel/>` rendered by `FloorPanel` **above** the staff list (spec D15) |
| The **registry dialog** — add / rename / reorder / deactivate / delete | owner, shift_manager | `<RoomsRegistryDialog/>`, the shipped `Modal` |
| The **dress dialog** — bind a gown to a room | all five | `<RoomDressDialog/>`, the shipped `Modal` |
| The **handover dialog** — give the room to a colleague | owner, shift_manager | `<RoomHandoverDialog/>`, the shipped `Modal` |
| The **staff card's third status** | all five | three lines inside the shipped `FloorPanel` card (§6) |

**Zero new `packages/ui` components and zero new variants.** Everything is `Card`, `Badge`, `Button`, `Input`, `Select`, `Toggle`, `Modal`, `EmptyState`, `Skeleton` and the two shipped bidi helpers (`isolateLtr`, `isolateBidi` — `lib/booking.tsx:74,101`). Verified against the shipped files rather than assumed: `Badge.tsx:15-21` exports `neutral` / `success` / `danger` / `muted` / `warning`, which is exactly the four-value tile vocabulary §2.3 needs; `Button.tsx:36` gives `md` a `min-h-11` (44px) and `:62` applies `focusRing` unconditionally; `Modal.tsx:19-49` is a native `<dialog>` with a free focus trap, Esc handling and focus return, and its own comment records that **two Modals may be mounted at once** (`:21-23`), which is what §5.3's delete confirm relies on; `Select.tsx:12` carries the *"native `<select>` — no custom dropdown in v1 (a11y cost not worth it)"* decision this feature would otherwise re-argue. **One new colour pair enters nothing** — the ledger is unchanged (§9).

### Binding inheritances (obeyed, not restated)

From **`tokens.md`**: the gold law (`--color-gold-strong` never carries text — **it appears on this screen zero times**); focus ring on every control; ≥44×44 touch targets (law 7); no raw px in app code; no colour communicates alone (law 2); `prefers-reduced-motion` is already global (`theme.css:155-163`).
From **`manage-restyle.md`**: 720px content cap at every breakpoint (`ConsoleShell.tsx:84`); the three-register split (an **outage** is `text-ink-muted`, a thing-she-must-fix is `text-danger`, a nothing-failed **notice** is `text-warning-text`); `EmptyState` over a blank column; inline muted cues over Toasts; **never override a `packages/ui` component's own utility from the call site** (F15 F-6 — `cn()` is a plain join and the consumer loses); the destructive pattern is a `danger` trigger → `Modal` with a ghost dismiss and a `danger` confirm.
From **`shift-board/design.md` Revision 2**: the poll may never write into a live region (its D11); a live region is written **only when its value actually changes** (its **F-7**); a tick may not repaint while a pointer is down (its **F-8**); the `{401,403}` terminal pair are two states, not one.
From **`floor-staff-roles/design.md`**: the freshness row is never announced and never `aria-hidden`; pause/resume is one button whose **name** changes, never `aria-pressed`; **which control EXISTS is the rendered form of the authorization axes** — no disabled button, no lock glyph, no «אין לך הרשאה» line, no tooltip; the WORD carries the state and the colour never does; a display name takes a **bare `<bdi>`** and a numeric run takes `<bdi dir="ltr">` (its **F-11**); `staff.loadFailed`, `floor.pause*`, `floor.resume*`, `floor.paused*`, `floor.stale*`, `floor.updatedAt`, `floor.idleStopped`, `floor.refresh`, `floor.reload`, `floor.sessionEnded` and `floor.accessEnded` are **shipped and reused unchanged**.

### Explicitly NOT here — with the spec's reasons

| Not shipped | Reason |
|---|---|
| A second poll loop, a second freshness row, a second pause control, a second `role="status"` region on the panel | Spec **D15**, and the LOOP-STATE ruling in as many words. `RoomsPanel` is a **child** of `FloorPanel`, so it inherits the one tick, the one 2.2.2 mechanism and the one announced region. `lib/usePoll.ts` gets a **zero-line diff** |
| A twelfth nav section, a «חדרים» row, any `App.tsx` change | Spec D15. The rooms are content of the floor, not a destination |
| Booking a room in advance, a room calendar, "hold room 2 for the 14:00" | Spec Out-of-scope. Rooms are claimed live |
| A room `capacity` field, "2 brides in the stage room" | Spec Out-of-scope: a space that holds two brides is **two rows in the registry**. A capacity column would turn D3's index into a count, which is a read-then-write, which is the lock the ruling forbids |
| A queue, a wait estimate, "next free room", auto-assignment | A human picks the room (spec Out-of-scope) |
| An occupancy timer, an SLA colour, anything that fires on elapsed minutes | The number is displayed; **nothing watches it** (spec Out-of-scope, F57's D7 for breaks, same absence) |
| Per-dress verdicts, ratings, photos, fitting notes | E9's alteration intake |
| Drag-and-drop reordering | Spec D18: a WCAG 2.1.1 keyboard failure axe cannot see. Reorder is a labelled `<input type="number">` (§5.2) |
| A history view of past assignments | Nothing reads them in v1 (spec Out-of-scope) |
| An SOS control on a tile | F37's, on this feature's assignment row |

---

## 1. The rooms panel — mobile 375, loaded

**375 is the primary case.** Pre-decided #27 puts the console on each staffer's own phone. For reception / sales_assistant / seamstress this panel and the staff list under it are the **entire product**.

⚠ **The diagrams in this deck are drawn LEFT-TO-RIGHT, for legibility in a Markdown file. The rendered pages are RTL** (`lang="he" dir="rtl"`). So in the shipped console every run inverts: **inline-start is the physical RIGHT and inline-end is the physical LEFT.** The room label starts at the physical right; the `Badge` sits to its physical left; every `justify-end` action row puts its controls at the physical **left**. This deck ships **no prototype and no `design-critic` pass**, so these ASCII blocks are the sole visual source — a builder implementing the drawn order ships a mirrored panel that passes axe, passes every named vitest assertion, and reads wrong to the only users who will ever see it. The blocks are not redrawn in RTL because a hand-mirrored ASCII diagram is one more thing to keep true; this paragraph is cheaper and says the same. **It is F57's §1 warning, repeated because this panel is denser and the cost of getting it wrong is higher.**

```
+--------------------------------------------------+
|  … <BoardSection/> above, on the board section    |   owner / shift_manager only
+--------------------------------------------------+
|  <main #console-main tabIndex=-1, max-w-720>      |
|                                                   |
|  צוות בקומה                                        |   h2 — F57's, UNCHANGED, tabIndex={-1}
|                         עודכן 14:07  [ השהיה ]     |   FRESHNESS ROW — F57's, UNCHANGED.
|                                                   |     first tab stop inside the panel.
|  <p role="status">  (empty at rest)               |   the ONE announced region — F57's.
|                                                   |     rooms cues write HERE (§10.2)
|                                                   |
|  חדרי מדידה                    [ ניהול חדרים ]     |   h3 (§10.5 / F-1), tabIndex={-1}.
|                                                   |     registry trigger: ELEVATED ONLY,
|                                                   |     inline-end, ghost md
|  +------ Card (surface, p-6) -----------------+   |
|  | <ul class="divide-y divide-border">        |   |
|  | ┌ <li data-room-id> ───────────────────    |   |
|  | │ חדר 1                        [ פנוי ]    |   |   FREE  — label bare <bdi>, no ellipsis
|  | │ לקוחה — חדר 1                            |   |   Select LABEL carries the room (§3.1)
|  | │ [ ללא לקוחה                        ▾ ]   |   |
|  | │                        [ תפיסת החדר ]    |   |   secondary md, own line at ≤767
|  | └                                          |   |
|  | ┌ חדר 2                        [ תפוס ]    |   |   OCCUPIED
|  | │ דנה כהן                                  |   |   holder — bare <bdi>, font-semibold
|  | │ תופרת                                    |   |   her role — muted WORDS, never a Badge
|  | │ לקוחה  מיכל                              |   |   «לקוחה» muted + name bare <bdi> (§3.4)
|  | │ כבר 42 דק'                               |   |   elapsed — number in <bdi dir="ltr">
|  | │ שמלות בחדר                               |   |   muted group label, NOT a heading
|  | │   ורוניק · 38                 [ הסרה ]   |   |   one row per binding, ghost md
|  | │   סברינה · 40                 [ הסרה ]   |   |
|  | │        [ הוספת שמלה ] [ העברה ] [ שחרור ] |   |   ghost · ghost(elevated) · secondary
|  | └                                          |   |
|  | ┌ הבמה                  [ מחוץ לשירות ]     |   |   OUT OF SERVICE — muted label,
|  | │                                          |   |     muted Badge, NO claim control (§2.4)
|  | └ </ul>                                    |   |
|  +--------------------------------------------+   |
|                                                   |
|  +------ Card (the SHIPPED staff list) --------+  |   §6 — unchanged except the third
|  | ┌ דנה כהן                    [ תפוסה ]      |  |     status, the occupancy line and the
|  | │ תופרת                                     |  |     corrected `onBreak` (F-2)
|  | │ חדר 2 · מיכל · כבר 42 דק'                 |  |
|  | └                                           |  |
|  +---------------------------------------------+  |
+--------------------------------------------------+
```

- **Order is the server's and the client never re-sorts.** The payload is `(sort_order, created_at)` (spec D1, D11) and the panel renders it as given. A five-second repaint that re-sorts rows is a repaint a finger cannot travel across, which is the whole reason D1's index carries both keys.
- **One `Card`, one `<ul className="divide-y divide-border">`, one column at every width.** §11 **P-1**.
- **The Card's `p-6` is not overridden** (F15 F-6).
- **Rooms above the staff list** (spec D15): a staffer opens this screen to find a free room; the staff cards are the reference, the rooms are the action.
- **The freshness row and the pause control stay exactly where F57 put them** — first stop inside the panel, before any content, because *"a 2.2.2 mechanism placed after the content it governs is reachable only by walking the list that is repainting under the walk"* (`FloorPanel.tsx:434-440`). They now govern **two** repainting regions, which is why §10.4 forbids cutting their tests as redundant.

### 1.1 One tick, one pause, one announced region — and what that buys

`RoomsPanel` receives `rooms`, `serverNow`, `fetchedAt`, `selfId`, `role`, `mutate` and `onCue` as props from `FloorPanel` (spec D15). It owns no timer, no `usePoll` instance and no pause state.

Three things fall out and each is an a11y win rather than an architectural convenience:

1. **One SC 2.2.2 mechanism, not two.** F57's D12 ruled that two pause controls on the board screen (board + floor) is the answer rather than a defect *provided their accessible names distinguish the regions*. **Three would start to be a defect** — and F36 adds none. The shipped «השהיה — עדכון הצוות» now stops the rooms too, which is honest: it stops the one tick that repaints both.
2. **One `role="status"`, so a room cue and a break cue cannot talk over each other.** Two polite regions on one screen queue unpredictably across AT; one region is a single sequence of the user's own outcomes.
3. **One freshness claim.** «עודכן 14:07» is true of the rooms and of the staff cards simultaneously, because they arrive in the same response. Two stamps could disagree by an interval and a shift manager would have no way to know which one to believe.

**Do NOT reach for `poll.pause()` from any dialog** (spec D15). The pause control's accessible name would then announce a state the user did not choose — F57's D12, and the reason there is exactly one named control per region.

### 1.2 The registry trigger — one on screen at a time

| Registry state | Trigger | Rendered for |
|---|---|---|
| **No rooms configured** | `EmptyState`'s `action` slot — «הוספת חדר» `Button secondary md` | owner, shift_manager only |
| **One or more rooms** | the heading row's inline-end — «ניהול חדרים» `Button ghost md` | owner, shift_manager only |

**Exactly one exists at any moment**, and both open the same `RoomsRegistryDialog`. Two doors to one dialog on a screen that otherwise holds nothing would be a puzzle; two labels because the act reads differently to a boutique that has never configured a room and to one that is renaming «הבמה». The empty-state entry opens the dialog with the **add row's** `Input` focused, because there is nothing else in it to do.

⚠ **The focus-return fallback is the FIRST thing a new boutique hits, not a rare path.** She opens the dialog from the `EmptyState` CTA, types «חדר 1», saves, closes — and the trigger she came from **no longer exists**, because the panel now renders tiles and the heading-row trigger instead. F51's shipped `isConnected` check (`StaffSection.tsx:80-92`) is the pattern, and the fallback target is the rooms `h3`. Named because a builder reading "the native `<dialog>` returns focus to its trigger for free" will not write the fallback, and the very first registry session in every boutique's life is the case that needs it.

---

## 2. The tile — anatomy, and the four states of a room

### 2.1 What a tile shows

| Slot | Content | Bidi | Notes |
|---|---|---|---|
| Label row | `label` + the status `Badge` | **bare `<bdi>`** on the label | `font-semibold text-ink`, `break-words`, **no ellipsis and no truncation, ever** — a panel that abbreviates «חדר המדידה הגדול» and «חדר המדידה הגדול השני» makes two rooms look like one, which is the exact failure this feature exists to remove |
| Out-of-service line | `rooms.inactive` as a **word**, only when `is_active === false` **and** the room is occupied | — | §2.4 — the Badge is spent on the occupancy in that one case, so the flag takes a line |
| Holder row | `staff_display_name`, or `rooms.holderGone` when it is `null` | **bare `<bdi>`** | `font-semibold text-ink`. `dir="ltr"` on a Hebrew name is itself a bidi defect and it looks deliberate (F57 F-11) |
| Role line | the holder's role through `roleLabelKey()` — **`lib/roles.ts` unchanged** | bare `<bdi>` | `--text-sm --color-ink-muted`. **Muted words, never a second `Badge`** — §11 **P-2**, E7 criterion 2 names the role and D11 puts `staff_role` on the wire for it |
| Client row | `rooms.clientLabel` (muted) + `client_label` (bare `<bdi>`), or `rooms.anonymous` alone | **bare `<bdi>`** | §3.4. **Never truncated** — spec D18 |
| Elapsed row | `rooms.elapsed` / `rooms.elapsedJustNow` | number in `<bdi dir="ltr">` via `isolateLtr` | §2.5 |
| Dress list | `rooms.dresses` group label + one row per binding | name bare `<bdi>`, size `<bdi dir="ltr">` | §4.3. Absent entirely when there are no bindings — a group label over nothing is five pixels of confusion |
| Alert | at most one, `role="alert" tabIndex={-1}` | — | §3.3 |
| Action row | one to three `Button`s (§2.2) | — | `justify-end`, own line at ≤767 |

**The tile is not a button and navigates nowhere.** There is nowhere to navigate to — the room *is* the record.

### 2.2 Which control exists — the two authorization axes, rendered

⚠ **A 403 is TERMINAL for the whole floor screen**, and for the three floor roles that is the entire product going dark: `usePoll.terminalOf` returns `"access"` for **any** 403, `poll.fail(error)` stops the loop permanently, and `FloorPanel.tsx:349-367` returns the terminal `<section>` and **clears every card**. So a control the server will refuse is not an in-tile alert — it is a blank screen and a reload button. F57 avoided that by **never rendering a control the caller may not use** (`FloorPanel.tsx:525-530`), and this panel carries the rule across for four controls (spec D15).

| Control | Rendered only when | Variant |
|---|---|---|
| claim «תפיסת החדר» + its client `Select` | the room is free **and** `is_active` | `secondary md` |
| the claim's `staff_user_id` field | **never sent as anything but `selfId`** unless `ELEVATED.has(role)` | — |
| release «שחרור» | `assignment.staff_user_id === selfId \|\| ELEVATED.has(role)` | `secondary md` |
| handover «העברה לעמיתה» | `ELEVATED.has(role)` | `ghost md` |
| add dress «הוספת שמלה» | there is an assignment — **all five roles, no ownership check** | `ghost md` |
| remove dress «הסרה» | same — **all five, no ownership check** | `ghost md` |
| registry trigger (either form) | `ELEVATED.has(role)` | §1.2 |

**No disabled buttons, no lock glyphs, no explanatory line — absence.** F57's three reasons hold unchanged: a disabled control with no explanation is worse than an absent one; an explanation would teach the permission model on a screen she opens fifty times a shift to answer a question she did not ask; and any such affordance would be the client asserting a rule the server owns.

**The two dress controls are deliberately open to all five and carry no ownership check** (spec D4). A colleague fetching a second gown for a fitting already in progress is the normal case on a shop floor, and binding a dress is not a destructive act on the holder's room — release and handover take the room away from her, which is why those two carry the axes and these two do not. `removed_by` is what keeps it accountable, and the permissiveness is **asserted as a positive** in the service matrix so it cannot arrive by omission.

**One `secondary` per tile, and it is the act that ENDS the tile's current state.** Free tile → «תפיסת החדר». Occupied tile → «שחרור». Everything else is `ghost`. This is a deliberate divergence from F57, where «חזרה» (the return-to-normal act) is `ghost` — and the reason is the **control count, not a change of mind**: a staff card has at most one control, so a ghost is unmissable; an occupied tile has up to three, and three ghosts in a row give a travelling finger nothing to aim at. The ending act is also the time-critical one — a bride is waiting for that room. Never `primary`: `primary` is gold, the storefront's CTA colour, and the console reserves it for save actions (`manage-restyle.md`); six gold buttons on one panel would be a wall.

### 2.3 Status is a word, and the tile carries exactly one `Badge`

| Room | Badge word | Variant | Contrast on paper | Reinforcement |
|---|---|---|---|---|
| free and active | `rooms.free` «פנוי» | `success` (`border-success text-success`) | 5.56:1 ✓ | the claim control exists |
| occupied (active **or** inactive) | `rooms.occupied` «תפוס» | `neutral` (`border-border text-ink`) | 13.89:1 ✓ | the holder's name, the client, the elapsed line, the release control |
| free and `is_active === false` | `rooms.inactive` «מחוץ לשירות» | `muted` (`border-border text-ink-muted`) | 5.61:1 ✓ | the muted label and the **absent** claim control |

**Occupancy wins the Badge, and the out-of-service flag takes a word line when it loses.** This is D12's precedence argument applied one level out and for the same reason: a person is standing in that room, and a screen that puts «מחוץ לשירות» where «תפוס» belongs is denying something a shift manager can see through the curtain. When both are true the tile reads Badge «תפוס» **plus** a muted `rooms.inactive` line under the label — one Badge, both facts, no ambiguity about which is which.

**`neutral` is the slot F57 reserved for exactly this** (`floor-staff-roles/design.md` §2.3: *"`occupied` — F36, not here — `neutral` is the slot it will take"*), and its stated reason survives inspection: `neutral` at 13.89:1 is a stronger, more legible treatment than a blue would be, and **no new colour pair enters the ledger**.

**No emoji, no dots, no glyphs anywhere.** F57's **P-5**, unchanged: an emoji is announced by a screen reader with a name the product did not choose and cannot translate; the console ships **no icon vocabulary at all**, so the first glyph would be a convention with one member; and a coloured dot beside a coloured pill is the same fact twice, which is how a reader learns to read the colour and stop reading the word.

**⚠ "Greyed" is a token swap, never `opacity-*`.** An out-of-service tile renders its label in `--color-ink-muted` instead of `--color-ink` and its Badge as `muted`. It does **not** get an opacity wash, because opacity multiplies every contrast ratio inside the element — a 5.61:1 muted line at `opacity-60` is 3.4:1, under the AA floor, on a screen where IS 5568 is a legal requirement — and **axe computes contrast against declared colours, not against composited pixels**, so it walks past the whole class. Stated because "grey it out" is the instruction a builder will read as an opacity utility.

### 2.4 The four tiles, drawn

```
FREE                          OCCUPIED                      OUT OF SERVICE (free)
+---------------------+       +---------------------+       +---------------------+
| חדר 1      [ פנוי ] |       | חדר 2      [ תפוס ] |       | הבמה  [ מחוץ לשירות ]|
| לקוחה — חדר 1       |       | דנה כהן             |       |                     |
| [ ללא לקוחה     ▾ ] |       | תופרת               |       | (no control at all) |
|     [ תפיסת החדר ]  |       | לקוחה  מיכל         |       +---------------------+
+---------------------+       | כבר 42 דק'          |
                              | שמלות בחדר          |       OUT OF SERVICE + OCCUPIED
HOLDER GONE                   |  ורוניק · 38 [הסרה] |       +---------------------+
+---------------------+       | [שמלה][העברה][שחרור]|       | חדר 3      [ תפוס ] |
| חדר 4      [ תפוס ] |       +---------------------+       | מחוץ לשירות         |
| אשת הצוות שתפסה     |                                     | נועה לוי            |
| את החדר כבר לא      |       JUST RELEASED = the FREE      | ...                 |
| ברשימה.             |       tile, patched in place        +---------------------+
| מיכל                |       from the release response —
| כבר 42 דק'          |       no interstitial, no fade.
|          [ שחרור ]  |   ← elevated only (§2.2)
+---------------------+
```

**Just-released is not a state — it is the free tile, arrived at.** The release answers the full `Room` with `assignment: null` and the tile patches from the server's own row (spec D7, F57's D7 contract), so the occupancy block, the dress list and the two extra controls unmount and the claim control plus its client `Select` appear in one paint. **No fade, no highlight, no "released" flash.** F34's D11 governs: a highlight that can fire every five seconds is a strobing screen for a whole shift, and it draws the eye to *what changed* when the question is *which room is free*. What confirms the act is the announced cue (§10.2) and the tile reading «פנוי».

**The holder-gone tile is real, not defensive.** F51's `StaffUsersRepository.soft_delete` has no interaction rule with an open assignment (spec D11), so a staffer removed mid-fitting leaves a live assignment with no card on the floor. `staff_display_name` is `string | null` on the wire for exactly this, the tile substitutes `rooms.holderGone` for the name **and drops the role line entirely** (there is no role to show), and only an elevated caller gets a release control — because the two axes cannot match a person who is gone (spec D7). The client, the elapsed time and the dress bindings all still render: they are facts about the room, not about her.

### 2.5 Elapsed minutes — anchored on the server, frozen when the panel freezes

`minutes_elapsed` is **not on the wire** and is **not** `Date.now() − assigned_at` (spec D11). The envelope carries `server_now`; the client computes

```
minutes = Math.floor(((serverNow + (Date.now() - fetchedAt)) - assignedAt) / 60000)
```

so only the *elapsed* device clock is trusted — drift-free over five seconds — and never the absolute one. «כבר 400 דק'» for a fitting that started twenty minutes ago is a number a shift manager acts on.

Three renderings the spec's one key does not cover, resolved here:

- **`fetchedAt` is not new state.** `FloorPanel` already stores the instant each successful tick resolved (`setUpdatedAt(new Date().toISOString())`, `FloorPanel.tsx:112`) — that value *is* the fetch anchor, and it is already passed nowhere, so §1's prop list adds it rather than adding a `useRef`.
- **The number is computed at render, so it freezes exactly when the panel freezes.** Nothing sets an interval to advance it. That is correct and not a limitation: a paused panel says «מושהה · עודכן 14:07», and a minute counter still climbing beside a stopped stamp would be the panel disagreeing with itself. Between ticks the count is at most five seconds stale, which is invisible in a minute counter.
- **Under one minute — including a negative — renders `rooms.elapsedJustNow` «זה עתה».** Two reasons, and the second is the spec's own: «כבר 0 דק'» is odd Hebrew and it is what **every fitting in the boutique reads for its first minute**; and spec D2's own ⚠ records that `created_at` comes from the **database** clock while everything else on this row comes from the **service's** Python clock, so `assignedAt > serverNow` is representable and a raw subtraction can go negative. `Math.max(0, …)` plus one string removes both, and «זה עתה» is a fact rather than a clamp artefact.

**No hours branch, no pluralisation, no date library.** «כבר 95 דק'» is exactly the alarm signal a shift manager wants and «כבר שעה ו-35 דק'» is a second key and an arithmetic branch to say the same thing less usefully. The abbreviated «דק'» is invariant in Hebrew, which is why one key covers 1 and 95 — **stated so nobody "fixes" it into an i18next plural rule**, which would be the first in this console. Elapsed minutes are arithmetic on two ISO instants and involve no timezone at all (spec D17), so `scripts/qa-greps.sh`'s unzoned-formatter grep gains nothing to find.

---

## 3. The claim, and the 409 loser's screen

### 3.1 The claim — one tap, or two

The claim lives **on the free tile itself. There is no dialog** (spec D16): no focus trap to write, no return contract to test, no fourth component. One tap if she does not care which bride, two if she does.

```
לקוחה — חדר 1                 ← the Select's VISIBLE label, carrying the room
[ ללא לקוחה                ▾ ]  ← @boutique/ui Select, defaulted to rooms.clientNone
                [ תפיסת החדר ]  ← Button secondary md, aria-label «תפיסת החדר — חדר 1»
```

**The `Select`'s visible label carries the room, and that is what disambiguates four identical pickers.** Four `<select>`s all labelled «לקוחה» is a screen-reader dead end at exactly the moment the panel is busy. **Declined the alternative** — a visible «לקוחה» plus an `aria-label` «לקוחה — חדר 1» — which also satisfies WCAG 2.5.3 label-in-name but costs a second key, a second string to keep in sync, and an `aria-label` that overrides a correctly wired `<label htmlFor>`. Putting the room in the visible label makes the accessible name **be** the visible label, so 2.5.3 is satisfied by construction rather than by an assertion.

**The picker is absent, not empty, whenever it has nothing to offer** (spec's states table): an empty client list, a failed `GET /manage/floor/clients`, or a boutique where nobody has checked in yet renders the claim control alone and the claim proceeds anonymously. That is the ordinary early-morning tile, and it is what keeps §11 **P-3**'s "four selects on one panel" objection small in practice.

**A truncated client list renders one muted line under the picker** and never a number (`rooms.clientsTruncated`) — F34's `limit=50` precedent for the same class of honesty, and copy rule 5 (no string names a server-owned limit, because the limit is the server's to change).

### 3.2 The tile alert has TWO registers and neither is red

`manage-restyle.md` splits three registers: an **outage** is `text-ink-muted`, a thing-she-must-fix is `text-danger`, a nothing-failed **notice** is `text-warning-text`. F57's in-card alert is `text-danger` for its one 404. **This panel diverges, deliberately:**

| Condition | Register | Why |
|---|---|---|
| 409 `ROOM_OCCUPIED` · 409 `STAFF_OCCUPIED` · both `*Unknown` variants | `--color-warning-text font-semibold` (5.20:1 on paper ✓) | **Nothing failed and she did nothing wrong.** Two staffers reaching for one curtain at the same second is the ordinary shop floor, and it is the exact event this feature exists to settle. Red would frame a normal race as her mistake |
| 404 — the room is gone (`rooms.error.notFound`) · the assignment is gone (`rooms.error.assignmentGone`) | `--color-warning-text font-semibold` | Nothing failed either: the screen was one tick behind and the next tick repairs it, which is what the sentence promises |
| anything unmapped (a 5xx, a dropped request) | `--color-ink-muted`, the shipped `staff.loadFailed` | The **outage** register. Not her problem and not actionable from this tile |
| **anything at all** | **never `--color-danger`** | The only `danger` in this feature is the registry's delete confirm `Button` (§5.3), which is the shipped destructive pattern and is a *choice*, not a report |

**Two 404 sentences, not one.** A 404 on a *claim* means the room is gone or out of service; a 404 on a *release*, *handover* or *dress* means the assignment is gone — somebody already released it. One string for both would be wrong on one of them every time, and «החדר כבר לא זמין» is actively misleading when the room is fine and the fitting simply ended.

### 3.3 The 409 loser's screen — she tapped claim and someone beat her

This is the screen the feature exists to deliver. **Requirements: it must NAME the current occupant, and it must not look like an error page.**

```
+-----------------------------------------+
| חדר 2                        [ פנוי ]   |  ← still «פנוי»: the tile has not been
| לקוחה — חדר 2                           |    repainted yet, and the panel is NOT
| [ ללא לקוחה                        ▾ ]  |    optimistic. It patches from the
|                                         |    server, and the server refused.
| דנה כהן כבר בחדר הזה.                   |  ← role="alert" tabIndex={-1},
|                                         |    --color-warning-text font-semibold,
|                         [ תפיסת החדר ]  |    FOCUS MOVES HERE (§10.1 move 1)
+-----------------------------------------+
        ↓ ~5s — the next tick, unforced
+-----------------------------------------+
| חדר 2                        [ תפוס ]   |  ← the alert clears, the tile repaints,
| דנה כהן                                 |    and it shows EXACTLY the person the
| תופרת                                   |    alert named. Focus hands back to the
| מיכל                                    |    tile's control — or, here, to the
| כבר 0 דק'  →  זה עתה                    |    rooms h3, because the claim control
+-----------------------------------------+    is GONE (§10.1, and it is the common
                                               case on this path, not the rare one)
```

**Six things make it information rather than an error page**, and each is a decision:

1. **It names a person.** «דנה כהן כבר בחדר הזה.» — the `details.staff_display_name` from the 409 body (spec D14), rendered mid-sentence through `isolateBidi` so a Latin-script name inside a Hebrew sentence does not throw the final period across the line.
2. **It is not red** (§3.2).
3. **It is in the tile, not a banner.** A panel-level error names no room, and with five tiles on screen a banner would make her hunt for which one refused her.
4. **The tiles stay, the poll keeps running, nothing is cleared.** Only 401 and 403 are terminal.
5. **The tile stays fully interactive.** The claim control does not disappear and is not disabled — the room may genuinely free up in the next ten seconds, and a control that vanishes on a refusal teaches her that the screen punishes trying.
6. **The alert keeps its own promise inside five seconds.** The very next tick repaints the tile into an occupied one showing the person the sentence named. That convergence is the design answer to "does it look broken": a message that is confirmed by the screen a moment later reads as *reporting*, and one that is never confirmed reads as *failing*.

**When the occupant read comes back empty** — the winner released between the violation and the read, which is a real branch the spec pins with its own `db` test — the 409 arrives with **no `details`** and the tile renders `rooms.error.roomOccupiedUnknown` «החדר נתפס זה עתה. נסי שוב.» instead. **A sentence that admits it does not know beats «{{name}} כבר בחדר הזה.» rendering with an empty interpolation on a legally binding surface**, which is exactly why D14 types `details` as `Record<string, string> | undefined` and never `| null`.

**`STAFF_OCCUPIED` is a different sentence with a different remedy**, which is why it is a different code (spec D14): «היא כבר בחדר אחר: חדר 5.» — the target staffer already holds a room, and the fix is to release that one, not to take another. Its `*Unknown` variant «היא כבר בחדר אחר.» is a **strict prefix** of the full form, so the two never read as two different facts.

### 3.4 The client label, and what this panel does and does not disclose

**The assignment stores no personal field of any kind** (spec D9). The tile's client label is resolved on every read from the live `bookings` → `customers` rows, and when either is gone the label is `null` and the tile renders `rooms.anonymous` «ללא לקוחה מקושרת». That is the *default* render for any claim made without a booking — a staffer prepping a room, or every walk-in until F58 ships — so it is on screen from day one rather than being dead code that first runs the day F20's sweep deletes something.

**The client name renders as its own element beside a muted label word, never interpolated into a sentence:**

```
לקוחה  מיכל          ← <span class="text-ink-muted">לקוחה</span> <bdi>מיכל</bdi>
ללא לקוחה מקושרת     ← the anonymous case: one muted line, no label word
```

This is a deck-wide rule and it is why this feature needs no third bidi helper: **wherever a value can be its own element, it is.** `isolateLtr` / `isolateBidi` split a translated string around **one** value and return a `ReactNode`, so they cannot be chained — a sentence carrying two interpolated names has no shipped way to isolate both. Structuring the value as a sibling element sidesteps the whole problem, and interpolation is reserved for the cues and the error sentences, where the value genuinely sits mid-sentence and the word order is the copy's to own. `copy.md` §8 is where each interpolation names its helper.

**No truncation and no first-name split, ever** (spec D9). Splitting `customers.name` on whitespace to synthesise a first name would be a new, untested string transform on a legally sensitive surface that mangles Hebrew compound names, for a disclosure reduction of roughly zero.

---

## 4. Release, handover, and the dresses

### 4.1 Release

One tap, no confirm. It is reversible in one tap (re-claim), it writes one timestamp, and F34's precedent is one tap for a reversible act. The control is `secondary md`, `aria-label` «שחרור — חדר 2», and it exists only for the holder or an elevated caller (§2.2).

**A second release is a 200 and reads identically to the first** (spec D7): she wanted the room free, the room is free. `rooms.releasedCue` announces the same sentence either way — F57's F-ok / F-noop argument verbatim, *"telling her she lost a race would be telling her she was wrong when she was right"*.

**Declined a confirm step.** A shift manager clearing up after someone who went home does it several times a shift, and a confirm on a reversible act at that frequency is a tax on the common case. The destructive act on this surface is the registry's **delete**, and that is where the confirm lives.

### 4.2 Handover — `RoomHandoverDialog`

Trigger «העברה לעמיתה» `ghost md`, `aria-label` «העברה לעמיתה — חדר 2», **elevated only**. The shipped `Modal`, title «העברת החדר».

```
+-- Modal ---------------------------+
| העברת החדר                         |   Modal's own <h2>, from `title`
|                                    |
| העברה אל                           |   Select LABEL (required prop)
| [ נועה לוי                     ▾ ] |     — the colleague list
|                                    |
|          [ ביטול ]   [ העברה ]     |   footer: ghost dismiss + secondary confirm
+------------------------------------+
```

- **The colleague list is built from the `staff` array the poll already carries.** No new endpoint, no second fetch: filter to `id !== assignment.staff_user_id` and exclude cards whose `status === "occupied"`, so the 409 `STAFF_OCCUPIED` is usually **prevented** rather than explained (spec's Frontend-changes table).
- **A colleague on a break is NOT excluded, and her option says so.** «נועה לוי — בהפסקה». The server accepts a handover to her, the indexes do not forbid it, and hiding her would be the client asserting a rule the server does not have — F57's discipline, and the realistic case is a staffer who forgot to end a break, which §6's corrected boolean now makes visible everywhere else too. `<option>` takes no markup, so the name needs no `<bdi>` — the same exemption an `aria-label` gets.
- **Empty list → `rooms.handoverNobody`** «אין עכשיו עמיתה פנויה לקבל את החדר.» and no confirm control. The dialog still opens, because a trigger that does nothing is worse than a dialog that explains.
- **The confirm is `secondary`, not `danger`.** A handover destroys nothing: the assignment survives, `created_at` does not move, every dress binding survives by not being touched (spec D8). The `danger` treatment is reserved for the one act that removes a row.
- **The residual 409** — the receiving colleague took a room between the tick and the confirm — renders **inside the dialog** in the notice register, naming her current room, and the dialog stays open so the shift manager can pick somebody else without reopening it.
- **A 404** — the assignment was released underneath the open dialog — closes the dialog and hands the tile's alert `rooms.error.assignmentGone`, with focus landing **in that alert** (§10.1 move 4's collision rule).

### 4.3 Dresses — the list, and `RoomDressDialog`

The bound gowns render as a `<ul>` under a muted `rooms.dresses` group label. **Rows, not chips:**

```
שמלות בחדר                        ← <p class="text-sm text-ink-muted">, NOT a heading
  ורוניק · 38          [ הסרה ]   ← name bare <bdi> · size <bdi dir="ltr"> · ghost md
  סברינה               [ הסרה ]   ← no size bound: the separator and the size are absent
```

**Declined chips.** Three reasons: the tile's one `Badge` is the occupancy (§2.3) and a row of `Badge`s would make the pill vocabulary mean two things; a removable chip's `×` is an icon, and the console ships no icon vocabulary; and a remove affordance inside a chip is the classic 44×44 failure — the target ends up the size of the glyph. A `ghost md` button reading «הסרה» is 44px tall, has a visible text name, and needs no new component.

**The group label is a `<p>`, not a heading, and the `<ul>` gets no accessible name.** A screen reader reads the paragraph and then the list in document order, which is what a sighted reader does. **Declined `aria-labelledby`**: it needs a `useId()` per tile to avoid duplicate ids across five rooms, and it buys a list name that the preceding paragraph already gives for free.

**When there are no bindings, neither the label nor the list renders** — only «הוספת שמלה». A group label over an empty list is a paragraph that says nothing.

`RoomDressDialog` — the shipped `Modal`, title «הוספת שמלה — חדר 2»:

```
+-- Modal ------------------------------+
| הוספת שמלה — חדר 2                    |
|                                       |
| חיפוש שמלה                            |   Input label — client-side filter,
| [ ורו                              ]  |     no ?q=, no debounce, no second request
|                                       |
| שמלה                                  |   Select label
| [ ורוניק                          ▾ ] |
|                                       |
| מידה                                  |   Select label — the chosen dress's sizes,
| [ ללא מידה                        ▾ ] |     defaulted to «ללא מידה»
|                                       |
|           [ ביטול ]   [ הוספה ]       |
+---------------------------------------+
```

- **`GET /manage/floor/dresses` fires once, when the dialog opens.** Never on the poll (spec D16).
- **«ללא מידה» is always the first size option and the default.** A sample gown carried in before a size is chosen is D4's stated ordinary case, and `dress_size` is nullable for exactly that.
- **A dress with no sizes at all**: the size `Select` is absent and the add binds a null size. Not a disabled empty picker.
- **A filter that matches nothing** removes the two `Select`s and the «הוספה» button and renders one muted line, `rooms.dressNoMatch`. A `<select>` with zero `<option>`s is a dead control that looks live.
- **An empty catalog** renders `rooms.dressEmpty` and **no CTA** — three of the five roles cannot reach «שמלות» at all, and pointing them at a door that answers 403 is the trap §2.2 exists to avoid.
- **Truncation** renders `rooms.dressTruncated`, which names neither a count nor the limit.
- **A concurrent double-add is a success** (spec D4), so the cue is the same sentence either way: two staffers tapping «ורוניק» at the same instant both wanted the dress in the room, and the dress is in the room.

---

## 5. The registry — `RoomsRegistryDialog`

The owner's «חדר 1 / חדר 2 / הבמה», typed once and never again.

### 5.1 The data contract, because this dialog lives inside a component that repaints every five seconds

There is no registry list endpoint — the dialog renders from the polled `rooms` prop. `holdRef` does not help: it consumes **one** tick on `pointerdown` and typing fires no pointer events (`FloorPanel.tsx:155-164`). A tick landing while the owner is halfway through «חדר 4» would re-render the rows from server data, and this feature's "patch from the server's row, never optimistic" discipline makes that a **reset** rather than a merge. So, as a contract (spec D15):

> `RoomsRegistryDialog` **seeds its editable rows from `rooms` ONCE at open** and does not re-read from the poll while open. It re-seeds on close, and on any successful write from **that write's own response**.

**Do NOT reach for `poll.pause()`** — the pause control's accessible name would announce a state the owner did not choose (§1.1). Two consequences, both stated rather than discovered: *a room changed underneath the open dialog* (the seeded row is kept; the next open shows the truth) and *the row being confirmed for deletion has vanished* (→ 404, close the confirm, re-seed). `RoomsRegistryDialog.test.tsx` drives a tick with a **dirty input** and asserts the input keeps its value.

**Declined suppressing the poll while any dialog is open** — the obvious way to delete §10.1's move 5 and two states from §7. It freezes the freshness stamp for as long as she takes, with no state on screen to explain the freeze: «אין עדכון מאז» renders after a *failed* tick, not a suppressed one, so the panel would simply stop being current and say nothing. A panel that goes quiet without saying so is the one thing F34's whole freshness contract exists to prevent.

### 5.2 The rows

```
+-- Modal ---------------------------------------+
| חדרי המדידה של הבוטיק                          |
|                                                |
| (empty at rest — role="status" §5.4)           |
|                                                |
| שם החדר                                        |
| [ חדר 1                                     ]  |
| סדר תצוגה   [ 0  ]     [x] פעיל                |
|                        [ שמירה ]  [ מחיקה ]    |
| ---------------------------------------------- |
| שם החדר                                        |
| [ הבמה                                      ]  |
| סדר תצוגה   [ 2  ]     [ ] פעיל                |
|                        [ שמירה ]  [ מחיקה ]    |
| ---------------------------------------------- |
| שם החדר                                        |
| [                                           ]  |   ← the ADD row, always last
|                                   [ הוספה ]    |
|                                                |
|                                    [ סגירה ]   |
+------------------------------------------------+
```

- **Reorder is a labelled `<input type="number">` bound to `sort_order`, never drag-and-drop** (spec D18). Drag's most common implementation is a WCAG 2.1.1 keyboard failure that **axe cannot see** — the same ladder rung and the same legal reasoning D16 uses to refuse an ARIA combobox. Validated against the mirrored `MAX_SORT_ORDER`, and **negatives are legal and useful**: they are how a row moves to the front without renumbering the rest, which is the whole point of the symmetric bound D1 chose.
- **Two commit shapes, and the split is by the nature of the fact.** The `Toggle` (`is_active`) and «מחיקה» act **immediately** — each is a single reversible or confirmed fact, and F57's break toggle is the precedent. The label and the order need an explicit «שמירה», because typing has no natural commit point. The save button is **always enabled**: tapping it on a clean row is a `PATCH` that changes nothing and answers 200, which is cheaper than dirty-tracking three fields and matches this codebase's F-noop philosophy everywhere else.
- **The add row is last**, because a new room defaults to `sort_order = 0` and the tiebreak is `created_at` (spec D1), so it lands at the end of the zero group — which is where the list will show it.
- **Deactivating an occupied room is allowed and does not evict anybody** (spec D1). The tile greys, the claim control goes, and the bride in there stays in there. That is the parked question §12 records, and the alternative — evicting a half-dressed bride to satisfy a flag — is clearly worse.
- **Validation is field-local and comes free from `Input`**: `Input.tsx:39-53` wires `aria-invalid`, `aria-describedby` and a `role="alert"` `--color-danger` message under the field. That is the one place `danger` is correct on this surface — it is a thing she must fix, in the field she must fix it in. **Not overridden from the call site** (F15 F-6).

### 5.3 Delete — a nested `Modal`, and why not the inline two-step

Trigger `Button variant="danger" size="md"` → a **second** `Modal`, footer `ghost` dismiss + `danger` confirm. That is `manage-restyle.md`'s shipped destructive pattern unchanged, and `Modal`'s own comment already anticipates two mounted at once (`Modal.tsx:21-23`). Native `<dialog>` stacks in the top layer, Esc closes the topmost only, and focus returns to the trigger — all for free.

**The inline two-step was considered and declined on evidence.** The storefront ships a reveal-in-place cancel two-step, and it would put the confirm sentence beside the row rather than over it. But `LOOP-STATE.md`'s `known_flaky` entry is exactly that pattern's focus test — *"the cancel two-step :: moves focus into the revealed block, onto the question itself"*, a jsdom focus/timing race that has already parked a green PR — and adopting the shape means inheriting the flake on a merge gate. The nested `Modal` needs no hand-rolled focus management at all. **Recorded rather than silently chosen**, because a reviewer will notice the console has two confirm idioms.

```
+-- Modal (nested) -----------------------+
| למחוק את «הבמה» מרשימת החדרים?          |
| אי אפשר למחוק חדר שיש בו לקוחה עכשיו.   |
|                                         |
|              [ ביטול ]   [ מחיקה ]      |
+-----------------------------------------+
```

- **The sentence names the room in guillemets**, so it agrees with nothing and reads correctly whatever the boutique typed (§8 / `copy.md` §0 rule 6).
- **The body states the one rule she can hit**, so the 409 below is expected rather than a surprise.
- **A 409 `ROOM_OCCUPIED` renders inside this confirm**, in the notice register, naming the occupant and the remedy: «דנה כהן נמצאת בחדר עכשיו. אפשר למחוק אותו אחרי שהיא תצא.» The confirm button **stays**, because a retry two minutes later is legitimate and closing the dialog would make her walk the whole path again. **This is the one place a registry action meets the concurrency design**, and it needs its own sentence — `rooms.error.ROOM_OCCUPIED` is written for a claim («כבר בחדר הזה» = "already in this room") and reads as a non-sequitur as a reason a delete failed.
- **Focus return** is the native `<dialog>`'s and lands on the row's «מחיקה» trigger — **unless the delete succeeded and the row is gone**, in which case F51's `isConnected` fallback targets the registry dialog's own title.

### 5.4 The registry's own announced region

Registry writes are confirmed by a `<p role="status">` **inside the `Modal`**, not by the panel's cue region. A live region outside an open modal dialog is not reliably read by AT while the dialog holds the accessibility tree, and the whole point of the cue is that it is heard. Three strings — `rooms.savedCue`, `rooms.addedCue`, `rooms.deletedCue` — and `rooms.savedCue` is deliberately the console's shipped save phrasing («נשמר לפני רגע», `manage-restyle.md` §States) rather than a fourth way to say the same thing.

**This is not a second region on the panel.** It exists only while the dialog is open, inside the top layer, and it disappears with it. §1.1's "one announced region" rule is about `FloorPanel`, and it is intact.

---

## 6. The staff card's third status — and the boolean F36 breaks if nobody looks

F57 shipped the card. F36 changes **three lines** in it, and the spec names one of them.

### 6.1 The Badge becomes a three-way

The shipped card is `const onBreak = card.status === "break"` (`FloorPanel.tsx:523`) feeding `<Badge variant={onBreak ? "warning" : "success"}>{t(onBreak ? "floor.statusBreak" : "floor.statusAvailable")}</Badge>` (`:556-557`). With `status: "occupied"` that ternary falls to the **else** branch and renders **«פנויה»** — the card saying a staffer standing in a fitting room is available, one word away from the lie this whole feature exists to prevent.

| `status` | Badge | Variant | Contrast on paper |
|---|---|---|---|
| `available` | «פנויה» | `success` | 5.56:1 ✓ |
| `break` | «בהפסקה» | `warning` | 5.20:1 ✓ |
| **`occupied`** | **«תפוסה»** — `floor.statusOccupied`, feminine, matching its two neighbours | **`neutral`** | 13.89:1 ✓ |

`neutral` for the same reason the tile uses it (§2.3), and **no new colour**.

### 6.2 The occupancy line — and why the spec's proposed string cannot ship

An occupancy line renders whenever `occupancy !== null`:

```
דנה כהן                        [ תפוסה ]
תופרת
חדר 2 · מיכל · כבר 42 דק'
```

⚠ **Spec D17 proposes `rooms.occupancyLine` = «בחדר {{room}} עם {{client}} · כבר {{minutes}} דק'». It does not ship, and the reason is the spec's own example.** The boutique types «חדר 1 / חדר 2 / הבמה» — the room label **already contains its own noun** — so «בחדר {{room}}» renders **«בחדר חדר 2»**. The same string also needs two bidi isolations plus a numeric one, and the shipped helpers take `(text, value)` and return a `ReactNode`, so they cannot be chained.

**Shipped instead: three fragments, each its own element, separated by the console's existing «·».** `<bdi>{room}</bdi> · <bdi>{client}</bdi> · isolateLtr(elapsed, minutes)`. No preposition to disagree with a user-typed noun, no nested interpolation, no new helper, and one less key than the spec's table carries. The separator is house vocabulary already — `floor.pausedAt` ships «מושהה · עודכן {{time}}». When `client_label` is `null`, the middle fragment is `rooms.anonymous`. When the elapsed count is under a minute it is `rooms.elapsedJustNow`. **Recorded as a copy correction to D17**, the F57 F-2 / F-3 / F-10 precedent, and it is one of four strings in that table with the same defect — `copy.md` §0 rule 6 states the general rule and §8 lists all four.

### 6.3 ⚠ `onBreak` must stop being derived from `status` — a defect F36 CREATES

**This is the sharpest thing in the deck and the spec does not name it.**

`FloorPanel` derives one boolean from `card.status` in **three** places, and `status === "break"` was equivalent to "she is on a break" only because `card_status()` was a total function of `break_started_at`. F36 makes `occupied` **win** over `break` (spec D12) while `break_started_at` **stays on the wire regardless**. So for a staffer who forgot to end a break and then claimed a room:

| Site | Shipped code | What it does after F36 | Consequence |
|---|---|---|---|
| `:523` / `:556` | Badge ternary | falls to «פנויה» | **the spec names this one**; §6.1 fixes it with a three-way |
| **`:281`** | `toggle()`'s `onBreak` | `false` → the control reads **«להפסקה»** and calls `startStaffBreak` | **she can never END that break from this screen** while she holds a room. The tap is a 200 no-op keeping the first timestamp, the cue confirms a break was recorded, and the button never offers «חזרה» until she releases the room |
| **`:566`** | the since-line guard | `false` → «מאז 11:20» disappears | the one signal F57's **F-6** relies on to make a forgotten break legible vanishes exactly when it has lasted longest |

**Ruling: the break fact is `break_started_at !== null`, and both the control and the since-line follow it. `status` is a display precedence for the Badge alone.**

```
const onBreak = card.break_started_at !== null;      // was: card.status === "break"
const badge   = card.status;                         // three-way, §6.1
```

An occupied staffer who is also on a break then renders five lines — Badge «תפוסה», role, occupancy line, «מאז 11:20», control «חזרה» — which is the rarest card in the product and the only place a screen can tell a shift manager that a break was never closed. It needs **no new string**: `floor.breakSince` is shipped. **It is also strictly better than D12's floated parenthetical** («(שכחה לסיים הפסקה מ־11:20)»), which is a fourth string saying the same thing with brackets round it.

**Two properties make this edit safe under D15's zero-edit acceptance rule.** First, `card_status()` returns `break` **iff** `break_started_at is not None` before F36, so the old and new derivations are **equivalent on every payload F57 can produce** and on every fixture `FloorPanel.test.tsx` ships — the shipped expectations pass unedited, which is exactly what that rule is for. Second, the new behaviour is only reachable with a fixture that has both `status: "occupied"` and a non-null `break_started_at`, which no shipped block constructs and which is therefore a **new** `it(` block, freely added.

**Named test and its mutation** (AC22's neighbour): *an occupied staffer who is also on a break shows «תפוסה», her room, «מאז 11:20» and a control reading «חזרה»* — **mutation: revert `onBreak` to `card.status === "break"`**. Nothing else in the suite goes red, which is precisely why it needs naming.

---

## 7. States — the single source for this feature

Everything the spec's Frontend-changes list enumerates, plus what is announced and where focus goes. **The list may not shrink.** States inherited from `FloorPanel`'s poll (F-load, F-fail, F-stale, F-paused, F-idle, F-401, F-403) are **F57's, unchanged**, and are not restated — they now govern the rooms too, which is §10.4's point.

| # | State | Trigger | What she sees | Region / focus |
|---|---|---|---|---|
| **R-load** | First load | section opened | `FloorPanel`'s existing `Skeleton` in a `Card`; no rooms heading yet | the shipped `floor.loading` cue |
| **R-empty** | No rooms configured — **what a brand-new boutique sees first** | 200, `rooms: []` | `EmptyState title={rooms.empty}` inside the rooms `Card`. **CTA «הוספת חדר» for owner/shift_manager only; for the other three, the title and nothing else** — no body, no CTA, no explanation. A seamstress cannot fix it and telling her to would be a dead end, and the staff list below is still the useful half of her screen | nothing announced |
| **R** | Loaded, some free | 200 | §1 | nothing announced |
| **R-full** | Every room occupied | 200 | every tile shows its holder, client and elapsed. **No panel-level "full" banner** — the tiles already say it and a banner is a second thing to keep true. No queue, no wait, no suggestion (out of scope) | nothing |
| **R-inactive** | A room out of service | `is_active === false` | muted label, «מחוץ לשירות» as a **word**, no claim control, **no opacity wash** (§2.3) | nothing |
| **R-inactive-occupied** | Deactivated with a bride inside | both | Badge «תפוס» + a muted `rooms.inactive` line. §12's parked question | nothing |
| **R-ghost** | Holder no longer on staff | `staff_display_name === null` | `rooms.holderGone` in place of the name, no role line, client and dresses intact, **release control for elevated callers only** | nothing |
| **R-clients** | The client picker | mount / after each claim | loading (the `Select` disabled, label present) · loaded · **empty → the `Select` is ABSENT and the claim proceeds anonymously** · truncated → one line, no number · load failed → absent, anonymous-only, **never a blocked claim** | nothing |
| **R-busy** | A room action in flight | tap | **that control only**: `loading` on the shipped `Button` (spinner overlaid, label kept for width, `aria-busy`). Every other tile stays live. The poll returns `"suppressed"`, so the tile cannot repaint under the request | nothing yet |
| **R-ok** | Claim / release / handover / dress succeeded | 200 | the tile patches **from the response** (§2.4). The freshness time updates. The cue carries the room-scoped sentence | `role="status"`; **focus returns to the tile's control** (§10.1 move 2) |
| **R-taken** | **A room claimed underneath you** | 409 `ROOM_OCCUPIED` | §3.3 — the tile alert **names the occupant**, notice register, tile stays interactive, the next tick confirms | `role="alert"`, **focused** |
| **R-taken-?** | Same, occupant released first | 409 with **no `details`** | «החדר נתפס זה עתה. נסי שוב.» | as R-taken |
| **R-hers** | Your target already holds a room | 409 `STAFF_OCCUPIED` | «היא כבר בחדר אחר: חדר 5.», or the prefix form with no `details` | as R-taken |
| **R-gone** | **A room released or deleted underneath you** | 404 | `rooms.error.notFound` (the room) or `rooms.error.assignmentGone` (the assignment), notice register. The next tick keeps the promise, clears the alert and hands focus back | `role="alert"`, focused; then §10.1's reclaim |
| **R-mine** | You re-claimed the room you hold | 200, nothing written | **identical to R-ok**, deliberately: the outcome she wanted is the outcome that holds | as R-ok |
| **R-403** | Any room action answers 403 | 403 | **terminal for the whole panel** — F57's **P-6**, unchanged. §2.2 is what keeps it unreachable by design | `role="alert"`, once |

**The registry dialog:** empty · populated · row in flight · label invalid (field-local, `danger`, from `Input`) · `sort_order` out of range (same) · delete confirm open · **delete blocked by an occupancy** (409, in the confirm, naming the occupant and the remedy, confirm retained) · delete confirmed · **a room changed underneath the open dialog** (the seeded row is kept) · **the row being confirmed has vanished** (404 → close the confirm, re-seed) · closed-and-focus-returned · **closed with its trigger gone** (§1.2).

**The dress dialog:** loading · loaded · truncated · filter matches nothing · empty catalog · dress chosen / size chosen · add in flight · **404 — the assignment was released** (dialog closes, the tile's alert takes over, **focus goes INTO that alert**) · **a poll tick removed the assignment with the dialog open** (dialog closes, focus to the tile's control or the rooms heading, never `<body>`).

**The handover dialog:** open with a colleague list · **nobody free** (`rooms.handoverNobody`) · chosen · confirm in flight · **residual 409 naming her room, dialog stays open** · **404, dialog closes and the tile's alert takes over** · cancelled-and-focus-returned.

**State precedence.** A mutation's response is always the truth for its tile (it *is* a `Room`). A poll's response is the truth for everything else. They cannot fight: the loop does not tick during a mutation and the mutation bumps the generation on settle.

---

## 8. Breakpoints — 375 / 768 / 1440

Mobile-first, and there is exactly **one** breakpoint branch in the panel — the same one F34 and F57 have, in the same place.

| Width | What is different | Why |
|---|---|---|
| **375** (primary) | The tile is a flex **column**: the text block on top, **the action row on its own line, `justify-end`** | Arithmetic: 375 − 2×`--space-4` = 343 of shell, − 2×`--space-6` of `Card` padding = **295px** of tile. A «מחוץ לשירות» pill, a «חדר המדידה הגדול» label and three 44-high controls do not share a line at 295px, and the `Card`'s padding cannot be reduced from the call site (F15 F-6). Dropping the controls to their own line returns the label the full 295 and makes the targets *larger* |
| **375, three controls** | The action row is `flex flex-wrap justify-end gap-3`; controls wrap to a second line rather than shrinking | `fullWidthMobile={false}` on every one — three full-width buttons per tile would be a wall, and F57 ships the same prop for the same reason |
| **375, long label** | The label wraps and pushes the `Badge` to the next line. `break-words` on the label, `flex-wrap` on the label row, **no truncation and no ellipsis anywhere** | The tile has vertical room it does not have horizontal room |
| **768** | The action row moves to the tile's inline-end on the **same** line as the text block (`sm:flex-row sm:items-start`). Still **one column** — no grid | 720 − 48 = 672 of tile. §11 **P-1** |
| **1440** | **Identical to 768.** The console never exceeds a 720px content column (`ConsoleShell.tsx:84`) | A wall-mounted display board is not this feature (F59's) |
| **Every width** | The `Modal` is `w-[min(28rem,calc(100vw-2rem))]` — 343px at 375, 448px above. The registry row **stacks** below 448: label input full width, then `[order] [toggle]`, then `[save] [delete]` | Five controls do not fit one 343px line, and the `Modal`'s width is `packages/ui`'s and is not overridden |

**`items-start`, not `items-center`, at 768.** An occupied tile's text block is six to ten lines and its action row is one; centring the controls against that block floats them into the middle of the dress list. F57 uses `items-center` because its card is three lines — the divergence is a height difference, not a taste difference.

---

## 9. Component notes — exact tokens

| Element | Notes |
|---|---|
| Rooms heading | `<h3 ref={roomsHeading} tabIndex={-1} className="text-base font-semibold text-ink">` — **`h3`, not `h2`; see F-1.** `tabIndex={-1}` is §10.1's rescue target and adds **no** tab stop |
| Heading row | `<div className="flex flex-wrap items-center justify-between gap-3">` — heading at inline-start, registry trigger at inline-end |
| Registry trigger | `Button variant="ghost" size="md" fullWidthMobile={false}` |
| List | `<Card>` → `<ul className="divide-y divide-border">` — `FloorPanel.tsx:521`'s exact shape |
| Tile | `<li data-room-id={id} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start">`; text block `min-w-0 grow space-y-1` |
| Room label | `<bdi className="font-semibold break-words text-ink">`, or `text-ink-muted` when `!is_active` — bare `<bdi>`, **never `dir="ltr"`** |
| Status Badge | `Badge variant={free ? "success" : occupied ? "neutral" : "muted"}` — **one per tile**, §2.3 |
| Out-of-service line | `<p className="text-sm text-ink-muted">` — only when inactive **and** occupied |
| Holder name | `<bdi className="font-semibold break-words text-ink">` |
| Holder role | `<p className="text-sm text-ink-muted"><bdi>{t(roleLabelKey(role))}</bdi></p>` — `lib/roles.ts` **unchanged** |
| Client row | `<p className="text-sm text-ink"><span className="text-ink-muted">{t("rooms.clientLabel")}</span>{" "}<bdi>{client}</bdi></p>`; anonymous → `<p className="text-sm text-ink-muted">{t("rooms.anonymous")}</p>` |
| Elapsed | `<p className="text-sm text-ink">{isolateLtr(t("rooms.elapsed", { minutes }), String(minutes))}</p>`, or `rooms.elapsedJustNow` plain under one minute. **No new formatter** (spec D17) |
| Dress group label | `<p className="text-sm text-ink-muted">` — a paragraph, not a heading |
| Dress row | `<li className="flex items-center justify-between gap-3 text-sm text-ink"><span><bdi>{name}</bdi>{size && <> · <bdi dir="ltr">{size}</bdi></>}</span>…</li>` |
| Remove dress | `Button variant="ghost" size="md" fullWidthMobile={false}` + `aria-label={t("rooms.removeDressAria", { dress })}` |
| Claim control | `Button variant="secondary" size="md" fullWidthMobile={false}` + `aria-label={t("rooms.claimAria", { room })}` |
| Client picker | `Select label={t("rooms.clientPick", { room })} className="min-h-11"` — **see F-4 for why the class is there and why it is not an F15 F-6 violation** |
| Release | `Button variant="secondary" size="md"` + `rooms.releaseAria` |
| Handover trigger | `Button variant="ghost" size="md"` + `rooms.handoverAria` |
| Add dress trigger | `Button variant="ghost" size="md"` + `rooms.addDressAria` |
| Tile alert | `<p role="alert" tabIndex={-1} className="text-sm font-semibold text-warning-text">` for every mapped code; `text-ink-muted` (no `font-semibold`) for the unmapped outage fallback. **Never `text-danger`** (§3.2) |
| Empty state | `<EmptyState title={t("rooms.empty")} action={elevated ? <Button variant="secondary" size="md">…</Button> : undefined} />` — **no `body` in either case** |
| Dialogs | the shipped `Modal`; footers `ghost` dismiss + `secondary` confirm, except the delete confirm which is `ghost` + `danger` |
| Registry inputs | `Input` (label), `Input type="number"` (order), `Toggle` (active) — every one shipped, every one label-required, none overridden |
| Registry cue | `<p role="status" className="text-sm text-ink-muted">` **inside** the `Modal` (§5.4) |

**Contrast, from the tokens ledger — not eyeballed.** ink 13.89 · ink-muted 5.61 · warning-text 5.20 · success 5.56 · danger 6.18 · focus ring 5.57 · border (non-text boundary) ✓. **This feature introduces no new colour pair and no gold at all** — the board's «עכשיו» hairline is still the console's only `gold-strong`, and this panel has no divider to put one on. The ledger needs no addition at this gate.

---

## 10. The a11y contract — IS 5568 / WCAG 2.0 AA is a legal requirement (pre-decided #38)

axe must return **zero** violations, and **axe is not the coverage**. Three whole classes below are invisible to it.

### 10.1 Focus — five moves, each with a named, non-vacuous test

⚠ **axe cannot see a focus move that never happened.** This repo has shipped that exact bug class **three times** — F56 on the storefront, F34 on the board, F57 on this very panel (*a successful poll unmounted the focused in-card alert and dropped focus to `<body>` five seconds later with no user action*) — and axe walked past all three. `@boutique/ui`'s `Button` is `disabled={disabled || loading}` (`Button.tsx:57`), so **the browser blurs the tapped control the instant a request starts, and every room action is that shape.**

| # | Move | Destination | Mutation that must turn it red |
|---|---|---|---|
| 1 | **A failed room action** (409, 404, outage) | the tile's alert — keyed on the error state, **not raised in the handler**, because the alert node does not exist when `setError` runs | delete the `[tileError]` effect |
| 2 | **A successful room action** | the tile's **current** primary control, via a `Map` keyed by room id — **guarded on `document.activeElement === document.body`** so it can never steal focus from wherever she moved it | delete the restore effect |
| 3 | **A room that leaves the list while holding focus** | the rooms `h3`. The only way a tile leaves is a registry delete | delete the departing-tile check |
| 4 | **Closing the dress or handover dialog** | the tile's trigger, falling back to the rooms `h3` when it is gone. ⚠ **The 404 collision is resolved explicitly: when the write fails because the assignment was released, the dialog closes and focus goes into the TILE'S ALERT — move 1 wins over the native `<dialog>` return**, which fires second and would otherwise win | make the native return win |
| 5 | **A poll tick that removes the open dialog's assignment** | close the dialog, focus the tile's control or the `h3` — **never `<body>`** | remove the open-dialog reconciliation |

**Move 2 does not assume the control survives, and the spec's premise that "it renames, it does not unmount" is not safe here.** On a staff card the break toggle is one element whose label swaps. On a **room tile** the free and occupied action rows have different shapes — a `Select` appears and disappears beside the button — so React may or may not reuse the DOM node. **The design does not depend on which**: the ref `Map` is keyed by **room id** and always resolves to whatever the tile's primary control currently is, which is `FloorPanel`'s shipped `controlRefs` pattern (`:589-591`) applied one level down. On a lost claim (R-taken) the claim control is genuinely gone and the `h3` fallback fires — **that is the common case on this path, not the rare one**.

⚠ **Every one of these must be MUTATION-CHECKED by running it, and jsdom is the trap.** F57's shipped note records that its own success-path focus test was **VACUOUS**: jsdom does not blur a disabled element, so `document.activeElement` never became `<body>`, the guard never passed, and the entire restore effect could be deleted with the suite green. **A test for move 2 must explicitly blur the tapped control before the promise resolves** — reproducing what a real browser does when `disabled` is set — or it asserts nothing at all. A test that passes with its mechanism removed is not a test, and both prior features in this program found a real vacuous one this way.

**Tab order** inside the panel: skip link → header logout → nav → `#console-main` → *(board section: the board's own stops)* → **the pause / resume control** → the registry trigger → per tile: the client `Select`, then the claim control · or the remove-dress buttons, «הוספת שמלה», «העברה», «שחרור» → the staff cards' controls. The pause control staying the **first stop inside the panel** is F57's ruling and is now more load-bearing, not less: it governs two repainting regions.

**Every action is keyboard-reachable and none needs a pointer.** The only new interaction primitives are native `<select>`, native `<input type="number">`, native `<input type="checkbox" role="switch">` and `<button>`. **There is no drag, no long-press, no swipe, no hover-only affordance, and no custom widget anywhere in this feature** — spec D16 refuses the ARIA combobox and D18 refuses drag reordering, and this is the sentence that says both refusals were the same decision.

**Tiles are keyed by `room.id`**, so a repaint mutates text nodes inside a stable element and focus inside a tile survives every tick.

**A tick may not repaint while a pointer is down.** F57's `holdRef` exists because a break starting on card 2 grows it ~20px and slides every control below it. **A room being claimed grows its tile by a holder line, a role line, a client line, an elapsed line, a dress list and two more controls — far more than 20px — directly above the tile a finger is travelling toward.** The mechanism is unchanged and its comment gains the rooms case (spec D15).

### 10.2 Live regions — announce on MEANINGFUL CHANGE ONLY, never per tick

**The poll never writes into `role="status"`** (F34's D11, verbatim and non-negotiable). A status update every five seconds announces the whole floor forever and makes a screen reader unusable for a whole shift. `role="status"` carries **user-initiated outcomes only**: the claim cue, the release cue, the handover cue, the two dress cues, plus F57's shipped pause / idle / resume / break cues. **A room claimed, released or handed over by a colleague repaints its tile silently.**

⚠ **"Write" means write, not change.** Assigning a byte-identical string to a text node still runs the DOM's string-replace-all and produces a real `childList` mutation inside `role="status"` (F34's **F-7**; `FloorPanel.tsx:194-201` carries the warning). The cue is written **only when its value actually changes**, and the test must drive **several consecutive ticks with the cue already populated** — a single-tick assertion passes against the broken version whenever the cue starts empty.

**The cues name the ROOM. They do NOT name the client — and that is a privacy decision, not an oversight.**

| Cue | Names | Why |
|---|---|---|
| `rooms.claimedCue` «החדר נתפס: חדר 2.» | the room | Five tiles, one region: a cue that cannot say *which* room is useless exactly when the panel is busy |
| `rooms.releasedCue` «החדר שוחרר: חדר 2.» | the room | same |
| `rooms.handedOverCue` «החדר הועבר אל נועה לוי.» | the **receiving colleague** | A colleague's name announced to a colleague, on a payload every staffer already reads — F57's rule, unchanged. What she needs confirmed is who has it now; the room is not in doubt, she opened the dialog from its tile |
| `rooms.dressAddedCue` / `rooms.dressRemovedCue` | the **dress** | same reasoning, same scope |

**The client's name is never in a cue.** F57's copy deck records that its cues may name a colleague *"not a customer's name, which is why F15's rule about the bride's name in a persistent landmark does not reach it"* — and F36's claim cue is the first one that could carry a customer's. It must not, for one concrete reason: **the cue is persistent.** F57's shipped region is not cleared on a timer — a cue stays visible until the next tap replaces it — so «חדר 2 נתפס עבור מיכל» would leave a bride's name sitting on screen for an arbitrary length of time, on a surface five roles can open, in a room she is standing in. That is precisely the disclosure D9's whole argument exists to minimise, and the tile one line away already carries the name for as long as the fitting lasts and not one second longer.

`role="alert"` appears exactly **twice** on this panel and both are bounded: the tile alert (once per refused action, bounded by her own tapping) and F57's shipped terminal 401/403 (once per dead session, and the loop has stopped). **Neither can be produced by the poll on its own.**

### 10.3 Status is never colour alone, and the tile carries exactly one `Badge`

«פנוי» / «תפוס» / «מחוץ לשירות» are words, and so is the staff card's «תפוסה». A `Badge`'s colour may accompany the word and may never replace it — F51's shipped rule (*"The WORD carries the role; the colour never does"*) and, closer to hand because it is about a **state** word, `FloorPanel.tsx:554`. Greyed is a token swap, never `opacity-*` (§2.3). The holder's role is muted words and **never a second `Badge`** (§11 **P-2**).

### 10.4 SC 2.2.2 — inherited, and its tests may not be cut

`FloorPanel`'s pause / resume control and idle stop now govern **two** repainting regions instead of one. **axe has no rule for SC 2.2.2**, so the shipped frontend assertions — pause stops the loop, resume fetches immediately at the base interval, the idle stop fires, one interaction resumes — are the **sole** coverage of a Level A requirement inside a legally binding AA bar. F36 adds no control and no constant (§11 **P-4**), and **the shipped tests must not be cut as redundant with the axe assertion.** The floor-program review says so about F34 in as many words; this is the third surface on one screen.

### 10.5 The rest of the floor

- **≥44×44 on every target.** Every `Button` is `size="md"` → `min-h-11`. The `Select`s carry `min-h-11` explicitly — **see F-4**, which does the arithmetic and names the real fix.
- **Visible focus ring** on every interactive element — `focusRing`, applied unconditionally by `Button.tsx:62`, `Input.tsx:45`, `Select.tsx:31` and `Toggle.tsx:30`. Nothing here sets `outline: none`. **axe sees a missing label; it does not see a missing focus ring**, which is why spec D16 names `Select` rather than "a native `<select>`".
- **Accessible names carry the visible label plus the room** — «תפיסת החדר — חדר 2», «שחרור — חדר 2», «העברה לעמיתה — חדר 2», «הוספת שמלה — חדר 2», «הסרה — ורוניק». Five tiles all offering a button named «שחרור» is a screen-reader dead end, and each name **starts with the visible string** so WCAG 2.5.3 label-in-name holds. An `aria-label` takes no markup, so an interpolated name in one needs no bidi treatment (F57 F-11).
- **Bidi**: `<bdi dir="ltr">` on every numeric run (elapsed minutes, sizes, the order field's value); **bare `<bdi>`** on every Hebrew free-text run (room labels, display names, client names, dress names). Forcing LTR on a Hebrew name reverses its words and it is the defect that *looks deliberate*.
- **No truncation and no ellipsis on a client label, a room label, a dress name or a display name, ever** (spec D18): a panel that abbreviates makes two people look like one.
- **Headings**: the shell owns the single `h1`; `FloorPanel`'s `h2` is unchanged; the rooms panel's is an **`h3`** (**F-1**); the two `Modal`s bring their own `h2` inside the top layer, which is the shipped component's behaviour and is not a level skip in the page outline.
- **Motion**: nothing new animates except the shipped `Modal` panel/backdrop animation and the `Button` spinner, both already frozen globally by `theme.css:155-163` under `prefers-reduced-motion`. **No highlight, no fade, no colour wash on a changed tile** (§2.4). **This feature adds no motion rule because it adds no motion.**
- **Content capped at 720px** at every width. `A11yMenu` / `A11yStatementLink` are storefront-only, so no fixed-chrome clearance applies.
- **An `axe` pass** runs over the panel and over each dialog — **and it is explicitly not sufficient**, per §10.1, §10.3 and §10.4.

---

## 11. RESOLVED decisions — self-approved with the design gate, 2026-08-03

**All eight carry a resolution and none is an open question.** Each keeps its reasoning, because the reasoning is what a later feature would have to overturn to reopen it. **The Hebrew remains the user's to edit post-merge** — the F15 P-1/P-5, F34 and F57 precedent: a one-line `he.ts` / `ar.ts` edit after merge, never a rebuild.

| | Resolution |
|---|---|
| **P-1** | **One `Card`, one `<ul>`, one column at every width** — not a grid of tiles |
| **P-2** | **The holder's role is muted words; the tile's single `Badge` is the occupancy** |
| **P-3** | **The client picker sits on the free tile, not behind a dialog** |
| **P-4** | **No new numbers and no new poll**: 5s / 60s cap / 10min idle, all inherited |
| **P-5** | **Occupancy ships as words in a `Badge`**, no glyphs, no dots, no colour-only |
| **P-6** | **A room action's 403 is terminal**, like a tick's — and §2.2 makes it unreachable |
| **P-7** | **The delete confirm is a nested `Modal`**, not the storefront's inline two-step |
| **P-8** | **The registry admits shift_manager**, not owner alone |

- **P-1 — RESOLVED: one `Card` containing a divided list, one column at 375, 768 and 1440.** F57's P-1 recorded the upgrade path — *"F36 adds a room label per card and F58 adds a dispatch control, and a card that has grown three lines is the moment a grid earns itself"* — and **this feature does not spend it**: the staff card grows by exactly **one** line (§6.2's occupancy line is one sentence, not three), so the condition has not been met. For the **rooms**, a grid is worse than for the staff list, not better: tiles are wildly heterogeneous in height (a free tile is two lines, an occupied one with four gowns is twelve), and a two-column grid of unequal tiles produces a ragged edge and turns "which room is free" into a scan across two columns instead of down one. A `Card` inside a `Card` is also a shadow on a shadow that `packages/ui` has no treatment for. **The upgrade path is handed to F58**, which adds a dispatch control to the staff card and is the PR where "three lines" becomes true.
- **P-2 — RESOLVED: the holder's role is `--text-sm --color-ink-muted` words under her name; the tile's one `Badge` is the occupancy.** E7 criterion 2 names the role explicitly and spec D11 puts `staff_role` on the wire for it, so it must render — but two pills in 295px teaches the reader to scan colours instead of words, which is how a status vocabulary dies. F15's rule (*exactly one Badge per row region, and the status owns it*) and F57's **P-2** are the same ruling arrived at from two directions.
- **P-3 — RESOLVED: the claim's client picker is inline on the free tile.** Spec D16 rules out a dialog and the reasons survive: no focus trap to write, no return contract to test, no fourth dialog component, one tap when she does not care which bride. The cost — up to six `Select`s on a panel — is smaller than it looks, because **the picker is absent whenever the client list is empty or failed** (§3.1), which is the ordinary state before the first arrival of the day. **Declined a single shared picker at the top of the panel** ("who are you seating?" + a claim button per tile): it is a mode, and a forgotten mode binds the next claim to the wrong bride with no error anywhere.
- **P-4 — RESOLVED: this feature introduces no constant, no timer and no second loop.** `POLL_INTERVAL_MS` = 5s, `MAX_BACKOFF_MS` = 60s and `IDLE_STOP_MS` = 10 minutes are exported by `usePoll` and were ruled at F34's gate. `lib/usePoll.ts` gets a **zero-line diff** (spec D15), stated because four features are queued to import it and a change here would be four features' problem. The elapsed-minute counter is computed at render and sets **no interval of its own** (§2.5).
- **P-5 — RESOLVED: words in a `Badge`, no emoji, no dots, no icons.** §2.3 is the argument and it is F57's **P-5** unchanged. The requirement the dots encode — legible across a counter — is met by a bordered pill carrying a Hebrew word.
- **P-6 — RESOLVED: a room action that answers 403 puts the whole panel into F57's terminal state, exactly as a tick would.** `usePoll.terminalOf` classifies a mutation's error on the same `{401,403}` rule the ticks use, so the alternative is an in-tile alert plus a loop that keeps polling with a role the server just refused — the panel disagreeing with itself for five seconds and then doing the same thing anyway. **§2.2 is what makes this unreachable rather than merely correct**, and `RoomsPanel.test.tsx` asserts all four elevated-only controls are **absent** for `role="seamstress"` and present for `owner` (spec AC21). A **404 is NOT terminal** and stays a tile alert.
- **P-7 — RESOLVED: the registry's delete confirm is a nested `Modal`.** §5.3 is the full argument. The short version: it is `manage-restyle.md`'s shipped destructive pattern; `Modal`'s own comment anticipates two mounted at once; native `<dialog>` gives the trap, the Esc handling and the focus return for free; and the alternative pattern's focus test is **already on `LOOP-STATE.md`'s `known_flaky` list**, where it has parked a green PR once. Adopting a known-flaky shape on a merge gate to save a component instance is not laziness, it is a bill arriving later.
- **P-8 — RESOLVED: owner AND shift_manager reach the registry.** The E7 brief says "Owner manages the list in `apps/manage`" and spec D10 widens it, flagged as Conflict 5. Endorsed here on the design's own footing: *"room 2's mirror is broken, take it out of service"* is an act that has to be possible at 10am without telephoning the owner, and the registry is the only screen that can express it. A shift manager already edits settings, hours, appointment types, the catalog and every booking — a room name is strictly less sensitive than what she can already change. **Declined all five**: a seamstress renaming the boutique's rooms is not a capability anything asks for, and the registry is configuration, not floor work.

---

## 12. ⚠ FINDINGS

- **F-1 — spec D18 says the rooms heading is an `h2`; this deck ships an `h3`, and what changed is D18's premise, not its rule.** `FloorPanel` already owns the section's `h2` («צוות בקומה», `FloorPanel.tsx:344`), and F57's deck §7.4 justified having no `h3`s with *"the panel has no groups"* — a sentence that is exactly what F36 falsifies. Three options were weighed. A **second `h2`** makes the rooms a *peer* of the floor panel, which then obliges the staff list to be named too — three headings and a new string for an outline nobody is confused by in a 2–6 room list, and it would edit shipped structure that D15's zero-edit rule protects. **No heading at all** leaves five tiles and four controls with nothing to navigate to, and the `h3` is also §10.1 move 3's focus-rescue target, so it has to exist. **`h3` it is**, and the honest cost is recorded: a heading-walking user hears «צוות בקומה» → «חדרי מדידה» and then falls out of the rooms subsection into unnamed staff cards, so the panel's heading names only half its own content. **The cheap remedy is renaming `floor.heading` to a floor-level word — and F58 is the PR where it earns the edit**, because that is when the waitlist becomes panel three and the mismatch stops being cosmetic. *Owner: team. Trigger: F58.*
- **F-2 — F36 CREATES a defect the spec names only one third of, and the other two thirds are silent.** §6.3 is the full argument. `FloorPanel` derives `onBreak` from `card.status` at **three** sites; D12 names the Badge and fixes it; `:281` (the toggle) and `:566` (the since-line) are not named anywhere in the spec. The consequence at `:281` is that **a staffer who forgot to end a break and then claimed a room can never end it from this screen** — the control reads «להפסקה» until she releases the room. The fix is one line (`card.break_started_at !== null`), needs no new string, is behaviour-identical on every payload F57 can produce (so D15's zero-edit rule survives), and requires a **new** test block with a named mutation because **nothing else in the suite goes red without it.** *Owner: team. **Trigger: this PR's build**, not a later one — the defect ships the day `occupied` does.*
- **F-3 — four of spec D17's proposed strings concatenate Hebrew onto a user-typed room label, and every one of them breaks on the spec's own example.** The boutique types «חדר 1 / חדר 2 / הבמה» — the label carries its own noun and its own gender — so «בחדר {{room}}» renders **«בחדר חדר 2»**, «היא כבר בחדר {{room}}» renders **«בחדר חדר 2»**, and any cue of the form «{{room}} נתפס» renders **«הבמה נתפס»**, a gender disagreement with a value no translator can see. **Fixed in copy, as a general rule rather than four patches** (`copy.md` §0 rule 6): *no string may place a Hebrew preposition, article or agreeing verb immediately against `{{room}}`.* The shapes that survive it are an em-dash («שחרור — {{room}}»), a colon appositive («החדר נתפס: {{room}}»), guillemets («למחוק את «{{room}}»?») and a fragment rendered as its own element (§6.2). **This is a copy correction to the spec, recorded rather than folded in silently**, the F57 F-2 / F-3 / F-10 precedent. *Owner: team. Trigger: the copy transcription; and F37, F41, F42 and F59 all interpolate user-typed nouns and inherit the rule.*
- **F-4 — the shipped `Select` renders ~43.6px tall, under the house 44 floor, and this feature is the first to put four of them under a thumb.** `Select.tsx:28` is `px-3 py-2 text-base` with a 1px border: `--text-base` is 1rem/1.6 = 25.6px of line, + 16px of padding, + 2px of border ≈ **43.6px**. WCAG 2.0 AA has no target-size criterion — 2.5.5 is 2.1 AAA and 2.5.8 is 2.2 AA — so this is `tokens.md` **usage law 7**, a house rule, not the legal floor. This deck passes `className="min-h-11"` at each call site, which is **not** an F15 F-6 violation: `Select` declares no `min-h-*` at all, so `cn()`'s plain join has no fight to lose. **The real fix is one line inside `Select` itself**, and F36 declines it because that component is consumed by eight screens and D15's entire discipline this run is not to reach into shared code for a convenience. *Owner: team. Trigger: the next feature that puts a `Select` under a thumb — it will pass the same class and that is the second occurrence that earns the component change.*
- **F-5 — `i18n.test.ts`'s two register guards and its `ar` parity guard will silently skip this feature's whole namespace unless `HE_F36` is FOLDED INTO `HE`, not merely declared.** The file says so about itself: `src/__tests__/i18n.test.ts:33-34` — *"Folded in, not just declared: without this the resolve check, BOTH register guards and the `ar` parity guard silently skip every F52 key."* The spec's Testing section names an `F36 rooms keys resolve` block and the `ar[key] === he[key]` assertion, and neither implies the fold. Without it, ~68 hand-transcribed Hebrew strings ship unchecked for an exclamation mark, for the `/נשלח|תישלח|בדרך/` send-ban, and for a missing `ar` key. **One line, and it is the one a builder working from the spec's enumerated edit list will not write.** *Owner: team. Trigger: this PR's build.*
- **F-6 — this deck's key count is ~68, not the spec's "~40", and Risk 12 is understated by three quarters.** Four dialogs, five error codes with two `details`-less variants, a delete refusal that needs its own sentence, three registry cues and two truncation lines are what the surface actually costs. There is still **no he/ar parity guard** in this repo (F15's Risk 5, inherited by F34, F51, F57 and now F36), so ~68 strings are transcribed by hand into two files. The mitigation is unchanged and is the reason `copy.md` is canonical: **it is one file to one file**, and the `ar[key] === he[key]` assertion spec D17 already requires is the mechanical half. *Owner: team. Trigger: F45, the feature that makes Arabic selectable.*
- **F-7 — the tile alert diverges from F57's shipped `text-danger`, and a reviewer diffing the two components will read it as drift.** §3.2 is the reasoning: on this surface **nothing that can go wrong is her fault** — a 409 is two staffers reaching for one curtain and a 404 is a screen one tick behind — so `manage-restyle.md`'s notice register (`--color-warning-text`) is the correct one and red would frame the ordinary shop floor as failure. F57's single 404 («אשת הצוות הזו כבר לא פעילה») has the same character and is arguably mis-registered too, **but this deck does not change it**: `FloorPanel.test.tsx`'s shipped expectations must pass unedited (spec D15's acceptance rule) and a colour change is exactly the kind of edit that rule exists to catch. *Owner: team. Trigger: the code-review pass — and if the divergence is judged worse than the inconsistency, the fix is to move F57's one string, not to redden six.*
- **F-8 — the registry's `role="status"` is a second live region on the screen, and it is only defensible because it lives inside the top layer.** §5.4 explains why the panel's cue region cannot serve it (a live region outside an open modal dialog is not reliably announced while the dialog holds the accessibility tree). It exists only while the dialog is open. **The rule it must not erode is F57's D12**: one named control per *auto-updating* region, and the registry's region is not auto-updating — nothing writes to it but her own saves. Named because "there are now two `role="status"` regions" is a true sentence that would read as a violation without this paragraph. *Owner: team. Trigger: F37, whose full-screen alert overlay is the next thing to want a region of its own.*
- **F-9 — no E2E covers any of this, and the states that matter most are the ones only a stubbed backend can produce.** A 409 naming an occupant, a room released underneath a travelling finger, a poll tick unmounting a dialog under the user's hands — all unit-tested with fake timers against a mocked `api`, none exercised against a real backend. The console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend. **F36 makes the gap wider than F34 or F57 did**, because the rooms panel is the first floor surface whose *interesting* states are unreachable without a stub. F58 owns the `/manage/**` interception harness and the floor-program review budgets it there as real work. *Owner: team. Trigger: F58.*
- **F-10 — ten of this panel's inherited strings are still declared twice under `board.*` and `floor.*`, and F36 is caller three.** F57's **F-9** recorded the duplication and named its own upgrade path: *"F37, F41 and F59 are callers three, four and five, and the PR that adds the third set of duplicates is the one where `poll.*` is worth the rename."* **F36 adds no eleventh duplicate** — it reuses every one of F57's `floor.*` state strings unchanged (spec D17's reuse-before-invention rule), which is why this is a finding and not a defect. But it is now the **third** polling surface on one screen and the rename gets no cheaper. *Owner: team. Trigger: F37, the next feature that would declare an eleventh copy.*

**Parked question, carried forward from the spec and not reopened here:** *should a room out of service still show a client who was in it when it was deactivated?* It does — deactivation does not release (spec D1), so a greyed tile can carry a live assignment, and §2.3 rules the **rendering** (occupancy wins the Badge, the flag takes a word line) without touching the product question. It ships as-is because the alternative — evicting a bride to satisfy a flag — is clearly worse, and the pilot is what settles whether it reads as reassuring or as broken.
