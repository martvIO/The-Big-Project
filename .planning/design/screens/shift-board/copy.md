# Copy deck — F34 Live shift board (`apps/manage`, section «לוח היום»)

**Date**: 2026-07-30 · **Revised**: 2026-07-30 (to the spec's post-adversarial-review revision — D14, D4.3's `{401,403}`, D4(6)'s backoff) · **Status**: **APPROVED under the 2026-07-31 self-approval** (`LOOP-STATE.md:1054`; design gate resolved, `design.md` §8). The Hebrew remains **the user's to edit post-merge** — the F15 P-1/P-5 precedent: a one-line `he.ts`/`ar.ts` edit after merge, never a rebuild. (Drafted for the design gate alongside `prototype.html` under Interview Q2, which named the feature novel; that gate is now closed.) Console copy, not a customer-facing SMS, so there is no counsel gate · **Owner of the Hebrew: the user** · **Consumes**: `.planning/specs/shift-board-checkin.md` (D1–**D14**) and `design.md` in this directory · **Lands in**: `Frontend/apps/manage/src/i18n/he.ts` (`nav.board` + a new `board.*` namespace) **and `…/i18n/ar.ts`**, same keys, Hebrew standing in untranslated.

**What this revision changed, and why each was not optional.** The first draft of this deck was written against the first draft of the spec. Three of its rulings moved underneath it:

| Change | Driver | Rows touched |
|---|---|---|
| **Eight new keys for the pause / resume control and the idle stop** | **spec D14** — WCAG 2.0 **SC 2.2.2 Pause, Stop, Hide is Level A**, IS 5568 / AA is a *legal* bar (pre-decided #38), and axe has no rule for 2.2.2 so it ships green in CI and non-conformant in law. A board with no user-operable pause fails it | §2, new rows |
| **One new key for the 403** | **spec D4.3** — the terminal set is `{401, 403}`. A mid-shift **demotion** ends in 403, not 401, and its body must be **generic**: it may not name the role or say what changed (`auth/dependencies.py:17-21` ships one body for every unadmitted role so a probe cannot learn which roles exist) | §5, new row |
| **`board.error.transitionInvalid` lost the word «מיד»** | **spec D4(6)** — the client now backs the poll off 5s → ~60s on consecutive failures. «הלוח יתעדכן מיד» was true at a fixed five-second beat and becomes a **lie** at a sixty-second one. Restated so it is true at any interval | §6, edited row |

No existing key was deleted and no state was dropped. One string was edited, and it is the one that stopped being true.

**F34 adds no SMS template, sends no message, and touches no `comms_templates.py` body.** There is no §SMS section in this deck and there cannot be one: check-in writes a timestamp and nothing else (spec D8). Nothing on this screen has any occasion to mention the customer being told anything.

## 0. The rules this deck is written under — hard constraints, not preferences

1. **Zero exclamation marks** (pre-decided #5). The product contains none; `he.ts` and every approved deck are mechanically checkable. One here would be the single string that breaks the register.
2. **Never claim, promise or hedge that a message was sent, in any tense.** Trivially satisfied — F34 sends nothing — and stated anyway, because "we let her know she arrived" is the exact sentence a well-meaning editor would add to a check-in cue.
3. **The board states, it does not reassure.** Every string is a fact with a time on it. No «הכל תקין», no «מעולה», no encouragement. A staffer reads this screen fifty times a shift and warmth at that frequency is noise.
4. **Freshness is claimed weakly and honestly.** «עודכן 14:07» says *this was true at 14:07*. Nothing anywhere says «בזמן אמת» or «חי» — the board polls, and a claim it cannot keep even for one interval is worse than the truth (design F-3).
5. **The arrival verb is the exact positive of a word the product already ships.** `booking.statusNoShow` is «לא הגיעה» (`he.ts`, `owner-bookings/copy.md` §3), so the button is «הגיעה» and the recorded fact is «נרשמה הגעה» — deliberately spelled differently so a `no_show` booking that was checked in reads as two true facts, not a contradiction (design P-7).
6. **Every value is a real string.** No `…`-as-placeholder, no Lorem, nothing to be filled in later. The two `…` glyphs in this deck are inside loading strings, where they are the content.
7. **The `ar` column is the approved Hebrew, standing in untranslated** (Interview Q3 / pre-decided #47), and it is **never an empty string**: i18next's `returnEmptyString` default renders `""` rather than falling back, so a premature switch would blank the page instead of showing Hebrew. `lng` stays `"he"`, `fallbackLng` stays `"he"`, no switcher ships.
8. **F34 reuses F15's `booking.*` keys wherever the two screens say the same thing** — the four status words, «אישרה הגעה» — by importing `statusBadge` from `lib/booking.tsx`, not by re-declaring them. A second spelling of «בוטל» in the same console would be a defect.
9. **No string names or implies a retry interval** (spec D4(6)). The client backs off 5s → ~60s on consecutive failures, so «הלוח ינסה שוב בעוד חמש שניות» — the exact sentence a well-meaning editor adds to a stale notice, and the exact sentence a reader wants — becomes false as the backoff grows and there is no honest number to put in it. The stale copy therefore states **what is unknown**, never **when it will be known**. This rule cost one edit (§6) and it is what §7's new register row measures.
10. **The 403 body is generic by design and may not be made specific.** `NotAuthorizedError` ships one body for every unadmitted role (`auth/dependencies.py:17-21`) so a probe cannot learn which roles exist; the client is not told what changed and must not guess. «הרשאות המשמרת שלך בוטלו» or anything naming a role would be an invention the server never made — and on the demotion path it would also be the product telling a staffer she was demoted, which is her manager's sentence to say, not a screen's.

**34 keys** — `nav.board` plus 33 under `board.*`. The first draft had 25; this revision adds **nine** (eight for D14's pause/resume + idle stop, one for D4.3's 403) and **edits one** (§6). Every one is a key F34 invents, and nothing here overwrites or edits an F15 key. §1 carries one further row that is **not** a key — the shell's shipped skip link, listed for the reason given there and marked so it can never be miscounted into the 34.

---

## 1. Navigation and section chrome

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated placeholder) | Status |
|---|---|---|---|---|
| `nav.board` | The seventh console nav item. **«לוח היום» and not «לוח»**: the console already has «תורים» one item away and a bare «לוח» would not say which of the two answers "today". Not «מי כאן» (cute, and wrong on an empty day), not «בזמן אמת» (a claim the poll cannot keep — §0 rule 4) | לוח היום | לוח היום | DRAFTED |
| `board.heading` | The section `h2` | לוח היום | לוח היום | DRAFTED |
| — *(no key)* | The shell's skip link, «דלג לתוכן», is the first tab stop on the page and design §7.2's tab order opens with it. It is **shipped** (`ConsoleShell.tsx:43` → `console.skipLink`, `he.ts:11`) and F34 neither adds nor edits it — listed here only because `prototype.html` was missing it until the critic pass (design **F-9**) and a reader checking the deck against the prototype should find the reason, not a discrepancy | דלג לתוכן | דלג לתוכן | **SHIPPED — reused, not invented** |
| `board.dayLine` | Under the heading. A board with no date picker must still say which day it shows — the moment it matters is a counter tablet at 00:01, where the date rolling under an unattended screen would otherwise be invisible (spec D12) | היום · {{date}} | היום · {{date}} | DRAFTED — `{{date}}` is `jerusalemDate()`, `d.m.yyyy`, inside `<bdi dir="ltr">` |

## 2. The freshness row — the whole live-ness contract, and it is never announced

**The pause / resume control lives in this row and its strings are in this section**, because 2.2.2's mechanism is only legible next to the thing it stops: «עודכן 14:07» is what makes «השהיה» mean something rather than being a mystery button (spec D14).

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `board.summary` | The board's one aggregate: how many of the day's brides have arrived. Counting forty rows by eye does not answer it. **One interpolation**, because the ratio is built client-side as a single `"3/12"` run — so `isolateLtr` (`lib/booking.tsx:32`) is reused unchanged and no second helper is invented | הגיעו {{ratio}} | הגיעו {{ratio}} | DRAFTED — `{{ratio}}` is `"3/12"` inside `<bdi dir="ltr">` |
| `board.updatedAt` | The freshness claim, at the row's inline-end. Changes **only when a fetch succeeds**, so it is a claim the board can keep. Past tense on purpose: it says *this was true at*, never *this is true now* | עודכן {{time}} | עודכן {{time}} | DRAFTED — `{{time}}` is `jerusalemTime()`, `HH:MM`, inside `<bdi dir="ltr">` |
| `board.staleAt` | Replaces `board.updatedAt` after a failed tick, in `--color-warning-text font-semibold` (design **P-6**). The rows are still on screen and still correct as of that time — which is exactly why this needs to be legible rather than muted: plausible-looking data next to a grey notice is what gets scanned past | אין עדכון מאז {{time}} | אין עדכון מאז {{time}} | **APPROVED** (design P-6 resolved: the escalation ships) |
| `board.staleBody` | The line under it. Says what is unknown, not what is wrong — the board cannot tell a dead wifi from a dead server and pretending otherwise would be a guess. No apology, no «אנא» | ייתכן שהמידע אינו עדכני. | ייתכן שהמידע אינו עדכני. | DRAFTED |
| `board.refresh` | The retry button, present in both the stale state and the first-load failure. The board has **no date control to re-poke** (design §0), which is why this control exists here and does not on F15's list | רענון | רענון | DRAFTED |

### 2.1 The pause / resume control and the idle stop — WCAG 2.0 SC 2.2.2, and it is a legal item

**Eight keys, all new in this revision.** Spec **D14**: a board that auto-updates every five seconds, starts on its own and sits beside other content is squarely SC 2.2.2 (Level A, inside AA, and pre-decided #38 makes AA a **legal** requirement). `document.hidden` does not satisfy it — it is automatic, and 2.2.2 asks for a mechanism *the user* can operate. **axe has no rule for 2.2.2**, so no automated check will ever tell us this string is missing.

The visible label is short because it sits inside a 343px line beside two other facts; the accessible name carries the object, and it **starts with the visible label** so WCAG 2.5.3 label-in-name holds — the identical rule and the identical `—` shape as §3's `board.checkInAria`.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `board.pause` | The control's visible label while the board is updating. Two syllables — it shares a 343px line with «הגיעו 3/12» and «עודכן 14:07» (design §5). Not «עצור» (a stop, and this is reversible in one tap), not «הקפאה» (a freeze implies the data froze; the data is fine, the *fetching* stopped) | השהיה | השהיה | **APPROVED** (spec D14) |
| `board.pauseAria` | Its accessible name. «השהיה» alone, in a rotor beside forty «הגיעה» buttons, does not say **what** is paused | השהיה — עדכון הלוח | השהיה — עדכון הלוח | **APPROVED** — `aria-label` only, never rendered |
| `board.resume` | The same control once paused — **one button whose name changes**, not two buttons. Not «רענון»: that word is already taken in this deck for the one-shot retry, and the two acts differ (one fetch now vs. start the beat again) | חידוש | חידוש | **APPROVED** |
| `board.resumeAria` | Same rule | חידוש — עדכון הלוח | חידוש — עדכון הלוח | **APPROVED** — `aria-label` only |
| `board.pausedAt` | Replaces `board.updatedAt` at the row's inline-end whenever the loop is stopped, in `--color-warning-text font-semibold` — **the identical escalation `board.staleAt` gets** (design P-6), for the identical reason: correct-looking rows next to a grey notice are what gets scanned past, and a paused board is easier to forget than a broken one because *she* paused it. Serves both the manual pause and the idle stop; the body line below says which | מושהה · עודכן {{time}} | מושהה · עודכן {{time}} | **APPROVED** — `{{time}}` inside `<bdi dir="ltr">` |
| `board.paused` | The body line under it after a **manual** pause. States the consequence, does not apologise for it and does not thank her for it — she asked for this | העדכון מושהה. הלוח לא יתעדכן עד לחידוש. | העדכון מושהה. הלוח לא יתעדכן עד לחידוש. | **APPROVED** |
| `board.idleStopped` | The body line after the **idle** stop. Names the cause, because the difference between "I paused this" and "this paused itself" is the whole difference between a control and a bug. `{{minutes}}` is one interpolation, so `isolateLtr` is reused unchanged | העדכון הופסק אחרי {{minutes}} דקות ללא פעילות. | העדכון הופסק אחרי {{minutes}} דקות ללא פעילות. | **APPROVED** — `{{minutes}}` inside `<bdi dir="ltr">`; the value is design **P-8** = 10 minutes (plan C3) |
| `board.resumed` | The announced cue on resume, in the existing `role="status"` region. Needed for a real reason and not for symmetry: on resume the button's own accessible name flips, and a screen reader does **not** reliably re-announce the name of a control that is already focused — so without this string the one confirmation a sighted user gets for free is denied to the user 2.2.2 exists for | העדכון חודש. | העדכון חודש. | **APPROVED** |

**What is announced, and what is not.** Pausing, idle-stopping and resuming are all **user-initiated outcomes** (an idle stop is the consequence of her *not* acting, which she still caused), so all three go through the existing `role="status"` cue — exactly what spec D11 admits there, and the same region the check-in cues use. `board.paused` and `board.idleStopped` are announced as the cue **and** rendered as the body line; `board.resumed` is announced only. No new region, no `role="alert"` — nothing here is an emergency.

**Declined: a frequency picker** («כל 5 שניות / כל 10 שניות / השהיה»). Spec D14 declines the mechanism and the copy follows: 2.2.2 is satisfied by *any one* of pause / stop / hide / control-frequency, and a picker is a settings surface, a persisted preference, a second constant and three more strings for a criterion one button closes.

## 3. The row — the action, and the fact it records

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `board.checkIn` | The check-in button, on a `confirmed` booking that has not been checked in. Two syllables, because it lives under a thumb on a 375px phone. The exact positive of the shipped «לא הגיעה» | הגיעה | הגיעה | DRAFTED |
| `board.checkInAria` | The button's accessible name. Forty buttons all named «הגיעה» is a screen-reader dead end, and the name **starts with the visible label** so WCAG 2.5.3 label-in-name holds | הגיעה — {{name}}, {{time}} | הגיעה — {{name}}, {{time}} | DRAFTED — `aria-label` only, never rendered |
| `board.checkedInAt` | The recorded arrival, replacing the button. **«נרשמה הגעה», not «הגיעה»** — a record that was made, so a booking marked `no_show` after a check-in (which spec D5 permits, since a status transition never clears `checked_in_at`) reads «לא הגיעה» beside «נרשמה הגעה · 09:24» as two true facts about different things | נרשמה הגעה · {{time}} | נרשמה הגעה · {{time}} | DRAFTED — `{{time}}` inside `<bdi dir="ltr">` |
| `board.undo` | The undo. Always visible, never time-boxed (design **P-3**): the server takes no clock bound on the undo, so a button that disappeared after five minutes would be a lie the API contradicts | ביטול הרישום | ביטול הרישום | DRAFTED |
| `board.undoAria` | Its accessible name, same rule as `board.checkInAria` | ביטול הרישום — {{name}}, {{time}} | ביטול הרישום — {{name}}, {{time}} | DRAFTED — `aria-label` only |
| `board.now` | The «עכשיו» divider between the last past row and the first future row. `aria-hidden` (design §2.3) — a clock-derived visual landmark, and unhidden it would inject a changing string into the middle of the list every tick, which is the D11 hazard through the back door | עכשיו {{time}} | עכשיו {{time}} | DRAFTED |
| `board.movedAway` | Replaces the control on a row that was rescheduled off today **while it holds focus** — the row is kept until focus moves, so focus is never dropped to `<body>` by something the user did not do (design §7.2) | התור הועבר לתאריך אחר | התור הועבר לתאריך אחר | DRAFTED |

## 4. The announced cues — user-initiated only, and they name the bride

The `role="status"` region carries **nothing the poll produces** (spec D11). Both cues below are the direct consequence of a tap.

**A cue is spoken once per tap, and staying on screen is not speaking again.** Neither string below is cleared on a timer — once tapped, a cue remains visible until the next tap replaces it, which is what lets a staffer look back at it. That is only safe because the region is **written only when its value changes** (design **F-7**): re-asserting an unchanged string into `role="status"` still replaces the text node and still announces, so a five-second repaint that "kept the cue the same" would in fact read «נרשמה הגעה עבור מיכל לוי.» aloud every five seconds until the end of the shift. The copy is written for one hearing; the implementation is what has to make it one hearing.

**They include the customer's name, and F15's detail heading deliberately does not.** F15 kept the name out of `BookingDetail`'s `h2` because that is a *persistent announced landmark*, re-read on every entry to the screen. A cue is the opposite: transient, once, confirming an act on a specific person — and «נרשמה הגעה.» after tapping one of forty rows cannot confirm **which** bride, which makes it useless exactly when the board is busy.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `board.checkedInCue` | After a successful check-in — **and after a no-op 200**, when another staffer got there first and the server kept her timestamp. Identical, deliberately: the outcome the staffer wanted is the outcome that holds, and telling her she lost a race would be telling her she was wrong when she was right (spec D4.5) | נרשמה הגעה עבור {{name}}. | נרשמה הגעה עבור {{name}}. | DRAFTED — `{{name}}` rendered inside a bare `<bdi>` |
| `board.undoneCue` | After a successful undo | הרישום בוטל עבור {{name}}. | הרישום בוטל עבור {{name}}. | DRAFTED |

## 5. States

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `board.loading` | Carried by the `role="status"` cue region on the **first** load only. The shipped console announces nothing while loading; F34 closes that for itself by reusing the region it already needs (F15 design F-1) | טוען את לוח היום… | טוען את לוח היום… | DRAFTED |
| `board.loadFailed` | The **first** fetch failed and there is nothing on screen. The **outage** register — recoverable, unblaming, no technical words | לא הצלחנו לטעון את הלוח כרגע. | לא הצלחנו לטעון את הלוח כרגע. | DRAFTED |
| `board.emptyTitle` | `EmptyState` title on a day with no bookings. A fact, not a fault, and **not** «אין מה לעשות» | אין תורים היום | אין תורים היום | DRAFTED |
| `board.emptyBody` | The body. **No CTA** — the owner cannot create a booking (Interview Q6), so an action prompt would point at nothing. Names «תורים» as where other days live, which is also the answer to "where is the rest of it" everywhere else in this deck | תורים שייקבעו להיום יופיעו כאן. לתאריכים אחרים אפשר לעבור למסך «תורים». | תורים שייקבעו להיום יופיעו כאן. לתאריכים אחרים אפשר לעבור למסך «תורים». | DRAFTED |
| `board.truncated` | `total > items.length`. **Stated, never absorbed** — a hidden bride is the one failure a board may not have (spec D3). One interpolation, so `isolateLtr` is reused unchanged | מוצגים {{count}} התורים הראשונים של היום. לרשימה המלאה אפשר לעבור למסך «תורים». | מוצגים {{count}} התורים הראשונים של היום. לרשימה המלאה אפשר לעבור למסך «תורים». | DRAFTED — `{{count}}` inside `<bdi dir="ltr">` |
| `board.sessionEnded` | A tick answered **401** and **the loop stopped**. `role="alert"`, one of the two assertive announcements in the feature. The session outlives a shift by design (`session_ttl_seconds = 43200`, no sliding renewal), so the realistic reader is a tablet that was left on the counter overnight — the copy must be a plain instruction, not an alarm | תוקף החיבור פג. צריך להתחבר מחדש. | תוקף החיבור פג. צריך להתחבר מחדש. | DRAFTED |
| `board.accessEnded` | A tick answered **403** and the loop stopped — the **mid-shift demotion** (spec D4.3). New in this revision; the first draft's terminal set was `{401}` and this state did not exist. **It is deliberately generic**: §0 rule 10 — no role is named, nothing is said about what changed, and the copy does not claim the change is permanent. «כרגע» is doing real work: a re-promotion restores the board, so a sentence implying the door is shut for good would be a guess the server never made. Points at a person rather than at a retry, because there is nothing here she can fix from this screen | אין הרשאה לצפות בלוח כרגע. לבירור אפשר לפנות לבעלת הבוטיק. | אין הרשאה לצפות בלוח כרגע. לבירור אפשר לפנות לבעלת הבוטיק. | **APPROVED** (spec D4.3) |
| `board.reload` | The button beside **both** of the two above. Says what it does. On the 401 a reload lands on the login screen; on the 403 it lands on a console whose board answers 403 again — which is the honest behaviour of F31's "a demotion bites on the very next request" and is recorded as design **F-10**, not papered over | רענון הדף | רענון הדף | DRAFTED |

## 6. Errors — one owned string, everything else falls through

**Design finding F-2.** `bookingErrorText(error, t)` (`lib/booking.tsx:63`) resolves `booking.error.<CODE>` unconditionally, and F15's Hebrew for `BOOKING_TRANSITION_INVALID` is «…כדאי לחזור לרשימה ולפתוח את התור מחדש» — advice for a detail screen you can back out of. The board has no list to back out to and repairs itself on the next tick, so it owns **one** replacement string and delegates everything else to the shared helper unchanged. No new helper, no `scope` argument, no second map.

| Key | Raised by | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `board.error.transitionInvalid` | 409 `BOOKING_TRANSITION_INVALID` — check-in on a booking somebody cancelled in the gap between the last tick and the tap. Renders **inside that row**, `--color-danger`, because a page-level error on a forty-row board names no bride. Tells her the board will fix itself, because it will — but **no longer says when** | מצב התור השתנה. השורה תתוקן בעדכון הבא. | מצב התור השתנה. השורה תתוקן בעדכון הבא. | **REVISED** — was «…הלוח יתעדכן מיד.» |

**Why «מיד» had to go, and it is the only string this revision edited.** Spec **D4(6)** gives the client a failure backoff: consecutive failed ticks stretch the interval 5s → ~60s and the first success resets it. «הלוח יתעדכן מיד» was written against a fixed five-second beat, where it was true. It is reachable in exactly the state where it stops being true — a staffer taps during an outage, the board is already stale and already backed off to a minute, and the string promises her an update that is up to sixty seconds away. A row-level error that lies about its own repair is worse than one that says nothing about timing, so it now names the **event** («בעדכון הבא») rather than a **duration**. That phrasing is true at 5s, at 60s, and at whatever a later F29 constant makes it — which is §0 rule 9 in one sentence.

Every other code — `NOT_FOUND`, `VALIDATION_ERROR`, anything unmapped — falls through to `bookingErrorText`, i.e. to F15's map for the codes it owns and to the server's own text otherwise. **F34 adds no error code** (spec D7: `SPEC_ERROR_CODES` stays set-equal and unchanged).

---

## 7. Register check — the mechanical pass

| Rule | Result |
|---|---|
| Exclamation marks in this deck | **0** |
| Strings claiming, implying or hedging an SMS send (any tense) | **0** — the feature sends nothing and says nothing about sending |
| Strings claiming the board is realtime / live / instant | **0** — «עודכן {{time}}» is past tense by construction; «בזמן אמת» appears nowhere |
| Strings naming or implying a **retry interval** (§0 rule 9, spec D4(6)) | **0** — one string said «מיד» and was revised (§6). `staleBody` states what is unknown; `transitionInvalid` names the next event, not a duration; nothing anywhere says «חמש שניות» |
| Strings naming a **role**, or saying what changed, on the 403 (§0 rule 10) | **0** — `board.accessEnded` says only that there is no permission and who to ask |
| Strings for the 2.2.2 mechanism (spec D14) | **8** — `pause` / `pauseAria` / `resume` / `resumeAria` / `pausedAt` / `paused` / `idleStopped` / `resumed`. **This row is the point of the revision**: at zero the product ships green in CI and non-conformant in law, because axe has no SC 2.2.2 rule |
| Strings that blame the staffer | **0** — `staleBody` states what is unknown; `loadFailed` is first-person-plural and unblaming; `sessionEnded` is an instruction |
| Money words | **0** — deposits are E4 |
| Reassurance / encouragement copy | **0** — §0 rule 3 |
| Placeholders, Lorem, `…`-as-content | **0** — the one `…` is inside `board.loading`, where it is the content |
| `ar` values that are empty strings | **0** — every row carries the Hebrew as its placeholder |
| Keys that overwrite or edit an F15 key | **0** — the four status words and «אישרה הגעה» are **reused** via `statusBadge`, not re-declared |
| Strings a poll tick can cause to be **announced** | **0** — and this is now a measured claim, not a stated one. Five strings ever enter a live region (`checkedInCue`, `undoneCue`, and D14's `paused` / `idleStopped` / `resumed`), and **none of the five is reachable from a tick**: the first four are the direct consequence of a tap, and the idle stop is the consequence of her not tapping — the timer that fires it is the user's own inactivity, not the poll. `render()` writes that node only when its value changes, so a repaint carrying an unchanged cue produces zero mutation records (design **F-7**). Verified in `prototype.html`: one record from the tap, none from the three ticks after it |
| Interpolations needing more than one LTR isolation per string | **0** — `board.summary` passes the ratio as one `"3/12"` run, so `isolateLtr` is reused unchanged |
