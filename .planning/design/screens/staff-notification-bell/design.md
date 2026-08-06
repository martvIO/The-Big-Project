# Screen: Staff notification bell (F35 — `ConsoleShell` header slot + panel, Epic E6)

**Date**: 2026-08-06 · **Status**: DESIGN GATE OPEN — awaiting critic + copy approval · **Designer**: Claude (design subagent)
**Consumes**: `.planning/specs/staff-notification-bell.md` (Gate 1 standing-approved) · tokens rev 1 · `packages/ui` as shipped
**Copy**: every Hebrew row below needs APPROVAL. Register: calm, feminine address, **no exclamation marks** (pre-decided #5).

---

## 0. Scope

One new chrome control in the manage console, reachable from all 18 sections and all five staff roles, plus its panel. `ConsoleShell` (`packages/ui`) gains `bell?: ReactNode`; `NotificationBell.tsx` (`apps/manage/src/components/`) fills it, reading `unreadNotifications` + `markRead(ids)` off the extended `SosContextValue`. **No new timer** — the count rides the SOS tick's payload (spec §Delivery). Out of scope: the customer bell (F24, a different app), deep links to a row, per-staffer preferences, browser push (#32).

**Binding inheritances, obeyed not restated.** F-W1 (`Button size="sm"` = 36px, **fails** the 44px floor — `md` only for touch controls). DL20 / `ConsoleShell.tsx:53-68` (chrome controls are bare `<button>` with `min-h-11 px-2` + `focusRing`, transparent background, **the visible Hebrew word is the name** — the console ships no icon-only control). R19 bidi isolation (`<bdi dir="ltr">` around every numeral). F37's live-surface law: **absolute times only, never a counter** — which is what keeps SC 2.2.2 inapplicable here. The house failure vocabulary `{ns}.loadFailed` + `{ns}.retry` («ניסיון נוסף», verbatim across the console). Jerusalem formatting through the two shipped helpers in `lib/jerusalem.ts` — no new date code.

## 1. The control — header slot, RTL order, sizing

Rendered as the **first child of the existing chrome wrapper `div`**, before `{guide}` (the wrapper is why the row does not re-spread — see the ⚠ at `ConsoleShell.tsx:53`). RTL reading order, right to left:

```
|  יציאה      מדריך      התראות ③                                 שם הבוטיק  |
|  └ logout   └ guide    └ bell (NEW), inline-start of the chrome group      |
|  ─────────────────────────────────────────────────────────────────────────  |
|  לוח היום · תורים · לקוחות …                                    ← nav row   |
```

- **A bare `<button type="button">`, `min-h-11 min-w-11 px-2 text-sm text-ink-muted hover:text-ink` + `focusRing`** — the logout button's line, character for character. Transparent, so the 44px box is invisible and the header still reads as text labels beside a wordmark. **No `Button` component and no `size="sm"`** (F-W1).
- **Visible text «התראות», not an icon.** DL20's ruling on the sibling `guide` slot: the visible word IS the name. An icon-only bell would be this console's first, and would ship an `aria-label` that no sighted user can verify against.
- **Badge**: `<bdi dir="ltr">` digit inside a `Badge variant="neutral"`, `ms-1`, `aria-hidden` — capped at «9+» (the portal bell's cap, and it is what keeps the 44px box from growing). **The exact count is in the accessible name, uncapped.** Zero unread renders **no badge at all**, not a «0».
- The badge never signals by colour: it carries the digit, and the word «התראות» is beside it either way.
- **Header at 375px**: the third control takes the chrome group to ~204px. The row degrades by **wrapping the wordmark to a second line**, never by overflowing — assert no horizontal scroll at 375 with a long `display_name` (F-B2).

## 2. The panel — `Modal` from `packages/ui`

Native `<dialog>`: focus trap, Esc, backdrop dismiss and focus-return to the bell are free (spec §UI contract). `title={t("bell.title")}`, `w-[min(28rem,calc(100vw-2rem))]`.

```
+---------------------------------------------------+
|  התראות                                            |  Modal title, font-display text-xl
|  ------------------------------------------------- |
|  | דנה כהן הפנתה אליך לקוחה          [חדש]  14:32 | |  row = <button>, min-h-11, semibold
|  | רותם לוי העבירה אליך חדר                 13:05 | |  read row: normal weight, muted time
|  | מיכל ביקשה עזרה                    [חדש]  12:40 | |  sos row: NOT a button (§3)
|  |  …                                              | |
|  מוצגות 20 ההתראות האחרונות                        |  cap note, only when items.length === 20
|                          [ סמני הכל כנקרא ] [ סגירה ] |  footer: secondary md · ghost md
+---------------------------------------------------+
```

- Items are `created_at` DESC, **hard cap 20, no pagination, no cursor**. The cap note renders only when the page is full — an honest statement of the ceiling, not a permanent footnote.
- The list is a `<ul>`; each item an `<li>`. Rows separated by a `border-t border-border` hairline, not by a card each — 20 cards in a 448px dialog is a scroll of chrome.
- Scroll: `max-h-[60vh] overflow-y-auto` on the list, so the footer's two buttons never leave the viewport at 375.
- **«סמני הכל כנקרא» sends the rendered page's ids only** (spec §API: one verb, `ids=<the page>`), and is hidden entirely when nothing on the page is unread.

## 3. Rows — content, time, read state, what a click does

| `kind` | Row copy | Click target |
|---|---|---|
| `dispatch_assigned` | `bell.kindDispatch` — «{{name}} הפנתה אליך לקוחה» | mark read + **navigate to the floor** (§F-B1) |
| `room_handed_over` | `bell.kindHandover` — «{{name}} העבירה אליך חדר» | same |
| `sos_targeted` | `bell.kindSos` — «{{name}} ביקשה עזרה» | **none — not a link.** The live surface is F37's overlay, which owns itself |
| any, `actor_name === null` | `bell.kindUnknownActor` — «התקבלה התראה» | as per kind above |
| unknown/future kind | row is **skipped entirely** — no raw enum ever reaches the screen | — |

- **No customer datum ever appears in a row** — no name, no phone, no ticket. The row says *who did what to you*; the floor screen, under its own audience rules, says who she is (spec §Data model).
- **Time is absolute and Jerusalem-local**, `<bdi dir="ltr">`: `jerusalemTime()` → `14:32` for rows from today (`jerusalemIsoDate(created_at) === todayJerusalem()`), `jerusalemDate()` + time → `4.8.2026 14:32` for older ones. **Never a relative counter** («לפני 3 דקות») — F37 forbids live counters on this surface, and a static "3 minutes ago" that silently ages is worse than either.
- **Unread is marked twice, never by colour**: `font-semibold` on the text **and** a `Badge variant="neutral"` «חדש». Read rows are normal weight with no badge; the time is `text-ink-muted` on both.
- **Interactive rows are whole-row `<button className="min-h-11 w-full text-start">`**; `sos_targeted` rows are plain `<li>` text — a row that looks tappable and does nothing is the lie this split avoids. SOS rows are cleared by «סמני הכל כנקרא».
- **The click sequence, in this order**: `markRead([id])` (optimistic) → `onOpenFloor()` → close the Modal → `document.getElementById("console-main")?.focus()`. The focus move comes **after** `close()`, which synchronously returns focus to the bell — otherwise the staffer lands on a chrome button above a section she did not ask for. `SosOverlay.tsx:230` is the shipped precedent for the same move.

## 4. States

| # | State | Trigger | What she sees | Test hook |
|---|---|---|---|---|
| D | idle, nothing unread | count 0 | «התראות», no badge; accessible name `bell.label` | no badge in DOM |
| U | unread | count > 0 | badge digit (9+ capped); accessible name carries the exact count | name asserts count |
| L | opening | panel mounted, GET in flight | 3 `Skeleton` rows inside the dialog; no announcement (the dialog title is the announcement) | skeleton present |
| P | populated | 200 | §2/§3 | rows render |
| E | empty | `items: []` | one muted line `bell.empty` — «אין התראות», its `useId` passed to `Modal`'s optional `describedById` so the sentence is the dialog's accessible description and is read with the title (§5). Not an `EmptyState`: 140px announcing calm would make the absence the point (`sos.centreEmpty`'s ruling) | `aria-describedby` resolves to the `bell.empty` line |
| C | capped | `items.length === 20` | cap note above the footer | note conditional |
| F1 | list load failure | GET 5xx / network | inside the panel: `bell.loadFailed` (muted) on a `role="alert"` line + `Button secondary md` `bell.retry`. **Immediate and unconditional, on the first render as on every retry** — the house `{ns}.loadFailed` shape (`CheckinQrSection.tsx:51` is the identical message-then-retry pair; `BookingsSection.tsx:126`, `BoardSection.tsx:382`/`535`, `CustomersSection.tsx:140`, `DressEditor.tsx:146`, `GatewaySection.tsx:102`, `HoursSection.tsx:61`, `ProfileSection.tsx:70`, `DashboardSection.tsx:113`, `CatalogSection.tsx:162`, `AtelierSection.tsx:1126` are the rest, and **not one** distinguishes a first load from a retry), and the shape F2 already uses one row down | `role="alert"` asserted on first render |
| F2 | mark-read rejected | POST 5xx / network | optimistic zero **rolls back** — rows return to unread, badge returns; `bell.markFailed` on a `role="alert"` line in the panel | rollback asserted |
| K | channel down | `channelDown` from the SOS poll | the badge **keeps its last value and is not cleared** (never invent a count, never zero one). **No second notice on the bell** — the app-wide `sos.channelDown` strip already says the channel is dead, and two notices for one outage is noise. The panel's own GET is independent and still works | strip only |
| X | session ended | poll 401/403 | `onSessionEnded` drops the whole console to the login form; the bell unmounts with it. Nothing bell-specific to word | existing path |

## 5. Keyboard + screen-reader contract

- **Tab order in the header**: skip link → bell → מדריך → יציאה → nav. The bell is first in the chrome group because it is first in DOM order; no `tabindex` anywhere.
- **The panel is a dialog, not a menu.** No `role="menu"`, no arrow-key contract, no roving tabindex — `Modal`'s native `<dialog>` gives trap + Esc + focus return, and a menu would owe a keyboard contract nothing here needs.
- **No `aria-haspopup`** — bare, it is synonymous with `"menu"`, which this is not (`A11yMenu.tsx:116` + `chrome-composites.test.tsx:107` are the shipped ruling). **No `aria-expanded`**: a modal dialog is not a disclosure.
- **The count lives in the accessible name and nowhere else.** `aria-label` = `bell.label` with no unread, `bell.labelUnread` with. The visible «התראות» is the name's prefix, so WCAG 2.5.3 holds. **No `role="status"` and no `aria-live` on the badge** — a 5-second-cadence live region narrating a count is the hostility F58's r3 caught, and SC 4.1.3 is WCAG 2.1, outside IS 5568 / WCAG 2.0 AA.
- **Focus**: open → `showModal()` puts focus on the dialog's first **focusable control** — never on a paragraph (`Modal.tsx:33-41`, children before footer at `:62-63`); Esc/close/backdrop → back to the bell; a row click → `#console-main` (§3).
- **A state whose point is a sentence must carry its own announcement.** Because focus lands on a control, a plain `<p>` is stepped over: in F1 she would hear «התראות» then «ניסיון נוסף, button» (the retry is the first focusable child), in E «התראות» then «סגירה, button» — the reason and the emptiness both silent. `Modal.tsx:16-19` names this failure verbatim in its own doc comment. Two shipped remedies, one per state, and the choice is semantic: **F1 takes `role="alert"`** on `bell.loadFailed`, immediately and on first render, matching every `{ns}.loadFailed` in the console and F35's own F2 (§4). **E takes `describedById`** — the `bell.empty` line's `useId` into `Modal`'s optional prop, so «אין התראות» is read as the dialog's description alongside its name; `GuideOverlay.tsx:186/236` is the shipped precedent for exactly this shape (a body sentence followed by footer buttons and no other focusable input). `role="alert"` would be wrong for E: an empty list is a condition, not an event. Under this rule no panel state renders text that only a sighted staffer receives, which is what the IS 5568 / WCAG 2.0 AA gate asks of the surface.
- **Targets**: bell 44×44; every row `min-h-11`; footer buttons `md` — no `sm` anywhere in this feature (F-W1).
- ⚠ jsdom has no `<dialog>`; `setup.ts` stubs `showModal()`, so a focus assertion that pre-places focus on its own target is vacuous. Assert the panel's **content** in unit tests and leave real focus behaviour to the e2e leg.

## 6. RTL + responsive

Logical properties only (`ms-1`, `text-start`, `border-t`) — the qa-greps physical-direction ban applies. LTR islands: the badge digit and every row time, each a `<bdi dir="ltr">`. The actor name is a **bare `<bdi>`** — `dir="ltr"` on a Hebrew name is itself a bug (`BookingsSection.tsx:171`'s note).

375: header wraps the wordmark if needed (§1); dialog is 343px wide; footer buttons stay on one row (two short labels). 768 / 1440: no deltas — the dialog is width-capped at 28rem and centred at every size. Reduced motion: `Modal`'s shipped panel/backdrop animation already respects it; the bell adds no motion of its own.

## 7. i18n keys — manage `bell.*` (he.ts; ar.ts mirrors with the Hebrew values, pre-decided #47)

| Key | Hebrew | English annotation |
|---|---|---|
| `bell.label` | התראות | "Notifications" — visible label AND accessible name with nothing unread |
| `bell.labelUnread` | התראות, {{count}} חדשות | "Notifications, {{count}} new" — accessible name only; count uncapped here |
| `bell.title` | התראות | panel heading (`Modal` title) |
| `bell.unreadMarker` | חדש | "New" — the per-row badge; the second, non-colour signal beside weight |
| `bell.kindDispatch` | {{name}} הפנתה אליך לקוחה | "{{name}} sent a customer to you" |
| `bell.kindHandover` | {{name}} העבירה אליך חדר | "{{name}} handed a room over to you" |
| `bell.kindSos` | {{name}} ביקשה עזרה | "{{name}} asked for help" |
| `bell.kindUnknownActor` | התקבלה התראה | "A notification arrived" — only when the actor's staff row is gone entirely |
| `bell.empty` | אין התראות | "No notifications" — muted line inside the open panel |
| `bell.capNote` | מוצגות 20 ההתראות האחרונות | "Showing the latest 20 notifications" — only on a full page |
| `bell.markAll` | סמני הכל כנקרא | "Mark all as read" — sends the rendered page's ids, never a true mark-all |
| `bell.close` | סגירה | "Close" |
| `bell.loadFailed` | לא הצלחנו לטעון את ההתראות כרגע. | "We could not load the notifications right now." — house `{ns}.loadFailed` shape |
| `bell.retry` | ניסיון נוסף | "Try again" — reused verbatim from `booking.retry` / `checkinQr.retry`, no drift |
| `bell.markFailed` | לא הצלחנו לסמן כנקרא כרגע. | "We could not mark them read right now." — announced on the rollback |

Zero exclamation marks. No key names or implies a retry interval (§0 rule 9 of the console copy law).

## 8. What this surface deliberately does not have

No polling of its own (the count rides the SOS tick) · no icon-only control · no live region on the count · no relative time anywhere · no colour-only unread state · no pagination, cursor or "load more" · no per-kind filter · no per-row dismiss or delete (`deleted_at` has no v1 writer) · no deep link to a specific room or alert row · no customer name, phone or ticket id, ever · no notification for a role-routed SOS (spec §Producers — the bell under-reports those by decision, and C3 is what makes that survivable) · no bell on the storefront (that is F24, no dependency either way).

## 9. PROPOSED (user confirms at the gate)

- **P1 — the control carries the visible word «התראות», not a bell glyph.** Spec §UI contract implies an icon-only button with an `aria-label`; DL20 and both shipped chrome siblings say the visible Hebrew word IS the name. Visible-text + `aria-hidden` badge satisfies both: the name is «התראות, 3 חדשות», which starts with the visible label.
- **P2 — SOS rows are text, not buttons.** They are the one kind with no destination, and an identical-looking row that only marks itself read would be an affordance that lies.
- **P3 — the badge caps at «9+» while the accessible name stays exact.** The badge is decoration (`aria-hidden`); the truth is in the name, so the cap costs nothing and keeps the 44px box from growing.
- **P4 — a row click parks focus on `#console-main`, not back on the bell.** The mover rule: the state change that mounted the target is the mover, and the target is the floor section.

## 10. ⚠ FINDINGS

- **F-B1 — «navigate to `floor`» is not universally reachable, and the spec states it flatly.** `App.tsx`'s NAV gives `floor` to `FLOOR_ONLY`; the owner and shift manager reach the same panel under `board` («לוח היום»). Both can be dispatch/handover recipients, so an unconditional `setSection("floor")` would land an owner on a section her nav does not contain. **Fix, one line in `App.tsx` and none in the bell**: `bell={<NotificationBell onOpenFloor={() => setSection(reachable.some(i => i.key === "floor") ? "floor" : "board")} />}`. The bell stays dumb; App already owns `reachable`.
- **F-B2 — the third chrome control is a 375px header risk.** ~204px of chrome plus 32px gutters leaves ~139px for `display_name`. It degrades by wrapping, not overflowing — but the e2e leg must assert **no horizontal scroll at 375** with a long boutique name, in both the badged and unbadged states.
- **F-B3 — `bell.kindUnknownActor` erases the kind.** A nameless row reads «התקבלה התראה» for all three kinds. Accepted for v1 because the trigger is rare (the actor's staff row deleted outright) and the spec pinned the string; the upgrade is three nameless variants and no code change.
- **F-B4 — `ConsoleShell`'s existing tests must pass with a zero-line diff when `bell` is omitted** (the `guide` extraction's acceptance gate, reused). Omitting the prop writes no node at all.

---

Design Gate: accepted by design-critic, 2026-08-06
