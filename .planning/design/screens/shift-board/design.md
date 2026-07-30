# Screen: Live shift board + check-in (F34 — `apps/manage` seventh section, Epic SMC-5)

**Date**: 2026-07-30 · **Status**: **DESIGN GATE — the user's, not the designer's.** Interview **Q2** names the staff shift board a genuinely novel interaction pattern, so this deck does **not** self-approve and `design-critic` is not the authority here. The deliverable the user reviews is `prototype.html` in this directory; this file is what the prototype is an argument for. **No `.tsx` is written before the user rules.**
**Designer**: Claude · **Consumes**: `.planning/specs/shift-board-checkin.md` (**D1–D14**, Gate 1 self-approved under Q1) · `tokens.md` rev 1 · `.planning/design/screens/design-system/manage-restyle.md` (**binding**) · `.planning/design/screens/owner-bookings/owner-bookings.md` (F15's shipped deck — this board sits beside its section and inherits its rulings) · `packages/ui` and `apps/manage` **as shipped**
**Copy**: `copy.md` in this directory — every Hebrew string with its untranslated `ar` value (Interview Q3 / pre-decided #47).
**Prototype**: `prototype.html` in this directory — self-contained, RTL, real Hebrew, and it **fakes the tick**. A still deck cannot answer the only two questions this feature actually raises (is a five-second beat usable, is one-tap check-in right under a thumb), which is why Q2 flagged it.

**Filename note.** The spec's design-gate list names this file `shift-board.md`; it is `design.md` here at the run's instruction. Same document, same §-skeleton the `owner-bookings` deck established.

**Revision 2 — 2026-07-30, to the spec's post-adversarial-review revision. Read this before the rest.** The spec was revised after an adversarial pass (12 of 13 findings applied, 3 of them BLOCKER) and this deck was authored against its **first draft**. The spec's own design-gate section names the four gaps that opened; all four are closed here, and **nothing that was already documented was removed** — the state list grew from 14 to 17 and no state left it.

| # | What the spec changed | What this deck now carries | Where |
|---|---|---|---|
| **1** | **D14 is new** — a **user-operable** pause/resume plus an idle stop, because **WCAG 2.0 SC 2.2.2 Pause, Stop, Hide is Level A**, IS 5568 / AA is a **legal** bar (pre-decided #38), and **axe has no rule for 2.2.2** — so a board without it ships green in CI and non-conformant in law. `document.hidden` (§3.2 case 3) is *automatic* and does not satisfy it | The control's placement beside the freshness row (§1, §1.1), its full spec (**§2.4**, §6), **two new states** `B-paused` and `B-idle` (§4), its announcement rule (§7.1), its tab position (§7.2), the criterion as an explicit a11y-floor row (§7.4), the idle window put to the user (**P-8**), and eight strings (`copy.md` §2.1). **The prototype makes it pressable** — a pause that cannot be operated demonstrates nothing, which is the entire point of the gate | §1, §1.1, §2.4, §4, §6, §7.1, §7.2, §7.4, §8 |
| **2** | **D4.3's terminal set widened to `{401, 403}`** — deactivation ends in 401, but a mid-shift **demotion** ends in 403 (`RoleGate` raises; `resolve_session` is fine), and F51, the feature that makes demotion possible, merges **during this entry's park** | A sibling state **`B-403`** rather than a generalised `B-401`, because the two arrive by different code paths, carry different copy and are two different frontend tests. The 403 body is **generic by design** and may not name the role (`copy.md` §0 rule 10) | §3.1, §4, §7.1, §9 **F-10** |
| **3** | **D4(6) adds a client failure backoff** — 5s doubling to a ~60s cap, reset on the first success | `B-stale` no longer claims the loop "keeps trying on its normal beat", §3.2 gains the **sixth** failure mode, and the one string that promised «מיד» was revised (`copy.md` §6) | §3.1, §3.2 (6), §4 |
| **4** | **F-1 was accepted into the spec's a11y floor** — the readable, non-`aria-hidden` freshness row is now the spec's own ruling, not this deck's departure from D11 | **F-1 restated as an agreed ruling.** It is no longer an open deviation and a reviewer should not re-litigate it | §7.1, §9 **F-1** |

**Revision 1 — 2026-07-30, after a `design-critic` REVISE.** Four findings, all four verified against the artifact and **all four applied**; none was rejected. One was a genuine blocker in `prototype.html` that this deck's own §7.1 would have caught if anyone had measured instead of read (**F-7**, the live region re-announcing an unchanged cue on every tick). One was a hazard nobody had named in either the spec or the deck (**F-8**, a row growing under a descending finger). Two were demonstration gaps in the prototype — a documented mechanism with no way to feel it (§3.2 case 3, `visibilitychange`) and a documented tab stop that was not in the markup (**F-9**, the skip link). The fixes are recorded in §3.2, §4 B-ok, §7.1, §7.2 and §9 rather than folded in silently, because two of them change what the build must do.

---

## 0. Scope

The console gains a **seventh section** — `nav` key `board`, label «לוח היום» — rendered inside the shipped `ConsoleShell` (skip link, single sr-only `h1`, plain `<nav>` with `aria-current="page"`, 720px content cap: nothing to design there). **One new component**, `BoardSection.tsx`, plus one `<Fact>` row added to F15's `BookingDetail`.

| Surface | Component | Shape |
|---|---|---|
| The day's board | `BoardSection.tsx` (**new**) | day line → freshness/summary line → `role="status"` cue → `<ul className="divide-y">` of rows, each with exactly one control |
| Arrival fact on the detail | `BookingDetail.tsx` (**one line**) | one `<Fact>` when `checked_in_at !== null`, the `cancelled_at` treatment (spec D6) |

**Zero new `packages/ui` components and zero new variants — and this survived D14.** Everything on this screen is `Card`, `Badge`, `Button`, `EmptyState`, `Skeleton` and the two `lib/` helpers F15 already shipped (`statusBadge`, `isolateLtr`, `bookingErrorText` — `lib/booking.tsx:22,32,63`). If this deck had needed a fifth `Button` variant or a sixth `Badge` variant, that would have been the finding; it did not.

**The pause control was the one place that could have forced a variant, and it does not** — checked against the shipped file rather than assumed. `Button.tsx:4` declares `"primary" | "secondary" | "ghost" | "danger"`, `Button.tsx:35-39` gives `md` a `min-h-11` (44px), and `focusRing` is applied unconditionally at `Button.tsx:62`. The pause control is `variant="ghost" size="md"` — the shipped ghost, the same one F15 uses for its back control and this deck uses for the undo. **If a reviewer wants it louder than ghost, the answer is `secondary`, which also already exists**; the only thing that would need a new variant is an `outline` treatment, and §2.2 already flags that as a design-system decision above this feature. Stated explicitly because "the a11y control needed a new component" is exactly the shape of thing that gets added quietly during a build.

### Binding inheritances (obeyed, not restated)

From **`manage-restyle.md`**: 720px content cap at every breakpoint; the three-register split (an **outage** is `text-ink-muted`, a thing-she-must-fix is `text-danger`, a nothing-failed **notice** is `text-warning-text`); `EmptyState` over a blank column; inline muted cues over Toasts; **no `role="tab"` anywhere**; the console drops the storefront's ornament level; **never override a `packages/ui` component's own utility from the call site** (F15 F-6 — `cn()` is a plain join and the consumer loses).
From **`tokens.md`** rev 1: the gold law (`--color-gold-strong` never carries text — it appears on this screen exactly once, as a **hairline**); focus ring on every control; ≥44×44 touch targets; no raw px in app code; `prefers-reduced-motion` is already global in `theme.css:155-163`.
From **`owner-bookings.md`**: status is never signalled by colour alone and the Hebrew word inside the `Badge` carries it; one `Badge` per row region; `<bdi dir="ltr">` for numeric runs and **bare `<bdi>`** for Hebrew free text; the detail `h2` never carries the bride's name.
From the **spec**: no version field, no realtime vendor, no new endpoint for reads, no dispatch, no on-shift roster, no queue tickets, no wait-time analytics, no kiosk mode, no walk-in creation, no polling abstraction.

### Explicitly NOT here — with the spec's reasons

| Not shipped | Reason |
|---|---|
| **A date filter on the board** | D10/D12: the board *is* today, recomputed every tick so a counter tablet crossing midnight rolls itself. Any other day is one nav item away in «תורים», which already owns the day filter. A second date control would make two screens answer the same question and would let a staffer leave the board pointed at Tuesday. **Consequence this deck must live with**: there is no control to re-poke on a failed load, so unlike F15's list the board **does** ship a retry button (§4, and the `RD-readfail` precedent — `owner-bookings.md:233`). |
| **Row → booking detail navigation** | D10, declined *provisionally*, and this deck upholds it — see **P-2**. The list payload carries no phone and no notes by F15's D18, so "tap for the full record" means either a second fetch or reopening that ruling. |
| **Bands (expected / here / done)** | Q-4, ruled — see **P-4**. A band re-sorts the row you just tapped out from under your finger, on the one screen whose entire budget goes on *not* moving under you. |
| **Dispatch, on-shift staff badges, queue tickets** | Spec D9: none has data. `staff_users` has no `on_shift` column (`0003_auth.py:34-41`); the only staff rows before F51 are provisioned owners. |
| **Wait-time analytics** | Pre-decided #28. `checked_in_at − starts_at` becomes computable here and nothing computes it. |
| **Any highlight, shimmer, pulse or flash when a row changes** | D11, and §7.3 justifies it rather than inheriting it. The prototype ships a **prototype-only** toggle so the user can overrule with the thing in front of them. |
| **An in-flight "מתעדכן…" indicator** | A spinner that appears every five seconds forever is the definition of visual noise, and it makes the board look *busy* rather than *current*. The freshness line changes only when a fetch **succeeds**; a tick that is in flight is indistinguishable from a tick that has not started, which is the truth (§3). |
| **A read-only kiosk / display mode** | Pre-decided #27 — a small follow-up if the pilot asks. |
| **A second `Badge` for the arrival state** | `lib/booking.tsx`'s stated rule and F15's §6.1: exactly one Badge per row region and the status owns it. Arrival is **words**, on the row's own line (§2). |

---

## 1. The board — mobile 375, loaded (state **B**)

**375 is the primary case, not the fallback.** Pre-decided #27 puts this on each staff member's own phone, signed in as herself; a reception tablet is one more signed-in device. The desktop rendering is what happens when the same 720px column gets more room, and nothing is designed for it first.

```
+------------------------------------------------+
| [ConsoleShell header: שם הבוטיק / יציאה ]       |
| [nav stacked ≤767:                             |
|  פרופיל והגדרות | שעות פעילות | סוגי תורים |     |   7th item «לוח היום», aria-current="page",
|  מדיניות ביטולים | שמלות | תורים | לוח היום ]     |   gold-strong underline + font-semibold
+------------------------------------------------+
|  <main #console-main tabIndex=-1, max-w-720>   |
|                                                |
|  לוח היום                                       |   h2, --text-lg font-semibold ink
|  היום · 2.8.2026                                |   --text-sm ink-muted, date in <bdi dir="ltr">
|                                                |
|  הגיעו 3/12     עודכן 14:07  [ השהיה ]           |   FRESHNESS ROW — one flex line, NOT announced
|                                                |     (§3). ratio + time each <bdi dir="ltr">,
|                                                |     --text-sm ink-muted, time at inline-end.
|                                                |     The PAUSE control sits at the row's very
|                                                |     inline-end (§1.2 / §2.4) — Button ghost md,
|                                                |     44px, WCAG SC 2.2.2, spec D14
|                                                |
|  <p role="status" tabIndex=-1>  (empty at rest) |   the ONE announced region — user-initiated
|                                                |     outcomes only (§7.1)
|  +------ Card (paper, p-6) ----------------+    |
|  | <ul class="divide-y divide-border">     |    |
|  | ┌ <li> ───────────────────────────────  |    |
|  | │ 09:30  מיכל לוי            [ מאושר ]   |    |   time w-14 shrink-0 font-semibold
|  | │        מדידה ראשונה · אישרה הגעה       |    |     <bdi dir="ltr">
|  | │        נרשמה הגעה · 09:24             |    |   name bare <bdi> font-semibold
|  | │                    [ ביטול הרישום ]    |    |   arrival FACT line, --text-sm, ink (not muted
|  | └                                        |    |     — it is the row's operative fact)
|  | ┌ 10:00  נועה כהן            [ מאושר ]   |    |   undo: Button ghost md, inline-end
|  | │        מדידה ראשונה                    |    |
|  | │                         [   הגיעה   ]  |    |   check-in: Button secondary md, inline-end,
|  | └                                        |    |     own line at ≤767 (§5)
|  | ┌ ─────────── עכשיו 14:07 ───────────    |    |   NOW divider: gold-strong hairline + ink-muted
|  | ┌ 14:30  שיר אברהם          [ מאושר ]    |    |     text. Recomputed each tick (§2.3)
|  | │        התאמות אחרונות · שמלת אלמה       |    |
|  | │                         [   הגיעה   ]  |    |
|  | └ </ul>                                  |    |
|  +-----------------------------------------+    |
+------------------------------------------------+
```

- **Order is the server's `(starts_at, seat_index)` and the client never re-sorts.** F15's rule, and here it is load-bearing rather than tidy: any client-side reordering would make a check-in move a row, and a row that teleports on tap is the failure this whole design is spending its budget avoiding (**P-4**).
- **Cancelled rows stay in the list**, exactly as they do on F15's «תורים» — `list_day` returns every status as a deliberate constant (`bookings.py:369-394`) and a cancelled row is the staffer's evidence that the 11:00 slot is genuinely free. Hiding them would make the board disagree with the list one nav item away.
- **The Card's `p-6` is not overridden.** F15 F-6: `cn()` is a plain join, a consumer `p-0` loses to the baked-in `p-6`, and inset dividers are what four shipped sections already read like.
- **The day line is a fact, not a control.** «היום · 2.8.2026» exists because a board with no date picker must still say which day it is showing — the one moment it matters is the counter tablet at 00:01 (D12), where the date silently changing under an unattended screen would otherwise be invisible.

### 1.1 The freshness row is the whole live-ness contract — and it is where the 2.2.2 mechanism lives

Two facts and one control, one line, never announced:

| Element | Content | Register | Why it is here |
|---|---|---|---|
| inline-start | `board.summary` → «הגיעו 3/12» | `--text-sm --color-ink-muted` | The board's one aggregate. "How many are still outside" is the shift manager's actual question and counting 40 rows by eye does not answer it. One interpolation (`ratio` is built client-side as `"3/12"`), so `isolateLtr` is reused **unchanged** — no new helper. |
| inline-end | `board.updatedAt` → «עודכן 14:07»; `board.staleAt` when a tick failed; `board.pausedAt` when the loop is stopped | `--text-sm --color-ink-muted`, escalating to `--color-warning-text font-semibold` in both the stale and the paused case | The freshness claim. It changes **only on a successful fetch**, so it is a claim the board can keep. |
| **inline-end, after the time** | the **pause / resume control** — `board.pause` «השהיה» ⇄ `board.resume` «חידוש» | `Button variant="ghost" size="md"` | **New in revision 2. Spec D14 / WCAG 2.0 SC 2.2.2 (Level A).** §1.2 is the whole argument for the placement; §2.4 is the control's spec. |

When a tick fails this row is the thing that changes — see §4 **B-stale**. It is the entire honesty mechanism of the feature: the board never claims to be current, it states when it last was.

**One slot, three reasons the board might not be current, and a precedence order — because two of them can be true at once.** The row's inline-end can say «עודכן», «אין עדכון מאז» or «מושהה · עודכן», and a staffer who pauses a board that was *already* stale has produced both conditions. Ruling: **paused/idle wins the slot.** It is the cause that is currently in force (a stopped loop cannot fail a tick), it is the one she can undo from that exact spot, and the alternative — rendering both — would put «רענון» and «חידוש» side by side, two Hebrew words a hurried reader will not distinguish. So the two retry-shaped controls **never co-render**, which is a copy problem solved by a state rule rather than by a longer string.

### 1.2 Why the pause control sits *here* and not in a settings menu

Spec D14 requires "a mechanism for the user" and places it "next to the freshness line". This deck endorses the placement on its own reasoning, because the alternative placements are the ones a build would drift toward:

- **A control in a menu, a header or a settings section fails the criterion in spirit while passing it on paper.** 2.2.2 asks for a mechanism *in the content* that auto-updates. A pause two taps away, on a screen a staffer opens fifty times a shift, is a mechanism she will never find — and the population it exists for (a user for whom five-second repaints are the difference between usable and unusable) is exactly the population that cannot go hunting for it.
- **Beside «עודכן 14:07» it is the only place the button has a legible meaning.** «השהיה» alone is a mystery; «השהיה» sitting against a timestamp that visibly stops advancing is self-explanatory in one press. The freshness row was already the feature's honesty mechanism (§1.1); the control turns it into an honesty mechanism the user can *operate*.
- **It costs the layout nothing it was not already paying.** The row is one flex line with a gap; the control joins it at the inline-end and wraps to its own line when the stale copy makes the line long (§5). No new region, no new landmark, no second row of chrome.

---

## 2. The row — anatomy, and the control matrix

### 2.1 What a row shows

| Slot | Content | Bidi | Notes |
|---|---|---|---|
| Leading | `jerusalemTime(starts_at)` — `09:30` | `<bdi dir="ltr">` | `w-14 shrink-0 font-semibold`, so times form a scannable column at every width. F15's shape, deliberately identical — the two screens must not spell a time differently. |
| Name row | `customer_name` + status `Badge` | **bare `<bdi>`** on the name | `dir="ltr"` on Hebrew is itself a bidi defect (`owner-bookings.md` §6.3). Exactly one Badge, and it is the status. |
| Meta line | `appointment_type_name` · «אישרה הגעה» when `attendance_confirmed_at !== null` · `dress_name` | bare `<bdi>` | F15's exact treatment, including the rule that the bride's own attendance confirmation is **muted words, never a second Badge**. |
| Arrival line | «נרשמה הגעה · 09:24» when `checked_in_at !== null` | time in `<bdi dir="ltr">` | `--text-sm --color-ink` (not muted): on this screen it is the operative fact, not a caption. Absent entirely when she has not arrived — an empty slot would be 40 lines of nothing. |
| Control | one `Button` (§2.2) | — | The **only** interactive element in the row. |

**The row is not a button.** F15's «תורים» rows are whole-row buttons; these are not, and it is a rule rather than an inconsistency: a row that is itself a button cannot contain a button (nested interactive content is an HTML parsing and an AT defect, not a style preference). One action per row, and on this screen the action is check-in, not navigation — **P-2**.

### 2.2 Which control exists, per status and arrival

The row renders **only the operation the server will accept**, the F15 discipline (`owner-bookings.md` §2: "rendering four buttons where three answer 409 is a trap; a disabled button with no explanation is worse than an absent one"). The server stays the authority — a control that races reality still answers 409 and renders per §4 **B-actfail**.

| `status` | `checked_in_at` | Control | Verified against |
|---|---|---|---|
| `confirmed` | `null` | **«הגיעה»** — `Button variant="secondary" size="md"` | spec D5: `check_in` requires `status = 'confirmed'`, and has **no clock bound in either direction** — an early arrival is the ordinary case this board exists for |
| `confirmed` | set | arrival line + **«ביטול הרישום»** — `Button variant="ghost" size="md"` | D5: the undo has no status guard and no clock bound |
| `cancelled` | `null` | **none** | check-in would 409 |
| `cancelled` | set | arrival line + **«ביטול הרישום»** | D5, asserted: "a bride checked in and then cancelled must still have the mis-tap undoable" |
| `no_show` / `completed` | `null` | **none** | 409 |
| `no_show` / `completed` | set | arrival line + **«ביטול הרישום»** | D5: a status transition never touches `checked_in_at`, so this row is real and its undo must work |

**`size="md"` on both, never `sm`.** `Button.tsx:36` gives `sm` a `min-h-9` (36px), under the 44 floor — the same reason F15 ships its back control at `md` (`owner-bookings.md` §5).

**The undo is `ghost`, and rendering it exposed the cost.** `Button ghost` is `bg-transparent text-ink` with no border (`Button.tsx:31`) — the same treatment F15 gives its back control — so in the prototype «ביטול הרישום» reads as a line of text rather than as a control until you hover it. That is the intended demotion working slightly too well, on the one control that is a **recovery from a mis-tap**. Three options, none of which invents anything: keep `ghost` (recommended — it is the shipped ghost, and the undo should not compete with the next bride's check-in); use `secondary` (one word, and the two row states then look identically weighted); or add an `outline` variant to `Button.tsx`, which is a design-system decision above this feature. **Put to the user with the prototype in front of her** — it is a two-second judgement to make by looking and an unanswerable one on paper.

**Why `secondary` and not `primary` for check-in.** `primary` is `bg-gold text-ink` (`Button.tsx:29`); a 40-row day would render forty gold blocks down one column, which is both a de-luxe signal the config bans outright and a hierarchy that says nothing — with exactly one control per row there is no second action for a primary to outrank. `secondary` (`border border-ink bg-transparent text-ink`) puts an ink boundary around the target, which is what actually makes it findable in a scan. Recorded as considered; the prototype renders `secondary` and the user may overrule it in one line.

### 2.3 The «עכשיו» divider

One `<li aria-hidden="true">` inserted between the last row whose `starts_at <= now` and the first whose `starts_at > now`, recomputed on every tick:

```
──────────────  עכשיו 14:07  ──────────────
```

`border-t border-gold-strong` hairline (a **non-text** UI boundary — 3.80:1, inside the gold law) with the words in `--text-xs --color-ink-muted` on the page background. It is the one piece of chrome that makes a forty-row list answer "who is next" without reordering anything, and it is why §0 can decline bands and still claim the board is scannable.

- **`aria-hidden="true"`.** It is a visual landmark computed from a clock, it carries no information a screen-reader user cannot get from the times themselves, and un-hidden it would inject a changing string into the middle of the list on every tick — which is precisely the D11 hazard, arriving through the back door.
- **The board scrolls it into view on the FIRST load and never again.** Scrolling the page under a user who is reading it is the cardinal sin of a self-updating screen; the divider moving down the list as the day passes is enough.
- Absent when the day has no future rows (the divider would sit at the end, marking nothing) and when the day has no past rows (it would sit at the top, same).

### 2.4 The pause / resume control — the SC 2.2.2 mechanism, specified

**New in revision 2 (spec D14).** This is the one control on the screen that exists for a legal reason rather than an operational one, and it is the one an automated check will never miss because axe has no 2.2.2 rule. It is therefore specified here to the same level as the check-in control, so a build cannot ship an approximation of it.

| Property | Value | Why, verified |
|---|---|---|
| Element | **one** `<button>` whose label changes — `Button variant="ghost" size="md"` | One control, two names. Not two buttons (a disabled «חידוש» beside a live «השהיה» is a dead target and a second tab stop for nothing), and **not `aria-pressed`**: a toggle that changes *both* its name and its pressed state double-signals, and AT reads it as two contradictory facts. The name is the state. |
| Target size | `size="md"` → `min-h-11` = **44px**, `px-4` → ≥ 76px wide with «השהיה» | `Button.tsx:36`'s `sm` is `min-h-9` = 36px, under the floor — the same reason both row controls and F15's back control are `md`. Spec D14 names 44×44 explicitly. |
| Variant | `ghost` | The shipped demoted treatment (`Button.tsx:31`, `bg-transparent text-ink`). It sits inside a `--text-sm --color-ink-muted` line and a bordered `secondary` there would out-shout the check-in controls in the Card below, inverting the screen's hierarchy: the thing she came to do is check people in. **If the user wants it louder, `secondary` is a one-word change and no new variant** (§0). |
| Position in the tab order | **after `#console-main`, before the first row's control** | §7.2. It is the first stop inside the board, which is correct for a mechanism whose job is to stop the thing that is happening to everything after it. A keyboard user reaches it without walking forty rows. |
| Focus ring | `focusRing` from `@boutique/ui`, applied unconditionally by `Button.tsx:62` — 2px `--color-focus`, 2px offset | Nothing on this screen sets `outline: none`. |
| Accessible name | **changes with state**: `board.pauseAria` «השהיה — עדכון הלוח» ⇄ `board.resumeAria` «חידוש — עדכון הלוח» | The `board.checkInAria` shape reused exactly. Each **starts with the visible label**, so WCAG 2.5.3 label-in-name holds — «השהיה» is a literal prefix of «השהיה — עדכון הלוח». The bare visible label would be ambiguous in a rotor beside forty «הגיעה» buttons. |
| Announcement | on press, the `role="status"` cue carries `board.paused` / `board.idleStopped` / `board.resumed` | User-initiated, which is exactly what spec D11 admits into that region (§7.1). `board.resumed` is not symmetry: a screen reader does not reliably re-announce the name of an **already-focused** control that changed, so without it the one confirmation a sighted user gets free is denied to the user 2.2.2 is for. |
| Focus after press | **stays on the control.** It does not unmount — it renames | Deliberately unlike check-in, where the tapped button becomes a fact line and focus must move to the cue (§7.2). Nothing moves here, so moving focus would be the defect. |
| Effect of **resume** | fetches **immediately**, then resumes the interval | The `visibilitychange` behaviour reused rather than reinvented (§3.2 case 3, spec D14). Waiting out an interval after being asked to resume would make the control feel broken on the one press that has to feel decisive. |
| Effect on the failure backoff | resume **resets the interval to the base** | D4(6)'s backoff is a response to consecutive failures; a resume is a fresh user intent and starts from the beat she expects. A resume that inherited a 60-second backed-off interval would look like a control that did not work. |

**The idle stop is the same control with a timer instead of a tap** — spec D14's own framing, and it is what keeps this one mechanism rather than four. After **P-8**'s window with no interaction the loop stops itself, the freshness row escalates identically, the body line says `board.idleStopped` instead of `board.paused`, and the same button — now reading «חידוש» — restarts it in one press. Any interaction resets the window: a tap, a key, a focus change, a scroll. **Three other problems fall to it**, which is why it is worth a timer at all (spec D14): the unattended reception tablet that would otherwise hold a live list of named brides' appointments on screen for a 12-hour session TTL (pre-decided #27), roughly half of Risk 2's sustained load, and most of Q-1 — an interval that is visible and stoppable is an interval the user has already been given a say over.

**Declined: a frequency picker.** Spec D14 declines it and this deck agrees on its own grounds: 2.2.2 is satisfied by *any one* of pause / stop / hide / control-frequency, a dropdown is a settings surface plus a persisted preference plus a second constant, and the board would then have two places that answer "how live is this" — the picker and the freshness row — which is one more than the number of true answers.

---

## 3. The poll, made visible

This is the section the prototype exists to argue, so it is written as behaviour rather than as pixels.

### 3.1 What the user sees on a tick

| Tick outcome | What changes on screen | What is announced |
|---|---|---|
| **Nothing changed** (the common case) | the «עודכן HH:MM» time, and nothing else | nothing |
| Another staffer checked someone in | that row's control becomes an arrival line + undo; the ratio increments; the time updates | nothing |
| A new booking landed on today | a row appears in `(starts_at, seat_index)` position; the ratio's denominator increments | nothing |
| A bride cancelled through her SMS link | that row's `Badge` becomes «בוטל» and its control disappears | nothing |
| A booking was rescheduled off today | the row leaves — **unless it holds focus** (§7.2) | nothing |
| The fetch failed | the freshness row flips to **B-stale** (§4), and **the next retry is further away than the last** — D4(6)'s backoff, 5s doubling to a ~60s cap | nothing |
| The fetch succeeded after failures | the stale copy clears and **the interval resets to the base** | nothing |
| The fetch answered **401** (the session ended) | the loop **stops**; `board.sessionEnded` replaces the board | **yes** — `role="alert"` (§7.1) |
| The fetch answered **403** (a mid-shift **demotion** — spec D4.3, new in revision 2) | the loop **stops**; `board.accessEnded` replaces the board. Terminal for the same reason and by a different code path: `resolve_session` succeeded and `RoleGate` refused | **yes** — `role="alert"` (§7.1) |

**No highlight, no fade-in, no colour wash on a changed row.** D11 pins it and this deck endorses it on its own reasoning: a highlight that can fire every five seconds is a strobing screen for a full shift, it draws the eye to *what changed* when the staffer's question is *who is next*, and a "flash only on real change" rule still strobes on the busy afternoon when there is a real change every tick. Reduced-motion falls out of the same rule for free rather than needing a second one. **The prototype ships a toggle for this** so the user can overrule the argument with the thing in front of her — that is what a prototype gate is for.

### 3.2 The six failure modes, as the user experiences them

The spec's D4 owns the mechanism; this is what each one looks like. **It was five in the first draft; D4(6) added the sixth** — the backoff — and it is the one whose *copy* consequences reach furthest, because a stretching retry interval quietly falsifies any string that named a duration.

1. **Overlapping requests** — schedule-after-settle, so at most one poll is in flight per tab by construction. **Visible consequence**: on a slow connection the beat stretches (a 4-second response makes the effective interval 9 seconds) and the «עודכן» time tells the truth about it. The board never queues up a backlog of stale answers to paint in sequence.
2. **A slow response landing after a newer one** — one monotonic generation, bumped by mutations and the date roll. **Visible consequence**: none, ever. A poll issued before your tap can never repaint the row you just changed.
3. **The tab backgrounded** — `document.hidden` pauses; `visibilitychange` back to visible fetches **immediately**. **Visible consequence**: picking the phone back up shows a board that is current within one round-trip, not within five seconds. The freshness time is what proves it. **The prototype implements this rather than only describing it** (step **h**): `document.hidden` joins `schedule()`'s bail conditions and the visible transition calls `tick()` directly, so the beat meter visibly stops while the tab is away and the board repaints on return without waiting out an interval. It was a documented mechanism with no demonstration until the critic pass; that was a real gap in the artifact under review, not a wording one.
4. **Check-in versus the poll** — the board is **not optimistic** (D4.4). **Visible consequence**: the tapped button shows `loading` (the shipped `Button` overlay, width locked — `Button.tsx:66-77`) and becomes an arrival line only when the server's own `OwnerBookingDetail` says so. One round-trip of perceived speed traded for a check-mark that can never un-tick.
5. **Two staff tapping the same bride** — idempotent by predicate. **Visible consequence**: both staffers see success and the row shows the **first** timestamp. Nobody is told they lost.

6. **The backend is down, slow, or 500-ing** — **new in revision 2 (spec D4(6))**. Consecutive failed ticks back the interval off, 5s doubling to a **~60s cap**, and the first success resets it to the base. There is no server-side ceiling on this path — D3 declines a read limiter and every shipped `FixedWindowRateLimiter` is on some other route — so the throttle is the client's, and a fleet of loyal boards retrying every five seconds through an outage is exactly the load the server is least able to take. **Visible consequence**: none directly. The board is already in **B-stale** and looks identical whether the next attempt is five seconds or sixty away.

   **And that is precisely why it is a copy ruling, not a mechanism ruling.** The state is invisible, so any string that quantified the wait would be a promise the board silently stops keeping as the interval grows — «הלוח יתעדכן מיד» is true at tick 1 and false by tick 5, on a screen nobody is watching change. Two consequences the build inherits:
   - **`B-stale`'s copy must be interval-free and it now is.** «אין עדכון מאז 14:07» is a statement about the past and is true at any interval; «ייתכן שהמידע אינו עדכני.» states what is unknown rather than when it will be known. **Neither needed changing** — verified rather than assumed — which is the payoff of having written them as facts rather than as reassurance in the first place (`copy.md` §0 rule 4).
   - **`board.error.transitionInvalid` did need changing**, and it is the only string in the deck that did. «מצב התור השתנה. הלוח יתעדכן מיד.» → «…השורה תתוקן בעדכון הבא.» It is reachable in exactly the state where the old wording lies: a staffer taps during an outage, the board is already backed off to a minute, and the row-level error promises her a repair that is up to sixty seconds out. Naming the **event** instead of a **duration** is true at 5s, at 60s and at whatever constant F29 lands on. Recorded as `copy.md` §0 rule 9: no string names or implies a retry interval.

   **The one control that resets it is the resume button** (§2.4): a user asking for the board back gets the base interval, not an inherited 60-second gap.

### 3.3 What the prototype must let the user do

| Spec question | Prototype control | This deck's recommendation |
|---|---|---|
| **Q-1** Is five seconds the beat? | `5 שניות / 10 שניות / השהיה` plus a visible countdown to the next tick (prototype chrome only) | **Ship 5s.** It is one client constant and halving the load is a one-line change the day F29 says so (Risk 2). |
| **Q-2** Does a row reach the full booking? | — (ruled; the deck argues it) | **No.** P-2. |
| **Q-3** Is undo always visible? | check a bride in, wait, undo | **Always visible.** P-3. |
| **Q-4** One list or bands? | `רשימה אחת / לפי מצב` toggle, on the same rows | **One chronological list.** P-4. |
| **Q-5** Is the board the landing section? | — (ruled; binds F52) | **Yes, and F52 implements it.** P-5. |

**And three things the prototype must let the user *operate*, added in revision 2. These are not questions with a right answer — they are mechanisms whose only honest demonstration is pressing them.**

| What | Prototype control | Why a still deck cannot answer it |
|---|---|---|
| **The 2.2.2 pause / resume** (spec D14) | the real «השהיה» / «חידוש» button **inside the board**, at the freshness row's inline-end | **A pause the user cannot press does not demonstrate 2.2.2** — it demonstrates a picture of a pause. The user has to see the «עודכן» stamp stop advancing, see the beat meter stop, press «חידוש», and see the board fetch **at once** rather than after an interval. The prototype's own `5 שניות / 10 שניות / השהיה` chrome in the dark bar is **the reviewer's demo switch and is not the product** — it lives outside the device frame, ships in no `.tsx`, and satisfies nothing. Confusing the two is how a board ships without the control. |
| **The idle stop** (spec D14, window is **P-8**) | fires on its own after the demo window with no interaction; any tap, key or scroll resets it | The judgement is "does being stopped without asking feel like a fault or like a feature", and that is a feeling, not a number. **The prototype's window is deliberately short (45s) so it is reachable in a review; production is P-8's value (recommended 10 minutes)** — the prototype bar says so, because a reviewer who thinks the shipped board stops after 45 seconds would reject the right design for the wrong reason. |
| **The failure backoff** (spec D4(6)) | «לא מתעדכן» now really backs off — 5s → 10 → 20 → 40 → 60 cap — with the growing gap visible on the beat meter and named in the log | The question is whether **B-stale**'s copy still reads true when the retry is a minute away. That is unanswerable on paper and obvious in ten seconds of watching the meter stretch while «אין עדכון מאז 14:07» sits there unchanged — which is the argument that it needed no rewrite, made by demonstration instead of by assertion. |
| **The 403** (spec D4.3) | «אין הרשאה» scenario button | So the user can read the generic body and confirm for herself that it names no role — the constraint is `copy.md` §0 rule 10 and it is easier to check by looking than by trusting a table. |

---

## 4. States — the single source for this feature

Every state the spec's Frontend-changes list names, plus what is announced and where focus goes. The list may not shrink.

| # | State | Trigger | What she sees | Region / focus |
|---|---|---|---|---|
| **B-load** | First load | section opened | day line + `<Skeleton variant="text" lines={4} />`; **no** freshness row (there is nothing to be fresh); cue region carries `board.loading` | the cue region is `role="status"`, so loading **is** announced — F15's F-1 fix, reusing the region the cues need anyway |
| **B** | Loaded, rows | 200, `total > 0` | §1 | nothing announced |
| **B-one** | Exactly one row | 200, `total === 1` | identical, no special case. The «עכשיו» divider renders only if it separates something (§2.3), so a one-row day shows a row and nothing else. Ratio reads «הגיעו 0/1» | — |
| **B-many** | 40 rows | 200 | identical rows, no virtualization, no paging. 40 × ~112px ≈ 4.5 screens at 375 — the divider is what makes that scannable, and the ratio is what makes it summable. **The board never auto-scrolls after the first load** | — |
| **B-empty** | Empty day | 200, `total === 0` | `<EmptyState title body />` inside the Card — never a blank column. Body names «תורים» for other dates and offers **no CTA** (the owner cannot create a booking — Interview Q6) | ratio and freshness row still render («הגיעו 0/0»): an empty board that has stopped updating must still be able to say so |
| **B-fail** | **First** fetch failed | non-2xx / network on the initial load | `<p role="alert" className="text-sm text-ink-muted">` `board.loadFailed` — the **outage** register — **plus a «רענון» `Button variant="secondary"`**. Unlike F15's list this screen has no date control to re-poke, so the retry is a real affordance and not a second tab stop for one act (the `RD-readfail` precedent, `owner-bookings.md:233`) | alert |
| **B-stale** | A poll failed **with rows on screen** | non-2xx / network on any later tick | **The rows stay.** The freshness row's inline-end flips from «עודכן 14:07» to «אין עדכון מאז 14:07» in `--color-warning-text font-semibold`, and a second `--text-sm` line appears under it with `board.staleBody` + the «רענון» button. **The loop keeps trying, and each consecutive failure pushes the next attempt further out — 5s doubling to a ~60s cap, reset by the first success** (spec D4(6), §3.2 case 6). Nothing on screen states the interval and nothing may: the copy is deliberately interval-free so it stays true as the gap grows | **not announced** (§7.1). The alternative — blanking to the outage message — throws away correct data to report a network fault |
| **B-paused** | **The user pressed «השהיה»** | a tap on the pause control (§2.4) | **New in revision 2 — spec D14 / WCAG 2.0 SC 2.2.2 (Level A).** The loop stops. **The rows stay and are not dimmed** — they were correct at «עודכן 14:07» and pausing did not make them wrong. The freshness row's inline-end becomes `board.pausedAt` «מושהה · עודכן 14:07» in `--color-warning-text font-semibold` — the identical escalation B-stale gets, for the identical reason (P-6: correct-looking rows beside a grey notice get scanned past, and a board *she* paused is easier to forget than one that broke). Under it, `board.paused`. The control itself now reads «חידוש». **No «רענון» button in this state** — the resume control is the affordance and two similar Hebrew words in one line is worse than one (§1.1's precedence rule) | **announced once**, `role="status"`, `board.paused`. It is user-initiated, which is exactly what D11 admits there. **Focus stays on the control** — it renamed, it did not unmount (§2.4) |
| **B-idle** | **The idle timer fired** | **P-8**'s window with no interaction (recommended 10 min) | **New in revision 2 — spec D14.** Mechanically identical to **B-paused**: same stopped loop, same freshness escalation, same «חידוש» control, same one-press recovery. **One thing differs and it is the whole point of having two states**: the body line is `board.idleStopped` «העדכון הופסק אחרי 10 דקות ללא פעילות.» — it names the cause, because a board that stopped *by itself* and does not say why is indistinguishable from a board that broke. Beyond the criterion this state also ends the unattended-counter-tablet exposure pre-decided #27 creates — a signed-in device holding a live list of named brides for a 12-hour session TTL — without a kiosk mode, a lock screen or a session change | **announced once**, `role="status"`, `board.idleStopped`. Focus is wherever she left it; the timer fires precisely because she was not touching anything, so there is nothing to move and moving it would be a jump-scare |
| **B-401** | Session ended (**deactivation**) | any tick answers 401 | **The loop stops.** The board is replaced by `<p role="alert">` `board.sessionEnded` + a «רענון הדף» button. Rows are cleared: a dead session cannot vouch for them, and leaving them under a "you are logged out" message invites a tap that will 401 too | `role="alert"` — **assertive**, and this is one of the two places that is right (§7.1) |
| **B-403** | Access ended (**a mid-shift demotion**) | any tick answers 403 `NOT_AUTHORIZED` | **New in revision 2 — spec D4.3, whose terminal set widened from `{401}` to `{401, 403}`.** Identical *shape* to B-401 — loop stopped, rows cleared, `<p role="alert">` + «רענון הדף» — and a **different sentence**: `board.accessEnded` «אין הרשאה לצפות בלוח כרגע. לבירור אפשר לפנות לבעלת הבוטיק.» **A separate state rather than a generalised B-401**, because the two arrive by different code paths (`resolve_session` returning `None` vs. `RoleGate` raising `NotAuthorizedError`), read differently to the staffer — one says *log in again*, the other says *logging in again will not help* — and are two separate frontend tests in the spec. **Rows are cleared here for a second reason 401 does not have**: the day's list is precisely what she is no longer permitted to see. The 403 body is **generic by design** and may not name the role (`copy.md` §0 rule 10) | `role="alert"`, once. The reload's honest limit is **F-10** |
| **B-trunc** | `total > items.length` | 200 with `total > 50` | one `--text-sm --color-ink-muted` line under the list: `board.truncated`, naming «תורים» as where the rest is. **Stated, never absorbed** — a hidden bride is the one failure a board may not have (spec D3) | — |
| **B-busy** | Check-in / undo in flight | control tapped | that control only: `loading` on the shipped `Button` (spinner overlaid, label kept for width, `aria-busy`). Every **other** row's control stays live — the board is not a form and one tap must not freeze the shift. **The poll does not tick while a mutation is in flight** (D4.4), so the row cannot be repainted underneath the request | nothing announced yet |
| **B-ok** | Check-in / undo succeeded | 2xx | the row is patched from the server's `OwnerBookingDetail` (`BookingsSection.tsx:74-78`'s shape); the ratio and the freshness time update; the cue region carries `board.checkedInCue` / `board.undoneCue` **including the customer's name** (§7.1). **The cue string then stays on screen until the next tap replaces it** — it is not cleared on a timer, and every repaint between now and then must leave the node untouched (**F-7**) | the cue region is `tabIndex={-1}` and is **focused** — on a check-in the tapped button unmounts (it becomes an arrival line), so without this focus drops to `<body>` (WCAG 2.4.3), which is F15's house mover-rule |
| **B-noop** | Repeat check-in | 200, `changed=false` (another staffer got there first) | **Identical to B-ok**, deliberately. The server keeps the first timestamp and the row renders it; the cue still confirms. A staffer who taps a bride who was just checked in by a colleague sees the outcome she wanted, because it *is* the outcome she wanted (spec D4.5: "a 409 here would be a lie told to the person who was right") | as B-ok |
| **B-actfail** | Check-in refused | 409 `BOOKING_TRANSITION_INVALID` (somebody cancelled her in the gap) | `<p role="alert" className="text-sm text-danger">` **inside that row**, under the control — the **fix-this** register, and it must be in the row because a page-level error on a 40-row board names no bride. Copy: «מצב התור השתנה. הלוח יתעדכן מיד.» The next tick repaints the row and the alert clears | alert, `tabIndex={-1}`, **focused** — the control it belonged to is `disabled` on tap and may unmount, so `.focus()` on the trigger is a no-op (F15's DA-fail reasoning, `owner-bookings.md:228`) |
| **B-404** | Check-in on a vanished booking | 404 `NOT_FOUND` | same in-row alert, copy from `errorMessage(error)`. Unreachable in practice — bookings are soft-deleted by nothing in v1 — and designed anyway because RLS makes another tenant's id indistinguishable from missing | as B-actfail |

**State precedence.** A mutation's response is always the truth for its row (it *is* an `OwnerBookingDetail`, which extends the list row). A poll's response is always the truth for everything else. The two can never fight, because the loop does not tick during a mutation and the mutation bumps the generation on settle.

**Precedence in the freshness row's inline-end slot**, now that three states compete for it: **B-401 / B-403** (the board is gone entirely, so the row is gone with it) > **B-paused / B-idle** («מושהה · עודכן») > **B-stale** («אין עדכון מאז») > **B** («עודכן»). The one case that actually occurs is pause-while-stale, and §1.1 rules it: a stopped loop cannot fail a tick, so the stop is the operative cause and the resume control is the operative remedy — which also keeps «רענון» and «חידוש» from ever sharing a line.

**Seventeen states, and the list still may not shrink.** It was fourteen; revision 2 adds `B-paused`, `B-idle` and `B-403` and removes none.

---

## 5. Breakpoints — 375 / 768 / 1440

Mobile-first, and there is exactly **one** breakpoint branch in the whole feature.

| Width | What is different | Why |
|---|---|---|
| **375** (primary) | The row is a two-part flex column: the text block (time + name + badge + meta + arrival line) on top, **the control on its own line, aligned to inline-end**. The nav is stacked full-width (shell behaviour). | Arithmetic, not taste: 375 − 2×`--space-4` gutters = 343, − 2×`--space-6` Card padding = **295px** of row. A `w-14` time column plus gap takes 68 and a 44-high control needs ~92 plus gap, leaving **123px** for the name — which wraps «אלכסנדרה בן-דוד הכהן» into a five-line ribbon. Dropping the control to its own line returns the name column to **227px** and makes the target *larger*, not smaller. The `Card`'s padding cannot be reduced from the call site (F15 F-6), so this is the lever that exists. |
| **375, long name** | A name that wraps (verified in the prototype with «אלכסנדרה-מרי בן-דוד הכהן אשכנזי») takes two lines and pushes the status `Badge` onto a third. That is the correct failure: `overflow-wrap: anywhere` on the name, `flex-wrap` on the name row, and no truncation anywhere. **No ellipsis, ever** — a board that abbreviates a bride's name is a board that makes two brides look like the same person, and the row has vertical room it does not have horizontal room. |
| **768** | The control moves to the row's inline-end on the **same** line as the text block, vertically centred (`sm:flex-row sm:items-center`). The nav becomes a horizontal row (shell behaviour). | 720px cap − 48 padding = 672 of row; the name column is 512px, which is more line-length than a Hebrew name ever needs. Rows get shorter, so more of the day fits one screen — which is the whole reason a reception tablet is worth its extra width. |
| **1440** | **Identical to 768.** | The console never exceeds a 720px content column (`ConsoleShell.tsx:83`), and this deck does not make the board the exception. Four to six columns of a table cannot hold a readable Hebrew line inside 720px, and a table that scrolls sideways on the owner's phone is worse than a list on every device — F15's ruling, and it applies harder here because the phone is the primary device. **A wall-mounted 1440 display board is not this feature** (pre-decided #27 makes kiosk mode a follow-up). |

The `<ul>`'s DOM is identical at all three widths. No breakpoint changes what is rendered, only how one flex wraps.

**The freshness row at 375, now that it carries a control — measured in the prototype, not estimated.** The row sits in `.shell-main`, not inside the Card, so it has 375 − 2×`--space-4` = **343px**. An earlier draft of this paragraph did the arithmetic by hand, predicted that the longer stale and paused stamps would push the row one pixel over and specified a wrap. **Driving the prototype at 375 says otherwise, and the measurement wins:**

| Variant | Row inline-end | Row height | Control box | Wrapped? | Overflow? |
|---|---|---|---|---|---|
| **B** updating | «עודכן 14:14» | 44px | 82×44 | no | no |
| **B-stale** | «אין עדכון מאז 14:14» | 44px | 82×44 | no | no |
| **B-paused / B-idle** | «מושהה · עודכן 14:14» | 44px | 76×44 | no | no |

All three fit **one line** at 375 with the 44px control on it, and the page never scrolls horizontally. The hand estimate was ~15% pessimistic about Hebrew at `--text-sm`. **`flex-wrap` stays on the row anyway** — not as a state that occurs today, but because the inline-end is the one slot in this feature whose string can grow (a longer stale phrasing, a future `ar` translation that is not the Hebrew standing in), and a control that gets squeezed under 44px is an accessibility regression rather than a layout one. No truncation, no icon-only fallback, no `sm:` branch of its own: the control's label is never abbreviated and never becomes a glyph, because an icon-only pause is a control whose meaning depends on a convention this product has not established anywhere else.

---

## 6. Component notes — exact tokens

| Element | Notes |
|---|---|
| Section heading | `<h2 className="text-lg font-semibold text-ink">` — `CatalogSection.tsx:116` / `BookingsSection.tsx:86`. Not `SectionHeading` + ornament (the console drops storefront flourishes) |
| Day line | `<p className="text-sm text-ink-muted">`, date in `<bdi dir="ltr">` via `jerusalemDate()` — **no new formatter** (D12) |
| Freshness row | `<div className="flex flex-wrap items-center justify-between gap-3 text-sm text-ink-muted">`; the stale **and** paused states add `text-warning-text font-semibold` on the time half only. `items-center` rather than `items-baseline` now that the line carries a 44px control — baseline-aligning a button against a caption drops it below the text's baseline box |
| **Pause / resume control** | `Button variant="ghost" size="md"` at the row's inline-end (§2.4). No new variant, no `aria-pressed`, no icon. `aria-label` = `board.pauseAria` / `board.resumeAria`, swapping with the visible label. Focus ring is `Button.tsx:62`'s unconditional `focusRing`; 44px is `sizes.md`'s `min-h-11` |
| Paused / idle body line | `<p className="text-sm text-ink-muted">` under the freshness row — the `board.staleBody` slot and treatment, carrying `board.paused` or `board.idleStopped` and **no** «רענון» button (§1.1) |
| Cue region | `<p role="status" tabIndex={-1} className="text-sm text-ink-muted">` — the `BookingDetail.tsx:231-239` shape, empty at rest. **Written only when its value changes** (**F-7**) — an unchanged re-assert is still a mutation inside a live region |
| List | `<Card>` → `<ul className="divide-y divide-border">`, `BookingsSection.tsx:142`'s exact shape |
| Row | `<li className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center">`; text block `flex items-start gap-3 min-w-0 grow`; time cell `w-14 shrink-0 font-semibold text-ink` |
| Status Badge | `statusBadge()` from `lib/booking.tsx` — **imported, not re-declared**. Four variants, the Hebrew word carries the state, `danger` deliberately absent |
| Check-in control | `Button variant="secondary" size="md"` (`min-h-11` = 44px, `border border-ink` = 13.89:1 boundary), `fullWidthMobile={false}` — a full-width button per row would be a wall |
| Undo control | `Button variant="ghost" size="md"` — demoted but not hidden, and `md` because `sm` is 36px |
| Arrival line | `<p className="text-sm text-ink">` with the time in `<bdi dir="ltr">` |
| «עכשיו» divider | `<li aria-hidden="true">` with `border-t border-gold-strong` and `text-xs text-ink-muted` — the **only** gold on this screen, and it is a hairline, never text (the gold law) |
| Loading | `Skeleton variant="text" lines={4}` — `aria-hidden`, so the announcement is the cue region's job |
| Empty | `EmptyState title body` — icon-less, **no CTA** |
| Retry | `Button variant="secondary" size="md"` |
| In-row error | `<p role="alert" tabIndex={-1} className="text-sm text-danger">` |
| Session-ended (B-401) **and access-ended (B-403)** | `<p role="alert" className="text-sm text-ink">` + `Button variant="secondary"` — **the same treatment for both**, different string. The shape is identical because the consequence is identical (the board is over); only the sentence and the remedy differ |

**Contrast, from the tokens ledger — not eyeballed.** ink/paper 13.89 · ink-muted/paper 5.61 · danger/paper 6.18 · warning-text/paper 5.20 · success/paper 5.56 · focus ring (gold-text) 5.57 on cream · gold-strong hairline 3.80 (non-text ✓). **This feature introduces no new colour pair**, so the ledger needs no addition at this gate.

---

## 7. The a11y contract — IS 5568 / WCAG 2.0 AA is a legal requirement (pre-decided #38)

### 7.1 Live regions — the real hazard in a five-second board

A board that repaints every five seconds has two opposite failure modes, and picking one at random gets you the wrong one:

- **Spam.** Wrap the list in `aria-live="polite"` and a screen-reader user is read the board every five seconds for a whole shift. It passes every automated check and is unusable.
- **Silence.** Wrap nothing, and the content under the user's virtual cursor is swapped with no signal at all — she can act on a row the server moved.

Spec D11 rules out the first. This deck rules on the rest, and the ruling is a **three-region split**:

| Region | ARIA | Carries | Politeness, justified |
|---|---|---|---|
| **The cue** (`<p>` above the list) | `role="status"` (= `aria-live="polite"` + `aria-atomic="true"`) | first-load «טוען את לוח היום…», then **user-initiated outcomes only**: `board.checkedInCue`, `board.undoneCue`, and **D14's `board.paused` / `board.idleStopped` / `board.resumed`**. Empty at rest | **polite.** Every string in it is the consequence of a tap the user just made, so it is never an interruption of something she did not ask for — and polite waits for her current sentence to finish, which on a screen she is actively reading is the difference between confirmation and interruption |
| **The list** | **no live attributes at all** — no `aria-live`, no `role="log"`, no `aria-relevant` | the rows | **off.** `role="log"` is the tempting wrong answer: it is designed for append-only chat, and this list mutates in place and re-sorts on the server. Applying it here would announce forty rows on the first tick after any change |
| **The freshness row** | **no live attributes**, and deliberately **not `aria-hidden`** | «הגיעו 3/12 · עודכן 14:07» / the stale copy | **off, but readable.** See the finding below |

**The freshness row is readable and not `aria-hidden` — and as of the spec's revision this is the AGREED RULING, not this deck's deviation.** The first draft of this deck recorded it as **F-1**, a considered departure from D11's parenthetical "an `aria-hidden` 'updated HH:MM' or equivalent", with the reasoning that `aria-hidden` would make the board's **only** honesty signal sighted-only: a screen-reader user would have no way, ever, to learn that the board stopped updating twenty minutes ago — on a statutory-AA surface, and about the one fact the feature is built to convey. **The revised spec accepted that reasoning and wrote it into its own a11y floor**: "the freshness line is **readable, reachable and not in a live region** rather than `aria-hidden` … The 'or equivalent' is taken (the deck's F-1, accepted)". So the row is plain, readable, reachable by the virtual cursor at any moment, and **not in a live region**, so it is never announced. No spam, no denial. **There is nothing left here for a reviewer to rule on** — F-1 in §9 is retained as the record of how the ruling was reached, not as an open item.

**The pause control's announcements are inside the same rule, not an exception to it.** Pausing, idle-stopping and resuming all write `board.paused` / `board.idleStopped` / `board.resumed` into the cue region. Each is **user-initiated** — including the idle stop, whose trigger is her own inactivity and not the poll — so none of them weakens D11's mechanical rule that *the poll* may never write into a live region. The frontend test the spec names ("the announced region does not change on a poll tick, and does change on a check-in **and on a pause**") is written against exactly this distinction.

**`role="alert"` (assertive) appears exactly three times**, and each is justified rather than reached for:
- **B-401**, once per dead session. Everything the user does next will fail silently; interrupting is proportionate, and it cannot repeat because the loop stops.
- **B-403**, once per demotion — **new in revision 2**. Same argument, different cause: her next action will be refused, the loop has stopped, and it cannot repeat. It is assertive rather than polite for the same reason 401 is: this is not a confirmation of something she did, it is the removal of the screen she is standing on.
- **B-actfail**, once per refused tap. It is the direct answer to an action she just took and it is bounded by her own tapping.

None can be triggered by the poll on its own — the 401 and 403 are *delivered* by a tick but are terminal responses to a revocation somebody else performed, and each fires once because the loop stops. **The poll can never write into any live region** — that is the mechanical rule, and the spec makes it a frontend test rather than a deck promise.

**And "write" means write, not change.** This deck's first prototype satisfied the rule in intent and broke it in fact, which is worth spelling out because the trap is invisible in a diff. The cue is set on a tap and never cleared; the repaint that follows every tick re-assigned `textContent` to whatever the cue currently held. Assigning a non-empty string to `textContent` runs the DOM's **string-replace-all**: the existing `Text` node is *removed* and a *new* one inserted, even when the two strings are byte-identical. That is a genuine `childList` mutation inside `role="status"` — measured, not reasoned: three identical assignments produce three `MutationObserver` records, and a screen-reader user would therefore have been read «נרשמה הגעה עבור מיכל לוי.» every five seconds from her first check-in to the end of the shift. The exact spam D11 and §7.1 exist to prevent, arriving through the one region that is *allowed* to speak. Recorded as **F-7**; the rule the build inherits is that **a live region is written only when its value actually changes**, and the frontend test asserts it across *repeated identical* ticks rather than a single one.

**The cue names the customer, and the detail heading does not.** F15 refused the bride's name in `BookingDetail`'s `h2` because it puts PII in a **persistent announced landmark** re-read on every screen entry. A cue is the opposite: transient, once, confirming an act on a specific person — and «נרשמה הגעה.» after tapping one of forty rows cannot confirm *which* bride, which makes the cue useless exactly when the board is busy. Different mechanism, different answer.

### 7.2 Focus, and content moving underneath it

- **Rows are keyed by `booking.id`.** A repaint mutates text nodes inside a stable element, so focus inside a row survives every tick. This is the single most important line in the section and it costs one prop.
- **A row that leaves the day is removed on the next tick — unless it holds focus.** The only way a row leaves is a reschedule to another date (cancelled rows stay). If the departing row contains `document.activeElement`, the board keeps it, replaces its control with the muted words «התור הועבר לתאריך אחר», and removes it on the first tick after focus moves. One condition, and it is the only case where focus could be dropped to `<body>` by something the user did not do.
- **After a check-in, focus goes to the cue region** (`tabIndex={-1}`), because the tapped control unmounts. After an **undo**, the check-in button reappears in the same row — focus still goes to the cue, for one rule instead of two. **After a pause or a resume, focus does not move at all**: that control renames itself rather than unmounting, so there is nothing to recover from and moving focus would be the defect (§2.4).
- **Tab order** is exactly: skip link → header logout → seven nav buttons → `#console-main` → **the pause / resume control** → **one stop per row** (its single control) → the retry button when present. Forty rows means forty tab stops, and that is correct: each is a distinct action on a distinct person. No trap, no roving tabindex, no `role="tab"` anywhere. The shell's skip link is shipped and unchanged; `prototype.html` renders it too, so that first stop is demonstrable from a cold page load rather than only asserted here.

  **The pause control's position in that order is a ruling, not an accident of DOM order.** It is the **first stop inside the board**, before any row. A 2.2.2 mechanism placed after the auto-updating content it governs would be reachable only by walking through forty tab stops on a list that is repainting underneath the walk — which is the exact situation the criterion exists to let a user escape from. Putting it first means one Tab from the skip target stops the thing that is happening.
- **The board never moves the scroll position after the first load** (§2.3).
- **A tick never repaints while a pointer is down on the board.** §2.3 and the bullet above protect a *stationary* target — focus, scroll, sort order. They do not protect a **moving finger**, and this screen has a mechanism that moves targets vertically without moving any row's *position in the list*: §2.1 renders the arrival line only when `checked_in_at` is set, so a remote check-in landing on row 3 grows row 3 by one `--text-sm` line plus a `--space-1` gap — **≈26px** — and slides every control below it down by that much. At 375 the control sits on its own line under the text block (§5), so it is exactly the thing that moves. A finger already travelling toward row 9's «הגיעה» during the ~200-400ms of a repaint can land on the row above or on nothing. **Mitigation**: a `pointerdown` anywhere on the board holds the next repaint, and `pointerup` / `pointercancel` releases it immediately; the loop keeps its own beat underneath, so a lost `pointerup` costs at most one interval and can never stall the board. One condition, at the poll's single entry point, and it covers every other reflow cause for free — a booking inserted above, a row leaving the day, a row's `Badge` wrapping — not just the arrival line that exposed it. **Rejected alternative**: reserving a fixed `min-block-size` on the row's text column for the two-line arrival case. It buys the same protection with 26px of dead space on every not-yet-arrived row — ~1,000px on a forty-row day, on the one screen whose value is that it scans — and §2.1's "an empty slot would be 40 lines of nothing" is the same ruling arrived at from the other side. Recorded as **F-8**; the prototype demonstrates it (step **i**).

### 7.3 Motion

Nothing on this screen animates except the shipped `Button` spinner during a mutation. No highlight on a changed row, no fade on an arriving row, no pulse on the freshness line (§3.1). `theme.css:155-163` already freezes everything globally under `prefers-reduced-motion`, so this feature adds no rule there — because it adds no motion.

### 7.4 The rest of the floor

**SC 2.2.2 Pause, Stop, Hide (Level A) — the row this deck was missing, and the one no tool will ever add for us.** Content that auto-updates, starts automatically and is presented in parallel with other content must offer **a mechanism for the user** to pause, stop or hide it, or to control its frequency. A board repainting every five seconds for a whole shift is squarely that. The first draft of this deck listed seven a11y items — live regions, 44×44, no colour-only, `bdi`, one `h1`, the 720px cap, focus rings — and **not one of them was a pause, a stop, a hide or a frequency control**; the only pause in the design was `document.hidden`, which is automatic, and *"a mechanism the user cannot operate is not a mechanism for the user"*. §2.4 is the discharge.

Three things make this row different from every other item in this section, and all three are reasons it is stated here rather than left to a build:

1. **It is a legal bar.** Pre-decided #38 makes IS 5568 / WCAG 2.0 AA a **legal** requirement for these staff screens, and Level A criteria sit inside AA conformance.
2. **`axe` cannot see it.** The security checklist's whole accessibility section is four rows whose one automated item is axe (`security-checklist-v1.md:46-50`), and **axe has no 2.2.2 rule** — the criterion needs a human judgement about what counts as auto-updating. So the failure mode is not "CI catches it late"; it is "**CI stays green and the product is non-conformant**". The `axe` pass in §7.4's last bullet is therefore explicitly **not sufficient** for this row and must not be treated as covering it.
3. **The only coverage is the two named frontend tests plus this gate.** The spec pins them: the pause control stops the loop and resume fetches immediately; the idle stop fires and one tap resumes. They may not be dropped as redundant with the axe assertion.

**SC 2.2.1 Timing Adjustable (Level A) — named here, and explicitly *not* F34's to close.** `session_ttl_seconds` is 43200 (12h), which is **under** 2.2.1's 20-hour exception, and it is both unextendable and unwarned (no sliding renewal). That is a Timing Adjustable gap, not the ops annoyance it was first filed as. The remedy is a warning before expiry plus a way to extend — a session-model change with its own security argument, owned by **F21**. What this screen does is stop the loop and say so honestly (**B-401**). Recorded so the item is inherited as a legal one rather than lost as a comfort one.

- **≥44×44 on every target**: both row controls **and the pause / resume control** are `size="md"` → `min-h-11`; the retry and reload buttons likewise. At 375 the row control sits on its own line and is *wider* than the floor, not narrower, and the pause control wraps to its own line in the two states that make the freshness row long (§5).
- **Visible focus ring** on every interactive element — `focusRing` from `@boutique/ui` (2px `--color-focus`, 2px offset). Nothing sets `outline: none`.
- **Accessible names carry the visible label plus the person**: `aria-label="הגיעה — מיכל לוי, 09:30"` / `aria-label="ביטול הרישום — מיכל לוי, 09:30"`. Forty buttons all named «הגיעה» is a screen-reader dead end; and the label **starts with the visible string**, so WCAG 2.5.3 label-in-name holds even though 2.0 does not require it.
- **Status is never colour alone** — the Hebrew word inside the `Badge` carries it (`lib/booking.tsx:10-20`), and **arrival is never colour alone either**: it is the words «נרשמה הגעה» plus a time, not a tint, not a dot, not a check glyph. **Paused is never colour alone either**: the `--color-warning-text` escalation on the freshness time is reinforcement, and the state is carried by the word «מושהה», by the body line and by the control's own label flipping to «חידוש» — three text signals, no icon anywhere.
- **Bidi**: `<bdi dir="ltr">` on times, dates and the ratio; **bare `<bdi>`** on customer name, type name and dress name. `dir="ltr"` on a Hebrew name is the worse defect because it looks deliberate.
- **Headings**: the shell owns the single (sr-only) `h1`; the board heading is `h2`; there are no `h3`s, because the board has no groups — which is itself the argument against bands (**P-4**).
- **Content capped at 720px** at every width.
- **`A11yMenu` / `A11yStatementLink` are storefront-only** (`tokens.md`) — the console ships neither, so no fixed-chrome clearance applies.
- **An `axe` pass** runs over the board in `__tests__/BoardSection.test.tsx` (spec Testing) — **and it is explicitly not sufficient**: axe has no SC 2.2.2 rule, so the pause and idle assertions above are the only automated coverage of that criterion and must survive any later tidy-up of "redundant" a11y tests.

---

## 8. PROPOSED decisions — these are what the user is being asked to rule on

- **P-1 — Five seconds, with the freshness line as the honesty valve (spec Q-1).** Ship 5s. The line «עודכן 14:07» is what makes any interval defensible, because the board stops *claiming* to be live and starts *stating* when it last was. If the pilot or F29 says 5s is too expensive, the fix is one client constant and the UI does not change. The prototype lets the user feel 5s and 10s back to back; **10s with the same line reads nearly identically**, which is the honest finding and would halve every number in the spec's Risk 2.
- **P-2 — A board row does not navigate (spec Q-2).** One row, one action, and that action is check-in. The list payload deliberately carries no phone and no notes (F15 D18), so "tap for the full record" means a second fetch and a second entry point into `BookingDetail` with a different lifecycle — and it would make the row a button containing a button, which is an HTML defect and not a style call. The full record is one nav item away in «תורים», and the empty and truncation copy both name it.
- **P-3 — Undo is always visible, never time-boxed (spec Q-3).** The server takes no clock bound on the undo, by an explicit D5 ruling. A time-boxed button would therefore be a **lie the server contradicts**: at minute six the control would be gone while the API still cheerfully accepts the call, and the staffer's only remedy would be to find someone with `psql`. Always-visible is one rule instead of two, and the mis-tap it protects against is one finger wide.
- **P-4 — One chronological list, no expected/here/done bands (spec Q-4).** Bands look like the obvious answer and they are the trap: checking a bride in **moves her row into another band**, so the single act this screen exists for teleports the thing you just touched — on the one screen whose entire design budget goes on not moving under you. They also make ordering ambiguous (arrival order and appointment order disagree the moment somebody arrives early, which is the ordinary case D5 refuses to guard against), and they add two `h3`s and two empty states to a screen that currently needs none. What bands were *for* — "who is waiting, and who is next" — is delivered by the «עכשיו» divider and the «הגיעו 3/12» ratio, neither of which reorders anything. **The prototype renders both on the same rows** so the user can rule with the thing in front of her.
- **P-5 — The board becomes the console's landing section, and F52 implements it.** Every other section is a configuration screen visited rarely; this is the one screen opened fifty times a shift, and pre-decided #27 puts it on a staffer's own phone where "two taps to the thing you came for" is the whole ergonomics. F34 itself does **not** change the default — D10 keeps `"profile"` and F52's queue note owns the landing decision — so this is a recommendation the user's answer binds, not a change this feature makes.
- **P-6 — A stale board is a `--color-warning-text` notice, not a `--color-ink-muted` outage (spec Risk 4, which names this as the user's call).** The inherited register (`manage-restyle.md`) puts an outage in muted, and F15's failed list load obeys it. This state is different in one way that matters: **it leaves plausible-looking data on screen**. Muted grey beside forty rows that look fine is exactly what gets scanned past, and the cost of scanning past it is a staffer acting on a board that stopped updating twenty minutes ago. The escalation is copy, not colour: «עודכן 14:07» becomes «אין עדכון מאז 14:07» plus one explanatory line and a retry. It is still not `text-danger` — nothing here is her fault and nothing here is hers to fix.
- **P-8 — the idle window is 10 minutes, and that number is the only genuinely open question D14 leaves (new in revision 2).** The pause control itself is not up for a ruling — spec D14 makes it a legal requirement and §2.4 specifies it. **The idle window is**, because the criterion says nothing about it and the trade is real in both directions. Too short and a shift manager who watches the board without touching it gets stopped mid-shift and reads the product as broken; too long and the reception tablet's exposure — a live list of named brides' appointments, unattended, for as long as a 12-hour session lasts — is barely reduced. **10 minutes** is the recommendation: longer than any plausible "reading the board" pause, short enough that an unattended counter goes quiet within one customer's fitting. The recovery is one press and the state says exactly why it stopped, so an over-eager window costs a tap, not a mystery — which is why the recommendation errs short rather than long. **The prototype's window is 45 seconds so the state is reachable in a review**, and the prototype bar says so; a reviewer who believes the shipped board stops after 45 seconds would reject the right design for the wrong reason. One constant either way, in one file.
- **P-7 — «הגיעה» as the check-in verb.** It is the exact positive of a word the product already ships: `booking.statusNoShow` is «לא הגיעה» (`copy.md` §3, `he.ts`). The recorded fact is spelled differently on purpose — «נרשמה הגעה · 09:24», a record that was made — so that a booking marked `no_show` **after** a check-in (which D5 explicitly permits, since a status transition never clears `checked_in_at`) renders «לא הגיעה» beside «נרשמה הגעה» as two true facts about different things, rather than as a contradiction. The button and the badge never co-render: check-in is only offered on `confirmed`.

## 9. ⚠ FINDINGS

- **F-1 — RESOLVED, and it is now the spec's own ruling rather than this deck's deviation.** The finding was that D11's parenthetical `aria-hidden` freshness line would make the board's only honesty signal sighted-only — a screen-reader user could never learn the board had stopped updating, on a statutory-AA surface, about the one fact the feature exists to convey. This deck took D11's "or equivalent" and rendered the row plain, readable, reachable and **not** in a live region (§7.1). **The revised spec accepted the reasoning and wrote the outcome into its own a11y floor**, which says in as many words: "the freshness line is readable, reachable and not in a live region rather than `aria-hidden` … The 'or equivalent' is taken (the deck's F-1, accepted)." **Status: agreed, closed, and not a reviewer's decision to re-open.** Retained here as the record of how the ruling was reached — the same reasoning is what would have to be overturned to change it — and no longer as an open deviation to be re-litigated at the gate.
- **F-2 — F15's `booking.error.BOOKING_TRANSITION_INVALID` string is wrong on this screen, and `bookingErrorText` hardcodes the prefix.** Its Hebrew is «…כדאי לחזור לרשימה ולפתוח את התור מחדש» — advice for a detail screen you can back out of. The board has no list to go back to and repairs itself on the next tick. `bookingErrorText(error, t)` (`lib/booking.tsx:63`) resolves `booking.error.<CODE>` unconditionally, so the board cannot supply its own string through it. **Resolution**: `BoardSection` checks that one code before delegating — `error.code === "BOOKING_TRANSITION_INVALID" ? t("board.error.transitionInvalid") : bookingErrorText(error, t)` — one conditional, no change to a shipped shared helper, no new abstraction. Recorded because the general shape (a shared code→string map whose copy is screen-specific) will recur, and the second occurrence is where a `scope` argument earns itself.
- **F-3 — the board's freshness claim can be up to one interval wrong, and no UI can fix that.** «עודכן 14:07» means "this was true at 14:07", not "this is true now", and a staffer reading it at 14:11 is looking at data that may be four seconds stale in the best case. The copy is written to state the weaker claim, and B-stale exists so the strong claim is never made falsely — but a board is a live-*ish* board, and the pilot should be told so in one sentence rather than discovering it. Owner: user. Trigger: pilot onboarding.
- **F-4 — forty rows means forty tab stops and no skip.** Correct (each is a distinct action) and still a long walk for a keyboard-only staffer who wants row 38. The console has no in-page skip pattern beyond the shell's one skip link, and inventing one for this screen would be a system decision above the feature. Recorded against the SMC epic-boundary QA pass; the cheap answer if the pilot complains is a second skip link past the list, not a roving tabindex.
- **F-5 — no he/ar parity guard exists in this repo** (spec Risk 6, F15's F-5 unchanged). `copy.md`'s `ar` column is transcribed into `apps/manage/src/i18n/ar.ts` by hand. The mitigation is unchanged: this deck's copy table is the single source for both columns, so it is one file to one file.
- **F-6 — the prototype's responsive branch is driven by a data attribute, not a media query.** CSS media queries answer to the browser viewport, not to a 375px frame drawn inside a 1440px window, so `prototype.html` selects on `.frame[data-w]`. Production uses Tailwind's real `sm:` branch. Stated so nobody ports the attribute into `.tsx`.
- **F-7 — a live region is written only when its value actually changes, and the first prototype broke that while appearing to keep it.** `textContent =` on a non-empty string replaces the `Text` node whether or not the string differs, so a repaint that re-asserted an unchanged cue was a real mutation inside `role="status"` — re-announcing the last check-in on every five-second tick for the rest of the shift (§7.1, measured with a `MutationObserver`: three identical assignments, three records). Fixed in the prototype with an equality guard at `render()`, the single writer of that node. **What the build inherits, and it is not optional**: (a) the same guard, wherever the cue is written — React's reconciler bails on an identical text child and will *usually* mask this, but "usually" is not a contract on a statutory-AA surface and any hand-rolled `ref.current.textContent` or `aria-live` string re-set reopens it; (b) the spec's planned frontend test — "the announced region does not change on a poll tick" — must drive **several consecutive ticks with the cue already populated** and assert zero mutations, because a single-tick assertion passes against the broken version whenever the cue starts empty.
- **F-8 — a poll tick may not repaint while a finger is down on the board.** An arrival line appearing on an earlier row grows it ≈26px and slides every control below it, which is a moving tap target rather than a moving list position — so §2.3's scroll rule and §7.2's focus rule both miss it. Held-repaint-on-`pointerdown` is the mitigation (§7.2), chosen over reserving row height because the reserved version costs ~1,000px of dead space on a forty-row day. **Caught by the critic pass; it was neither designed against nor acknowledged in the first deck**, which is the honest record. It is behaviour the build must carry, not prototype chrome — noted here because it is the one fix in this pass that adds a mechanism to `BoardSection.tsx` rather than removing a defect from it.
- **F-10 — the 403's «רענון הדף» lands the staffer on another 403, and there is nothing better to offer (new in revision 2).** B-401's reload is a real remedy: it lands on the login screen and she can sign in. B-403's is not — a reload re-enters a console she is still signed into, whose board answers 403 again on its first tick. That is *correct*: it is F31's "a demotion bites on the very next request" behaving exactly as designed. But it means the one button under a terminal message does not fix the terminal condition. **Considered and declined**: hiding the nav item on 403 (the client would be inferring a role from an error the server deliberately keeps generic — `copy.md` §0 rule 10 — and it would be wrong the moment the 403 came from anything else); forcing the login screen (spec D4.3 declines lifting the terminal into `App.tsx`'s `staff` state, and it would discard whatever the owner had typed in another section); and offering no button at all (a dead-end message with no control is worse, and a re-promotion *is* fixed by a reload). **The copy is what closes the gap instead**: `board.accessEnded` points at a person — «לבירור אפשר לפנות לבעלת הבוטיק» — rather than implying the button will help. Recorded so a reviewer finds the reasoning rather than a bug.
- **F-9 — the prototype was missing the shell's skip link.** §7.2's tab order opens with it and `ConsoleShell.tsx:43` ships it (`SkipLink href="#console-main"`, label `console.skipLink` → «דלג לתוכן»), but the first `prototype.html` shell markup jumped straight to the header, so a keyboard reviewer tabbing from a cold load never saw the documented first stop. Added to the prototype; **no production change** — the shell is unchanged and F34 invents no key for it.
